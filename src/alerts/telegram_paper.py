"""PAPER (SP-D): the brave analyst's trade push and its 21:00 report.

DRAFT for the owner's review (2026-10-04). Labelled PAPER everywhere: the account is
hypothetical and its BUY/SELL are what it did, not a signal; the system's own BUY alert
keeps its authority. Plain words, read on a phone: grams, toman, the venue, the reason,
the account after the trade, and the trader's next move in prices. Dates in the Persian
calendar, which is how the quarters run. Only <b> and <i>; no bare "<", ">" or "&".
"""

from alerts.helpers import format_m_tomans_short
from alerts.telegram import _send
from timeutil import persian_day, to_tehran


def _m(rial):
    return format_m_tomans_short(rial)


def _signed(value):
    return f"{value:+.2f}%".replace("-", "−")


def _book(holding, cash, sell):
    return f"{holding} g gold + {_m(cash)} cash = <b>{_m(cash + holding * sell)}</b>"


def build_trade_message(action, grams, price, venue, at_utc, reason, holding, cash, sell, plan=""):
    local = to_tehran(at_utc)
    verb = "Bought" if action == "BUY" else "Sold"
    lines = [f"<b>GOLDPremium: PAPER {action}</b>",
             f"{verb} {grams} g at {_m(price)} on {venue} · {persian_day(local.date())} {local:%H:%M}",
             f"Why: {reason}",
             f"Now: {_book(holding, cash, sell)}"]
    if plan:
        lines.append(f"Next: {plan}")
    return "\n".join(lines)


def build_report_message(day, venue, sell, sell_note, analyst, hold, base_day, trades, plan, quant=None):
    """`analyst`/`hold`/`quant`: (holding, cash, quarter base value); `trades`: today's
    analyst trades as (action, grams, price, venue, local HH:MM)."""
    holding, cash, base = analyst
    total = cash + holding * sell
    lines = [f"<b>GOLDPremium: PAPER</b> · {persian_day(day, year=True)}, 21:00",
             f"Gold: {holding} g = {_m(holding * sell)} ({venue} pays {_m(sell)} a gram{sell_note})",
             f"Cash: {_m(cash)}",
             f"<b>Total: {_m(total)}</b>",
             f"This quarter (since {persian_day(base_day)}): {_signed((total / base - 1) * 100)}"]
    for label, other in (("Bought on day 1, never traded", hold), ("Quant engine, same money", quant)):
        if other is not None:
            o_holding, o_cash, o_base = other
            o_total = o_cash + o_holding * sell
            lines.append(f"{label}: {_m(o_total)} ({_signed((o_total / o_base - 1) * 100)})")
    if trades:
        for action, grams, price, trade_venue, clock in trades:
            lines.append(f"Today: {'bought' if action == 'BUY' else 'sold'} {grams} g at {_m(price)}"
                         f"{' on ' + trade_venue if trade_venue else ''} ({clock})")
    else:
        lines.append("Today: no trade")
    if plan:
        lines.append(f"Plan: {plan}")
    return "\n".join(lines)


# -- the room, the front office (SP_D_HANDOFF.md section 27; DRAFT for the owner's review) ------------

def _review_line(view):
    from datetime import date
    if not view or not view.get("next_review"):
        return ""
    return persian_day(date.fromisoformat(view["next_review"]))


def _room_line(view):
    if not view:
        return "The room: no view yet, all in gold by default"
    n = len(view.get("members") or {})
    fi, gold = len(view.get("for_fixed_income") or []), len(view.get("for_gold") or [])
    return f"The room: {fi} of {n} lean to fixed income, {gold} to gold · next review {_review_line(view)}"


def _fund_note(fund_price, estimated, as_of=None):
    return " (Afran's last close, an estimate)" if estimated else ""


def build_room_trade_message(action, grams, price, venue, at_utc, view, after, fund_price, fund_estimated, sell,
                             base, units_before=0.0):
    """The room's push: what it did, why, what it kept, how it comes back, and the account."""
    local = to_tehran(at_utc)
    base_value, _ = base
    total = after.value(sell, fund_price)
    in_fund = after.units * fund_price if after.units and fund_price else 0.0
    why = "; ".join((view or {}).get("reasons") or []) or "the room's default: all in gold"
    lines = ["<b>GOLDPremium: PAPER · the room</b>",
             f"{'Bought' if action == 'BUY' else 'Sold'} {grams} g at {_m(price)} on {venue} · "
             f"{persian_day(local.date())} {local:%H:%M}"]
    if action == "SELL":
        lines += [f"Moved to Afran (fixed income): {_m(in_fund)}{_fund_note(fund_price, fund_estimated)}",
                  f"Why: {why}",
                  f"Kept in gold: {after.grams} g",
                  f"Back to gold: when the stock index turns up, or at the review on {_review_line(view)}"]
    else:
        if units_before:
            lines.append(f"Paid from Afran (fixed income): {_m(units_before * fund_price)}"
                         f"{_fund_note(fund_price, fund_estimated)}")
        lines += [f"Why: {why}", f"Now all in gold: {after.grams} g"]
    lines.append(f"Total: <b>{_m(total)}</b> (this quarter {_signed((total / base_value - 1) * 100)})")
    return "\n".join(lines)


def build_room_report_message(day, venue, sell, sell_note, holding, units, fund_price, fund_estimated, value,
                              base, base_day, hold, trades, view, demand=None):
    """The room's 21:00 report. `hold`: (value, quarter base) of buy-and-hold; `trades`: today's
    trades as (action, grams, price, venue, local HH:MM); `demand`: main._gold_demand's reading."""
    lines = [f"<b>GOLDPremium: PAPER</b> · {persian_day(day, year=True)}, 21:00"]
    if view and view.get("phase_line"):
        lines.append(f"Phase: {view['phase_line']}")
    if units and fund_price:
        lines.append(f"Posture: {holding} g in gold, {_m(units * fund_price)} in Afran (fixed income)"
                     f"{_fund_note(fund_price, fund_estimated)}")
    else:
        lines.append(f"Posture: all in gold · {holding} g ({venue} pays {_m(sell)} a gram{sell_note})")
    if trades:
        for action, grams, price, trade_venue, clock in trades:
            lines.append(f"Today: {'bought' if action == 'BUY' else 'sold'} {grams} g at {_m(price)}"
                         f"{' on ' + trade_venue if trade_venue else ''} ({clock})")
    else:
        lines.append("Today: no trade")
    lines.append(f"<b>Total: {_m(value)}</b> · this quarter {_signed((value / base - 1) * 100)}")
    if hold:
        h_value, h_base = hold
        lines.append(f"Holding instead: {_signed((h_value / h_base - 1) * 100)}")
    lines.append(_room_line(view))
    # the gold funds' block in place of the buyers' line (owner, 2026-10-17: "the cash flow part"; sections
    # 37.5, 46-47), the words the evening and Direction share
    funds = demand_block(demand, day)
    if funds:
        lines += [""] + funds
    return "\n".join(lines)


def demand_block(demand, day):
    """The gold funds' last 7 days for the 21:00 report (alerts/gold_funds.block); [] when stale or missing."""
    if not demand or not demand.get("as_of"):
        return []
    from datetime import date as _date
    if (day - _date.fromisoformat(demand["as_of"])).days > 7:
        return []
    from alerts.gold_funds import block
    return block(demand)


from caluclator.patterns import RATED_LIFT  # noqa: E402,F401  -- a rate only with lift (section 52)


EVENT_WORDS = {"RANGE BREAKOUT": ("Broke up out of the box ({low}-{high}) on {day}: target {target} while above {low}",
                                  "past breaks up"),
               "RANGE BREAKDOWN": ("Broke down out of the box ({low}-{high}) on {day}: target {target} while below {high}",
                                   "past breaks down"),
               "DOUBLE BOTTOM": ("Double bottom on {day}: opens the road to {target}", "past ones")}
BOX_BREAKS = ("RANGE BREAKOUT", "RANGE BREAKDOWN")
# a break whose closes came back inside the box (owner, 2026-10-28; SP_D_HANDOFF.md section 60)
BACK_WORDS = {"RANGE BREAKOUT": "Broke up on {day}; back inside the box since {back}",
              "RANGE BREAKDOWN": "Broke down on {day}; back inside the box since {back}"}
EVENT_DAYS = 14          # a break is told for two weeks after its close


def box_break_levels(kind, level, stop):
    """(low, high, target) of a box's break as shown (0.01M toman), so they add up: the box's height beyond the
    edge it broke; valid while the price stays beyond the other edge (rd_patterns' rule)."""
    lo, hi = sorted((round(level / 1e5) * 1e5, round(stop / 1e5) * 1e5))
    return lo, hi, (hi + (hi - lo) if kind == "RANGE BREAKOUT" else lo - (hi - lo))


def box_break_line(day, kind, level, stop):
    """A box's break in words, for the caption (section 56)."""
    lo, hi, target = box_break_levels(kind, level, stop)
    return EVENT_WORDS[kind][0].format(day=persian_day(day), low=_m(lo), high=_m(hi), target=_m(target))


def pattern_lines(found):
    """The pattern reader's words for a caption (sections 37.4, 46, 52): its last test of the 20-day average,
    the box the price is in with the road out of each side, a live flag, and the patterns of the last 10
    days whose record beat any day's by RATED_LIFT points. A rate is given only then, beside what any day
    did: in a market that rises most years a target above is reached often from any day, so a hit rate
    alone says nothing (the external audit's B7; the box's rates were dropped, the owner's call to make,
    2026-10-18)."""
    from caluclator.patterns import FLAG_RECORD, RECORD, name, rated
    out = []
    found = found or {}
    current = [r for r in found.get("ranges", []) if r[4]]
    if current and found.get("tests"):
        out.append(f"Touched the 20D EMA on {persian_day(found['tests'][-1])} and bounced "
                   "(after such bounces the next month was a little stronger than usual)")
    if current:
        start, _end, lo, hi, _running = current[-1]
        # the edges as shown (0.01M toman), so the reader's own sum gives the target: 25.27 - 1.47 read 23.79
        # when it was taken from the unrounded edges (SP-D section 54)
        lo, hi = round(lo / 1e5) * 1e5, round(hi / 1e5) * 1e5
        height = hi - lo
        up, down = RECORD["RANGE BREAKOUT"], RECORD["RANGE BREAKDOWN"]
        top = found.get("box_high")
        out += [f"In a box since {persian_day(start)}: closes between {_m(lo)} and {_m(hi)}"
                + (f" (highest high {_m(top)})" if top and top > hi else ""),
                f"  Close above {_m(hi)}: opens the road to {_m(hi + height)}",
                f"  Close below {_m(lo)}: may lead to {_m(lo - height)}"]
    flag = found.get("flag")
    if flag:
        day, _level, target, stop = flag
        hit, n, control = FLAG_RECORD
        out += [f"Flag of {persian_day(day)}: target {_m(target)} while above {_m(stop)}",
                f"  ({hit} of {n} past flags got there within 2 months; from any day {control} in 100)"]
    events = found.get("events", [])
    if events:
        latest = found.get("as_of") or events[-1][0]
        seen = set()
        for day, kind, level, target, stop in events:
            base = kind.replace(" (up)", "").replace(" (down)", "")
            if (base in ("FLAG", "EMA20 TEST") or base not in RECORD or base in seen or target is None
                    or (latest - day).days > EVENT_DAYS):
                continue
            # a box's break is told even without a rate: it ends the box line, and the reader saw no word of it
            # on 29 Mehr while the chart marked it (owner, 2026-10-22; SP_D_HANDOFF.md section 56). Any other
            # pattern only with a rate (52.1).
            if base not in BOX_BREAKS and not rated(base):
                continue
            if current and base in BOX_BREAKS and day >= current[-1][0]:
                continue
            seen.add(base)
            hit, n, control = RECORD[base]
            who = EVENT_WORDS.get(base, (None, "past ones"))[1]
            if base in BOX_BREAKS:
                back = next((b for d, k, b in found.get("back", []) if d == day and k == base), None)
                out.append(BACK_WORDS[base].format(day=persian_day(day), back=persian_day(back)) if back
                           else box_break_line(day, base, level, stop))
            else:
                text = EVENT_WORDS.get(base, (f"{name(kind).capitalize()} on {{day}}: target {{target}}",))[0]
                out.append(text.format(day=persian_day(day), target=_m(target)))
            if rated(base):
                out.append(f"  ({hit} of {n} {who} got there within 2 months; from any day {control} in 100)")
    return out


def build_evening_message(day, reading, funds=None, back_on=None):
    """The 21:00 caption when the database cannot be read and PAPER cannot run (SP-D sections 35.2,
    46-47): the chart's reading, then the gold funds' block. `reading`: main._evening_reading, or None;
    `funds`: the block's lines (alerts/gold_funds.block), or None; `back_on`: the date the database is
    expected back, or None."""
    from caluclator.chartist import PHASE_WORDS
    side = lambda v: "above" if v >= 0 else "below"
    lines = [f"<b>GOLDPremium: EVENING</b> · {persian_day(day, year=True)}, 21:00"]
    if reading is None:
        lines.append("Chart reading: not enough history")
    else:
        head = f"18K {_m(reading['price'])} (market, tgju)"
        if reading["phase"]:
            head += f" · {PHASE_WORDS[reading['phase']].split(' (')[0]}"
        if reading["swing"]:
            swing_day, swing_price, kind = reading["swing"]
            head += f", {'up' if kind == 'L' else 'down'} from {_m(swing_price)} on {persian_day(swing_day)}"
        lines.append(head)
        # the two trend lines the chart draws, by its legend's names (section 55)
        drawn = reading.get("trend_lines") or {}
        sup, res, price = drawn.get("support"), drawn.get("resistance"), reading["price"]
        if sup and res and res > sup:
            spot = (price - sup) / (res - sup)
            where = ("above the resistance line" if spot > 1 else "below the support line" if spot < 0
                     else "in their upper half" if spot > 0.5 else "in their lower half")
            lines.append(f"Support trend line {_m(sup)}, resistance trend line {_m(res)}; price {where}")
        elif sup:
            lines.append(f"Support trend line {_m(sup)}; price {'above' if price >= sup else 'below'} it")
        elif res:
            lines.append(f"Resistance trend line {_m(res)}; price {'below' if price <= res else 'above'} it")
        d20, was20 = reading["ema20"]
        d50 = reading["ema50"][0]
        was = f"{abs(was20):.1f}%" + ("" if side(was20) == side(d20) else f" {side(was20)}")
        # "20D EMA", "50D EMA", one decimal, "was": Direction's words (owner, 2026-10-22)
        lines.append(f"{abs(d20):.1f}% {side(d20)} the 20D EMA (was {was}), {abs(d50):.1f}% {side(d50)} the 50D EMA")
        lines.extend(pattern_lines(reading.get("patterns")))
    if funds:
        lines += [""] + list(funds)
    lines += ["", "The room's report returns with the database"
              + (f" (expected {persian_day(back_on)})" if back_on else "")]
    return "\n".join(lines)


def send_paper(text):
    _send(text)


CAPTION_LIMIT = 1024                     # Telegram's caption limit, in characters of text


def send_paper_report(text, png=None):
    """The 21:00 report: the chart with the report as its caption, or the text alone when
    there is no chart, the caption is too long, or the photo fails."""
    import re
    from alerts.telegram import _send_photo
    if png and len(re.sub(r"</?[bi]>", "", text)) <= CAPTION_LIMIT and _send_photo(png, text):
        return
    _send(text)
