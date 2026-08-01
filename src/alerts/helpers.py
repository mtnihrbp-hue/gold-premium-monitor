"""Shared notification formatting helpers.

Channel-agnostic text formatting used by both Email and Telegram.
"""

from datetime import datetime


def format_platform_bullets(markets):
    """Format valid platforms as bullet lines for plain-text / Telegram."""
    lines = []
    for name, info in markets.items():
        if info.get("status") == "OK":
            lines.append(f"• {name}: {info['price']:,.0f}")
    return lines


def format_platform_table_rows(markets):
    """Format valid platforms as HTML table rows for Email."""
    rows = ""
    for name, info in markets.items():
        if info.get("status") != "OK":
            continue
        rows += f"""
<tr>
<td style="padding:6px;border-bottom:1px solid #ddd;">
{name}
</td>
<td style="padding:6px;border-bottom:1px solid #ddd;text-align:right;">
{info["price"]:,.0f}
</td>
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
    ma7 = trends.get("ma7")

    if diff is not None:
        lines.append(f"Recent Trend: {arrow} ({diff:+.2f}%)")
    if ma7 is not None:
        lines.append(f"7-Day MA: {ma7:.2f}%")

    return lines


def format_timestamp():
    """Return current timestamp string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M")
