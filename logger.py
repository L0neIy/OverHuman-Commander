import pandas as pd
from datetime import datetime
import os

class CommanderLogger:
    def __init__(self, logfile="commander_log.csv"):
        self.logfile = logfile
        if not os.path.exists(self.logfile):
            df = pd.DataFrame(columns=[
                "timestamp", "symbol", "position", "entry_price",
                "direction", "strength", "order_side", "order_size",
                "reason", "pnl_daily"
            ])
            df.to_csv(self.logfile, index=False)

    def log(self, symbol, pos, entry, direction, strength, decision, daily_pnl):
        row = {
            "timestamp": datetime.now(),
            "symbol": symbol,
            "position": pos,
            "entry_price": entry,
            "direction": direction,
            "strength": strength,
            "order_side": getattr(decision, "side", None),
            "order_size": getattr(decision, "size", None),
            "reason": getattr(decision, "reason", None),
            "pnl_daily": daily_pnl
        }
        df = pd.DataFrame([row])
        df.to_csv(self.logfile, mode='a', header=False, index=False)
        print(f"[{row['timestamp']}] {symbol} pos={pos} dir={direction} str={strength:.2f} "
              f"order={row['order_side']} size={row['order_size']} pnl_daily={daily_pnl:.4f}")
