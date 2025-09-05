import pandas as pd
import os

LOG_FILE = "data/paper_trades.csv"

def generate_summary(log_file=LOG_FILE):
    if not os.path.exists(log_file):
        print("❌ Log file not found:", log_file)
        return

    df = pd.read_csv(log_file)
    if df.empty or len(df) < 2:
        print("❌ Not enough trades in log.")
        return

    # คำนวณ PnL จากคู่เทรด (entry-exit)
    df["pnl"] = 0.0
    equity_curve = [0.0]
    for i in range(1, len(df)):
        entry = df.iloc[i - 1]
        exit_trade = df.iloc[i]
        if entry["symbol"] != exit_trade["symbol"]:
            continue
        if entry["side"].lower() == "buy":
            df.at[i, "pnl"] = (exit_trade["price"] - entry["price"]) * entry["size"]
        elif entry["side"].lower() == "sell":
            df.at[i, "pnl"] = (entry["price"] - exit_trade["price"]) * entry["size"]
        equity_curve.append(equity_curve[-1] + df.at[i, "pnl"])

    # สรุป performance
    total_pnl = df["pnl"].sum()
    wins = (df["pnl"] > 0).sum()
    losses = (df["pnl"] < 0).sum()
    trades = wins + losses
    winrate = (wins / trades * 100) if trades > 0 else 0
    avg_pnl = df["pnl"].mean()
    per_symbol = df.groupby("symbol")["pnl"].sum().to_dict()

    gross_profit = df[df["pnl"] > 0]["pnl"].sum()
    gross_loss = -df[df["pnl"] < 0]["pnl"].sum()
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

    equity_series = pd.Series(equity_curve)
    rolling_max = equity_series.cummax()
    drawdown = rolling_max - equity_series
    max_drawdown = drawdown.max()

    summary = {
        "trades": trades,
        "wins": int(wins),
        "losses": int(losses),
        "winrate": f"{winrate:.2f}%",
        "total_pnl": round(total_pnl, 4),
        "avg_pnl": round(avg_pnl, 4),
        "per_symbol": per_symbol,
        "profit_factor": round(profit_factor, 2),
        "max_drawdown": round(max_drawdown, 2),
    }

    print("\n===== Trading Performance Summary =====")
    for k, v in summary.items():
        print(f"{k}: {v}")

    return summary

if __name__ == "__main__":
    generate_summary()
