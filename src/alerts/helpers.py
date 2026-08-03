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
    """Format valid platforms as a sorted table with price change.

    Args:
        markets: current markets dict {name: {price, status}}
        previous_markets: flat dict {name: price} from previous run

    Returns:
        List of formatted strings, alphabetically sorted.
    """
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
        lines.append(f"{name:<12} {price:>15,.0f}   {change:>12}")
    return lines


def format_platform_table_rows(markets, previous_markets=None):
    """Format valid platforms as HTML table rows for Email.

    Includes a Change column compared to previous run.
    """
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
                change_html = "<span>—</span>"
            elif diff > 0:
                change_html = f"<span style=\"color:green;\">+{diff:,.0f}</span>"
            else:
                change_html = f"<span style=\"color:red;\">{diff:,.0f}</span>"
        else:
            change_html = "<span>—</span>"

        rows += f"""
<tr>
<td style="padding:6px;border-bottom:1px solid #ddd;">{name}</td>
<td style="padding:6px;border-bottom:1px solid #ddd;text-align:right;">{price:,.0f}</td>
<td style="padding:6px;border-bottom:1px solid #ddd;text-align:right;">{change_html}</td>
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
        lines.append(f"Fair Price Trend: {arrow} ({pct:+.2f}%)")
    if vs_diff is not None and vs_pct is not None:
        lines.append(f"vs Yesterday: {vs_pct:+.2f}%")
    if ma7 is not None:
        lines.append(f"7-Day Avg Fair: {ma7:,.0f}")

    return lines


def format_timestamp():
    """Return current timestamp string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M")
