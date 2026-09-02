"""Reusable historical trend resolver for UPDATE and ANALYZE.

The 7D values are true calendar-day averages: each available completed day
contributes one equally weighted daily value. This avoids collection-frequency
bias when snapshots arrive at different densities.

No persistence or schema changes are introduced. The resolver reads the
canonical MarketSnapshot/PlatformPrice history already used by UPDATE.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, Optional

from database.models import MarketSnapshot, PlatformPrice

SEVEN_DAY_COUNT = 7


@dataclass
class SevenDayTrend:
    xau_usd: Optional[float]
    usd_irr: Optional[float]
    fair_price: Optional[float]
    platform_average: Optional[float]
    premium_percent: Optional[float]
    day_count: int


def _platform_average(session, snapshot_id: int) -> Optional[float]:
    rows = (
        session.query(PlatformPrice)
        .filter(PlatformPrice.snapshot_id == snapshot_id)
        .all()
    )
    values = [float(row.price_irr) for row in rows if row.price_irr is not None]
    return sum(values) / len(values) if values else None


def _daily_values(session, start_date: date, end_date: date) -> Dict[date, Dict[str, list]]:
    start = datetime.combine(start_date, datetime.min.time())
    end = datetime.combine(end_date + timedelta(days=1), datetime.min.time())
    snapshots = (
        session.query(MarketSnapshot)
        .filter(MarketSnapshot.timestamp >= start, MarketSnapshot.timestamp < end)
        .order_by(MarketSnapshot.timestamp.asc())
        .all()
    )

    grouped: Dict[date, Dict[str, list]] = {}
    for snapshot in snapshots:
        day = snapshot.timestamp.date()
        bucket = grouped.setdefault(
            day,
            {"xau_usd": [], "usd_irr": [], "fair_price": [], "platform_average": [], "premium_percent": []},
        )
        if snapshot.world_gold_usd is not None:
            bucket["xau_usd"].append(float(snapshot.world_gold_usd))
        if snapshot.usd_irr is not None:
            bucket["usd_irr"].append(float(snapshot.usd_irr))
        if snapshot.fair_price is not None:
            bucket["fair_price"].append(float(snapshot.fair_price))
        if snapshot.premium_percent is not None:
            bucket["premium_percent"].append(float(snapshot.premium_percent))
        platform_avg = _platform_average(session, snapshot.id)
        if platform_avg is not None:
            bucket["platform_average"].append(platform_avg)
    return grouped


def _mean(values) -> Optional[float]:
    return sum(values) / len(values) if values else None


def resolve_seven_day_trend(session, now: Optional[datetime] = None) -> SevenDayTrend:
    """Return seven equally weighted daily averages for completed days only.

    The current partial day is deliberately excluded. A 7D value is returned
    only when all seven preceding calendar days contain at least one valid
    observation for that metric. ``day_count`` reports the number of complete
    calendar days represented in the window.
    """
    if now is None:
        now = datetime.now()
    today = now.date()
    start_date = today - timedelta(days=SEVEN_DAY_COUNT)
    end_date = today - timedelta(days=1)
    grouped = _daily_values(session, start_date, end_date)

    complete_days = [day for day in (start_date + timedelta(days=i) for i in range(SEVEN_DAY_COUNT)) if day in grouped]
    day_count = len(complete_days)
    if day_count < SEVEN_DAY_COUNT:
        return SevenDayTrend(None, None, None, None, None, day_count)

    metric_values = {"xau_usd": [], "usd_irr": [], "fair_price": [], "platform_average": [], "premium_percent": []}
    for day in complete_days:
        bucket = grouped[day]
        for metric in metric_values:
            daily_mean = _mean(bucket[metric])
            if daily_mean is None:
                return SevenDayTrend(None, None, None, None, None, day_count)
            metric_values[metric].append(daily_mean)

    return SevenDayTrend(
        xau_usd=_mean(metric_values["xau_usd"]),
        usd_irr=_mean(metric_values["usd_irr"]),
        fair_price=_mean(metric_values["fair_price"]),
        platform_average=_mean(metric_values["platform_average"]),
        premium_percent=_mean(metric_values["premium_percent"]),
        day_count=day_count,
    )
