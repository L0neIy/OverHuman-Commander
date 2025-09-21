import sys
import os
import time
import pandas as pd
from dotenv import load_dotenv
from math import floor
from datetime import datetime
import pytz

# --- fix path ---
project_path = os.path.dirname(os.path.abspath(__file__))
if project_path not in sys.path:
    sys.path.insert(0, project_path)

# --- imports ---
from config import CFG
from broker import CCXTBroker
from regime import RegimeDetector
from experts.trend import TrendFollower
from experts.mean_revert import MeanRevert
from experts.breakout import Breakout
from experts.pullback import TrendPullback
from experts.vol_squeeze import VolSqueezeBreakout
from meta import MetaLearner
from risk import RiskGovernor
from utils import atr_wilder
from trade_selectors import rank_by_momentum, pick_diversified
from logger import CommanderLogger
from utils_sizing import compute_sl_tp, position_size_by_risk
from autoscaler import AutoScaler

logger = CommanderLogger()
load_dotenv()

CAPITAL_TOTAL = float(os.getenv('CAPITAL_TOTAL', '10000'))
# initial defaults (will be overridden by autoscaler at runtime)
RISK_PER_TRADE = float(os.getenv('RISK_PER_TRADE', '0.01'))  # fraction per trade (used as cap)
MAX_POSITIONS = int(os.getenv('MAX_POSITIONS', '4'))
MAX_GROSS_EXPOSURE = float(os.getenv('MAX_GROSS_EXPOSURE', '0.6'))
MAX_RISK_PER_DAY = float(os.getenv('MAX_RISK_PER_DAY', '0.02'))
MAX_PER_BUCKET = int(os.getenv('MAX_PER_BUCKET', '2'))

# helper: map strength -> crude prob (calibrated later via backtest)
def strength_to_prob(strength: float) -> float:
    return max(0.45, min(0.66, 0.46 + 0.2 * strength))

def pass_filters(df: pd.DataFrame, direction: int) -> bool:
    if df is None or len(df) < 50:
        return False
    ema50 = df['close'].ewm(span=50).mean().iloc[-1]
    ema200 = df['close'].ewm(span=200).mean().iloc[-1]
    trend_ok = (direction > 0 and ema50 > ema200) or (direction < 0 and ema50 < ema200)

    atr = float(df.get('atr14', pd.Series([0.0])).iloc[-1] or 0.0)
    volp = atr / max(df['close'].iloc[-1], 1e-9)
    vol_ok = (0.01 <= volp <= 0.06)

    delta = df['close'].diff().fillna(0)
    up = delta.clip(lower=0).rolling(14).mean()
    down = -delta.clip(upper=0).rolling(14).mean()
    rs = (up / (down + 1e-9)).replace([float('inf')], 0)
    rsi = 100 - (100 / (1 + rs))
    rsi_latest = float(rsi.iloc[-1]) if not rsi.isna().iloc[-1] else 50
    mom_ok = (direction > 0 and rsi_latest >= 55) or (direction < 0 and rsi_latest <= 45)

    return trend_ok and vol_ok and mom_ok

# timezone helper
BANGKOK = pytz.timezone("Asia/Bangkok")
def now_thai():
    return datetime.now(BANGKOK)

def main():
    ex_name = os.getenv('EXCHANGE', CFG.data.exchange)
    api_key = os.getenv('API_KEY')
    api_secret = os.getenv('API_SECRET')
    dry_run = os.getenv('DRY_RUN', 'true').lower() == 'true'
    sandbox = os.getenv('SANDBOX', 'false').lower() == 'true'

    symbols_env = os.getenv('SYMBOLS')
    symbols = [s.strip() for s in symbols_env.split(',')] if symbols_env else list(CFG.data.symbols)
    symbols = [s if '/' in s else s[:-4] + '/' + s[-4:] for s in symbols]
    timeframes = ["15m", "30m", "1h"]

    logger.info(f"Commander live (multi) DryRun={dry_run} Sandbox={sandbox} Symbols={symbols} Timeframes={timeframes}")

    broker = CCXTBroker(ex_name, api_key, api_secret, sandbox=sandbox)
    reg = RegimeDetector(CFG.regime)
    experts = [TrendFollower(), MeanRevert(), Breakout(), TrendPullback(), VolSqueezeBreakout()]
    meta = MetaLearner(CFG.meta, [e.name for e in experts])

    risk_cfg = type("C", (), {})()
    risk_cfg.max_positions = MAX_POSITIONS
    risk_cfg.max_gross_exposure = MAX_GROSS_EXPOSURE
    risk_cfg.max_risk_per_day = MAX_RISK_PER_DAY
    risk_cfg.max_per_bucket = MAX_PER_BUCKET
    risk_cfg.portfolio_risk_unit = float(os.getenv('PORTFOLIO_RISK_UNIT', '100'))
    risk_cfg.dyn_budget_lookback = int(os.getenv('DYN_BUDGET_LOOKBACK', '20'))
    risk_cfg.dyn_budget_min = float(os.getenv('DYN_BUDGET_MIN', '50'))
    risk_cfg.dyn_budget_max = float(os.getenv('DYN_BUDGET_MAX', '2000'))
    risk_cfg.daily_loss_limit = float(os.getenv('DAILY_LOSS_LIMIT', '0.05')) * CAPITAL_TOTAL

    risk = RiskGovernor(risk_cfg)
    autoscaler = AutoScaler(cooldown_secs=3600)
    realized_pnl = 0.0

    auto_set = autoscaler.get_settings(CAPITAL_TOTAL, force=True)
    dyn_risk_per_trade = auto_set['risk_per_trade']
    dyn_max_positions = auto_set['max_positions']
    dyn_max_gross_exposure = auto_set['max_gross_exposure']

    state = {s: {"entry": None, "pos": 0.0, "sl": None, "tp1": None, "tp2": None} for s in symbols}

    # mark day
    risk._last_day = now_thai().strftime("%Y-%m-%d")

    while True:
        TF_WEIGHTS = {"15m": 0.3, "30m": 0.3, "1h": 0.4}
        try:
            # reset daily pnl if new day
            today_str = now_thai().strftime("%Y-%m-%d")
            if risk._last_day != today_str:
                logger.info(f"[Daily Reset] New day {today_str}, reset daily PnL")
                risk.daily_pnl = 0.0
                risk._last_day = today_str

            data = {}
            for s in symbols:
                data[s] = {}
                for tf in timeframes:
                    try:
                        df = broker.fetch_ohlcv(s, tf, limit=max(CFG.data.lookback, 220))
                        if df is None or df.empty:
                            df = None
                        else:
                            if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                                df['timestamp'] = pd.to_datetime(df['timestamp'])
                            try:
                                df['atr14'] = atr_wilder(df, 14)
                            except Exception:
                                df['atr14'] = 0.0
                        data[s][tf] = df
                        time.sleep(0.12)
                    except Exception as e:
                        logger.error(f"[fetch err] {s} {tf} -> {e}")
                        data[s][tf] = None

            usable = [s for s in symbols if data.get(s, {}).get("1h") is not None]
            if not usable:
                logger.warning("No usable symbols, sleeping...")
                time.sleep(5)
                continue

            equity_estimate = float(CAPITAL_TOTAL) + float(realized_pnl)
            auto_set = autoscaler.get_settings(equity_estimate)
            dyn_risk_per_trade = auto_set['risk_per_trade']
            dyn_max_positions = auto_set['max_positions']
            dyn_max_gross_exposure = auto_set['max_gross_exposure']
            logger.info(f"[AutoScaler] eq={equity_estimate:.2f} -> RPT={dyn_risk_per_trade:.4f} MAX_POS={dyn_max_positions} MAX_GROSS={dyn_max_gross_exposure:.2f}")

            ranked = rank_by_momentum({s: data[s]["1h"] for s in usable})
            tradables = pick_diversified(ranked, {s: data[s]["1h"] for s in usable},
                                         CFG.risk.top_k, CFG.risk.corr_threshold)

            candidates = []
            for s in usable:
                df1h = data[s]["1h"]
                tf_signals = {}
                for tf in timeframes:
                    df_tf = data[s].get(tf)
                    sigs = []
                    if df_tf is not None:
                        for e in experts:
                            try:
                                sgl = e.signal(df_tf)
                                st = max(0.0, min(1.0, getattr(sgl, 'strength', 0.0)))
                                dirn = int(getattr(sgl, 'direction', 0))
                                sigs.append((dirn, st, e.name))
                            except Exception:
                                sigs.append((0, 0.0, e.name))
                    tf_signals[tf] = sigs
                tf_nets = {tf: sum(d * st for (d, st, _) in sigs) for tf, sigs in tf_signals.items()}
                combined = sum(tf_nets.get(tf, 0.0) * w for tf, w in TF_WEIGHTS.items())
                direction = 1 if combined > 0.05 else (-1 if combined < -0.05 else 0)
                strength = min(1.0, abs(combined))
                if direction == 0:
                    logger.debug(f"[Filter] {s} rejected: neutral signal")
                    continue
                if not pass_filters(df1h, direction):
                    logger.debug(f"[Filter] {s} rejected: filters not passed")
                    continue
                p = strength_to_prob(strength)
                rr = 1.5
                eu = p * rr - (1 - p)
                if eu <= 0:
                    logger.debug(f"[Filter] {s} rejected: EU={eu:.2f}")
                    continue
                candidates.append((eu, s, direction, strength))

            candidates.sort(reverse=True, key=lambda x: x[0])

            equity = float(CAPITAL_TOTAL) + float(realized_pnl)
            open_positions = [sym for sym in symbols if state[sym]["pos"] != 0.0]
            corr_bucket_count = {}

            for eu, s, direction, strength in candidates:
                if len(open_positions) >= dyn_max_positions:
                    logger.info(f"[Block] Skip {s}: max positions reached")
                    break
                if s not in tradables:
                    logger.debug(f"[Block] {s} not in tradables")
                    continue

                price = float(data[s]["1h"]['close'].iloc[-1])
                atrv = float(data[s]["1h"].get('atr14', pd.Series([0.0])).iloc[-1] or 0.0)
                side = 'buy' if direction > 0 else 'sell'
                k_atr = 2.0
                sl, tp1, tp2 = compute_sl_tp(price, atrv, k_atr=k_atr, side=1 if side == 'buy' else -1)

                per_slot_budget = risk.dynamic_budget()
                positions_remaining = max(1, dyn_max_positions - len(open_positions))
                risk_per_trade_frac = min(dyn_risk_per_trade, (MAX_RISK_PER_DAY / positions_remaining))
                qty = position_size_by_risk(equity, risk_per_trade_frac, price, sl)

                p = strength_to_prob(strength)
                R = rr
                kelly_f = max(0.0, min(0.5, (p * R - (1 - p)) / max(1e-9, R)))
                qty *= (0.5 + kelly_f)

                qty_rounded = broker._round_amount(s, qty)
                if qty_rounded <= 0:
                    logger.info(f"[SizeReject] {s} qty=0 after rounding")
                    continue

                symbol_notional = qty_rounded * price
                can, reason = risk.can_open(equity, s, symbol_notional, corr_bucket_count, len(open_positions))
                if not can:
                    logger.info(f"[RiskBlock] Skip {s} reason={reason}")
                    continue

                if not dry_run:
                    order = broker.place_order(s, side, qty_rounded)
                    if order:
                        state[s].update({"pos": qty_rounded if side == 'buy' else -qty_rounded,
                                         "entry": price, "sl": sl, "tp1": tp1, "tp2": tp2})
                        risk.on_open(s, symbol_notional, qty_rounded, price, sl, tp2)
                        open_positions.append(s)
                        logger.info(f"[Order] Live {side} {s} qty={qty_rounded} price={price}")
                else:
                    state[s].update({"pos": qty_rounded if side == 'buy' else -qty_rounded,
                                     "entry": price, "sl": sl, "tp1": tp1, "tp2": tp2})
                    risk.on_open(s, symbol_notional, qty_rounded, price, sl, tp2)
                    open_positions.append(s)
                    logger.info(f"[Order] DryRun {side} {s} qty={qty_rounded} price={price}")

            for s in list(open_positions):
                if state[s]['pos'] == 0.0:
                    continue
                price = float(data[s]['1h']['close'].iloc[-1])
                side_sign = 1 if state[s]['pos'] > 0 else -1
                entry = state[s]['entry']
                sl = state[s]['sl']
                tp2 = state[s]['tp2']

                r = (price - entry) * side_sign
                oneR = abs(entry - sl)
                if oneR > 0 and r >= oneR and sl != entry:
                    state[s]['sl'] = entry
                if r >= oneR * 1.5:
                    atr_now = float(data[s]['1h'].get('atr14', pd.Series([0.0])).iloc[-1] or 0.0)
                    trail = 1.2 * atr_now
                    new_sl = price - side_sign * trail
                    if side_sign > 0:
                        state[s]['sl'] = max(state[s]['sl'], new_sl)
                    else:
                        state[s]['sl'] = min(state[s]['sl'], new_sl)

                exit_now = False
                if side_sign > 0 and price <= state[s]['sl']:
                    exit_now = True
                if side_sign < 0 and price >= state[s]['sl']:
                    exit_now = True
                if side_sign > 0 and price >= tp2:
                    exit_now = True
                if side_sign < 0 and price <= tp2:
                    exit_now = True

                if exit_now:
                    if not dry_run:
                        broker.place_order(s, 'sell' if side_sign > 0 else 'buy', abs(state[s]['pos']))
                    pnl_usd = (price - entry) * side_sign * abs(state[s]['pos'])
                    realized_pnl += pnl_usd
                    risk.register_pnl(pnl_usd)
                    risk.on_close(s)
                    logger.info(f"[Exit] {s} pnl={pnl_usd:.2f}")
                    state[s].update({"pos": 0.0, "entry": None, "sl": None, "tp1": None, "tp2": None})
                    try:
                        open_positions.remove(s)
                    except ValueError:
                        pass
                    risk.set_cooldown(s, 1800)

            summaries = []
            for s in symbols:
                pos = state[s]['pos']
                entry = state[s]['entry'] or 0.0
                sl = state[s]['sl'] or 0.0
                size = abs(pos)
                price = float(data[s]['1h']['close'].iloc[-1]) if data[s]['1h'] is not None else 0.0
                summaries.append(f"{s}: price={price:.2f} pos={pos:.6f} entry={entry:.2f} sl={sl:.2f} size={size:.6f}")
            logger.info(" | ".join(summaries))
            time.sleep(5)

        except Exception as e:
            logger.error(f"Runner error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
