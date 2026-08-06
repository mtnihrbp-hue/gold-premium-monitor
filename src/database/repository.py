"""Database repository for market snapshot operations."""

from datetime import datetime, timedelta

from sqlalchemy import func

from database.connection import get_session
from database.models import MarketSnapshot, PlatformPrice, MarketHypothesis


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


def get_daily_premium_stats(target_date, session):
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

    if yesterday_stats:
        diff = current_premium - yesterday_stats["avg"]
    elif today_stats:
        diff = current_premium - today_stats["avg"]
    else:
        diff = 0.0

    context["verbal_direction"] = _verbal_direction(current_premium, diff)
    return context


def _label_premium_diff(diff):
    if diff < -0.05:
        return "Discount Deepening", "▼"
    elif diff > 0.05:
        return "Premium Expanding", "▲"
    else:
        return "Stable", "→"


def _verbal_direction(premium, diff):
    if abs(diff) < 0.05:
        return "Neutral"
    if diff < 0:
        return "Toward Buy"
    return "Toward Sell"


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
