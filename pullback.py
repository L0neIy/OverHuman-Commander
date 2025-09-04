import pandas as pd
from experts.base import Expert, ExpertSignal
from utils import ema, rsi

class TrendPullback(Expert):
    name = "trend_pullback"

    def signal(self, df: pd.DataFrame) -> ExpertSignal:
        if len(df) < 210:
            return ExpertSignal(0, 0.0, "insufficient data")
        close = df['close']
        e50 = ema(close, 50)
        e200 = ema(close, 200)
        r = rsi(close, 14)
        last = df.index[-1]
        if e50.iloc[-1] > e200.iloc[-1] and r.iloc[-1] < 40:  # bullish trend, pullback on RSI
            strength = min(1.0, float((40 - r.iloc[-1]) / 20.0))
            return ExpertSignal(+1, strength, "trend up + rsi pullback")
        if e50.iloc[-1] < e200.iloc[-1] and r.iloc[-1] > 60:  # bearish trend, rebound
            strength = min(1.0, float((r.iloc[-1] - 60) / 20.0))
            return ExpertSignal(-1, strength, "trend down + rsi rebound")
        return ExpertSignal(0, 0.0, "no pullback setup")

experts/vol_squeeze.py — Volatility Breakout (Squeeze)

import pandas as pd
from experts.base import Expert, ExpertSignal
from utils import atr_wilder, ema

class VolSqueezeBreakout(Expert):
    name = "vol_squeeze"

    def signal(self, df: pd.DataFrame) -> ExpertSignal:
        if len(df) < 100:
            return ExpertSignal(0, 0.0, "insufficient data")
        # Squeeze proxy: ATR short vs long
        atr_s = atr_wilder(df, 14)
        atr_l = atr_wilder(df, 50)
        ratio = atr_s / (atr_l + 1e-9)
        close = df['close']
        e20 = ema(close, 20)
        last = df.iloc[-1]
        # breakout confirmation: close crosses above/below EMA20 with ATR expansion
        if ratio.iloc[-1] > 1.2 and close.iloc[-1] > e20.iloc[-1]:
            return ExpertSignal(+1, min(1.0, float(ratio.iloc[-1] / 2.0)), "ATR expand up + EMA cross up")
        if ratio.iloc[-1] > 1.2 and close.iloc[-1] < e20.iloc[-1]:
            return ExpertSignal(-1, min(1.0, float(ratio.iloc[-1] / 2.0)), "ATR expand down + EMA cross down")
        return ExpertSignal(0, 0.0, "no squeeze breakout")