"""C.14C Error Classification — deterministic diagnostic only.

Classifies why a forecast was wrong. No state modification.
"""

from typing import Optional, Dict, Any

ERROR_CATEGORIES = {
    "DIRECTION_ERROR",
    "CONFIDENCE_ERROR",
    "TIMING_ERROR",
    "REGIME_ERROR",
    "DATA_QUALITY_ERROR",
}


def classify_error(
    forecast: Optional[str],
    actual: Optional[str],
    confidence: Optional[float] = None,
    probabilities: Optional[Dict[str, float]] = None,
    regime: Optional[str] = None,
    feature_quality: Optional[str] = None,
    other_horizons: Optional[Dict[int, str]] = None,
) -> Optional[str]:
    """Classify the nature of a forecast error.

    Args:
        forecast: predicted direction (UP/NEUTRAL/DOWN) or None
        actual: realized direction (UP/NEUTRAL/DOWN) or None
        confidence: model confidence at prediction time
        probabilities: full probability distribution
        regime: market regime at prediction time
        feature_quality: data quality flag (DEGRADED/INSUFFICIENT_DATA/INVALID)
        other_horizons: dict of horizon_hours -> direction for timing checks

    Returns:
        Error category string, or None if forecast was correct or absent.
    """
    # No forecast was issued
    if forecast is None or actual is None:
        return "DATA_QUALITY_ERROR"

    # Correct prediction — no error
    if forecast == actual:
        return None

    # Data quality issues take precedence
    if feature_quality in ("DEGRADED", "INSUFFICIENT_DATA", "INVALID"):
        return "DATA_QUALITY_ERROR"

    # Timing error: direction eventually correct at longer horizon?
    if other_horizons:
        for horizon, direction in other_horizons.items():
            if direction == forecast:
                return "TIMING_ERROR"

    # Regime error: volatile/unusual regime
    if regime in ("PANIC", "FEAR", "RELIEF"):
        return "REGIME_ERROR"

    # Confidence error: high confidence but wrong
    if confidence is not None and confidence > 0.7:
        if probabilities:
            predicted_prob = probabilities.get(forecast, 0.0)
            if predicted_prob > 0.7:
                return "CONFIDENCE_ERROR"

    # Default: simple directional miss
    return "DIRECTION_ERROR"
