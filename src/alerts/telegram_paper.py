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


SHOWN = 0.5        # a pattern's line is shown when more than half of its past ones on 18K reached their target


def odds(hit, n):
    """A record in plain words for the box's two sides: '3 in 4', 'about half'."""
    words = ((1 / 4, "1 in 4"), (1 / 3, "1 in 3"), (1 / 2, "about half"), (2 / 3, "2 in 3"), (3 / 4, "3 in 4"),
             (4 / 5, "4 in 5"), (9 / 10, "9 in 10"))
    return min(words, key=lambda w: abs(w[0] - hit / n))[1]


EVENT_WORDS = {"RANGE BREAKOUT": ("Broke up out of the box on {day}: opens the road to {target}", "past breaks up"),
               "RANGE BREAKDOWN": ("Broke down out of the box on {day}: may lead to {target}", "past breaks down"),
               "DOUBLE BOTTOM": ("Double bottom on {day}: opens the road to {target}", "past ones")}


def pattern_lines(found):
    """The pattern reader's words for a caption (sections 37.4, 46): its last test of the 20-day average, the
    box the price is in with the road out of each side, a live flag, and the patterns of the last 10 days
    that worked on 18K -- more than half of the past ones reached their target, so the rising wedge, the
    double top and the falling wedge are left out (owner, 2026-10-17). Each with its record on 18K: the
    target reached within 40 trading days, before a close back through the pattern's other side."""
    from caluclator.patterns import FLAG_RECORD, RECORD, name
    out = []
    found = found or {}
    current = [r for r in found.get("ranges", []) if r[4]]
    if current and found.get("tests"):
        out.append(f"Touched the 20-day average on {persian_day(found['tests'][-1])} and bounced "
                   "(after such bounces the next month was a little stronger than usual)")
    if current:
        start, _end, lo, hi, _running = current[-1]
        height = hi - lo
        up, down = RECORD["RANGE BREAKOUT"], RECORD["RANGE BREAKDOWN"]
        out += [f"In a box since {persian_day(start)}, {_m(lo)} to {_m(hi)}",
                f"  Close above {_m(hi)}: opens the road to {_m(hi + height)} ({odds(*up[:2])} got there)",
                f"  Close below {_m(lo)}: may lead to {_m(lo - height)} ({odds(*down[:2])} got there)"]
    flag = found.get("flag")
    if flag:
        day, _level, target, stop = flag
        hit, n, _control = FLAG_RECORD
        out += [f"Flag of {persian_day(day)}: target {_m(target)} while above {_m(stop)}",
                f"  ({hit} of {n} past flags got there within 2 months)"]
    events = found.get("events", [])
    if events:
        latest = events[-1][0]
        seen = set()
        for day, kind, _level, target, *_r in events:
            base = kind.replace(" (up)", "").replace(" (down)", "")
            if (base in ("FLAG", "EMA20 TEST") or base not in RECORD or base in seen or target is None
                    or (latest - day).days > 14 or RECORD[base][0] / RECORD[base][1] <= SHOWN):
                continue
            if current and base in ("RANGE BREAKOUT", "RANGE BREAKDOWN") and day >= current[-1][0]:
                continue
            seen.add(base)
            hit, n, _control = RECORD[base]
            text, who = EVENT_WORDS.get(base, (f"{name(kind).capitalize()} on {{day}}: target {{target}}", "past ones"))
            out += [text.format(day=persian_day(day), target=_m(target)),
                    f"  ({hit} of {n} {who} got there within 2 months)"]
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
        channel = reading["channel"]
        if channel:
            where = ("above its top line" if channel["position"] > 1 else "below its bottom line" if channel["position"] < 0
                     else "in its upper half" if channel["position"] > 0.5 else "in its lower half")
            slope = channel["slope_pct_day"]
            lines.append(f"{'Rising' if slope >= 0 else 'Falling'} channel, {slope:+.2f}% a day; price {where}".replace("-", "−"))
        d20, was20 = reading["ema20"]
        d50 = reading["ema50"][0]
        was = f"{abs(was20):.1f}%" + ("" if side(was20) == side(d20) else f" {side(was20)}")
        lines.append(f"{abs(d20):.1f}% {side(d20)} the 20-day average (yesterday {was}), {abs(d50):.0f}% {side(d50)} the 50-day")
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
