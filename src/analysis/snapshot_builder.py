"""Analysis Snapshot builder.

PRE-SP-C.4: integrates representative price, technical structure, and regime
into the scheduled analysis snapshot. Reconstructs regime hysteresis from the
latest persisted snapshot so state survives across independent scheduled runs.
"""
from analysis.outcome_evaluator import run_outcome_evaluation_for_snapshot
from analysis.evidence_package import build_evidence_package, validate_evidence_package
from intelligence.market_intelligence import build_intelligence_result, validate_intelligence_result
from intelligence.features import build_feature_snapshot, validate_feature_snapshot
from intelligence.read_model import build_read_model, validate_read_model

from datetime import datetime
from typing import Optional, Dict

from database.repository import (
    save_analysis_snapshot,
    analysis_snapshot_exists,
    get_latest_market_snapshot,
    get_latest_market_state,
    get_latest_analysis_snapshot,
    get_price_observations_by_instrument,
    get_recent_news_events,
    get_snapshots,
)
from analysis.scheduler import generate_source_run_id
from analysis.representative_price import get_representative_price
from analysis.structure import build_structure_state
from analysis.regime import RegimeClassifier


def _compute_price_volatility(prices: list) -> float:
    """Compute normalized volatility as coefficient of variation (%).

    Args:
        prices: list of float prices (oldest → newest)

    Returns:
        volatility as percentage, or 0.0 if insufficient data.
    """
    if len(prices) < 2:
        return 0.0
    mean_price = sum(prices) / len(prices)
    if mean_price == 0:
        return 0.0
    variance = sum((p - mean_price) ** 2 for p in prices) / len(prices)
    std_dev = variance ** 0.5
    return (std_dev / mean_price) * 100


def _compute_usd_change() -> float:
    """Compute recent USD/IRR percent change from canonical observations.

    Returns:
        percent change, or 0.0 if insufficient data.
    """
    obs = get_price_observations_by_instrument("USD/IRR", limit=2)
    if len(obs) < 2:
        return 0.0
    latest = float(obs[0].price)
    previous = float(obs[1].price)
    if previous == 0:
        return 0.0
    return ((latest - previous) / previous) * 100


def _compute_premium_change() -> float:
    """Compute recent premium percent change from market snapshots.

    Returns:
        premium change, or 0.0 if insufficient data.
    """
    snaps = get_snapshots(days=1)
    if len(snaps) < 2:
        return 0.0
    latest = float(snaps[0].premium_percent)
    previous = float(snaps[1].premium_percent)
    return latest - previous


def _gather_regime_evidence(
    market_snapshot,
    market_state,
    config: Optional[Dict] = None,
) -> Dict:
    """Gather evidence for regime classification from canonical sources.

    Args:
        market_snapshot: latest MarketSnapshot or None
        market_state: latest MarketState or None
        config: optional configuration dict

    Returns:
        evidence dict for RegimeClassifier.classify()
    """
    evidence = {}

    if market_snapshot and market_snapshot.premium_percent is not None:
        evidence["premium_percent"] = float(market_snapshot.premium_percent)

    evidence["premium_change"] = _compute_premium_change()

    # Volatility from recent REP_IRAN_GOLD observations
    price_obs = get_price_observations_by_instrument("REP_IRAN_GOLD", limit=20)
    if len(price_obs) >= 2:
        prices = [float(o.price) for o in reversed(price_obs)]
        evidence["volatility"] = _compute_price_volatility(prices)

    evidence["usd_change"] = _compute_usd_change()

    if market_state and market_state.platform_spread is not None:
        evidence["platform_spread"] = float(market_state.platform_spread)

    # External event stress
    news = get_recent_news_events(hours=6)
    high_impact = [n for n in news if n.relevance in ("HIGH", "CRITICAL")]
    evidence["high_impact_news_count"] = len(high_impact)

    return evidence


def _build_technical_state_json(
    rep_price,
    structure_state,
) -> Optional[Dict]:
    """Serialize technical analysis result into machine-readable JSON.

    Args:
        rep_price: RepresentativePrice result
        structure_state: StructureState result

    Returns:
        dict suitable for technical_state_json column.
    """
    if rep_price is None and structure_state is None:
        return None

    tech_json = {
        "representative_price": None,
        "support_levels": [],
        "resistance_levels": [],
        "structure_status": "UNKNOWN",
    }

    if rep_price is not None:
        tech_json["representative_price"] = {
            "price": rep_price.price,
            "source": rep_price.source,
            "status": rep_price.status,
        }

    if structure_state is not None:
        tech_json["structure_status"] = structure_state.status
        tech_json["support_levels"] = [
            {
                "price": l.price,
                "touches": l.touches,
                "strength": l.strength,
                "source": l.source,
                "lookback": l.lookback,
            }
            for l in structure_state.support_levels
        ]
        tech_json["resistance_levels"] = [
            {
                "price": l.price,
                "touches": l.touches,
                "strength": l.strength,
                "source": l.source,
                "lookback": l.lookback,
            }
            for l in structure_state.resistance_levels
        ]

    return tech_json


def build_analysis_snapshot(
    analysis_timestamp: Optional[datetime] = None,
    config: Optional[Dict] = None,
) -> int:
    """Build and save an analysis snapshot from the latest market data.

    Integrates PRE-SP-C.3 analytical primitives:
    - representative price
    - technical structure (support/resistance)
    - regime classification with cross-run hysteresis reconstruction

    Non-blocking: returns -1 on failure or if snapshot already exists.

    Args:
        analysis_timestamp: timestamp for the analysis (default: now)
        config: optional configuration dict

    Returns:
        snapshot id, or -1 on failure/duplicate
    """
    if analysis_timestamp is None:
        analysis_timestamp = datetime.now()

    source_run_id = generate_source_run_id(analysis_timestamp)

    # Idempotency: do not create duplicate snapshots
    if analysis_snapshot_exists(source_run_id):
        print(f"Analysis snapshot {source_run_id} already exists — skipping")
        return -1

    # Fetch latest market data
    market_snapshot = get_latest_market_snapshot()
    market_state = get_latest_market_state()

    # --- PRE-SP-C.4: Reconstruct regime hysteresis from last snapshot ---
    last_snap = get_latest_analysis_snapshot()
    regime_cfg = (config or {}).get("regime", {})
    classifier = RegimeClassifier(regime_cfg)

    if last_snap is not None:
        classifier.restore_state(
            previous_state=last_snap.regime_state,
            candidate_state=last_snap.regime_candidate_state,
            confirmation_count=last_snap.regime_confirmation_count or 0,
        )

    # --- PRE-SP-C.4: Build representative price ---
    rep_price = get_representative_price()

    # --- PRE-SP-C.4: Build technical structure ---
    sr_cfg = (config or {}).get("support_resistance", {})
    structure_state = build_structure_state(
        instrument="REP_IRAN_GOLD",
        lookback=sr_cfg.get("lookback_periods", 20),
        cluster_tolerance_percent=sr_cfg.get("cluster_tolerance_percent", 0.3),
        min_history=sr_cfg.get("min_history", 10),
        neighborhood_size=sr_cfg.get("neighborhood_size", 1),
    )

    # --- PRE-SP-C.4: Classify regime ---
    evidence = _gather_regime_evidence(market_snapshot, market_state, config)
    regime_result = classifier.classify(evidence)

    # --- Build data quality tracking ---
    data_quality = {
        "market_snapshot": "AVAILABLE" if market_snapshot else "UNAVAILABLE",
        "market_state": "AVAILABLE" if market_state else "UNAVAILABLE",
        "xau_usd": "AVAILABLE" if market_snapshot and market_snapshot.world_gold_usd else "UNAVAILABLE",
        "usd_irr": "AVAILABLE" if market_snapshot and market_snapshot.usd_irr else "UNAVAILABLE",
        "representative_price": "AVAILABLE" if rep_price and rep_price.status == "AVAILABLE" else "UNAVAILABLE",
        "technical_structure": structure_state.status,
        "regime": regime_result.state,
    }

    # Extract values with safe defaults
    xau_usd = None
    usd_irr = None
    premium_percent = None
    market_snapshot_id = None
    if market_snapshot:
        xau_usd = float(market_snapshot.world_gold_usd) if market_snapshot.world_gold_usd else None
        usd_irr = float(market_snapshot.usd_irr) if market_snapshot.usd_irr else None
        premium_percent = float(market_snapshot.premium_percent) if market_snapshot.premium_percent else None
        market_snapshot_id = market_snapshot.id

    valuation_state = "UNKNOWN"
    momentum_state = "UNKNOWN"
    structure_state_val = "UNKNOWN"
    market_state_id = None
    if market_state:
        valuation_state = market_state.valuation_state or "UNKNOWN"
        momentum_state = market_state.momentum_state or "UNKNOWN"
        structure_state_val = market_state.structure_state or "UNKNOWN"
        market_state_id = market_state.id

    rep_gold_price = rep_price.price if rep_price else None

    # Serialize technical and regime evidence
    technical_state_json = _build_technical_state_json(rep_price, structure_state)

    # --- PRE-SP-C.6: Build deterministic evidence package ---
    evidence_package = None
    try:
        evidence_package = build_evidence_package(
            analysis_timestamp=analysis_timestamp,
            source_run_id=source_run_id,
            market_snapshot=market_snapshot,
            market_state=market_state,
            rep_price=rep_price,
            structure_state=structure_state,
            regime_result=regime_result,
            classifier=classifier,
            data_quality=data_quality,
            technical_state_json=technical_state_json,
            config=config,
        )
        valid, ev_errors = validate_evidence_package(evidence_package)
        if not valid:
            print(f"Evidence package validation warnings: {ev_errors}")
    except Exception as e:
        print(f"Evidence package build failed: {e}")

    # --- PRE-SP-C.7: Build bounded market intelligence ---
    intelligence_result = None
    try:
        if evidence_package:
            intelligence_result = build_intelligence_result(
                evidence_package=evidence_package,
                model_provider="deterministic_fallback",
                prompt_version="1",
            )
            intel_valid, intel_errors = validate_intelligence_result(intelligence_result)
            if not intel_valid:
                print(f"Intelligence validation warnings: {intel_errors}")
    except Exception as e:
        print(f"Intelligence build failed: {e}")

        # --- PRE-SP-C.8: Build analytical feature snapshot ---
    features = None
    try:
        features = build_feature_snapshot(
            analysis_timestamp=analysis_timestamp,
            current_regime=regime_result.state,
            previous_regime=regime_result.previous_state,
            market_state=market_state,
            config=config,
        )
        feat_valid, feat_errors = validate_feature_snapshot(features)
        if not feat_valid:
            print(f"Feature validation warnings: {feat_errors}")
    except Exception as e:
        print(f"Feature build failed: {e}")

    # --- PRE-SP-C.9: Build analytical read model ---
    read_model = None
    try:
        snapshot_facts = {
            "xau_usd": xau_usd,
            "usd_irr": usd_irr,
            "rep_gold_price": rep_gold_price,
            "premium_percent": premium_percent,
            "valuation_state": valuation_state,
            "momentum_state": momentum_state,
            "structure_state": structure_state_val,
            "regime_state": regime_result.state,
            "candidate_decision": market_state.candidate_decision if market_state else "UNKNOWN",
            "final_decision": market_state.final_decision if market_state else "UNKNOWN",
        }
        read_model = build_read_model(
            analysis_timestamp=analysis_timestamp,
            source_run_id=source_run_id,
            market_snapshot_id=market_snapshot_id,
            market_state_id=market_state_id,
            evidence_package=evidence_package,
            intelligence_result=intelligence_result,
            features=features,
            snapshot_facts=snapshot_facts,
        )
        rm_valid, rm_errors = validate_read_model(read_model)
        if not rm_valid:
            print(f"Read model validation warnings: {rm_errors}")
    except Exception as e:
        print(f"Read model build failed: {e}")

    snapshot_id = save_analysis_snapshot(
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
        structure_state=structure_state_val,
        data_quality_json=data_quality,
        regime_state=regime_result.state,
        technical_state_json=technical_state_json,
        previous_regime=regime_result.previous_state,
        regime_candidate_state=classifier._candidate_state,
        regime_confirmation_count=classifier._confirmation_count,
        evidence_package_json=evidence_package,
        intelligence_result_json=intelligence_result,
        features_json=features,
        analysis_read_model_json=read_model,
    )

    # PRE-SP-C.5: non-blocking outcome evaluation
    if snapshot_id is not None and snapshot_id > 0:
        try:
            from analysis.outcome_evaluator import run_outcome_evaluation_for_snapshot
            run_outcome_evaluation_for_snapshot(snapshot_id, config=config)
        except Exception as e:
            print(f"Outcome evaluation failed for snapshot {snapshot_id}: {e}")

    return snapshot_id
