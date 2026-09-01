"""Optional delivery channels. Every sender is opt-in and fail-soft: if its
environment variables are absent, or the network call errors, it prints one
line, returns False, and the scan carries on. Nothing here can fail a run.

  Telegram   TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
  Slack      SLACK_WEBHOOK_URL  (incoming webhook, e.g.
             https://hooks.slack.com/services/T.../B.../...)

The Slack URL is a bearer credential — anyone holding it can post to the
channel — so it belongs in a repo secret, never in this file.
"""
import os

import requests

TIMEOUT = 20
MAX_BLOCKS = 50      # Slack silently truncates past this, with no error


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


def send_slack(text: str, blocks=None) -> bool:
    """Post to an incoming webhook. `text` is the notification fallback that
    shows in the push alert and sidebar preview, so it is always sent even
    when blocks carry the real layout.

    A malformed block payload returns 400 invalid_blocks; rather than lose
    the alert we retry once as plain text.
    """
    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        print("  SLACK_WEBHOOK_URL not set — slack skipped")
        return False

    payload = {"text": text[:3000]}
    if blocks:
        if len(blocks) > MAX_BLOCKS:
            print(f"  slack: {len(blocks)} blocks, trimming to {MAX_BLOCKS}")
            blocks = blocks[:MAX_BLOCKS]
        payload["blocks"] = blocks
    try:
        r = requests.post(url, json=payload, timeout=TIMEOUT)
        if r.status_code == 200:
            return True
        print(f"  slack failed {r.status_code}: {r.text[:200]}")
        if blocks:
            r2 = requests.post(url, json={"text": text[:3000]},
                               timeout=TIMEOUT)
            if r2.status_code == 200:
                print("  slack: blocks rejected, sent as plain text")
                return True
    except requests.RequestException as e:
        print(f"  slack error: {type(e).__name__}: {e}")
    return False
