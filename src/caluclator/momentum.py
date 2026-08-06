"""Premium momentum analysis using historical database data.

Replaces the noisy 'last N checks' approach with daily average comparisons
anchored to today and yesterday's full data.
"""

from datetime import datetime, timedelta


def build_momentum_context(current_premium: float, session) -> dict:
    """Build a momentum context dict for alerts.

    Returns:
        {
            "premium_vs_today": {
                "avg": float,
                "diff": float,
                "min": float,
                "max": float,
                "count": int,
                "label": str,
                "emoji": str,
            } or None,
            "premium_vs_yesterday": {
                "avg": float,
                "diff": float,
                "date": str,
                "label": str,
            } or None,
            "candlestick": {
                "open": float,
                "high": float,
                "low": float,
                "close": float,
                "avg": float,
            } or None,
            "verbal_direction": str,
        }
    """
    from database.repository import get_premium_momentum_context as _db_context

    try:
        return _db_context(current_premium, session)
    except Exception as e:
        print(f"Momentum DB query failed: {e}")
        return _fallback_momentum(current_premium)


def _fallback_momentum(current_premium: float) -> dict:
    """Return minimal momentum when DB is unavailable."""
    return {
        "premium_vs_today": None,
        "premium_vs_yesterday": None,
        "candlestick": None,
        "verbal_direction": "Neutral (no history)",
    }
