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



# --- SP-B.1: Historical Intelligence Queries ---

def get_market_states_by_criteria(
    valuation=None,
    momentum=None,
    structure=None,
    premium_min=None,
    premium_max=None,
    days=None,
    limit=100,
):
    """Query market_states with optional categorical + premium + date filters.

    Joins with market_snapshots to include premium_percent.
    Returns list of MarketState objects with .snapshot joined.
    Non-blocking: returns [] if DB unavailable.

    Args:
        valuation: CHEAP | FAIR | EXPENSIVE | None (no filter)
        momentum: IMPROVING | NEUTRAL | WEAKENING | None
        structure: DISCOUNT_DOMINANT | PREMIUM_DOMINANT | MIXED | None
        premium_min: minimum premium_percent (inclusive)
        premium_max: maximum premium_percent (inclusive)
        days: lookback window in days from now
        limit: max results to return

    Returns:
        List of MarketState objects (with joined snapshot for premium access)
    """
    session = get_session()
    if session is None:
        return []

    try:
        query = (
            session.query(MarketState)
            .join(MarketSnapshot, MarketState.snapshot_id == MarketSnapshot.id)
            .order_by(MarketState.timestamp.desc())
        )

        if valuation is not None:
            query = query.filter(MarketState.valuation_state == valuation)
        if momentum is not None:
            query = query.filter(MarketState.momentum_state == momentum)
        if structure is not None:
            query = query.filter(MarketState.structure_state == structure)
        if premium_min is not None:
            query = query.filter(MarketSnapshot.premium_percent >= premium_min)
        if premium_max is not None:
            query = query.filter(MarketSnapshot.premium_percent <= premium_max)
        if days is not None:
            since = datetime.now() - timedelta(days=days)
            query = query.filter(MarketState.timestamp >= since)

        return query.limit(limit).all()
    except Exception as e:
        print(f"DB query failed (get_market_states_by_criteria): {e}")
        return []
    finally:
        session.close()


def get_similar_market_states(
    reference_state,
    premium_tolerance=1.0,
    days=90,
    max_results=20,
):
    """Fetch historical states similar to a reference SignalState.

    Deterministic similarity:
      1. Exact match on valuation, momentum, structure
      2. Premium within tolerance (via joined snapshot)
      3. Within lookback window
      4. Sorted by premium distance (asc), then recency (desc)

    Args:
        reference_state: SignalState-like object with
            valuation, momentum, premium_direction, structure, premium
        premium_tolerance: max premium difference for match (default 1.0%)
        days: lookback window in days (default 90)
        max_results: max results to return (default 20)

    Returns:
        HistoricalComparison with matched states
    """
    from intelligence.historical import build_historical_comparison

    try:
        # Fetch candidates with same categorical state
        candidates = get_market_states_by_criteria(
            valuation=getattr(reference_state, "valuation", None),
            momentum=getattr(reference_state, "momentum", None),
            structure=getattr(reference_state, "structure", None),
            days=days,
            limit=500,
        )

        # Build reference dict for similarity engine
        reference_dict = {
            "premium": getattr(reference_state, "premium", None),
            "valuation": getattr(reference_state, "valuation", None),
            "momentum": getattr(reference_state, "momentum", None),
            "structure": getattr(reference_state, "structure", None),
        }

        config = {
            "premium_tolerance": premium_tolerance,
            "lookback_days": days,
            "max_results": max_results,
        }

        comparison = build_historical_comparison(reference_dict, candidates, config)
        return comparison
    except Exception as e:
        print(f"DB query failed (get_similar_market_states): {e}")
        # Return empty comparison on failure
        from intelligence.historical import HistoricalComparison
        return HistoricalComparison(
            reference_premium=getattr(reference_state, "premium", 0.0),
            reference_valuation=getattr(reference_state, "valuation", "UNKNOWN"),
            reference_momentum=getattr(reference_state, "momentum", "UNKNOWN"),
            reference_structure=getattr(reference_state, "structure", "UNKNOWN"),
        )




# --- SP-B.2: News Intelligence Repository ---

def save_news_event(news_event: dict) -> int:
    """Save a classified news event to the database.

    Args:
        news_event: dict with keys matching NewsEvent model

    Returns:
        event id, or -1 on failure
    """
    from database.models import NewsEvent

    session = get_session()
    if session is None:
        print("DB unavailable — news event not saved")
        return -1

    try:
        event = NewsEvent(
            timestamp=news_event.get("published_at", datetime.now()),
            source=news_event.get("source", "unknown"),
            url=news_event.get("url") or None,
            dedup_key=news_event.get("dedup_key") or None,
            raw_headline=news_event.get("title", ""),
            raw_summary=news_event.get("summary") or None,
            event_type=news_event.get("event_type", "UNKNOWN"),
            topic=news_event.get("topic") or None,
            relevance=news_event.get("relevance", "UNKNOWN"),
            expected_usd_direction=news_event.get("expected_usd_direction") or None,
            expected_gold_direction=news_event.get("expected_gold_direction") or None,
            expected_duration=news_event.get("expected_duration") or None,
            impact=news_event.get("impact") or None,
            confidence=news_event.get("confidence") or None,
            uncertainty_notes=news_event.get("uncertainty_notes") or None,
            classification_method=news_event.get("classification_method", "KEYWORD"),
            processed_at=datetime.now(),
        )
        session.add(event)
        session.commit()
        return event.id
    except Exception as e:
        print(f"DB save failed (save_news_event): {e}")
        session.rollback()
        return -1
    finally:
        session.close()


def news_event_exists(dedup_key: str) -> bool:
    """Check if a news event with the given dedup key already exists.

    Non-blocking: returns False if DB unavailable.
    """
    from database.models import NewsEvent

    session = get_session()
    if session is None:
        return False

    try:
        if dedup_key:
            since = datetime.now() - timedelta(days=7)
            count = (
                session.query(NewsEvent)
                .filter(NewsEvent.created_at >= since)
                .filter(NewsEvent.dedup_key == dedup_key)
                .count()
            )
            return count > 0
        return False
    except Exception as e:
        print(f"DB query failed (news_event_exists): {e}")
        return False
    finally:
        session.close()


def get_recent_news_events(hours: int = 24, limit: int = 100) -> list:
    """Get recent news events ordered by timestamp desc.

    Non-blocking: returns [] if DB unavailable.
    """
    from database.models import NewsEvent

    session = get_session()
    if session is None:
        return []

    try:
        since = datetime.now() - timedelta(hours=hours)
        return (
            session.query(NewsEvent)
            .filter(NewsEvent.timestamp >= since)
            .order_by(NewsEvent.timestamp.desc())
            .limit(limit)
            .all()
        )
    except Exception as e:
        print(f"DB query failed (get_recent_news_events): {e}")
        return []
    finally:
        session.close()


def get_news_events_by_type(event_type: str, hours: int = 24, limit: int = 100) -> list:
    """Get news events filtered by event type.

    Non-blocking: returns [] if DB unavailable.
    """
    from database.models import NewsEvent

    session = get_session()
    if session is None:
        return []

    try:
        since = datetime.now() - timedelta(hours=hours)
        return (
            session.query(NewsEvent)
            .filter(NewsEvent.event_type == event_type)
            .filter(NewsEvent.timestamp >= since)
            .order_by(NewsEvent.timestamp.desc())
            .limit(limit)
            .all()
        )
    except Exception as e:
        print(f"DB query failed (get_news_events_by_type): {e}")
        return []
    finally:
        session.close()
######



# --- PRE-SP-C.1: Price Observations ---

def save_price_observation(
    instrument: str,
    source: str,
    timestamp: datetime,
    price: float,
    freshness: str = "UNKNOWN",
    collection_run_id: str = None,
) -> int:
    """Save a price observation to the canonical time-series layer.

    Non-blocking: returns -1 on DB failure so market execution continues.

    Args:
        instrument: XAUUSD | USD/IRR | PAXG | REP_IRAN_GOLD
        source: collector source name
        timestamp: observation timestamp
        price: observed price
        freshness: FRESH | STALE | UNKNOWN
        collection_run_id: traceable collection cycle ID

    Returns:
        observation id, or -1 on failure
    """
    from database.models import PriceObservation

    session = get_session()
    if session is None:
        print("DB unavailable — price observation not saved")
        return -1

    try:
        obs = PriceObservation(
            instrument=instrument,
            source=source,
            timestamp=timestamp,
            price=price,
            freshness=freshness,
            collection_run_id=collection_run_id,
        )
        session.add(obs)
        session.commit()
        return obs.id
    except Exception as e:
        print(f"DB save failed (save_price_observation): {e}")
        session.rollback()
        return -1
    finally:
        session.close()


def get_price_observations(
    instrument: str = None,
    source: str = None,
    limit: int = 100,
    hours: int = None,
):
    """Get price observations with optional filtering.

    Non-blocking: returns [] if DB unavailable.

    Args:
        instrument: filter by instrument
        source: filter by source
        limit: max results
        hours: lookback window from now

    Returns:
        List of PriceObservation objects, ordered by timestamp DESC.
    """
    from database.models import PriceObservation

    session = get_session()
    if session is None:
        return []

    try:
        query = session.query(PriceObservation).order_by(
            PriceObservation.timestamp.desc()
        )

        if instrument is not None:
            query = query.filter(PriceObservation.instrument == instrument)
        if source is not None:
            query = query.filter(PriceObservation.source == source)
        if hours is not None:
            since = datetime.now() - timedelta(hours=hours)
            query = query.filter(PriceObservation.timestamp >= since)

        return query.limit(limit).all()
    except Exception as e:
        print(f"DB query failed (get_price_observations): {e}")
        return []
    finally:
        session.close()


def get_latest_price_observation(instrument: str = None, source: str = None):
    """Return the most recent price observation, or None if unavailable.

    Args:
        instrument: optional instrument filter
        source: optional source filter

    Returns:
        Latest PriceObservation or None.
    """
    from database.models import PriceObservation

    session = get_session()
    if session is None:
        return None

    try:
        query = session.query(PriceObservation).order_by(
            PriceObservation.timestamp.desc()
        )
        if instrument is not None:
            query = query.filter(PriceObservation.instrument == instrument)
        if source is not None:
            query = query.filter(PriceObservation.source == source)
        return query.first()
    except Exception as e:
        print(f"DB query failed (get_latest_price_observation): {e}")
        return None
    finally:
        session.close()


def get_price_observations_by_instrument(instrument: str, limit: int = 100, hours: int = None):
    """Convenience wrapper: get observations for a specific instrument.

    Non-blocking: returns [] if DB unavailable.
    """
    return get_price_observations(
        instrument=instrument, limit=limit, hours=hours
    )

########


# --- PRE-SP-C.2: Analysis Snapshots ---

def save_analysis_snapshot(
    analysis_timestamp: datetime,
    source_run_id: str,
    market_snapshot_id: int = None,
    market_state_id: int = None,
    xau_usd: float = None,
    usd_irr: float = None,
    rep_gold_price: float = None,
    premium_percent: float = None,
    valuation_state: str = "UNKNOWN",
    momentum_state: str = "UNKNOWN",
    structure_state: str = "UNKNOWN",
    analysis_window: str = None,
    data_quality_json: dict = None,
    # PRE-SP-C.4 fields
    regime_state: str = "UNKNOWN",
    technical_state_json: dict = None,
    previous_regime: str = None,
    regime_candidate_state: str = None,
    regime_confirmation_count: int = 0,
    # Pre-SP-C.6 fileds:
    evidence_package_json: dict = None,
    # Pre-SP-C.7 fileds:
    intelligence_result_json: dict = None,
    # Pre-SP-C.8 fileds:
    features_json: dict = None,

) -> int:
    """Save an analysis snapshot to the database.

    Non-blocking: returns -1 on DB failure.

    Args:
        analysis_timestamp: scheduled analysis timestamp
        source_run_id: deterministic unique run identifier
        market_snapshot_id: FK to market_snapshots
        market_state_id: FK to market_states
        xau_usd: world gold price at analysis time
        usd_irr: USD/IRR rate at analysis time
        rep_gold_price: representative Iranian gold price
        premium_percent: premium/discount percent
        valuation_state: CHEAP | FAIR | EXPENSIVE | UNKNOWN
        momentum_state: IMPROVING | NEUTRAL | WEAKENING | UNKNOWN
        structure_state: DISCOUNT_DOMINANT | PREMIUM_DOMINANT | MIXED | UNKNOWN
        analysis_window: descriptive window label
        data_quality_json: per-component quality tracking

    Returns:
        snapshot id, or -1 on failure
    """
    from database.models import AnalysisSnapshot

    session = get_session()
    if session is None:
        print("DB unavailable — analysis snapshot not saved")
        return -1

    try:
        snap = AnalysisSnapshot(
            snapshot_type="analysis",
            analysis_timestamp=analysis_timestamp,
            source_run_id=source_run_id,
            market_snapshot_id=market_snapshot_id,
            market_state_id=market_state_id,
            xau_usd=xau_usd,
            usd_irr=usd_irr,
            rep_gold_price=rep_gold_price,
            premium_percent=premium_percent,
            valuation_state=valuation_state,
            momentum_state=momentum_state,
            structure_state=structure_state,
            analysis_window=analysis_window,
            data_quality_json=data_quality_json,
            regime_state=regime_state,
            technical_state_json=technical_state_json,
            previous_regime=previous_regime,
            regime_candidate_state=regime_candidate_state,
            regime_confirmation_count=regime_confirmation_count,
            evidence_package_json=evidence_package_json,
            intelligence_result_json=intelligence_result_json,
        )
        session.add(snap)
        session.commit()
        return snap.id
    except Exception as e:
        print(f"DB save failed (save_analysis_snapshot): {e}")
        session.rollback()
        return -1
    finally:
        session.close()


def get_latest_analysis_snapshot():
    """Return the most recent analysis snapshot, or None if unavailable."""
    from database.models import AnalysisSnapshot

    session = get_session()
    if session is None:
        return None
    try:
        return (
            session.query(AnalysisSnapshot)
            .order_by(AnalysisSnapshot.analysis_timestamp.desc())
            .first()
        )
    except Exception as e:
        print(f"DB query failed (get_latest_analysis_snapshot): {e}")
        return None
    finally:
        session.close()


def get_analysis_snapshots(limit: int = 100, hours: int = None):
    """Get analysis snapshots ordered by timestamp desc.

    Non-blocking: returns [] if DB unavailable.
    """
    from database.models import AnalysisSnapshot

    session = get_session()
    if session is None:
        return []

    try:
        query = session.query(AnalysisSnapshot).order_by(
            AnalysisSnapshot.analysis_timestamp.desc()
        )
        if hours is not None:
            since = datetime.now() - timedelta(hours=hours)
            query = query.filter(AnalysisSnapshot.analysis_timestamp >= since)
        return query.limit(limit).all()
    except Exception as e:
        print(f"DB query failed (get_analysis_snapshots): {e}")
        return []
    finally:
        session.close()


def analysis_snapshot_exists(source_run_id: str) -> bool:
    """Check if an analysis snapshot with the given run ID already exists.

    Non-blocking: returns False if DB unavailable.
    """
    from database.models import AnalysisSnapshot

    session = get_session()
    if session is None:
        return False

    try:
        count = (
            session.query(AnalysisSnapshot)
            .filter(AnalysisSnapshot.source_run_id == source_run_id)
            .count()
        )
        return count > 0
    except Exception as e:
        print(f"DB query failed (analysis_snapshot_exists): {e}")
        return False
    finally:
        session.close()

#########
# --- PRE-SP-C.5: Outcome Evaluations ---

def save_outcome_evaluation(
    analysis_snapshot_id: int,
    horizon_hours: int,
    reference_time: datetime,
    target_time: datetime,
    actual_observation_time: datetime = None,
    outcome_status: str = "PENDING",
    reference_rep_gold_price: float = None,
    reference_xau_usd: float = None,
    reference_usd_irr: float = None,
    reference_premium_percent: float = None,
    actual_rep_gold_price: float = None,
    actual_xau_usd: float = None,
    actual_usd_irr: float = None,
    actual_premium_percent: float = None,
    rep_gold_movement_percent: float = None,
    rep_gold_direction: str = None,
    xau_usd_movement_percent: float = None,
    xau_usd_direction: str = None,
    usd_irr_movement_percent: float = None,
    usd_irr_direction: str = None,
    premium_movement_percent: float = None,
    premium_direction: str = None,
) -> int:
    """Save or update an outcome evaluation. Idempotent by (snapshot, horizon)."""
    from database.models import OutcomeEvaluation

    session = get_session()
    if session is None:
        print("DB unavailable — outcome evaluation not saved")
        return -1

    try:
        existing = session.query(OutcomeEvaluation).filter(
            OutcomeEvaluation.analysis_snapshot_id == analysis_snapshot_id,
            OutcomeEvaluation.horizon_hours == horizon_hours,
        ).first()

        if existing:
            existing.reference_time = reference_time
            existing.target_time = target_time
            existing.actual_observation_time = actual_observation_time
            existing.outcome_status = outcome_status
            existing.reference_rep_gold_price = reference_rep_gold_price
            existing.reference_xau_usd = reference_xau_usd
            existing.reference_usd_irr = reference_usd_irr
            existing.reference_premium_percent = reference_premium_percent
            existing.actual_rep_gold_price = actual_rep_gold_price
            existing.actual_xau_usd = actual_xau_usd
            existing.actual_usd_irr = actual_usd_irr
            existing.actual_premium_percent = actual_premium_percent
            existing.rep_gold_movement_percent = rep_gold_movement_percent
            existing.rep_gold_direction = rep_gold_direction
            existing.xau_usd_movement_percent = xau_usd_movement_percent
            existing.xau_usd_direction = xau_usd_direction
            existing.usd_irr_movement_percent = usd_irr_movement_percent
            existing.usd_irr_direction = usd_irr_direction
            existing.premium_movement_percent = premium_movement_percent
            existing.premium_direction = premium_direction
            existing.updated_at = datetime.now()
            session.commit()
            return existing.id

        ev = OutcomeEvaluation(
            analysis_snapshot_id=analysis_snapshot_id,
            horizon_hours=horizon_hours,
            reference_time=reference_time,
            target_time=target_time,
            actual_observation_time=actual_observation_time,
            outcome_status=outcome_status,
            reference_rep_gold_price=reference_rep_gold_price,
            reference_xau_usd=reference_xau_usd,
            reference_usd_irr=reference_usd_irr,
            reference_premium_percent=reference_premium_percent,
            actual_rep_gold_price=actual_rep_gold_price,
            actual_xau_usd=actual_xau_usd,
            actual_usd_irr=actual_usd_irr,
            actual_premium_percent=actual_premium_percent,
            rep_gold_movement_percent=rep_gold_movement_percent,
            rep_gold_direction=rep_gold_direction,
            xau_usd_movement_percent=xau_usd_movement_percent,
            xau_usd_direction=xau_usd_direction,
            usd_irr_movement_percent=usd_irr_movement_percent,
            usd_irr_direction=usd_irr_direction,
            premium_movement_percent=premium_movement_percent,
            premium_direction=premium_direction,
        )
        session.add(ev)
        session.commit()
        return ev.id
    except Exception as e:
        print(f"DB save failed (save_outcome_evaluation): {e}")
        session.rollback()
        return -1
    finally:
        session.close()


def get_outcome_evaluation(analysis_snapshot_id: int, horizon_hours: int):
    from database.models import OutcomeEvaluation
    session = get_session()
    if session is None:
        return None
    try:
        return session.query(OutcomeEvaluation).filter(
            OutcomeEvaluation.analysis_snapshot_id == analysis_snapshot_id,
            OutcomeEvaluation.horizon_hours == horizon_hours,
        ).first()
    except Exception as e:
        print(f"DB query failed (get_outcome_evaluation): {e}")
        return None
    finally:
        session.close()


def get_outcome_evaluations_by_snapshot(analysis_snapshot_id: int):
    from database.models import OutcomeEvaluation
    session = get_session()
    if session is None:
        return []
    try:
        return session.query(OutcomeEvaluation).filter(
            OutcomeEvaluation.analysis_snapshot_id == analysis_snapshot_id,
        ).order_by(OutcomeEvaluation.horizon_hours.asc()).all()
    except Exception as e:
        print(f"DB query failed (get_outcome_evaluations_by_snapshot): {e}")
        return []
    finally:
        session.close()

############









