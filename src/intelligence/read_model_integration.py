"""Read Model Integration & Audit Layer — PRE-SP-C.10

Stable downstream consumption contract for analytical read models.
Retrieves persisted analytical layers and produces completeness-classified state.
No calculation. No decision. No prediction. No market queries.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from database.connection import get_session
from database.models import AnalysisSnapshot, OutcomeEvaluation
from intelligence.read_model import validate_read_model, READ_MODEL_SCHEMA_VERSION


COMPLETENESS_COMPLETE = "COMPLETE"
COMPLETENESS_DEGRADED = "DEGRADED"
COMPLETENESS_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
COMPLETENESS_INVALID = "INVALID"


def classify_completeness(read_model: Optional[Dict]) -> Tuple[str, List[str]]:
    """Deterministic completeness classification for an analytical read model.

    Rules (evaluated in order):
    1. INVALID if read model fails structural validation or is missing.
    2. INSUFFICIENT_DATA if core facts (decision, interpretation) are missing.
    3. DEGRADED if some evidence/features are insufficient but core exists.
    4. COMPLETE if all major sections are present and valid.

    Returns:
        (status, reasons)
    """
    if not read_model or not isinstance(read_model, dict):
        return COMPLETENESS_INVALID, ["Read model is missing or not a dict"]

    valid, errors = validate_read_model(read_model)
    if not valid:
        return COMPLETENESS_INVALID, [f"Validation failed: {e}" for e in errors]

    reasons = []
    status = COMPLETENESS_COMPLETE

    # Facts check
    facts = read_model.get("facts", {})
    missing_facts = [k for k, v in facts.items() if v is None or v == "UNKNOWN"]
    if missing_facts:
        reasons.append(f"Missing facts: {missing_facts}")
        status = COMPLETENESS_DEGRADED

    # Evidence check
    evidence = read_model.get("evidence_summary", {})
    insufficient_evidence = [k for k, v in evidence.items() if v in ("INSUFFICIENT_DATA", "UNKNOWN")]
    if insufficient_evidence:
        reasons.append(f"Insufficient evidence: {insufficient_evidence}")
        if status == COMPLETENESS_COMPLETE:
            status = COMPLETENESS_DEGRADED

    # Interpretation check
    interp = read_model.get("interpretation_summary", {})
    if interp.get("market_context_summary") == "UNKNOWN" or not interp.get("market_context_summary"):
        reasons.append("Missing market context interpretation")
        status = COMPLETENESS_INSUFFICIENT_DATA

    # Features check
    features = read_model.get("features_summary", {})
    if features.get("sufficient_history") is False:
        reasons.append("Insufficient feature history")
        if status == COMPLETENESS_COMPLETE:
            status = COMPLETENESS_DEGRADED

    # Uncertainty / conflicts
    uncertainty = read_model.get("uncertainty", {})
    conflicts = uncertainty.get("conflicts", [])
    if conflicts:
        reasons.append(f"Conflicts present: {len(conflicts)}")
        if status == COMPLETENESS_COMPLETE:
            status = COMPLETENESS_DEGRADED

    # Decision authority check
    decision = read_model.get("decision", {})
    if decision.get("final_decision") == "UNKNOWN":
        reasons.append("Missing final decision")
        if status in (COMPLETENESS_COMPLETE, COMPLETENESS_DEGRADED):
            status = COMPLETENESS_INSUFFICIENT_DATA

    # Severity threshold: too many gaps
    if len(reasons) >= 5:
        status = COMPLETENESS_INSUFFICIENT_DATA

    return status, reasons


def get_analysis_read_model(snapshot_id: int) -> Optional[Dict]:
    """Retrieve the analytical read model for a specific snapshot.

    Returns the persisted read model augmented with completeness metadata.
    Does NOT query current market data.
    Safe for historical snapshots.

    Args:
        snapshot_id: analysis snapshot ID

    Returns:
        read model dict with retrieval_metadata, or None if snapshot not found
    """
    session = get_session()
    if session is None:
        return None

    try:
        snap = session.query(AnalysisSnapshot).filter(
            AnalysisSnapshot.id == snapshot_id
        ).first()

        if snap is None:
            return None

        read_model = snap.analysis_read_model_json

        # Fallback for pre-C.9 snapshots
        if not read_model:
            read_model = {
                "schema_version": READ_MODEL_SCHEMA_VERSION,
                "provenance": {
                    "source_run_id": snap.source_run_id,
                    "analysis_timestamp": snap.analysis_timestamp.isoformat() if snap.analysis_timestamp else None,
                    "retrieved_at": datetime.now().isoformat(),
                    "note": "Reconstructed from snapshot fields — read model was not persisted",
                },
                "facts": {
                    "xau_usd": float(snap.xau_usd) if snap.xau_usd else None,
                    "usd_irr": float(snap.usd_irr) if snap.usd_irr else None,
                    "rep_gold_price": float(snap.rep_gold_price) if snap.rep_gold_price else None,
                    "premium_percent": float(snap.premium_percent) if snap.premium_percent else None,
                    "valuation_state": snap.valuation_state or "UNKNOWN",
                    "momentum_state": snap.momentum_state or "UNKNOWN",
                    "structure_state": snap.structure_state or "UNKNOWN",
                    "regime_state": snap.regime_state or "UNKNOWN",
                },
                "evidence_summary": {"status": "NOT_PERSISTED"},
                "interpretation_summary": {"status": "NOT_PERSISTED"},
                "features_summary": {"status": "NOT_PERSISTED"},
                "uncertainty": {"missing_evidence": ["Read model not persisted for this snapshot"]},
                "outcome_history": {"status": "UNKNOWN"},
                "decision": {
                    "candidate_decision": "UNKNOWN",
                    "final_decision": "UNKNOWN",
                    "source": "reconstructed_fallback",
                    "note": "Snapshot predates C.9 read model persistence",
                },
            }

        completeness_status, completeness_reasons = classify_completeness(read_model)

        result = dict(read_model)
        result["retrieval_metadata"] = {
            "retrieved_at": datetime.now().isoformat(),
            "snapshot_id": snapshot_id,
            "completeness_status": completeness_status,
            "completeness_reasons": completeness_reasons,
            "evidence_persisted": snap.evidence_package_json is not None,
            "interpretation_persisted": snap.intelligence_result_json is not None,
            "features_persisted": snap.features_json is not None,
            "read_model_persisted": snap.analysis_read_model_json is not None,
        }

        return result
    except Exception as e:
        print(f"Read model retrieval failed: {e}")
        return None
    finally:
        session.close()


def reconstruct_historical_state(snapshot_id: int) -> Optional[Dict]:
    """Reconstruct the complete analytical state for a historical snapshot.

    Strict audit: uses ONLY persisted data associated with the snapshot.
    No current market values. No recalculation. No future observations.

    Args:
        snapshot_id: analysis snapshot ID

    Returns:
        historical audit envelope dict
    """
    session = get_session()
    if session is None:
        return None

    try:
        snap = session.query(AnalysisSnapshot).filter(
            AnalysisSnapshot.id == snapshot_id
        ).first()

        if snap is None:
            return None

        # Outcome evaluations (C.5) — strictly historical
        outcomes = session.query(OutcomeEvaluation).filter(
            OutcomeEvaluation.analysis_snapshot_id == snapshot_id
        ).order_by(OutcomeEvaluation.horizon_hours.asc()).all()

        outcome_history = []
        for ev in outcomes:
            outcome_history.append({
                "horizon_hours": ev.horizon_hours,
                "outcome_status": ev.outcome_status,
                "target_time": ev.target_time.isoformat() if ev.target_time else None,
                "actual_observation_time": ev.actual_observation_time.isoformat() if ev.actual_observation_time else None,
                "rep_gold_direction": ev.rep_gold_direction,
                "xau_usd_direction": ev.xau_usd_direction,
                "usd_irr_direction": ev.usd_irr_direction,
            })

        read_model = get_analysis_read_model(snapshot_id)
        if read_model is None:
            return None

        return {
            "audit_schema_version": "1",
            "snapshot_id": snapshot_id,
            "source_run_id": snap.source_run_id,
            "analysis_timestamp": snap.analysis_timestamp.isoformat() if snap.analysis_timestamp else None,
            "historical_state": {
                "facts": read_model.get("facts"),
                "evidence": read_model.get("evidence_summary"),
                "interpretation": read_model.get("interpretation_summary"),
                "features": read_model.get("features_summary"),
                "uncertainty": read_model.get("uncertainty"),
                "decision": read_model.get("decision"),
            },
            "outcome_evaluations": outcome_history,
            "completeness": {
                "status": read_model.get("retrieval_metadata", {}).get("completeness_status"),
                "reasons": read_model.get("retrieval_metadata", {}).get("completeness_reasons"),
            },
            "provenance": {
                "retrieved_at": datetime.now().isoformat(),
                "evidence_persisted": read_model.get("retrieval_metadata", {}).get("evidence_persisted"),
                "interpretation_persisted": read_model.get("retrieval_metadata", {}).get("interpretation_persisted"),
                "features_persisted": read_model.get("retrieval_metadata", {}).get("features_persisted"),
                "read_model_persisted": read_model.get("retrieval_metadata", {}).get("read_model_persisted"),
            },
            "audit_invariants": {
                "no_current_data_queried": True,
                "no_future_observations": True,
                "no_recalculation": True,
                "decision_read_only": True,
            },
        }
    except Exception as e:
        print(f"Historical reconstruction failed: {e}")
        return None
    finally:
        session.close()


def validate_retrieved_state(state: Dict) -> Tuple[bool, List[str]]:
    """Validate a retrieved analytical state meets C.10 contract."""
    errors = []

    if not isinstance(state, dict):
        errors.append("State must be a dict")
        return False, errors

    if "historical_state" not in state and "retrieval_metadata" not in state:
        errors.append("Missing expected state structure")

    # Decision must be read-only
    decision = state.get("historical_state", {}).get("decision", {})
    if decision.get("source") not in ("existing_decision_engine", "reconstructed_fallback", None):
        errors.append("Decision source must be read-only")

    # No BUY/SELL generation
    state_str = str(state).upper()
    if "RECOMMENDED_ACTION" in state_str or "BUY_PROBABILITY" in state_str or "SELL_PROBABILITY" in state_str:
        errors.append("State must not contain decision authority fields")

    return len(errors) == 0, errors
