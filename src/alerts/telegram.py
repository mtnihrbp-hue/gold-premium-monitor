import os
import sys
import html

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


def _send(text: str):
    """Send a Telegram message.

    Telegram failures are intentionally non-fatal.
    """
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
        status = e.response.status_code if e.response is not None else "UNKNOWN"
        body = e.response.text if e.response is not None else str(e)

        print(
            f"TELEGRAM ERROR HTTP {status}: {body}",
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


def _signal_state_lines(signal_state):
    """Format SP-A normalized signal state.

    This deliberately exposes state rather than reproducing the
    internal decision algorithm.
    """
    if signal_state is None:
        return []

    valuation = getattr(signal_state, "valuation", None)
    momentum = getattr(signal_state, "momentum", None)
    premium_direction = getattr(signal_state, "premium_direction", None)
    structure = getattr(signal_state, "structure", None)
    conflict = getattr(signal_state, "conflict", None)
    candidate = getattr(signal_state, "candidate_decision", None)
    final = getattr(signal_state, "final_decision", None)

    lines = []

    if valuation is not None:
        lines.append(f"Valuation:    {html.escape(str(valuation))}")

    if momentum is not None:
        momentum_text = str(momentum)

        if premium_direction:
            momentum_text += f" ({premium_direction})"

        lines.append(
            f"Momentum:     {html.escape(momentum_text)}"
        )

    if structure is not None:
        lines.append(
            f"Structure:    {html.escape(str(structure))}"
        )

    if conflict is not None:
        lines.append(
            f"Conflict:     {html.escape(str(conflict))}"
        )

    if candidate is not None:
        lines.append(
            f"Candidate:    {html.escape(str(candidate))}"
        )

    if final is not None:
        lines.append(
            f"Decision:     <b>{html.escape(str(final))}</b>"
        )

    return lines


def _signal_state_block(signal_state):
    lines = _signal_state_lines(signal_state)

    if not lines:
        return []

    return [
        SEPARATOR,
        "SIGNAL STATE",
        SEPARATOR,
        *lines,
    ]


def _market_block(
    world,
    usd,
    fair,
    lowest,
    premium,
    trends=None,
    momentum=None,
    markets=None,
    input_directions=None,
):
    lines = [
        SEPARATOR,
        "MARKET",
        SEPARATOR,
        f"Fair Price:  {_money(fair)}",
        f"Lowest:      {_money(lowest)}",
        f"Premium:     {_number(premium)}%",
    ]

    trend_lines = format_trend_lines(trends)

    if trend_lines:
        lines.extend(trend_lines)

    if world is not None:
        lines.append(
            f"World Gold:  {_number(world)} USD/oz"
        )

    if usd is not None:
        lines.append(
            f"USD:         {_money(usd)} IRR"
        )

    momentum_lines = format_momentum_block(momentum)

    if momentum_lines:
        lines.extend([
            "",
            SEPARATOR,
            "MOMENTUM",
            SEPARATOR,
            *momentum_lines,
        ])

    if markets:
        structure = format_market_structure(markets, fair)

        if structure:
            structure_lines = format_market_structure_block(structure)

            if structure_lines:
                lines.extend([
                    "",
                    SEPARATOR,
                    "MARKET STRUCTURE",
                    SEPARATOR,
                    *structure_lines,
                ])

    if input_directions:
        lines.extend([
            "",
            "INPUT DIRECTIONS",
        ])

        world_direction = input_directions.get("world")

        if world_direction:
            lines.append(
                f"World Gold: {world_direction.get('arrow', '→')} "
                f"({world_direction.get('pct', 0):+.2f}%)"
            )

        usd_direction = input_directions.get("usd")

        if usd_direction:
            lines.append(
                f"USD:        {usd_direction.get('arrow', '→')} "
                f"({usd_direction.get('pct', 0):+.2f}%)"
            )

    return lines


def send_processing():
    """Heartbeat used by manual runs."""
    _send(
        "\n".join([
            "GOLDPremium:",
            "Processing market data...",
            format_timestamp(),
        ])
    )


def send_data_unavailable(
    usd=None,
    markets=None,
    reason="Market data unavailable.",
):
    """Notify Telegram that required data is unavailable."""
    lines = [
        "GOLDPremium:",
        "",
        "DATA UNAVAILABLE",
        "",
        html.escape(str(reason)),
    ]

    if usd is not None:
        lines.extend([
            "",
            f"USD: {_money(usd)} IRR",
        ])

    if markets:
        valid_count = sum(
            1
            for info in markets.values()
            if info.get("status") == "OK"
        )

        lines.append(
            f"Platforms available: {valid_count}"
        )

    lines.extend([
        "",
        format_timestamp(),
    ])

    _send("\n".join(lines))


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
    """Send BUY/SELL alert.

    Existing main.py signature is preserved.
    """
    signal_name = signal.get("signal", "UNKNOWN")
    reason = signal.get("reason", "")

    lines = [
        "GOLDPremium:",
        "",
        f"<b>{html.escape(str(signal_name))} ALERT</b>",
        "",
    ]

    lines.extend(
        _market_block(
            world=world,
            usd=usd,
            fair=fair,
            lowest=lowest,
            premium=premium,
            trends=trends,
            momentum=momentum,
            markets=markets,
            input_directions=input_directions,
        )
    )

    state_lines = _signal_state_block(signal_state)

    if state_lines:
        lines.extend([""] + state_lines)

    if markets:
        lines.extend([
            "",
            SEPARATOR,
            "PLATFORMS",
            SEPARATOR,
            _format_platforms(markets, previous_markets),
        ])

    lines.extend([
        "",
        SEPARATOR,
        "DECISION",
        SEPARATOR,
        f"Signal: <b>{html.escape(str(signal_name))}</b>",
        f"Reason: {html.escape(str(reason))}",
        "",
        format_timestamp(),
    ])

    _send("\n".join(lines))


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
    """Send a manual market update.

    Preserves the existing main.py call signature.
    """
    lines = [
        "GOLDPremium:",
        "",
        "<b>MANUAL UPDATE</b>",
        "",
    ]

    lines.extend(
        _market_block(
            world=world,
            usd=usd,
            fair=fair,
            lowest=lowest,
            premium=premium,
            trends=trends,
            momentum=momentum,
            markets=markets,
            input_directions=input_directions,
        )
    )

    state_lines = _signal_state_block(signal_state)

    if state_lines:
        lines.extend([""] + state_lines)

    if markets:
        lines.extend([
            "",
            SEPARATOR,
            "PLATFORMS",
            SEPARATOR,
            _format_platforms(markets, previous_markets),
        ])

    lines.extend([
        "",
        format_timestamp(),
    ])

    _send("\n".join(lines))


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
    """Send scheduled daily Telegram recap."""
    lines = [
        "GOLDPremium:",
        "",
        "<b>DAILY RECAP</b>",
        "",
    ]

    lines.extend(
        _market_block(
            world=world,
            usd=usd,
            fair=fair,
            lowest=lowest,
            premium=premium,
            trends=trends,
            momentum=momentum,
            markets=markets,
            input_directions=input_directions,
        )
    )

    state_lines = _signal_state_block(signal_state)

    if state_lines:
        lines.extend([""] + state_lines)

    if markets:
        lines.extend([
            "",
            SEPARATOR,
            "PLATFORMS",
            SEPARATOR,
            _format_platforms(markets, previous_markets),
        ])

    lines.extend([
        "",
        format_timestamp(),
    ])

    _send("\n".join(lines))
