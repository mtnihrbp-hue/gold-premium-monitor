"""A copy of the recent record for the reads a run makes while Neon is out of reach (SP-D,
SP_D_HANDOFF.md section 37.12).

From 2026-10-13 Neon refused every connection for 18 days (its free plan's monthly transfer, section
34). The spool (spool.py) kept what the runs wrote, but what they read failed:
- the stale-quote rules ran without history;
- the valuation leg abstained;
- the confirmation held every BUY;
- UPDATE lost its rank, its deep-discount level and its baselines.

Those reads need only the last 60 days of two tables, market_snapshots and their platform_prices. So
a scheduled run that reaches Neon copies them into a SQLite file (RECORD_MIRROR_FILE, which the
workflow caches beside state.json), and a run that cannot reach Neon reads them from there.

- **Opt-in.** Only the readers that ask for `read_session()` use the copy. Writers keep
  `get_session()`, so a write still fails as unreachable and goes to the spool. The deep-discount push
  (parked by the owner during an outage), PAPER and ANALYZE stay as they are without Neon.
- **Read-only.** A session on the copy refuses to write.
- **Held readings.** A reading the spool holds is also added to the copy under a negative id, so the
  next run's reads see it. Once Neon answers again, the copy is rebuilt from it, which drops them.
- **Refreshed.** Copied in full weekly, and otherwise only the readings added since, so a row Neon
  corrects in place reaches the copy within a week.

Unset (tests, local runs), `read_session()` is `get_session()` and nothing is copied.
"""

import os
from datetime import datetime, timedelta

WINDOW_DAYS = 61          # the stale-quote rule reads 60 days back (validation/data.py); the valuation pool 30
REBUILD_DAYS = 7          # a full copy at least this often

_reachable = None         # Neon probed once per process: True, False, or None before the probe
_reason = ""              # the probe's error when Neon did not answer (the SERVICE notice reads it)
_engine = None
_meta = None


def _path():
    return os.environ.get("RECORD_MIRROR_FILE") or None


def enabled():
    return _path() is not None


def _tables():
    """The copy's tables: the two the outage-sensitive readers query, and a small key-value table."""
    global _meta
    from sqlalchemy import Column, MetaData, String, Table
    from database.models import MarketSnapshot, PlatformPrice
    if _meta is None:
        _meta = Table("mirror_meta", MetaData(), Column("key", String(40), primary_key=True),
                      Column("value", String(40)))
    return MarketSnapshot.__table__, PlatformPrice.__table__, _meta


def _mirror_engine():
    global _engine
    from sqlalchemy import create_engine
    if _engine is None or _engine.url.database != _path():
        _engine = create_engine(f"sqlite:///{_path()}")
        snap, prices, meta = _tables()
        for table in (snap, prices, meta):
            table.create(_engine, checkfirst=True)
    return _engine


def reachable():
    """True when Neon answers a trivial query. Probed once per process; a run that starts with Neon
    out of reach is treated as out of reach throughout, as its writes already are."""
    global _reachable, _reason
    if _reachable is None:
        from sqlalchemy import text
        from database import connection
        from persistence.spool import unreachable
        engine = connection.get_engine()
        if engine is None:
            _reachable = False
        else:
            try:
                with engine.connect() as c:
                    c.execute(text("SELECT 1"))
                _reachable = True
            except Exception as e:  # noqa: BLE001 -- anything but an unreachable database reads as usual
                _reachable = not unreachable(e)
                _reason = str(e).strip().splitlines()[0][:300] if str(e).strip() else type(e).__name__
    return _reachable


def unreachable_reason():
    """Why the probe found Neon out of reach ("" when it answered or was not probed)."""
    return _reason


def _built_at(conn):
    from sqlalchemy import select
    _, _, meta = _tables()
    value = conn.execute(select(meta.c.value).where(meta.c.key == "built_at")).scalar()
    return datetime.fromisoformat(value) if value else None


def built_at():
    """When the copy was last made in full from Neon, or None."""
    if not enabled() or not os.path.exists(_path()):
        return None
    try:
        with _mirror_engine().connect() as c:
            return _built_at(c)
    except Exception:  # noqa: BLE001
        return None


def _read_only(session, flush_context, instances):
    if session.new or session.dirty or session.deleted:
        raise RuntimeError("the record mirror is read-only")


def read_session():
    """A session for the reads that can be served from the copy: Neon's when it answers, the copy's
    when it does not and a copy exists, and otherwise Neon's (which then fails as it always has)."""
    from database import connection
    if not enabled() or reachable() or built_at() is None:
        return connection.get_session()
    from sqlalchemy import event
    from sqlalchemy.orm import sessionmaker
    session = sessionmaker(bind=_mirror_engine())()
    event.listen(session, "before_flush", _read_only)
    return session


def refresh(session, now=None):
    """Bring the copy up to date from Neon through `session`. Returns the rows copied, or None when
    unset or when the copy fails (the run goes on: the copy only serves the next outage)."""
    if not enabled():
        return None
    from sqlalchemy import func, select
    now = now or datetime.utcnow()
    since = now - timedelta(days=WINDOW_DAYS)
    snap, prices, meta = _tables()
    try:
        engine = _mirror_engine()
        with engine.begin() as m:
            built = _built_at(m)
            held = m.execute(select(func.count()).select_from(snap).where(snap.c.id < 0)).scalar()
            full = built is None or now - built >= timedelta(days=REBUILD_DAYS) or held > 0
            if full:
                m.execute(prices.delete())
                m.execute(snap.delete())
                after = 0
            else:
                after = m.execute(select(func.max(snap.c.id))).scalar() or 0
            new_snaps = [dict(r) for r in session.execute(
                select(snap).where(snap.c.timestamp >= since, snap.c.id > after).order_by(snap.c.id)).mappings()]
            new_prices = [dict(r) for r in session.execute(
                select(prices).select_from(prices.join(snap, prices.c.snapshot_id == snap.c.id))
                .where(snap.c.timestamp >= since, snap.c.id > after).order_by(prices.c.id)).mappings()]
            if new_snaps:
                m.execute(snap.insert(), new_snaps)
            if new_prices:
                m.execute(prices.insert(), new_prices)
            old = select(snap.c.id).where(snap.c.timestamp < since)
            m.execute(prices.delete().where(prices.c.snapshot_id.in_(old)))
            m.execute(snap.delete().where(snap.c.timestamp < since))
            stamps = {"refreshed_at": now.isoformat()}
            if full:
                stamps["built_at"] = now.isoformat()
            for key, value in stamps.items():
                m.execute(meta.delete().where(meta.c.key == key))
                m.execute(meta.insert(), [{"key": key, "value": value}])
        return len(new_snaps) + len(new_prices)
    except Exception as e:  # noqa: BLE001
        print(f"MIRROR not refreshed: {str(e).strip().splitlines()[0][:200]}")
        return None


def add_held(snapshot, platform_prices):
    """Add a reading the spool holds, so the next run's reads see it. Only into a copy made from Neon:
    a copy of the outage alone would rank today's reading against a few hours. True when added."""
    if not enabled() or built_at() is None:
        return False
    from sqlalchemy import func, select
    snap, prices, _ = _tables()
    fields = ("timestamp", "fair_price", "premium_percent", "world_gold_usd", "usd_irr", "signal",
              "confidence", "collection_mode")
    try:
        with _mirror_engine().begin() as m:
            snapshot_id = min(m.execute(select(func.min(snap.c.id))).scalar() or 0, 0) - 1
            price_id = min(m.execute(select(func.min(prices.c.id))).scalar() or 0, 0)
            m.execute(snap.insert(), [{"id": snapshot_id, **{k: snapshot.get(k) for k in fields}}])
            rows = []
            for row in platform_prices:
                price_id -= 1
                rows.append({"id": price_id, "snapshot_id": snapshot_id, "platform_name": row["platform_name"],
                             "price_irr": row["price_irr"], "change_irr": row.get("change_irr"),
                             "timestamp": snapshot["timestamp"]})
            if rows:
                m.execute(prices.insert(), rows)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"MIRROR: a held reading was not added: {e}")
        return False
