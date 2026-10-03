"""Direction: where 18K's trend stands, its levels, and what followed similar moments.

SP-D's first deliverable (owner, 2026-10-03: "if I know the up trend, I will transform my
rial into gold and maintain my money value"). The question it answers is not BUY/SELL
but "convert now, or wait for a better entry?", with the evidence for each part.

Source: tgju's daily 18K candles (`market_daily_candles`, 13 years), which track our
platforms at 0.95 daily correlation (SP_C_HANDOFF.md section 41).

Every figure is a count over history, and **causal**: judging day i uses only days whose
outcome was known by day i (a 20-day outcome of day j is known from j + 20). Nothing
here is a decision: it is EVIDENCE for the reader, and has no BUY/SELL authority
(CLAUDE.md invariants) until it has been validated as one.

In toman, 18K rises on most days simply because the rial loses value: higher 20 trading
days later on about two days in three since 2014. That base rate is reported beside
every conditional figure, because the information is in how far a situation moves the
odds away from it, not in the odds themselves.
"""

from dataclasses import dataclass, field
from datetime import date
from statistics import median
from typing import Dict, List, Optional

from caluclator.technical import (moving_averages, rsi, split_levels, stretch_pct,
                                  swing_levels, trend_state)

INSTRUMENT = "TGJU_GOLD_18K"
HORIZONS = (5, 20, 60)
# Distance from the 50-day average, in percent. Measured over 2014-2026: 82% of days
# 10-15% above it were higher 20 days later, but only 65% of days 15%+ above it, and
# 47% of those fell 5% or more on the way (SP_C_HANDOFF.md section 46).
STRETCH_BANDS = ((None, 0.0), (0.0, 5.0), (5.0, 10.0), (10.0, 15.0), (15.0, None))
PULLBACK_PCT = 5.0
DIP_PCTS = (2.0, 3.0, 5.0)
ENTRY_WINDOW = 20
MIN_CASES = 30            # fewer similar cases than this: the condition is widened
MIN_HISTORY_DAYS = 260    # a 200-day average plus a year of swings


@dataclass
class Odds:
    horizon: int
    cases: int = 0
    episodes: int = 0
    higher_pct: Optional[float] = None
    median_move_pct: Optional[float] = None
    pullback_pct: Optional[float] = None


@dataclass
class EntryOption:
    """Waiting up to ENTRY_WINDOW days for a dip of `dip_pct`, else converting then."""
    dip_pct: float
    cases: int = 0
    reached_pct: Optional[float] = None
    mean_saving_pct: Optional[float] = None    # positive: waiting paid less on average


@dataclass
class Level:
    price: float
    distance_pct: float
    touches: int
    last: date


@dataclass
class DirectionView:
    status: str = "INSUFFICIENT_DATA"
    as_of: Optional[date] = None
    close: Optional[float] = None
    averages: Dict[int, Optional[float]] = field(default_factory=dict)
    trend: Optional[str] = None
    stretch_pct: Optional[float] = None
    rsi: Optional[float] = None
    supports: List[Level] = field(default_factory=list)
    resistances: List[Level] = field(default_factory=list)
    condition: Optional[str] = None
    odds: Dict[int, Odds] = field(default_factory=dict)
    baseline: Dict[int, Odds] = field(default_factory=dict)
    entry: List[EntryOption] = field(default_factory=list)
    history_days: int = 0


def stretch_band(value):
    if value is None:
        return None
    for low, high in STRETCH_BANDS:
        if (low is None or value >= low) and (high is None or value < high):
            return (low, high)
    return None


def band_words(band):
    low, high = band
    if low is None:
        return "below the 50-day average"
    if high is None:
        return f"{low:.0f}% or more above the 50-day average"
    return f"{low:.0f}-{high:.0f}% above the 50-day average"


def _episodes(cases, gap):
    count, last = 0, None
    for j in cases:
        if last is None or j - last > gap:
            count += 1
        last = j
    return count


def measure_odds(close, cases, horizon):
    """Odds over `cases` (indices whose `horizon`-day outcome is known)."""
    odds = Odds(horizon=horizon, cases=len(cases), episodes=_episodes(cases, horizon))
    if not cases:
        return odds
    moves = [(close[j + horizon] / close[j] - 1) * 100 for j in cases]
    falls = [(min(close[j + 1:j + horizon + 1]) / close[j] - 1) * 100 for j in cases]
    odds.higher_pct = sum(m > 0 for m in moves) / len(moves) * 100
    odds.median_move_pct = median(moves)
    odds.pullback_pct = sum(f <= -PULLBACK_PCT for f in falls) / len(falls) * 100
    return odds


def measure_entry(close, cases, dip_pct, window=ENTRY_WINDOW):
    """What waiting for a `dip_pct` dip (else converting at day `window`) paid, against
    converting at once. A dip is reached when a close is at or below the target; the
    price paid is then the target itself, the price a standing order would get."""
    option = EntryOption(dip_pct=dip_pct, cases=len(cases))
    if not cases:
        return option
    reached, paid = 0, []
    for j in cases:
        target = close[j] * (1 - dip_pct / 100)
        if any(close[k] <= target for k in range(j + 1, j + window + 1)):
            reached += 1
            paid.append(-dip_pct)
        else:
            paid.append((close[j + window] / close[j] - 1) * 100)
    option.reached_pct = reached / len(cases) * 100
    option.mean_saving_pct = -sum(paid) / len(paid)
    return option


def build_view(dates, high, low, close, usable=None, i=None):
    """The Direction view at day `i` (default: the last), from the series up to it."""
    n = len(close)
    i = n - 1 if i is None else i
    view = DirectionView(history_days=i + 1)
    if i + 1 < MIN_HISTORY_DAYS:
        return view
    averages = moving_averages(close[:i + 1])
    view.trend = trend_state(close, averages, i)
    if view.trend is None:
        return view
    view.status = "OK"
    view.as_of, view.close = dates[i], float(close[i])
    view.averages = {p: float(a[i]) for p, a in averages.items()}
    view.stretch_pct = stretch_pct(close, averages, i)
    r = rsi(close[:i + 1])[i]
    view.rsi = None if r != r else float(r)

    levels = swing_levels(high, low, upto=i, usable=usable)
    supports, resistances = split_levels(levels, close[i])
    as_level = lambda lv: Level(lv["price"], (lv["price"] / close[i] - 1) * 100, lv["touches"], dates[lv["last"]])
    view.supports = [as_level(lv) for lv in supports[:3]]
    view.resistances = [as_level(lv) for lv in resistances[:3]]

    # every earlier day's own state, computed from the same causal averages
    states = [trend_state(close, averages, j) for j in range(i + 1)]
    bands = [stretch_band(stretch_pct(close, averages, j)) for j in range(i + 1)]
    band_now = stretch_band(view.stretch_pct)
    known = lambda h: [j for j in range(i - h + 1) if states[j] is not None]

    def similar(h, widen=False):
        return [j for j in known(h) if states[j] == view.trend and (widen or bands[j] == band_now)]

    widen = len(similar(max(HORIZONS))) < MIN_CASES
    view.condition = view.trend.lower() if widen else f"{view.trend.lower()}, {band_words(band_now)}"
    for h in HORIZONS:
        view.odds[h] = measure_odds(close, similar(h, widen), h)
        view.baseline[h] = measure_odds(close, known(h), h)
    view.entry = [measure_entry(close, similar(ENTRY_WINDOW, widen), d) for d in DIP_PCTS]
    return view


def load_series(session, instrument=INSTRUMENT):
    """(dates, high, low, close, usable) from market_daily_candles, oldest first."""
    from database.models import MarketDailyCandle
    rows = (session.query(MarketDailyCandle.trade_date, MarketDailyCandle.open, MarketDailyCandle.high,
                          MarketDailyCandle.low, MarketDailyCandle.close, MarketDailyCandle.source_quality)
            .filter(MarketDailyCandle.instrument == instrument)
            .order_by(MarketDailyCandle.trade_date.asc()).all())
    dates = [r[0] for r in rows]
    o, h, l, c = ([float(r[k]) for r in rows] for k in (1, 2, 3, 4))
    usable = [r[5] == "COMPLETE" and not (r[1] == r[2] == r[3] == r[4]) for r in rows]
    return dates, h, l, c, usable


def resolve_direction(session):
    """The current view, or INSUFFICIENT_DATA. Never raises."""
    try:
        dates, high, low, close, usable = load_series(session)
        if len(close) < MIN_HISTORY_DAYS:
            return DirectionView(history_days=len(close))
        return build_view(dates, high, low, close, usable)
    except Exception as e:
        print(f"Direction unavailable: {e}")
        return DirectionView()
