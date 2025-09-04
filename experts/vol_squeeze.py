class VolSqueezeBreakout:
    name = "vol_squeeze"

    def signal(self, df):
        """
        ถ้า Bollinger Band แคบมาก → รอ breakout
        """
        try:
            if len(df) < 20:
                return self._empty_signal("not enough data")

            close = df['close']
            ma20 = close.rolling(20).mean().iloc[-1]
            std20 = close.rolling(20).std().iloc[-1]

            upper = ma20 + 2 * std20
            lower = ma20 - 2 * std20
            band_width = (upper - lower) / ma20
            price = close.iloc[-1]

            if band_width < 0.05:  # squeeze < 5%
                if price > upper:
                    return self._make_signal(1, 1.0, "Bollinger squeeze breakout ↑")
                elif price < lower:
                    return self._make_signal(-1, 1.0, "Bollinger squeeze breakdown ↓")
                else:
                    return self._empty_signal("Waiting breakout")
            else:
                return self._empty_signal("No squeeze")
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
