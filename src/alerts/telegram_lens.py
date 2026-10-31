"""GOLDPremium: LENS, the nightly read (SP_D_HANDOFF.md sections 84-86; previewed to the owner 2026-10-31, the AI
model's part approved the same day). Formats analysis/lens.build_view; computes nothing.

Four blocks: NOW against the last close; THE EVENT, the ceasefire's real-money odds and the day's headlines toward
a strike or a deal (picked and translated by the model, never written by it); WHAT FOLLOWED BEFORE, the case
library against any day; the READ, from the numbers. Persian dates only; the vocabulary of
skills/telegram-product.md."""

from datetime import date

from alerts.helpers import format_m_tomans_short
from alerts.telegram import _send
from timeutil import persian_day

TITLE = "<b>GOLDPremium: LENS</b>"
FOOTER = "<i>Decision support, not an instruction to trade.</i>"


def _signed(value):
    return f"{value:+.1f}%".replace("-", "−") if value is not None else "n/a"


def _tomans(rials):
    return f"{rials / 10:,.0f}" if rials else "n/a"


def _day(iso, year=False):
    return persian_day(date.fromisoformat(iso) if isinstance(iso, str) else iso, year=year)


def _gap(value):
    if value is None:
        return None
    side = "Premium" if value > 0 else "Discount"
    return f"{side} {abs(value):.1f}% {'above' if value > 0 else 'below'} world price"


def _now(m):
    if not m:
        return ["<b>NOW</b>", "<i>tgju's closes could not be read tonight.</i>"]
    lines = [f"<b>NOW</b> vs the last close ({_day(m['ref_date'])})",
             f"18K {format_m_tomans_short(m['price'])} (market, tgju): {_signed(m['price_pct'])}" if m["price"] else
             "18K: the platforms could not be read",
             f"World gold ${m['world']:,.0f}: {_signed(m['world_pct'])}" if m["world"] else "World gold: not read",
             f"USD/IRR {_tomans(m['usd'])}: {_signed(m['usd_pct'])}" if m["usd"] else "USD/IRR: not read"]
    if m["tether"]:
        lines.append(f"Tether {_tomans(m['tether'])}: {_signed(m['tether_pct'])}"
                     + (", the highest on record" if m["tether_record"] else ""))
    gap = _gap(m["gap_now"])
    if gap:
        then = m["gap_then"]
        lines.append(gap + (f" (was {abs(then):.1f}% {'above' if then > 0 else 'below'})" if then is not None else ""))
    return lines


def _in100(p):
    return (round(p * 1000) + 5) // 10           # half up, as a reader rounds: 74.5 in 100 reads 75


def _event(v):
    lines = ["<b>THE EVENT</b>"]
    if v["odds"]:
        parts = [f"to {_day(end)}: {_in100(holds)} in 100" + (f" (was {_in100(was)})" if was is not None
                                                            and _in100(was) != _in100(holds) else "")
                 for end, holds, was in v["odds"]]
        lines += ["Ceasefire holds " + "; ".join(parts), "<i>Real-money odds, Polymarket</i>"]
    else:
        lines.append("<i>No market priced the ceasefire tonight.</i>")
    news = v["news"]
    if news is None:
        lines.append("<i>The headlines were not read tonight.</i>")
    elif not news.get("strike") and not news.get("deal"):
        lines.append(f"No headline of {v['headlines']} pointed either way.")
    else:
        for side, label in (("strike", "Toward a strike:"), ("deal", "Toward a deal:")):
            if news.get(side):
                lines.append(label)
                lines += [f"· {en}" for _, en in news[side]]
    return lines


def _cases(v):
    s, d, base = v["strikes"], v["deals"], v["base"]
    if not s:
        return []
    since = _day(v["first_case"], year=True).split()[-1]
    lines = [f"<b>WHAT FOLLOWED BEFORE</b> (since {since})",
             f"{s['n']} strikes: 18K higher 40 days later in {s['higher']} (any day: {round(s['base_share'] * 100)} in "
             f"100); typical move {s['typical_abs']:.1f}% (any day: {s['base_typical']:.1f}%)"]
    if s["lower"]:
        each = ", ".join(f"{_signed(c['gold18_40'])} ({_day(c['date'], year=True)})" for c in s["lower"])
        lines.append(f"Lower in {len(s['lower'])}" + (", each when the dollar dropped" if s["lower_with_dollar_down"]
                                                      else "") + f": {each}")
    if d:
        line = f"{d['n']} deals: 18K higher 40 days later in {d['higher']}; typical move {d['typical_abs']:.1f}%"
        worst = d["worst_first_week"]
        if worst:
            line += f"; the worst first week {_signed(worst['gold18_5'])} ({_day(worst['date'], year=True)})"
            if (worst.get("gold18_10") or 0) > 0:
                line += ", back above within 10 days"
        lines.append(line)
    if s["shut"]:
        days = " and ".join(str(c["shut_days"]) for c in s["shut"])
        lines.append(f"The market shut for {days} days in the last {len(s['shut'])} wars")
    return lines


def _read(f):
    lines = []
    if f.get("strikes_usual"):
        lines.append("Past strikes did not change 18K's usual direction"
                     + ("; they made the moves bigger." if f.get("strikes_bigger") else "."))
    if f.get("driver") == "world":
        lines.append("Today's move comes from world gold, not the dollar.")
    elif f.get("driver") == "dollar":
        lines.append("Today's move comes from the dollar, not world gold.")
    if f.get("shut_caution"):
        lines.append("A move to fixed income has to come before a strike: the market may shut.")
    return ["<b>READ</b>"] + lines if lines else []


def build_lens_message(v):
    head = f"{TITLE} · {persian_day(v['at'].date())}, {v['at']:%H:%M}"
    blocks = [[head], _now(v["market"]), _event(v), _cases(v), _read(v["flags"]), [FOOTER]]
    return "\n\n".join("\n".join(b) for b in blocks if b)


def send_lens(text):
    _send(text)
