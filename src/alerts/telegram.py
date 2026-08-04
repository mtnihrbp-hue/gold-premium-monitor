import os
import sys
import html

import requests

from alerts.helpers import (
    format_platform_table,
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
        response = requests.post(
            url,
            json=payload,
            timeout=15,
        )

        response.raise_for_status()

        print(
            f"TELEGRAM OK: message sent to chat {TELEGRAM_CHAT_ID}"
        )

    except requests.exceptions.HTTPError as e:
        print(
            f"TELEGRAM ERROR HTTP {e.response.status_code}: {e.response.text}",
            file=sys.stderr,
        )

    except Exception as e:
        print(
            f"TELEGRAM ERROR: {e}",
            file=sys.stderr,
        )


# -----------------------------
# Safe format helpers
# -----------------------------

def _money(value):
    if value is None:
        return "N/A"

    try:
        return f"{float(value):,.0f}"
    except Exception:
        return str(value)


def _number(value, decimals=2):
    if value is None:
        return "N/A"

    try:
        return f"{float(value):.{decimals}f}"
    except Exception:
        return str(value)


def _signed(value):
    if value is None:
        return "N/A"

    try:
        return f"{float(value):+,.0f}"
    except Exception:
        return str(value)


# -----------------------------
# Trend formatting
# -----------------------------

def _format_trends(trends=None, sparkline=None):
    lines = []

    if trends:
        lines.extend(format_trend_lines(trends))

        # Replace sparkline with directional sentence
        premium_direction = trends.get("premium_direction")
        if premium_direction:
            lines.append(premium_direction)

    # Sparkline removed — no longer rendered
    # if sparkline is None:
    #     sparkline = trends.get("sparkline")
    # if sparkline:
    #     lines.append(
    #         f"Premium Trend: `{html.escape(str(sparkline))}`"
    #     )

    if not lines:
        return ""

    return "\n".join(lines) + "\n"


# -----------------------------
# Platform formatting
# -----------------------------

def _format_platforms(markets, previous_markets=None):
    table_lines = format_platform_table(
        markets,
        previous_markets,
    )

    if not table_lines:
        return "No platforms available."

    header = (
        f"{'Platform':<12} "
        f"{'Price':>15} "
        f"{'Change':>12}"
    )

    separator = "-" * 42

    return (
        "```\n"
        f"{header}\n"
        f"{separator}\n"
        f"{chr(10).join(table_lines)}"
        "\n```"
    )


# -----------------------------
# Daily recap
# -----------------------------

def send_daily_recap(
    world,
    usd,
    fair,
    lowest,
    premium,
    markets,
    trends=None,
    sparkline="",
    previous_markets=None,
):

    trend_block = _format_trends(
        trends,
        sparkline,
    )

    platform_block = _format_platforms(
        markets,
        previous_markets,
    )

    text = f"""📊 <b>Daily Gold Report</b>

<b>Fair Price:</b> {_money(fair)}
<b>Lowest:</b> {_money(lowest)}
<b>Premium:</b> {_number(premium)}%

{trend_block}<b>World Gold:</b> {_number(world)} USD/oz
<b>USD:</b> {_money(usd)} IRR

<b>Platforms:</b>
{platform_block}

<i>{format_timestamp()}</i>"""

    _send(text)


# -----------------------------
# Alert
# -----------------------------

def send_alert(
    signal,
    world,
    usd,
    fair,
    lowest,
    premium,
    markets,
    trends=None,
    sparkline="",
    previous_markets=None,
):

    emoji = {
        "BUY": "🟢",
        "SELL": "🔴",
        "HOLD": "⚪",
    }

    trend_block = _format_trends(
        trends,
        sparkline,
    )

    platform_block = _format_platforms(
        markets,
        previous_markets,
    )

    text = f"""{emoji.get(signal["signal"], "⚡")} <b>{signal["signal"]} ALERT</b>

{signal["reason"]}

<b>Fair Price:</b> {_money(fair)}
<b>Lowest:</b> {_money(lowest)}
<b>Premium:</b> {_number(premium)}%

{trend_block}<b>World Gold:</b> {_number(world)} USD/oz
<b>USD:</b> {_money(usd)} IRR

<b>Platforms:</b>
{platform_block}

<i>{format_timestamp()}</i>"""

    _send(text)


# -----------------------------
# Manual update
# -----------------------------

def send_manual_update(
    world,
    usd,
    fair,
    lowest,
    premium,
    markets,
    trends=None,
    sparkline="",
    previous_markets=None,
):
    """
    Manual status update triggered by workflow.
    """

    trend_block = _format_trends(
        trends,
        sparkline,
    )

    platform_block = _format_platforms(
        markets,
        previous_markets,
    )

    text = f"""📋 <b>Manual Update</b>

<b>Fair Price:</b> {_money(fair)}
<b>Lowest:</b> {_money(lowest)}
<b>Premium:</b> {_number(premium)}%

{trend_block}<b>World Gold:</b> {_number(world)} USD/oz
<b>USD:</b> {_money(usd)} IRR

<b>Platforms:</b>
{platform_block}

<i>{format_timestamp()}</i>"""

    _send(text)


# -----------------------------
# Missing data message
# -----------------------------

def send_data_unavailable(
    usd=None,
    markets=None,
    reason="World gold price unavailable",
):

    lines = []

    if markets:
        lines = format_platform_table(markets)

    usd_line = (
        f"<b>USD:</b> {_money(usd)} IRR\n"
        if usd
        else ""
    )

    platforms_line = (
        "\n<b>Platforms:</b>\n"
        + "\n".join(lines)
        if lines
        else ""
    )

    text = f"""⚠️ <b>Data Temporarily Unavailable</b>

{html.escape(reason)}

{usd_line}{platforms_line}

<i>{format_timestamp()}</i>"""

    _send(text)


# -----------------------------
# Processing heartbeat
# -----------------------------

def send_processing():
    _send(
        "⏳ <b>Collecting market data...</b>"
    )
