import pandas as pd
import matplotlib.pyplot as plt
import os

LOG_FILE = "data/paper_trades.csv"

def plot_equity_curve(log_file=LOG_FILE):
    if not os.path.exists(log_file):
        print("❌ Log file not found:", log_file)
        return

    df = pd.read_csv(log_file)
    if df.empty or len(df) < 2:
        print("❌ Not enough trades in log.")
        return

    df["pnl"] = 0.0
    equity_curve = [0.0]

    for i in range(1, len(df)):
        entry = df.iloc[i-1]
        exit_trade = df.iloc[i]
        if entry["symbol"] != exit_trade["symbol"]:
            continue
        if entry["side"].lower() == "buy":
            df.at[i, "pnl"] = (exit_trade["price"] - entry["price"]) * entry["size"]
        elif entry["side"].lower() == "sell":
            df.at[i, "pnl"] = (entry["price"] - exit_trade["price"]) * entry["size"]
        equity_curve.append(equity_curve[-1] + df.at[i, "pnl"])

    # Plot
    plt.figure(figsize=(10,6))
    plt.plot(equity_curve, label="Equity Curve", color="blue")
    plt.title("Equity Curve from Paper Trades")
    plt.xlabel("Trade #")
    plt.ylabel("Equity (PnL)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    plot_equity_curve()
