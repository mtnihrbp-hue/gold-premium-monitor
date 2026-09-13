"""Where the current bubble sits inside its own recent distribution.

The project's fixed valuation thresholds carry no information: across 278 recorded
observations the bubble never once crossed buy_premium_percent, so valuation_state
read CHEAP on every state ever stored. A market that sits permanently outside a
fixed line needs a reference that moves with it.

This module measures the bubble against its own recent history instead. The method
is the standard one for a security trading at a persistent discount to fair value:
express the current reading as a z-score against a rolling mean and standard
deviation, so the reference recalculates itself as the market changes rather than
being pinned to a constant.

Two deliberate limits:

- Nothing here decides. It reports position and observed history. BUY/WAIT/SELL
  authority stays with the deterministic decision engine.
- Confidence is reported from the amount of history actually available. Published
  work on this signal class uses 120 to 180 days; below that the output is marked
  LOW and is not to be presented as reliable.

Known limitation: market_snapshots does not record whether a row came from a
scheduled run or a user-triggered update, so the distribution is drawn from a mixed
sample. Sampling driven by user curiosity will bias it. This resolves when the
collection_mode migration lands.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean, pstdev
from typing import List, Optional

from database.models import MarketSnapshot

DEFAULT_WINDOW_DAYS = 30

# Minimum readings before any position is reported at all.
MIN_OBSERVATIONS = 30

# Calendar coverage thresholds for confidence. The literature for this signal class
# uses 120 to 180 days, so anything below that is explicitly LOW.
LOW_CONFIDENCE_DAYS = 60
MEDIUM_CONFIDENCE_DAYS = 120

# Standard deviations. These are the conventional levels for discount z-scores and
# are not tuned to this project's data, which would be overfitting on 41 days.
UNUSUAL_Z = 2.0
NOTABLE_Z = 1.0

# A drift in the window mean larger than this fraction of the window's own spread
# means the reference itself is moving, not just the current reading.
DRIFT_FRACTION_OF_STD = 0.5


@dataclass
class BubblePosition:
    bubble: Optional[float]
    window_days: int
    sample_size: int
    coverage_days: int
    average: Optional[float]
    spread: Optional[float]
    normal_low: Optional[float]
    normal_high: Optional[float]
    z_score: Optional[float]
    zone: str
    confidence: str
    drift: str


def _empty(window_days: int) -> BubblePosition:
    return BubblePosition(
        bubble=None,
        window_days=window_days,
        sample_size=0,
        coverage_days=0,
        average=None,
        spread=None,
        normal_low=None,
        normal_high=None,
        z_score=None,
        zone="INSUFFICIENT_DATA",
        confidence="INSUFFICIENT_DATA",
        drift="UNKNOWN",
    )


def _classify_zone(z_score: Optional[float]) -> str:
    """A more negative bubble is a deeper discount, so negative z is the cheap side."""
    if z_score is None:
        return "INSUFFICIENT_DATA"
    if z_score <= -UNUSUAL_Z:
        return "VERY_CHEAP"
    if z_score <= -NOTABLE_Z:
        return "CHEAP"
    if z_score >= UNUSUAL_Z:
        return "VERY_EXPENSIVE"
    if z_score >= NOTABLE_Z:
        return "EXPENSIVE"
    return "NORMAL"


def _classify_confidence(coverage_days: int, sample_size: int) -> str:
    if sample_size < MIN_OBSERVATIONS:
        return "INSUFFICIENT_DATA"
    if coverage_days < LOW_CONFIDENCE_DAYS:
        return "LOW"
    if coverage_days < MEDIUM_CONFIDENCE_DAYS:
        return "MEDIUM"
    return "HIGH"


def _classify_drift(values: List[float], spread: Optional[float]) -> str:
    """Report whether the reference itself is moving.

    A purely relative measure cannot tell a cheap reading from a market that has
    re-rated, so the window mean is compared against its own two halves.
    """
    if spread is None or spread == 0 or len(values) < MIN_OBSERVATIONS:
        return "UNKNOWN"
    midpoint = len(values) // 2
    first_half = values[:midpoint]
    second_half = values[midpoint:]
    if not first_half or not second_half:
        return "UNKNOWN"
    shift = mean(second_half) - mean(first_half)
    if abs(shift) < spread * DRIFT_FRACTION_OF_STD:
        return "STABLE"
    return "TOWARD_LESS_DISCOUNT" if shift > 0 else "TOWARD_MORE_DISCOUNT"


def resolve_bubble_position(
    session,
    current_bubble: Optional[float] = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    now: Optional[datetime] = None,
) -> BubblePosition:
    """Locate the current bubble within its own recent distribution.

    `current_bubble` lets a caller position a reading that is not yet persisted.
    When omitted the most recent stored reading is used.
    """
    if session is None:
        return _empty(window_days)

    if now is None:
        now = datetime.now()
    window_start = now - timedelta(days=window_days)

    try:
        rows = (
            session.query(MarketSnapshot.timestamp, MarketSnapshot.premium_percent)
            .filter(
                MarketSnapshot.premium_percent.isnot(None),
                MarketSnapshot.timestamp >= window_start,
                MarketSnapshot.timestamp <= now,
            )
            .order_by(MarketSnapshot.timestamp.asc())
            .all()
        )
    except Exception as e:
        print(f"Bubble position query failed: {e}")
        return _empty(window_days)

    values = [float(premium) for _, premium in rows if premium is not None]
    if not values:
        return _empty(window_days)

    timestamps = [ts for ts, _ in rows]
    coverage_days = len({ts.date() for ts in timestamps})

    bubble = current_bubble if current_bubble is not None else values[-1]

    if len(values) < MIN_OBSERVATIONS:
        position = _empty(window_days)
        position.bubble = bubble
        position.sample_size = len(values)
        position.coverage_days = coverage_days
        return position

    average = mean(values)
    spread = pstdev(values)

    z_score = None if spread == 0 else (bubble - average) / spread

    return BubblePosition(
        bubble=bubble,
        window_days=window_days,
        sample_size=len(values),
        coverage_days=coverage_days,
        average=round(average, 4),
        spread=round(spread, 4),
        normal_low=round(average - spread, 4),
        normal_high=round(average + spread, 4),
        z_score=None if z_score is None else round(z_score, 3),
        zone=_classify_zone(z_score),
        confidence=_classify_confidence(coverage_days, len(values)),
        drift=_classify_drift(values, spread),
    )


# ---------------------------------------------------------------------------
# What happened after comparable readings
# ---------------------------------------------------------------------------

# A move smaller than this is treated as no change, matching the existing bubble
# movement dead-band convention used elsewhere in the project.
UNCHANGED_DEADBAND_PP = 0.05

# How far a reading may sit from the target horizon and still count. This is looser
# than the 15-minute tolerance outcome_evaluations uses, because that strictness is
# for the authoritative outcome record while this is descriptive history.
DEFAULT_TOLERANCE_HOURS = 2.0

# How close a past reading must be to the current one to count as comparable,
# expressed as a fraction of the window's spread so it adapts to volatility.
COMPARABLE_BAND_FRACTION = 0.5


@dataclass
class SimilarOutcomes:
    horizon_hours: int
    cases: int
    became_cheaper: int
    became_pricier: int
    unchanged: int
    average_move_pp: Optional[float]
    band_low: Optional[float]
    band_high: Optional[float]
    status: str


def _empty_outcomes(horizon_hours: int) -> SimilarOutcomes:
    return SimilarOutcomes(
        horizon_hours=horizon_hours,
        cases=0,
        became_cheaper=0,
        became_pricier=0,
        unchanged=0,
        average_move_pp=None,
        band_low=None,
        band_high=None,
        status="INSUFFICIENT_DATA",
    )


def resolve_similar_outcomes(
    session,
    current_bubble: float,
    spread: Optional[float],
    horizon_hours: int = 24,
    tolerance_hours: float = DEFAULT_TOLERANCE_HOURS,
    now: Optional[datetime] = None,
) -> SimilarOutcomes:
    """What the bubble did after past readings comparable to the current one.

    A positive move means the discount shrank, so gold became more expensive and
    buying at that moment was the better choice. A negative move means the discount
    grew and waiting was better. The caller is expected to present it in those terms
    rather than as a signed number.
    """
    if session is None or current_bubble is None or not spread:
        return _empty_outcomes(horizon_hours)

    if now is None:
        now = datetime.now()

    try:
        rows = (
            session.query(MarketSnapshot.timestamp, MarketSnapshot.premium_percent)
            .filter(MarketSnapshot.premium_percent.isnot(None))
            .order_by(MarketSnapshot.timestamp.asc())
            .all()
        )
    except Exception as e:
        print(f"Similar outcomes query failed: {e}")
        return _empty_outcomes(horizon_hours)

    series = [(ts, float(premium)) for ts, premium in rows if premium is not None]
    if len(series) < MIN_OBSERVATIONS:
        return _empty_outcomes(horizon_hours)

    band = abs(spread) * COMPARABLE_BAND_FRACTION
    band_low = current_bubble - band
    band_high = current_bubble + band
    horizon = timedelta(hours=horizon_hours)
    tolerance = timedelta(hours=tolerance_hours)

    moves = []
    for index, (timestamp, premium) in enumerate(series):
        if not (band_low <= premium <= band_high):
            continue
        target = timestamp + horizon
        best = None
        best_gap = None
        # Only later readings qualify, so there is no look-ahead into the past.
        for later_timestamp, later_premium in series[index + 1:]:
            gap = abs(later_timestamp - target)
            if later_timestamp > target + tolerance:
                break
            if gap <= tolerance and (best_gap is None or gap < best_gap):
                best = later_premium
                best_gap = gap
        if best is not None:
            moves.append(best - premium)

    if not moves:
        return SimilarOutcomes(
            horizon_hours=horizon_hours,
            cases=0,
            became_cheaper=0,
            became_pricier=0,
            unchanged=0,
            average_move_pp=None,
            band_low=round(band_low, 4),
            band_high=round(band_high, 4),
            status="INSUFFICIENT_DATA",
        )

    became_pricier = sum(1 for m in moves if m > UNCHANGED_DEADBAND_PP)
    became_cheaper = sum(1 for m in moves if m < -UNCHANGED_DEADBAND_PP)
    unchanged = len(moves) - became_pricier - became_cheaper

    return SimilarOutcomes(
        horizon_hours=horizon_hours,
        cases=len(moves),
        became_cheaper=became_cheaper,
        became_pricier=became_pricier,
        unchanged=unchanged,
        average_move_pp=round(mean(moves), 3),
        band_low=round(band_low, 4),
        band_high=round(band_high, 4),
        status="OK",
    )
