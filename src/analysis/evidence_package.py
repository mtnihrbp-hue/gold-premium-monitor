"""Evidence Package Builder — PRE-SP-C.6

Deterministic assembly of normalized evidence from all analytical primitives.
No prediction, no LLM, no trading decisions.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Dict, List, Optional, Any, Tuple

from database.repository import (
    get_recent_news_events,
    get_similar_market_states,
    get_outcome_evaluations_by_snapshot,
    get_analysis_snapshots,
)

EVIDENCE_SCHEMA_VERSION = "1"


def _safe_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_evidence_package(
    analysis_timestamp: datetime,
    source_run_id: str,
    market_snapshot,
    market_state,
    rep_price,
    structure_state,
    regime_result,
    classifier,
    data_quality: Dict,
    technical_state_json: Optional[Dict],
    config: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Build a deterministic evidence package from analytical primitives.

    Args:
        analysis_timestamp: snapshot timestamp
        source_run_id: deterministic run ID
        market_snapshot: latest MarketSnapshot or None
        market_state: latest MarketState or None
        rep_price: RepresentativePrice result or None
        structure_state: StructureState result or None
        regime_result: RegimeResult from classifier
        classifier: RegimeClassifier instance
        data_quality: data quality tracking dict
        technical_state_json: pre-built technical state JSON
        config: optional configuration dict

    Returns:
        deterministic evidence package dict
    """
    if config is None:
        config = {}

    evidence_cfg = config.get("evidence", {})
    news_window_hours = evidence_cfg.get("news_window_hours", 6)
    outcome_lookback_hours = evidence_cfg.get("outcome_lookback_hours", 72)
    max_historical_context = evidence_cfg.get("max_historical_context", 5)
    max_outcome_context = evidence_cfg.get("max_outcome_context", 5)

    package = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "generated_at": analysis_timestamp.isoformat(),
    }

    # --- PROVENANCE ---
    package["provenance"] = {
        "source_run_id": source_run_id,
        "analysis_timestamp": analysis_timestamp.isoformat(),
        "market_snapshot_id": getattr(market_snapshot, "id", None) if market_snapshot else None,
        "market_state_id": getattr(market_state, "id", None) if market_state else None,
    }

    # --- VALUATION ---
    valuation = {
        "premium_percent": _safe_float(getattr(market_snapshot, "premium_percent", None)),
        "valuation_state": getattr(market_state, "valuation_state", "UNKNOWN") if market_state else "UNKNOWN",
        "fair_price": _safe_float(getattr(market_snapshot, "fair_price", None)),
        "lowest_market_price": None,
        "status": "INSUFFICIENT_DATA",
    }
    if market_snapshot and market_snapshot.premium_percent is not None:
        valuation["status"] = "AVAILABLE"
    package["valuation"] = valuation

    # --- MOMENTUM ---
    momentum = {
        "momentum_state": getattr(market_state, "momentum_state", "UNKNOWN") if market_state else "UNKNOWN",
        "premium_direction": getattr(market_state, "premium_direction", "UNKNOWN") if market_state else "UNKNOWN",
        "status": "INSUFFICIENT_DATA",
    }
    if market_state and market_state.momentum_state not in (None, "UNKNOWN"):
        momentum["status"] = "AVAILABLE"
    package["momentum"] = momentum

    # --- TECHNICAL STRUCTURE ---
    tech = {
        "representative_price": None,
        "support_levels": [],
        "resistance_levels": [],
        "status": "INSUFFICIENT_DATA",
    }
    if technical_state_json:
        tech["representative_price"] = technical_state_json.get("representative_price")
        tech["support_levels"] = technical_state_json.get("support_levels", [])
        tech["resistance_levels"] = technical_state_json.get("resistance_levels", [])
        tech["status"] = technical_state_json.get("structure_status", "INSUFFICIENT_DATA")
    package["technical_structure"] = tech

    # --- REGIME ---
    regime = {
        "regime_state": getattr(regime_result, "state", "UNKNOWN") if regime_result else "UNKNOWN",
        "previous_regime": getattr(regime_result, "previous_state", None) if regime_result else None,
        "candidate_state": getattr(classifier, "_candidate_state", None) if classifier else None,
        "confirmation_count": getattr(classifier, "_confirmation_count", 0) if classifier else 0,
        "status": "AVAILABLE" if regime_result and getattr(regime_result, "state", "UNKNOWN") != "UNKNOWN" else "INSUFFICIENT_DATA",
    }
    package["regime"] = regime

    # --- XAU/USD ---
    xau = {
        "price": _safe_float(getattr(market_snapshot, "world_gold_usd", None)),
        "timestamp": None,
        "freshness": "UNKNOWN",
        "status": "INSUFFICIENT_DATA",
    }
    if market_snapshot and market_snapshot.timestamp:
        xau["timestamp"] = market_snapshot.timestamp.isoformat()
    if market_snapshot and market_snapshot.world_gold_usd is not None:
        xau["status"] = "AVAILABLE"
        xau["freshness"] = data_quality.get("xau_usd", "UNKNOWN") if isinstance(data_quality, dict) else "UNKNOWN"
    package["xau_usd"] = xau

    # --- USD/IRR ---
    usd = {
        "price": _safe_float(getattr(market_snapshot, "usd_irr", None)),
        "timestamp": None,
        "freshness": "UNKNOWN",
        "status": "INSUFFICIENT_DATA",
    }
    if market_snapshot and market_snapshot.timestamp:
        usd["timestamp"] = market_snapshot.timestamp.isoformat()
    if market_snapshot and market_snapshot.usd_irr is not None:
        usd["status"] = "AVAILABLE"
        usd["freshness"] = data_quality.get("usd_irr", "UNKNOWN") if isinstance(data_quality, dict) else "UNKNOWN"
    package["usd_irr"] = usd

    # --- REPRESENTATIVE GOLD ---
    rep_gold = {
        "price": _safe_float(getattr(rep_price, "price", None)) if rep_price else None,
        "source": getattr(rep_price, "source", "UNKNOWN") if rep_price else "UNKNOWN",
        "fallback_status": "UNKNOWN",
        "status": "INSUFFICIENT_DATA",
    }
    if rep_price and getattr(rep_price, "status", None) == "AVAILABLE":
        rep_gold["status"] = "AVAILABLE"
        if getattr(rep_price, "source", None) == "milli":
            rep_gold["fallback_status"] = "PRIMARY"
        else:
            rep_gold["fallback_status"] = "FALLBACK"
    package["representative_gold"] = rep_gold

    # --- PLATFORM STRUCTURE ---
    platform = {
        "active_platform_count": None,
        "platform_high": _safe_float(getattr(market_state, "platform_high", None)),
        "platform_low": _safe_float(getattr(market_state, "platform_low", None)),
        "platform_spread": _safe_float(getattr(market_state, "platform_spread", None)),
        "platforms_below_fair": _safe_int(getattr(market_state, "platforms_below_fair", None)),
        "platforms_above_fair": _safe_int(getattr(market_state, "platforms_above_fair", None)),
        "status": "INSUFFICIENT_DATA",
    }
    if market_state and getattr(market_state, "structure_state", None) not in (None, "UNKNOWN"):
        platform["status"] = "AVAILABLE"
    package["platform_structure"] = platform

    # --- NEWS CONTEXT ---
    news_pkg = {
        "recent_event_count": 0,
        "high_impact_count": 0,
        "latest_events": [],
        "status": "INSUFFICIENT_DATA",
    }
    try:
        news_events = get_recent_news_events(hours=news_window_hours, limit=20)
        if news_events:
            news_pkg["recent_event_count"] = len(news_events)
            news_pkg["high_impact_count"] = sum(
                1 for n in news_events if getattr(n, "relevance", "") in ("HIGH", "CRITICAL")
            )
            news_pkg["latest_events"] = [
                {
                    "event_type": getattr(n, "event_type", "UNKNOWN"),
                    "relevance": getattr(n, "relevance", "UNKNOWN"),
                    "impact": getattr(n, "impact", None),
                    "topic": getattr(n, "topic", None),
                    "timestamp": getattr(n, "timestamp", None).isoformat() if getattr(n, "timestamp", None) else None,
                }
                for n in news_events[:5]
            ]
            news_pkg["status"] = "AVAILABLE"
    except Exception:
        pass
    package["news_context"] = news_pkg

    # --- HISTORICAL CONTEXT ---
    hist_pkg = {
        "similar_state_count": None,
        "recent_similar_states": [],
        "status": "INSUFFICIENT_DATA",
    }
    try:
        if market_state:
            ref = SimpleNamespace(
                valuation=getattr(market_state, "valuation_state", "UNKNOWN"),
                momentum=getattr(market_state, "momentum_state", "UNKNOWN"),
                premium_direction=getattr(market_state, "premium_direction", "UNKNOWN"),
                structure=getattr(market_state, "structure_state", "UNKNOWN"),
                premium=_safe_float(getattr(market_snapshot, "premium_percent", 0.0)) or 0.0,
            )
            comparison = get_similar_market_states(ref)
            matches = getattr(comparison, "matches", None) or []
            if matches:
                hist_pkg["similar_state_count"] = len(matches)
                hist_pkg["recent_similar_states"] = [
                    {
                        "valuation": getattr(m, "valuation_state", "UNKNOWN"),
                        "momentum": getattr(m, "momentum_state", "UNKNOWN"),
                        "structure": getattr(m, "structure_state", "UNKNOWN"),
                        "timestamp": getattr(m, "timestamp", None).isoformat() if getattr(m, "timestamp", None) else None,
                    }
                    for m in matches[:max_historical_context]
                ]
                hist_pkg["status"] = "AVAILABLE"
    except Exception:
        pass
    package["historical_context"] = hist_pkg

    # --- OUTCOME CONTEXT ---
    outcome_pkg = {
        "recent_evaluated_snapshots": 0,
        "latest_outcomes": [],
        "status": "INSUFFICIENT_DATA",
    }
    try:
        recent_snapshots = get_analysis_snapshots(limit=max_outcome_context * 2, hours=outcome_lookback_hours)
        outcomes = []
        for snap in recent_snapshots:
            snap_id = getattr(snap, "id", None)
            if snap_id is None:
                continue
            evals = get_outcome_evaluations_by_snapshot(snap_id)
            if evals:
                outcomes.append({
                    "snapshot_id": snap_id,
                    "analysis_timestamp": snap.analysis_timestamp.isoformat() if snap.analysis_timestamp else None,
                    "evaluations": [
                        {
                            "horizon": e.horizon_hours,
                            "status": e.outcome_status,
                            "rep_gold_direction": getattr(e, "rep_gold_direction", None),
                            "xau_usd_direction": getattr(e, "xau_usd_direction", None),
                            "usd_irr_direction": getattr(e, "usd_irr_direction", None),
                        }
                        for e in evals
                    ],
                })
        if outcomes:
            outcome_pkg["recent_evaluated_snapshots"] = len(outcomes)
            outcome_pkg["latest_outcomes"] = outcomes[:max_outcome_context]
            outcome_pkg["status"] = "AVAILABLE"
    except Exception:
        pass
    package["outcome_context"] = outcome_pkg

    # --- DATA QUALITY ---
    dq = {
        "overall": "UNKNOWN",
        "components": {},
        "missing": [],
        "stale": [],
        "warnings": [],
    }
    if isinstance(data_quality, dict):
        dq["overall"] = data_quality.get("overall", "UNKNOWN")
        for key, val in data_quality.items():
            if key != "overall":
                dq["components"][key] = val
                if val in ("UNAVAILABLE", "INSUFFICIENT_DATA", "UNKNOWN"):
                    dq["missing"].append(key)
                elif val == "STALE":
                    dq["stale"].append(key)
    package["data_quality"] = dq

    return package


def validate_evidence_package(package: Dict) -> Tuple[bool, List[str]]:
    """Deterministically validate an evidence package.

    Returns:
        (is_valid, list_of_error_messages)
    """
    errors = []

    if not isinstance(package, dict):
        errors.append("Package must be a dict")
        return False, errors

    # Schema version
    if package.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        errors.append(f"Schema version must be '{EVIDENCE_SCHEMA_VERSION}'")

    # Required top-level sections
    required_sections = [
        "schema_version", "generated_at", "provenance", "valuation",
        "momentum", "technical_structure", "regime", "xau_usd", "usd_irr",
        "representative_gold", "platform_structure", "news_context",
        "historical_context", "outcome_context", "data_quality",
    ]
    for section in required_sections:
        if section not in package:
            errors.append(f"Missing required section: {section}")

    # No BUY/SELL anywhere in the package
    package_str = str(package).upper()
    for forbidden in ["'BUY'", "'SELL'", "\"BUY\"", "\"SELL\""]:
        if forbidden.upper().replace("'", "").replace('"', '') in package_str:
            # More precise check: look for decision language in values
            pass

    # Simpler: flatten and check string values
    def _check_values(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                _check_values(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                _check_values(v, f"{path}[{i}]")
        elif isinstance(obj, str):
            upper = obj.upper()
            if "BUY" in upper or "SELL" in upper:
                errors.append(f"Evidence package must not contain decision language at {path}: {obj}")

    _check_values(package)

    # Provenance checks
    prov = package.get("provenance", {})
    if not prov.get("source_run_id"):
        errors.append("Provenance missing source_run_id")
    if not prov.get("analysis_timestamp"):
        errors.append("Provenance missing analysis_timestamp")

    # Numeric validation for key fields
    for section_name, field_name in [
        ("valuation", "premium_percent"),
        ("xau_usd", "price"),
        ("usd_irr", "price"),
        ("representative_gold", "price"),
    ]:
        section = package.get(section_name, {})
        val = section.get(field_name)
        if val is not None and not isinstance(val, (int, float)):
            errors.append(f"{section_name}.{field_name} must be numeric")

    # Data quality must be a dict
    dq = package.get("data_quality", {})
    if not isinstance(dq, dict):
        errors.append("data_quality must be a dict")

    return len(errors) == 0, errors
