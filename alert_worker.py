"""CLI alert evaluator for Windows Task Scheduler or cron."""
from __future__ import annotations
import os
from notifications import send_email,send_telegram
from research import evaluate_alerts
from storage import newly_triggered,watchlist

def main() -> None:
    evaluated=evaluate_alerts(watchlist());triggered=newly_triggered(evaluated)
    if triggered.empty:return
    message="AANIANG alerts\n"+"\n".join(f"{row.Symbol}: {row.Alert} at {row['Last price']}" for _,row in triggered.iterrows())
    send_telegram(message,os.getenv("TELEGRAM_BOT_TOKEN",""),os.getenv("TELEGRAM_CHAT_ID",""))
    send_email(message,"AANIANG Trading Alert",os.getenv("SMTP_HOST",""),int(os.getenv("SMTP_PORT","587")),os.getenv("SMTP_USER",""),os.getenv("SMTP_PASSWORD",""),os.getenv("ALERT_EMAIL",""))

if __name__=="__main__":main()
