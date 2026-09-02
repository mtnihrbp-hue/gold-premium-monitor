"""Shared notification formatting helpers.

Channel-agnostic text formatting used by both Email and Telegram.
"""

from datetime import datetime


def format_platform_bullets(markets, previous_markets=None):
    """Format valid platforms as bullet lines for plain-text / Telegram.

    Deprecated: use format_platform_table instead.
    """
    lines = []
    for name in sorted(markets.keys()):
        info = markets[name]
        if info.get("status") == "OK":
            lines.append(f"• {name}: {info['price']:,.0f}")
    return lines


def format_platform_table(markets, previous_markets=None):
    """Format valid platforms as a sorted table with price change."""
    lines = []
    for name in sorted(markets.keys()):
        info = markets[name]
        if info.get("status") != "OK":
            continue
        price = info["price"]
        prev = previous_markets.get(name) if previous_markets else None
        if prev is not None:
            diff = price - prev
            change = "—" if abs(diff) < 0.01 else f"{diff:+,.0f}"
        else:
            change = "—"
        lines.append(f"{name:<12} {price:>15,.0f} {change:>12}")
    return lines


def format_platform_table_rows(markets, previous_markets=None):
    """Format valid platforms as HTML table rows for Email."""
    rows = ""
    for name in sorted(markets.keys()):
        info = markets[name]
        if info.get("status") != "OK":
            continue
        price = info["price"]
        prev = previous_markets.get(name) if previous_markets else None
        if prev is not None:
            diff = price - prev
            if abs(diff) < 0.01:
                change_html = "—"
            elif diff > 0:
                change_html = f"+{diff:,.0f}"
            else:
                change_html = f"{diff:,.0f}"
        else:
            change_html = "—"

        rows += f"""
<tr>
  <td>{name}</td>
  <td>{price:,.0f}</td>
  <td>{change_html}</td>
</tr>
"""
    return rows


def format_trend_lines(trends):
    """Format trend info as text lines."""
    if not trends:
        return []

    lines = []
    arrow = trends.get("arrow", "→")
    diff = trends.get("arrow_diff")
    pct = trends.get("arrow_pct")
    vs_diff = trends.get("vs_yesterday_diff")
    vs_pct = trends.get("vs_yesterday_pct")

    if diff is not None and pct is not None:
        lines.append(f"Fair Value:      {arrow} ({pct:+.2f}%)")
    if vs_diff is not None and vs_pct is not None:
        lines.append(f"vs Yesterday:    {vs_pct:+.2f}%")

    return lines


SEPARATOR = "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"


def canonical_premium_direction(current_premium, diff):
    """Return canonical premium/discount terminology.

    The sign of current_premium identifies discount vs premium; diff
    identifies widening vs narrowing. This mirrors SP-A analytical state.
    """
    if diff is None or current_premium is None:
        return "→", "STABLE"

    threshold = 0.05
    if abs(diff) < threshold:
        return "→", "DISCOUNT STABLE" if current_premium < 0 else "PREMIUM STABLE"

    if current_premium < 0:
        return ("▼", "DISCOUNT WIDENING") if diff < 0 else ("▲", "DISCOUNT NARROWING")

    return ("▲", "PREMIUM WIDENING") if diff > 0 else ("▼", "PREMIUM NARROWING")


def format_momentum_block(momentum, current_premium=None):
    """Format momentum section using canonical SP-A terminology."""
    if not momentum:
        return []

    lines = []
    vs_today = momentum.get("premium_vs_today")
    vs_yesterday = momentum.get("premium_vs_yesterday")
    candle = momentum.get("candlestick")
    verbal = momentum.get("verbal_direction", "Neutral")

    if vs_today:
        diff = vs_today.get("diff")
        emoji, label = canonical_premium_direction(current_premium, diff)
        lines.append(f"Premium:         {emoji} {label}")
        lines.append(f"  vs today avg:  {diff:+.2f}%" if diff is not None else "  vs today avg:  —")
    else:
        lines.append("Premium:         —")
        lines.append("  vs today avg:  — (first run today)")

    if vs_yesterday:
        y_diff = vs_yesterday.get("diff")
        y_avg = vs_yesterday.get("avg")
        y_date = vs_yesterday.get("date", "")
        if y_diff is not None and y_avg is not None:
            lines.append(f"  vs yesterday:  {y_diff:+.2f}% ({y_date} avg: {y_avg:+.2f}%)")

    if candle:
        n = vs_today["count"] if vs_today else 0
        if n >= 2:
            lines.append(
                f"Candle:          {candle['low']:+.2f}% ━━━━ {candle['high']:+.2f}%  "
                f"(avg {candle['avg']:+.2f}%, n={n})"
            )
        else:
            lines.append(f"Candle:          — (insufficient data, n={n})")

    lines.append(f"Direction:       {verbal}")
    return lines


def format_market_structure(markets, fair_price):
    """Build market structure data for alerts."""
    valid = [
        (name, info["price"])
        for name, info in markets.items()
        if info.get("status") == "OK" and info.get("price") is not None
    ]

    if len(valid) < 2:
        return None

    highest = max(valid, key=lambda x: x[1])
    lowest = min(valid, key=lambda x: x[1])
    spread = highest[1] - lowest[1]
    below_fair = sum(1 for _, price in valid if price < fair_price)
    above_fair = sum(1 for _, price in valid if price >= fair_price)

    if below_fair > above_fair:
        consensus = f"{below_fair}/{len(valid)} below fair (Discount Dominant)"
    elif above_fair > below_fair:
        consensus = f"{above_fair}/{len(valid)} above fair (Premium Dominant)"
    else:
        consensus = f"Split {below_fair}-{above_fair} (Balanced)"

    return {
        "platform_count": len(valid),
        "spread": spread,
        "high_name": highest[0],
        "high_price": highest[1],
        "low_name": lowest[0],
        "low_price": lowest[1],
        "below_count": below_fair,
        "above_count": above_fair,
        "consensus_label": consensus,
        
    }


def format_market_structure_block(structure):
    """Format market structure section for Telegram."""
    if not structure:
        return []

    return [
        f"Platforms:   {structure['platform_count']} active",
        f"Spread:      {structure['spread']:,.0f}",
        f"  High: {structure['high_name']} ({structure['high_price']:,.0f})",
        f"  Low:  {structure['low_name']} ({structure['low_price']:,.0f})",
        f"Consensus:   {structure['consensus_label']}",
    ]


# ---------------------------------------------------------------------------
# UPDATE v1 classification helpers
# ---------------------------------------------------------------------------

def classify_candle(momentum: dict) -> str:
    """Classify premium candle as BULLISH / BEARISH / NEUTRAL / N/A.

    Uses existing candlestick data from build_momentum_context().
    close > open  → BULLISH
    close < open  → BEARISH
    approximately equal (within 0.05 pp) → NEUTRAL
    """
    if not momentum:
        return "N/A"
    candle = momentum.get("candlestick")
    if not candle:
        return "N/A"
    open_p = candle.get("open")
    close_p = candle.get("close")
    if open_p is None or close_p is None:
        return "N/A"
    diff = close_p - open_p
    threshold = 0.05  # Same dead-band as bubble movement convention
    if abs(diff) < threshold:
        return "NEUTRAL"
    return "BULLISH" if diff > 0 else "BEARISH"


def build_update_interpretation(
    price_direction: str,
    bubble_state: str,
    bubble_movement: str,
) -> str:
    """Build concise deterministic interpretation for UPDATE v1.

    Synthesizes measurable state only. No trader psychology.
    """
    parts = []

    if price_direction == "RISING":
        parts.append("Local prices are rising")
    elif price_direction == "FALLING":
        parts.append("Local prices are falling")
    elif price_direction == "STABLE":
        parts.append("Local prices are stable")

    bubble_phrase = ""
    if bubble_state == "NEGATIVE":
        if bubble_movement == "INCREASING":
            bubble_phrase = "The negative bubble is increasing"
        elif bubble_movement == "DECREASING":
            bubble_phrase = "The negative bubble is decreasing"
        elif bubble_movement == "STABLE":
            bubble_phrase = "The negative bubble is stable"
    elif bubble_state == "POSITIVE":
        if bubble_movement == "INCREASING":
            bubble_phrase = "The positive bubble is increasing"
        elif bubble_movement == "DECREASING":
            bubble_phrase = "The positive bubble is decreasing"
        elif bubble_movement == "STABLE":
            bubble_phrase = "The positive bubble is stable"

    if parts and bubble_phrase:
        return f"{parts[0]}. {bubble_phrase}."
    elif bubble_phrase:
        return f"{bubble_phrase}."
    elif parts:
        return f"{parts[0]}."
    return "Insufficient data for interpretation."


def bubble_state_label(premium: float) -> str:
    """Return user-facing bubble state label.

    Positive premium → POSITIVE BUBBLE
    Negative premium → NEGATIVE BUBBLE
    """
    if premium is None:
        return "UNKNOWN"
    return "POSITIVE BUBBLE" if premium >= 0 else "NEGATIVE BUBBLE"


def bubble_state_short(premium: float) -> str:
    """Return short bubble state label for inline display."""
    if premium is None:
        return "UNKNOWN"
    return "POSITIVE" if premium >= 0 else "NEGATIVE"


def format_pct(value: float, decimals: int = 2) -> str:
    """Format a percentage change with sign."""
    if value is None:
        return "—"
    return f"{value:+.2f}%"


def format_pp(value: float, decimals: int = 2) -> str:
    """Format a percentage-point change with sign."""
    if value is None:
        return "—"
    return f"{value:+.2f} pp"


def format_arrow(value: float, threshold: float = 0.0) -> str:
    """Return directional arrow for a signed value."""
    if value is None:
        return "→"
    if abs(value) <= threshold:
        return "→"
    return "↑" if value > 0 else "↓"

def format_timestamp():
    """Return current timestamp string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M")




# ---------------------------------------------------------------------------
# UPDATE v1 Chunk C — Tomans conversion + absolute formatting
# ---------------------------------------------------------------------------

RIALS_PER_TOMAN = 10
"""Conversion: 1 Toman = 10 Rials."""


def to_tomans(rials: float) -> float:
    """Convert Rials to Tomans."""
    if rials is None:
        return None
    return rials / RIALS_PER_TOMAN


def format_m_tomans(value: float, decimals: int = 2) -> str:
    """Format value in Millions of Tomans (full label).

    Example: 222700000 → "22.27M Tomans"
    """
    if value is None:
        return "—"
    tomans = value / RIALS_PER_TOMAN
    m_tomans = tomans / 1_000_000
    return f"{m_tomans:,.{decimals}f}M Tomans"


def format_m_tomans_short(value: float, decimals: int = 2) -> str:
    """Abbreviated M Tomans for table (no unit label).

    Example: 222700000 → "22.27M"
    """
    if value is None:
        return "—"
    tomans = value / RIALS_PER_TOMAN
    m_tomans = tomans / 1_000_000
    return f"{m_tomans:,.{decimals}f}M"


# Override format_pct / format_pp to support absolute mode
def format_pct(value: float, decimals: int = 2, signed: bool = True) -> str:
    """Format a percentage change.

    Args:
        signed: If False, returns absolute value (use with arrow).
    """
    if value is None:
        return "—"
    if not signed:
        return f"{abs(value):.{decimals}f}%"
    return f"{value:+.{decimals}f}%"


def format_pp(value: float, decimals: int = 2, signed: bool = True) -> str:
    """Format a percentage-point change.

    Args:
        signed: If False, returns absolute value (use with arrow).
    """
    if value is None:
        return "—"
    if not signed:
        return f"{abs(value):.{decimals}f} pp"
    return f"{value:+.{decimals}f} pp"
