# position_registry.py - simple in-memory position registry with cooldown & TTL
import time
from collections import defaultdict

class PositionRegistry:
    def __init__(self):
        # symbol -> position info dict:
        # { symbol, entry_time, entry_price, notional, qty, side, tf_origin, ttl_candles, last_update }
        self._open = {}
        # symbol -> cooldown_until timestamp
        self._cooldowns = defaultdict(float)

    def list_open(self):
        return list(self._open.values())

    def symbol_exposure(self, symbol: str) -> float:
        p = self._open.get(symbol)
        return float(p.get('notional', 0.0)) if p else 0.0

    def can_open(self, symbol: str) -> bool:
        now = time.time()
        if symbol in self._open:
            return False
        if now < self._cooldowns.get(symbol, 0.0):
            return False
        return True

    def open(self, symbol: str, info: dict):
        # info must include 'notional'
        info = dict(info)
        info['entry_time'] = time.time()
        info['last_update'] = time.time()
        self._open[symbol] = info

    def close(self, symbol: str, reason: str = None, cooldown_seconds: int = 0):
        if symbol in self._open:
            del self._open[symbol]
        if cooldown_seconds > 0:
            self._cooldowns[symbol] = time.time() + float(cooldown_seconds)

    def enforce_ttl(self, now_timestamp: float, candle_age_map: dict):
        # candle_age_map: symbol -> age_in_seconds per TF candle count, optional for TTL enforcement
        # For simple use we skip detailed TTL enforcement here
        pass

    def clear_all(self):
        self._open = {}
        self._cooldowns = defaultdict(float)
