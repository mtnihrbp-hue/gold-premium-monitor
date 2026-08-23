"""C.14C Regime Analysis — performance segmentation by market regime.

Diagnostic only. No regime-based prediction override.
"""

from typing import Dict, List, Any
from collections import defaultdict


def analyze_regime_performance(
    records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Segment forecast performance by regime.

    Args:
        records: list of dicts with keys:
            - regime: str
            - forecast: str or None
            - actual: str
            - confidence: float or None
            - correct: bool

    Returns:
        dict mapping regime -> performance metrics.
        Regimes with < 3 samples report INSUFFICIENT_DATA.
    """
    regimes = defaultdict(list)
    for r in records:
        reg = r.get("regime") or "UNKNOWN"
        regimes[reg].append(r)

    result = {}
    for reg, recs in sorted(regimes.items()):
        n = len(recs)
        if n < 3:
            result[reg] = {
                "status": "INSUFFICIENT_DATA",
                "sample_count": n,
            }
            continue

        correct = sum(1 for r in recs if r.get("correct", False))
        accuracy = correct / n if n > 0 else 0.0

        confidences = [
            r["confidence"] for r in recs
            if r.get("confidence") is not None
        ]
        avg_conf = sum(confidences) / len(confidences) if confidences else None

        # Calibration: average confidence vs accuracy
        calibration_gap = (
            round(avg_conf - accuracy, 4)
            if avg_conf is not None else None
        )

        result[reg] = {
            "status": "OK",
            "sample_count": n,
            "correct": correct,
            "accuracy": round(accuracy, 4),
            "average_confidence": round(avg_conf, 4) if avg_conf is not None else None,
            "calibration_gap": calibration_gap,
        }

    return result
