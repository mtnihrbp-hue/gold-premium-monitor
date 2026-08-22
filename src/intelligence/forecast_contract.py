"""Forecast Output Contract — PRE-SP-C.14B

Frozen canonical structure. All forecast producers must return this exact shape.
No post-hoc aliases. No weakening.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any

FORECAST_SCHEMA_VERSION = "1"
LABEL_SCHEMA_VERSION = "1"  # Maps to C.5/C.12 authoritative labels

VALID_STATUSES = {"OK", "INSUFFICIENT_DATA", "ABSTAIN"}
VALID_DIRECTIONS = {"UP", "NEUTRAL", "DOWN"}


@dataclass
class ForecastResult:
    status: str
    forecast: Optional[str]
    probabilities: Dict[str, float]
    confidence: Optional[float]
    horizon_hours: int
    model_version: str
    feature_schema_version: str
    label_schema_version: str
    regime_state: Optional[str]
    provenance: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {self.status}")
        if self.status == "OK":
            if self.forecast not in VALID_DIRECTIONS:
                raise ValueError(f"Invalid forecast direction: {self.forecast}")
            total = sum(self.probabilities.get(d, 0.0) for d in VALID_DIRECTIONS)
            if abs(total - 1.0) > 1e-6:
                raise ValueError(f"Probabilities sum to {total}, expected 1.0")
            for d in VALID_DIRECTIONS:
                p = self.probabilities.get(d, 0.0)
                if not (0.0 <= p <= 1.0):
                    raise ValueError(f"Probability {d}={p} out of range [0,1]")


def validate_forecast_result(result: dict) -> tuple:
    """Validate a forecast result dict matches the frozen contract.

    Returns:
        (is_valid: bool, errors: list of str)
    """
    errors = []
    status = result.get("status")
    if status not in VALID_STATUSES:
        errors.append(f"Invalid status: {status}")
        return False, errors

    probs = result.get("probabilities", {})
    for d in VALID_DIRECTIONS:
        p = probs.get(d)
        if p is None:
            errors.append(f"Missing probability for {d}")
        elif not (0.0 <= p <= 1.0):
            errors.append(f"Probability {d}={p} out of range [0,1]")

    if not errors:
        total = sum(probs.get(d, 0.0) for d in VALID_DIRECTIONS)
        if abs(total - 1.0) > 1e-6:
            errors.append(f"Probabilities sum to {total}, expected 1.0")

    required = [
        "status", "forecast", "probabilities", "confidence",
        "horizon_hours", "model_version", "feature_schema_version",
        "label_schema_version", "regime_state", "provenance",
    ]
    for key in required:
        if key not in result:
            errors.append(f"Missing required field: {key}")

    return len(errors) == 0, errors
