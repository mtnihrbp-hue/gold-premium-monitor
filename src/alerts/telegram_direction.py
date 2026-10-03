"""DIRECTION (SP-D): the /Direction message, rendered from a stored panel.

DRAFT v6, for the owner's review (2026-10-03). Read on a phone, by someone deciding when
to turn rial into gold, so every line answers one of four questions -- is the uptrend
intact, how late and stretched is it, what would change it, has waiting for a drop paid
-- in plain words: percentages, "a month" for 20 trading days, and each warning with
what followed it before. No padded columns (they do not align in a proportional font);
only <b> and <i>, and no bare "<", ">" or "&" (Telegram's HTML parser rejects them).

Same vocabulary as UPDATE and ANALYZE: a discount increases or decreases; a large one is
"heavily discounted", never "cheap"; Cheap/Expensive, never comparatives of "dear". No
BUY or SELL is printed except the system's own decision, which keeps its authority; the
analyst stance is a stance.
"""

from datetime import date, datetime

from alerts.helpers import format_m_tomans_short, format_timestamp, to_tehran
from alerts.telegram import _send
from analysis.direction import DIP_PCT, DOLLAR_SHARE, DROP_PCT, trading_date
from analysis.direction_ledger import GATE_MIN_RESOLVED
from timeutil import local_now

VALUATION_WORDS = {
    "CHEAP": "platforms heavily discounted against fair value",
    "FAIR": "platforms at their usual discount to fair value",
    "EXPENSIVE": "platforms above fair value",
    "UNKNOWN": "not enough history to judge the discount",
}
REASON_WORDS = {
    "trend_up": "uptrend",
    "below_sma50": "below its 50-day average",
    "new_highs": "new record highs",
    "no_high_20d": "no record high for 20+ days",
    "usd_above_sma50": "dollar above its 50-day average",
    "usd_below_sma50": "dollar below its 50-day average",
    "rally_broken": "rally broken",
}


def _m(price):
    return format_m_tomans_short(price)


def _pct(value, decimals=0):
    return f"{abs(value):.{decimals}f}%"


def _signed(value, decimals=0):
    return f"{value:+.{decimals}f}%".replace("-", "−")


def _local(iso):
    return to_tehran(datetime.fromisoformat(iso)) if iso else None


def _view(p):
    s, sysd = p.stance, p.system or {}
    decision = sysd.get("final_decision") or "—"
    words = VALUATION_WORDS.get(sysd.get("valuation") or "UNKNOWN", VALUATION_WORDS["UNKNOWN"])
    flag = " ⚠" if (p.record or {}).get("stance", {}).get("state") == "DEMOTED" else ""
    lines = ["<b>VIEW</b>",
             f"System: <b>{decision}</b> ({words})",
             f"Analyst: <b>{s['label']}</b>{flag}",
             f"Why: {' · '.join(REASON_WORDS[r] for r in s['reasons'])}"]
    rec = s["record"]
    if rec.get("cases"):
        lines.append(f"After past days like this, 18K was higher a month later {_pct(rec['higher_pct'])} "
                     f"of the time (any day: {_pct(rec['all_higher_pct'])}).")
    return "\n".join(lines)


def _trend(p):
    r = p.rally
    lines = ["<b>TREND</b>"]
    if r.get("in_rally"):
        lines.append(f"Rally {r['number']} of the uptrend since {r['trend_since'][:7]}: "
                     f"{_signed(r['gain_pct'])} since {r['start_date'][5:]} ({r['age_days']} trading days)")
        usd, xau = r.get("usd_since_start"), r.get("xau_since_start")
        if usd is not None and xau is not None:
            source = ("the dollar" if usd >= DOLLAR_SHARE * r["gain_pct"]
                      else "world gold" if xau >= DOLLAR_SHARE * r["gain_pct"] else "the dollar and world gold")
            lines.append(f"Driven by {source}: dollar {_signed(usd)}, world gold {_signed(xau)}")
    else:
        lines.append(f"In a correction: {_signed((p.price / r['record_high'] - 1) * 100)} from the "
                     f"{_m(r['record_high'])} record")
    return "\n".join(lines)


def _averages(p):
    pos = p.position
    ema = pos.get("ema") or {}
    d20, d50 = pos["dist"]["EMA20"], pos["dist"]["EMA50"]
    side = lambda v: "above" if v >= 0 else "below"
    lines = ["<b>MOVING AVERAGES</b> (EMA)",
             f"Price is {_pct(d20, 1)} {side(d20)} the 20-day and {_pct(d50, 1)} {side(d50)} the 50-day"]
    if ema.get("since_date"):
        state = "bullish" if ema["above"] else "bearish"
        lines.append(f"20-day is {_pct(ema['gap_pct'], 1)} {side(ema['gap_pct'])} the 50-day: "
                     f"{state} since {ema['since_date'][5:]}")
    rank = pos["rank"].get("EMA20")
    if "STRETCHED" in pos.get("tags", []) and rank is not None:
        lines.append(f"Stretched: price was this far above its 20-day on only "
                     f"{max(1, round(100 - rank))}% of uptrend days")
    return "\n".join(lines)


def _next_month(p):
    o, cv, rec = p.outlook, p.convert, p.record or {}
    lines = ["<b>NEXT MONTH</b> (20 trading days, from past days like today)"]
    nh = o["new_high"]
    above = "" if p.rally["days_since_high"] == 0 else f" (above {_m(nh['record'])})"
    if nh.get("prob") is not None and rec.get("new_high", {}).get("state") != "DEMOTED":
        lines.append(f"New record high{above}: {_pct(nh['prob'])} chance")
    elif nh.get("base") is not None:
        lines.append(f"New record high{above}: {_pct(nh['base'])} chance (base rate ⚠)")
    if cv.get("dip_came_pct") is not None:
        lines.append(f"{DIP_PCT:.0f}% drop (to {_m(p.price * (1 - DIP_PCT / 100))}): {_pct(cv['dip_came_pct'])} chance")
        cost = cv["wait_cost_pct"]
        better = ("buying now was" if cost > 0 else "waiting was")
        lines.append(f"Buy now or wait for that drop? On average, {better} {_pct(cost, 1)} better.")
    return "\n".join(lines)


def _watch(p):
    r, s, pos = p.rally, p.stance, p.position
    risk = pos.get("risk") or {}
    usual = risk.get("base_drop_pct")
    label = s["label"]
    analyst = lambda t: f" Analyst → {t['to']}" if t["to"] != label else ""

    def followed(key):
        x = risk.get(key) or {}
        return f" chance of a {DROP_PCT:.0f}% drop {_pct(x['drop_pct'])}" if x.get("drop_pct") is not None else ""

    lines = ["<b>WATCH</b>" + (f" (chance of a {DROP_PCT:.0f}% drop within a month: usually {_pct(usual)})"
                               if usual else "")]
    down = []
    for t in s["triggers"]:
        if t["key"] == "rally_end":
            past = r["past"]
            down.append((t["price"], f"Below {_m(t['price'])} (−8%): rally over; past corrections "
                                     f"−{_pct(past['correction_median_depth'])} median.{analyst(t)}"))
        elif t["key"] == "below_sma50":
            down.append((t["price"], f"Below {_m(t['price'])} (50-day avg): uptrend broken;"
                                     f"{followed('below_sma50')}.{analyst(t)}"))
    lines.extend(text for _, text in sorted(down, key=lambda x: -x[0]))
    ema = pos.get("ema") or {}
    if ema.get("above"):
        lines.append(f"20-day EMA under the 50-day:{followed('ema_death')}.")
    for t in s["triggers"]:
        if t["key"] == "usd_below_sma50":
            lines.append(f"Dollar below {t['price'] / 10:,.0f} (its 50-day avg):{followed('usd_below_sma50')}."
                         f"{analyst(t)}")
        elif t["key"] == "usd_above_sma50":
            lines.append(f"Dollar above {t['price'] / 10:,.0f} (its 50-day avg):{analyst(t)}")
    as_of = date.fromisoformat(r["as_of"])
    since = r["days_since_high"]
    late = next((b for b in r.get("ladder", []) if b["band"][0] == 20), None)
    for t in s["triggers"]:
        if t["key"] == "no_high_days" and since <= 4:
            lines.append(f"No new record by ~{trading_date(as_of, t['days']):%m-%d}:{analyst(t)}")
    if late and since < 20:
        lines.append(f"No new record by ~{trading_date(as_of, 20 - since):%m-%d}: the rally then ended "
                     f"{_pct(late['ended'])} of the time.")
    elif late:
        lines.append(f"{since} trading days without a record: the rally then ended {_pct(late['ended'])} "
                     f"of the time.")
    return "\n".join(lines)


def _footer(p):
    local = _local(p.computed_at)
    rec = p.record or {}
    n = max([v.get("n", 0) for v in rec.values() if isinstance(v, dict)] or [0])
    source = "live prices" if p.price_source == "live" else "tgju's close"
    lines = [f"<i>Computed {local:%H:%M} from {source} · history since 2014 · not a price forecast · "
             f"track record {min(n, GATE_MIN_RESOLVED)} of {GATE_MIN_RESOLVED} days checked</i>"]
    lines.extend(f"⚠ {alarm}" for alarm in rec.get("alarms", []))
    lines.append(f"<b>{format_timestamp()}</b>")
    return "\n".join(lines)


def build_direction_message(panel):
    """Assemble /Direction from a stored panel. Returns the body so it can be rendered
    without sending."""
    title = "<b>GOLDPremium: DIRECTION</b>"
    if panel is None:
        return "\n\n".join([title, "No panel computed yet: the first scheduled run from 06:00 or "
                                   "13:00 computes it.", f"<b>{format_timestamp()}</b>"])
    if panel.status != "OK":
        return "\n\n".join([title, "Not enough history yet.", f"<b>{format_timestamp()}</b>"])
    local = _local(panel.computed_at)
    when = f"{local:%H:%M}" if local.date() == local_now().date() else f"{local:%m-%d %H:%M} ⚠ not today"
    record = " · record high" if panel.rally["days_since_high"] == 0 else ""
    tags = " ".join(f"[{t}]" for t in panel.position.get("tags", []) if t != "RECORD")
    head = "\n".join(x for x in (title, f"18K <b>{_m(panel.price)}</b> · {when}{record}", tags) if x)
    return "\n\n".join([head, _view(panel), _trend(panel), _averages(panel), _next_month(panel),
                        _watch(panel), _footer(panel)])


def send_direction(panel):
    _send(build_direction_message(panel))
