import numpy as np
import pandas as pd

# --- smoothing helpers ---
def rma(series: pd.Series, period: int) -> pd.Series:
    # Wilder's RMA (EMA with alpha=1/period) initialized with SMA
    s = series.copy().astype(float)
    alpha = 1.0 / period
    out = s.ewm(alpha=alpha, adjust=False).mean()
    # better seed: simple SMA for first period
    sma = s.rolling(period, min_periods=period).mean()
    out.iloc[:period] = sma.iloc[:period]
    return out

# True Range
def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df['close'].shift(1)
    return np.maximum(df['high'] - df['low'],
                      np.maximum(abs(df['high'] - prev_close), abs(df['low'] - prev_close)))

# Wilder ATR
def atr_wilder(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tr = true_range(df)
    return rma(tr, period).rename(f"atr{period}")

# Wilder ADX (standard-ish)
def adx_wilder(df: pd.DataFrame, period: int = 14) -> pd.Series:
    up = df['high'].diff()
    down = -df['low'].diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = true_range(df)
    atr = rma(tr, period)
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / atr
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di)).fillna(0)
    adx = rma(dx, period).rename('adx')
    return adx

# EMA
def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()

# RSI (Wilder)
def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    rs = rma(up, period) / (rma(down, period) + 1e-12)
    return 100 - (100 / (1 + rs))

# z-score
def zscore(series: pd.Series, window: int = 20) -> pd.Series:
    mean = series.rolling(window).mean()
    std = series.rolling(window).std(ddof=0)
    return (series - mean) / (std.replace(0, np.nan))

# Donchian
def donchian_channels(df: pd.DataFrame, period: int = 20):
    upper = df['high'].rolling(period).max()
    lower = df['low'].rolling(period).min()
    return upper, lower