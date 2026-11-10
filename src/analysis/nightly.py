"""The nightly message, computed (SP_D_HANDOFF.md sections 102.1, 105.4, 106.3 and 109): every number it prints that
the LENS does not. alerts/telegram_nightly.py only formats it. No clock, no network, no database here: main reads
them and passes them in.

- **The 3-day line.** The base is the 18K figure of the message's own NOW line. Its low edge is the 3-day range's
  (98.3): -1.11 x the calm model's daily volatility x the root of 3. The chance of a higher close comes from the record by the
  latest finished fund week's ticket-size zone (102.1), the way it was measured.
- **The funds' week,** Saturday to Wednesday: money, buyers and each side's ticket from TSETMC's individuals. The zone
  is the week's power (the buyers' ticket over the sellers') ranked in the 52 weeks before: registered in 89ae9f5 for
  the forward test (98.2). From a week's third session the funds' line gives the record's rates by zone (100.3).
  Those rates count a daily close at the level within 7 days of the week's last session.
- **The record:** what the 21:00 message showed is written down before its outcome, and judged on the same NOW line.
"""

import math
import statistics as st
from datetime import timedelta

VERSION = "v1"
HORIZON_NIGHTS = 3
Q_LOW, Q_HIGH = -1.11, 1.89               # the 3-day range's edges, in units of the calm daily volatility x root 3
CHANCE_ABOVE_FLOOR = 90                   # the low edge holds 9 days in 10 by construction (102.1)
CHANCE_HIGHER = {"SELLERS": 58, "BUYERS": 61, "CROWDED": 57, None: 60}    # 3-day close higher, 2,341 days (102.1)
# Ended the next week lower, and the record's chance of reaching the level the line names (100.3)
WEEK_RECORD = {"SELLERS": (46, "drop", 25), "BUYERS": (29, "rise", 30), "CROWDED": (42, "drop", 23)}
TYPICAL_LOWER = 38                        # every week (100.3)
TRAIL, MIN_TRAIL = 52, 26                 # the weeks a week's power is ranked in, as research/rd_fund_week_classes.py
MIN_SESSIONS = 3                          # the zones were registered on weeks of 3 sessions or more (98.2, 105.4)
SELLERS_BELOW, BUYERS_BELOW = 40, 80      # the zones' ranks (98.2)
USUAL_LOW, USUAL_HIGH = 20, 80            # the buyers' count against the same sessions of the past year
FRIDAY = 4
SATURDAY = 5
FUND_DAYS = (5, 6, 0, 1, 2)               # Saturday to Wednesday, in date.weekday()


def trading_nights_after(day, nights):
    """The Tehran day `nights` trading nights after `day`: Friday does not count (106.3)."""
    while nights:
        day += timedelta(days=1)
        if day.weekday() != FRIDAY:
            nights -= 1
    return day


def three_day_line(base, sigma, zone):
    """The line's numbers, or None without a base or the day's volatility. Unrounded: rounded at render."""
    if not base or not sigma:
        return None
    root = math.sqrt(3)
    floor, high = base * math.exp(Q_LOW * sigma * root), base * math.exp(Q_HIGH * sigma * root)
    return {"base": base, "sigma": sigma, "zone": zone, "chance_higher": CHANCE_HIGHER[zone],
            "chance_above": CHANCE_ABOVE_FLOOR, "floor": floor, "floor_pct": (floor / base - 1) * 100,
            "high": high, "high_pct": (high / base - 1) * 100}


def week_of(day):
    """The Saturday that opens `day`'s fund week."""
    return day - timedelta(days=(day.weekday() - SATURDAY) % 7)


def _stats(flows, days):
    bv, bc, sv, sc = (sum(flows[d][k] for d in days) for k in range(4))
    if not (bv and bc and sv and sc):
        return None
    return {"net": bv - sv, "buyers": bc / len(days), "buy_head": bv / bc, "sell_head": sv / sc,
            "power": (bv / bc) / (sv / sc)}


def _rank(history, value):
    values = [x for x in history if x is not None and math.isfinite(x)]
    return 100 * sum(x < value for x in values) / len(values) if len(values) >= MIN_TRAIL and value is not None else None


def _zone(rank):
    return None if rank is None else "SELLERS" if rank < SELLERS_BELOW else "BUYERS" if rank < BUYERS_BELOW else "CROWDED"


def _buyers_word(rank):
    return None if rank is None else "more than usual" if rank >= USUAL_HIGH else "fewer than usual" if rank <= USUAL_LOW else "as usual"


def funds_view(flows, today):
    """The funds' block. `flows`: {day: [buy value, buy count, sell value, sell count]} of the individuals. None
    when no week can be read."""
    weeks = {}
    for day in sorted(d for d in flows or () if d <= today):
        weeks.setdefault(week_of(day), []).append(day)
    if not weeks:
        return None
    this_key = week_of(today)
    counted = [w for w in sorted(weeks) if len(weeks[w]) >= MIN_SESSIONS and _stats(flows, weeks[w])]
    past = [w for w in counted if w < this_key]
    if not past:
        return None

    def power_rank(days, before):
        return _rank([_stats(flows, weeks[w])["power"] for w in before[-TRAIL:]], _stats(flows, days)["power"])

    last = past[-1]
    last_zone = _zone(power_rank(weeks[last], past[:-1]))
    history = past[-TRAIL:]
    view = {"last_week": (weeks[last][0], weeks[last][-1]), "last_zone": last_zone, "chance_zone": last_zone,
            "today_missing": today.weekday() in FUND_DAYS and today not in weeks.get(this_key, ()),
            "today": today, "finished": today.weekday() not in FUND_DAYS, "sessions": [], "n": 0, "zone": None}
    sessions = weeks.get(this_key, [])
    now = _stats(flows, sessions) if sessions else None
    if now is None:
        return view
    n = len(sessions)
    first = [_stats(flows, weeks[w][:n]) for w in history]
    first = [s for s in first if s]
    view.update(now)
    view.update({"sessions": sessions, "n": n,
                 "usual_net": st.mean(s["net"] for s in first) if first else None,
                 "buyers_word": _buyers_word(_rank([s["buyers"] for s in first], now["buyers"]))})
    if n >= MIN_SESSIONS:
        view["zone"] = _zone(power_rank(sessions, past))
        if view["finished"]:            # the record's 3-day chance reads the last fund week that has ended (102.1)
            view["chance_zone"] = view["zone"]
    return view


def funds_line(funds, three):
    """The line of a week from its third session, or None: the zone's rates, at the 3-day line's own edges."""
    if not funds or not funds.get("zone") or not three:
        return None
    lower, side, chance = WEEK_RECORD[funds["zone"]]
    level, pct = (three["floor"], three["floor_pct"]) if side == "drop" else (three["high"], three["high_pct"])
    return {"zone": funds["zone"], "lower": lower, "typical_lower": TYPICAL_LOWER, "side": side, "chance": chance,
            "level": level, "level_pct": pct, "base": three["base"]}


def forecast_rows(day, view, recorded_at):
    """The rows the 21:00 message commits to, each ready for repository.save_nightly_forecast."""
    three = view.get("three_day")
    if not three:
        return []
    common = {"local_date": day, "version": VERSION, "recorded_at": recorded_at, "base_price": three["base"]}
    rows = [dict(common, forecaster="three_day", due_date=trading_nights_after(day, HORIZON_NIGHTS),
                 forecast={k: three[k] for k in ("chance_higher", "chance_above", "floor", "high", "sigma", "zone")})]
    line = view.get("funds_line")
    if line:
        funds = view["funds"]
        last_session = funds["sessions"][-1]
        rows.append(dict(common, forecaster="funds_week", due_date=last_session + timedelta(days=7),
                         forecast={"zone": line["zone"], "lower": line["lower"], "side": line["side"], "chance": line["chance"],
                                   "level": line["level"], "n": funds["n"], "week": week_of(last_session).isoformat()}))
    return rows


def score(forecaster, base, forecast, price, nights):
    """A due forecast's outcome. `price`: tonight's NOW line; `nights`: {day: the NOW line} from the day after the
    forecast through tonight. Counted on the nightly figures alone, so one series stands at both ends."""
    base = float(base)
    out = {"price": price, "change_pct": (price / base - 1) * 100, "nights": len(nights)}
    if forecaster == "three_day":
        out.update(higher=price > base, above_floor=price > forecast["floor"])
    elif forecaster == "funds_week":
        seen = list(nights.values()) or [price]
        out.update(lower=price < base, reached=min(seen) <= forecast["level"] if forecast["side"] == "drop"
                   else max(seen) >= forecast["level"])
    return out
