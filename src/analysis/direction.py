"""DIRECTION: where 18K's trend stands, measured -- SP-D's first deliverable.

The owner's question (2026-10-03): "if I know the up trend, I will transform my rial into
gold and maintain my money value" -- convert now, or wait? Built only from what passed the
SP-D R&D (SP_C_HANDOFF.md sections 46-49), every part causal and every figure a count over
completed history:

- RALLY     the current 8% leg of the trend, the price that would end it, and the stall
            clock (days without a new high) with what followed at each length. A rally's
            age and size did not time its end (10-16% ended within 20 days at every size
            rank, against 12% for all rally days); the stall clock did (from 20 days
            without a new high, 71% ended on the 2024-2026 holdout);
- POSITION  distances to the 20/50/200-day averages with their rank, defined tags, and
            how such gaps closed (time, and whether the price fell or the average rose);
- STANCE    a fixed analyst rulebook from the signals that passed, with its reasons, the
            triggers that would change it, and what followed its past stances. A stance
            (bullish .. bearish), shown beside the system's own decision; it has no
            BUY/SELL authority (owner's choice (a), 2026-10-03);
- OUTLOOK   the chance of a new high within 20 trading days (the stall clock's band), and
            the volatility-scaled 10/50/90% range of the 20-day move;
- LEVELS    swing supports and resistances, and time-at-price zones near the price;
- CONVERT   what waiting for a 3% dip cost, on days like today, against converting at once.

"Now" is the live platform price when one is given: a provisional close for today, which
tgju's daily candle confirms the next morning. Up/down is not forecast: no tested signal
beat the base rate (section 46.1).
"""

from bisect import bisect_right
from dataclasses import asdict, dataclass, field
from datetime import datetime
from statistics import median
from typing import Dict, List, Optional

import numpy as np

from caluclator.technical import (HIGH_LOOKBACK_DAYS, RALLY_REVERSAL, days_since_high, moving_averages,
                                  rally_legs, rsi, split_levels, swing_levels, time_at_price_zones,
                                  trend_state)
from timeutil import local_date

GOLD, USD = "TGJU_GOLD_18K", "TGJU_USD_IRR"
HORIZON, HORIZON_LONG = 20, 60
STRETCH_PCT = 9.0          # above SMA20: such gaps closed mostly by a fall (68%)
STRONG_ADX = 30.0
STALL_TAG_DAYS = 10        # from 10 days without a new high, one came within 20 days 58% of the time
DOLLAR_SHARE = 0.75        # the dollar's 60-day rise at least 3/4 of gold's
GAP_MAX_WAIT = 120
GAP_BANDS = {"SMA20": ((3, 6), (6, 9), (9, 1e9)), "SMA50": ((5, 10), (10, 15), (15, 1e9))}
ZONE_MAX_PCT = 10.0        # time-at-price zones farther than this are not shown
DIP_PCT = 3.0
MIN_HISTORY_DAYS = 400
QUANTILES = (0.1, 0.5, 0.9)
STALL_BANDS = ((0, 0), (1, 4), (5, 9), (10, 19), (20, 39), (40, 250))
STANCES = ("STRONG BULLISH", "BULLISH", "NEUTRAL", "BEARISH", "STRONG BEARISH")
TGJU_OFFSET_PCT = 0.19     # tgju's close sat a median 0.19% above our platforms (section 41.4)
MODEL_VERSION = "direction-1"


@dataclass
class DirectionPanel:
    status: str = "INSUFFICIENT_DATA"
    model_version: str = MODEL_VERSION
    computed_at: Optional[str] = None
    candle_date: Optional[str] = None
    price: Optional[float] = None
    price_source: Optional[str] = None
    rally: Dict = field(default_factory=dict)
    position: Dict = field(default_factory=dict)
    stance: Dict = field(default_factory=dict)
    outlook: Dict = field(default_factory=dict)
    levels: Dict = field(default_factory=dict)
    convert: Dict = field(default_factory=dict)
    system: Dict = field(default_factory=dict)
    forecasts: List[Dict] = field(default_factory=list)
    record: Dict = field(default_factory=dict)       # the live track record and its alarms

    def to_json(self):
        return asdict(self)

    @classmethod
    def from_json(cls, data):
        return cls(**{k: v for k, v in (data or {}).items() if k in cls.__dataclass_fields__})


# -- helpers ---------------------------------------------------------------------------

def _pct(a, b):
    return float((a / b - 1) * 100)


def _rank(values, value):
    values = np.sort(values[~np.isnan(values)])
    return float(np.searchsorted(values, value) / len(values) * 100) if len(values) else None


def _stance_score(c, s50, s200, since, usd_above, broken, i):
    """(score, reasons) of the fixed rulebook at day i; reasons are keys, worded at render."""
    score, reasons = 0, []
    if c[i] > s50[i] > s200[i] and s50[i] > s50[i - 10]:
        score += 1; reasons.append("trend_up")
    if c[i] < s50[i]:
        score -= 1; reasons.append("below_sma50")
    if since[i] <= 4:
        score += 1; reasons.append("new_highs")
    if since[i] >= 20:
        score -= 1; reasons.append("no_high_20d")
    if usd_above[i] == 1:
        score += 1; reasons.append("usd_above_sma50")
    elif usd_above[i] == 0:
        score -= 1; reasons.append("usd_below_sma50")
    if broken[i]:
        score -= 1; reasons.append("rally_broken")
    return score, reasons


def stance_label(score):
    return ("STRONG BULLISH" if score >= 3 else "BULLISH" if score == 2 else "NEUTRAL" if score >= 0
            else "BEARISH" if score >= -2 else "STRONG BEARISH")


def _waited(close, j, dip_pct=DIP_PCT, window=HORIZON):
    """Price paid by waiting up to `window` days for a `dip_pct` dip (else converting on
    the last day), against converting on day j, in percent: positive = waiting cost more."""
    target = close[j] * (1 - dip_pct / 100)
    if (close[j + 1:j + window + 1] <= target).any():
        return -dip_pct
    return _pct(close[j + window], close[j])


def _completed_legs(direction, start, dates, since_year=2014):
    """[(kind, start_index, end_index)] of the finished ZigZag legs; the open one excluded."""
    legs = []
    for i in range(1, len(direction)):
        if direction[i] != direction[i - 1] and dates[start[i - 1]].year >= since_year:
            legs.append(("rally" if direction[i - 1] == "up" else "correction", int(start[i - 1]), int(start[i])))
    return legs


# -- the panel -------------------------------------------------------------------------

def build_panel(gold, usd, live_price=None, live_at=None, markets=None, system=None, now=None):
    """`gold`/`usd`: (dates, high, low, close) oldest first, completed days only.
    `live_price`: today's platform-based price, used as a provisional close. Every
    historical count uses completed days only."""
    import talib
    now = now or datetime.utcnow()
    panel = DirectionPanel(computed_at=now.isoformat(timespec="seconds"), system=system or {})
    gd, gh, gl, gc = (list(x) for x in gold)
    if len(gc) < MIN_HISTORY_DAYS:
        return panel
    done = len(gc)
    last = done - 1                                  # the last completed candle
    panel.candle_date = str(gd[-1])
    live_day = local_date(live_at) if live_at else None
    if live_price and live_day and live_day > gd[-1]:
        gd.append(live_day); gh.append(float(live_price)); gl.append(float(live_price)); gc.append(float(live_price))
        panel.price_source = "live"
    else:
        panel.price_source = "close"
    c, hgh, low = np.array(gc, float), np.array(gh, float), np.array(gl, float)
    n, i = len(c), len(c) - 1
    panel.price = float(c[i])

    ma = moving_averages(c)
    s20, s50, s200 = ma[20], ma[50], ma[200]
    e20, e50 = talib.EMA(c, 20), talib.EMA(c, 50)
    # range-based indicators from completed candles: the live bar has no range yet
    adx = talib.ADX(hgh[:done], low[:done], c[:done], 14)
    atr = talib.ATR(hgh[:done], low[:done], c[:done], 14)
    r = rsi(c)
    trend = [trend_state(c, ma, j) for j in range(n)]
    up = np.array([t == "UPTREND" for t in trend])
    since = days_since_high(c)
    direction, leg_start = rally_legs(c)
    peak = np.array([c[leg_start[j]:j + 1].max() for j in range(n)])
    broken = np.array([direction[j] == "down" for j in range(n)])

    ud, _, _, uc = usd
    ud = list(ud)
    uc = np.array(uc, float)
    u50 = talib.SMA(uc, 50)
    uidx = [bisect_right(ud, x) - 1 for x in gd]
    usd_above = np.array([float(uc[j] > u50[j]) if j >= 0 and not np.isnan(u50[j]) else np.nan for j in uidx])

    first = next(j for j in range(n) if gd[j].year >= 2014 and trend[j] is not None)
    pool = list(range(first, done - HORIZON))
    fwd = np.full(n, np.nan)
    fwd[:done - HORIZON] = (c[HORIZON:done] / c[:done - HORIZON] - 1) * 100
    record_at = np.array([c[max(0, j - HIGH_LOOKBACK_DAYS + 1):j + 1].max() for j in range(n)])

    # the stall clock as tested (section 49): days in a major uptrend (50-day above the
    # 200-day); "resumed" is a new 52-week closing high within 20 days, "ended" a close 8%
    # or more below that high without one
    major = np.array([not np.isnan(s200[j]) and s50[j] > s200[j] for j in range(n)])

    def follow(j):
        nxt = c[j + 1:j + HORIZON + 1]
        resumed = bool(nxt.max() > record_at[j])
        ended = bool((nxt <= record_at[j] * (1 - RALLY_REVERSAL)).any()) and not resumed
        return resumed, ended

    # RALLY: the leg, its end line, and the stall clock's ladder
    in_rally = direction[i] == "up"
    ladder = []
    for lo, hi in STALL_BANDS:
        cases = [j for j in pool if major[j] and lo <= since[j] <= hi]
        if cases:
            out = [follow(j) for j in cases]
            k = len(cases)
            ladder.append({"band": [lo, hi], "cases": k, "resumed": sum(x[0] for x in out) / k * 100,
                           "ended": sum(x[1] for x in out) / k * 100})
    band = next((b for b in ladder if b["band"][0] <= since[i] <= b["band"][1]), None)
    primary = i
    while primary > 0 and s50[primary - 1] > s200[primary - 1]:
        primary -= 1
    legs = _completed_legs(direction[:done], leg_start[:done], gd)
    rallies = [(b - a, _pct(c[b], c[a])) for kind, a, b in legs if kind == "rally"]
    corrections = [(b - a, _pct(c[b], c[a])) for kind, a, b in legs if kind == "correction"]
    depths = [x[1] for x in corrections]
    rally = {"in_rally": bool(in_rally), "days_since_high": int(since[i]), "record_high": float(record_at[i]),
             "ladder": ladder, "band": band,
             "past": {"rallies": len(rallies),
                      "median_days": float(median(x[0] for x in rallies)) if rallies else None,
                      "median_gain": float(median(x[1] for x in rallies)) if rallies else None,
                      "corrections": len(corrections),
                      "correction_median_days": float(median(x[0] for x in corrections)) if corrections else None,
                      "correction_median_depth": float(median(depths)) if depths else None,
                      # the middle half of past corrections: shallow quarter and deep quarter cut off
                      "correction_depth_shallow": float(np.percentile(depths, 75)) if depths else None,
                      "correction_depth_deep": float(np.percentile(depths, 25)) if depths else None}}
    if in_rally:
        a = int(leg_start[i])
        age, gain = i - a, _pct(c[i], c[a])
        rally.update({
            "number": len({int(leg_start[j]) for j in range(primary, n) if direction[j] == "up"}),
            "trend_since": str(gd[primary]), "start_date": str(gd[a]), "start_price": float(c[a]),
            "age_days": int(age), "gain_pct": gain, "peak": float(peak[i]),
            "end_line": float(peak[i] * (1 - RALLY_REVERSAL)),
            "end_line_pct": _pct(peak[i] * (1 - RALLY_REVERSAL), c[i]),
            "longer_than": int(sum(x[0] < age for x in rallies)),
            "larger_than": int(sum(x[1] < gain for x in rallies))})
    panel.rally = rally

    # POSITION: distances, their rank among uptrend days, tags, and how such gaps closed
    avgs = {"SMA20": s20, "EMA20": e20, "SMA50": s50, "EMA50": e50, "SMA200": s200}
    position = {"average": {k: float(v[i]) for k, v in avgs.items()},
                "dist": {k: _pct(c[i], v[i]) for k, v in avgs.items()},
                "rank": {}, "rsi": float(r[i]), "adx": float(adx[last]),
                "atr_pct": float(atr[last] / c[last] * 100), "trend": trend[i], "gaps": {}}
    for key in ("SMA20", "SMA50", "SMA200"):
        series = (c[:done] / avgs[key][:done] - 1) * 100
        position["rank"][key] = _rank(series[np.flatnonzero(up[:done])], position["dist"][key])
    tags = []
    if since[i] == 0:
        tags.append("RECORD")
    if trend[i] in ("UPTREND", "DOWNTREND") and adx[last] >= STRONG_ADX:
        tags.append("STRONG TREND")
    if position["dist"]["SMA20"] >= STRETCH_PCT:
        tags.append("STRETCHED")
    if since[i] >= STALL_TAG_DAYS:
        tags.append("STALLING")
    if not in_rally:
        tags.append("CORRECTION")
    j60 = uidx[i - 60]
    gold60 = _pct(c[i], c[i - 60])
    usd60 = _pct(uc[uidx[i]], uc[j60]) if j60 >= 0 else None
    if usd60 is not None and gold60 > 0 and usd60 >= DOLLAR_SHARE * gold60:
        tags.append("DOLLAR-DRIVEN")
    position["tags"] = tags
    position["gold60"], position["usd60"] = gold60, usd60
    for key, bands in GAP_BANDS.items():
        s = avgs[key]
        dist = (c / s - 1) * 100
        band_ = next((b for b in bands if b[0] <= position["dist"][key] < b[1]), None)
        if band_ is None:
            continue
        idx = [j for j in range(first, done - GAP_MAX_WAIT) if up[j] and band_[0] <= dist[j] < band_[1]]
        waits, moves = [], []
        for j in idx:
            k = next((k for k in range(j + 1, j + GAP_MAX_WAIT + 1) if c[k] <= s[k]), None)
            if k is not None:
                waits.append(k - j); moves.append(_pct(c[k], c[j]))
        if idx and moves:
            position["gaps"][key] = {
                "band": [band_[0], None if band_[1] > 1e8 else band_[1]], "cases": len(idx),
                "closed_pct": len(waits) / len(idx) * 100, "median_days": float(median(waits)),
                "by_fall_pct": float(np.mean([m < 0 for m in moves]) * 100),
                "median_move_at_touch": float(median(moves))}
    panel.position = position

    # STANCE: the rulebook, its triggers, and what followed it before
    score, reasons = _stance_score(c, s50, s200, since, usd_above, broken, i)
    label = stance_label(score)
    triggers = [{"key": "below_sma50", "price": float(s50[i])}]
    if in_rally:
        triggers.append({"key": "rally_end", "price": float(peak[i] * (1 - RALLY_REVERSAL))})
    if usd_above[i] == 1:
        triggers.append({"key": "usd_below_sma50", "price": float(u50[uidx[i]])})
    elif usd_above[i] == 0:
        triggers.append({"key": "usd_above_sma50", "price": float(u50[uidx[i]])})
    if since[i] <= 4:
        triggers.append({"key": "no_high_days", "days": int(5 - since[i])})
    elif since[i] < 20:
        triggers.append({"key": "no_high_days", "days": int(20 - since[i])})
    # the stance each trigger alone would leave, by the same rulebook
    change = {"below_sma50": -1 - ("trend_up" in reasons), "rally_end": -1,
              "usd_below_sma50": -2, "usd_above_sma50": 2, "no_high_days": -1}
    for t in triggers:
        t["to"] = stance_label(score + change[t["key"]])
    same = [j for j in pool if not np.isnan(usd_above[j])
            and stance_label(_stance_score(c, s50, s200, since, usd_above, broken, j)[0]) == label]
    panel.stance = {"label": label, "score": int(score),
                    "stretched": bool(position["dist"]["SMA20"] >= STRETCH_PCT),
                    "reasons": reasons, "triggers": triggers,
                    "record": {"cases": len(same),
                               "higher_pct": float(np.mean(fwd[same] > 0) * 100) if same else None,
                               "median_move": float(np.median(fwd[same])) if same else None,
                               "all_higher_pct": float(np.mean(fwd[pool] > 0) * 100),
                               "all_median_move": float(np.median(fwd[pool]))}}

    # OUTLOOK: a new high within 20 days (the stall clock's band), and the
    # volatility-scaled range of the 20- and 60-day move
    lr = np.full(n, np.nan)
    lr[1:done] = np.log(c[1:done] / c[:done - 1])
    if panel.price_source == "live":
        lr[i] = np.log(c[i] / c[last])
    sigma = np.array([np.nanstd(lr[max(1, j - 59):j + 1]) if j >= 60 else np.nan for j in range(n)])
    ranges = {}
    for hzn in (HORIZON, HORIZON_LONG):
        y = np.full(n, np.nan)
        y[:done - hzn] = (c[hzn:done] / c[:done - hzn] - 1) * 100
        z = (y / (sigma * np.sqrt(hzn) * 100))[first:]
        zs = z[~np.isnan(z)]
        qs = [float(np.quantile(zs, q) * sigma[i] * np.sqrt(hzn) * 100) for q in QUANTILES]
        ranges[hzn] = {"pct": qs, "price": [float(c[i] * (1 + q / 100)) for q in qs],
                       "daily_vol_pct": float(sigma[i] * 100)}
    base_cases = [j for j in pool if major[j]]
    base_rate = float(np.mean([follow(j)[0] for j in base_cases]) * 100) if base_cases else None
    panel.outlook = {"new_high": {"prob": band["resumed"] if band and major[i] else None, "base": base_rate,
                                  "cases": band["cases"] if band else None, "record": float(record_at[i])},
                     "range20": ranges[HORIZON], "range60": ranges[HORIZON_LONG]}

    # LEVELS: swing supports and resistances; time-at-price zones near the price
    usable = [bool(hgh[j] > low[j] and low[j] <= c[j] <= hgh[j]) for j in range(done)] + [False] * (n - done)
    sup, res = split_levels(swing_levels(hgh, low, upto=i, usable=usable), c[i])
    zones = [z for z in time_at_price_zones(c, upto=i) if abs(_pct(z["price"], c[i])) <= ZONE_MAX_PCT]
    panel.levels = {
        "supports": [{"price": lv["price"], "pct": _pct(lv["price"], c[i]), "touches": lv["touches"]} for lv in sup[:3]],
        "resistances": [{"price": lv["price"], "pct": _pct(lv["price"], c[i]), "touches": lv["touches"]} for lv in res[:2]],
        "zones": [{"price": z["price"], "pct": _pct(z["price"], c[i]), "days": z["days"]} for z in zones[:2]]}

    # CONVERT: waiting for a dip on days like today, against converting at once
    stretched_now = position["dist"]["SMA20"] >= STRETCH_PCT
    similar = [j for j in pool if up[j] == up[i] and ((c[j] / s20[j] - 1) * 100 >= STRETCH_PCT) == stretched_now]
    paid = np.array([_waited(c, j) for j in similar])
    years = {}
    for j in pool:
        years.setdefault(gd[j].year, []).append(_waited(c, j))
    panel.convert = {"dip_pct": DIP_PCT, "similar_days": len(similar),
                     "dip_came_pct": float(np.mean(paid == -DIP_PCT) * 100) if len(paid) else None,
                     "wait_cost_pct": float(paid.mean()) if len(paid) else None,
                     "years": len(years), "years_costlier": int(sum(np.mean(v) > 0 for v in years.values())),
                     "first_year": min(years) if years else None}
    if markets:
        ok = sorted((float(v["price"]), k) for k, v in markets.items() if v.get("status") == "OK" and v.get("price"))
        if len(ok) >= 2:
            panel.convert.update({"cheapest": ok[0][1], "cheapest_price": ok[0][0],
                                  "most_expensive_price": ok[-1][0], "spread_pct": _pct(ok[-1][0], ok[0][0])})

    # the forecasts this panel commits to, resolved later against tgju's candles
    from_date = str(gd[i])
    panel.forecasts = [
        {"key": "new_high_20d", "prob": panel.outlook["new_high"]["prob"], "base": base_rate,
         "record": float(record_at[i]), "from_date": from_date, "horizon": HORIZON},
        {"key": "range_20d", "from_price": float(c[i]), "price": ranges[HORIZON]["price"],
         "from_date": from_date, "horizon": HORIZON},
        {"key": "range_60d", "from_price": float(c[i]), "price": ranges[HORIZON_LONG]["price"],
         "from_date": from_date, "horizon": HORIZON_LONG},
        {"key": "stance_20d", "label": label, "from_price": float(c[i]), "from_date": from_date,
         "horizon": HORIZON, "base": panel.stance["record"]["all_higher_pct"]},
    ]
    panel.status = "OK"
    return panel


def load_series(session, instrument):
    """(dates, high, low, close) of a tgju instrument from market_daily_candles."""
    from database.models import MarketDailyCandle
    rows = (session.query(MarketDailyCandle.trade_date, MarketDailyCandle.high, MarketDailyCandle.low,
                          MarketDailyCandle.close)
            .filter(MarketDailyCandle.source == "tgju", MarketDailyCandle.instrument == instrument)
            .order_by(MarketDailyCandle.trade_date.asc()).all())
    return ([r[0] for r in rows], [float(r[1]) for r in rows], [float(r[2]) for r in rows],
            [float(r[3]) for r in rows])


def live_gold_price(markets, offset_pct=TGJU_OFFSET_PCT):
    """tgju-level price from the platforms: their median, raised by tgju's measured level
    offset, so a provisional close sits where tgju's own close would."""
    prices = sorted(float(v["price"]) for v in (markets or {}).values()
                    if v.get("status") == "OK" and v.get("price"))
    return median(prices) * (1 + offset_pct / 100) if prices else None


def resolve_direction(session, markets=None, system=None, now=None):
    """The current panel from stored candles and the live platforms, or INSUFFICIENT_DATA.
    Never raises."""
    try:
        gold, usd = load_series(session, GOLD), load_series(session, USD)
        if len(gold[0]) < MIN_HISTORY_DAYS or len(usd[0]) < 60:
            return DirectionPanel()
        now = now or datetime.utcnow()
        return build_panel(gold, usd, live_price=live_gold_price(markets), live_at=now,
                           markets=markets, system=system, now=now)
    except Exception as e:
        print(f"Direction unavailable: {e}")
        return DirectionPanel()
