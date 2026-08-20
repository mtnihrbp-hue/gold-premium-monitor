"""Bounded Market Intelligence — PRE-SP-C.7

Deterministic intelligence interpretation layer.
Consumes the C.6 evidence package and produces structured interpretations.
No LLM required. No BUY/SELL authority. Safe degradation when evidence missing.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

INTELLIGENCE_SCHEMA_VERSION = "1"


def _fmt(val) -> str:
    if val is None:
        return "UNKNOWN"
    if isinstance(val, float):
        return f"{val:.4f}"
    return str(val)


def _build_interpretation_triplet(
    fact_parts: List[str],
    interpretation_parts: List[str],
    uncertainty_parts: List[str],
) -> Dict[str, str]:
    return {
        "fact": " ".join(fact_parts) if fact_parts else "INSUFFICIENT_DATA",
        "interpretation": " ".join(interpretation_parts) if interpretation_parts else "INSUFFICIENT_DATA",
        "uncertainty": " ".join(uncertainty_parts) if uncertainty_parts else "INSUFFICIENT_DATA",
    }


def _detect_conflicts(evidence: Dict) -> Tuple[List[str], List[str], List[str]]:
    """Detect aligned, conflicting, and missing evidence.

    Returns: (aligned, conflicting, missing)
    """
    aligned = []
    conflicting = []
    missing = []

    valuation = evidence.get("valuation", {})
    momentum = evidence.get("momentum", {})
    regime = evidence.get("regime", {})
    tech = evidence.get("technical_structure", {})
    platform = evidence.get("platform_structure", {})
    news = evidence.get("news_context", {})
    historical = evidence.get("historical_context", {})
    outcome = evidence.get("outcome_context", {})
    dq = evidence.get("data_quality", {})

    # Valuation vs Momentum conflicts
    val_state = valuation.get("valuation_state", "UNKNOWN")
    prem_dir = momentum.get("premium_direction", "UNKNOWN")
    mom_state = momentum.get("momentum_state", "UNKNOWN")

    if val_state == "CHEAP" and prem_dir == "DISCOUNT WIDENING":
        conflicting.append("CHEAP valuation vs DISCOUNT WIDENING indicates price may fall further")
    elif val_state == "CHEAP" and prem_dir == "DISCOUNT NARROWING":
        aligned.append("CHEAP valuation and DISCOUNT NARROWING suggest recovery")
    elif val_state == "EXPENSIVE" and prem_dir == "PREMIUM WIDENING":
        aligned.append("EXPENSIVE valuation and PREMIUM WIDENING suggest continued premium expansion")
    elif val_state == "EXPENSIVE" and prem_dir == "PREMIUM NARROWING":
        conflicting.append("EXPENSIVE valuation vs PREMIUM NARROWING indicates price may correct")

    if val_state == "UNKNOWN" or val_state is None:
        missing.append("Valuation state unavailable")

    if mom_state == "UNKNOWN" or mom_state is None:
        missing.append("Momentum state unavailable")

    # Regime uncertainty
    reg_state = regime.get("regime_state", "UNKNOWN")
    prev_reg = regime.get("previous_regime", "UNKNOWN")
    candidate = regime.get("candidate_state", None)

    if reg_state == "PANIC":
        conflicting.append("PANIC regime increases execution risk regardless of valuation")
    if candidate is not None and candidate != reg_state:
        missing.append(f"Regime transition pending: candidate={candidate}, current={reg_state}")

    # Technical
    if tech.get("status") == "INSUFFICIENT_DATA":
        missing.append("Technical structure data insufficient")

    # Platform
    if platform.get("status") == "INSUFFICIENT_DATA":
        missing.append("Platform structure data insufficient")

    # News
    if news.get("status") == "INSUFFICIENT_DATA":
        missing.append("News context unavailable")
    elif news.get("high_impact_count", 0) > 0:
        aligned.append(f"High-impact news detected: {news['high_impact_count']} event(s)")

    # Historical
    if historical.get("status") == "INSUFFICIENT_DATA":
        missing.append("Historical context unavailable")

    # Outcome
    if outcome.get("status") == "INSUFFICIENT_DATA":
        missing.append("Outcome feedback context unavailable")

    # Data quality
    missing_components = dq.get("missing", [])
    if missing_components:
        missing.extend([f"Missing data: {m}" for m in missing_components])

    stale_components = dq.get("stale", [])
    if stale_components:
        missing.extend([f"Stale data: {s}" for s in stale_components])

    return aligned, conflicting, missing


def build_intelligence_result(
    evidence_package: Dict[str, Any],
    model_provider: str = "deterministic_fallback",
    prompt_version: str = "1",
) -> Dict[str, Any]:
    """Build a deterministic intelligence result from an evidence package.

    Args:
        evidence_package: structured evidence package from C.6
        model_provider: identifier for the interpretation engine
        prompt_version: version identifier for reproducibility

    Returns:
        structured intelligence result dict
    """
    if not evidence_package or not isinstance(evidence_package, dict):
        return _build_fallback_intelligence(model_provider, prompt_version)

    now = datetime.now().isoformat()
    evidence_schema = evidence_package.get("schema_version", "UNKNOWN")
    provenance = evidence_package.get("provenance", {})

    valuation = evidence_package.get("valuation", {})
    momentum = evidence_package.get("momentum", {})
    tech = evidence_package.get("technical_structure", {})
    regime = evidence_package.get("regime", {})
    xau = evidence_package.get("xau_usd", {})
    usd = evidence_package.get("usd_irr", {})
    rep = evidence_package.get("representative_gold", {})
    platform = evidence_package.get("platform_structure", {})
    news = evidence_package.get("news_context", {})
    historical = evidence_package.get("historical_context", {})
    outcome = evidence_package.get("outcome_context", {})
    dq = evidence_package.get("data_quality", {})

    aligned, conflicting, missing = _detect_conflicts(evidence_package)

    # Build uncertainties list
    uncertainties = []
    if conflicting:
        uncertainties.extend([f"Conflict: {c}" for c in conflicting])
    if missing:
        uncertainties.extend([f"Gap: {m}" for m in missing])

    # Market context summary
    summary_parts = []
    if valuation.get("status") == "AVAILABLE":
        summary_parts.append(f"Valuation is {valuation.get('valuation_state')} (premium {_fmt(valuation.get('premium_percent'))}%)")
    if momentum.get("status") == "AVAILABLE":
        summary_parts.append(f"Momentum is {momentum.get('momentum_state')}")
    if regime.get("status") == "AVAILABLE":
        summary_parts.append(f"Regime is {regime.get('regime_state')}")
    if not summary_parts:
        summary_parts.append("Insufficient data for market context summary")

    key_drivers = []
    if xau.get("status") == "AVAILABLE":
        key_drivers.append(f"XAU/USD at {_fmt(xau.get('price'))}")
    if usd.get("status") == "AVAILABLE":
        key_drivers.append(f"USD/IRR at {_fmt(usd.get('price'))}")
    if rep.get("status") == "AVAILABLE":
        key_drivers.append(f"Representative gold at {_fmt(rep.get('price'))} ({rep.get('source')})")

    risks = []
    if regime.get("regime_state") == "PANIC":
        risks.append("PANIC regime elevates execution risk")
    if regime.get("regime_state") == "FEAR":
        risks.append("FEAR regime indicates stressed conditions")
    if news.get("high_impact_count", 0) > 0:
        risks.append("High-impact news events present")
    if dq.get("overall") == "DEGRADED":
        risks.append("Data quality is degraded")

    # Valuation interpretation
    val_fact = []
    val_interp = []
    val_unc = []
    if valuation.get("status") == "AVAILABLE":
        val_fact.append(f"premium_percent={_fmt(valuation.get('premium_percent'))}, valuation_state={valuation.get('valuation_state')}")
        if valuation.get("valuation_state") == "CHEAP":
            val_interp.append("Market is trading below fair value.")
        elif valuation.get("valuation_state") == "EXPENSIVE":
            val_interp.append("Market is trading above fair value.")
        else:
            val_interp.append("Market is near fair value.")
        val_unc.append("Fair value calculation depends on USD/IRR and world gold assumptions.")
    else:
        val_fact.append("Valuation data unavailable")
        val_unc.append("Cannot assess valuation without premium and fair price data.")

    # Momentum interpretation
    mom_fact = []
    mom_interp = []
    mom_unc = []
    if momentum.get("status") == "AVAILABLE":
        mom_fact.append(f"momentum_state={momentum.get('momentum_state')}, premium_direction={momentum.get('premium_direction')}")
        mom_interp.append(f"Momentum is {momentum.get('momentum_state').lower()} with {momentum.get('premium_direction').lower().replace('_', ' ')}.")
        if momentum.get("momentum_state") == "IMPROVING" and momentum.get("premium_direction") == "DISCOUNT WIDENING":
            mom_unc.append("Directional tension: momentum improving but discount widening.")
    else:
        mom_fact.append("Momentum data unavailable")
        mom_unc.append("Cannot assess momentum without state and direction data.")

    # Technical interpretation
    tech_fact = []
    tech_interp = []
    tech_unc = []
    if tech.get("status") == "AVAILABLE":
        support = tech.get("support_levels", [])
        resistance = tech.get("resistance_levels", [])
        rep_price = tech.get("representative_price", {})
        if rep_price:
            tech_fact.append(f"Representative price: {_fmt(rep_price.get('price'))} from {rep_price.get('source', 'UNKNOWN')}")
        if support:
            tech_fact.append(f"Support: {len(support)} level(s)")
        if resistance:
            tech_fact.append(f"Resistance: {len(resistance)} level(s)")
        tech_interp.append("Price is between established technical levels.")
        if not support or not resistance:
            tech_unc.append("Insufficient history for strong level confidence.")
    else:
        tech_fact.append("Technical structure data unavailable")
        tech_unc.append("Cannot assess technical structure without support/resistance data.")

    # Regime interpretation
    reg_fact = []
    reg_interp = []
    reg_unc = []
    if regime.get("status") == "AVAILABLE":
        reg_fact.append(f"regime_state={regime.get('regime_state')}, previous={regime.get('previous_regime')}")
        reg_interp.append(f"Market is in a {regime.get('regime_state').lower()} regime.")
        if regime.get("candidate_state"):
            reg_unc.append(f"Regime transition pending: candidate={regime.get('candidate_state')}, confirmations={regime.get('confirmation_count', 0)}")
    else:
        reg_fact.append("Regime data unavailable")
        reg_unc.append("Cannot assess regime without classification data.")

    # News interpretation
    news_fact = []
    news_interp = []
    news_unc = []
    if news.get("status") == "AVAILABLE":
        news_fact.append(f"Recent events: {news.get('recent_event_count', 0)}, high-impact: {news.get('high_impact_count', 0)}")
        if news.get("recent_event_count", 0) == 0:
            news_interp.append("No recent news events detected.")
        else:
            news_interp.append("Recent news flow present.")
        news_unc.append("News coverage may be incomplete.")
    else:
        news_fact.append("News context unavailable")
        news_unc.append("Cannot assess news impact without event data.")

    # Historical interpretation
    hist_fact = []
    hist_interp = []
    hist_unc = []
    if historical.get("status") == "AVAILABLE":
        hist_fact.append(f"Similar state count: {historical.get('similar_state_count', 'UNKNOWN')}")
        hist_interp.append("Historical comparable states exist.")
    else:
        hist_fact.append("Historical context unavailable")
        hist_unc.append("Cannot assess historical parallels without sufficient data.")

    # Outcome interpretation
    out_fact = []
    out_interp = []
    out_unc = []
    if outcome.get("status") == "AVAILABLE":
        out_fact.append(f"Recent evaluated snapshots: {outcome.get('recent_evaluated_snapshots', 0)}")
        if outcome.get("recent_evaluated_snapshots", 0) == 0:
            out_interp.append("No recent outcome evaluations.")
        else:
            out_interp.append("Outcome feedback available.")
    else:
        out_fact.append("Outcome context unavailable")
        out_unc.append("Cannot assess outcome feedback without evaluation data.")

    result = {
        "schema_version": INTELLIGENCE_SCHEMA_VERSION,
        "intelligence_schema_version": INTELLIGENCE_SCHEMA_VERSION,
        "generated_at": now,
        "model_provider": model_provider,
        "prompt_version": prompt_version,
        "market_context": {
            "summary": " ".join(summary_parts),
            "key_drivers": key_drivers,
            "risks": risks,
            "conflicts": conflicting,
        },
        "valuation_interpretation": _build_interpretation_triplet(val_fact, val_interp, val_unc),
        "momentum_interpretation": _build_interpretation_triplet(mom_fact, mom_interp, mom_unc),
        "technical_interpretation": _build_interpretation_triplet(tech_fact, tech_interp, tech_unc),
        "regime_interpretation": _build_interpretation_triplet(reg_fact, reg_interp, reg_unc),
        "news_interpretation": _build_interpretation_triplet(news_fact, news_interp, news_unc),
        "historical_context": _build_interpretation_triplet(hist_fact, hist_interp, hist_unc),
        "outcome_context": _build_interpretation_triplet(out_fact, out_interp, out_unc),
        "aligned_evidence": aligned,
        "conflicting_evidence": conflicting,
        "missing_evidence": missing,
        "uncertainties": uncertainties,
        "provenance": {
            "evidence_schema_version": evidence_schema,
            "source_run_id": provenance.get("source_run_id"),
            "analysis_timestamp": provenance.get("analysis_timestamp"),
        },
    }

    return result


def _build_fallback_intelligence(
    model_provider: str = "deterministic_fallback",
    prompt_version: str = "1",
) -> Dict[str, Any]:
    """Return a safe fallback when evidence is completely unavailable."""
    now = datetime.now().isoformat()
    return {
        "schema_version": INTELLIGENCE_SCHEMA_VERSION,
        "intelligence_schema_version": INTELLIGENCE_SCHEMA_VERSION,
        "generated_at": now,
        "model_provider": model_provider,
        "prompt_version": prompt_version,
        "market_context": {
            "summary": "Insufficient evidence for market context.",
            "key_drivers": [],
            "risks": ["Evidence package unavailable"],
            "conflicts": [],
        },
        "valuation_interpretation": _build_interpretation_triplet([], [], ["Evidence unavailable"]),
        "momentum_interpretation": _build_interpretation_triplet([], [], ["Evidence unavailable"]),
        "technical_interpretation": _build_interpretation_triplet([], [], ["Evidence unavailable"]),
        "regime_interpretation": _build_interpretation_triplet([], [], ["Evidence unavailable"]),
        "news_interpretation": _build_interpretation_triplet([], [], ["Evidence unavailable"]),
        "historical_context": _build_interpretation_triplet([], [], ["Evidence unavailable"]),
        "outcome_context": _build_interpretation_triplet([], [], ["Evidence unavailable"]),
        "aligned_evidence": [],
        "conflicting_evidence": [],
        "missing_evidence": ["All evidence sections"],
        "uncertainties": ["Completely insufficient data"],
        "provenance": {
            "evidence_schema_version": "UNKNOWN",
            "source_run_id": None,
            "analysis_timestamp": None,
        },
    }


def validate_intelligence_result(result: Dict) -> Tuple[bool, List[str]]:
    """Validate that an intelligence result meets the C.7 contract.

    Returns:
        (is_valid, error_messages)
    """
    errors = []

    if not isinstance(result, dict):
        errors.append("Result must be a dict")
        return False, errors

    required_top = [
        "schema_version", "intelligence_schema_version", "generated_at",
        "model_provider", "market_context", "valuation_interpretation",
        "momentum_interpretation", "technical_interpretation",
        "regime_interpretation", "news_interpretation",
        "historical_context", "outcome_context",
        "aligned_evidence", "conflicting_evidence", "missing_evidence",
        "uncertainties", "provenance",
    ]
    for key in required_top:
        if key not in result:
            errors.append(f"Missing required field: {key}")

    # No BUY/SELL decision authority
    result_str = str(result).upper()
    for forbidden in ["BUY", "SELL", "RECOMMENDED_ACTION", "BUY_PROBABILITY", "SELL_PROBABILITY"]:
        if forbidden in result_str:
            errors.append(f"Intelligence result must not contain decision authority: {forbidden}")

    # Validate interpretation triplets
    triplet_keys = [
        "valuation_interpretation", "momentum_interpretation",
        "technical_interpretation", "regime_interpretation",
        "news_interpretation", "historical_context", "outcome_context",
    ]
    for key in triplet_keys:
        triplet = result.get(key, {})
        for sub in ("fact", "interpretation", "uncertainty"):
            if sub not in triplet:
                errors.append(f"{key} missing '{sub}'")

    # Provenance
    prov = result.get("provenance", {})
    if not prov.get("evidence_schema_version"):
        errors.append("Provenance missing evidence_schema_version")

    return len(errors) == 0, errors
