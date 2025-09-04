# utils_sizing.py
from math import floor

def compute_sl_tp(price: float, atr: float, k_atr: float = 2.0, rr1: float = 1.5, rr2: float = 2.5, side: int = 1):
    """
    คืนค่า (sl, tp1, tp2)
    side = 1 for buy (long), -1 for sell (short)
    sl = price - side * k_atr * atr
    tp1/tp2 based on RR multiples
    """
    sl = price - side * k_atr * atr
    rr_dist = abs(price - sl)
    tp1 = price + side * rr1 * rr_dist
    tp2 = price + side * rr2 * rr_dist
    return float(sl), float(tp1), float(tp2)

def position_size_by_risk(equity: float, risk_per_trade: float, price: float, sl: float, contract_multiplier: float = 1.0):
    """
    คำนวณจำนวนสัญญา/โทเค็นจาก risk (USD) และ SL distance
    equity: USD
    risk_per_trade: fractional (e.g., 0.01 = 1% of equity)
    price, sl in quote currency (USD)
    contract_multiplier: 1 for spot-like, for perp could be different
    """
    usd_risk = equity * float(risk_per_trade)
    sl_dist = abs(price - sl)
    if sl_dist <= 1e-12:
        return 0.0
    qty = usd_risk / (sl_dist * contract_multiplier)
    # Don't return fractional dust; caller should round to market step
    return float(qty)
