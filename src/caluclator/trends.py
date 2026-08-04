"""Trend analysis for premium and fair price history.

Computes directional trends and moving averages from state history.
"""

from datetime import datetime


def _extract_premiums(history, days):
    """Extract last N premium values from history."""
    if not history or len(history) < 2:
        return []
    return [h["premium"] for h in history[-days:] if h.get("premium") is not None]


def _get_daily_values(history, key):
    """Extract the last value per day for a given key.

    Returns a list of values sorted by date.
    """
    daily = {}
    for entry in history:
        ts_str = entry.get("timestamp")
        if not ts_str:
            continue
        try:
            ts = datetime.fromisoformat(ts_str)
        except ValueError:
            continue
        date_key = ts.strftime("%Y-%m-%d")
        value = entry.get(key)
        if value is not None:
            daily[date_key] = value
    return [v for k, v in sorted(daily.items())]


# ─── Premium trends (backward compat) ───

def get_3day_trend(history):
    """Return 3-sample premium trend (legacy alias)."""
    return get_recent_trend(history)


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


def get_7day_ma(history):
    """Return 7-sample moving average of premium."""
    premiums = _extract_premiums(history, 7)
    if len(premiums) < 7:
        return None
    return sum(premiums) / len(premiums)


# ─── Fair price trends (new) ───

def get_fair_price_trend(history):
    """Return fair price trend comparing the last two consecutive readings.

    Returns:
        (diff, pct, arrow) where diff is absolute change,
        pct is percentage change, arrow is ↑/↓/→.
    """
    values = [h["fair_price"] for h in history if h.get("fair_price") is not None]
    if len(values) < 2:
        return None, None, "→"

    diff = values[-1] - values[-2]
    pct = (diff / values[-2] * 100) if values[-2] else 0

    if abs(pct) < 0.1:
        return diff, pct, "→"
    elif pct > 0:
        return diff, pct, "↑"
    else:
        return diff, pct, "↓"


def get_fair_price_7day_ma(history):
    """Return 7-day moving average of fair price (absolute IRR).

    Returns float or None if fewer than 7 daily data points.
    """
    values = _get_daily_values(history, "fair_price")
    if len(values) < 7:
        return None
    return sum(values[-7:]) / len(values[-7:])


def get_fair_price_vs_yesterday(history):
    """Compare today's fair price vs yesterday's.

    Returns:
        (diff, pct) or (None, None) if insufficient data.
    """
    values = _get_daily_values(history, "fair_price")
    if len(values) < 2:
        return None, None
    today = values[-1]
    yesterday = values[-2]
    diff = today - yesterday
    pct = (diff / yesterday * 100) if yesterday else 0
    return diff, pct


# ─── Market spread (current run) ───

def get_market_spread(markets):
    """Return spread between highest and lowest valid platform prices.

    Returns (spread, highest_name, lowest_name) or (None, None, None).
    """
    valid = [(name, info["price"]) for name, info in markets.items()
             if info.get("status") == "OK" and info.get("price") is not None]
    if len(valid) < 2:
        return None, None, None

    highest = max(valid, key=lambda x: x[1])
    lowest = min(valid, key=lambda x: x[1])
    spread = highest[1] - lowest[1]
    return spread, highest[0], lowest[0]


# ─── Summary builder ───

def get_trend_summary(history):
    """Build a trends dict for use by alert modules.

    Returns:
        {
            "arrow": "↑" | "↓" | "→",
            "arrow_diff": float | None,
            "arrow_pct": float | None,
            "ma7": float | None,
            "vs_yesterday_diff": float | None,
            "vs_yesterday_pct": float | None,
            "history_length": int,
            "premium_direction": str,
        }
    """
    diff, pct, arrow = get_fair_price_trend(history)
    ma7 = get_fair_price_7day_ma(history)
    vs_diff, vs_pct = get_fair_price_vs_yesterday(history)

    # Premium direction sentence (replaces sparkline)
    premiums = [h["premium"] for h in history if h.get("premium") is not None]
    premium_direction = ""
    if len(premiums) >= 2:
        window = min(5, len(premiums))
        recent_premiums = premiums[-window:]
        p_diff = recent_premiums[-1] - recent_premiums[0]
        if abs(p_diff) >= 0.05:
            direction = "rising" if p_diff > 0 else "falling"
            premium_direction = (
                f"Premium {direction} by {abs(p_diff):.2f}% "
                f"over last {window} check{'s' if window > 1 else ''}"
            )
        else:
            premium_direction = "Premium stable"
    else:
        premium_direction = "Premium trend: insufficient data"

    return {
        "arrow": arrow,
        "arrow_diff": diff,
        "arrow_pct": pct,
        "ma7": ma7,
        "vs_yesterday_diff": vs_diff,
        "vs_yesterday_pct": vs_pct,
        "history_length": len(history),
        "premium_direction": premium_direction,
    }
