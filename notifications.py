"""Optional Telegram and SMTP delivery. Credentials are supplied at runtime."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage
import requests


def send_telegram(message: str, token: str, chat_id: str, timeout: int = 15) -> tuple[bool,str]:
    if not token or not chat_id:return False,"Telegram is not configured."
    try:
        response=requests.post(f"https://api.telegram.org/bot{token}/sendMessage",json={"chat_id":chat_id,"text":message},timeout=timeout);response.raise_for_status();return True,"Telegram notification sent."
    except requests.RequestException as exc:return False,f"Telegram failed: {type(exc).__name__}"


def send_email(message: str, subject: str, host: str, port: int, username: str, password: str, recipient: str) -> tuple[bool,str]:
    if not all([host,username,password,recipient]):return False,"Email is not configured."
    mail=EmailMessage();mail["Subject"]=subject;mail["From"]=username;mail["To"]=recipient;mail.set_content(message)
    try:
        if int(port)==465:
            with smtplib.SMTP_SSL(host,int(port),timeout=20) as server:server.login(username,password);server.send_message(mail)
        else:
            with smtplib.SMTP(host,int(port),timeout=20) as server:server.starttls();server.login(username,password);server.send_message(mail)
        return True,"Email notification sent."
    except (OSError,smtplib.SMTPException) as exc:return False,f"Email failed: {type(exc).__name__}"
