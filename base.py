# base.py
from abc import ABC, abstractmethod

class Broker(ABC):
    @abstractmethod
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int):
        """Fetch OHLCV data for a symbol"""
        pass

    @abstractmethod
    def get_price(self, symbol: str) -> float:
        """Return current price"""
        pass

    @abstractmethod
    def place_order(self, symbol: str, side: str, size: float, price: float = None, stop: float = None, take: float = None):
        """Place an order"""
        pass
