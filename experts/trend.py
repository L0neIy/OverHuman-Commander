class TrendFollower:
    name = "trend"

    def signal(self, df):
        """
        ตีความง่าย ๆ: ถ้าราคาปิดล่าสุด > ราคาเฉลี่ย 20 วัน → แนวโน้มขึ้น
        """
        try:
            if len(df) < 20:
                return self._empty_signal("not enough data")

            ma20 = df['close'].rolling(20).mean().iloc[-1]
            price = df['close'].iloc[-1]

            if price > ma20:
                return self._make_signal(1, 0.8, "Price above MA20 (uptrend)")
            elif price < ma20:
                return self._make_signal(-1, 0.8, "Price below MA20 (downtrend)")
            else:
                return self._empty_signal("Price near MA20")
        except Exception as e:
            return self._empty_signal(str(e))

    class Sig:
        def __init__(self, direction=0, strength=0.0, reason=""):
            self.direction = direction  # 1=buy, -1=sell, 0=neutral
            self.strength = strength
            self.reason = reason

    def _make_signal(self, direction, strength, reason):
        return self.Sig(direction, strength, reason)

    def _empty_signal(self, reason):
        return self.Sig(0, 0.0, reason)
