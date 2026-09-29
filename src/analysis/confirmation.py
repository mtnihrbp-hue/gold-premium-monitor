"""Confirmation of a BUY or SELL before it can become a final decision.

The SP-A matrix turns three legs into a candidate, and two of those legs read one
platform: valuation ranks the stored premium, which is the single cheapest price, and
momentum moves with it. On 2026-09-29 the cheapest price was a stale copy of Taline's
web page, served to GitHub's non-Iranian runners by its CDN, 2.4 pp below every other
platform. The candidate read BUY, hysteresis let it through, and the alert went out
(SP_C_HANDOFF.md section 37).

This module does not touch the matrix. It asks, between the candidate and the final
decision, whether the evidence underneath the candidate can be trusted:

- a BUY needs a **second platform** to confirm the discount, judged on that platform's
  own record by the same classifier the valuation leg uses;
- any signal needs the **dollar rate** to be today's;
- any signal needs **world gold** to be a live quote rather than a cached fallback.

SELL is not given the second-platform check. It rests on the cheapest platform being
above fair value by the sell gate, and the cheapest price is already the most
conservative reading of a premium: every other platform is higher.

A check that cannot be evaluated counts as failed. Holding an alert costs one message;
sending one that rests on a stale input is the failure this module exists to prevent.
The push fails open for the opposite reason -- its failure mode is silence about a
measurement -- but a BUY is a recommendation, and a recommendation must be able to
show its evidence.
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Optional

from analysis.bubble_position import (
    CHEAP_PERCENTILE,
    DEFAULT_WINDOW_DAYS,
    EXPENSIVE_PERCENTILE,
    MIN_OBSERVATIONS,
    _percentile_of,
    reference_readings,
    signed_gap,
)
from caluclator.valuation import classify_valuation
from database.models import MarketSnapshot, PlatformPrice
from timeutil import local_date, to_tehran, to_utc

# Tehran hours, measured over the scheduled readings of 2026-09-15 to 09-28
# (SP_C_HANDOFF.md 34.3 and 38). The USD/IRR input barely moves before the currency
# market opens -- one change in 39 readings at 07:00, 09:00 and 10:00, and tgju.org
# still showed the previous close at 09:20 on 09-29 -- and every large step landed
# between 11:00 and 13:00. Before the open a reading carries yesterday's dollar;
# between the open and 13:00 it carries today's only if the rate has moved since the
# open; from 13:00 an unmoved rate is taken as the day's rate, since a flat dollar on
# a quiet day (Fridays, and one Wednesday) is a real rate, not a missing update.
DOLLAR_OPEN_HOUR = 11
DOLLAR_SETTLED_HOUR = 13


@dataclass
class SignalConfirmation:
    """What was checked before a candidate could become final.

    Every check is True, False or None, and None means it could not be evaluated,
    which `held_reason` treats as a failure.
    """

    second_platform: Optional[str] = None
    second_gap: Optional[float] = None          # signed gap to fair value, percent
    second_percentile: Optional[int] = None     # rank in its own settled window
    second_confirms: Optional[bool] = None
    dollar_live: Optional[bool] = None
    dollar_updated_at: Optional[datetime] = None  # naive UTC; when the current rate took effect
    world_live: Optional[bool] = None
    status: str = "UNKNOWN"

    def held_reason(self, side: str) -> Optional[str]:
        """Why a `side` candidate may not become final, or None when it may."""
        if side == "BUY":
            if self.second_confirms is None:
                return "a second platform could not be checked"
            if not self.second_confirms:
                if self.second_platform:
                    return (f"only one platform shows this discount; the next cheapest, "
                            f"{self.second_platform}, is not heavily discounted on its "
                            f"own record")
                return "only one platform shows this discount"
        if self.dollar_live is None:
            return "the dollar rate could not be checked"
        if not self.dollar_live:
            return "the dollar rate has not updated today"
        if not self.world_live:
            return "world gold is a cached price, not a live quote"
        return None


def second_cheapest(markets, fair_price):
    """(name, signed gap) of the second-cheapest platform, or (None, None)."""
    valid = sorted(
        (float(info["price"]), name)
        for name, info in (markets or {}).items()
        if info.get("status") == "OK" and info.get("price") is not None
    )
    if len(valid) < 2 or not fair_price:
        return None, None
    price, name = valid[1]
    return name, signed_gap(price, fair_price)


def second_gap_series(session, window_start, reference_end):
    """(timestamp, collection_mode, signed gap of the second-cheapest platform).

    Rebuilt from platform prices, as `bubble_position._basis_series` is for the
    trimmed basis, so the reading is ranked against a window on its own basis.
    """
    rows = (
        session.query(
            MarketSnapshot.id,
            MarketSnapshot.timestamp,
            MarketSnapshot.fair_price,
            MarketSnapshot.collection_mode,
            PlatformPrice.price_irr,
        )
        .join(PlatformPrice, PlatformPrice.snapshot_id == MarketSnapshot.id)
        .filter(
            MarketSnapshot.fair_price.isnot(None),
            PlatformPrice.price_irr.isnot(None),
            MarketSnapshot.timestamp >= window_start,
            MarketSnapshot.timestamp < reference_end,
        )
        .all()
    )
    grouped = {}
    for snapshot_id, timestamp, fair, mode, price in rows:
        entry = grouped.setdefault(
            snapshot_id,
            {"timestamp": timestamp, "fair": float(fair), "mode": mode, "prices": []},
        )
        entry["prices"].append(float(price))

    series = []
    for entry in grouped.values():
        prices = sorted(entry["prices"])
        if len(prices) < 2:
            continue
        gap = signed_gap(prices[1], entry["fair"])
        if gap is not None:
            series.append((entry["timestamp"], entry["mode"], gap))
    series.sort(key=lambda item: item[0])
    return series


def _check_second_platform(session, markets, fair_price, thresholds, now, result):
    name, gap = second_cheapest(markets, fair_price)
    result.second_platform, result.second_gap = name, gap
    if gap is None:
        return
    # The same settled, non-user window the valuation leg ranks against (SP-C.7,
    # SP-C.15), so the two ranks can only disagree because the platforms do.
    reference_end = to_utc(datetime.combine(local_date(now), datetime.min.time()))
    series = second_gap_series(
        session, reference_end - timedelta(days=DEFAULT_WINDOW_DAYS), reference_end)
    values = sorted(item[2] for item in reference_readings(series, reference_end))
    if len(values) < MIN_OBSERVATIONS:
        return
    result.second_percentile = _percentile_of(gap, values)
    state = classify_valuation(
        result.second_percentile, gap,
        cheap_rank=CHEAP_PERCENTILE, expensive_rank=EXPENSIVE_PERCENTILE,
        buy_at=thresholds.get("buy_premium_percent", -1.5),
        sell_at=thresholds.get("sell_premium_percent", 3.0),
    )
    result.second_confirms = state == "CHEAP"


def _check_dollar(session, usd, now, result):
    if usd is None:
        return
    local = to_tehran(now)
    open_utc = to_utc(datetime.combine(local.date(), time(DOLLAR_OPEN_HOUR)))
    since = to_utc(datetime.combine(local.date() - timedelta(days=1), datetime.min.time()))
    rows = (
        session.query(MarketSnapshot.timestamp, MarketSnapshot.usd_irr)
        .filter(
            MarketSnapshot.usd_irr.isnot(None),
            MarketSnapshot.timestamp >= since,
            MarketSnapshot.timestamp < now,
        )
        .order_by(MarketSnapshot.timestamp.asc())
        .all()
    )
    readings = [(timestamp, float(value)) for timestamp, value in rows]
    current = float(usd)

    # When the current rate took effect: the start of the trailing run of readings
    # that carry it, or now if this reading is the first to carry it.
    updated_at = now
    for timestamp, value in reversed(readings):
        if value != current:
            break
        updated_at = timestamp
    result.dollar_updated_at = updated_at

    if local.hour < DOLLAR_OPEN_HOUR:
        result.dollar_live = False
        return
    if local.hour >= DOLLAR_SETTLED_HOUR:
        result.dollar_live = True
        return
    before_open = [value for timestamp, value in readings if timestamp < open_utc]
    if not before_open:
        return
    rate_at_open = before_open[-1]
    since_open = [value for timestamp, value in readings if timestamp >= open_utc]
    result.dollar_live = any(value != rate_at_open for value in since_open + [current])


def resolve_signal_confirmation(session, markets, fair_price, usd, world_from_fallback,
                                thresholds, now=None) -> SignalConfirmation:
    """Evaluate every confirmation check for the reading being decided.

    Reads only. `now` is naive UTC. The caller treats any exception as a failed
    confirmation, so a database outage holds signals rather than releasing them.
    """
    if now is None:
        now = datetime.utcnow()
    result = SignalConfirmation(world_live=not world_from_fallback)
    _check_second_platform(session, markets, fair_price, thresholds or {}, now, result)
    _check_dollar(session, usd, now, result)
    result.status = "OK"
    return result
