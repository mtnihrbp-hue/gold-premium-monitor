"""DIRECTION (SP-D): the /Direction message, rendered from a stored panel.

DRAFT v5, for the owner's review (2026-10-03): read on a phone, so short lines, no padded
columns (they do not align in a proportional font), and only what bears on the reader's
decision -- is the uptrend intact, how late is it, what would change the picture, and has
waiting for a dip paid. The evidence behind each line stays in the stored panel.

Same vocabulary as UPDATE and ANALYZE: a discount increases or decreases; a large one is
"heavily discounted", never "cheap"; Cheap/Expensive, never comparatives of "dear". Odds
are written as "N in 100" over past cases like today. No BUY or SELL is printed except the
system's own decision, which keeps its authority; the analyst stance is a stance.
"""

from datetime import date, datetime

from alerts.helpers import format_m_tomans_short, format_timestamp, to_tehran
from alerts.telegram import _send
from analysis.direction import DIP_PCT, trading_date
from analysis.direction_ledger import GATE_MIN_RESOLVED
from timeutil import local_now

VALUATION_WORDS = {
    "CHEAP": "heavily discounted",
    "FAIR": "usual discount",
    "EXPENSIVE": "above fair value",
    "UNKNOWN": "discount not ranked yet",
}
REASON_WORDS = {
    "trend_up": "trend up",
    "below_sma50": "below the 50-day",
    "new_highs": "new highs",
    "no_high_20d": "no new high for 20+ days",
    "usd_above_sma50": "dollar above its 50-day",
    "usd_below_sma50": "dollar below its 50-day",
    "rally_broken": "rally broken",
}


def _m(price):
    return format_m_tomans_short(price)


def _signed(value, decimals=1):
    return f"{value:+.{decimals}f}%".replace("-", "−")


def _in100(pct):
    return f"{pct:.0f} in 100"


def _local(iso):
    return to_tehran(datetime.fromisoformat(iso)) if iso else None


def _view(p):
    s, sysd = p.stance, p.system or {}
    decision = sysd.get("final_decision") or "—"
    words = VALUATION_WORDS.get(sysd.get("valuation") or "UNKNOWN", VALUATION_WORDS["UNKNOWN"])
    flag = " ⚠" if (p.record or {}).get("stance", {}).get("state") == "DEMOTED" else ""
    lines = ["<b>VIEW</b>",
             f"System: <b>{decision}</b> · {words}",
             f"Analyst: <b>{s['label']}</b>{flag}",
             f"<i>{' · '.join(REASON_WORDS[r] for r in s['reasons'])}</i>"]
    rec = s["record"]
    if rec.get("cases"):
        lines.append(f"<i>Past such days: {_in100(rec['higher_pct'])} higher 20 days later "
                     f"(all days {rec['all_higher_pct']:.0f})</i>")
    return "\n".join(lines)


def _where(p):
    r, pos = p.rally, p.position
    lines = ["<b>WHERE WE ARE</b>"]
    if r.get("in_rally"):
        lines.append(f"Rally #{r['number']} · day {r['age_days']} · {_signed(r['gain_pct'], 0)} "
                     f"from {_m(r['start_price'])}")
    else:
        lines.append(f"Correction · {_signed((p.price / r['record_high'] - 1) * 100)} from the "
                     f"{_m(r['record_high'])} peak")
    d20, rank = pos["dist"]["SMA20"], pos["rank"].get("SMA20")
    top = f"top {max(1, round(100 - rank))}%" if rank is not None else ""
    if "STRETCHED" in pos.get("tags", []):
        lines.append(f"{_signed(d20)} above its 20-day avg (stretched: {top})")
    else:
        lines.append(f"{_signed(d20)} vs its 20-day avg" + (f" ({top})" if top and d20 > 0 else ""))
    ema = pos.get("ema") or {}
    if ema.get("since_date"):
        side = "bullish" if ema["above"] else "bearish"
        lines.append(f"EMA 20/50: {side} since {ema['since_date'][5:]} (gap {_signed(ema['gap_pct'])})")
    if "DOLLAR-DRIVEN" in pos.get("tags", []):
        lines.append(f"60 days: 18K {_signed(pos['gold60'], 0)} · dollar {_signed(pos['usd60'], 0)}")
    return "\n".join(lines)


def _next20(p):
    o, cv, rec = p.outlook, p.convert, p.record or {}
    lines = ["<b>NEXT 20 DAYS</b> <i>(past cases like today)</i>"]
    nh = o["new_high"]
    above = "" if p.rally["days_since_high"] == 0 else f" (above {_m(nh['record'])})"
    if nh.get("prob") is not None and rec.get("new_high", {}).get("state") != "DEMOTED":
        lines.append(f"New high{above}: {_in100(nh['prob'])}")
    elif nh.get("base") is not None:
        lines.append(f"New high{above}: {_in100(nh['base'])} (base rate ⚠)")
    if cv.get("dip_came_pct") is not None:
        lines.append(f"{cv['dip_pct']:.0f}% dip (to {_m(p.price * (1 - DIP_PCT / 100))}): {_in100(cv['dip_came_pct'])}")
        cost = cv["wait_cost_pct"]
        lines.append(f"Waiting for it paid {cost:.1f}% more on avg" if cost > 0
                     else f"Waiting for it saved {abs(cost):.1f}% on avg")
    return "\n".join(lines)


def _watch(p):
    r, s, pos = p.rally, p.stance, p.position
    lines = ["<b>LINES TO WATCH</b>"]
    label = s["label"]
    to = lambda t: f" → {t['to']}" if t["to"] != label else ""
    down = []
    supports = [lv["price"] for lv in p.levels.get("supports", [])]
    for t in s["triggers"]:
        if t["key"] == "rally_end":
            near = any(abs(x / t["price"] - 1) < 0.01 for x in supports)
            down.append((t["price"], f"▼ {_m(t['price'])}: rally ends (−8%)" + (" · support" if near else "") + to(t)))
        elif t["key"] == "below_sma50":
            down.append((t["price"], f"▼ {_m(t['price'])}: trend breaks (50-day){to(t)}"))
    lines.extend(text for _, text in sorted(down, key=lambda x: -x[0]))
    ema = pos.get("ema") or {}
    if ema.get("above") and ema.get("death_cross_drop_pct") is not None:
        lines.append(f"▼ EMA20 under EMA50: 5% drop {_in100(ema['death_cross_drop_pct'])} "
                     f"(usual {ema['base_drop_pct']:.0f})")
    for t in s["triggers"]:
        if t["key"] in ("usd_below_sma50", "usd_above_sma50"):
            below = t["key"] == "usd_below_sma50"
            lines.append(f"{'▼' if below else '▲'} Dollar {'below' if below else 'above'} "
                         f"{t['price'] / 10:,.0f} (its 50-day){to(t)}")
    as_of = date.fromisoformat(r["as_of"])
    since = r["days_since_high"]
    late = next((b for b in r.get("ladder", []) if b["band"][0] == 20), None)
    for t in s["triggers"]:
        if t["key"] == "no_high_days" and since <= 4:
            lines.append(f"⏳ No new high by ~{trading_date(as_of, t['days']):%m-%d}{to(t)}")
    if late and since < 20:
        lines.append(f"⏳ No new high by ~{trading_date(as_of, 20 - since):%m-%d}: "
                     f"rally ended {_in100(late['ended'])}")
    elif late:
        lines.append(f"⏳ {since} days without a new high: rally ended {_in100(late['ended'])}")
    return "\n".join(lines)


def _footer(p):
    local = _local(p.computed_at)
    rec = p.record or {}
    n = max([v.get("n", 0) for v in rec.values() if isinstance(v, dict)] or [0])
    source = "live prices" if p.price_source == "live" else "tgju close"
    lines = [f"<i>Computed {local:%H:%M} from {source} · self-check {min(n, GATE_MIN_RESOLVED)}/"
             f"{GATE_MIN_RESOLVED} · not an up/down forecast</i>"]
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
    return "\n\n".join([head, _view(panel), _where(panel), _next20(panel), _watch(panel), _footer(panel)])


def send_direction(panel):
    _send(build_direction_message(panel))
