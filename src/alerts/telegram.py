"""Telegram alert formatter and sender for SP-A."""

import os
import sys

import requests

from alerts.helpers import (
    format_platform_table,
    format_trend_lines,
    format_momentum_block,
    format_market_structure,
    format_market_structure_block,
    format_timestamp,
    SEPARATOR,
)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
APP_HEADER = "GOLDPremium:"


def _send(text: str):
    if not TELEGRAM_BOT_TOKEN:
        print("TELEGRAM SKIP: TELEGRAM_BOT_TOKEN not set", file=sys.stderr)
        return
    if not TELEGRAM_CHAT_ID:
        print("TELEGRAM SKIP: TELEGRAM_CHAT_ID not set", file=sys.stderr)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}

    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        print(f"TELEGRAM OK: message sent to chat {TELEGRAM_CHAT_ID}")
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "UNKNOWN"
        body = e.response.text if e.response is not None else str(e)
        print(f"TELEGRAM ERROR HTTP {status}: {body}", file=sys.stderr)
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
    return "\n".join(["```", f"{'Platform':<12} {'Price':>15} {'Change':>12}", "-" * 42, *table_lines, "```"])


def format_decision_section(signal_state):
    if signal_state is None:
        return ""
    lines = [
        SEPARATOR, "<b>DECISION</b>", SEPARATOR, "", "<b>Market State:</b>",
        f"  Valuation:  <code>{signal_state.valuation}</code>",
        f"  Momentum:   <code>{signal_state.momentum}</code> ({signal_state.premium_direction.replace('_', ' ')})",
        f"  Structure:  <code>{signal_state.structure.replace('_', ' ')}</code>",
        f"  Conflict:   <code>{signal_state.conflict.replace('_', ' ')}</code>", "",
        f"Candidate:   <code>{signal_state.candidate_decision}</code>",
    ]
    final = signal_state.final_decision
    lines.append(f"Final:       <b>{final}</b>" if final in {"BUY", "SELL", "WAIT"} else f"Final:       <code>{final}</code>")
    if signal_state.reason:
        lines.extend(["", "<b>Reason:</b>", f"  {signal_state.reason}"])
    return "\n".join(lines)


def _format_market_section(world, usd, fair, lowest, premium, input_directions=None):
    lines = [
        SEPARATOR, "<b>MARKET</b>", SEPARATOR, "",
        f"World Gold: ${_money(world)}  |  USD: {_money(usd)} IRR",
        f"Fair Price:  {_money(fair)} IRR",
        f"Lowest:      {_money(lowest)} IRR",
        f"Premium:     {_number(premium)}%",
    ]
    if input_directions:
        wd = input_directions.get("world")
        ud = input_directions.get("usd")
        if wd:
            stale = f" stale={wd['stale_count']}" if wd.get("stale_count") else ""
            lines.append(f"World Gold:  {wd['arrow']} ({wd['pct']:+.2f}%){stale}")
        if ud:
            stale = f" stale={ud['stale_count']}" if ud.get("stale_count") else ""
            lines.append(f"USD:         {ud['arrow']} ({ud['pct']:+.2f}%){stale}")
    return "\n".join(lines)


def _format_trends_section(trends):
    if not trends:
        return ""
    lines = [SEPARATOR, "<b>TRENDS</b>", SEPARATOR, ""]
    lines.extend(format_trend_lines(trends) or ["No trend data available."])
    premium_direction = trends.get("premium_direction")
    if premium_direction:
        lines.extend(["", premium_direction])
    return "\n".join(lines)


def _format_momentum_section(momentum, current_premium):
    if not momentum:
        return ""
    lines = [SEPARATOR, "<b>MOMENTUM</b>", SEPARATOR, ""]
    lines.extend(format_momentum_block(momentum, current_premium=current_premium) or ["No momentum data available."])
    return "\n".join(lines)


def _format_structure_section(markets, fair_price):
    structure = format_market_structure(markets, fair_price)
    if not structure:
        return ""
    lines = [SEPARATOR, "<b>MARKET STRUCTURE</b>", SEPARATOR, ""]
    lines.extend(format_market_structure_block(structure))
    return "\n".join(lines)


def _format_platforms_section(markets, previous_markets=None):
    return "\n".join([
        SEPARATOR, "<b>PLATFORMS</b>", SEPARATOR, "",
        _format_platforms(markets, previous_markets), "",
    ])


def _build_common_body(world, usd, fair, lowest, premium, markets, trends=None, momentum=None, previous_markets=None, input_directions=None, signal_state=None):
    sections = [
        _format_market_section(world, usd, fair, lowest, premium, input_directions),
        format_decision_section(signal_state),
        _format_trends_section(trends),
        _format_momentum_section(momentum, premium),
        _format_structure_section(markets, fair),
        _format_platforms_section(markets, previous_markets),
        f"<b>{format_timestamp()}</b>",
    ]
    return "\n\n".join(section for section in sections if section)


def _build_message(message_type_header, reason, body):
    parts = [APP_HEADER, "", message_type_header]
    if reason:
        parts.extend(["", reason])
    parts.extend(["", body])
    return "\n".join(parts)


def send_alert(signal, world, usd, fair, lowest, premium, markets, trends=None, momentum=None, previous_markets=None, input_directions=None, signal_state=None):
    if signal_state is not None:
        alert_type = signal_state.final_decision
        if alert_type not in {"BUY", "SELL"}:
            return
        reason = signal_state.reason or ""
    else:
        alert_type = signal.get("signal", "ALERT") if signal else "ALERT"
        if alert_type not in {"BUY", "SELL"}:
            return
        reason = signal.get("reason", "") if signal else ""

    header = f"<b>{alert_type} SIGNAL</b>"
    body = _build_common_body(world, usd, fair, lowest, premium, markets, trends, momentum, previous_markets, input_directions, signal_state)
    _send(_build_message(header, reason, body))


def send_manual_update(world, usd, fair, lowest, premium, markets, trends=None, momentum=None, previous_markets=None, input_directions=None, signal_state=None):
    body = _build_common_body(world, usd, fair, lowest, premium, markets, trends, momentum, previous_markets, input_directions, signal_state)
    _send(_build_message("<b>MANUAL UPDATE</b>", "", body))


def send_data_unavailable(usd=None, markets=None, reason=None):
    lines = [APP_HEADER, "", "<b>DATA UNAVAILABLE</b>", "", reason or "Unable to fetch required market data."]
    if usd is not None:
        lines.append(f"USD Rate: {_money(usd)} IRR")
    if markets:
        valid = [name for name, info in markets.items() if info.get("status") == "OK"]
        lines.append(f"Available platforms: {len(valid)}")
    _send("\n".join(lines))


def send_processing():
    _send(f"{APP_HEADER}\n\n<b>Processing...</b> Gathering market data.")


def send_daily_recap(world, usd, fair, lowest, premium, markets, trends=None, momentum=None, previous_markets=None, input_directions=None, signal_state=None):
    body = _build_common_body(world, usd, fair, lowest, premium, markets, trends, momentum, previous_markets, input_directions, signal_state)
    _send(_build_message("<b>DAILY RECAP</b>", "", body))
