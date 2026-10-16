"""The record kept while the database cannot be written (SP-D, SP_D_HANDOFF.md section 35.4).

From 2026-10-13 21:00 Tehran Neon refused every connection (its free plan's monthly transfer was
spent, section 34), and what each run collected was lost: about 16 readings a day of the hourly
record, the room's daily inputs, Tether's history. A write that fails because the database is out of
reach is held here instead, one JSON line per write, in the file RECORD_SPOOL_FILE names -- the
workflow keeps it in its cache beside state.json -- and the next scheduled run that reaches the
database writes it back, oldest first and with its original time, as the phone's node does with its
own readings.

Only an unreachable database is held: a row the database rejects would be rejected again. Unset
(tests, local runs), nothing is held.
"""

import json
import os
import time
from datetime import date, datetime

MAX_BYTES = 20_000_000       # about two months of the record; beyond it a write is not held
# News is held too (the owner, 2026-10-16: "spool"; SP_D_HANDOFF.md section 37.13): about 0.7 MB a day
# against the record's 0.1 MB, so it stops here and leaves the rest, about 40 days, to the record.
NEWS_MAX_BYTES = 16_000_000
FLUSH_SECONDS = 240          # a run writes held entries for at most this long; the rest wait
BATCH = 50                   # observations and news go in batches; a reading or a day's input one at a time
BATCHED = ("observation", "news")


def _path():
    return os.environ.get("RECORD_SPOOL_FILE") or None


def unreachable(error):
    """True when `error` is the database out of reach (refused, suspended, dropped), not a row it
    rejects."""
    from sqlalchemy.exc import InterfaceError, OperationalError
    return isinstance(error, (OperationalError, InterfaceError))


def _encode(value):
    if isinstance(value, datetime):
        return {"__datetime__": value.isoformat()}
    if isinstance(value, date):
        return {"__date__": value.isoformat()}
    raise TypeError(f"{type(value).__name__} cannot be held")


def _decode(obj):
    if "__datetime__" in obj:
        return datetime.fromisoformat(obj["__datetime__"])
    if "__date__" in obj:
        return date.fromisoformat(obj["__date__"])
    return obj


def hold(kind, payload):
    """Keep one write for later: "reading", "observation", "candles" or "news". True when held."""
    path = _path()
    if path is None:
        return False
    try:
        limit = NEWS_MAX_BYTES if kind == "news" else MAX_BYTES
        if os.path.exists(path) and os.path.getsize(path) > limit:
            if kind != "news":      # news counts what it could not hold itself (collector/news/ingest.py)
                print(f"SPOOL full ({limit:,} bytes): a {kind} was not held")
            return False
        line = json.dumps({"kind": kind, "payload": payload}, default=_encode, separators=(",", ":"))
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return True
    except (OSError, TypeError, ValueError) as e:
        print(f"SPOOL: a {kind} was not held: {e}")
        return False


def held():
    """The held writes, oldest first."""
    path = _path()
    if path is None or not os.path.exists(path):
        return []
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    entries.append(json.loads(line, object_hook=_decode))
                except ValueError:
                    print("SPOOL: an unreadable line skipped")
    return entries


def held_keys(kind, field):
    """The values of `field` among the held entries of `kind`: the news ingestion's dedup keys, so an
    item every run fetches again is held once."""
    return {e["payload"].get(field) for e in held() if e["kind"] == kind and e["payload"].get(field)}


def _keep(path, entries):
    try:
        if not entries:
            if os.path.exists(path):
                os.remove(path)
            return
        with open(path, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, default=_encode, separators=(",", ":")) + "\n")
    except OSError as e:
        print(f"SPOOL: not rewritten: {e}")


def flush(session, writers, entries, clock=time.monotonic):
    """Write `entries` (held()) through `writers` {kind: fn(session, payload)}, oldest first, for
    at most FLUSH_SECONDS, committing each reading and day's input alone and observations in
    batches. A rejected batch is retried one write at a time and a rejected write dropped; an
    unreachable database stops the flush. What was not written stays held. Returns (written,
    dropped, left)."""
    path = _path()
    start, k, written, dropped = clock(), 0, 0, 0

    def run(unit):
        try:
            for e in unit:
                writers[e["kind"]](session, e["payload"])
            session.commit()
            return "ok", None
        except Exception as error:  # noqa: BLE001 -- sorted below: unreachable stops, rejected drops
            session.rollback()
            return ("unreachable" if unreachable(error) else "rejected"), error

    try:
        while k < len(entries) and clock() - start < FLUSH_SECONDS:
            kind = entries[k]["kind"]
            size = 1
            if kind in BATCHED:
                while size < BATCH and k + size < len(entries) and entries[k + size]["kind"] == kind:
                    size += 1
            result, error = run(entries[k:k + size])
            if result == "ok":
                written, k = written + size, k + size
                continue
            if result == "unreachable":
                print(f"SPOOL: the database went out of reach: {str(error).strip().splitlines()[0][:160]}")
                break
            stopped = False
            for e in entries[k:k + size]:
                one, error = run([e])
                if one == "unreachable":
                    stopped = True
                    break
                if one == "ok":
                    written += 1
                else:
                    dropped += 1
                    print(f"SPOOL: a held {e['kind']} was rejected and dropped: {str(error).strip().splitlines()[0][:160]}")
                k += 1
            if stopped:
                print("SPOOL: the database went out of reach")
                break
    finally:
        if path is not None:
            _keep(path, entries[k:])
    return written, dropped, len(entries) - k
