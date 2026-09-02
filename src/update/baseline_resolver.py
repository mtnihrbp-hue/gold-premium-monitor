"""RUN/DAY/7D baseline resolver for UPDATE v1.

Retrieval and lightweight classification only. UPDATE does not execute the
Analyze pipeline. DAY currently means the first canonical market snapshot of
the current day; 7D is the arithmetic mean of canonical platform-average
snapshots in the trailing seven-day window. These baselines can later switch
to controlled Analyze-wing history without changing the UPDATE contract.

Threshold calibration status:
- Bubble movement: 0.05 percentage points, existing project convention.
- Price direction: 0.01% relative dead-band, placeholder.
- Price acceleration: 0.01% relative dead-band, placeholder.
- Price pace / Bubble pace: deliberately deferred until empirical history
  is sufficient.

No Neon schema changes are required.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from sqlalchemy import func

from database.connection import get_session
from database.models import MarketSnapshot, PlatformPrice

BUBBLE_MOVEMENT_DEADBAND_PP = 0.05
PRICE_DIRECTION_STABLE_THRESHOLD_PCT = 0.0001
ACCELERATION_STABLE_THRESHOLD_PCT = 0.0001
SEVEN_DAY_WINDOW = timedelta(days=7)
MIN_SEVEN_DAY_SNAPSHOTS = 3


@dataclass
class BaselineSnapshot:
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
    run: Optional[BaselineSnapshot]
    day: Optional[BaselineSnapshot]
    seven_day_platform_average: Optional[float]
    seven_day_snapshot_count: int
    rep_gold_acceleration: Optional[float]
    rep_gold_acceleration_label: str
    bubble_movement: str
    bubble_magnitude_change: Optional[float]
    price_direction: str
    price_direction_raw: Optional[float]
    bubble_movement_deadband: float
    acceleration_threshold: float
    day_source: str


def _get_latest_market_snapshot(session):
    return session.query(MarketSnapshot).order_by(MarketSnapshot.timestamp.desc()).first()


def _get_earliest_market_snapshot_today(session):
    today = datetime.now().date()
    return (
        session.query(MarketSnapshot)
        .filter(func.date(MarketSnapshot.timestamp) == today)
        .order_by(MarketSnapshot.timestamp.asc())
        .first()
    )


def _get_platform_prices(session, snapshot_id: Optional[int]) -> Dict[str, float]:
    if snapshot_id is None:
        return {}
    rows = session.query(PlatformPrice).filter(PlatformPrice.snapshot_id == snapshot_id).all()
    return {
        row.platform_name: float(row.price_irr)
        for row in rows
        if row.price_irr is not None
    }


def _build_baseline(session, snapshot) -> Optional[BaselineSnapshot]:
    if snapshot is None:
        return None
    platform_prices = _get_platform_prices(session, snapshot.id)
    platform_average = (
        sum(platform_prices.values()) / len(platform_prices)
        if platform_prices else None
    )
    return BaselineSnapshot(
        timestamp=snapshot.timestamp,
        xau_usd=float(snapshot.world_gold_usd) if snapshot.world_gold_usd is not None else None,
        usd_irr=float(snapshot.usd_irr) if snapshot.usd_irr is not None else None,
        fair_price=float(snapshot.fair_price) if snapshot.fair_price is not None else None,
        premium_percent=float(snapshot.premium_percent) if snapshot.premium_percent is not None else None,
        platform_prices=platform_prices,
        platform_average=platform_average,
        platform_count=len(platform_prices),
    )


def _classify_price_direction(current: Optional[float], baseline: Optional[float]) -> Tuple[str, Optional[float]]:
    if current is None or baseline is None or baseline == 0:
        return "N/A", None
    diff = current - baseline
    threshold = abs(baseline * PRICE_DIRECTION_STABLE_THRESHOLD_PCT)
    if abs(diff) < threshold:
        return "STABLE", diff
    return ("RISING", diff) if diff > 0 else ("FALLING", diff)


def _classify_bubble_movement(current: Optional[float], baseline: Optional[float]) -> Tuple[str, Optional[float]]:
    if current is None or baseline is None:
        return "N/A", None
    change = abs(current) - abs(baseline)
    if abs(change) < BUBBLE_MOVEMENT_DEADBAND_PP:
        return "STABLE", change
    return ("INCREASING", change) if change > 0 else ("DECREASING", change)


def _snapshot_platform_average(session, snapshot) -> Optional[float]:
    if snapshot is None:
        return None
    prices = _get_platform_prices(session, snapshot.id)
    return sum(prices.values()) / len(prices) if prices else None


def _compute_7d_platform_average(session, now: Optional[datetime] = None) -> Tuple[Optional[float], int]:
    """Return the trailing seven-day mean of canonical platform averages.

    The UPDATE wing is resolved before the current snapshot is persisted, so
    this intentionally uses historical MarketSnapshot records only. It is a
    time-window average, not a fixed-count average. A minimum history guard
    prevents a one- or two-observation "7D average" from looking authoritative.
    """
    if now is None:
        now = datetime.now()
    cutoff = now - SEVEN_DAY_WINDOW

    snapshots = (
        session.query(MarketSnapshot)
        .filter(MarketSnapshot.timestamp >= cutoff, MarketSnapshot.timestamp <= now)
        .order_by(MarketSnapshot.timestamp.asc())
        .all()
    )

    values = []
    for snapshot in snapshots:
        avg = _snapshot_platform_average(session, snapshot)
        if avg is not None:
            values.append(avg)

    if len(values) < MIN_SEVEN_DAY_SNAPSHOTS:
        return None, len(values)
    return sum(values) / len(values), len(values)


def _compute_rep_gold_acceleration(session) -> Tuple[Optional[float], str]:
    """Acceleration of the canonical local representative price.

    The representative price is the arithmetic platform average per canonical
    market snapshot. This deliberately avoids using the raw REP_IRAN_GOLD
    observation stream because that stream contains multiple platforms and,
    for Goldika, BUY/SELL observations; treating those as consecutive prices
    would manufacture false acceleration from source ordering or spread.
    """
    try:
        snapshots = (
            session.query(MarketSnapshot)
            .order_by(MarketSnapshot.timestamp.desc())
            .limit(20)
            .all()
        )
        values = []
        for snapshot in snapshots:
            avg = _snapshot_platform_average(session, snapshot)
            if avg is not None:
                values.append(avg)
            if len(values) >= 3:
                break

        if len(values) < 3:
            return None, "N/A"

        p0, p1, p2 = reversed(values)
        v1 = p1 - p0
        v2 = p2 - p1
        acceleration = v2 - v1
        threshold = abs(p2 * ACCELERATION_STABLE_THRESHOLD_PCT)
        if abs(acceleration) < threshold:
            return acceleration, "STABLE"
        return (acceleration, "ACCELERATING") if acceleration > 0 else (acceleration, "DECELERATING")
    except Exception as e:
        print(f"Baseline resolver: acceleration computation failed: {e}")
        return None, "N/A"


def _empty_baselines() -> UpdateBaselines:
    return UpdateBaselines(
        run=None, day=None,
        seven_day_platform_average=None,
        seven_day_snapshot_count=0,
        rep_gold_acceleration=None,
        rep_gold_acceleration_label="N/A", bubble_movement="N/A",
        bubble_magnitude_change=None, price_direction="N/A",
        price_direction_raw=None,
        bubble_movement_deadband=BUBBLE_MOVEMENT_DEADBAND_PP,
        acceleration_threshold=ACCELERATION_STABLE_THRESHOLD_PCT,
        day_source="market_snapshot",
    )


def resolve_update_baselines(
    current_platform_avg: Optional[float] = None,
    current_premium: Optional[float] = None,
) -> UpdateBaselines:
    """Resolve RUN/DAY/7D baselines before the current snapshot is persisted."""
    session = get_session()
    if session is None:
        return _empty_baselines()

    try:
        run = _build_baseline(session, _get_latest_market_snapshot(session))
        day = _build_baseline(session, _get_earliest_market_snapshot_today(session))
        seven_day_avg, seven_day_count = _compute_7d_platform_average(session)
        acceleration, acceleration_label = _compute_rep_gold_acceleration(session)
        price_direction, price_direction_raw = _classify_price_direction(
            current_platform_avg,
            run.platform_average if run else None,
        )
        bubble_movement, bubble_change = _classify_bubble_movement(
            current_premium,
            run.premium_percent if run else None,
        )
        return UpdateBaselines(
            run=run, day=day,
            seven_day_platform_average=seven_day_avg,
            seven_day_snapshot_count=seven_day_count,
            rep_gold_acceleration=acceleration,
            rep_gold_acceleration_label=acceleration_label,
            bubble_movement=bubble_movement,
            bubble_magnitude_change=bubble_change,
            price_direction=price_direction,
            price_direction_raw=price_direction_raw,
            bubble_movement_deadband=BUBBLE_MOVEMENT_DEADBAND_PP,
            acceleration_threshold=ACCELERATION_STABLE_THRESHOLD_PCT,
            day_source="market_snapshot",
        )
    except Exception as e:
        print(f"Baseline resolver failed: {e}")
        return _empty_baselines()
    finally:
        session.close()
