"""GOLDPremium: NIGHT, the one nightly message (locked by the owner on 2026-11-08; SP_D_HANDOFF.md 105.4, 106.3 and 109).
Formats analysis/nightly and analysis/lens; computes nothing.

The day against its last close, the next 3 days, the gold funds' week, the event as the LENS sends it, and the room
as how much. Replaces the PAPER report's text and the LENS; the chart goes as its own photo. /Analyze pulls the same
message with the time of the pull: never recorded, never scored. Persian dates only; the vocabulary of
skills/telegram-product.md. Only <b> and <i>; no bare "<", ">" or "&".
"""

from datetime import date

from alerts.helpers import format_m_tomans_short as _m
from alerts.telegram import _send
from alerts.telegram_lens import FOOTER, _day, _event, _signed, _tomans, _vs
from timeutil import persian_day

TITLE = "<b>GOLDPremium: NIGHT</b>"
MESSAGE_LIMIT = 4000                      # Telegram refuses a message over 4,096 characters
UNKNOWN = "<i>Unknown tonight.</i>"
EARLY = "<i>Early look. Only the 21:00 report is recorded and scored.</i>"
LATER = "<i>These numbers are from now. Only the 21:00 report is recorded and scored.</i>"
# who is selling, in a week and in the week before; "big holders among them": they are the same individuals (105.4)
NOW_WORDS = {"SELLERS": "Big holders among them are selling this week.",
             "BUYERS": "Big holders among them are selling no more than usual this week.",
             "CROWDED": "Big buyers crowded in this week."}
LAST_WORDS = {"SELLERS": "big holders among them were selling",
              "BUYERS": "big holders among them sold no more than usual",
              "CROWDED": "big buyers crowded in"}


def _gap_words(value):
    return f"{abs(value):.1f}% {'above' if value > 0 else 'below'}"


def _discount(d, ref):
    if d is None or d.get("now") is None:
        return f"Discount not read ({(d or {}).get('index', 'WallGold')})"
    side = "Premium" if d["now"] > 0 else "Discount"
    line = f"{side} {_gap_words(d['now'])} world price"
    if d.get("then") is not None:
        line += f" (was {_gap_words(d['then'])} at the close of {_day(ref)})"
    return line


def _now(v):
    m = v["market"]
    if not m:
        return ["<b>NOW</b>", "<i>tgju's closes could not be read.</i>"]
    lines = [f"<b>NOW</b> vs the close of {_day(m['ref_date'])}",
             _vs(f"18K {_m(m['price'])} (market, tgju)", m["price_pct"]) if m["price"] else "18K: the platforms could not be read",
             _vs(f"World gold ${m['world']:,.0f}", m["world_pct"]) if m["world"] else "World gold: not read",
             _vs(f"USD/IRR {_tomans(m['usd'])}", m["usd_pct"]) if m["usd"] else "USD/IRR: not read"]
    if m["tether"]:
        lines.append(_vs(f"Tether {_tomans(m['tether'])}", m["tether_pct"]) + (", the highest on record" if m["tether_record"] else ""))
    lines.append(_discount(v.get("discount"), m["ref_date"]))
    return lines


def _base_words(base, pull):
    return f"{_m(base)} now" if pull else f"tonight's {_m(base)}"


def _next(v):
    t = v.get("three_day")
    if not t:
        return ["<b>NEXT 3 DAYS</b>", UNKNOWN]
    return ["<b>NEXT 3 DAYS</b>",
            f"18K, 3 days from now vs {_base_words(t['base'], v.get('pull'))}: {t['chance_higher']}% to close higher; "
            f"{t['chance_above']}% to close above {_m(t['floor'])} ({_signed(t['floor_pct'])})."]


def _span(first, last):
    """'Sat 9 – Tue 12 Aban', the month once when both days share it."""
    a, b = persian_day(first), persian_day(last)
    if a.split()[1] == b.split()[1]:
        a = a.split()[0]
    return f"{first:%a} {a} – {last:%a} {b}"


def _plain_span(first, last):
    a, b = persian_day(first), persian_day(last)
    if a.split()[1] == b.split()[1]:
        a = a.split()[0]
    return f"{a}–{b}"


def _sessions(n):
    return f"{n} session{'' if n == 1 else 's'}"


def _money(f):
    def amount(rial):
        return f"{abs(rial) / 1e10:,.0f}B"
    line = f"Money: individuals {'put in' if f['net'] >= 0 else 'took out'} {amount(f['net'])} toman"
    usual = f.get("usual_net")
    if usual is None:
        return line
    n = f["n"]
    who = "a usual week" if n == 5 else "a usual first session" if n == 1 else f"the usual first {n} sessions"
    verb = ("brings" if usual >= 0 else "takes") if n in (1, 5) else ("bring" if usual >= 0 else "take")
    return f"{line}; {who} {verb} {amount(usual)} {'in' if usual >= 0 else 'out'}"


def _funds(v):
    f, line = v.get("funds"), v.get("funds_line")
    head = "<b>GOLD FUNDS</b>"
    if not f:
        return [head, UNKNOWN]
    if not f["n"]:
        lines = [f"{head} · no session of this week read yet"]
    else:
        days = f["sessions"]
        span = f"{days[0]:%a} {persian_day(days[0])}" if f["n"] == 1 else _span(days[0], days[-1])
        extra = _sessions(f["n"])
        if f["today_missing"]:
            extra += f"; {f['today']:%A}'s not read yet"
        lines = [f"{head} · this week{'' if f['finished'] else ' so far'}, {span} ({extra})",
                 _money(f)]
        buyers = f"Buyers: {f['buyers']:,.0f} a day"
        lines.append(buyers + (f", {f['buyers_word']}" if f.get("buyers_word") else ""))
        lines.append(f"Per head: sellers {f['sell_head'] / 1e7:,.0f}M toman, buyers {f['buy_head'] / 1e7:,.0f}M")
    if line:
        verb = f"{line['chance']}% to {line['side']} to {_m(line['level'])} ({_signed(line['level_pct'])})"
        lines.append(f"{NOW_WORDS[line['zone']]} Next trade week vs {_base_words(line['base'], v.get('pull'))}: "
                     f"{line['lower']}% to close lower (typical {line['typical_lower']}%); {verb}.")
    elif f["last_zone"]:
        first, last = f["last_week"]
        lines.append(f"Too early to call this week. Last week ({_plain_span(first, last)}), {LAST_WORDS[f['last_zone']]}.")
    else:
        lines.append("Too early to call this week.")
    return lines


def _room(r):
    head = "<b>THE ROOM</b> (PAPER)"
    if not r:
        return [head, UNKNOWN]
    since = f" since {persian_day(date.fromisoformat(r['since']))}" if r.get("since") else ""
    if r.get("afran"):
        return [head, f"{_m(r['gold'], 1)} toman in gold ({r['grams']} g), {_m(r['afran'], 1)} in Afran (fixed income){since} · "
                      f"total {_m(r['total'], 1)}"]
    return [head, f"{_m(r['total'], 1)} toman, all in gold ({r['grams']} g){since}"]


def build_nightly_message(v):
    head = [f"{TITLE} · {persian_day(v['at'].date())}, {v['at']:%H:%M}"]
    if v.get("pull"):
        head.append(EARLY if v["at"].hour < 21 else LATER)
    blocks = [head, _now(v), _next(v), _funds(v), _event(v), _room(v.get("room")), [FOOTER]]
    return "\n\n".join("\n".join(b) for b in blocks if b)


def parts(text):
    """The message in pieces Telegram will take, cut between its blocks: a night of many headlines must not be lost."""
    out, current = [], ""
    for block in text.split("\n\n"):
        candidate = f"{current}\n\n{block}" if current else block
        if current and len(candidate) > MESSAGE_LIMIT:
            out.append(current)
            current = block
        else:
            current = candidate
    return out + [current] if current else out


def send_nightly(text):
    for part in parts(text):
        _send(part)
