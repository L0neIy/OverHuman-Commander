class Breakout:
    name = "breakout"

    def signal(self, df):
        """
        ถ้าราคาทะลุ High/Low 20 วัน → breakout
        """
        try:
            if len(df) < 20:
                return self._empty_signal("not enough data")

            high20 = df['high'].rolling(20).max().iloc[-1]
            low20 = df['low'].rolling(20).min().iloc[-1]
            price = df['close'].iloc[-1]

            if price > high20:
                return self._make_signal(1, 1.0, "Breakout above 20-day high")
            elif price < low20:
                return self._make_signal(-1, 1.0, "Breakdown below 20-day low")
            else:
                return self._empty_signal("Inside range")
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
