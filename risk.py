# risk.py
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict
import math

@dataclass
class OrderDecision:
    side: str
    size: float          # absolute qty (not fraction). Runner will round to step
    stop: float | None
    take: float | None
    reason: str

class RiskGovernor:
    def __init__(self, cfg):
        # cfg can be simple namespace/dict with keys used below
        self.cfg = cfg
        self.daily_pnl = 0.0          # USD
        self.current_day = None
        self.cooldown_until = defaultdict(float)
        self.positions: Dict[str, dict] = {}  # symbol -> {size, entry, sl, tp}
        self.gross_exposure = 0.0     # notional USD
        self.equity_history = []

    # ---- day lifecycle ----
    def reset_day(self, day_key):
        if self.current_day != day_key:
            self.current_day = day_key
            self.daily_pnl = 0.0

    def register_pnl(self, pnl_usd: float):
        # pnl_usd is USD for this position / change
        self.daily_pnl += float(pnl_usd)
        # disable trading if daily loss limit exceed
        if hasattr(self.cfg, 'daily_loss_limit') and self.daily_pnl <= -abs(self.cfg.daily_loss_limit):
            print("[Risk] Daily loss limit hit. Disabling trading for today.")
            return

    def on_equity(self, equity: float):
        # call periodically to feed equity values (mark-to-market)
        self.equity_history.append(float(equity))
        if len(self.equity_history) > 1000:
            self.equity_history.pop(0)

    # ---- internal helpers ----
    def set_cooldown(self, symbol: str, secs: int):
        self.cooldown_until[symbol] = max(self.cooldown_until[symbol], time.time() + secs)

    def is_cooldown(self, symbol: str) -> bool:
        return time.time() < self.cooldown_until.get(symbol, 0)

    def current_open_count(self) -> int:
        return sum(1 for v in self.positions.values() if abs(v.get("size", 0)) > 0)

    def total_abs_exposure(self) -> float:
        return self.gross_exposure

    # ---- portfolio rules ----
    def can_trade_today(self, equity: float) -> bool:
        # check daily drawdown limit (frac)
        if not hasattr(self.cfg, 'max_risk_per_day'):
            return True
        dd_frac = (-self.daily_pnl / max(1.0, equity)) if self.daily_pnl < 0 else 0.0
        return dd_frac < float(self.cfg.max_risk_per_day)

    def can_open(self, equity: float, symbol: str, symbol_notional: float, corr_bucket_count: dict, open_positions_count: int):
        if not self.can_trade_today(equity):
            return False, "day-paused"
        if open_positions_count >= int(self.cfg.max_positions):
            return False, "too-many-positions"
        if (self.gross_exposure + abs(symbol_notional)) / max(1.0, equity) > float(self.cfg.max_gross_exposure):
            return False, "gross-exposure"
        # correlation bucket check
        bucket = getattr(self.cfg, 'buckets_map', {}).get(symbol, None)
        if bucket:
            if corr_bucket_count.get(bucket, 0) >= int(self.cfg.max_per_bucket):
                return False, "corr-bucket"
        if self.is_cooldown(symbol):
            return False, "cooldown"
        return True, ""

    def on_open(self, symbol: str, notional: float, size: float, entry: float, sl: float, tp: float | None = None):
        self.gross_exposure += abs(notional)
        self.positions[symbol] = {"size": size, "entry": entry, "sl": sl, "tp": tp, "notional": notional}

    def on_close(self, symbol: str):
        if symbol in self.positions:
            notional = self.positions[symbol].get("notional", 0.0)
            self.gross_exposure = max(0.0, self.gross_exposure - abs(notional))
            del self.positions[symbol]

    # dynamic budget (simple volatility scaling)
    def dynamic_budget(self) -> float:
        # returns USD per-slot budget (approx)
        base_unit = float(getattr(self.cfg, 'portfolio_risk_unit', 100.0))
        lookback = int(getattr(self.cfg, 'dyn_budget_lookback', 20))
        if len(self.equity_history) < lookback:
            return base_unit
        import numpy as np
        r = np.diff(np.log(self.equity_history[-lookback:]))
        rv = float(np.std(r)) * (len(r) ** 0.5) if len(r) > 1 else 0.0
        adj = base_unit * (0.02 / max(0.005, rv))
        return max(float(getattr(self.cfg, 'dyn_budget_min', base_unit*0.5)), min(float(getattr(self.cfg, 'dyn_budget_max', base_unit*5)), adj))
