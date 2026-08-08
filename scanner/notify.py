"""Optional Telegram delivery. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID."""
import os

import requests


def send_telegram(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text[:4000],
                  "disable_web_page_preview": True},
            timeout=15)
        return r.status_code == 200
    except requests.RequestException:
        return False
