"""Event-Impact Audit — Diagnostic Observability

Measures temporal association between classified news events and subsequent
market outcomes. Read-only. No causal claims. No database mutations.

Explicitly labels results as TEMPORAL_ASSOCIATION, not causation.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from database.connection import get_session
from database.models import NewsEvent, AnalysisSnapshot, OutcomeEvaluation

DEFAULT_HOURS_LOOKBACK = 72
DEFAULT_MIN_RELEVANCE = "HIGH"
DEFAULT_SNAPSHOT_WINDOW_MINUTES = 120
DEFAULT_HORIZONS = [1, 6, 24]

_RELEVANCE_ORDER = {"CRITICAL": 4, "HIGH": 3, "RELEVANT": 2, "LOW": 1, "UNKNOWN": 0}


def _safe_iso(ts) -> Optional[str]:
    return ts.isoformat() if ts else None


def _relevance_score(relevance: Optional[str]) -> int:
    return _RELEVANCE_ORDER.get(relevance or "UNKNOWN", 0)


def _find_nearest_snapshot(
    event_timestamp: datetime,
    snapshots: List[AnalysisSnapshot],
    window_minutes: int,
) -> Optional[AnalysisSnapshot]:
    """Find the closest snapshot within the temporal window."""
    window = timedelta(minutes=window_minutes)
    candidates = [
        s for s in snapshots
        if s.analysis_timestamp
        and abs(s.analysis_timestamp - event_timestamp) <= window
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda s: abs(s.analysis_timestamp - event_timestamp))


def _match_outcomes(
    snapshot_id: int,
    horizons: List[int],
    session,
) -> Dict[str, Any]:
    """Query outcomes for a snapshot across horizons."""
    results: Dict[str, Any] = {}
    for horizon in horizons:
        ev = (
            session.query(OutcomeEvaluation)
            .filter(
                OutcomeEvaluation.analysis_snapshot_id == snapshot_id,
                OutcomeEvaluation.horizon_hours == horizon,
            )
            .first()
        )

        if ev is None:
            results[str(horizon)] = {
                "horizon_hours": horizon,
                "outcome_status": "INSUFFICIENT_DATA",
                "observed_direction": None,
                "observed_movement_percent": None,
                "directional_agreement": "INSUFFICIENT_DATA",
            }
            continue

        direction = getattr(ev, "rep_gold_direction", None)
        movement = getattr(ev, "rep_gold_movement_percent", None)
        status = getattr(ev, "outcome_status", "INSUFFICIENT_DATA")

        if status == "COMPLETE" and direction in ("UP", "DOWN", "FLAT"):
            results[str(horizon)] = {
                "horizon_hours": horizon,
                "outcome_status": "OBSERVED",
                "observed_direction": direction,
                "observed_movement_percent": round(float(movement), 4) if movement is not None else None,
                "directional_agreement": "INSUFFICIENT_DATA",  # resolved later
            }
        else:
            results[str(horizon)] = {
                "horizon_hours": horizon,
                "outcome_status": "INSUFFICIENT_DATA",
                "observed_direction": None,
                "observed_movement_percent": None,
                "directional_agreement": "INSUFFICIENT_DATA",
            }
    return results


def _resolve_agreement(
    classified_direction: Optional[str],
    outcomes_by_horizon: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare classified expected direction with observed outcome directions."""
    resolved = {}
    for horizon, data in outcomes_by_horizon.items():
        observed = data.get("observed_direction")
        if classified_direction is None or observed is None:
            agreement = "INSUFFICIENT_DATA"
        elif classified_direction == observed:
            agreement = "AGREED"
        else:
            agreement = "DISAGREED"
        resolved[horizon] = {**data, "directional_agreement": agreement}
    return resolved


def audit_event_impact(
    hours_lookback: int = DEFAULT_HOURS_LOOKBACK,
    config: Optional[Dict[str, Any]] = None,
    session=None,
) -> Dict[str, Any]:
    """Audit temporal association between news events and market outcomes.

    Args:
        hours_lookback: how far back to search for news events.
        config: optional dict with keys:
            - min_relevance: str (default "HIGH")
            - event_types: List[str] (default all non-UNKNOWN)
            - snapshot_window_minutes: int (default 120)
            - horizons: List[int] (default [1, 6, 24])
        session: optional SQLAlchemy session.

    Returns:
        structured event-impact report (read-only, no DB mutations).
        All directional relationships are explicitly labelled TEMPORAL_ASSOCIATION.
    """
    cfg = config or {}
    min_relevance = cfg.get("min_relevance", DEFAULT_MIN_RELEVANCE)
    event_types = cfg.get("event_types")
    snapshot_window = cfg.get("snapshot_window_minutes", DEFAULT_SNAPSHOT_WINDOW_MINUTES)
    horizons = cfg.get("horizons", DEFAULT_HORIZONS)
    min_score = _relevance_score(min_relevance)

    should_close = False
    if session is None:
        session = get_session()
        if session is None:
            return {
                "audit_timestamp": datetime.now().isoformat(),
                "status": "DB_UNAVAILABLE",
                "error": "Database session unavailable",
                "disclaimer": "This audit measures TEMPORAL_ASSOCIATION, not causation.",
                "parameters": {},
                "events_audited": 0,
                "events_with_insufficient_context": 0,
                "event_results": [],
                "aggregate": {},
            }
        should_close = True

    try:
        since = datetime.now() - timedelta(hours=hours_lookback)

        # Fetch all candidate news events
        events_query = session.query(NewsEvent).filter(
            NewsEvent.timestamp >= since,
            NewsEvent.event_type != "UNKNOWN",
        )
        if event_types:
            events_query = events_query.filter(NewsEvent.event_type.in_(event_types))
        all_events = events_query.order_by(NewsEvent.timestamp.desc()).all()

        # Filter by relevance threshold
        selected = [e for e in all_events if _relevance_score(e.relevance) >= min_score]

        # Pre-fetch snapshots in window for matching (optimization)
        window_start = since - timedelta(minutes=snapshot_window)
        window_end = datetime.now() + timedelta(minutes=snapshot_window)
        all_snapshots = (
            session.query(AnalysisSnapshot)
            .filter(
                AnalysisSnapshot.analysis_timestamp >= window_start,
                AnalysisSnapshot.analysis_timestamp <= window_end,
            )
            .all()
        )

        event_results: List[Dict[str, Any]] = []
        events_with_insufficient_context = 0

        for event in selected:
            snap = _find_nearest_snapshot(
                event.timestamp, all_snapshots, snapshot_window
            )

            if snap is None:
                events_with_insufficient_context += 1
                event_results.append({
                    "event_id": event.id,
                    "event_timestamp": _safe_iso(event.timestamp),
                    "source": event.source or "unknown",
                    "event_type": event.event_type or "UNKNOWN",
                    "relevance": event.relevance or "UNKNOWN",
                    "classified_expected_gold_direction": event.expected_gold_direction,
                    "classified_expected_usd_direction": event.expected_usd_direction,
                    "snapshot_match": None,
                    "outcomes_by_horizon": {
                        str(h): {
                            "horizon_hours": h,
                            "outcome_status": "INSUFFICIENT_DATA",
                            "observed_direction": None,
                            "observed_movement_percent": None,
                            "directional_agreement": "INSUFFICIENT_DATA",
                        }
                        for h in horizons
                    },
                    "summary": {
                        "any_observed": False,
                        "agreement_count": 0,
                        "disagreement_count": 0,
                        "insufficient_count": len(horizons),
                    },
                })
                continue

            outcomes_raw = _match_outcomes(snap.id, horizons, session)
            outcomes = _resolve_agreement(event.expected_gold_direction, outcomes_raw)

            observed_count = sum(
                1 for o in outcomes.values() if o["outcome_status"] == "OBSERVED"
            )
            agreed_count = sum(
                1 for o in outcomes.values() if o["directional_agreement"] == "AGREED"
            )
            disagreed_count = sum(
                1 for o in outcomes.values() if o["directional_agreement"] == "DISAGREED"
            )
            insufficient_count = sum(
                1 for o in outcomes.values() if o["directional_agreement"] == "INSUFFICIENT_DATA"
            )

            event_results.append({
                "event_id": event.id,
                "event_timestamp": _safe_iso(event.timestamp),
                "source": event.source or "unknown",
                "event_type": event.event_type or "UNKNOWN",
                "relevance": event.relevance or "UNKNOWN",
                "classified_expected_gold_direction": event.expected_gold_direction,
                "classified_expected_usd_direction": event.expected_usd_direction,
                "snapshot_match": {
                    "snapshot_id": snap.id,
                    "snapshot_timestamp": _safe_iso(snap.analysis_timestamp),
                    "regime_state": snap.regime_state or "UNKNOWN",
                    "premium_percent": float(snap.premium_percent) if snap.premium_percent is not None else None,
                },
                "outcomes_by_horizon": outcomes,
                "summary": {
                    "any_observed": observed_count > 0,
                    "agreement_count": agreed_count,
                    "disagreement_count": disagreed_count,
                    "insufficient_count": insufficient_count,
                },
            })

        # Aggregate counts
        total_events = len(selected)
        events_with_snapshot = total_events - events_with_insufficient_context
        observed_total = sum(
            1 for r in event_results
            for o in r["outcomes_by_horizon"].values()
            if o["outcome_status"] == "OBSERVED"
        )
        agreed_total = sum(r["summary"]["agreement_count"] for r in event_results)
        disagreed_total = sum(r["summary"]["disagreement_count"] for r in event_results)
        insufficient_total = sum(r["summary"]["insufficient_count"] for r in event_results)

        by_event_type: Dict[str, dict] = {}
        by_source: Dict[str, dict] = {}
        for r in event_results:
            et = r["event_type"]
            src = r["source"]
            for key, bucket in ((et, by_event_type), (src, by_source)):
                if key not in bucket:
                    bucket[key] = {"count": 0, "observed": 0, "agreed": 0, "disagreed": 0, "insufficient": 0}
                bucket[key]["count"] += 1
                bucket[key]["observed"] += sum(
                    1 for o in r["outcomes_by_horizon"].values() if o["outcome_status"] == "OBSERVED"
                )
                bucket[key]["agreed"] += r["summary"]["agreement_count"]
                bucket[key]["disagreed"] += r["summary"]["disagreement_count"]
                bucket[key]["insufficient"] += r["summary"]["insufficient_count"]

        return {
            "audit_timestamp": datetime.now().isoformat(),
            "status": "OK",
            "error": None,
            "disclaimer": "This audit measures TEMPORAL_ASSOCIATION, not causation. "
                          "Directional agreement does not imply the event caused the movement.",
            "parameters": {
                "hours_lookback": hours_lookback,
                "min_relevance": min_relevance,
                "snapshot_window_minutes": snapshot_window,
                "horizons": horizons,
            },
            "events_audited": total_events,
            "events_with_insufficient_context": events_with_insufficient_context,
            "event_results": event_results,
            "aggregate": {
                "total_events": total_events,
                "events_with_snapshot": events_with_snapshot,
                "observed_outcomes_total": observed_total,
                "agreed_total": agreed_total,
                "disagreed_total": disagreed_total,
                "insufficient_total": insufficient_total,
                "by_event_type": by_event_type,
                "by_source": by_source,
            },
        }

    except Exception as e:
        return {
            "audit_timestamp": datetime.now().isoformat(),
            "status": "ERROR",
            "error": str(e),
            "disclaimer": "This audit measures TEMPORAL_ASSOCIATION, not causation.",
            "parameters": {},
            "events_audited": 0,
            "events_with_insufficient_context": 0,
            "event_results": [],
            "aggregate": {},
        }
    finally:
        if should_close:
            session.close()
