class MeanRevert:
    name = "mean_revert"

    def signal(self, df):
        """
        ถ้าราคาห่างจากค่าเฉลี่ย 20 วันมากเกินไป → คาดว่าจะ revert
        """
        try:
            if len(df) < 20:
                return self._empty_signal("not enough data")

            ma20 = df['close'].rolling(20).mean().iloc[-1]
            price = df['close'].iloc[-1]

            diff = (price - ma20) / ma20
            if diff > 0.05:  # ราคา +5% จาก MA
                return self._make_signal(-1, 0.6, "Price above MA20 → short")
            elif diff < -0.05:  # ราคา -5% จาก MA
                return self._make_signal(1, 0.6, "Price below MA20 → long")
            else:
                return self._empty_signal("Near mean")
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
