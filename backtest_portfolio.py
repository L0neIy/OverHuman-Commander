import argparse
import os
import numpy as np
import pandas as pd
import ccxt
from config import CFG
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

FEE = 0.0005       # 0.05% per trade side
SLIPPAGE = 0.001   # 0.10% adverse


def load_ccxt(exchange: str, symbol: str, timeframe: str, limit: int=1500) -> pd.DataFrame:
    ex = getattr(ccxt, exchange)()
    o = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(o, columns=['timestamp','open','high','low','close','volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df


def run_portfolio(symbols, timeframe, limit):
    # load data for all symbols
    data = {s: load_ccxt(CFG.data.exchange, s, timeframe, limit) for s in symbols}
    # sync common timeline by inner join on timestamp
    idx = None
    for df in data.values():
        idx = df['timestamp'] if idx is None else idx
    # choose the smallest common index
    common = None
    for s, df in data.items():
        common = df['timestamp'] if common is None else pd.Series(np.intersect1d(common.values, df['timestamp'].values))
    for s in symbols:
        data[s] = data[s][data[s]['timestamp'].isin(common.values)].reset_index(drop=True)
        data[s]['atr14'] = atr_wilder(data[s], 14)
        data[s]['date'] = data[s]['timestamp'].dt.date

    experts = [TrendFollower(), MeanRevert(), Breakout(), TrendPullback(), VolSqueezeBreakout()]
    meta = MetaLearner(CFG.meta, [e.name for e in experts])
    risk = RiskGovernor(CFG.risk)
    reg = RegimeDetector(CFG.regime)

    equity = 1.0
    equity_curve = []
    state = {s: {"pos": 0.0, "entry": None} for s in symbols}

    # iterate timebar by timebar
    n = len(next(iter(data.values())))
    for i in range(max(CFG.data.lookback, 220), n):
        # build per‑symbol window
        window = {s: data[s].iloc[:i].copy() for s in symbols}
        day_key = next(iter(window.values()))['date'].iloc[-1]
        risk.reset_day(day_key)

        # select tradeable set: XSM top‑K and correlation filter
        ranked = rank_by_momentum({s: window[s] for s in symbols})
        tradables = pick_diversified(ranked, window, top_k=CFG.risk.top_k, corr_threshold=CFG.risk.corr_threshold)

        # process symbols
        pnl_step = 0.0
        total_weight = 0.0

        for sym in tradables:
            df = window[sym]
            rfeat = reg.detect(df).iloc[-1]
            w_reg = {
                'trend': float(rfeat['w_trend']),
                'mean_revert': float(rfeat['w_range']),
                'breakout': float(rfeat['w_breakout'])
            }
            ssum = sum(w_reg.values()) or 1.0
            w_reg = {k: v/ssum for k,v in w_reg.items()}

            # expert signals
            sigs = {}
            for e in experts:
                sgl = e.signal(df)
                w = w_reg.get(e.name, 0.0) * meta.get_weight(e.name)
                sigs[e.name] = (sgl.direction, max(0.0, min(1.0, sgl.strength)) * w, sgl.reason)

            net = sum(direction * strength for (direction, strength, _) in sigs.values())
            direction = 1 if net > 0.05 else (-1 if net < -0.05 else 0)
            strength = min(1.0, abs(net))

            price = float(df['close'].iloc[-1])
            atrv = float(df['atr14'].iloc[-1] or 0.0)
            dec = risk.decide(sym, price, atrv, direction, strength)

            # mark‑to‑market & close logic

pos = state[sym]['pos']
            entry = state[sym]['entry']
            if pos != 0.0 and entry is not None:
                ret = (price/entry - 1.0)
                pnl = (ret if pos>0 else -ret) - FEE - SLIPPAGE
                pnl_step += pnl * abs(pos)
                # simple reversal/exit
                if dec is None or (dec.side == 'buy' and pos<0) or (dec.side=='sell' and pos>0):
                    state[sym]['pos'] = 0.0
                    state[sym]['entry'] = None
                    risk.close_position(sym)

            # open new
            if dec and state[sym]['pos'] == 0.0:
                state[sym]['pos'] = dec.size if dec.side=='buy' else -dec.size
                state[sym]['entry'] = price * (1 + SLIPPAGE if dec.side=='buy' else 1 - SLIPPAGE)
                risk.open_position(sym, state[sym]['pos'], state[sym]['entry'])

        # update equity
        equity *= (1.0 + pnl_step)
        equity_curve.append(equity)
        risk.register_pnl(pnl_step)
        risk.on_equity(equity)

    # metrics
    curve = pd.Series(equity_curve, index=data[symbols[0]].iloc[max(CFG.data.lookback,220):].timestamp)
    rets = curve.pct_change().dropna()
    ann = (1 + rets.mean())**(365*24) - 1 if len(rets) else 0  # rough hourly→annual if 1h bars
    vol = rets.std() * (365*24)**0.5 if len(rets) else 0
    sharpe = ann / vol if vol>0 else 0
    dd = (curve / curve.cummax() - 1).min()

    # profit factor (approx via positive/negative step pnls)
    pos = rets[rets>0].sum()
    neg = -rets[rets<=0].sum()
    pf = (pos/neg) if neg>0 else np.inf

    print(f"Final equity: {equity:.3f}x | CAGR~{ann*100:.2f}% | Sharpe~{sharpe:.2f} | MaxDD {dd*100:.2f}% | PF {pf:.2f}")
    curve.to_csv('equity_curve_portfolio.csv', index_label='timestamp', header=['equity'])
    print("Saved: equity_curve_portfolio.csv")

if name == "main":
    parser = argparse.ArgumentParser()
    parser.add_argument('--timeframe', default=CFG.data.timeframe)
    parser.add_argument('--limit', type=int, default=1500)
    parser.add_argument('--symbols', default=",".join(CFG.data.symbols))
    args = parser.parse_args()
    symbols = [s.strip() for s in args.symbols.split(',') if s.strip()]
    run_portfolio(symbols, args.timeframe, args.limit)