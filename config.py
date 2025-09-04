from dataclasses import dataclass, field
from typing import List

@dataclass
class DataConfig:
    exchange: str = "binance"
    symbol: str = "BTC/USDT"                 # kept for backward compat
    symbols: List[str] = field(default_factory=lambda: [
        "BTC/USDT","ETH/USDT","BNB/USDT","SOL/USDT","ADA/USDT",
        "XRP/USDT","LTC/USDT","MATIC/USDT","DOGE/USDT","LINK/USDT"
    ])
    timeframe: str = "1h"
    lookback: int = 600                        # a bit longer for indicators

@dataclass
class RegimeConfig:
    adx_trend_on: float = 25.0
    adx_range_off: float = 18.0
    atr_expansion_ratio: float = 1.2

@dataclass
class RiskConfig:
    per_trade_atr_multiple_stop: float = 1.8
    trailing_atr_multiple: float = 1.0
    daily_loss_limit: float = 0.02             # portfolio-level (-2%)
    max_concurrent_positions: int = 3          # conservative default
    portfolio_risk_unit: float = 0.001         # ~0.1% risk budget
    dyn_budget_lookback: int = 200             # realized vol window (equity)
    dyn_budget_min: float = 0.0005             # floor
    dyn_budget_max: float = 0.003              # cap
    corr_threshold: float = 0.75               # avoid pairs > this corr
    top_k: int = 5                             # trade only top-K symbols

@dataclass
class MetaConfig:
    window_trades: int = 50
    pf_down_threshold: float = 0.9
    reduce_weight_factor: float = 0.7
    increase_weight_step: float = 0.1

@dataclass
class CommanderConfig:
    data: DataConfig = field(default_factory=DataConfig)
    regime: RegimeConfig = field(default_factory=RegimeConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    meta: MetaConfig = field(default_factory=MetaConfig)

CFG = CommanderConfig()
