"""Market structure engine — analyzes platform price distribution.

Deterministic, no ML.
"""

from typing import Dict, Any


def evaluate_structure(markets: Dict[str, Any], fair_price: float) -> dict:
    """Evaluate market structure from platform prices.

    Args:
        markets: dict of {name: {price, status, ...}}
        fair_price: calculated fair price

    Returns:
        dict with state, platform_average, platform_high, platform_low,
        platform_spread, platforms_below_fair, platforms_above_fair
    """
    valid = [
        (name, info["price"])
        for name, info in markets.items()
        if info.get("status") == "OK" and info.get("price") is not None
    ]

    if len(valid) < 2:
        return {
            "state": "UNKNOWN",
            "platform_average": 0.0,
            "platform_high": 0.0,
            "platform_low": 0.0,
            "platform_spread": 0.0,
            "platforms_below_fair": 0,
            "platforms_above_fair": 0,
        }

    prices = [p for _, p in valid]
    below = sum(1 for _, p in valid if p < fair_price)
    above = sum(1 for _, p in valid if p >= fair_price)
    total = len(valid)

    # 60% threshold for dominant consensus
    if below / total >= 0.6:
        state = "DISCOUNT_DOMINANT"
    elif above / total >= 0.6:
        state = "PREMIUM_DOMINANT"
    else:
        state = "MIXED"

    return {
        "state": state,
        "platform_average": sum(prices) / len(prices),
        "platform_high": max(prices),
        "platform_low": min(prices),
        "platform_spread": max(prices) - min(prices),
        "platforms_below_fair": below,
        "platforms_above_fair": above,
    }
