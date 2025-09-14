import pandas as pd
import os
import json
import requests
from datetime import datetime, timedelta, timezone

# ─── Config ─────────────────────────────
LOG_FILE = "data/paper_trades.csv"
SUMMARY_CSV = "data/summary_report.csv"
SUMMARY_JSON = "data/summary_report.json"
DEBUG_LOG = "data/telegram_debug.log"

THAI_TZ = timezone(timedelta(hours=7))


# ─── Logger ─────────────────────────────
def get_thai_time():
    return datetime.now(THAI_TZ).strftime("%Y-%m-%d %H:%M:%S")


def write_log(message: str):
    """เขียน log ลงไฟล์ + print console พร้อม timestamp ไทย"""
    os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
    line = f"[{get_thai_time()}] {message}\n"
    with open(DEBUG_LOG, "a", encoding="utf-8") as f:
        f.write(line)
    print(line.strip())


# ─── Telegram ──────────────────────────
def send_telegram_message(message: str):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        msg = "⚠️ TELEGRAM_TOKEN หรือ TELEGRAM_CHAT_ID ไม่ถูกตั้งค่า"
        write_log(msg)
        write_log("ข้อความที่ควรส่ง: " + message)
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code != 200:
            write_log(f"❌ Telegram API error: {response.text}")
        else:
            write_log(f"✅ ส่งข้อความไป Telegram สำเร็จ")
    except Exception as e:
        write_log(f"Error sending to Telegram: {e}")


# ─── Summary Generator ──────────────────
def generate_summary(log_file=LOG_FILE):
    if not os.path.exists(log_file):
        msg = f"❌ Log file not found: {log_file}"
        write_log(msg)
        send_telegram_message(msg)
        return msg

    df = pd.read_csv(log_file)
    if df.empty or len(df) < 2:
        msg = "❌ Not enough trades in log."
        write_log(msg)
        send_telegram_message(msg)
        return msg

    # คำนวณ PnL จาก entry-exit
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

    # Performance summary
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
        "winrate": round(winrate, 2),
        "total_pnl": round(total_pnl, 4),
        "avg_pnl": round(avg_pnl, 4),
        "per_symbol": per_symbol,
        "profit_factor": round(profit_factor, 2),
        "max_drawdown": round(max_drawdown, 2),
    }

    # Save
    os.makedirs(os.path.dirname(SUMMARY_CSV), exist_ok=True)
    pd.DataFrame([summary]).to_csv(SUMMARY_CSV, index=False)
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=4, ensure_ascii=False)

    write_log("===== Trading Performance Summary =====")
    for k, v in summary.items():
        write_log(f"{k}: {v}")
    write_log(f"✅ Summary saved: {SUMMARY_CSV}, {SUMMARY_JSON}")

    # ส่งไป Telegram พร้อมเวลาไทย
    msg = (
        f"📊 Daily Summary Report ({get_thai_time()})\n"
        f"รวมการเทรด: {summary['trades']}\n"
        f"ชนะ: {summary['wins']} | แพ้: {summary['losses']}\n"
        f"Winrate: {summary['winrate']}%\n"
        f"กำไรรวม: {summary['total_pnl']} USDT\n"
        f"Profit Factor: {summary['profit_factor']}\n"
        f"Max Drawdown: {summary['max_drawdown']} USDT"
    )
    send_telegram_message(msg)

    return summary


if __name__ == "__main__":
    generate_summary()
