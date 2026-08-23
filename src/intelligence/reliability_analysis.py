"""C.14C Feature Reliability — measure historical feature usefulness.

Pure measurement. No model weight modification.
"""

from typing import Dict, List, Any
from collections import defaultdict
import math


def analyze_feature_reliability(
    records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Measure which features correlate with correct predictions.

    Args:
        records: list of dicts with keys:
            - features: dict of feature_name -> numeric value
            - correct: bool
            - regime: str (optional)

    Returns:
        dict mapping feature_name -> reliability metrics.
    """
    feature_stats = defaultdict(lambda: {"correct": [], "incorrect": []})

    for r in records:
        features = r.get("features", {})
        correct = r.get("correct", False)
        for name, value in features.items():
            try:
                v = float(value)
                if math.isnan(v):
                    continue
                if correct:
                    feature_stats[name]["correct"].append(v)
                else:
                    feature_stats[name]["incorrect"].append(v)
            except (TypeError, ValueError):
                continue

    result = {}
    for name, stats in feature_stats.items():
        c_vals = stats["correct"]
        i_vals = stats["incorrect"]

        c_mean = sum(c_vals) / len(c_vals) if c_vals else None
        i_mean = sum(i_vals) / len(i_vals) if i_vals else None

        separation = None
        if c_mean is not None and i_mean is not None:
            separation = c_mean - i_mean

        reliability_score = None
        total = len(c_vals) + len(i_vals)
        if total > 0:
            reliability_score = len(c_vals) / total

        result[name] = {
            "correct_count": len(c_vals),
            "incorrect_count": len(i_vals),
            "correct_mean": round(c_mean, 6) if c_mean is not None else None,
            "incorrect_mean": round(i_mean, 6) if i_mean is not None else None,
            "mean_separation": round(separation, 6) if separation is not None else None,
            "reliability_score": round(reliability_score, 4) if reliability_score is not None else None,
        }

    return result
