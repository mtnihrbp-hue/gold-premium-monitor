"""DIRECTION (SP-D): the /Direction message, rendered from a stored panel.

DRAFT v4, for the owner's review (2026-10-03). Not reachable from any command on main
until the owner approves the layout (process rule: no message layout without permission).

Same vocabulary as UPDATE and ANALYZE: a discount increases or decreases; a large one is
"heavily discounted", never "cheap"; Cheap/Expensive, never comparatives of "dear". Tags
are fixed words with fixed definitions (analysis/direction.py). Every figure is a count
over completed history with its sample, or a level computed from it; no BUY or SELL is
printed except the system's own decision, which keeps its authority. The analyst stance
is a stance, not an instruction.
"""

from alerts.helpers import format_m_tomans_short, format_timestamp, to_tehran
from alerts.telegram import _send
from alerts.telegram_analyze import _cont, _row, _sep
from timeutil import local_now

VALUATION_WORDS = {
    "CHEAP": "platforms heavily discounted against fair value",
    "FAIR": "platforms at their usual discount to fair value",
    "EXPENSIVE": "platforms above fair value",
    "UNKNOWN": "not enough history to rank the discount",
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
# measured on the 2024-2026 holdout (SP_C_HANDOFF.md section 49): the 20-day 10-90% range
# held 72% of outcomes, and 22% ended above it -- the range is short on the upside in a
# strong market; replaced by the live record once that has GATE_MIN_RESOLVED days
RANGE20_HOLDOUT_INSIDE, RANGE20_HOLDOUT_ABOVE = 72, 22
SUPPORT_EDGE = "+4 to +9 pp"       # swing supports against a level with no history (R2b)


def _m(price):
    return format_m_tomans_short(price)


def _signed(value, decimals=1):
    return f"{value:+.{decimals}f}%".replace("-", "−")


def _top(rank):
    return f"top {max(1, round(100 - rank))}%" if rank is not None else "—"


def _band_label(band):
    lo, hi = band
    return f"{lo} days" if lo == hi else (f"{lo}+ days" if hi >= 250 else f"{lo}–{hi} days")


def _local(iso):
    from datetime import datetime
    return to_tehran(datetime.fromisoformat(iso)) if iso else None


def _read_line(p):
    """One deterministic sentence on the position, from the tags."""
    tags = p.position.get("tags", [])
    trend = p.position.get("trend")
    if "CORRECTION" in tags:
        return f"In a correction: {_signed(_from_peak(p))} from the peak."
    if trend == "UPTREND" and "STRETCHED" in tags:
        return "Strong trend, stretched: a pause or a dip toward the 20-day is the usual next step."
    if "STALLING" in tags:
        return f"Stalling: {p.rally['days_since_high']} days without a new high."
    if trend == "UPTREND":
        return "Uptrend, not stretched."
    if trend == "DOWNTREND":
        return "Downtrend."
    return "No settled trend."


def _from_peak(p):
    return (p.price / p.rally["record_high"] - 1) * 100


def _view(p):
    s, sysd = p.stance, p.system or {}
    lines = [_sep(), "<b>VIEW</b>", _sep()]
    decision = sysd.get("final_decision")
    words = VALUATION_WORDS.get(sysd.get("valuation") or "UNKNOWN", VALUATION_WORDS["UNKNOWN"])
    lines.append(_row("System", f"{decision} · {words}" if decision else "—"))
    stance = s["label"] + (" · STRETCHED" if s.get("stretched") else "")
    st = (p.record or {}).get("stance", {})
    if st.get("state") == "DEMOTED":
        stance += " ⚠"
    lines.append(_row("Analyst", stance))
    lines.append(_cont(" · ".join(REASON_WORDS[r] for r in s["reasons"])))
    rec = s["record"]
    if rec.get("cases"):
        lines.append(_cont(f"past {s['label']} days: {rec['higher_pct']:.0f}% higher 20 days later "
                           f"(all days {rec['all_higher_pct']:.0f}%)"))
    lines.append("<i>System: platform price against fair value. Analyst: the trend.</i>")
    return "\n".join(lines)


def _rally(p):
    r = p.rally
    if not r.get("in_rally"):
        lines = [_sep(), "<b>CORRECTION</b>", _sep()]
        lines.append(_row("From the peak", f"{_signed(_from_peak(p))} ({_m(r['record_high'])})"))
    else:
        lines = [_sep(), f"<b>RALLY #{r['number']}</b> of the uptrend since {r['trend_since'][:7]}", _sep()]
        lines.append(_row("Since", f"{r['start_date'][5:]} at {_m(r['start_price'])} · {r['age_days']} days"))
        lines.append(_row("Gain", _signed(r["gain_pct"])))
        at_peak = abs(r["peak"] - p.price) < 1
        lines.append(_row("Peak", f"{_m(r['peak'])}" + (" (now)" if at_peak else "")))
        lines.append(_row("Ends below", f"{_m(r['end_line'])} ({_signed(r['end_line_pct'])})"))
        past = r["past"]
        lines.append(_row("Past rallies", f"{past['rallies']} since 2014: longer than {r['longer_than']}, "
                                          f"larger than {r['larger_than']}"))
    lines.append("<i>Age and size have not timed a rally's end. The stall clock has:</i>")
    lines.append("<i>days without a new high → next 20 days</i>")
    now_band = (r.get("band") or {}).get("band")
    for b in r["ladder"]:
        if b["band"][0] > 39:
            continue
        mark = "  ← now" if b["band"] == now_band else ""
        lines.append(_row(_band_label(b["band"]), f"new high {b['resumed']:.0f}% · ended {b['ended']:.0f}%{mark}"))
    return "\n".join(lines)


def _position(p):
    pos = p.position
    lines = [_sep(), "<b>POSITION</b>", _sep()]
    for key, label in (("SMA20", "vs 20-day"), ("SMA50", "vs 50-day"), ("SMA200", "vs 200-day")):
        lines.append(_row(label, f"{_signed(pos['dist'][key])} ({_m(pos['average'][key])}) · "
                                 f"{_top(pos['rank'].get(key))} of uptrend days"))
    lines.append(_row("RSI · ADX", f"{pos['rsi']:.0f} · {pos['adx']:.0f}"))
    lines.append(f"<i>{_read_line(p)}</i>")
    g = pos["gaps"].get("SMA20")
    if g:
        closed = (f"closed in all {g['cases']} past cases" if g["closed_pct"] >= 99.5
                  else f"closed in {g['closed_pct']:.0f}% of {g['cases']} cases")
        how = (f"{round(g['by_fall_pct'] / 100 * 3)} in 3 by a dip" if g["by_fall_pct"] >= 50
               else "mostly by the average rising")
        lines.append(_row("20-day gap", f"{closed}, median {g['median_days']:.0f} days"))
        lines.append(_cont(f"{how}; price at the touch {_signed(g['median_move_at_touch'])} "
                           f"(~{_m(p.price * (1 + g['median_move_at_touch'] / 100))})"))
    g = pos["gaps"].get("SMA50")
    if g:
        how = "mostly by a dip" if g["by_fall_pct"] >= 50 else "mostly by the average rising"
        lines.append(_row("50-day gap", f"closed in {g['closed_pct']:.0f}% within 120 days, median "
                                        f"{g['median_days']:.0f} days"))
        lines.append(_cont(f"{how}; price at the touch {_signed(g['median_move_at_touch'])}"))
    if "DOLLAR-DRIVEN" in pos.get("tags", []):
        lines.append(_row("60 days", f"18K {_signed(pos['gold60'])} · dollar {_signed(pos['usd60'])}"))
    return "\n".join(lines)


def _outlook(p):
    o, rec = p.outlook, p.record or {}
    lines = [_sep(), "<b>OUTLOOK</b> (20 trading days)", _sep()]
    nh = o["new_high"]
    nh_rec = rec.get("new_high", {})
    if nh.get("prob") is not None and nh_rec.get("state") != "DEMOTED":
        lines.append(_row("New high", f"{nh['prob']:.0f}% (all uptrend days {nh['base']:.0f}%)"))
    elif nh.get("base") is not None:
        lines.append(_row("New high", f"{nh['base']:.0f}% (base rate; the clock's rate is under review ⚠)"))
    low, mid, high = o["range20"]["price"]
    lines.append(_row("Range 10–90%", f"{_m(low)} – {_m(high)} · middle {_m(mid)}"))
    rg = rec.get("range20", {})
    if rg.get("state") in ("OK", "DEMOTED"):
        flag = " ⚠" if rg["state"] == "DEMOTED" else ""
        lines.append(_cont(f"<i>live: {rg['inside_pct']:.0f}% inside, {rg['above_pct']:.0f}% above "
                           f"({rg['n']} days){flag}</i>"))
    else:
        lines.append(_cont(f"<i>since 2024: {RANGE20_HOLDOUT_INSIDE}% inside, "
                           f"{RANGE20_HOLDOUT_ABOVE}% above</i>"))
    return "\n".join(lines)


def _levels(p):
    lv = p.levels
    lines = [_sep(), "<b>LEVELS</b>", _sep()]
    end_line = p.rally.get("end_line")
    for k, s in enumerate(lv.get("supports", [])):
        text = f"{_m(s['price'])} ({_signed(s['pct'])}" + (f", {s['touches']} swings)" if s["touches"] > 1 else ")")
        if k == 0 and end_line and abs(s["price"] / end_line - 1) < 0.01:
            text += " · at the rally end line"
        lines.append(_row("Support", text) if k == 0 else _cont(text))
    if lv.get("resistances"):
        for k, s in enumerate(lv["resistances"]):
            text = f"{_m(s['price'])} ({_signed(s['pct'])})"
            lines.append(_row("Resistance", text) if k == 0 else _cont(text))
    else:
        lines.append(_row("Resistance", "none (record)"))
    for k, z in enumerate(lv.get("zones", [])):
        text = f"{_m(z['price'])} ({_signed(z['pct'])}, {z['days']} days there this year)"
        lines.append(_row("Traded zone", text) if k == 0 else _cont(text))
    lines.append(f"<i>A swing support held {SUPPORT_EDGE} more often than a level with no history.</i>")
    return "\n".join(lines)


def _convert(p):
    cv = p.convert
    lines = [_sep(), "<b>CONVERT</b>", _sep()]
    if cv.get("wait_cost_pct") is not None:
        verdict = (f"yet cost {cv['wait_cost_pct']:.1f}% more on average" if cv["wait_cost_pct"] > 0
                   else f"and saved {abs(cv['wait_cost_pct']):.1f}% on average")
        lines.append(_row(f"Wait for {cv['dip_pct']:.0f}% dip", f"on {cv['similar_days']} days like today it came "
                                                              f"{cv['dip_came_pct']:.0f}% of the time,"))
        lines.append(_cont(f"{verdict} than converting at once"))
        lines.append(_cont(f"<i>all days: costlier in {cv['years_costlier']} of {cv['years']} years</i>"))
    if cv.get("spread_pct") is not None:
        lines.append(_row("Platforms", f"{cv['cheapest']} {_m(cv['cheapest_price'])} … "
                                       f"{_m(cv['most_expensive_price'])} (spread {cv['spread_pct']:.2f}%)"))
    return "\n".join(lines)


def _next(p):
    """DRAFT: the scenario ladder, for the deep-dive session with the owner."""
    r, s, pos = p.rally, p.stance, p.position
    lines = [_sep(), "<b>NEXT</b> <i>(draft)</i>", _sep()]
    ladder = {tuple(b["band"]): b for b in r.get("ladder", [])}
    if r.get("in_rally"):
        lines.append(f"▲ <b>New high</b> (above {_m(r['record_high'])}): clock resets")
    for t in s["triggers"]:
        if t["key"] == "no_high_days":
            days = r["days_since_high"] + t["days"]
            band = next((b for k, b in ladder.items() if k[0] <= days <= k[1]), None)
            odds = f"; new high {band['resumed']:.0f}%, ended {band['ended']:.0f}%" if band else ""
            lines.append(f"▬ <b>{t['days']} more days</b> without a new high: Analyst → {t['to']}{odds}")
    down = []                       # (price, lines) below the price, nearest first
    g = pos["gaps"].get("SMA20")
    if g and g["by_fall_pct"] >= 50:
        touch = p.price * (1 + g["median_move_at_touch"] / 100)
        down.append((touch, [f"▼ <b>Dip to the 20-day</b> (~{_m(touch)}): the stretch has closed; trend intact"]))
    for t in s["triggers"]:
        if t["key"] == "rally_end":
            past = r["past"]
            down.append((t["price"], [
                f"▼ <b>Close below {_m(t['price'])}</b>: rally #{r['number']} ends; Analyst → {t['to']}",
                f"    past corrections: median {_signed(past['correction_median_depth'], 0)} from the peak, "
                f"{past['correction_median_days']:.0f} days (half {_signed(past['correction_depth_shallow'], 0)} "
                f"to {_signed(past['correction_depth_deep'], 0)})"]))
        elif t["key"] == "below_sma50":
            down.append((t["price"], [f"▼ <b>Close below {_m(t['price'])}</b> (50-day): trend no longer up; "
                                      f"Analyst → {t['to']}"]))
    for _, text in sorted(down, key=lambda x: -x[0]):
        lines.extend(text)
    for t in s["triggers"]:
        if t["key"] in ("usd_below_sma50", "usd_above_sma50"):
            side = "below" if t["key"] == "usd_below_sma50" else "above"
            lines.append(f"{'▼' if side == 'below' else '▲'} <b>Dollar {side} {t['price'] / 10:,.0f}</b> "
                         f"(its 50-day): Analyst → {t['to']}")
    return "\n".join(lines)


def _footer(p):
    local = _local(p.computed_at)
    source = "live platform prices" if p.price_source == "live" else "tgju's close"
    lines = [f"<i>Computed {local:%H:%M} from {source}; tgju candle {p.candle_date[5:]}.</i>",
             "<i>Up or down is not forecast: no tested signal beat the base rate.</i>"]
    rec = p.record or {}
    n = max([v.get("n", 0) for k, v in rec.items() if isinstance(v, dict)] or [0])
    lines.append(f"<i>Live record: {n} days resolved" + (" (learning)" if n < 30 else "") + ".</i>")
    for alarm in rec.get("alarms", []):
        lines.append(f"⚠ {alarm}")
    lines.append(f"<b>{format_timestamp()}</b>")
    return "\n".join(lines)


def build_direction_message(panel):
    """Assemble /Direction from a stored panel. Returns the body so it can be rendered
    without sending."""
    head = ["<b>GOLDPremium: DIRECTION</b>"]
    if panel is None:
        head.append("No panel computed yet: the first scheduled run from 06:00 or 13:00 computes it.")
        head.append(f"<b>{format_timestamp()}</b>")
        return "\n\n".join(head)
    if panel.status != "OK":
        head.append("Not enough history yet.")
        head.append(f"<b>{format_timestamp()}</b>")
        return "\n\n".join(head)
    local = _local(panel.computed_at)
    when = f"{local:%H:%M}" if local.date() == local_now().date() else f"{local:%m-%d %H:%M} ⚠ not today"
    tags = " ".join(f"[{t}]" for t in panel.position.get("tags", []))
    head.append(f"18K <b>{_m(panel.price)}</b> · {'live' if panel.price_source == 'live' else 'close'} "
                f"{when}\n{tags}")
    blocks = ["\n".join(head), _view(panel), _rally(panel), _position(panel), _outlook(panel),
              _levels(panel), _convert(panel), _next(panel), _footer(panel)]
    return "\n\n".join(blocks)


def send_direction(panel):
    _send(build_direction_message(panel))
