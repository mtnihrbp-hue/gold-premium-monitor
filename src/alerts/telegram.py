import os
import sys
from datetime import datetime

import requests

from alerts.helpers import (
    format_platform_bullets,
    format_trend_lines,
    format_timestamp,
)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def _send(text: str):
    if not TELEGRAM_BOT_TOKEN:
        print("TELEGRAM SKIP: TELEGRAM_BOT_TOKEN not set", file=sys.stderr)
        return
    if not TELEGRAM_CHAT_ID:
        print("TELEGRAM SKIP: TELEGRAM_CHAT_ID not set", file=sys.stderr)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        print(f"TELEGRAM OK: message sent to chat {TELEGRAM_CHAT_ID}")
    except requests.exceptions.HTTPError as e:
        print(f"TELEGRAM ERROR HTTP {e.response.status_code}: {e.response.text}", file=sys.stderr)
    except Exception as e:
        print(f"TELEGRAM ERROR: {e}", file=sys.stderr)


def _format_trends(trends):
    """Format trend block for Telegram message."""
    if not trends:
        return ""

    lines = format_trend_lines(trends)
    spark = trends.get("sparkline", "")

    if spark:
        lines.append(f"<code>{spark}</code>")

    if lines:
        return "\n".join(lines) + "\n"
    return ""


def send_daily_recap(world, usd, fair, lowest, premium, markets, trends=None):
    platform_lines = format_platform_bullets(markets)
    trend_block = _format_trends(trends)

    text = f"""📊 <b>Daily Gold Report</b>

<b>Fair Price:</b> {fair:,.0f}
<b>Lowest:</b> {lowest:,.0f}
<b>Premium:</b> {premium:.2f}%

{trend_block}<b>World Gold:</b> {world:.2f} USD/oz
<b>USD:</b> {usd:,} IRR

<b>Platforms:</b>
{chr(10).join(platform_lines)}

<i>{format_timestamp()}</i>"""

    _send(text)


def send_alert(signal, world, usd, fair, lowest, premium, markets, trends=None):
    emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}

    platform_lines = format_platform_bullets(markets)
    trend_block = _format_trends(trends)

    text = f"""{emoji.get(signal["signal"], "⚡")} <b>{signal["signal"]} ALERT</b>

{signal["reason"]}

<b>Fair Price:</b> {fair:,.0f}
<b>Lowest:</b> {lowest:,.0f}
<b>Premium:</b> {premium:.2f}%

{trend_block}<b>World Gold:</b> {world:.2f} USD/oz
<b>USD:</b> {usd:,} IRR

<b>Platforms:</b>
{chr(10).join(platform_lines)}

<i>{format_timestamp()}</i>"""

    _send(text)


def send_manual_update(world, usd, fair, lowest, premium, markets, trends=None):
    """Send a manual status update to Telegram (on-demand trigger)."""
    platform_lines = format_platform_bullets(markets)
    trend_block = _format_trends(trends)

    text = f"""📋 <b>Manual Update</b>

<b>Fair Price:</b> {fair:,.0f}
<b>Lowest:</b> {lowest:,.0f}
<b>Premium:</b> {premium:.2f}%

{trend_block}<b>World Gold:</b> {world:.2f} USD/oz
<b>USD:</b> {usd:,} IRR

<b>Platforms:</b>
{chr(10).join(platform_lines)}

<i>{format_timestamp()}</i>"""

    _send(text)
