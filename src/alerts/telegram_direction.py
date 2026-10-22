"""DIRECTION (SP-D): the /Direction message, rendered from a stored panel.

v7, the revamp the owner agreed on 2026-10-15 (SP_D_HANDOFF.md sections 35.8-35.11). Read on a
phone by someone deciding when to turn rial into gold. Each section answers one question, in plain
words, and shows only what has a measured record:

  TREND           how far this leg has gone and what carried it; the EMA distances against yesterday
  BUY NOW OR WAIT has waiting for a dip paid on days like today
  LEVELS          the nearest lines, with what lines that far away did (the chart's own lines did no
                  better than that, section 15)
  WATCH           where the uptrend would end, and whether that is near
  GOLD DEMAND     the gold funds' last 7 days, each reading against the past year; no forecast
  DOLLAR FROM NEWS  left out until its measurement holds (section 35.9)

Dropped from v6: the analyst's label (the same on every panel), "higher a month later", the
drop chance, the range, the new-high chance, the rally-age lines, the track-record line. Only <b>
and <i>; no bare "<", ">" or "&" (Telegram's HTML parser rejects them). No BUY or SELL: the
system's decision keeps its authority in UPDATE.
"""

from datetime import date, datetime

from alerts.helpers import format_m_tomans_short, to_tehran
from alerts.telegram import _send
from analysis.direction import DIP_PCT, DOLLAR_SHARE
from timeutil import local_now, persian_day

NEAR_PCT = 3.0              # a watched line this close is "close", not "far away"
DEMAND_MAX_AGE_DAYS = 7     # older gold-fund days leave the section out


def _m(price):
    return format_m_tomans_short(price)


def _pct(value, decimals=0):
    return f"{abs(value):.{decimals}f}%"


def _signed(value, decimals=0):
    return f"{value:+.{decimals}f}%".replace("-", "−")


def _local(iso):
    return to_tehran(datetime.fromisoformat(iso)) if iso else None


def _day(iso, year=False):
    return persian_day(date.fromisoformat(iso[:10]), year=year)


def _side(value):
    return "above" if value >= 0 else "below"


def _head(p):
    pos, r = p.position, p.rally
    words = [f"18K <b>{_m(p.price)}</b>"]
    trend = pos.get("trend")
    if trend == "UPTREND" and r.get("trend_since"):
        words.append(f"uptrend since {_day(r['trend_since'], year=True)}")
    elif trend == "DOWNTREND":
        words.append("downtrend")
    else:
        words.append("no clear trend")
    usd, xau = r.get("usd_since_start"), r.get("xau_since_start")
    if r.get("in_rally") and usd is not None and r.get("gain_pct", 0) > 0:
        if usd >= DOLLAR_SHARE * r["gain_pct"]:
            words.append("driven by the dollar")
        elif xau is not None and xau >= DOLLAR_SHARE * r["gain_pct"]:
            words.append("driven by world gold")
    return " · ".join(words)


def _trend(p):
    r, pos = p.rally, p.position
    lines = ["<b>TREND</b>"]
    if r.get("in_rally"):
        usd, xau = r.get("usd_since_start"), r.get("xau_since_start")
        drivers = (f"dollar {_signed(usd)}, world gold {_signed(xau)}" if usd is not None and xau is not None
                   else f"dollar {_signed(usd)}; world gold: not available" if usd is not None else "")
        lines.append(f"This leg {_signed(r['gain_pct'])} since {_day(r['start_date'])}" + (f": {drivers}" if drivers else ""))
    else:
        lines.append(f"In a correction: {_signed((p.price / r['record_high'] - 1) * 100)} from the "
                     f"{_m(r['record_high'])} record")
    d, prev = pos["dist"], pos.get("dist_prev") or {}

    def dist(key, label):
        now, was = d[key], prev.get(key)
        text = f"{_pct(now, 1)} {_side(now)} the {label}"
        if was is not None:
            text += f" (was {_pct(was, 1)}{'' if _side(was) == _side(now) else ' ' + _side(was)})"
        return text
    lines.append(f"{dist('EMA20', '20-day')}, {dist('EMA50', '50-day')}")
    ema = pos.get("ema") or {}
    if ema.get("since_date"):
        lines.append(f"20-day {_pct(ema['gap_pct'], 1)} {_side(ema['gap_pct'])} the 50-day: "
                     f"{'bullish' if ema['above'] else 'bearish'} since {_day(ema['since_date'])}")
    return "\n".join(lines)


def _buy_or_wait(p):
    cv = p.convert or {}
    if cv.get("dip_came_pct") is None or cv.get("wait_cost_pct") is None:
        return None
    cost, years, costlier = cv["wait_cost_pct"], cv.get("years"), cv.get("years_costlier")
    lines = ["<b>BUY NOW OR WAIT</b>",
             f"Waiting for a {DIP_PCT:.0f}% drop: on days like today it came {cv['dip_came_pct']:.0f} in 100;"]
    if cost > 0:
        tail = f"; waiting cost more in {costlier} of {years} years" if years else ""
        lines.append(f"buying now was {_pct(cost, 1)} better on average{tail}")
    else:
        tail = f"; waiting cost less in {years - costlier} of {years} years" if years else ""
        lines.append(f"waiting was {_pct(cost, 1)} better on average{tail}")
    return "\n".join(lines)


def _levels(p):
    lv = p.levels or {}
    res, sup = (lv.get("resistances") or [None])[0], (lv.get("supports") or [None])[0]
    if not res and not sup:
        return None
    lines = ["<b>LEVELS</b> (how lines this far away did)"]
    if res and res.get("held_10d_pct") is not None:
        lines.append(f"Resistance {_m(res['price'])} ({_signed(res['pct'], 1)}): broken within 10 days "
                     f"{100 - res['held_10d_pct']:.0f} in 100")
    if sup and sup.get("held_10d_pct") is not None:
        lines.append(f"Support {_m(sup['price'])} ({_signed(sup['pct'], 1)}): held 10 days "
                     f"{sup['held_10d_pct']:.0f} in 100")
    return "\n".join(lines) if len(lines) > 1 else None


def _watch(p):
    pos = p.position
    s50, usd = pos["average"].get("SMA50"), pos.get("usd") or {}
    gold_gap = (s50 / p.price - 1) * 100 if s50 else None                       # negative: the line is below
    usd_gap = (usd["sma50"] / usd["close"] - 1) * 100 if usd.get("sma50") else None
    both_above = gold_gap is not None and gold_gap < 0 and (usd_gap is None or usd_gap < 0)
    lines = ["<b>WATCH</b>" + (" (where the uptrend would end)" if both_above else "")]
    if gold_gap is not None:
        lines.append(f"18K: a close under {_m(s50)}, its 50-day average ({_pct(gold_gap)} below today)" if gold_gap < 0
                     else f"18K: under its 50-day average, {_m(s50)} ({_pct(gold_gap)} above today)")
    if usd_gap is not None:
        lines.append(f"Dollar: a close under {usd['sma50'] / 10:,.0f} toman, its 50-day average "
                     f"({_pct(usd_gap)} below today)" if usd_gap < 0
                     else f"Dollar: under its 50-day average, {usd['sma50'] / 10:,.0f} toman")
    # by separate breaks, 2014-2026: 18K's next 20 trading days trailed all days by 1.2-5.9 points;
    # it usually did not fall (SP_D_HANDOFF.md section 35.11)
    lines.append("After past breaks, 18K's next month was weaker than usual, by 1 to 6 points.")
    gaps = [g for g in (gold_gap, usd_gap) if g is not None]
    if any(g >= 0 for g in gaps):
        lines.append("Today: a line is broken.")
    elif any(-g <= NEAR_PCT for g in gaps):
        lines.append("Today: close to a line, within 3%.")
    elif gaps:
        lines.append("Today: both far away, no warning." if len(gaps) == 2 else "Today: far away, no warning.")
    return "\n".join(lines)


def _demand(p):
    dm = p.demand or {}
    if not dm.get("as_of") or not all(dm.get(k, {}).get("state") for k in ("money", "people", "size")):
        return None
    computed = _local(p.computed_at)
    if computed and (computed.date() - date.fromisoformat(dm["as_of"])).days > DEMAND_MAX_AGE_DAYS:
        return None
    # tablokhani's 10 sessions stand in for the phone's 7 days while the database is out of reach (section 54)
    span = dm.get("label") or f"7 days to {_day(dm['as_of'])}"
    lines = [f"<b>GOLD DEMAND</b> (gold funds, {span})"]
    net = dm["net_rial"] / 1e10                                                   # billion toman
    money = dm["money"]["state"]
    # the money as times the usual week, the reading and words the evening and the room's report share
    # (alerts/gold_funds.py, SP_D_HANDOFF.md section 47)
    from alerts.gold_funds import usual_phrase
    usual = usual_phrase(dm)
    usual = (f", {usual}" if net >= 0 else f" ({usual})") if usual else ""
    spans = "weeks" if dm.get("window", 7) == 7 else "such spans"
    if money == "HIGH":
        lines.append(f"Money: heavy buying, a net {net:,.0f}B toman in{usual}; more than in 9 of 10 {spans} of the past year.")
    elif money == "LOW":
        lines.append(f"Money: heavy selling, a net {abs(net):,.0f}B toman out{usual}; more than in 9 of 10 {spans} of the past year.")
    else:
        lines.append(f"Money: individuals {'put in' if net >= 0 else 'took out'} a net {abs(net):,.0f}B toman{usual}; "
                     f"normal for the past year.")
    people, n, ratio = dm["people"]["state"], dm["buyers_per_day"], dm["people"]["value"]
    if people == "HIGH":
        lines.append(f"People: a rush, {n:,.0f} a day bought, {ratio:.1f} times the usual number.")
    elif people == "LOW":
        lines.append(f"People: few buyers, {n:,.0f} a day, {ratio:.1f} times the usual number.")
    else:
        lines.append(f"People: {n:,.0f} a day bought, {ratio:.1f} times the usual number; normal.")
    size = dm["size"]["state"]
    if size == "LOW":
        lines.append("Sellers in control: each seller sold far more than each buyer bought; unusual.")
    elif size == "HIGH":
        lines.append("Big buyers: each buyer bought far more than each seller sold; unusual.")
    elif dm["size"]["value"] < 1:
        lines.append("Each seller sold more than each buyer bought; normal.")
    else:
        lines.append("Each buyer bought more than each seller sold; normal.")
    return "\n".join(lines)


def _footer(p):
    local = _local(p.computed_at)
    source = "live prices" if p.price_source == "live" else "tgju's close"
    funds = " · gold funds since 2017" if _demand(p) else ""
    return f"<i>Computed {local:%H:%M} from {source} · tgju since 2014{funds}</i>"


def build_direction_message(panel):
    """Assemble /Direction from a stored panel. Returns the body so it can be rendered
    without sending."""
    title = "<b>GOLDPremium: DIRECTION</b>"
    if panel is None:
        return "\n\n".join([title, "No panel computed yet: the first scheduled run from 06:00 or "
                                   "13:00 computes it."])
    if panel.status != "OK":
        return "\n\n".join([title, "Not enough history yet."])
    local = _local(panel.computed_at)
    when = f"{persian_day(local.date())}, {local:%H:%M}"
    if local.date() != local_now().date():
        when += " ⚠ not today"
    head = "\n".join([f"{title} · {when}", _head(panel)])
    sections = [head, _trend(panel), _buy_or_wait(panel), _levels(panel), _watch(panel), _demand(panel), _footer(panel)]
    return "\n\n".join(s for s in sections if s)


def send_direction(panel):
    _send(build_direction_message(panel))
