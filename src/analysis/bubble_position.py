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
from statistics import mean, median, pstdev
from typing import List, Optional

from database.models import MarketSnapshot, PlatformPrice
from timeutil import local_date

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

# Band boundaries as percentiles of the window.
#
# The forward 24h return changed sign near the 40th percentile in the first 41 days
# of production data, and readings above the 80th were consistently the worst
# entries. These are starting boundaries derived from observation, not constants
# believed to be permanent: the percentile they correspond to in price terms is
# recomputed from the window on every call, and the boundaries themselves should be
# re-derived once enough history exists to measure them properly.
CHEAP_PERCENTILE = 40
EXPENSIVE_PERCENTILE = 80


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
    percentile: Optional[int]
    cheap_below: Optional[float]
    expensive_above: Optional[float]
    band: str
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
        percentile=None,
        cheap_below=None,
        expensive_above=None,
        band="INSUFFICIENT_DATA",
        zone="INSUFFICIENT_DATA",
        confidence="INSUFFICIENT_DATA",
        drift="UNKNOWN",
    )


def _percentile_of(value: float, sorted_values: List[float]) -> int:
    """Share of the window at or below this reading, as a whole number."""
    at_or_below = sum(1 for v in sorted_values if v <= value)
    return round(100.0 * at_or_below / len(sorted_values))


def _value_at_percentile(sorted_values: List[float], percentile: int) -> float:
    index = int(percentile / 100.0 * len(sorted_values))
    return sorted_values[max(0, min(len(sorted_values) - 1, index))]


def _classify_band(percentile: Optional[int]) -> str:
    """Plain bands for presentation.

    Percentile is used rather than the z-score because the bubble distribution is
    left-skewed: a long tail of deep discounts inflates the standard deviation, so
    a z-score reports readings as normal while they sit in the top fifth of the
    range. Rank survives skew; distance from the mean does not.
    """
    if percentile is None:
        return "INSUFFICIENT_DATA"
    if percentile < CHEAP_PERCENTILE:
        return "CHEAP"
    if percentile >= EXPENSIVE_PERCENTILE:
        return "EXPENSIVE"
    return "TYPICAL"


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

    ordered = sorted(values)
    percentile = _percentile_of(bubble, ordered)

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
        percentile=percentile,
        cheap_below=round(_value_at_percentile(ordered, CHEAP_PERCENTILE), 4),
        expensive_above=round(_value_at_percentile(ordered, EXPENSIVE_PERCENTILE), 4),
        band=_classify_band(percentile),
        zone=_classify_zone(z_score),
        confidence=_classify_confidence(coverage_days, len(values)),
        drift=_classify_drift(values, spread),
    )


# ---------------------------------------------------------------------------
# Relative valuation on a trimmed basis
# ---------------------------------------------------------------------------

# How many of the cheapest platforms the valuation price is drawn from.
#
# This was the single cheapest platform until 2026-09-16. Measured over 332
# snapshots, the cheapest platform sits more than 3 median absolute deviations
# below the median of the rest in 62% of them: it is a tail point, not a market
# level. That showed up as noise rather than signal — hour-to-hour standard
# deviation of 0.438 against 0.273 for the mean of the three cheapest, and 8
# jumps larger than 1 pp between consecutive readings against 1.
#
# A jump of that size in an hour is a quote artefact. On 2026-09-15 a single
# stale MioGold quote moved the reported discount 2.07 pp and would have read as
# "unusually large, bigger than 94% of the last 30 days" while the market had not
# moved at all; the quote refreshed the next morning and the discount fell back.
#
# Three is a trim, which is the standard treatment for a skewed distribution and
# the same reasoning that put percentile ahead of z-score above. It keeps the
# buyer's side of the distribution (3.47% against the median's 2.97%) instead of
# retreating to the middle of a pack nobody transacts at.
#
# The single cheapest platform is still resolved and displayed, as the execution
# price. What changed is which number the valuation rests on.
CHEAP_BASIS_COUNT = 3

# Before the collection_mode migration of 2026-09-14, nothing recorded whether a
# reading came from the schedule or from a user pressing Update, so the window is
# drawn from a sample whose composition cannot be verified. Scheduled readings are
# preferred once there are enough of them.
#
# Enough means both a count and a calendar span. The count alone is not sufficient:
# at 16 scheduled runs a day, 30 readings is under two days, and a line reading
# "of the last 30 days" would be measuring against Tuesday. The Iranian week also
# has a shape — the Thursday and Friday weekend runs 0.28 and 0.40 pp deeper than
# the weekday median, against a 0.55 pp spread across the whole week — so a
# seven-day span either contains a weekend or does not, and that alone shifts the
# median by more than a typical hourly move. Fourteen days always contains two.
MIN_SCHEDULED_READINGS = 30
MIN_SCHEDULED_COVERAGE_DAYS = 14


@dataclass
class RelativeValuation:
    gap: Optional[float]            # signed; negative is a discount
    percentile: Optional[int]
    bigger_than: Optional[int]      # share of the window with a smaller discount
    deep_at: Optional[float]        # signed threshold at CHEAP_PERCENTILE
    move_label: str
    move_percentile: Optional[int]
    basis_price: Optional[float]
    basis_count: int
    window_days: int
    sample_size: int
    coverage_days: int
    sampling: str                   # SCHEDULED | MIXED
    status: str


def cheap_basis_price(prices) -> Optional[float]:
    """Mean of the cheapest few platform prices."""
    values = sorted(p for p in prices if p is not None)
    if not values:
        return None
    return mean(values[:min(CHEAP_BASIS_COUNT, len(values))])


def signed_gap(basis_price: Optional[float], fair_price: Optional[float]) -> Optional[float]:
    """Gap to fair value, negative for a discount.

    The same sign convention as premium_percent, so this can be compared against
    stored history and read by code that already understands that convention.
    """
    if basis_price is None or not fair_price:
        return None
    return (basis_price / fair_price - 1) * 100


def _empty_valuation(window_days: int) -> RelativeValuation:
    return RelativeValuation(None, None, None, None, "UNKNOWN", None, None, 0,
                             window_days, 0, 0, "UNKNOWN", "INSUFFICIENT_DATA")


def _basis_series(session, window_start, now):
    """(timestamp, collection_mode, signed gap) per snapshot, on the trimmed basis.

    Rebuilt from platform_prices rather than read from the stored premium_percent,
    because the stored column is computed from the single cheapest platform. Mixing
    the two would compare a reading on one basis against a window on another, which
    is the contamination this whole change exists to remove.
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
            MarketSnapshot.timestamp <= now,
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
        gap = signed_gap(cheap_basis_price(entry["prices"]), entry["fair"])
        if gap is not None:
            series.append((entry["timestamp"], entry["mode"], gap))
    series.sort(key=lambda item: item[0])
    return series


def resolve_relative_valuation(
    session,
    markets=None,
    fair_price: Optional[float] = None,
    change_pp: Optional[float] = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    now: Optional[datetime] = None,
) -> RelativeValuation:
    """Where the current reading sits in its own recent distribution.

    Move size is ranked here rather than in a separate call because it needs the
    same window, rebuilt by the same query. `change_pp` is the change in the size
    of the gap, in percentage points, which the caller has already resolved against
    its own baseline.
    """
    if session is None:
        return _empty_valuation(window_days)
    if now is None:
        now = datetime.utcnow()

    prices = []
    if markets:
        prices = [
            float(info["price"]) for info in markets.values()
            if info.get("status") == "OK" and info.get("price") is not None
        ]
    basis_price = cheap_basis_price(prices)
    current = signed_gap(basis_price, fair_price)

    try:
        series = _basis_series(session, now - timedelta(days=window_days), now)
    except Exception as e:
        print(f"Relative valuation query failed: {e}")
        return _empty_valuation(window_days)

    if current is None:
        if not series:
            return _empty_valuation(window_days)
        current = series[-1][2]

    scheduled = [item for item in series if item[1] == "scheduled"]
    scheduled_days = len({local_date(item[0]) for item in scheduled})
    clean = (
        len(scheduled) >= MIN_SCHEDULED_READINGS
        and scheduled_days >= MIN_SCHEDULED_COVERAGE_DAYS
    )
    chosen = scheduled if clean else series
    sampling = "SCHEDULED" if clean else "MIXED"
    values = sorted(item[2] for item in chosen)
    coverage_days = len({local_date(item[0]) for item in chosen})

    result = _empty_valuation(window_days)
    result.gap = current
    result.basis_price = basis_price
    result.basis_count = min(CHEAP_BASIS_COUNT, len(prices)) if prices else 0
    result.sample_size = len(values)
    result.coverage_days = coverage_days
    result.sampling = sampling
    if len(values) < MIN_OBSERVATIONS:
        return result

    percentile = _percentile_of(current, values)
    result.percentile = percentile
    result.bigger_than = 100 - percentile
    result.deep_at = round(_value_at_percentile(values, CHEAP_PERCENTILE), 4)
    result.status = "OK"

    if change_pp is not None:
        ordered = [item[2] for item in chosen]
        moves = sorted(
            abs(abs(ordered[i + 1]) - abs(ordered[i])) for i in range(len(ordered) - 1)
        )
        if moves:
            move_percentile = _percentile_of(abs(change_pp), moves)
            result.move_percentile = move_percentile
            if move_percentile < LARGE_MOVE_PERCENTILE:
                result.move_label = "a normal move"
            elif move_percentile < UNUSUAL_MOVE_PERCENTILE:
                result.move_label = "a large move"
            else:
                result.move_label = "unusually large"
    return result


# ---------------------------------------------------------------------------
# How large this move is, against the distribution of past moves
# ---------------------------------------------------------------------------

# Band boundaries as percentiles of past absolute changes.
#
# Percentile is used rather than a standard deviation or a median absolute
# deviation for the same reason the position bands use it: the distribution is
# skewed, so any measure of distance from a centre misreports rank. It also keeps
# one vocabulary across the whole message. Position and move size both answer
# "where does this sit against its own history", so the reader learns one idea
# instead of two, and no threshold in an invented unit has to be explained.
LARGE_MOVE_PERCENTILE = 50
UNUSUAL_MOVE_PERCENTILE = 80


@dataclass
class ChangeMagnitude:
    change_pp: Optional[float]
    percentile: Optional[int]
    label: str
    sample_size: int
    status: str


def resolve_change_magnitude(
    session,
    change_pp: Optional[float],
    window_days: int = DEFAULT_WINDOW_DAYS,
    now: Optional[datetime] = None,
) -> ChangeMagnitude:
    """Rank the size of the current move against the bubble's own past moves.

    Direction is discarded and only size is ranked, so a 2 pp move is judged the
    same whether the discount grew or shrank. The caller states direction
    separately, which keeps this measure from having to carry two meanings.
    """
    empty = ChangeMagnitude(change_pp, None, "UNKNOWN", 0, "INSUFFICIENT_DATA")
    if session is None or change_pp is None:
        return empty
    if now is None:
        now = datetime.now()

    try:
        rows = (
            session.query(MarketSnapshot.timestamp, MarketSnapshot.premium_percent)
            .filter(
                MarketSnapshot.premium_percent.isnot(None),
                MarketSnapshot.timestamp >= now - timedelta(days=window_days),
                MarketSnapshot.timestamp <= now,
            )
            .order_by(MarketSnapshot.timestamp.asc())
            .all()
        )
    except Exception as e:
        print(f"Change magnitude query failed: {e}")
        return empty

    values = [float(p) for _, p in rows if p is not None]
    if len(values) < MIN_OBSERVATIONS:
        return empty

    moves = sorted(abs(values[i + 1] - values[i]) for i in range(len(values) - 1))
    if not moves:
        return empty

    percentile = _percentile_of(abs(change_pp), moves)
    if percentile < LARGE_MOVE_PERCENTILE:
        label = "a normal move"
    elif percentile < UNUSUAL_MOVE_PERCENTILE:
        label = "a large move"
    else:
        label = "unusually large"

    return ChangeMagnitude(
        change_pp=round(change_pp, 3),
        percentile=percentile,
        label=label,
        sample_size=len(moves),
        status="OK",
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
    saved_when_cheaper_pp: Optional[float]
    cost_when_pricier_pp: Optional[float]
    expectancy_pp: Optional[float]
    reward_to_risk: Optional[float]
    best_case_pp: Optional[float]
    worst_case_pp: Optional[float]
    band_low: Optional[float]
    band_high: Optional[float]
    status: str


def _empty_outcomes(horizon_hours: int, band_low=None, band_high=None) -> SimilarOutcomes:
    return SimilarOutcomes(
        horizon_hours=horizon_hours,
        cases=0,
        became_cheaper=0,
        became_pricier=0,
        unchanged=0,
        average_move_pp=None,
        saved_when_cheaper_pp=None,
        cost_when_pricier_pp=None,
        expectancy_pp=None,
        reward_to_risk=None,
        best_case_pp=None,
        worst_case_pp=None,
        band_low=band_low,
        band_high=band_high,
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
        return _empty_outcomes(horizon_hours, round(band_low, 4), round(band_high, 4))

    cheaper_moves = [m for m in moves if m < -UNCHANGED_DEADBAND_PP]
    pricier_moves = [m for m in moves if m > UNCHANGED_DEADBAND_PP]
    unchanged = len(moves) - len(cheaper_moves) - len(pricier_moves)

    # Counting alone is not enough to judge whether waiting is worthwhile. A high
    # share of favourable cases can still lose if the unfavourable ones are larger,
    # so the average size of each side is carried and combined into an expectancy.
    saved = abs(mean(cheaper_moves)) if cheaper_moves else 0.0
    cost = abs(mean(pricier_moves)) if pricier_moves else 0.0
    decided = len(cheaper_moves) + len(pricier_moves)
    share_cheaper = (len(cheaper_moves) / decided) if decided else 0.0
    expectancy = share_cheaper * saved - (1 - share_cheaper) * cost

    return SimilarOutcomes(
        horizon_hours=horizon_hours,
        cases=len(moves),
        became_cheaper=len(cheaper_moves),
        became_pricier=len(pricier_moves),
        unchanged=unchanged,
        average_move_pp=round(mean(moves), 3),
        saved_when_cheaper_pp=round(saved, 3),
        cost_when_pricier_pp=round(cost, 3),
        expectancy_pp=round(expectancy, 3),
        reward_to_risk=round(saved / cost, 2) if cost else None,
        best_case_pp=round(abs(min(moves)), 3),
        worst_case_pp=round(max(moves), 3),
        band_low=round(band_low, 4),
        band_high=round(band_high, 4),
        status="OK",
    )


# ---------------------------------------------------------------------------
# Speed, expressed against its own normal
# ---------------------------------------------------------------------------

SPEED_LOOKBACK_HOURS = 48
QUIET_RATIO = 0.5
FAST_RATIO = 1.5


@dataclass
class BubbleSpeed:
    rate_per_day_pp: Optional[float]
    typical_per_day_pp: Optional[float]
    ratio_to_typical: Optional[float]
    pace: str
    direction: str
    status: str


def resolve_bubble_speed(
    session,
    cheap_below: Optional[float] = None,
    lookback_hours: int = SPEED_LOOKBACK_HOURS,
    now: Optional[datetime] = None,
) -> BubbleSpeed:
    """How fast the bubble is moving, relative to its own normal pace.

    A rate on its own tells a reader nothing, because there is no reference for
    whether it is fast. It is therefore divided by the typical daily move, and
    pointed at the cheap boundary so the direction carries meaning.
    """
    empty = BubbleSpeed(None, None, None, "UNKNOWN", "UNKNOWN", "INSUFFICIENT_DATA")
    if session is None:
        return empty
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
        print(f"Bubble speed query failed: {e}")
        return empty

    series = [(ts, float(p)) for ts, p in rows if p is not None]
    if len(series) < MIN_OBSERVATIONS:
        return empty

    recent = [(ts, p) for ts, p in series if ts >= now - timedelta(hours=lookback_hours)]
    if len(recent) < 2:
        return empty

    hours = (recent[-1][0] - recent[0][0]).total_seconds() / 3600.0
    if hours <= 0:
        return empty
    rate = (recent[-1][1] - recent[0][1]) / hours * 24.0

    # Measure the typical move over a genuine day rather than extrapolating from
    # whatever gap happens to separate two readings. Consecutive readings can be
    # minutes apart, and scaling a small change across a short gap to a daily rate
    # produces figures larger than the bubble's entire observed range.
    daily_changes = []
    day = timedelta(hours=24)
    slack = timedelta(hours=2)
    for index, (timestamp, premium) in enumerate(series):
        target = timestamp + day
        for later_timestamp, later_premium in series[index + 1:]:
            if later_timestamp > target + slack:
                break
            if abs(later_timestamp - target) <= slack:
                daily_changes.append(abs(later_premium - premium))
                break
    typical = mean(daily_changes) if daily_changes else None

    ratio = (abs(rate) / typical) if typical else None
    if ratio is None:
        pace = "UNKNOWN"
    elif ratio < QUIET_RATIO:
        pace = "QUIET"
    elif ratio > FAST_RATIO:
        pace = "FAST"
    else:
        pace = "NORMAL"

    direction = "FLAT"
    if cheap_below is not None and abs(rate) > 0:
        current = series[-1][1]
        if current <= cheap_below:
            direction = "INSIDE_CHEAP"
        else:
            direction = "TOWARD_CHEAP" if rate < 0 else "AWAY_FROM_CHEAP"

    return BubbleSpeed(
        rate_per_day_pp=round(rate, 3),
        typical_per_day_pp=round(typical, 3) if typical else None,
        ratio_to_typical=round(ratio, 2) if ratio else None,
        pace=pace,
        direction=direction,
        status="OK",
    )


# ---------------------------------------------------------------------------
# Moving averages of the bubble
# ---------------------------------------------------------------------------

SHORT_AVERAGE_DAYS = 7
LONG_AVERAGE_DAYS = 15


@dataclass
class BubbleTrend:
    bubble: Optional[float]
    short_average: Optional[float]
    long_average: Optional[float]
    short_days: int
    long_days: int
    versus_short: str
    cross: str
    reading: str
    status: str


# Messages show two decimal places. Comparisons are made at that precision so the
# text never asserts a difference the reader cannot see.
DISPLAY_DECIMALS = 2


def _compare_at_display_precision(left: float, right: float) -> str:
    """ABOVE, BELOW or EQUAL, judged at the precision actually displayed."""
    rounded_left = round(left, DISPLAY_DECIMALS)
    rounded_right = round(right, DISPLAY_DECIMALS)
    if rounded_left == rounded_right:
        return "EQUAL"
    return "ABOVE" if rounded_left > rounded_right else "BELOW"


def _equal_weighted_daily_mean(series, reference_date, days: int) -> Optional[float]:
    """Mean of daily means over completed days.

    Each day contributes once regardless of how many readings it holds, so a day
    that happened to be sampled heavily does not dominate the average.
    """
    by_day = {}
    for timestamp, value in series:
        day = timestamp.date()
        if day == reference_date or (reference_date - day).days > days:
            continue
        by_day.setdefault(day, []).append(value)
    if not by_day:
        return None
    return mean(mean(values) for values in by_day.values())


def resolve_bubble_trend(
    session,
    current_bubble: Optional[float] = None,
    now: Optional[datetime] = None,
) -> BubbleTrend:
    """Moving averages of the bubble, not of the price.

    A moving average of the local price mostly tracks currency devaluation, so it
    reports an uptrend almost permanently and carries little information. The bubble
    is the part that mean-reverts, so the averages are taken on it: a short average
    above the long one means the discount has been shrinking, which is gold becoming
    more expensive relative to fair value.
    """
    empty = BubbleTrend(None, None, None, SHORT_AVERAGE_DAYS, LONG_AVERAGE_DAYS,
                        "UNKNOWN", "UNKNOWN", "UNKNOWN", "INSUFFICIENT_DATA")
    if session is None:
        return empty
    if now is None:
        now = datetime.now()

    try:
        rows = (
            session.query(MarketSnapshot.timestamp, MarketSnapshot.premium_percent)
            .filter(
                MarketSnapshot.premium_percent.isnot(None),
                MarketSnapshot.timestamp >= now - timedelta(days=LONG_AVERAGE_DAYS + 1),
            )
            .order_by(MarketSnapshot.timestamp.asc())
            .all()
        )
    except Exception as e:
        print(f"Bubble trend query failed: {e}")
        return empty

    series = [(ts, float(p)) for ts, p in rows if p is not None]
    if not series:
        return empty

    bubble = current_bubble if current_bubble is not None else series[-1][1]
    reference_date = now.date()
    short_average = _equal_weighted_daily_mean(series, reference_date, SHORT_AVERAGE_DAYS)
    long_average = _equal_weighted_daily_mean(series, reference_date, LONG_AVERAGE_DAYS)

    if short_average is None or long_average is None:
        result = empty
        result.bubble = bubble
        return result

    # Compare at the precision the reader is shown, not at storage precision. Two
    # values that both display as -3.42% must not carry a claim that one is below the
    # other; a difference the reader cannot see is not a difference worth asserting.
    versus_short = _compare_at_display_precision(bubble, short_average)
    cross = _compare_at_display_precision(short_average, long_average)
    if cross == "EQUAL":
        reading = "DISCOUNT_FLAT"
    elif cross == "ABOVE":
        reading = "DISCOUNT_SHRINKING"
    else:
        reading = "DISCOUNT_DEEPENING"

    return BubbleTrend(
        bubble=bubble,
        short_average=round(short_average, 3),
        long_average=round(long_average, 3),
        short_days=SHORT_AVERAGE_DAYS,
        long_days=LONG_AVERAGE_DAYS,
        versus_short=versus_short,
        cross=cross,
        reading=reading,
        status="OK",
    )


# ---------------------------------------------------------------------------
# How often the cheap zone appears and how long it lasts
# ---------------------------------------------------------------------------

@dataclass
class ZoneEpisodes:
    threshold: Optional[float]
    episodes: int
    typical_hours: Optional[float]
    longest_hours: Optional[float]
    currently_inside: bool
    measurement_quality: str
    status: str


def resolve_zone_episodes(
    session,
    cheap_below: Optional[float],
    window_days: int = DEFAULT_WINDOW_DAYS,
    now: Optional[datetime] = None,
) -> ZoneEpisodes:
    """How many times the cheap zone occurred, and how long each spell lasted.

    An episode is a run of consecutive readings below the threshold, so the measured
    duration is bounded by how often readings are taken. Under irregular collection a
    short spell may be an artefact of two adjacent readings rather than a real one,
    which is why measurement_quality is reported alongside the numbers.
    """
    empty = ZoneEpisodes(cheap_below, 0, None, None, False, "UNKNOWN", "INSUFFICIENT_DATA")
    if session is None or cheap_below is None:
        return empty
    if now is None:
        now = datetime.now()

    try:
        rows = (
            session.query(MarketSnapshot.timestamp, MarketSnapshot.premium_percent)
            .filter(
                MarketSnapshot.premium_percent.isnot(None),
                MarketSnapshot.timestamp >= now - timedelta(days=window_days),
            )
            .order_by(MarketSnapshot.timestamp.asc())
            .all()
        )
    except Exception as e:
        print(f"Zone episode query failed: {e}")
        return empty

    series = [(ts, float(p)) for ts, p in rows if p is not None]
    if len(series) < MIN_OBSERVATIONS:
        return empty

    spans: List[List[datetime]] = []
    run: List[datetime] = []
    for timestamp, premium in series:
        if premium <= cheap_below:
            run.append(timestamp)
        elif run:
            spans.append(run)
            run = []
    if run:
        spans.append(run)

    durations = [
        (span[-1] - span[0]).total_seconds() / 3600.0
        for span in spans if len(span) > 1
    ]

    gaps = [
        (series[i][0] - series[i - 1][0]).total_seconds() / 3600.0
        for i in range(1, len(series))
    ]
    median_gap = median(gaps) if gaps else None
    if median_gap is None:
        quality = "UNKNOWN"
    elif median_gap <= 1.0:
        quality = "RELIABLE"
    else:
        quality = "COARSE"

    return ZoneEpisodes(
        threshold=cheap_below,
        episodes=len(spans),
        typical_hours=round(median(durations), 1) if durations else None,
        longest_hours=round(max(durations), 1) if durations else None,
        currently_inside=series[-1][1] <= cheap_below,
        measurement_quality=quality,
        status="OK",
    )
