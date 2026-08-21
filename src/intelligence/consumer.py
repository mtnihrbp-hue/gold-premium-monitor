"""Analytical Consumer Interface — PRE-SP-C.11

Stable application-level contract over the C.10 retrieval layer.
Downstream components (Telegram, API, Dashboard) consume this interface.

Does NOT calculate, interpret, decide, predict, or format.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from database.connection import get_session
from database.models import AnalysisSnapshot
from database.repository import get_analysis_snapshots
from intelligence.read_model_integration import (
    get_analysis_read_model,
    reconstruct_historical_state,
    validate_retrieved_state,
    COMPLETENESS_COMPLETE,
    COMPLETENESS_DEGRADED,
    COMPLETENESS_INSUFFICIENT_DATA,
    COMPLETENESS_INVALID,
)

CONSUMER_SCHEMA_VERSION = "1"


def get_analysis(snapshot_id: int) -> Dict[str, Any]:
    """Primary consumer interface: retrieve authoritative analytical state.

    Args:
        snapshot_id: analysis snapshot ID

    Returns:
        consumer envelope containing the C.10 read model and metadata
    """
    read_model = get_analysis_read_model(snapshot_id)

    if read_model is None:
        return _build_not_found_envelope(snapshot_id)

    # Validate the retrieved state meets C.10 contract
    valid, errors = validate_retrieved_state(read_model)
    if not valid:
        return _build_invalid_envelope(snapshot_id, errors)

    completeness = read_model.get("retrieval_metadata", {}).get("completeness_status", "UNKNOWN")

    return {
        "schema_version": CONSUMER_SCHEMA_VERSION,
        "consumer_contract": "analysis_state",
        "snapshot_id": snapshot_id,
        "status": "OK",
        "completeness": completeness,
        "data": read_model,
        "retrieved_at": datetime.now().isoformat(),
        "presentation_note": "Structured data only. No UI formatting included.",
    }


def get_latest_analysis(limit: int = 1) -> List[Dict[str, Any]]:
    """Retrieve the most recent analysis snapshots with read models.

    Args:
        limit: maximum number of snapshots to return

    Returns:
        list of consumer envelopes
    """
    session = get_session()
    if session is None:
        return []

    try:
        snapshots = get_analysis_snapshots(limit=limit, hours=168)
        results = []
        for snap in snapshots:
            snap_id = getattr(snap, "id", None)
            if snap_id is None:
                continue
            consumer_data = get_analysis(snap_id)
            results.append(consumer_data)
        return results
    except Exception as e:
        print(f"Latest analysis retrieval failed: {e}")
        return []
    finally:
        if session:
            session.close()


def get_analysis_summary(snapshot_id: int) -> Dict[str, Any]:
    """Lightweight flattened summary for lightweight consumers.

    Does not replace the full read model. Provides a quick overview.
    """
    full = get_analysis(snapshot_id)

    if full.get("status") != "OK":
        return full

    data = full.get("data", {})
    facts = data.get("facts", {})
    decision = data.get("decision", {})
    completeness = full.get("completeness", "UNKNOWN")

    return {
        "schema_version": CONSUMER_SCHEMA_VERSION,
        "consumer_contract": "analysis_summary",
        "snapshot_id": snapshot_id,
        "status": "OK",
        "completeness": completeness,
        "summary": {
            "valuation_state": facts.get("valuation_state", "UNKNOWN"),
            "momentum_state": facts.get("momentum_state", "UNKNOWN"),
            "regime_state": facts.get("regime_state", "UNKNOWN"),
            "final_decision": decision.get("final_decision", "UNKNOWN"),
            "candidate_decision": decision.get("candidate_decision", "UNKNOWN"),
        },
        "retrieved_at": full.get("retrieved_at"),
        "presentation_note": "Structured data only. No UI formatting included.",
    }


def _build_not_found_envelope(snapshot_id: int) -> Dict[str, Any]:
    return {
        "schema_version": CONSUMER_SCHEMA_VERSION,
        "consumer_contract": "analysis_state",
        "snapshot_id": snapshot_id,
        "status": "NOT_FOUND",
        "completeness": COMPLETENESS_INVALID,
        "data": None,
        "retrieved_at": datetime.now().isoformat(),
        "presentation_note": "Snapshot not found.",
    }


def _build_invalid_envelope(snapshot_id: int, errors: List[str]) -> Dict[str, Any]:
    return {
        "schema_version": CONSUMER_SCHEMA_VERSION,
        "consumer_contract": "analysis_state",
        "snapshot_id": snapshot_id,
        "status": "INVALID",
        "completeness": COMPLETENESS_INVALID,
        "data": None,
        "validation_errors": errors,
        "retrieved_at": datetime.now().isoformat(),
        "presentation_note": "Retrieved state failed validation.",
    }


def validate_consumer_envelope(envelope: Dict) -> Tuple[bool, List[str]]:
    """Validate a consumer envelope meets the C.11 contract."""
    errors = []

    if not isinstance(envelope, dict):
        errors.append("Envelope must be a dict")
        return False, errors

    required = ["schema_version", "consumer_contract", "snapshot_id", "status", "completeness", "data"]
    for key in required:
        if key not in envelope:
            errors.append(f"Missing required field: {key}")

    if envelope.get("schema_version") != CONSUMER_SCHEMA_VERSION:
        errors.append(f"Schema version must be '{CONSUMER_SCHEMA_VERSION}'")

    if envelope.get("consumer_contract") not in ("analysis_state", "analysis_summary"):
        errors.append("Invalid consumer_contract")

    if envelope.get("status") not in ("OK", "NOT_FOUND", "INVALID"):
        errors.append("Invalid status")

    # No UI formatting contamination
    envelope_str = str(envelope).upper()
    ui_markers = ["<B>", "</B>", "<I>", "</I>", "```", "**", "__", "`"]
    for marker in ui_markers:
        if marker in envelope_str:
            errors.append(f"Envelope contains UI formatting: {marker}")

    # No decision authority
    if "RECOMMENDED_ACTION" in envelope_str or "BUY_PROBABILITY" in envelope_str:
        errors.append("Envelope contains decision authority")

    return len(errors) == 0, errors
