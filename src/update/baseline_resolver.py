"""RUN/DAY/7D baseline resolver for UPDATE v1.

Retrieval and lightweight classification only. UPDATE does not execute the
Analyze pipeline. DAY currently means the first canonical market snapshot of
the current day. 7D context is supplied by the reusable analysis trend
resolver using seven equally weighted completed calendar days.

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
from analysis.trend_resolver import SevenDayTrend, resolve_seven_day_trend
from timeutil import local_now, to_utc

# One definition, imported rather than restated -- see `tolerances.py`.
from tolerances import UNCHANGED_DEADBAND_PP as BUBBLE_MOVEMENT_DEADBAND_PP
PRICE_DIRECTION_STABLE_THRESHOLD_PCT = 0.0001
ACCELERATION_STABLE_THRESHOLD_PCT = 0.0001


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
    seven_day: SevenDayTrend
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
    """Latest scheduled reading, not simply the latest row.

    Without the filter this returned whatever snapshot was written last, which on the
    UPDATE path is the user's own previous request. RUN then measured the interval
    between two clicks rather than market movement, which is why it so often read
    +0.00%. PROJECT_MEMORY.md already required that accumulated user-triggered calls
    not serve as a baseline; the column needed to enforce it only arrived with the
    SP-C.1 migration.

    Falls back to any snapshot when no scheduled reading exists yet, so history
    predating the migration still resolves a baseline instead of none.
    """
    scheduled = (
        session.query(MarketSnapshot)
        .filter(MarketSnapshot.collection_mode == "scheduled")
        .order_by(MarketSnapshot.timestamp.desc())
        .first()
    )
    if scheduled is not None:
        return scheduled
    return session.query(MarketSnapshot).order_by(MarketSnapshot.timestamp.desc()).first()


def _get_earliest_market_snapshot_today(session, now=None):
    """First scheduled reading of today, with the same fallback.

    UPDATE_V1_IMPLEMENTATION.md anticipated this switch: DAY moves to the first
    controlled Analyze collection of the day once that wing runs on a real cadence.
    It now runs hourly, so the condition is met.

    `now` is injectable so the day boundary can be exercised without depending on
    the clock at the moment the tests happen to run.
    """
    # "Today" is the reader's calendar day, not the runner's. Stored timestamps are
    # UTC, so the boundary is local midnight expressed back in UTC. Comparing on the
    # stored date would place a reading taken at 01:00 local into yesterday, because
    # 01:00 local is 21:30 UTC of the previous day.
    today = local_now(now).date()
    day_start = to_utc(datetime.combine(today, datetime.min.time()))
    base = session.query(MarketSnapshot).filter(
        MarketSnapshot.timestamp >= day_start,
        MarketSnapshot.timestamp < day_start + timedelta(days=1),
    )
    scheduled = (
        base.filter(MarketSnapshot.collection_mode == "scheduled")
        .order_by(MarketSnapshot.timestamp.asc())
        .first()
    )
    if scheduled is not None:
        return scheduled
    return base.order_by(MarketSnapshot.timestamp.asc()).first()


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
        run=None,
        day=None,
        seven_day=SevenDayTrend(None, None, None, None, None, 0),
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
        seven_day = resolve_seven_day_trend(session)
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
            run=run,
            day=day,
            seven_day=seven_day,
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
