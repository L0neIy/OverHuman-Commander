# autoscaler.py
import time
from typing import Dict

class AutoScaler:
    """
    AutoScaler ปรับ RISK_PER_TRADE และ MAX_POSITIONS ตาม equity thresholds.
    - ใช้ cooldown (วินาที) เพื่อไม่ให้เปลี่ยนบ่อยเกินไป
    - กำหนด tiers ตาม equity (USD)
    """

    def __init__(self, cooldown_secs: int = 3600):
        # tiers: (min_equity, settings)
        # settings เป็น dict ที่มี keys: risk_per_trade (fraction), max_positions (int), max_gross_exposure (fraction)
        self.tiers = [
            (0,     {"risk_per_trade": 0.008, "max_positions": 3, "max_gross_exposure": 0.30}),  # 0..5k
            (5000,  {"risk_per_trade": 0.010, "max_positions": 4, "max_gross_exposure": 0.35}),  # 5k..20k
            (20000, {"risk_per_trade": 0.015, "max_positions": 6, "max_gross_exposure": 0.45}),  # 20k..100k
            (100000,{"risk_per_trade": 0.020, "max_positions": 8, "max_gross_exposure": 0.55}),  # 100k+
        ]
        self.cooldown_secs = cooldown_secs
        self.last_apply_time = 0
        self.current_settings = self.tiers[0][1].copy()

    def _get_tier_for(self, equity: float) -> Dict:
        eq = float(max(0.0, equity))
        chosen = self.tiers[0][1]
        for min_eq, settings in self.tiers:
            if eq >= min_eq:
                chosen = settings
        return chosen

    def get_settings(self, equity: float, force: bool = False) -> Dict:
        """
        คืนค่า settings (risk_per_trade, max_positions, max_gross_exposure).
        จะ apply change ถ้า cooldown หมดหรือ force=True.
        """
        desired = self._get_tier_for(equity)
        now = time.time()
        if force or (desired != self.current_settings and (now - self.last_apply_time) >= self.cooldown_secs):
            # apply (but we still return desired even if cooldown not passed)
            self.current_settings = desired.copy()
            self.last_apply_time = now
        return self.current_settings.copy()

    def set_tiers(self, tiers_list):
        """
        (Optional) เสริม: ตั้ง tiers ใหม่เป็น list ของ tuples (min_equity, settings_dict)
        """
        self.tiers = sorted(tiers_list, key=lambda x: x[0])
        self.current_settings = self.tiers[0][1].copy()
