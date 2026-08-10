"""Telegram alert formatter and sender.

SP-A CHANGES:
- Preserves all existing public functions (send_alert, send_manual_update,
  send_data_unavailable, send_processing, send_daily_recap).
- Adds format_decision_section() for SP-A market state breakdown.
- Replaces ASCII sparkline with directional sentence (per project memory).
"""

import os
import sys
import html

import requests
from typing import Optional

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
        return f"{float(value):,.{decimals}f}"
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


# ---------------------------------------------------------------------------
# SP-A: Decision section formatter
# ---------------------------------------------------------------------------

def format_decision_section(signal_state) -> str:
    """Format the SP-A DECISION section for Telegram.

    Args:
        signal_state: SignalState dataclass with valuation, momentum,
                      structure, conflict, candidate_decision,
                      final_decision, reason.

    Returns:
        HTML-formatted string for the DECISION block.
    """
    if signal_state is None:
        return ""

    lines = [
        SEPARATOR,
        "⚡ <b>DECISION</b>",
        SEPARATOR,
        "",
        "<b>Market State:</b>",
        f"  Valuation:  <code>{signal_state.valuation}</code>",
        f"  Momentum:   <code>{signal_state.momentum}</code> ({signal_state.premium_direction.replace('_', ' ')})",
        f"  Structure:  <code>{signal_state.structure.replace('_', ' ')}</code>",
        f"  Conflict:   <code>{signal_state.conflict.replace('_', ' ')}</code>",
        "",
        f"Candidate:   <code>{signal_state.candidate_decision}</code>",
    ]

    # Final decision with emoji
    final = signal_state.final_decision
    if final == "BUY":
        final_line = "Final:       🟢 <b>BUY</b>"
    elif final == "SELL":
        final_line = "Final:       🔴 <b>SELL</b>"
    elif final == "WAIT":
        final_line = "Final:       ⚪ <b>WAIT</b>"
    else:
        final_line = f"Final:       <code>{final}</code>"
    lines.append(final_line)

    # Reason
    if signal_state.reason:
        lines.extend(["", "<b>Reason:</b>", f"  {signal_state.reason}"])

    lines.append("")
    return "\n".join(lines)


def _format_input_directions(input_directions) -> str:
    """Format input directions section."""
    if not input_directions:
        return ""

    lines = [SEPARATOR, "📊 <b>INPUT DIRECTIONS</b>", SEPARATOR, ""]
    wd = input_directions.get("world")
    if wd:
        stale = f" stale={wd['stale_count']}" if wd.get("stale_count") else ""
        lines.append(
            f"World Gold: {wd['arrow']} ({wd['pct']:+.2f}%){stale}"
        )
    ud = input_directions.get("usd")
    if ud:
        stale = f" stale={ud['stale_count']}" if ud.get("stale_count") else ""
        lines.append(
            f"USD Rate:   {ud['arrow']} ({ud['pct']:+.2f}%){stale}"
        )
    lines.append("")
    return "\n".join(lines)


def _format_trends_section(trends) -> str:
    """Format trends section with directional sentence (no sparkline)."""
    if not trends:
        return ""

    lines = [SEPARATOR, "📈 <b>TRENDS</b>", SEPARATOR, ""]

    trend_lines = format_trend_lines(trends)
    if trend_lines:
        lines.extend(trend_lines)
    else:
        lines.append("No trend data available.")

    # Directional sentence replaces sparkline
    premium_direction = trends.get("premium_direction", "")
    if premium_direction:
        lines.append("")
        lines.append(premium_direction)

    lines.append("")
    return "\n".join(lines)


def _format_momentum_section(momentum) -> str:
    """Format momentum section."""
    if not momentum:
        return ""

    lines = [SEPARATOR, "🌊 <b>MOMENTUM</b>", SEPARATOR, ""]
    block = format_momentum_block(momentum)
    if block:
        lines.extend(block)
    else:
        lines.append("No momentum data available.")
    lines.append("")
    return "\n".join(lines)


def _format_structure_section(markets, fair_price) -> str:
    """Format market structure section."""
    structure = format_market_structure(markets, fair_price)
    if not structure:
        return ""

    lines = [SEPARATOR, "🏛 <b>MARKET STRUCTURE</b>", SEPARATOR, ""]
    block = format_market_structure_block(structure)
    lines.extend(block)
    lines.append("")
    return "\n".join(lines)


def _build_common_body(
    world,
    usd,
    fair,
    lowest,
    premium,
    markets,
    trends=None,
    momentum=None,
    previous_markets=None,
    input_directions=None,
    signal_state=None,
) -> str:
    """Build the common message body shared by all alert types."""
    lines = []

    # Timestamp
    lines.append(f"<b>{format_timestamp()}</b>")
    lines.append("")

    # Inputs
    lines.append(f"World Gold: ${_money(world)}  |  USD: {_money(usd)} IRR")
    lines.append("")

    # Fair / Lowest / Premium
    lines.append(f"Fair Price:  {_money(fair)} IRR")
    lines.append(f"Lowest:      {_money(lowest)} IRR")
    lines.append(f"Premium:     {_number(premium)}%")
    lines.append("")

    # Platform table
    lines.append(_format_platforms(markets, previous_markets))
    lines.append("")

    # SP-A Decision section
    if signal_state is not None:
        lines.append(format_decision_section(signal_state))

    # Trends (directional sentence, no sparkline)
    lines.append(_format_trends_section(trends))

    # Momentum
    lines.append(_format_momentum_section(momentum))

    # Market Structure
    lines.append(_format_structure_section(markets, fair))

    # Input Directions
    lines.append(_format_input_directions(input_directions))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PUBLIC API — preserved for all existing callers
# ---------------------------------------------------------------------------

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
    input_directions=None,
    signal_state=None,
):
    """Send a BUY/SELL alert via Telegram.

    Args:
        signal: dict with keys "signal", "new_alert_type", "reason"
        world: world gold price in USD
        usd: USD/IRR rate
        fair: fair price in IRR
        lowest: lowest market price in IRR
        premium: premium percentage
        markets: dict of platform data
        trends: optional trends dict
        momentum: optional momentum dict
        previous_markets: optional previous market prices
        input_directions: optional input directions dict
        signal_state: optional SignalState dataclass
    """
    alert_type = signal.get("signal", "ALERT") if signal else "ALERT"
    reason = signal.get("reason", "") if signal else ""

    if alert_type == "BUY":
        header = "🟢 <b>BUY SIGNAL</b> 🟢"
    elif alert_type == "SELL":
        header = "🔴 <b>SELL SIGNAL</b> 🔴"
    else:
        header = f"⚡ <b>{alert_type} SIGNAL</b>"

    body = _build_common_body(
        world, usd, fair, lowest, premium, markets,
        trends=trends,
        momentum=momentum,
        previous_markets=previous_markets,
        input_directions=input_directions,
        signal_state=signal_state,
    )

    message = f"{header}\n\n{reason}\n\n{body}"
    _send(message)


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
    input_directions=None,
    signal_state=None,
):
    """Send a manual update (no active signal) via Telegram."""
    header = "📊 <b>MANUAL UPDATE</b>"

    body = _build_common_body(
        world, usd, fair, lowest, premium, markets,
        trends=trends,
        momentum=momentum,
        previous_markets=previous_markets,
        input_directions=input_directions,
        signal_state=signal_state,
    )

    message = f"{header}\n\n{body}"
    _send(message)


def send_data_unavailable(usd=None, markets=None, reason=None):
    """Send a data-unavailable notification."""
    lines = [
        "⚠️ <b>DATA UNAVAILABLE</b>",
        "",
        f"{reason or 'Unable to fetch required market data.'}",
        "",
    ]

    if usd is not None:
        lines.append(f"USD Rate: {_money(usd)} IRR")
    if markets:
        lines.append("")
        lines.append("<b>Available Platforms:</b>")
        for name, info in sorted(markets.items()):
            if info.get("status") == "OK":
                lines.append(f"  {name}: {_money(info.get('price'))}")

    message = "\n".join(lines)
    _send(message)


def send_processing():
    """Send a processing heartbeat (manual trigger)."""
    _send("⏳ <b>Processing...</b> Gathering market data.")


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
    input_directions=None,
    signal_state=None,
):
    """Send the daily scheduled recap via Telegram."""
    header = "📅 <b>DAILY RECAP</b>"

    body = _build_common_body(
        world, usd, fair, lowest, premium, markets,
        trends=trends,
        momentum=momentum,
        previous_markets=previous_markets,
        input_directions=input_directions,
        signal_state=signal_state,
    )

    message = f"{header}\n\n{body}"
    _send(message)
