import os
import sys
import html

import requests

from alerts.helpers import (
    format_platform_table,
    format_trend_lines,
    format_timestamp,
    format_momentum_block,
    format_market_structure,
    format_market_structure_block,
    SEPARATOR,
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
        print(f"TELEGRAM OK: message sent to chat {TELEGRAM_CHAT_ID}")

    except requests.exceptions.HTTPError as e:
        print(
            f"TELEGRAM ERROR HTTP {e.response.status_code}: {e.response.text}",
            file=sys.stderr,
        )

    except Exception as e:
        print(f"TELEGRAM ERROR: {e}", file=sys.stderr)


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
        return f"{float(value):,.2f}"
    except Exception:
        return str(value)


def _format_platforms(markets, previous_markets=None):
    table_lines = format_platform_table(markets, previous_markets)
    if not table_lines:
        return "No platforms available."

    header = f"{'Platform':<12} {'Price':>15} {'Change':>12}"
    separator = "-" * 42

    parts = ["```", header, separator]
    parts.extend(table_lines)
    parts.append("```")
    return "\n".join(parts)


def _build_message(
    header_emoji,
    header_text,
    world,
    usd,
    fair,
    lowest,
    premium,
    trends=None,
    momentum=None,
    markets=None,
    previous_markets=None,
    signal=None,
    reason=None,
):
    lines = []
    lines.append(f"{header_emoji} {header_text}")
    lines.append("")

    # MARKET
    lines.append(SEPARATOR)
    lines.append("📊 MARKET")
    lines.append(SEPARATOR)
    lines.append(f"Fair Price:  {_money(fair)}")
    lines.append(f"Lowest:      {_money(lowest)}")
    lines.append(f"Premium:     {_number(premium)}%")
    lines.append(f"World Gold:  {_number(world)} USD/oz")
    lines.append(f"USD:         {_money(usd)} IRR")
    lines.append("")

    # MOMENTUM
    trend_lines = format_trend_lines(trends) if trends else []
    momentum_lines = format_momentum_block(momentum) if momentum else []
    if trend_lines or momentum_lines:
        lines.append(SEPARATOR)
        lines.append("📈 MOMENTUM")
        lines.append(SEPARATOR)
        lines.extend(trend_lines)
        if trend_lines and momentum_lines:
            lines.append("")
        lines.extend(momentum_lines)
        lines.append("")

    # MARKET STRUCTURE
    if markets:
        structure = format_market_structure(markets, fair)
        if structure:
            lines.append(SEPARATOR)
            lines.append("🏛️ MARKET STRUCTURE")
            lines.append(SEPARATOR)
            lines.extend(format_market_structure_block(structure))
            lines.append("")
            platform_block = _format_platforms(markets, previous_markets)
            lines.append("**Platforms:**")
            lines.append(platform_block)
            lines.append("")

    # DECISION (alerts only)
    if signal:
        lines.append(SEPARATOR)
        lines.append("⚡ DECISION")
        lines.append(SEPARATOR)
        emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}.get(signal, "⚡")
        lines.append(f"Signal:      {emoji} {signal}")
        if reason:
            lines.append(f"Reason:      {reason}")
        lines.append("")

    lines.append(f"_{format_timestamp()}_")

    return "\n".join(lines)


def send_daily_recap(
    world,
    usd,
    fair,
    lowest,
    premium,
    markets,
    trends=None,
    momentum=None,
    previous_markets=None,
):
    text = _build_message(
        "📊",
        "Daily Gold Report",
        world,
        usd,
        fair,
        lowest,
        premium,
        trends=trends,
        momentum=momentum,
        markets=markets,
        previous_markets=previous_markets,
    )
    _send(text)


def send_alert(
    signal,
    world,
    usd,
    fair,
    lowest,
    premium,
    markets,
    trends=None,
    momentum=None,
    previous_markets=None,
):
    text = _build_message(
        "⚡",
        f"{signal['signal']} ALERT",
        world,
        usd,
        fair,
        lowest,
        premium,
        trends=trends,
        momentum=momentum,
        markets=markets,
        previous_markets=previous_markets,
        signal=signal["signal"],
        reason=signal.get("reason"),
    )
    _send(text)


def send_manual_update(
    world,
    usd,
    fair,
    lowest,
    premium,
    markets,
    trends=None,
    momentum=None,
    previous_markets=None,
):
    text = _build_message(
        "📋",
        "Manual Update",
        world,
        usd,
        fair,
        lowest,
        premium,
        trends=trends,
        momentum=momentum,
        markets=markets,
        previous_markets=previous_markets,
    )
    _send(text)


def send_data_unavailable(
    usd=None,
    markets=None,
    reason="World gold price unavailable",
):
    lines = []
    lines.append("⚠️ **Data Temporarily Unavailable**")
    lines.append("")
    lines.append(html.escape(reason))
    lines.append("")

    if usd:
        lines.append(f"**USD:** {_money(usd)} IRR")
    if markets:
        table_lines = format_platform_table(markets)
        if table_lines:
            lines.append("")
            lines.append("**Platforms:**")
            lines.append("```")
            lines.extend(table_lines)
            lines.append("```")

    lines.append("")
    lines.append(f"_{format_timestamp()}_")

    _send("\n".join(lines))


def send_processing():
    _send("⏳ **Collecting market data...**")
