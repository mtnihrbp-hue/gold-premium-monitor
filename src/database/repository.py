"""Database repository for market snapshot operations.

All database writes are wrapped in transactions.
Read operations return None / [] when the database is unavailable.
"""

from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.connection import get_session
from database.models import (
    MarketSnapshot,
    PlatformPrice,
    MarketHypothesis,
    MarketState,
)


def save_market_snapshot(
    timestamp,
    fair_price,
    premium_percent,
    world_gold_usd=None,
    usd_irr=None,
    signal=None,
    confidence=None,
    platform_prices=None,
):
    """Save a market snapshot and associated platform prices."""
    session = get_session()
    if session is None:
        raise RuntimeError("Database not configured (DATABASE_URL missing)")

    try:
        snapshot = MarketSnapshot(
            timestamp=timestamp,
            fair_price=fair_price,
            premium_percent=premium_percent,
            world_gold_usd=world_gold_usd,
            usd_irr=usd_irr,
            signal=signal,
            confidence=confidence,
        )
        session.add(snapshot)
        session.flush()

        if platform_prices:
            for pp in platform_prices:
                session.add(
                    PlatformPrice(
                        snapshot_id=snapshot.id,
                        platform_name=pp["platform_name"],
                        price_irr=pp["price_irr"],
                        change_irr=pp.get("change_irr"),
                        timestamp=timestamp,
                    )
                )

        session.commit()
        return snapshot.id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_latest_market_snapshot():
    """Return the most recent market snapshot, or None if unavailable."""
    session = get_session()
    if session is None:
        return None
    try:
        return (
            session.query(MarketSnapshot)
            .order_by(MarketSnapshot.timestamp.desc())
            .first()
        )
    finally:
        session.close()


def get_snapshots(days=30):
    """Return market snapshots from the last N days."""
    session = get_session()
    if session is None:
        return []
    try:
        since = datetime.now() - timedelta(days=days)
        return (
            session.query(MarketSnapshot)
            .filter(MarketSnapshot.timestamp >= since)
            .order_by(MarketSnapshot.timestamp.desc())
            .all()
        )
    finally:
        session.close()


# --- Daily Premium Stats (Task C) ---

def get_daily_premium_stats(target_date, session):
    """Return premium statistics for a given calendar day."""
    results = (
        session.query(MarketSnapshot)
        .filter(func.date(MarketSnapshot.timestamp) == target_date)
        .order_by(MarketSnapshot.timestamp.asc())
        .all()
    )
    if not results:
        return None
    premiums = [float(r.premium_percent) for r in results]
    return {
        "avg": round(sum(premiums) / len(premiums), 4),
        "min": round(min(premiums), 4),
        "max": round(max(premiums), 4),
        "count": len(premiums),
        "open": round(premiums[0], 4),
        "close": round(premiums[-1], 4),
    }


def get_premium_momentum_context(current_premium, session):
    """Return full momentum context comparing current premium to daily averages."""
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    today_stats = get_daily_premium_stats(today, session)
    yesterday_stats = get_daily_premium_stats(yesterday, session)

    context = {
        "premium_vs_today": None,
        "premium_vs_yesterday": None,
        "candlestick": None,
        "verbal_direction": "Neutral",
    }

    if today_stats:
        diff = round(current_premium - today_stats["avg"], 4)
        label, emoji = _label_premium_diff(diff)
        context["premium_vs_today"] = {
            "avg": today_stats["avg"],
            "diff": diff,
            "min": today_stats["min"],
            "max": today_stats["max"],
            "count": today_stats["count"],
            "label": label,
            "emoji": emoji,
        }
        context["candlestick"] = {
            "open": today_stats["open"],
            "high": today_stats["max"],
            "low": today_stats["min"],
            "close": today_stats["close"],
            "avg": today_stats["avg"],
        }

    if yesterday_stats:
        diff = round(current_premium - yesterday_stats["avg"], 4)
        label, _ = _label_premium_diff(diff)
        context["premium_vs_yesterday"] = {
            "avg": yesterday_stats["avg"],
            "diff": diff,
            "date": yesterday.strftime("%b %d"),
            "label": label,
        }

    if today_stats:
        diff = current_premium - today_stats["avg"]
    elif yesterday_stats:
        diff = current_premium - yesterday_stats["avg"]
    else:
        diff = 0.0

    context["verbal_direction"] = _verbal_direction(current_premium, diff)
    return context


def _label_premium_diff(diff):
    """Return (label, emoji) for a premium difference."""
    if diff < -0.05:
        return "Discount Deepening", "▼"
    elif diff > 0.05:
        return "Premium Expanding", "▲"
    else:
        return "Stable", "→"


def _verbal_direction(premium, diff):
    """Return verbal momentum direction."""
    if abs(diff) < 0.05:
        return "Neutral"
    if diff < 0:
        return "Toward Buy"
    return "Toward Sell"


# --- Input Directions (Refinement R1) ---

def get_input_directions(world, usd, session):
    """Return direction indicators for world gold and USD."""
    if world is None or usd is None:
        return {
            "world": {"arrow": "→", "pct": 0.0, "stale_count": 0},
            "usd": {"arrow": "→", "pct": 0.0, "stale_count": 0},
        }

    recent = (
        session.query(MarketSnapshot)
        .filter(MarketSnapshot.world_gold_usd.isnot(None))
        .filter(MarketSnapshot.usd_irr.isnot(None))
        .order_by(MarketSnapshot.timestamp.desc())
        .limit(20)
        .all()
    )

    result = {
        "world": {"arrow": "→", "pct": 0.0, "stale_count": 0},
        "usd": {"arrow": "→", "pct": 0.0, "stale_count": 0},
    }

    if not recent:
        return result

    prev_world = float(recent[0].world_gold_usd) if recent[0].world_gold_usd else None
    if prev_world and prev_world != 0:
        pct = ((world - prev_world) / prev_world) * 100
        result["world"]["pct"] = round(pct, 2)
        if abs(pct) < 0.01:
            result["world"]["arrow"] = "→"
        elif pct > 0:
            result["world"]["arrow"] = "↑"
        else:
            result["world"]["arrow"] = "↓"

    prev_usd = float(recent[0].usd_irr) if recent[0].usd_irr else None
    if prev_usd and prev_usd != 0:
        pct = ((usd - prev_usd) / prev_usd) * 100
        result["usd"]["pct"] = round(pct, 2)
        if abs(pct) < 0.01:
            result["usd"]["arrow"] = "→"
        elif pct > 0:
            result["usd"]["arrow"] = "↑"
        else:
            result["usd"]["arrow"] = "↓"

    stale_world = 0
    for r in recent:
        if r.world_gold_usd is not None and abs(float(r.world_gold_usd) - world) < 0.01:
            stale_world += 1
        else:
            break

    stale_usd = 0
    for r in recent:
        if r.usd_irr is not None and abs(float(r.usd_irr) - usd) < 0.01:
            stale_usd += 1
        else:
            break

    result["world"]["stale_count"] = stale_world
    result["usd"]["stale_count"] = stale_usd

    return result


# --- Market Hypotheses (SP3 Foundation) ---

def save_hypothesis(
    session,
    hypothesis_type,
    description,
    expected_outcome=None,
    horizon_hours=None,
    basis_json=None,
    model_version=None,
    source=None,
):
    """Save a new market hypothesis."""
    hypothesis = MarketHypothesis(
        hypothesis_type=hypothesis_type,
        description=description,
        expected_outcome=expected_outcome,
        horizon_hours=horizon_hours,
        basis_json=basis_json,
        predicted_at=datetime.now(),
        model_version=model_version,
        source=source,
    )
    session.add(hypothesis)
    session.flush()
    session.commit()
    return hypothesis.id


def resolve_hypothesis(session, hypothesis_id, actual_outcome, result, failure_reason=None):
    """Resolve a hypothesis with actual outcome."""
    hypothesis = (
        session.query(MarketHypothesis)
        .filter(MarketHypothesis.id == hypothesis_id)
        .first()
    )
    if not hypothesis:
        return False
    hypothesis.resolved_at = datetime.now()
    hypothesis.actual_outcome = actual_outcome
    hypothesis.result = result
    hypothesis.failure_reason = failure_reason
    session.commit()
    return True


def get_hypothesis_accuracy(session, hypothesis_type=None, days=30):
    """Return accuracy stats for hypotheses."""
    since = datetime.now() - timedelta(days=days)
    query = session.query(MarketHypothesis).filter(
        MarketHypothesis.resolved_at >= since,
        MarketHypothesis.result.isnot(None),
    )
    if hypothesis_type:
        query = query.filter(MarketHypothesis.hypothesis_type == hypothesis_type)

    results = query.all()
    if not results:
        return None

    total = len(results)
    correct = sum(1 for r in results if r.result == "Correct")
    partial = sum(1 for r in results if r.result == "Partially Correct")
    wrong = sum(1 for r in results if r.result == "Wrong")
    weighted = (correct + partial * 0.5) / total if total else 0

    return {
        "total": total,
        "correct": correct,
        "partially_correct": partial,
        "wrong": wrong,
        "accuracy_rate": round(weighted, 4),
    }


# --- SP-A: Market State Persistence ---

def save_market_state(state: "SignalState") -> int:
    """Persist a SignalState to the market_states table.

    Args:
        state: populated SignalState dataclass

    Returns:
        id of persisted MarketState record
    """
    session = get_session()
    if session is None:
        raise RuntimeError("Database not configured (DATABASE_URL missing)")

    try:
        db_state = MarketState(
            snapshot_id=state.snapshot_id,
            valuation_state=state.valuation,
            momentum_state=state.momentum,
            premium_direction=state.premium_direction,
            structure_state=state.structure,
            platform_average=state.platform_average,
            platform_high=state.platform_high,
            platform_low=state.platform_low,
            platform_spread=state.platform_spread,
            platforms_below_fair=state.platforms_below_fair,
            platforms_above_fair=state.platforms_above_fair,
            conflict_state=state.conflict,
            candidate_decision=state.candidate_decision,
            final_decision=state.final_decision,
            reason=state.reason,
            timestamp=state.timestamp,
        )
        session.add(db_state)
        session.commit()
        session.refresh(db_state)
        return db_state.id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_latest_market_state():
    """Fetch the most recent market state.

    Returns:
        latest MarketState or None if table is empty
    """
    session = get_session()
    if session is None:
        return None
    try:
        return (
            session.query(MarketState)
            .order_by(MarketState.timestamp.desc())
            .first()
        )
    finally:
        session.close()
