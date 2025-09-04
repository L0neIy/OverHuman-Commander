import pandas as pd
from utils import ema, atr_wilder, adx_wilder
from config import CFG

class RegimeDetector:
    def __init__(self, cfg=CFG.regime):  # <- แก้ตรงนี้
        self.cfg = cfg

    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['ema50'] = ema(df['close'], 50)
        df['ema200'] = ema(df['close'], 200)
        df['atr14'] = atr_wilder(df, 14)
        df['atr20'] = atr_wilder(df, 20)
        df['atr20_ma'] = df['atr20'].rolling(20).mean()
        df['atr_ratio'] = df['atr20'] / df['atr20_ma']
        df['adx14'] = adx_wilder(df, 14)

        df['is_trend'] = ((df['adx14'] > self.cfg.adx_trend_on) & (df['ema50'] > df['ema200'])).astype(int)
        df['is_range'] = (df['adx14'] < self.cfg.adx_range_off).astype(int)
        df['is_breakout'] = (df['atr_ratio'] > self.cfg.atr_expansion_ratio).astype(int)

        df['w_trend'] = (df['is_trend'] * (df['adx14'] / (self.cfg.adx_trend_on + 1e-9))).clip(0, 1)
        df['w_range'] = (df['is_range'] * ((self.cfg.adx_range_off - df['adx14']).abs() / self.cfg.adx_range_off)).clip(0, 1)
        df['w_breakout'] = (df['is_breakout'] * df['atr_ratio'] / (self.cfg.atr_expansion_ratio + 1e-9)).clip(0, 1)
        return df
