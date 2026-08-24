"""Forecast Readiness Audit — Diagnostic Observability

Quantitative measurement of why generate_forecast() returns INSUFFICIENT_DATA.
Read-only. No database mutations. No forecast behavior changes.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from database.connection import get_session
from database.models import AnalysisSnapshot, OutcomeEvaluation

DEFAULT_HORIZONS = [1, 6, 24]
DEFAULT_MIN_TRAIN_SAMPLES = 10
DEFAULT_MIN_PER_CLASS = 3
DEFAULT_MIN_DISTINCT_DAYS = 2
DEFAULT_HOURS_LOOKBACK = 2160  # 90 days

# Must stay in sync with forecast_engine.py label mapping
_VALID_LABELS = {"UP", "DOWN", "FLAT"}


def _safe_iso(ts) -> Optional[str]:
    return ts.isoformat() if ts else None


def _count_distinct_days(timestamps: List[datetime]) -> int:
    return len({t.date() for t in timestamps if t})


def _compute_estimated_days_to_readiness(
    current_examples: int,
    required_examples: int,
    qualifying_timestamps: List[datetime],
) -> Optional[float]:
    """Estimate days to readiness from observed accumulation cadence.

    Returns None if insufficient data to estimate.
    """
    if current_examples >= required_examples:
        return 0.0
    if len(qualifying_timestamps) < 2:
        return None

    # Sort oldest → newest
    sorted_ts = sorted(qualifying_timestamps)
    total_span_hours = (sorted_ts[-1] - sorted_ts[0]).total_seconds() / 3600
    if total_span_hours <= 0:
        return None

    examples_per_hour = len(sorted_ts) / total_span_hours
    if examples_per_hour <= 0:
        return None

    remaining = required_examples - current_examples
    hours_needed = remaining / examples_per_hour
    return round(hours_needed / 24, 2)


def audit_forecast_readiness(
    config: Optional[Dict[str, Any]] = None,
    session=None,
) -> Dict[str, Any]:
    """Audit actual database state for forecast readiness per horizon.

    Args:
        config: optional overrides for thresholds and horizons.
        session: optional SQLAlchemy session. If None, opens/closes own.

    Returns:
        structured readiness report (read-only, no DB mutations).
    """
    cfg = config or {}
    horizons = cfg.get("horizons_hours", DEFAULT_HORIZONS)
    min_train = cfg.get("min_train_samples", DEFAULT_MIN_TRAIN_SAMPLES)
    min_per_class = cfg.get("min_per_class", DEFAULT_MIN_PER_CLASS)
    min_distinct_days = cfg.get("min_distinct_days", DEFAULT_MIN_DISTINCT_DAYS)
    hours_lookback = cfg.get("hours_lookback", DEFAULT_HOURS_LOOKBACK)

    should_close = False
    if session is None:
        session = get_session()
        if session is None:
            return {
                "audit_timestamp": datetime.now().isoformat(),
                "status": "DB_UNAVAILABLE",
                "error": "Database session unavailable",
                "aggregate": {},
                "per_horizon": {},
                "provenance": {},
            }
        should_close = True

    try:
        since = datetime.now() - timedelta(hours=hours_lookback)

        # Aggregate snapshot counts
        all_snaps = (
            session.query(AnalysisSnapshot)
            .filter(AnalysisSnapshot.analysis_timestamp >= since)
            .order_by(AnalysisSnapshot.analysis_timestamp.asc())
            .all()
        )
        total_snapshots = len(all_snaps)
        snaps_with_features = [
            s for s in all_snaps
            if s.features_json is not None and isinstance(s.features_json, dict)
        ]
        snapshots_without_features = total_snapshots - len(snaps_with_features)

        earliest_snap = all_snaps[0].analysis_timestamp if all_snaps else None
        latest_snap = all_snaps[-1].analysis_timestamp if all_snaps else None
        distinct_days = _count_distinct_days(
            [s.analysis_timestamp for s in all_snaps if s.analysis_timestamp]
        )

        aggregate = {
            "total_snapshots": total_snapshots,
            "snapshots_with_features": len(snaps_with_features),
            "snapshots_without_features": snapshots_without_features,
            "snapshot_timestamp_earliest": _safe_iso(earliest_snap),
            "snapshot_timestamp_latest": _safe_iso(latest_snap),
            "distinct_observation_days": distinct_days,
        }

        per_horizon: Dict[str, Any] = {}

        for horizon in horizons:
            # All outcomes for this horizon in lookback
            outcomes = (
                session.query(OutcomeEvaluation)
                .join(
                    AnalysisSnapshot,
                    OutcomeEvaluation.analysis_snapshot_id == AnalysisSnapshot.id,
                )
                .filter(AnalysisSnapshot.analysis_timestamp >= since)
                .filter(OutcomeEvaluation.horizon_hours == horizon)
                .all()
            )

            total_outcomes = len(outcomes)
            complete = [o for o in outcomes if o.outcome_status == "COMPLETE"]
            insufficient = [o for o in outcomes if o.outcome_status == "INSUFFICIENT_DATA"]
            pending = [o for o in outcomes if o.outcome_status not in ("COMPLETE", "INSUFFICIENT_DATA")]

            # Usable: snapshot has features_json AND outcome is COMPLETE AND direction is valid
            usable = []
            for o in outcomes:
                snap = session.query(AnalysisSnapshot).filter(
                    AnalysisSnapshot.id == o.analysis_snapshot_id
                ).first()
                if snap is None:
                    continue
                if snap.features_json is None or not isinstance(snap.features_json, dict):
                    continue
                if o.outcome_status != "COMPLETE":
                    continue
                direction = getattr(o, "rep_gold_direction", None)
                if direction not in _VALID_LABELS:
                    continue
                usable.append({"snapshot": snap, "outcome": o, "direction": direction})

            class_counts = {"UP": 0, "DOWN": 0, "NEUTRAL": 0}
            qualifying_timestamps = []
            for u in usable:
                d = u["direction"]
                if d == "FLAT":
                    class_counts["NEUTRAL"] += 1
                else:
                    class_counts[d] += 1
                ts = u["snapshot"].analysis_timestamp
                if ts:
                    qualifying_timestamps.append(ts)

            min_class_count = min(class_counts.values()) if class_counts else 0
            usable_count = len(usable)
            distinct_qualifying_days = _count_distinct_days(qualifying_timestamps)

            meets_train = usable_count >= min_train
            meets_class = min_class_count >= min_per_class
            meets_days = distinct_qualifying_days >= min_distinct_days

            gate_reasons: List[str] = []
            if not meets_train:
                gate_reasons.append(f"insufficient_training_examples: {usable_count}/{min_train}")
            if not meets_class:
                gate_reasons.append(
                    f"class_imbalance: UP={class_counts['UP']}, DOWN={class_counts['DOWN']}, NEUTRAL={class_counts['NEUTRAL']}"
                )
            if not meets_days:
                gate_reasons.append(f"insufficient_temporal_coverage: {distinct_qualifying_days}/{min_distinct_days} days")

            gate = "OPEN" if (meets_train and meets_class and meets_days) else "GATED"

            latest_qualifying = max(qualifying_timestamps) if qualifying_timestamps else None
            estimated_days = _compute_estimated_days_to_readiness(
                usable_count, min_train, qualifying_timestamps
            )

            per_horizon[str(horizon)] = {
                "horizon_hours": horizon,
                "total_outcomes": total_outcomes,
                "complete_outcomes": len(complete),
                "insufficient_data_outcomes": len(insufficient),
                "pending_outcomes": len(pending),
                "usable_training_examples": usable_count,
                "class_distribution": class_counts,
                "min_class_count": min_class_count,
                "meets_min_train_samples": meets_train,
                "meets_min_per_class": meets_class,
                "meets_distinct_days": meets_days,
                "readiness_gate": gate,
                "gate_reasons": gate_reasons,
                "latest_qualifying_training_timestamp": _safe_iso(latest_qualifying),
                "estimated_days_to_readiness": estimated_days,
            }

        return {
            "audit_timestamp": datetime.now().isoformat(),
            "status": "OK",
            "error": None,
            "aggregate": aggregate,
            "per_horizon": per_horizon,
            "provenance": {
                "min_train_samples": min_train,
                "min_per_class": min_per_class,
                "min_distinct_days": min_distinct_days,
                "hours_lookback": hours_lookback,
                "query_method": "repository_abstraction",
                "forecast_engine_min_train": DEFAULT_MIN_TRAIN_SAMPLES,
            },
        }

    except Exception as e:
        return {
            "audit_timestamp": datetime.now().isoformat(),
            "status": "ERROR",
            "error": str(e),
            "aggregate": {},
            "per_horizon": {},
            "provenance": {},
        }
    finally:
        if should_close:
            session.close()
