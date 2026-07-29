import os
from datetime import datetime

import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def _send(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
    except Exception:
        pass


def send_alert(signal, world, usd, fair, lowest, premium, markets):
    emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}
    
    lines = []
    for name, info in markets.items():
        if info["status"] == "OK":
            lines.append(f"• {name}: {info['price']:,.0f}")
    
    text = f"""{emoji.get(signal["signal"], "⚡")} <b>{signal["signal"]} ALERT</b>

{signal["reason"]}

<b>Platforms:</b>
{chr(10).join(lines)}

<b>Fair Price:</b> {fair:,.0f}
<b>Lowest:</b> {lowest:,.0f}
<b>Premium:</b> {premium:.2f}%

<b>World Gold:</b> {world:.2f} USD/oz
<b>USD:</b> {usd:,} IRR

<i>{datetime.now().strftime("%Y-%m-%d %H:%M")}</i>"""
    
    _send(text)
