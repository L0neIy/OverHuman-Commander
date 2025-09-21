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
                "reason", "pnl_daily", "level", "message"
            ])
            df.to_csv(self.logfile, index=False)

    def log(self, symbol=None, pos=None, entry=None, direction=None, strength=None,
            decision=None, daily_pnl=None, level="INFO", message=None):
        row = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "position": pos,
            "entry_price": entry,
            "direction": direction,
            "strength": strength,
            "order_side": getattr(decision, "side", None) if decision else None,
            "order_size": getattr(decision, "size", None) if decision else None,
            "reason": getattr(decision, "reason", None) if decision else None,
            "pnl_daily": daily_pnl,
            "level": level,
            "message": message
        }
        df = pd.DataFrame([row])
        df.to_csv(self.logfile, mode='a', header=False, index=False)

        # console log
        if message:
            print(f"[{row['timestamp']}] [{level}] {message}")
        else:
            print(f"[{row['timestamp']}] {symbol} pos={pos} dir={direction} str={strength:.2f if strength else 0} "
                  f"order={row['order_side']} size={row['order_size']} pnl_daily={daily_pnl}")

    # === shortcut methods ===
    def info(self, message):
        self.log(level="INFO", message=message)

    def warning(self, message):
        self.log(level="WARNING", message=message)

    def error(self, message):
        self.log(level="ERROR", message=message)

    def debug(self, message):
        self.log(level="DEBUG", message=message)
