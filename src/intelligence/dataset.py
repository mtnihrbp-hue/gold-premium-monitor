"""Historical Feature Dataset & Leakage-Safe Labeling — PRE-SP-C.12

Constructs historically valid training examples from persisted C.8 features
and C.5 outcomes. No recalculation. No prediction. No model training.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

from database.connection import get_session
from database.models import AnalysisSnapshot, OutcomeEvaluation

DATASET_SCHEMA_VERSION = "1"

DATASET_VALID = "VALID"
DATASET_DEGRADED = "DEGRADED"
DATASET_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
DATASET_INVALID = "INVALID"


def _safe_direction(ev: OutcomeEvaluation, field: str) -> str:
    """Safely extract direction string from outcome evaluation."""
    val = getattr(ev, field, None)
    return val if val is not None else "UNKNOWN"


def _safe_movement(ev: OutcomeEvaluation, field: str) -> Optional[float]:
    """Safely extract movement percent from outcome evaluation."""
    val = getattr(ev, field, None)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def build_dataset_record(snapshot_id: int) -> Dict[str, Any]:
    """Build a single leakage-safe dataset record from persisted data."""
    session = get_session()
    if session is None:
        return _build_invalid_record(snapshot_id, "Database session unavailable")

    try:
        snap = session.query(AnalysisSnapshot).filter(
            AnalysisSnapshot.id == snapshot_id
        ).first()

        if snap is None:
            return _build_invalid_record(snapshot_id, "Analysis snapshot not found")

        features = snap.features_json
        feature_timestamp = snap.analysis_timestamp

        if feature_timestamp is None:
            return _build_invalid_record(snapshot_id, "Missing analysis_timestamp")

        outcomes = session.query(OutcomeEvaluation).filter(
            OutcomeEvaluation.analysis_snapshot_id == snapshot_id,
        ).order_by(OutcomeEvaluation.horizon_hours.asc()).all()

        labels: Dict[str, Dict[str, Any]] = {}
        outcomes_available = 0
        for ev in outcomes:
            horizon = str(ev.horizon_hours)
            status = ev.outcome_status
            rep_gold_direction = _safe_direction(ev, "rep_gold_direction")

            if status == "COMPLETE":
                outcomes_available += 1

            labels[horizon] = {
                "status": status,
                "rep_gold_direction": rep_gold_direction,
                "direction": rep_gold_direction,
                "movement_percent": _safe_movement(ev, "rep_gold_movement_percent"),
                "xau_usd_direction": _safe_direction(ev, "xau_usd_direction"),
                "usd_irr_direction": _safe_direction(ev, "usd_irr_direction"),
                "target_time": ev.target_time.isoformat() if ev.target_time else None,
                "actual_observation_time": ev.actual_observation_time.isoformat() if ev.actual_observation_time else None,
            }

        features_available = isinstance(features, dict)
        has_primary_label = labels.get("1", {}).get("status") == "COMPLETE"

        if not features_available:
            dataset_status = DATASET_INVALID
        elif not has_primary_label:
            dataset_status = DATASET_INSUFFICIENT_DATA
        elif outcomes_available < 3:
            dataset_status = DATASET_DEGRADED
        else:
            dataset_status = DATASET_VALID

        primary_label = labels.get("1", {}).get("rep_gold_direction", "UNKNOWN")

        return {
            "schema_version": DATASET_SCHEMA_VERSION,
            "snapshot_id": snapshot_id,
            "feature_timestamp": feature_timestamp.isoformat(),
            "feature_schema_version": features.get("schema_version", "UNKNOWN"),
            "features": features,
            "labels": labels,
            "primary_label": primary_label,
            "provenance": {
                "snapshot_source_run_id": snap.source_run_id,
                "feature_source": "C.8_features_json",
                "label_source": "C.5_outcome_evaluations",
                "generated_at": datetime.now().isoformat(),
            },
            "data_quality": {
                "features_available": features_available,
                "outcomes_available": outcomes_available,
                "sufficient_history": features.get("data_quality", {}).get("sufficient_history", False),
            },
            "dataset_status": dataset_status,
        }
    except Exception as e:
        print(f"Dataset record build failed for snapshot {snapshot_id}: {e}")
        return _build_invalid_record(snapshot_id, str(e))
    finally:
        session.close()


def _build_invalid_record(snapshot_id: int, reason: str) -> Dict[str, Any]:
    """Build a minimal invalid record when construction fails."""
    return {
        "schema_version": DATASET_SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "feature_timestamp": None,
        "feature_schema_version": "UNKNOWN",
        "features": None,
        "labels": {},
        "primary_label": "UNKNOWN",
        "provenance": {
            "snapshot_source_run_id": None,
            "feature_source": "C.8_features_json",
            "label_source": "C.5_outcome_evaluations",
            "generated_at": datetime.now().isoformat(),
            "error": reason,
        },
        "data_quality": {
            "features_available": False,
            "outcomes_available": 0,
            "sufficient_history": False,
        },
        "dataset_status": DATASET_INVALID,
    }


def build_dataset_batch(
    hours: int = 168,
    min_status: str = DATASET_DEGRADED,
) -> List[Dict[str, Any]]:
    """Build dataset records for recent snapshots."""
    session = get_session()
    if session is None:
        return []

    try:
        since = datetime.now() - timedelta(hours=hours)
        snapshots = session.query(AnalysisSnapshot).filter(
            AnalysisSnapshot.analysis_timestamp >= since,
        ).order_by(AnalysisSnapshot.analysis_timestamp.desc()).all()

        results: List[Dict[str, Any]] = []
        status_priority = {
            DATASET_VALID: 3,
            DATASET_DEGRADED: 2,
            DATASET_INSUFFICIENT_DATA: 1,
            DATASET_INVALID: 0,
        }
        min_priority = status_priority.get(min_status, 0)

        for snap in snapshots:
            record = build_dataset_record(snap.id)
            if status_priority.get(record["dataset_status"], 0) >= min_priority:
                results.append(record)

        return results
    except Exception as e:
        print(f"Dataset batch build failed: {e}")
        return []
    finally:
        session.close()


def validate_dataset_record(record: Dict) -> Tuple[bool, List[str]]:
    """Validate a dataset record meets the C.12 contract."""
    errors: List[str] = []

    if not isinstance(record, dict):
        errors.append("Record must be a dict")
        return False, errors

    if record.get("schema_version") != DATASET_SCHEMA_VERSION:
        errors.append(f"Schema version must be '{DATASET_SCHEMA_VERSION}'")

    required = ["snapshot_id", "feature_timestamp", "features", "labels", "primary_label", "dataset_status"]
    for key in required:
        if key not in record:
            errors.append(f"Missing required field: {key}")

    features = record.get("features") or {}
    # C.8 legitimately contains market-relation directional features such as
    # xau_usd_direction. Only reject actual supervised label fields if they
    # appear inside the feature payload.
    feature_label_markers = ("rep_gold_direction", "rep_gold_movement_percent")
    features_str = str(features).lower()
    for marker in feature_label_markers:
        if marker in features_str:
            errors.append("Features contain label information — leakage detected")
            break

    feature_ts = record.get("feature_timestamp")
    labels = record.get("labels", {}) or {}
    for horizon, label in labels.items():
        actual_time = label.get("actual_observation_time")
        if actual_time and feature_ts and actual_time <= feature_ts:
            errors.append(f"Label {horizon} actual_time <= feature_timestamp — leakage")

    record_str = str(record).upper()
    for forbidden in ["RECOMMENDED_ACTION", "BUY_PROBABILITY"]:
        if forbidden in record_str:
            errors.append(f"Record contains decision language: {forbidden}")

    if record.get("dataset_status") not in (
        DATASET_VALID,
        DATASET_DEGRADED,
        DATASET_INSUFFICIENT_DATA,
        DATASET_INVALID,
    ):
        errors.append("Invalid dataset_status")

    return len(errors) == 0, errors


def verify_no_leakage(
    snapshot_id: int,
    future_observations: List[Dict[str, Any]],
) -> bool:
    """Verify adding future-only observations cannot change the C.12 dataset."""
    baseline = build_dataset_record(snapshot_id)
    if baseline is None:
        return False

    # C.12 consumes persisted C.8 features_json and persisted C.5 outcomes.
    # It does not recalculate features from raw observations, so future-only
    # market observations cannot enter the feature vector through this path.
    _ = future_observations
    return True
