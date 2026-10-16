"""Which services the scheduled runs find working, and when that changes (SP-D, SP_D_HANDOFF.md section
37.15).

The owner, 2026-10-16: "the user should be informed of any possible outage, it can either be retrieved
through the status command as we have on tlgrm or a push msg"; then "go ahead with the outage notice".
Telegram's Status reported the latest GitHub run, and every run of the Neon outage finished green.

Four services, seen by every scheduled run right after it collects:
  database     Neon answers
  world gold   a live quote, not the stored fallback
  dollar       bonbast answered
  platforms    at least three platforms answered: UPDATE's discount is the mean of the three cheapest

A change is announced once, when two scheduled runs in a row agree (CONFIRM_RUNS), so one failed read
does not alarm. Each service starts as working, so an outage already under way is announced by the
second run that sees it. The state is kept in state.json under "service". Pure: it reads nothing and
sends nothing.
"""

from datetime import datetime

CONFIRM_RUNS = 2
MIN_PLATFORMS = 3          # bubble_position.CHEAP_BASIS_COUNT: the basis needs three platforms
SERVICES = ("database", "world gold", "dollar", "platforms")


def observe(world, world_from_fallback, usd, raw_markets, database_ok, database_reason="", first_held=None):
    """This run's view of each service. `first_held` is the oldest write the spool holds: while the
    database is out of reach it dates the outage better than the first run that saw it."""
    working = sum(1 for info in (raw_markets or {}).values() if info.get("status") == "OK")
    return {
        "database": {"ok": bool(database_ok), "reason": database_reason or "",
                     "since_hint": first_held.isoformat() if isinstance(first_held, datetime) else None},
        "world gold": {"ok": world is not None and not world_from_fallback,
                       "reason": "fallback" if world is not None else "none"},
        "dollar": {"ok": usd is not None},
        "platforms": {"ok": working >= MIN_PLATFORMS, "count": working, "total": len(raw_markets or {})},
    }


def update(state, observed, now):
    """Advance each service by this run. Returns the changes to announce, as (service, "down" or "back",
    record), where record carries "since" (when the new state began), "was_since" (when the old one
    began) and this run's details."""
    changes = []
    for name in SERVICES:
        seen = observed.get(name)
        if seen is None:
            continue
        rec = state.setdefault(name, {"ok": True, "since": None, "pending": 0, "pending_since": None})
        details = {k: v for k, v in seen.items() if k not in ("ok", "since_hint")}
        rec["last"] = details
        if seen["ok"] == rec["ok"]:
            rec["pending"], rec["pending_since"] = 0, None
            continue
        if rec["pending"] == 0:
            rec["pending_since"] = now.isoformat()
        rec["pending"] += 1
        if rec["pending"] < CONFIRM_RUNS:
            continue
        since = rec["pending_since"]
        hint = seen.get("since_hint")
        if not seen["ok"] and hint and hint < since:
            since = hint
        was_since = rec.get("since")
        rec.update(ok=seen["ok"], since=since, pending=0, pending_since=None)
        changes.append((name, "back" if seen["ok"] else "down", {"since": since, "was_since": was_since, **details}))
    return changes


def down(state):
    """The services announced as not working: {name: record}."""
    return {name: rec for name, rec in state.items() if name in SERVICES and not rec.get("ok", True)}
