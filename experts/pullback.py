class TrendPullback:
    name = "pullback"

    def signal(self, df):
        """
        ถ้าราคาอยู่ในขาขึ้น แต่ย่อตัวกลับมาใกล้ MA20 → เป็นจังหวะเข้าซื้อ
        """
        try:
            if len(df) < 20:
                return self._empty_signal("not enough data")

            ma20 = df['close'].rolling(20).mean().iloc[-1]
            price = df['close'].iloc[-1]

            if price > ma20 * 1.02:
                return self._empty_signal("Too far above MA20")
            elif price > ma20:
                return self._make_signal(1, 0.7, "Pullback near MA20 in uptrend")
            else:
                return self._empty_signal("Not in uptrend")
        except Exception as e:
            return self._empty_signal(str(e))

    class Sig:
        def __init__(self, direction=0, strength=0.0, reason=""):
            self.direction = direction
            self.strength = strength
            self.reason = reason

    def _make_signal(self, direction, strength, reason):
        return self.Sig(direction, strength, reason)

    def _empty_signal(self, reason):
        return self.Sig(0, 0.0, reason)
