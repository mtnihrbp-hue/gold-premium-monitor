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


def _seven_day_metric(grouped, days, metric) -> Optional[float]:
    daily_means = []
    for day in days:
        bucket = grouped.get(day)
        if not bucket:
            return None
        daily_mean = _mean(bucket[metric])
        if daily_mean is None:
            return None
        daily_means.append(daily_mean)
    return _mean(daily_means) if len(daily_means) == SEVEN_DAY_COUNT else None


def resolve_seven_day_trend(session, now: Optional[datetime] = None) -> SevenDayTrend:
    """Return seven equally weighted daily averages for completed days only.

    The current partial day is deliberately excluded. Each metric is evaluated
    independently, so a missing XAU/USD observation does not suppress a valid
    7D Platform Avg or Fair Price value.
    """
    if now is None:
        now = datetime.now()
    today = now.date()
    start_date = today - timedelta(days=SEVEN_DAY_COUNT)
    end_date = today - timedelta(days=1)
    days = [start_date + timedelta(days=i) for i in range(SEVEN_DAY_COUNT)]
    grouped = _daily_values(session, start_date, end_date)

    return SevenDayTrend(
        xau_usd=_seven_day_metric(grouped, days, "xau_usd"),
        usd_irr=_seven_day_metric(grouped, days, "usd_irr"),
        fair_price=_seven_day_metric(grouped, days, "fair_price"),
        platform_average=_seven_day_metric(grouped, days, "platform_average"),
        premium_percent=_seven_day_metric(grouped, days, "premium_percent"),
        day_count=sum(1 for day in days if day in grouped),
    )
