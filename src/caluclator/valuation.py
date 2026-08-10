"""Valuation engine — maps premium to categorical valuation state.

Deterministic, no ML, no scoring.
"""


def evaluate_valuation(premium: float, thresholds: dict) -> str:
    """Return valuation state based on premium and configured thresholds.

    Args:
        premium: current premium percentage
        thresholds: dict with 'buy_premium' and 'sell_premium' keys

    Returns:
        CHEAP | FAIR | EXPENSIVE | UNKNOWN
    """
    if premium is None:
        return "UNKNOWN"

    buy_threshold = thresholds.get("buy_premium", -1.5)
    sell_threshold = thresholds.get("sell_premium", 2.0)

    if premium <= buy_threshold:
        return "CHEAP"
    elif premium >= sell_threshold:
        return "EXPENSIVE"
    else:
        return "FAIR"
