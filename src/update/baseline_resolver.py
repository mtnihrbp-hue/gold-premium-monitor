"""Baseline resolver for UPDATE v1.

Retrieval-only module. Resolves RUN and DAY baselines from existing schema.
Does NOT format. Does NOT calculate market values owned by other modules.

RUN  = latest canonical market collection run (market_snapshots)
DAY  = first canonical market collection of current day (market_snapshots)
       Transitional: will become first analysis snapshot when Analyze is live.

Calibration status for thresholds:
- Bubble movement dead-band: 0.05 pp — EXISTING PROJECT CONVENTION
  (inherited from get_premium_direction). NOT EMPIRICALLY CALIBRATED.
- Price acceleration stable threshold: 0.01% of current price — PLACEHOLDER
  pending empirical calibration.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Tuple

from sqlalchemy import func

from database.connection import get_session
from database.models import MarketSnapshot, PlatformPrice
from database.repository import get_price_observations_by_instrument

# ---------------------------------------------------------------------------
# Thresholds — documented as convention-based / placeholder
# ---------------------------------------------------------------------------

BUBBLE_MOVEMENT_DEADBAND_PP = 0.05
"""Dead-band for bubble magnitude stability (percentage points).

Source: existing project convention in get_premium_direction().
Status: CONVENTION-BASED / NOT EMPIRICALLY CALIBRATED.
"""

ACCELERATION_STABLE_THRESHOLD_PCT = 0.0001
"""Relative threshold for price acceleration stability.

0.01% of current price. Placeholder pending empirical calibration.
Status: PLACEHOLDER / NOT EMPIRICALLY CALIBRATED.
"""

PRICE_DIRECTION_STABLE_THRESHOLD_PCT = 0.0001
"""Relative threshold for price direction stability.

0.01% of baseline price. Placeholder pending empirical calibration.
Status: PLACEHOLDER / NOT EMPIRICALLY CALIBRATED.
"""


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class BaselineSnapshot:
    """Canonical baseline snapshot for UPDATE comparison."""
    timestamp: Optional[datetime]
    xau_usd: Optional[float]
    usd_irr: Optional[float]
    fair_price: Optional[float]
    premium_percent: Optional[float]
    platform_prices: Dict[str, float]
    platform_average: Optional[float]
    platform_count: int


@dataclass
class UpdateBaselines:
    """Complete baseline resolution result for UPDATE v1."""
    run: Optional[BaselineSnapshot]
    day: Optional[BaselineSnapshot]
    rep_gold_acceleration: Optional[float]
    rep_gold_acceleration_label: str
    bubble_movement: str
    bubble_magnitude_change: Optional[float]
    price_direction: str
    price_direction_raw: Optional[float]
    bubble_movement_deadband: float
    acceleration_threshold: float
    day_source: str


# ---------------------------------------------------------------------------
# Internal retrieval helpers
# ---------------------------------------------------------------------------

def _get_latest_market_snapshot(session) -> Optional[MarketSnapshot]:
    """Retrieve the most recent market snapshot."""
    try:
        return (
            session.query(MarketSnapshot)
            .order_by(MarketSnapshot.timestamp.desc())
            .first()
        )
    except Exception as e:
        print(f"Baseline resolver: latest snapshot query failed: {e}")
        return None


def _get_earliest_market_snapshot_today(session) -> Optional[MarketSnapshot]:
    """Retrieve the earliest market snapshot of the current day."""
    try:
        today = datetime.now().date()
        return (
            session.query(MarketSnapshot)
            .filter(func.date(MarketSnapshot.timestamp) == today)
            .order_by(MarketSnapshot.timestamp.asc())
            .first()
        )
    except Exception as e:
        print(f"Baseline resolver: earliest today snapshot query failed: {e}")
        return None


def _get_platform_prices_for_snapshot(
    session, snapshot_id: Optional[int]
) -> Dict[str, float]:
    """Retrieve platform prices for a given snapshot."""
    if snapshot_id is None:
        return {}
    try:
        rows = (
            session.query(PlatformPrice)
            .filter(PlatformPrice.snapshot_id == snapshot_id)
            .all()
        )
        return {
            r.platform_name: float(r.price_irr)
            for r in rows
            if r.price_irr is not None
        }
    except Exception as e:
        print(f"Baseline resolver: platform prices query failed: {e}")
        return {}


def _build_baseline_snapshot(
    session, snapshot: Optional[MarketSnapshot]
) -> Optional[BaselineSnapshot]:
    """Build a BaselineSnapshot from a MarketSnapshot."""
    if snapshot is None:
        return None

    platform_prices = _get_platform_prices_for_snapshot(session, snapshot.id)

    platform_avg = None
    if platform_prices:
        platform_avg = sum(platform_prices.values()) / len(platform_prices)

    return BaselineSnapshot(
        timestamp=snapshot.timestamp,
        xau_usd=float(snapshot.world_gold_usd) if snapshot.world_gold_usd else None,
        usd_irr=float(snapshot.usd_irr) if snapshot.usd_irr else None,
        fair_price=float(snapshot.fair_price) if snapshot.fair_price else None,
        premium_percent=float(snapshot.premium_percent)
        if snapshot.premium_percent is not None
        else None,
        platform_prices=platform_prices,
        platform_average=platform_avg,
        platform_count=len(platform_prices),
    )


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

def _compute_rep_gold_acceleration() -> Tuple[Optional[float], str]:
    """Compute REP_IRAN_GOLD price acceleration from canonical observations.

    Uses the 3 most recent valid REP_IRAN_GOLD observations.
    Classification uses ACCELERATION_STABLE_THRESHOLD_PCT (placeholder).

    Returns:
        (raw_acceleration_value, classification_label)
        Label: ACCELERATING | DECELERATING | STABLE | N/A
    """
    try:
        obs = get_price_observations_by_instrument("REP_IRAN_GOLD", limit=20)
        if not obs:
            return None, "N/A"

        prices = []
        for o in obs:
            if o.price is not None:
                try:
                    prices.append(float(o.price))
                except (TypeError, ValueError):
                    continue
            if len(prices) >= 3:
                break

        if len(prices) < 3:
            return None, "N/A"

        # obs are newest-first; reverse for chronological order
        p = list(reversed(prices))

        v1 = p[1] - p[0]   # velocity t-2 → t-1
        v2 = p[2] - p[1]   # velocity t-1 → t
        acceleration = v2 - v1

        if p[2] == 0:
            return acceleration, "N/A"

        threshold = abs(p[2] * ACCELERATION_STABLE_THRESHOLD_PCT)

        if abs(acceleration) < threshold:
            return acceleration, "STABLE"
        return (acceleration, "ACCELERATING") if acceleration > 0 else (acceleration, "DECELERATING")

    except Exception as e:
        print(f"Baseline resolver: acceleration computation failed: {e}")
        return None, "N/A"


def _classify_bubble_movement(
    current_bubble: Optional[float], baseline_bubble: Optional[float]
) -> Tuple[str, Optional[float]]:
    """Classify bubble movement based on magnitude change.

    Uses BUBBLE_MOVEMENT_DEADBAND_PP (existing convention).

    Returns:
        (movement_label, magnitude_change_pp)
        Label: INCREASING | DECREASING | STABLE | N/A
    """
    if current_bubble is None or baseline_bubble is None:
        return "N/A", None

    current_magnitude = abs(current_bubble)
    baseline_magnitude = abs(baseline_bubble)
    change = current_magnitude - baseline_magnitude

    if abs(change) < BUBBLE_MOVEMENT_DEADBAND_PP:
        return "STABLE", change
    return ("INCREASING", change) if change > 0 else ("DECREASING", change)


def _classify_price_direction(
    current_price: Optional[float], baseline_price: Optional[float]
) -> Tuple[str, Optional[float]]:
    """Classify local price direction from current vs baseline.

    Uses PRICE_DIRECTION_STABLE_THRESHOLD_PCT (placeholder).

    Returns:
        (direction_label, raw_diff)
        Label: RISING | FALLING | STABLE | N/A
    """
    if current_price is None or baseline_price is None:
        return "N/A", None

    diff = current_price - baseline_price
    if baseline_price == 0:
        return "N/A", diff

    threshold = abs(baseline_price * PRICE_DIRECTION_STABLE_THRESHOLD_PCT)

    if abs(diff) < threshold:
        return "STABLE", diff
    return ("RISING", diff) if diff > 0 else ("FALLING", diff)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_update_baselines(
    current_platform_avg: Optional[float] = None,
    current_premium: Optional[float] = None,
) -> UpdateBaselines:
    """Resolve RUN and DAY baselines for UPDATE v1.

    RUN = latest canonical market snapshot (before current run).
    DAY = earliest market snapshot of current day.

    Args:
        current_platform_avg: current arithmetic mean of valid platforms.
        current_premium: current signed premium percentage.

    Returns:
        UpdateBaselines with all resolved values and computed classifications.
    """
    session = get_session()
    if session is None:
        return UpdateBaselines(
            run=None,
            day=None,
            rep_gold_acceleration=None,
            rep_gold_acceleration_label="N/A",
            bubble_movement="N/A",
            bubble_magnitude_change=None,
            price_direction="N/A",
            price_direction_raw=None,
            bubble_movement_deadband=BUBBLE_MOVEMENT_DEADBAND_PP,
            acceleration_threshold=ACCELERATION_STABLE_THRESHOLD_PCT,
            day_source="market_snapshot",
        )

    try:
        # RUN baseline (latest snapshot BEFORE current)
        run_snapshot = _get_latest_market_snapshot(session)
        run = _build_baseline_snapshot(session, run_snapshot)

        # DAY baseline (earliest today)
        day_snapshot = _get_earliest_market_snapshot_today(session)
        day = _build_baseline_snapshot(session, day_snapshot)

        # Local price acceleration (from canonical observations)
        rep_gold_acceleration, rep_gold_acceleration_label = _compute_rep_gold_acceleration()

        # Price direction (current vs RUN baseline)
        price_direction, price_direction_raw = _classify_price_direction(
            current_platform_avg, run.platform_average if run else None
        )

        # Bubble movement (current vs RUN baseline)
        bubble_movement, bubble_magnitude_change = _classify_bubble_movement(
            current_premium, run.premium_percent if run else None
        )

        return UpdateBaselines(
            run=run,
            day=day,
            rep_gold_acceleration=rep_gold_acceleration,
            rep_gold_acceleration_label=rep_gold_acceleration_label,
            bubble_movement=bubble_movement,
            bubble_magnitude_change=bubble_magnitude_change,
            price_direction=price_direction,
            price_direction_raw=price_direction_raw,
            bubble_movement_deadband=BUBBLE_MOVEMENT_DEADBAND_PP,
            acceleration_threshold=ACCELERATION_STABLE_THRESHOLD_PCT,
            day_source="market_snapshot",
        )
    except Exception as e:
        print(f"Baseline resolver failed: {e}")
        return UpdateBaselines(
            run=None,
            day=None,
            rep_gold_acceleration=None,
            rep_gold_acceleration_label="N/A",
            bubble_movement="N/A",
            bubble_magnitude_change=None,
            price_direction="N/A",
            price_direction_raw=None,
            bubble_movement_deadband=BUBBLE_MOVEMENT_DEADBAND_PP,
            acceleration_threshold=ACCELERATION_STABLE_THRESHOLD_PCT,
            day_source="market_snapshot",
        )
    finally:
        if session:
            session.close()
