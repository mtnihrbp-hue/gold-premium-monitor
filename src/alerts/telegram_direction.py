"""The DIRECTION section for ANALYZE (SP-D). DRAFT: not wired into any message until the
owner approves its layout (process rule: no message layout changes without permission).

Same voice as ANALYZE: what the record shows, counted, with its sample size and the
all-days base rate beside every conditional figure; no BUY, SELL or WAIT, and no
instruction.
"""

from alerts.helpers import format_m_tomans_short
from alerts.telegram_analyze import _cont, _row, _sep

HEADLINE_HORIZON = 20


def _m(price):
    return format_m_tomans_short(price)


def _times_tested(touches):
    return "" if touches < 2 else f", tested {touches}x"


def _trend_words(view):
    if view.trend == "UPTREND":
        return "up (above the 50- and 200-day averages)"
    if view.trend == "DOWNTREND":
        return "down (below the 50- and 200-day averages)"
    return "mixed (no settled trend)"


def build_direction_section(view):
    lines = [_sep(), "<b>DIRECTION (18K, daily)</b>", _sep()]
    if view.status != "OK":
        lines.append(_row("Not enough history", "yet"))
        return "\n".join(lines)

    lines.append(_row(f"Close {view.as_of:%m-%d}", _m(view.close)))
    lines.append(_row("Trend", _trend_words(view)))
    side = "above" if view.stretch_pct >= 0 else "below"
    lines.append(_row("50-day average", f"{_m(view.averages[50])}  (price {abs(view.stretch_pct):.1f}% {side})"))
    lines.append(_row("200-day average", _m(view.averages[200])))
    if view.rsi is not None:
        lines.append(_row("RSI (14)", f"{view.rsi:.0f}"))

    lines.append("")
    if view.resistances:
        for k, lv in enumerate(view.resistances[:2]):
            text = f"{_m(lv.price)}  ({lv.distance_pct:.1f}% above{_times_tested(lv.touches)})"
            lines.append(_row("Resistance", text) if k == 0 else _cont(text))
    else:
        lines.append(_row("Resistance", "none above (record high)"))
    for k, lv in enumerate(view.supports[:3]):
        text = f"{_m(lv.price)}  ({abs(lv.distance_pct):.1f}% below{_times_tested(lv.touches)}, last {lv.last:%m-%d})"
        lines.append(_row("Support", text) if k == 0 else _cont(text))

    odds, base = view.odds[HEADLINE_HORIZON], view.baseline[HEADLINE_HORIZON]
    lines.append("")
    lines.append(f"<i>In {odds.cases} similar days since 2014 ({odds.episodes} episodes:</i>")
    lines.append(f"<i>{view.condition}):</i>")
    lines.append(_row(f"Higher after {HEADLINE_HORIZON}d", f"{odds.higher_pct:.0f}%   (all days: {base.higher_pct:.0f}%)"))
    move = "up" if odds.median_move_pct >= 0 else "down"
    base_move = "up" if base.median_move_pct >= 0 else "down"
    lines.append(_row(f"Typical {HEADLINE_HORIZON}d move", f"{move} {abs(odds.median_move_pct):.1f}%   "
                                                         f"(all days: {base_move} {abs(base.median_move_pct):.1f}%)"))
    lines.append(_row("Fell 5%+ meanwhile", f"{odds.pullback_pct:.0f}%   (all days: {base.pullback_pct:.0f}%)"))

    lines.append("")
    lines.append("<i>Waiting for a dip, against converting at once:</i>")
    for option in view.entry:
        if option.dip_pct not in (3.0, 5.0) or option.cases == 0:
            continue
        verdict = (f"saved {option.mean_saving_pct:.1f}% on average" if option.mean_saving_pct >= 0
                   else f"cost {abs(option.mean_saving_pct):.1f}% more on average")
        lines.append(_row(f"{option.dip_pct:.0f}% dip", f"came {option.reached_pct:.0f}% of the time;"))
        lines.append(_cont(verdict))

    lines.append("")
    lines.append("<i>tgju's 18K market price; our platforms track it closely.</i>")
    lines.append("<i>This is the historical record, not a forecast.</i>")
    return "\n".join(lines)
