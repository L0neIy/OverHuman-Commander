import ccxt
import pandas as pd
import csv
import os
from math import floor
from abc import ABC, abstractmethod
from datetime import datetime
from dotenv import load_dotenv

# ===============================
# Load .env
# ===============================
load_dotenv()

EXCHANGE = os.getenv("EXCHANGE", "binance")
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
PASSPHRASE = os.getenv("PASSPHRASE", "")

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
SANDBOX = os.getenv("SANDBOX", "true").lower() == "true"

# 🔥 log เก็บลง /data เสมอ
LOG_DIR = "data"
os.makedirs(LOG_DIR, exist_ok=True)
PAPER_LOG = os.path.join(LOG_DIR, "paper_trades.csv")


# ===============================
# Base Broker
# ===============================
class Broker(ABC):
    @abstractmethod
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int):
        pass

    @abstractmethod
    def get_price(self, symbol: str) -> float:
        pass

    @abstractmethod
    def place_order(self, symbol: str, side: str, size: float, price: float = None, stop: float = None, take: float = None):
        pass


# ===============================
# CCXT Broker with Paper Mode + Report
# ===============================
class CCXTBroker(Broker):
    def __init__(self, exchange=EXCHANGE, api_key=API_KEY, api_secret=API_SECRET,
                 sandbox=SANDBOX, paper_mode=DRY_RUN, paper_log=PAPER_LOG):
        self.paper_mode = paper_mode
        self.paper_log = paper_log
        self.paper_trades = []

        self.ex = getattr(ccxt, exchange)({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'future'},
        })

        if sandbox and exchange == 'binance':
            self.ex.urls['api'] = {
                'fapiPublic': 'https://testnet.binancefuture.com/fapi/v1',
                'fapiPrivate': 'https://testnet.binancefuture.com/fapi/v1',
            }
            self.ex.has['fetchCurrencies'] = False
            self.ex.set_sandbox_mode(True)

        self.markets = self.ex.load_markets()
        self.hedge_mode = True if sandbox else self._check_hedge_mode()

        # prepare paper log
        if self.paper_mode:
            if not os.path.exists(self.paper_log):
                with open(self.paper_log, mode="w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["timestamp", "symbol", "side", "size", "price", "status"])

    def _check_hedge_mode(self) -> bool:
        try:
            account_info = self.ex.fapiPrivateGetAccount()
            if 'hedgeMode' in account_info:
                return account_info['hedgeMode']
            positions = account_info.get('positions', [])
            for pos in positions:
                if pos.get('positionSide') in ['LONG', 'SHORT']:
                    return True
            return False
        except Exception:
            return False

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int):
        o = self.ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(o, columns=['timestamp','open','high','low','close','volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df

    def get_price(self, symbol: str) -> float:
        t = self.ex.fetch_ticker(symbol)
        return float(t['last'])

    def _round_amount(self, symbol: str, amount: float) -> float:
        m = self.markets.get(symbol, {})
        filters = m.get('info', {}).get('filters', [])
        step, min_qty = 0, 0
        for f in filters:
            if f.get('filterType') == 'LOT_SIZE':
                step = float(f.get('stepSize', 0))
                min_qty = float(f.get('minQty', 0))
        if step > 0:
            amount = floor(amount / step) * step
        if min_qty > 0 and amount < min_qty:
            amount = min_qty
        precision = m.get('precision', {}).get('amount')
        if precision is not None:
            scale = 10 ** precision
            amount = floor(amount * scale) / scale
        return float(amount)

    def place_order(self, symbol: str, side: str, size: float, price: float = None, stop: float = None, take: float = None):
        if size <= 0:
            return None
        amt = self._round_amount(symbol, size)
        if amt <= 0:
            return None

        if self.paper_mode:
            trade_price = price if price else self.get_price(symbol)
            record = {
                "timestamp": datetime.utcnow().isoformat(),
                "symbol": symbol,
                "side": side,
                "size": amt,
                "price": trade_price,
                "status": "FILLED"
            }
            self.paper_trades.append(record)
            with open(self.paper_log, mode="a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([record["timestamp"], record["symbol"], record["side"],
                                 record["size"], record["price"], record["status"]])
            return record

        params = {}
        if self.hedge_mode:
            params['positionSide'] = 'LONG' if side.lower()=='buy' else 'SHORT'

        try:
            order = self.ex.create_order(symbol, type='market', side=side, amount=amt, params=params)
            return order
        except Exception as e:
            print(f"[Order Error] {symbol} {side} {amt}: {e}")
            return None

    def get_paper_report(self):
        if not os.path.exists(self.paper_log):
            return {"error": "No paper log found"}

        df = pd.read_csv(self.paper_log)
        if df.empty or len(df) < 2:
            return {"error": "Not enough trades to calculate report"}

        df["pnl"] = 0.0
        equity_curve = [0.0]
        for i in range(1, len(df)):
            entry = df.iloc[i-1]
            exit_trade = df.iloc[i]
            if entry["symbol"] != exit_trade["symbol"]:
                continue
            if entry["side"].lower() == "buy":
                df.at[i, "pnl"] = (exit_trade["price"] - entry["price"]) * entry["size"]
            elif entry["side"].lower() == "sell":
                df.at[i, "pnl"] = (entry["price"] - exit_trade["price"]) * entry["size"]
            equity_curve.append(equity_curve[-1] + df.at[i, "pnl"])

        total_pnl = df["pnl"].sum()
        wins = (df["pnl"] > 0).sum()
        losses = (df["pnl"] < 0).sum()
        trades = wins + losses
        winrate = (wins / trades * 100) if trades > 0 else 0
        avg_pnl = df["pnl"].mean()
        per_symbol = df.groupby("symbol")["pnl"].sum().to_dict()
        gross_profit = df[df["pnl"] > 0]["pnl"].sum()
        gross_loss = -df[df["pnl"] < 0]["pnl"].sum()
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")
        equity_series = pd.Series(equity_curve)
        rolling_max = equity_series.cummax()
        drawdown = rolling_max - equity_series
        max_drawdown = drawdown.max()

        return {
            "trades": trades,
            "wins": int(wins),
            "losses": int(losses),
            "winrate": f"{winrate:.2f}%",
            "total_pnl": round(total_pnl, 4),
            "avg_pnl": round(avg_pnl, 4),
            "per_symbol": per_symbol,
            "profit_factor": round(profit_factor, 2),
            "max_drawdown": round(max_drawdown, 2),
        }


# ===============================
# Instantiate Broker
# ===============================
broker = CCXTBroker()

if __name__ == "__main__":
    print("BTC Price:", broker.get_price("BTC/USDT"))
    broker.place_order("BTC/USDT", "buy", 0.001)
    report = broker.get_paper_report()
    print(report)
