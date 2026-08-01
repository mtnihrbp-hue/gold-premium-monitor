"""ASCII sparkline generator for inline charts in notifications.

Uses Unicode block characters for maximum compatibility in
Telegram HTML and plain-text email.
"""

BLOCKS = "▁▂▃▄▅▆▇█"


def sparkline(values, width=20):
    """Generate an ASCII sparkline from a list of numeric values.

    Args:
        values: List of numbers (e.g. premium percentages).
        width: Maximum number of characters in the sparkline.

    Returns:
        A string of block characters, or empty string if insufficient data.
    """
    if not values or len(values) < 2:
        return ""

    # Take the most recent `width` points
    recent = values[-width:]

    min_val = min(recent)
    max_val = max(recent)

    if max_val == min_val:
        return "─" * len(recent)

    result = []
    for v in recent:
        idx = int((v - min_val) / (max_val - min_val) * (len(BLOCKS) - 1))
        result.append(BLOCKS[idx])

    return "".join(result)


def premium_sparkline(history, width=20):
    """Convenience: sparkline from history entries."""
    if not history:
        return ""
    premiums = [h["premium"] for h in history]
    return sparkline(premiums, width=width)
