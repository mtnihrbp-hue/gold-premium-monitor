"""The gold funds' block, in the words every message shares (SP-D, SP_D_HANDOFF.md sections 46-47).

One reading, analysis/gold_demand.assess, is shown by the evening message, the room's 21:00 report and
Direction's GOLD DEMAND, so the money's "times the usual week" and its verdict are the same everywhere
(CLAUDE.md: the number a reader is shown is the number the system acts on). Presentation formats; the
reading is computed elsewhere. Only <b> and <i>; no bare "<", ">" or "&".
"""

from timeutil import persian_day


def _b(rial):
    return f"{abs(rial) / 1e10:,.0f}B"                  # billion toman


def _times(x):
    return f"{abs(x):.1f} times {'in' if x >= 0 else 'out'}"


def period(demand):
    return "week" if demand.get("window") == 7 else f"{demand.get('window')} sessions"


def usual_phrase(demand):
    """'5.3 times the usual week', or, when the window was net out, what the usual week brings; None
    when there is no usual to compare with (the past year net out)."""
    money, usual = demand["money"].get("value"), demand.get("usual_rial")
    if money is None or not usual or usual <= 0:
        return None
    if demand["net_rial"] >= 0:
        return f"{money:.1f} times the usual {period(demand)}"
    return f"the usual {period(demand)} brings {_b(usual)} in"


def money_line(demand):
    net, state, band = demand["net_rial"], demand["money"].get("state"), demand.get("band")
    line = f"Money: {_b(net)} toman {'in' if net >= 0 else 'out'}"
    usual = usual_phrase(demand)
    if usual is None:
        return line + "; no usual to compare with (the past year was net out)"
    line += f", {usual}" if net >= 0 else f" ({usual})"
    if state == "HIGH" and band:
        return line + f"; above the normal range (up to {band[1]:.1f} times)"
    if state == "LOW" and band:
        return line + f"; below the normal range (down to {_times(band[0])})"
    return line + "; normal range"


def buyers_line(demand):
    people = demand["people"]
    word = {"HIGH": "a rush", "LOW": "few buyers"}.get(people.get("state"), "normal")
    return f"Buyers: {demand['buyers_per_day']:,.0f} a day, {people['value']:.1f} times the usual; {word}"


def per_head_line(demand):
    buy, sell = demand.get("per_head_rial") or (None, None)
    if not buy or not sell:
        return None
    state = demand["size"].get("state")
    who = "sellers" if sell > buy else "buyers"
    note = {"LOW": "sellers far bigger than usual", "HIGH": "buyers far bigger than usual"}.get(state, f"{who} bigger, as usual")
    return f"Per head: buyers {buy / 1e7:,.0f}M, sellers {sell / 1e7:,.0f}M toman ({note})"


def block(demand, title=None):
    """The block's lines, or [] without a complete reading. `title` overrides the heading's span (the
    tablokhani stand-in names its own); by default '7 days to <day>'."""
    if not demand or not all((demand.get(k) or {}).get("state") for k in ("people", "size")):
        return []
    if title is None:
        from datetime import date
        title = f"{demand['window']} days to {persian_day(date.fromisoformat(demand['as_of']))}"
    lines = [f"<b>GOLD FUNDS</b> · individuals, {title}", money_line(demand), buyers_line(demand)]
    per_head = per_head_line(demand)
    if per_head:
        lines.append(per_head)
    return lines
