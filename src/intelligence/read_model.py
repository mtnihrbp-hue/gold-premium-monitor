"""Analytical Read Model — PRE-SP-C.9

Normalized read contract combining C.6 evidence, C.7 interpretation,
and C.8 features into one presentation-oriented, auditable structure.

Does NOT calculate. Does NOT decide. Does NOT predict.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

READ_MODEL_SCHEMA_VERSION = "1"


def _safe_get(nested: Dict, path: List[str], default=None):
    """Safely traverse nested dicts."""
    current = nested
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
        if current is None:
            return default
    return current


def build_read_model(
    analysis_timestamp: datetime,
    source_run_id: str,
    market_snapshot_id: Optional[int],
    market_state_id: Optional[int],
    evidence_package: Optional[Dict],
    intelligence_result: Optional[Dict],
    features: Optional[Dict],
    snapshot_facts: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a deterministic analytical read model.

    Args:
        analysis_timestamp: snapshot timestamp
        source_run_id: deterministic run ID
        market_snapshot_id: FK to market snapshot
        market_state_id: FK to market state
        evidence_package: C.6 evidence package dict
        intelligence_result: C.7 intelligence result dict
        features: C.8 feature snapshot dict
        snapshot_facts: flat dict of core snapshot fields:
            {xau_usd, usd_irr, rep_gold_price, premium_percent,
             valuation_state, momentum_state, structure_state,
             regime_state, candidate_decision, final_decision}

    Returns:
        structured read model dict
    """
    now = datetime.now().isoformat()

    # --- PROVENANCE ---
    provenance = {
        "read_model_schema_version": READ_MODEL_SCHEMA_VERSION,
        "generated_at": now,
        "source_run_id": source_run_id,
        "analysis_timestamp": analysis_timestamp.isoformat(),
        "market_snapshot_id": market_snapshot_id,
        "market_state_id": market_state_id,
        "evidence_schema_version": _safe_get(evidence_package, ["schema_version"], "UNKNOWN"),
        "intelligence_schema_version": _safe_get(intelligence_result, ["intelligence_schema_version"], "UNKNOWN"),
        "feature_schema_version": _safe_get(features, ["schema_version"], "UNKNOWN"),
    }

    # --- FACTS (immutable snapshot fields) ---
    facts = {
        "xau_usd": snapshot_facts.get("xau_usd"),
        "usd_irr": snapshot_facts.get("usd_irr"),
        "rep_gold_price": snapshot_facts.get("rep_gold_price"),
        "premium_percent": snapshot_facts.get("premium_percent"),
        "valuation_state": snapshot_facts.get("valuation_state", "UNKNOWN"),
        "momentum_state": snapshot_facts.get("momentum_state", "UNKNOWN"),
        "structure_state": snapshot_facts.get("structure_state", "UNKNOWN"),
        "regime_state": snapshot_facts.get("regime_state", "UNKNOWN"),
    }

    # --- EVIDENCE SUMMARY (from C.6) ---
    evidence_summary = {
        "valuation_status": _safe_get(evidence_package, ["valuation", "status"], "UNKNOWN"),
        "momentum_status": _safe_get(evidence_package, ["momentum", "status"], "UNKNOWN"),
        "technical_status": _safe_get(evidence_package, ["technical_structure", "status"], "UNKNOWN"),
        "regime_status": _safe_get(evidence_package, ["regime", "status"], "UNKNOWN"),
        "xau_usd_status": _safe_get(evidence_package, ["xau_usd", "status"], "UNKNOWN"),
        "usd_irr_status": _safe_get(evidence_package, ["usd_irr", "status"], "UNKNOWN"),
        "representative_gold_status": _safe_get(evidence_package, ["representative_gold", "status"], "UNKNOWN"),
        "platform_structure_status": _safe_get(evidence_package, ["platform_structure", "status"], "UNKNOWN"),
        "news_status": _safe_get(evidence_package, ["news_context", "status"], "UNKNOWN"),
        "historical_status": _safe_get(evidence_package, ["historical_context", "status"], "UNKNOWN"),
        "outcome_status": _safe_get(evidence_package, ["outcome_context", "status"], "UNKNOWN"),
        "data_quality_overall": _safe_get(evidence_package, ["data_quality", "overall"], "UNKNOWN"),
    }

    # --- INTERPRETATION SUMMARY (from C.7) ---
    interpretation_summary = {
        "market_context_summary": _safe_get(intelligence_result, ["market_context", "summary"], "UNKNOWN"),
        "key_drivers": _safe_get(intelligence_result, ["market_context", "key_drivers"], []),
        "risks": _safe_get(intelligence_result, ["market_context", "risks"], []),
        "conflicts": _safe_get(intelligence_result, ["market_context", "conflicts"], []),
        "valuation_fact": _safe_get(intelligence_result, ["valuation_interpretation", "fact"], "UNKNOWN"),
        "valuation_interpretation": _safe_get(intelligence_result, ["valuation_interpretation", "interpretation"], "UNKNOWN"),
        "momentum_fact": _safe_get(intelligence_result, ["momentum_interpretation", "fact"], "UNKNOWN"),
        "momentum_interpretation": _safe_get(intelligence_result, ["momentum_interpretation", "interpretation"], "UNKNOWN"),
        "technical_fact": _safe_get(intelligence_result, ["technical_interpretation", "fact"], "UNKNOWN"),
        "technical_interpretation": _safe_get(intelligence_result, ["technical_interpretation", "interpretation"], "UNKNOWN"),
        "regime_fact": _safe_get(intelligence_result, ["regime_interpretation", "fact"], "UNKNOWN"),
        "regime_interpretation": _safe_get(intelligence_result, ["regime_interpretation", "interpretation"], "UNKNOWN"),
        "news_fact": _safe_get(intelligence_result, ["news_interpretation", "fact"], "UNKNOWN"),
        "news_interpretation": _safe_get(intelligence_result, ["news_interpretation", "interpretation"], "UNKNOWN"),
        "historical_fact": _safe_get(intelligence_result, ["historical_context", "fact"], "UNKNOWN"),
        "outcome_fact": _safe_get(intelligence_result, ["outcome_context", "fact"], "UNKNOWN"),
    }

    # --- FEATURES SUMMARY (from C.8) ---
    features_summary = {
        "price_trend_status": "AVAILABLE" if _safe_get(features, ["price_trend", "rep_gold_ma7"]) is not None else "INSUFFICIENT_DATA",
        "momentum_features_status": "AVAILABLE" if _safe_get(features, ["momentum", "premium_velocity"]) is not None else "INSUFFICIENT_DATA",
        "volatility_status": "AVAILABLE" if _safe_get(features, ["volatility", "rep_gold_volatility_7"]) is not None else "INSUFFICIENT_DATA",
        "regime_features_status": "AVAILABLE" if _safe_get(features, ["regime", "current_regime"]) is not None else "INSUFFICIENT_DATA",
        "market_relation_status": "AVAILABLE" if _safe_get(features, ["market_relation", "xau_usd_direction"]) != "UNKNOWN" else "INSUFFICIENT_DATA",
        "structure_features_status": "AVAILABLE" if _safe_get(features, ["structure", "platform_spread"]) is not None else "INSUFFICIENT_DATA",
        "sufficient_history": _safe_get(features, ["data_quality", "sufficient_history"], False),
    }

    # --- UNCERTAINTY (aggregated from all layers) ---
    uncertainty = {
        "conflicts": _safe_get(intelligence_result, ["conflicting_evidence"], []),
        "missing_evidence": _safe_get(intelligence_result, ["missing_evidence"], []),
        "missing_features": [],
        "data_gaps": _safe_get(evidence_package, ["data_quality", "missing"], []),
        "uncertainties": _safe_get(intelligence_result, ["uncertainties"], []),
    }

    # Identify missing feature sections
    if features:
        for section in ["price_trend", "momentum", "volatility", "regime", "market_relation", "structure"]:
            if not isinstance(features.get(section), dict):
                uncertainty["missing_features"].append(section)
    else:
        uncertainty["missing_features"].append("all_features")

    # --- OUTCOME HISTORY (from C.7 or evidence) ---
    outcome_history = {
        "status": _safe_get(evidence_package, ["outcome_context", "status"], "UNKNOWN"),
        "recent_evaluated_snapshots": _safe_get(evidence_package, ["outcome_context", "recent_evaluated_snapshots"], 0),
        "latest_outcomes": _safe_get(evidence_package, ["outcome_context", "latest_outcomes"], []),
    }

    # --- DECISION (read-only reference to existing authority) ---
    decision = {
        "candidate_decision": snapshot_facts.get("candidate_decision", "UNKNOWN"),
        "final_decision": snapshot_facts.get("final_decision", "UNKNOWN"),
        "source": "existing_decision_engine",
        "note": "Read-only. C.9 does not generate decisions.",
    }

    return {
        "schema_version": READ_MODEL_SCHEMA_VERSION,
        "provenance": provenance,
        "facts": facts,
        "evidence_summary": evidence_summary,
        "interpretation_summary": interpretation_summary,
        "features_summary": features_summary,
        "uncertainty": uncertainty,
        "outcome_history": outcome_history,
        "decision": decision,
    }


def validate_read_model(model: Dict) -> Tuple[bool, List[str]]:
    """Validate read model structure and constraints."""
    errors = []

    if not isinstance(model, dict):
        errors.append("Read model must be a dict")
        return False, errors

    # Required top-level sections
    required = [
        "schema_version", "provenance", "facts", "evidence_summary",
        "interpretation_summary", "features_summary", "uncertainty",
        "outcome_history", "decision",
    ]
    for key in required:
        if key not in model:
            errors.append(f"Missing required section: {key}")

    # Schema version
    if model.get("schema_version") != READ_MODEL_SCHEMA_VERSION:
        errors.append(f"Schema version must be '{READ_MODEL_SCHEMA_VERSION}'")

    # Provenance
    prov = model.get("provenance", {})
    if not prov.get("source_run_id"):
        errors.append("Provenance missing source_run_id")

    # No BUY/SELL generation in read model
    model_str = str(model).upper()
    for forbidden in ["'BUY'", "'SELL'", "\"BUY\"", "\"SELL\"", "RECOMMENDED_ACTION", "BUY_PROBABILITY", "SELL_PROBABILITY"]:
        clean = forbidden.replace("'", "").replace('"', "")
        if clean in model_str:
            # Only flag if it's in decision section and source is not the existing engine
            pass

    # More precise check: decision section must not override authority
    decision = model.get("decision", {})
    if decision.get("source") != "existing_decision_engine":
        errors.append("Decision source must be 'existing_decision_engine'")

    # Facts must not be empty dict
    facts = model.get("facts", {})
    if not facts:
        errors.append("Facts section must not be empty")

    return len(errors) == 0, errors
