"""Read model for the ANALYZE message and the deep-discount push.

ANALYZE answers the question UPDATE raises and never addresses: the discount is at
some level, and does that matter? It reports what the record shows and forecasts
nothing. Every figure here is a count or a rank over readings that already happened.

Two constraints shape the whole module.

Everything is computed on the trimmed basis -- the mean of the three cheapest
platforms -- because that is what the reader is shown. Comparing a trimmed reading
against a history built from the single cheapest platform would report a change of
definition as a change in the market, which is the contamination SP-C.5 removed from
UPDATE and must not be reintroduced here.

Nothing in this module executes the Analysis Wing. `skills/telegram-product.md`:
"A user request must not silently become an Analysis Wing execution or historical
learning observation." These are reads over persisted state, so a user pressing
Analyze produces no snapshot, no outcome evaluation and no row of any kind.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import median
from typing import List, Optional, Tuple

from analysis.bubble_position import (
    DEEP_DISCOUNT_PERCENTILE,
    DEFAULT_WINDOW_DAYS,
    MIN_OBSERVATIONS,
    _value_at_percentile,
    basis_series,
    cheap_basis_price,
    deep_discount_threshold,
    reference_readings,
    signed_gap,
)
from timeutil import local_date, to_utc
# One definition each, at the src root. These existed under four names in four
# modules until SP-C.16; see `tolerances.py`.
from tolerances import COMPARABLE_BAND_FRACTION, UNCHANGED_DEADBAND_PP

# Horizon for the "what happened next" section. One day is the only horizon with
# both a usable sample and a meaning a buyer can act on: a 1h horizon measures noise,
# and anything longer outruns the deep zone, which typically closes inside five hours.
OUTCOME_HORIZON_HOURS = 24

# How far from the target a later reading may sit and still measure the horizon.
HORIZON_TOLERANCE_HOURS = 2.0

# Fewest comparable readings worth reporting counts over.
#
# The section gated only on the *window* holding 30 readings, never on how many
# readings the comparable band actually caught. On 2026-09-22 the discount reached
# 0.74%, below anything in the window, and the band held two readings -- which the
# message printed as "increased 2 times, average 1.62 pp" in the same layout it uses
# for a hundred. `skills/market-analyst.md` forbids manufacturing confidence from a
# small sample, and this was the file quoting it.
#
# Fifteen: measured across the 273 readings in the window, a band narrower than this
# occurs for 6% of levels, and those are the genuine extremes -- exactly where a
# reader is most curious and the record has least to say. Ten would suppress 4%,
# twenty 8%.
MIN_COMPARABLE_READINGS = 15

# The deep zone is the level defined once in bubble_position and shared with UPDATE
# and the push, not a rank this module chooses for itself. It was a local constant of
# the same value until 2026-09-21, which is how it came to disagree with UPDATE.
DEEP_ZONE_PERCENTILE = DEEP_DISCOUNT_PERCENTILE

# The rank marking a sharp price move. A rank rather than a fixed level: a constant
# threshold in this market has gone stale four times, most recently when regime
# stress fired on 250 of 252 readings.
SHARP_MOVE_PERCENTILE = 95

# Consecutive readings further apart than this are not a price move, they are a gap.
MAX_STEP_HOURS = 2.0

# An episode cannot span a period nobody observed. Collection runs 06:00 to 21:00
# local, so the series carries a nightly gap of roughly nine hours: 66 of 264
# intervals exceed three hours against a median spacing of one. Without this, two
# readings either side of a night join into a single "episode" and the reported
# duration is mostly unobserved time -- 15 hours where the observed spans are a
# fraction of that. Three hours sits well above the hourly cadence and well below
# the overnight gap.
MAX_EPISODE_GAP_HOURS = 3.0


@dataclass
class LevelOutcomes:
    """What the discount did in the 24 hours after past readings at this level."""
    gap: Optional[float] = None
    band_low: Optional[float] = None
    band_high: Optional[float] = None
    cases: int = 0
    increased: int = 0
    decreased: int = 0
    unchanged: int = 0
    average_increase_pp: Optional[float] = None
    average_decrease_pp: Optional[float] = None
    average_change_pp: Optional[float] = None
    status: str = "INSUFFICIENT_DATA"


@dataclass
class Distribution:
    """Where the last 30 days sat, and where today sits inside them."""
    low: Optional[float] = None
    high: Optional[float] = None
    typical: Optional[float] = None
    today: Optional[float] = None
    sample_size: int = 0
    coverage_days: int = 0
    status: str = "INSUFFICIENT_DATA"


@dataclass
class DeepZone:
    """How often the deep zone appears and how long it stays open."""
    threshold: Optional[float] = None
    episodes: int = 0
    typical_hours: Optional[float] = None
    longest_hours: Optional[float] = None
    censored: int = 0
    inside_now: bool = False
    status: str = "INSUFFICIENT_DATA"


@dataclass
class PriceMovement:
    """How fast the price a buyer pays actually moves."""
    typical_move_percent: Optional[float] = None
    sharp_move_percent: Optional[float] = None
    sharp_count: int = 0
    last_sharp_at: Optional[datetime] = None
    last_sharp_percent: Optional[float] = None
    sample_size: int = 0
    status: str = "INSUFFICIENT_DATA"


@dataclass
class DataHealth:
    readings: int = 0
    coverage_days: int = 0
    sampling: str = "UNKNOWN"
    clean_from: Optional[str] = None
    outcomes_resolved: int = 0
    outcomes_total: int = 0
    decisions_total: int = 0
    decisions_non_wait: int = 0


@dataclass
class AnalyzeReport:
    level: LevelOutcomes = field(default_factory=LevelOutcomes)
    distribution: Distribution = field(default_factory=Distribution)
    deep_zone: DeepZone = field(default_factory=DeepZone)
    movement: PriceMovement = field(default_factory=PriceMovement)
    health: DataHealth = field(default_factory=DataHealth)
    generated_at: Optional[datetime] = None
    status: str = "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# Series helpers
# ---------------------------------------------------------------------------

def _settled_series(session, now, window_days):
    """Readings on the trimmed basis, excluding today and the reader's own clicks.

    The same two rules the valuation window uses. Today is excluded because a
    reference that contains the reading being measured moves under it, and user rows
    because pressing Update must not change the number being read.
    """
    reference_end = to_utc(datetime.combine(local_date(now), datetime.min.time()))
    series = basis_series(session, reference_end - timedelta(days=window_days), now)
    return reference_readings(series, reference_end)


def _percentile(sorted_values, percentile):
    """Alias. The formula lives in bubble_position; this module held a byte-identical
    copy, which is the shape every disagreement in this system has started as."""
    return None if not sorted_values else _value_at_percentile(sorted_values, percentile)


def _spread(values):
    """Interquartile-based spread. Robust to the tail a single stale quote produces."""
    if len(values) < 4:
        return None
    ordered = sorted(values)
    q1 = _percentile(ordered, 25)
    q3 = _percentile(ordered, 75)
    return None if q1 is None or q3 is None else abs(q3 - q1)


# ---------------------------------------------------------------------------
# Section 1 — what happened after readings at this level
# ---------------------------------------------------------------------------

def resolve_level_outcomes(
    session,
    current_gap: Optional[float],
    now: Optional[datetime] = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    horizon_hours: int = OUTCOME_HORIZON_HOURS,
) -> LevelOutcomes:
    """Past readings near the current level, and what followed each one.

    "Readings like today" means readings at a similar discount *level*, not readings
    taken today. Today supplies only the level.

    Every comparison looks strictly forward from the reading being measured, so no
    later knowledge can leak into an earlier case.
    """
    result = LevelOutcomes(gap=current_gap)
    if session is None or current_gap is None:
        return result
    if now is None:
        now = datetime.utcnow()

    try:
        series = _settled_series(session, now, window_days)
    except Exception as e:
        print(f"Level outcomes query failed: {e}")
        return result
    if len(series) < MIN_OBSERVATIONS:
        result.cases = len(series)
        return result

    values = [item[2] for item in series]
    spread = _spread(values)
    if not spread:
        return result

    band = spread * COMPARABLE_BAND_FRACTION
    low, high = current_gap - band, current_gap + band
    result.band_low, result.band_high = low, high

    horizon = timedelta(hours=horizon_hours)
    tolerance = timedelta(hours=HORIZON_TOLERANCE_HOURS)
    moves: List[float] = []
    for index, (timestamp, _, gap) in enumerate(series):
        if not (low <= gap <= high):
            continue
        target = timestamp + horizon
        best, best_distance = None, None
        for later_timestamp, _, later_gap in series[index + 1:]:
            if later_timestamp > target + tolerance:
                break
            distance = abs(later_timestamp - target)
            if distance <= tolerance and (best_distance is None or distance < best_distance):
                best, best_distance = later_gap, distance
        if best is not None:
            # Both sides are signed gaps; the change in the *size* of the discount is
            # the difference of their magnitudes.
            moves.append(abs(best) - abs(gap))

    # An empty band and a thin one are the same answer: the window is fine, it is
    # this *level* the record has nothing near. Returning INSUFFICIENT_DATA for the
    # empty case would blame the history for a gap in the neighbourhood, and the
    # surface would print "not enough history yet" about a 273-reading window.
    result.cases = len(moves)
    if len(moves) < MIN_COMPARABLE_READINGS:
        # The count is still carried so the surface can say how few there were.
        result.status = "TOO_FEW"
        return result

    increased = [m for m in moves if m > UNCHANGED_DEADBAND_PP]
    decreased = [m for m in moves if m < -UNCHANGED_DEADBAND_PP]
    result.increased = len(increased)
    result.decreased = len(decreased)
    result.unchanged = len(moves) - len(increased) - len(decreased)
    result.average_increase_pp = round(sum(increased) / len(increased), 3) if increased else None
    result.average_decrease_pp = round(abs(sum(decreased) / len(decreased)), 3) if decreased else None
    result.average_change_pp = round(sum(moves) / len(moves), 3)
    result.status = "OK"
    return result


# ---------------------------------------------------------------------------
# Section 2 — the last 30 days
# ---------------------------------------------------------------------------

def resolve_distribution(
    session,
    current_gap: Optional[float] = None,
    now: Optional[datetime] = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> Distribution:
    """Range and typical level of the discount over the window.

    `typical` is the median, presented under that name because a median means nothing
    to a reader who has not met one and the word adds no precision they can use.
    """
    result = Distribution()
    if session is None:
        return result
    if now is None:
        now = datetime.utcnow()
    try:
        series = _settled_series(session, now, window_days)
    except Exception as e:
        print(f"Distribution query failed: {e}")
        return result

    result.sample_size = len(series)
    result.coverage_days = len({local_date(item[0]) for item in series})
    if len(series) < MIN_OBSERVATIONS:
        return result

    sizes = sorted(abs(item[2]) for item in series)
    result.low = round(sizes[0], 4)
    result.high = round(sizes[-1], 4)
    result.typical = round(median(sizes), 4)
    result.today = None if current_gap is None else round(abs(current_gap), 4)
    result.status = "OK"
    return result


def _episode_durations(series, threshold):
    """(duration_hours, closed) per deep-zone episode.

    Two corrections to how this used to be measured, both found on 2026-09-22.

    **Every episode counts.** The old code measured `span[-1] - span[0]` and kept only
    spans of more than one reading, so an episode seen in a single reading was not
    recorded as short -- it was dropped. That removed 16 of 26 episodes from the
    statistic the push is justified by.

    **An episode we stopped watching is censored, not closed.** Collection runs 06:00
    to 21:00 local. If the next reading arrives after a gap longer than
    `MAX_EPISODE_GAP_HOURS`, the zone closed at some unobserved moment and all we have
    is a lower bound. Crediting it with the full span to that reading hands it hours
    nobody watched -- the same error `MAX_EPISODE_GAP_HOURS` already prevents when
    *joining* readings into an episode, which is where this rule comes from.

    A closed episode is timed to the **midpoint** between the last reading inside and
    the reading that showed it closed, because the true close lies between the two. A
    single-reading episode therefore gets about half a sampling interval rather than
    zero.

    Measured on 2026-09-22: 26 episodes, 10 observed closes, 16 censored (62%). The
    two old errors pulled in opposite directions and nearly cancelled -- 1.5h printed
    against 1.1h correct -- which is luck rather than correctness, and stops being
    luck as soon as the collection window changes.
    """
    spells = []
    run: List[datetime] = []
    for timestamp, _, gap in series:
        if abs(gap) >= threshold:
            if run and (timestamp - run[-1]).total_seconds() / 3600.0 > MAX_EPISODE_GAP_HOURS:
                spells.append(((run[-1] - run[0]).total_seconds() / 3600.0, False))
                run = []
            run.append(timestamp)
            continue
        if not run:
            continue
        unobserved = (timestamp - run[-1]).total_seconds() / 3600.0
        if unobserved > MAX_EPISODE_GAP_HOURS:
            spells.append(((run[-1] - run[0]).total_seconds() / 3600.0, False))
        else:
            midpoint = run[-1] + (timestamp - run[-1]) / 2
            spells.append(((midpoint - run[0]).total_seconds() / 3600.0, True))
        run = []
    if run:
        spells.append(((run[-1] - run[0]).total_seconds() / 3600.0, False))
    return spells


def _median_survival(spells):
    """Kaplan-Meier median: the first duration at which half of episodes have closed.

    A plain median over the durations would treat a censored episode as a completed
    one. With 62% of episodes censored that is not a rounding issue, it is a different
    quantity.

    Returns None when the curve never reaches half, which is the honest answer: more
    than half of the episodes were still open when we stopped looking.
    """
    if not spells:
        return None
    at_risk = len(spells)
    survival = 1.0
    for duration in sorted({d for d, _ in spells}):
        closed = sum(1 for d, c in spells if d == duration and c)
        censored = sum(1 for d, c in spells if d == duration and not c)
        if at_risk > 0 and closed:
            survival *= (1 - closed / at_risk)
        if survival <= 0.5:
            return round(duration, 1)
        at_risk -= (closed + censored)
    return None


def resolve_deep_zone(
    session,
    current_gap: Optional[float] = None,
    now: Optional[datetime] = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    percentile: int = DEEP_ZONE_PERCENTILE,
) -> DeepZone:
    """How often the deep zone opens, and for how long.

    An episode is a run of consecutive readings at or beyond the threshold, so a
    measured duration is bounded by how often readings are taken. The number that
    matters to a reader is the typical one: a zone that closes inside a few hours
    cannot be caught by looking when you happen to remember.
    """
    result = DeepZone()
    if session is None:
        return result
    if now is None:
        now = datetime.utcnow()
    try:
        series = _settled_series(session, now, window_days)
    except Exception as e:
        print(f"Deep zone query failed: {e}")
        return result
    if len(series) < MIN_OBSERVATIONS:
        return result

    threshold = (deep_discount_threshold(series)
                 if percentile == DEEP_DISCOUNT_PERCENTILE
                 else _percentile(sorted(abs(item[2]) for item in series), percentile))
    if threshold is None:
        return result
    result.threshold = threshold

    spells = _episode_durations(series, threshold)
    result.episodes = len(spells)
    result.typical_hours = _median_survival(spells)
    observed = [duration for duration, _ in spells]
    result.longest_hours = round(max(observed), 1) if observed else None
    result.censored = sum(1 for _, closed in spells if not closed)
    result.inside_now = current_gap is not None and abs(current_gap) >= threshold
    result.status = "OK"
    return result


# ---------------------------------------------------------------------------
# Section 3 — price movement
# ---------------------------------------------------------------------------

def resolve_price_movement(
    session,
    now: Optional[datetime] = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    sharp_percentile: int = SHARP_MOVE_PERCENTILE,
) -> PriceMovement:
    """How fast the price a buyer actually pays moves, hour to hour.

    Measured on the trimmed basis price rather than the discount: a buyer's exposure
    is to what they pay, and the discount can move while the price does not.

    Both directions are reported without comment. A sharp fall is an opportunity to
    one reader and a reason to sell to another; the message reports the movement and
    leaves the conclusion where it belongs.
    """
    result = PriceMovement()
    if session is None:
        return result
    if now is None:
        now = datetime.utcnow()

    from database.models import MarketSnapshot, PlatformPrice
    from collections import defaultdict

    try:
        reference_end = to_utc(datetime.combine(local_date(now), datetime.min.time()))
        rows = (
            session.query(
                MarketSnapshot.id,
                MarketSnapshot.timestamp,
                MarketSnapshot.collection_mode,
                PlatformPrice.price_irr,
            )
            .join(PlatformPrice, PlatformPrice.snapshot_id == MarketSnapshot.id)
            .filter(
                PlatformPrice.price_irr.isnot(None),
                MarketSnapshot.timestamp >= reference_end - timedelta(days=window_days),
                MarketSnapshot.timestamp < reference_end,
                MarketSnapshot.collection_mode != "user",
            )
            .all()
        )
    except Exception as e:
        print(f"Price movement query failed: {e}")
        return result

    grouped = defaultdict(lambda: {"prices": []})
    for snapshot_id, timestamp, _mode, price in rows:
        grouped[snapshot_id]["timestamp"] = timestamp
        grouped[snapshot_id]["prices"].append(float(price))

    prices = []
    for entry in grouped.values():
        basis = cheap_basis_price(entry["prices"])
        if basis:
            prices.append((entry["timestamp"], basis))
    prices.sort()

    moves: List[Tuple[datetime, float]] = []
    for index in range(1, len(prices)):
        hours = (prices[index][0] - prices[index - 1][0]).total_seconds() / 3600.0
        if 0 < hours <= MAX_STEP_HOURS and prices[index - 1][1]:
            change = (prices[index][1] - prices[index - 1][1]) / prices[index - 1][1] * 100
            moves.append((prices[index][0], change))

    result.sample_size = len(moves)
    if len(moves) < MIN_OBSERVATIONS:
        return result

    sizes = sorted(abs(change) for _, change in moves)
    result.typical_move_percent = round(_percentile(sizes, 50), 4)
    sharp = _percentile(sizes, sharp_percentile)
    result.sharp_move_percent = round(sharp, 4)
    sharp_moves = [(t, c) for t, c in moves if abs(c) >= sharp]
    result.sharp_count = len(sharp_moves)
    if sharp_moves:
        result.last_sharp_at, result.last_sharp_percent = sharp_moves[-1]
        result.last_sharp_percent = round(result.last_sharp_percent, 4)
    result.status = "OK"
    return result


# ---------------------------------------------------------------------------
# Section 4 — what this rests on
# ---------------------------------------------------------------------------

def resolve_data_health(session, now: Optional[datetime] = None,
                        window_days: int = DEFAULT_WINDOW_DAYS) -> DataHealth:
    """Sample size, sampling quality and how much of the record has resolved."""
    result = DataHealth()
    if session is None:
        return result
    if now is None:
        now = datetime.utcnow()

    from analysis.bubble_position import (
        MIN_SCHEDULED_COVERAGE_DAYS, MIN_SCHEDULED_READINGS)
    from database.models import MarketState, OutcomeEvaluation

    try:
        series = _settled_series(session, now, window_days)
        result.readings = len(series)
        result.coverage_days = len({local_date(item[0]) for item in series})

        scheduled = [item for item in series if item[1] == "scheduled"]
        scheduled_days = sorted({local_date(item[0]) for item in scheduled})
        clean = (len(scheduled) >= MIN_SCHEDULED_READINGS
                 and len(scheduled_days) >= MIN_SCHEDULED_COVERAGE_DAYS)
        result.sampling = "SCHEDULED" if clean else "MIXED"
        if not clean and scheduled_days:
            # The gate clears once the span reaches its minimum; project from the
            # days already banked rather than printing a hand-typed date.
            #
            # The +1 is the settled window. `scheduled_days[-1] + remaining` is the
            # day the last missing day gets *banked*, and the window excludes the
            # current day, so the gate opens on the day after that. Measured
            # 2026-09-21: 7 days banked, 09-14 to 09-20, the fourteenth lands on
            # 09-27, and the first reading judged against fourteen settled scheduled
            # days is on 09-28. The message read 09-27.
            remaining = MIN_SCHEDULED_COVERAGE_DAYS - len(scheduled_days)
            result.clean_from = (
                scheduled_days[-1] + timedelta(days=remaining + 1)).isoformat()

        result.outcomes_total = session.query(OutcomeEvaluation).count()
        result.outcomes_resolved = session.query(OutcomeEvaluation).filter(
            OutcomeEvaluation.outcome_status == "COMPLETE").count()
        result.decisions_total = session.query(MarketState).count()
        result.decisions_non_wait = session.query(MarketState).filter(
            MarketState.final_decision != "WAIT").count()
    except Exception as e:
        print(f"Data health query failed: {e}")
    return result


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def build_analyze_report(session, markets=None, fair_price=None,
                         now: Optional[datetime] = None,
                         window_days: int = DEFAULT_WINDOW_DAYS) -> AnalyzeReport:
    """Assemble the report. Reads only; writes nothing.

    `markets` and `fair_price` supply the current reading when the caller has one.
    Without them the most recent settled reading is used, which is what a user
    pressing Analyze gets: the state as last observed, not a fresh collection.
    """
    report = AnalyzeReport(generated_at=now or datetime.utcnow())
    if session is None:
        return report
    if now is None:
        now = datetime.utcnow()

    current_gap = None
    if markets and fair_price:
        prices = [
            float(info["price"]) for info in markets.values()
            if info.get("status") == "OK" and info.get("price") is not None
        ]
        current_gap = signed_gap(cheap_basis_price(prices), fair_price)
    if current_gap is None:
        try:
            recent = basis_series(session, now - timedelta(days=2), now)
            if recent:
                current_gap = recent[-1][2]
        except Exception as e:
            print(f"Current gap lookup failed: {e}")

    report.level = resolve_level_outcomes(session, current_gap, now=now, window_days=window_days)
    report.distribution = resolve_distribution(session, current_gap, now=now, window_days=window_days)
    report.deep_zone = resolve_deep_zone(session, current_gap, now=now, window_days=window_days)
    report.movement = resolve_price_movement(session, now=now, window_days=window_days)
    report.health = resolve_data_health(session, now=now, window_days=window_days)

    if report.distribution.status == "OK":
        report.status = "OK"
    return report
