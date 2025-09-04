import pandas as pd
import numpy as np
from typing import Dict, List

# rank symbols by 90‑period momentum (simple ROC)
def rank_by_momentum(prices_by_symbol: Dict[str, pd.DataFrame], period: int = 90) -> List[str]:
    scores = []
    for sym, df in prices_by_symbol.items():
        if df is None or df.empty or len(df) < period + 5:
            continue
        ret = df['close'].iloc[-1] / df['close'].iloc[-period] - 1.0
        scores.append((sym, float(ret)))
    scores.sort(key=lambda x: x[1], reverse=True)
    return [s for s,_ in scores]

# greedily pick up to top_k with low pairwise correlation
# correlation computed on last 120 returns

def pick_diversified(symbols_ranked: List[str], prices_by_symbol: Dict[str, pd.DataFrame], top_k: int = 5, corr_threshold: float = 0.75) -> List[str]:
    chosen = []
    def series(sym):
        df = prices_by_symbol[sym]
        r = df['close'].pct_change().dropna().tail(120)
        return r if len(r) >= 20 else None
    for sym in symbols_ranked:
        s = series(sym)
        if s is None:
            continue
        ok = True
        for c in chosen:
            sc = series(c)
            if sc is None: continue
            # align indices
            aligned = pd.concat([s, sc], axis=1).dropna()
            if len(aligned) < 20: continue
            corr = float(aligned.iloc[:,0].corr(aligned.iloc[:,1]))
            if corr >= corr_threshold:
                ok = False
                break
        if ok:
            chosen.append(sym)
        if len(chosen) >= top_k:
            break
    return chosen