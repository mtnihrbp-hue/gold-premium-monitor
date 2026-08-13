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
            if abs(diff) < 0.01:
                change = "—"
            else:
                change = f"{diff:+,.0f}"
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
    """Format trend info as text lines.

    Returns a list of strings. Empty list if no trends available.
    """
    if not trends:
        return []

    lines = []
    arrow = trends.get("arrow", "→")
    diff = trends.get("arrow_diff")
    pct = trends.get("arrow_pct")
    ma7 = trends.get("ma7")
    vs_diff = trends.get("vs_yesterday_diff")
    vs_pct = trends.get("vs_yesterday_pct")

    if diff is not None and pct is not None:
        lines.append(f"Fair Value:      {arrow} ({pct:+.2f}%)")
    if vs_diff is not None and vs_pct is not None:
        lines.append(f"vs Yesterday:    {vs_pct:+.2f}%")

    return lines


# --- Task C: Momentum & Market Structure formatting ---

SEPARATOR = "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"


def _canonical_premium_label(diff):
    """Map premium diff to canonical SP-A terminology."""
    if diff is None:
        return "→", "STABLE"
    if diff < -0.05:
        return "▼", "DISCOUNT WIDENING"
    elif diff > 0.05:
        return "▲", "PREMIUM WIDENING"
    else:
        return "→", "STABLE"

def format_momentum_block(momentum):
    """Format momentum section for Telegram.

    Returns a list of strings. Empty list if no momentum data.
    """
    if not momentum:
        return []

    lines = []
    vs_today = momentum.get("premium_vs_today")
    vs_yesterday = momentum.get("premium_vs_yesterday")
    candle = momentum.get("candlestick")
    verbal = momentum.get("verbal_direction", "Neutral")

    # Premium label line — always show, even when vs_today is None (R4)
    if vs_today:
        
        diff = vs_today.get("diff")
        emoji, label = _canonical_premium_label(diff)
        lines.append(f"Premium:         {emoji} {label}")
        
        lines.append(
            f"  vs today avg:  {vs_today['diff']:+.2f}%"
        )
    else:
        lines.append("Premium:         —")
        lines.append("  vs today avg:  — (first run today)")

    if vs_yesterday:
        lines.append(
            f"  vs yesterday:  {vs_yesterday['diff']:+.2f}% "
            f"({vs_yesterday['date']} avg: {vs_yesterday['avg']:+.2f}%)"
        )

    # Candlestick — hide range bar when n < 2 (R2)
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
    """Build market structure data for alerts.

    Returns dict with platform_count, spread, high_name, high_price,
    low_name, low_price, consensus_label.
    Returns None if fewer than 2 valid platforms.
    """
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
        "consensus_label": consensus,
    }


def format_market_structure_block(structure):
    """Format market structure section for Telegram.

    Returns a list of strings. Empty list if no structure data.
    """
    if not structure:
        return []

    lines = [
        f"Platforms:   {structure['platform_count']} active",
        f"Spread:      {structure['spread']:,.0f}",
        f"  High: {structure['high_name']} ({structure['high_price']:,.0f})",
        f"  Low:  {structure['low_name']} ({structure['low_price']:,.0f})",
        f"Consensus:   {structure['consensus_label']}",
    ]
    return lines


def format_timestamp():
    """Return current timestamp string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M")
