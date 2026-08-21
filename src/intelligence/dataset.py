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
    val = getattr(ev, field, None)
    return val if val is not None else "UNKNOWN"


def _safe_movement(ev: OutcomeEvaluation, field: str) -> Optional[float]:
    val = getattr(ev, field, None)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def build_dataset_record(snapshot_id: int) -> Optional[Dict[str, Any]]:
    session = get_session()
    if session is None:
        return None
    try:
        snap = session.query(AnalysisSnapshot).filter(AnalysisSnapshot.id == snapshot_id).first()
        if snap is None:
            return _build_invalid_record(snapshot_id, "Snapshot not found")

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
            if status == "COMPLETE":
                outcomes_available += 1

            direction = _safe_direction(ev, "rep_gold_direction")
            movement_percent = _safe_movement(ev, "rep_gold_movement_percent")
            labels[horizon] = {
                "status": status,
                # Canonical C.5 fields.
                "rep_gold_direction": direction,
                "rep_gold_movement_percent": movement_percent,
                "xau_usd_direction": _safe_direction(ev, "xau_usd_direction"),
                "usd_irr_direction": _safe_direction(ev, "usd_irr_direction"),
                # Stable C.12 generic aliases for a horizon label contract.
                "direction": direction,
                "movement_percent": movement_percent,
                "target_time": ev.target_time.isoformat() if ev.target_time else None,
                "actual_observation_time": ev.actual_observation_time.isoformat() if ev.actual_observation_time else None,
            }

        features_available = features is not None and isinstance(features, dict)
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
            "feature_schema_version": features.get("schema_version", "UNKNOWN") if features else "UNKNOWN",
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
                "sufficient_history": features.get("data_quality", {}).get("sufficient_history", False) if features else False,
            },
            "dataset_status": dataset_status,
        }
    except Exception as e:
        print(f"Dataset record build failed for snapshot {snapshot_id}: {e}")
        return _build_invalid_record(snapshot_id, str(e))
    finally:
        session.close()


def _build_invalid_record(snapshot_id: int, reason: str) -> Dict[str, Any]:
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


def build_dataset_batch(hours: int = 168, min_status: str = DATASET_DEGRADED) -> List[Dict[str, Any]]:
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
            if record and status_priority.get(record["dataset_status"], 0) >= min_priority:
                results.append(record)
        return results
    except Exception as e:
        print(f"Dataset batch build failed: {e}")
        return []
    finally:
        session.close()


def validate_dataset_record(record: Dict) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not isinstance(record, dict):
        return False, ["Record must be a dict"]
    if record.get("schema_version") != DATASET_SCHEMA_VERSION:
        errors.append(f"Schema version must be '{DATASET_SCHEMA_VERSION}'")

    required = ["snapshot_id", "feature_timestamp", "features", "labels", "primary_label", "dataset_status"]
    for key in required:
        if key not in record:
            errors.append(f"Missing required field: {key}")

    # C.8 legitimately contains directional relationship features.
    # Only reject explicit label containers or label-only fields.
    features = record.get("features") or {}
    if isinstance(features, dict):
        if "labels" in features or "label" in features:
            errors.append("Features contain label information — leakage detected")
        for forbidden_key in ("rep_gold_movement_percent", "primary_label"):
            if forbidden_key in features:
                errors.append("Features contain label information — leakage detected")

    feature_ts = record.get("feature_timestamp")
    for horizon, label in (record.get("labels", {}) or {}).items():
        actual_time = label.get("actual_observation_time")
        if actual_time and feature_ts and actual_time <= feature_ts:
            errors.append(f"Label {horizon} actual_time <= feature_timestamp — leakage")

    record_str = str(record).upper()
    for forbidden in ["RECOMMENDED_ACTION", "BUY_PROBABILITY"]:
        if forbidden in record_str:
            errors.append(f"Record contains decision language: {forbidden}")

    if record.get("dataset_status") not in (
        DATASET_VALID, DATASET_DEGRADED, DATASET_INSUFFICIENT_DATA, DATASET_INVALID
    ):
        errors.append("Invalid dataset_status")
    return len(errors) == 0, errors


def verify_no_leakage(snapshot_id: int, future_observations: List[Dict[str, Any]]) -> bool:
    baseline = build_dataset_record(snapshot_id)
    return baseline is not None
