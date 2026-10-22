"""The SERVICE message: a push when a service stops or comes back, and the line Telegram's Status shows
(SP-D, SP_D_HANDOFF.md section 37.15). The wording was previewed to the owner on 2026-10-16 ("go ahead
with the outage notice"): plain words, Tehran time, what still works and what waits.
"""

from datetime import datetime, timedelta

from timeutil import persian_day, to_tehran

TITLE = "<b>GOLDPremium: SERVICE</b>"
QUOTA = "data transfer quota"          # Neon's words when the free plan's monthly transfer is spent


def _at(value, now):
    """ "21:00" on the same Tehran day as `now`, else "21 Mehr, 21:00"."""
    local, today = to_tehran(value), to_tehran(now)
    clock = local.strftime("%H:%M")
    return clock if local.date() == today.date() else f"{persian_day(local.date())}, {clock}"


def _after(start, now):
    """How long it lasted, in words: "after 18 days", "after 3 hours"."""
    hours = (now - start).total_seconds() / 3600
    if hours >= 48:
        return f"after {round(hours / 24)} days"
    if hours >= 2:
        return f"after {round(hours)} hours"
    return "after about an hour"


def _first_of_next_month(now):
    """Neon's monthly allowance resets on the first of the month (UTC)."""
    year, month = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
    return datetime(year, month, 1)


def _count(n, one, many):
    return f"{n:,} {one if n == 1 else many}"


def build_message(name, change, record, now, kept=None, left=None, mirror_built=False):
    """The push for one service's change. `kept` and `left` count the spool's held writes by kind
    ({"reading": n, "news": n}): kept while the database was out of reach, and still to be written."""
    local = to_tehran(now)
    lines = [f"{TITLE} · {persian_day(local.date())}, {local:%H:%M}"]
    since = datetime.fromisoformat(record["since"]) if record.get("since") else now
    if name == "database" and change == "down":
        quota = QUOTA in (record.get("reason") or "")
        lines.append(f"The database is out of reach since {_at(since, now)}"
                     + (" (its free monthly limit)." if quota else "."))
        lines.append("Working: UPDATE, DIRECTION, the 21:00 chart.")
        paused = ["ANALYZE", "the discount push", "the room's report"] + ([] if mirror_built else ["BUY signals"])
        lines.append("Paused: " + ", ".join(paused) + ".")
        lines.append("Prices and news are still collected and kept.")
        if quota:
            lines.append(f"Expected back: {persian_day(to_tehran(_first_of_next_month(now)).date())}.")
    elif name == "database":
        start = datetime.fromisoformat(record["was_since"]) if record.get("was_since") else since
        lines.append(f"The database is back, {_after(start, now)}.")
        kept, left = kept or {}, left or {}
        readings, news = kept.get("reading", 0), kept.get("news", 0)
        if readings or news:
            what = ", ".join(x for x in (_count(readings, "reading", "readings") if readings else "",
                                         _count(news, "news item", "news items") if news else "") if x)
            waiting = sum(left.values())
            lines.append(f"Kept meanwhile, now written: {what}." if not waiting
                         else f"Kept meanwhile: {what}; {_count(waiting, 'more is', 'more are')} still being written.")
        lines.append("ANALYZE, the push and the room's report work again.")
    elif name == "world gold" and change == "down":
        if record.get("reason") == "fallback":
            lines.append(f"World gold has not updated since {_at(since, now)}; its last price is used.")
            lines.append("Parity and the discount may be off until it updates.")
        else:
            lines.append(f"World gold is unavailable since {_at(since, now)}; the discount is not computed.")
    elif name == "world gold":
        start = datetime.fromisoformat(record["was_since"]) if record.get("was_since") else since
        lines.append(f"World gold is updating again, {_after(start, now)}.")
    elif name == "dollar" and change == "down":
        lines.append(f"The dollar rate is unavailable since {_at(since, now)}; the discount is not computed.")
    elif name == "dollar":
        start = datetime.fromisoformat(record["was_since"]) if record.get("was_since") else since
        lines.append(f"The dollar rate is updating again, {_after(start, now)}.")
    elif name == "platforms" and change == "down":
        lines.append(f"Only {record.get('count', 0)} of {record.get('total', 0)} platforms answered since "
                     f"{_at(since, now)}; the discount needs three.")
    else:
        start = datetime.fromisoformat(record["was_since"]) if record.get("was_since") else since
        lines.append(f"The platforms answer again: {record.get('count', 0)} of {record.get('total', 0)}, "
                     f"{_after(start, now)}.")
    return "\n".join(lines)


def status_line(state, now):
    """The line Telegram's Status adds: every service working, or which are not and since when."""
    from analysis.service import down
    out = []
    for name, rec in down(state).items():
        since = _at(datetime.fromisoformat(rec["since"]), now) if rec.get("since") else "now"
        out.append({"database": "the database out of reach", "world gold": "world gold not live",
                    "dollar": "the dollar rate unavailable",
                    "platforms": "too few platforms answering"}[name] + f" since {since}")
    return "Service: all working." if not out else "Service: " + "; ".join(out) + "."


def send_service(text):
    from alerts.telegram import _send
    _send(text)
