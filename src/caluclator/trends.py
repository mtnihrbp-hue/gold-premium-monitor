"""Trend analysis for premium history.

Computes directional trends and moving averages from state history.
"""


def _extract_premiums(history, days):
    """Extract last N premium values from history."""
    if not history or len(history) < 2:
        return []
    return [h["premium"] for h in history[-days:]]


def get_recent_trend(history):
    """Return recent premium trend (last 3 samples).

    Returns:
        (diff, arrow) where diff is last - first premium,
        arrow is one of ↑, ↓, →.
    """
    premiums = _extract_premiums(history, 3)
    if len(premiums) < 3:
        return None, "→"

    diff = premiums[-1] - premiums[0]

    if diff > 0.5:
        return diff, "↑"
    elif diff < -0.5:
        return diff, "↓"
    else:
        return diff, "→"


# Backward compatibility alias
get_3day_trend = get_recent_trend


def get_7day_ma(history):
    """Return 7-day moving average of premium.

    Returns float or None if fewer than 7 data points.
    """
    premiums = _extract_premiums(history, 7)
    if len(premiums) < 7:
        return None
    return sum(premiums) / len(premiums)


def get_trend_summary(history):
    """Build a trends dict for use by alert modules.

    Returns:
        {
            "arrow": "↑" | "↓" | "→",
            "arrow_diff": float | None,
            "ma7": float | None,
            "history_length": int,
        }
    """
    diff, arrow = get_recent_trend(history)
    ma7 = get_7day_ma(history)

    return {
        "arrow": arrow,
        "arrow_diff": diff,
        "ma7": ma7,
        "history_length": len(history),
    }
