"""C.14C Intelligence Layer — main downstream entry point.

Answers:
1. What did we predict?
2. Why did we predict it?
3. What happened?
4. Why were we wrong?
5. Under what conditions are we reliable?
"""

from typing import Dict, Any, Optional, List
from datetime import datetime

from .error_classifier import classify_error
from .regime_analysis import analyze_regime_performance
from .reliability_analysis import analyze_feature_reliability


def analyze_forecast_outcome(
    forecast: Optional[str],
    actual: Optional[str],
    confidence: Optional[float] = None,
    probabilities: Optional[Dict[str, float]] = None,
    regime: Optional[str] = None,
    features: Optional[Dict[str, Any]] = None,
    feature_quality: Optional[str] = None,
    other_horizons: Optional[Dict[int, str]] = None,
    snapshot_id: Optional[int] = None,
    timestamp: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Analyze a single forecast-outcome pair.

    Pure diagnostic. No state modification.
    """
    error_type = classify_error(
        forecast=forecast,
        actual=actual,
        confidence=confidence,
        probabilities=probabilities,
        regime=regime,
        feature_quality=feature_quality,
        other_horizons=other_horizons,
    )

    return {
        "snapshot_id": snapshot_id,
        "timestamp": timestamp.isoformat() if timestamp else None,
        "forecast": forecast,
        "actual": actual,
        "correct": forecast == actual if forecast and actual else None,
        "error_type": error_type,
        "regime": regime,
        "confidence": confidence,
    }


def analyze_historical_batch(
    records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Analyze a batch of forecast-outcome records.

    Args:
        records: list of dicts from analyze_forecast_outcome or equivalent.

    Returns:
        aggregated diagnostics: accuracy, errors, regime breakdown, feature reliability.
    """
    # Regime analysis
    regime_perf = analyze_regime_performance(records)

    # Feature reliability (only for records that carry features)
    feature_records = [
        {
            "features": r.get("features", {}),
            "correct": r.get("correct", False),
            "regime": r.get("regime", "UNKNOWN"),
        }
        for r in records
        if "features" in r
    ]
    feature_reliability = analyze_feature_reliability(feature_records)

    # Overall stats
    total = len(records)
    correct = sum(1 for r in records if r.get("correct", False))
    errors = [r for r in records if r.get("error_type") is not None]

    error_breakdown = {}
    for e in errors:
        et = e["error_type"]
        error_breakdown[et] = error_breakdown.get(et, 0) + 1

    return {
        "total_evaluated": total,
        "correct_count": correct,
        "accuracy": round(correct / total, 4) if total > 0 else 0.0,
        "error_breakdown": error_breakdown,
        "regime_performance": regime_perf,
        "feature_reliability": feature_reliability,
    }
