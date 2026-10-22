"""The pulse: a push when 18K's daily close breaks out of a box or a flag (SP-D, SP_D_HANDOFF.md section 56; the
owner, 2026-10-22: "the gold is coming out of the box ... but there is no pulse to the user, no alert is sent").

PREVIEW, not wired: built for the owner's lock. It describes a confirmed close against the chart's own levels,
as the evening's caption and the chart draw them; a rate only where the pattern beat any day (the flag), beside
any day's; no BUY, SELL or WAIT -- final_decision keeps that authority (CLAUDE.md), parked since 2026-10-18.
Only <b> and <i>; no bare "<", ">" or "&".
"""

from alerts.helpers import format_m_tomans_short
from timeutil import persian_day, to_tehran

TITLES = {"RANGE BREAKOUT": "BREAKOUT", "RANGE BREAKDOWN": "BREAKDOWN", "FLAG": "BREAKOUT"}


def _m(rial):
    return format_m_tomans_short(rial)


def build_pulse_message(event, close, now, box=None, flag=None):
    """`event`: (day, kind, level, target, stop) from patterns.read; `close`: that day's close (rial); `box`:
    (start, end) of the box it left; `flag`: the live flag, (day, level, target, stop), shown beside a box break."""
    from alerts.telegram_paper import box_break_levels
    from caluclator.patterns import FLAG_RECORD, rated
    day, kind, level, target, stop = event
    local = to_tehran(now)
    lines = [f"<b>GOLDPremium: {TITLES[kind]}</b> · {persian_day(local.date())}, {local:%H:%M}"]
    if kind == "FLAG":
        hit, n, control = FLAG_RECORD
        lines += [f"18K closed out of a flag on {persian_day(day)}: {_m(close)} (market, tgju)",
                  f"Target {_m(target)} while above {_m(stop)}",
                  f"{hit} of {n} past flags got there within 2 months; from any day {control} in 100"]
    else:
        up = kind == "RANGE BREAKOUT"
        lo, hi, goal = box_break_levels(kind, level, stop)
        lines.append(f"18K closed out of its box, {'upward' if up else 'downward'}: {_m(close)} on "
                     f"{persian_day(day)} (market, tgju)")
        if box:
            lines.append(f"Box of {persian_day(box[0])}-{persian_day(box[1])}: closes between {_m(lo)} and {_m(hi)}")
        lines.append(f"Target {_m(goal)} while {'above ' + _m(lo) if up else 'below ' + _m(hi)}")
        if rated(kind):
            from caluclator.patterns import RECORD
            hit, n, control = RECORD[kind]
            lines.append(f"{hit} of {n} past breaks got there within 2 months; from any day {control} in 100")
        if flag:
            f_day, _l, f_target, f_stop = flag
            lines.append(f"Still live: the flag of {persian_day(f_day)}, target {_m(f_target)} while above {_m(f_stop)}")
    lines += ["", "<i>Decision support, not an instruction to trade.</i>"]
    return "\n".join(lines)
