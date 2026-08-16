"""Deterministic freshness utility for price observations.

PRE-SP-C.1: configurable freshness rules for time-series data.
"""

from datetime import datetime, timedelta
from typing import Optional


FRESHNESS_STATES = ["FRESH", "STALE", "UNKNOWN"]


def evaluate_freshness(
    observation_timestamp: Optional[datetime],
    reference_time: Optional[datetime] = None,
    stale_threshold_minutes: int = 15,
) -> str:
    """Evaluate freshness of an observation against a configurable threshold.

    Args:
        observation_timestamp: the timestamp of the observation
        reference_time: the time to compare against (default: now)
        stale_threshold_minutes: minutes after which observation is STALE

    Returns:
        FRESH, STALE, or UNKNOWN
    """
    if observation_timestamp is None:
        return "UNKNOWN"

    if reference_time is None:
        reference_time = datetime.now()

    # Ensure both are naive or both are aware
    if observation_timestamp.tzinfo is None and reference_time.tzinfo is not None:
        reference_time = reference_time.replace(tzinfo=None)
    elif observation_timestamp.tzinfo is not None and reference_time.tzinfo is None:
        observation_timestamp = observation_timestamp.replace(tzinfo=None)

    age = reference_time - observation_timestamp
    if age < timedelta(0):
        # Future timestamp — treat as UNKNOWN
        return "UNKNOWN"

    if age <= timedelta(minutes=stale_threshold_minutes):
        return "FRESH"

    return "STALE"
