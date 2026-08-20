"""Feature Intelligence Layer — PRE-SP-C.8

Deterministic analytical feature engineering.
Consumes canonical observations and produces structured features.
No prediction. No BUY/SELL. No interpretation text. No external AI.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

from database.repository import (
    get_price_observations_by_instrument,
    get_analysis_snapshots,
    get_market_states_by_criteria,
    get_snapshots,
)
from analysis.regime import REGIME_STATES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_prices(obs_list) -> List[float]:
    """Extract float prices from observation objects (newest first → reversed)."""
    return [_safe_float(o.price) for o in reversed(obs_list) if _safe_float(o.price) is not None]


def _to_premiums(snap_list) -> List[float]:
    """Extract float premiums from market snapshots (newest first → reversed)."""
    return [_safe_float(s.premium_percent) for s in reversed(snap_list) if _safe_float(s.premium_percent) is not None]


def _sma(values: List[float], window: int) -> Optional[float]:
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def _ema(values: List[float], window: int) -> Optional[float]:
    if len(values) < window:
        return None
    alpha = 2.0 / (window + 1)
    ema = values[0]
    for price in values[1:]:
        ema = alpha * price + (1 - alpha) * ema
    return ema


def _price_vs_ma_percent(price: Optional[float], ma: Optional[float]) -> Optional[float]:
    if price is None or ma is None or ma == 0:
        return None
    return round(((price - ma) / ma) * 100, 4)


def _rolling_std(values: List[float], window: int) -> Optional[float]:
    if len(values) < window:
        return None
    window_vals = values[-window:]
    mean = sum(window_vals) / len(window_vals)
    variance = sum((v - mean) ** 2 for v in window_vals) / len(window_vals)
    return variance ** 0.5


def _rolling_volatility(values: List[float], window: int) -> Optional[float]:
    """Coefficient of variation (%)."""
    std = _rolling_std(values, window)
    mean = _sma(values, window)
    if std is None or mean is None or mean == 0:
        return None
    return round((std / mean) * 100, 4)


def _direction_from_change(current: Optional[float], previous: Optional[float]) -> str:
    if current is None or previous is None or previous == 0:
        return "UNKNOWN"
    diff = current - previous
    if abs(diff) < 0.0001:
        return "FLAT"
    return "UP" if diff > 0 else "DOWN"


def _direction_persistence(directions: List[str]) -> int:
    """Count how many recent periods the direction has persisted."""
    if not directions:
        return 0
    last = directions[-1]
    count = 0
    for d in reversed(directions):
        if d == last and d != "UNKNOWN":
            count += 1
        else:
            break
    return count


# ---------------------------------------------------------------------------
# Feature Families
# ---------------------------------------------------------------------------

def _build_price_trend_features(
    rep_prices: List[float],
    xau_prices: List[float],
    usd_prices: List[float],
) -> Dict[str, Any]:
    """MA, EMA, and distance-from-average features."""
    features = {}

    for name, prices in [
        ("rep_gold", rep_prices),
        ("xau_usd", xau_prices),
        ("usd_irr", usd_prices),
    ]:
        prefix = name
        latest = prices[-1] if prices else None

        for window in [7, 15, 30]:
            ma = _sma(prices, window)
            ema = _ema(prices, window)
            features[f"{prefix}_ma{window}"] = round(ma, 4) if ma is not None else None
            features[f"{prefix}_ema{window}"] = round(ema, 4) if ema is not None else None
            features[f"{prefix}_vs_ma{window}_percent"] = _price_vs_ma_percent(latest, ma)

    return features


def _build_momentum_features(
    premiums: List[float],
    rep_prices: List[float],
) -> Dict[str, Any]:
    """Premium velocity, acceleration, direction persistence, change rate."""
    features = {}

    if len(premiums) >= 2:
        velocity = premiums[-1] - premiums[-2]
        features["premium_velocity"] = round(velocity, 4)
    else:
        features["premium_velocity"] = None

    if len(premiums) >= 3:
        v1 = premiums[-2] - premiums[-3]
        v2 = premiums[-1] - premiums[-2]
        features["premium_acceleration"] = round(v2 - v1, 4)
    else:
        features["premium_acceleration"] = None

    # Direction persistence from premium changes
    directions = []
    for i in range(1, len(premiums)):
        diff = premiums[i] - premiums[i - 1]
        if abs(diff) < 0.01:
            directions.append("FLAT")
        elif diff > 0:
            directions.append("UP")
        else:
            directions.append("DOWN")

    features["premium_direction_persistence"] = _direction_persistence(directions)
    features["premium_latest_direction"] = directions[-1] if directions else "UNKNOWN"

    # Momentum change rate: % change in premium over last N observations
    if len(premiums) >= 2 and premiums[-2] != 0:
        change_rate = ((premiums[-1] - premiums[-2]) / abs(premiums[-2])) * 100
        features["momentum_change_rate_percent"] = round(change_rate, 4)
    else:
        features["momentum_change_rate_percent"] = None

    return features


def _build_volatility_features(
    rep_prices: List[float],
    xau_prices: List[float],
    usd_prices: List[float],
) -> Dict[str, Any]:
    """Rolling volatility, range expansion/contraction, instability."""
    features = {}

    for name, prices in [
        ("rep_gold", rep_prices),
        ("xau_usd", xau_prices),
        ("usd_irr", usd_prices),
    ]:
        prefix = name
        vol7 = _rolling_volatility(prices, 7) if len(prices) >= 7 else None
        vol15 = _rolling_volatility(prices, 15) if len(prices) >= 15 else None
        features[f"{prefix}_volatility_7"] = round(vol7, 4) if vol7 is not None else None
        features[f"{prefix}_volatility_15"] = round(vol15, 4) if vol15 is not None else None

        # Range expansion/contraction: compare recent range to prior range
        if len(prices) >= 14:
            recent_range = max(prices[-7:]) - min(prices[-7:])
            prior_range = max(prices[-14:-7]) - min(prices[-14:-7])
            if prior_range != 0:
                features[f"{prefix}_range_expansion_percent"] = round(((recent_range - prior_range) / prior_range) * 100, 4)
            else:
                features[f"{prefix}_range_expansion_percent"] = None
        else:
            features[f"{prefix}_range_expansion_percent"] = None

    # Price instability: max single-period change %
    if len(rep_prices) >= 2:
        changes = [abs(rep_prices[i] - rep_prices[i - 1]) / rep_prices[i - 1] * 100
                   for i in range(1, len(rep_prices)) if rep_prices[i - 1] != 0]
        features["rep_gold_max_period_change_percent"] = round(max(changes), 4) if changes else None
    else:
        features["rep_gold_max_period_change_percent"] = None

    return features


def _build_regime_features(
    current_regime: str,
    previous_regime: Optional[str],
    analysis_timestamp: datetime,
    hours_lookback: int = 168,
) -> Dict[str, Any]:
    """Regime duration, transition frequency from recent snapshots."""
    features = {
        "current_regime": current_regime,
        "previous_regime": previous_regime,
        "regime_duration_observations": None,
        "regime_transition_frequency": None,
    }

    try:
        recent = get_analysis_snapshots(limit=500, hours=hours_lookback)
        if not recent:
            return features

        # Count how long current regime has persisted
        duration = 0
        for snap in recent:
            if getattr(snap, "regime_state", None) == current_regime:
                duration += 1
            else:
                break
        features["regime_duration_observations"] = duration

        # Transition frequency: count of regime changes in lookback
        transitions = 0
        prev = None
        for snap in reversed(recent):  # oldest first
            rs = getattr(snap, "regime_state", None)
            if rs is not None and prev is not None and rs != prev:
                transitions += 1
            prev = rs
        features["regime_transition_frequency"] = transitions

    except Exception:
        pass

    return features


def _build_market_relation_features(
    xau_prices: List[float],
    usd_prices: List[float],
    rep_prices: List[float],
    premiums: List[float],
) -> Dict[str, Any]:
    """XAU/USD direction, USD/IRR pressure, divergence indicators."""
    features = {}

    # XAU/USD direction
    features["xau_usd_direction"] = _direction_from_change(
        xau_prices[-1] if xau_prices else None,
        xau_prices[-2] if len(xau_prices) >= 2 else None,
    )

    # USD/IRR direction (pressure)
    features["usd_irr_direction"] = _direction_from_change(
        usd_prices[-1] if usd_prices else None,
        usd_prices[-2] if len(usd_prices) >= 2 else None,
    )

    # Local gold direction
    features["rep_gold_direction"] = _direction_from_change(
        rep_prices[-1] if rep_prices else None,
        rep_prices[-2] if len(rep_prices) >= 2 else None,
    )

    # Gold/local premium relationship: correlation proxy
    if len(premiums) >= 2 and len(rep_prices) >= 2:
        prem_change = premiums[-1] - premiums[-2]
        rep_change_pct = ((rep_prices[-1] - rep_prices[-2]) / rep_prices[-2] * 100) if rep_prices[-2] != 0 else 0
        features["premium_vs_local_gold_alignment"] = "ALIGNED" if (prem_change > 0 and rep_change_pct > 0) or (prem_change < 0 and rep_change_pct < 0) else "DIVERGENT"
    else:
        features["premium_vs_local_gold_alignment"] = "UNKNOWN"

    # Divergence: XAU/USD up + local gold down = divergence
    xau_dir = features["xau_usd_direction"]
    rep_dir = features["rep_gold_direction"]
    if xau_dir != "UNKNOWN" and rep_dir != "UNKNOWN":
        features["xau_local_divergence"] = xau_dir != rep_dir
    else:
        features["xau_local_divergence"] = None

    # USD/IRR pressure on local gold
    usd_dir = features["usd_irr_direction"]
    rep_dir = features["rep_gold_direction"]
    if usd_dir != "UNKNOWN" and rep_dir != "UNKNOWN":
        features["usd_irr_local_gold_pressure"] = "SAME" if usd_dir == rep_dir else "OPPOSITE"
    else:
        features["usd_irr_local_gold_pressure"] = "UNKNOWN"

    return features


def _build_structure_features(
    market_state,
) -> Dict[str, Any]:
    """Platform spread, consensus ratio, discount/premium dominance."""
    features = {}

    if market_state is None:
        features["platform_spread"] = None
        features["consensus_ratio"] = None
        features["discount_dominance"] = None
        features["premium_concentration"] = None
        return features

    spread = _safe_float(getattr(market_state, "platform_spread", None))
    features["platform_spread"] = round(spread, 2) if spread is not None else None

    below = getattr(market_state, "platforms_below_fair", None)
    above = getattr(market_state, "platforms_above_fair", None)
    total = (below or 0) + (above or 0)

    if total > 0:
        features["consensus_ratio"] = round(below / total, 4)
        features["discount_dominance"] = below > above
        features["premium_concentration"] = round(above / total, 4)
    else:
        features["consensus_ratio"] = None
        features["discount_dominance"] = None
        features["premium_concentration"] = None

    return features


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

FEATURE_SCHEMA_VERSION = "1"


def build_feature_snapshot(
    analysis_timestamp: datetime,
    current_regime: str,
    previous_regime: Optional[str],
    market_state,
    config: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Build a deterministic feature snapshot from canonical observations.

    Args:
        analysis_timestamp: snapshot timestamp (upper bound for observations)
        current_regime: current regime state
        previous_regime: previous regime state
        market_state: latest MarketState or None
        config: optional configuration dict

    Returns:
        structured feature dict
    """
    if config is None:
        config = {}

    feat_cfg = config.get("features", {})
    price_lookback = feat_cfg.get("price_observation_lookback", 100)
    premium_lookback_days = feat_cfg.get("premium_lookback_days", 30)

    # Fetch observations strictly before or at analysis_timestamp
    # Note: get_price_observations_by_instrument returns newest first
    rep_obs = get_price_observations_by_instrument("REP_IRAN_GOLD", limit=price_lookback)
    xau_obs = get_price_observations_by_instrument("XAUUSD", limit=price_lookback)
    usd_obs = get_price_observations_by_instrument("USD/IRR", limit=price_lookback)

    # Filter to observations at or before analysis_timestamp (no look-ahead)
    cutoff = analysis_timestamp
    rep_obs = [o for o in rep_obs if o.timestamp <= cutoff]
    xau_obs = [o for o in xau_obs if o.timestamp <= cutoff]
    usd_obs = [o for o in usd_obs if o.timestamp <= cutoff]

    rep_prices = _to_prices(rep_obs)
    xau_prices = _to_prices(xau_obs)
    usd_prices = _to_prices(usd_obs)

    # Premiums from market snapshots
    snaps = get_snapshots(days=premium_lookback_days)
    premiums = _to_premiums(snaps)

    features = {
        "schema_version": FEATURE_SCHEMA_VERSION,
        "generated_at": analysis_timestamp.isoformat(),
        "price_trend": _build_price_trend_features(rep_prices, xau_prices, usd_prices),
        "momentum": _build_momentum_features(premiums, rep_prices),
        "volatility": _build_volatility_features(rep_prices, xau_prices, usd_prices),
        "regime": _build_regime_features(current_regime, previous_regime, analysis_timestamp),
        "market_relation": _build_market_relation_features(xau_prices, usd_prices, rep_prices, premiums),
        "structure": _build_structure_features(market_state),
        "data_quality": {
            "rep_gold_observations": len(rep_prices),
            "xau_usd_observations": len(xau_prices),
            "usd_irr_observations": len(usd_prices),
            "premium_observations": len(premiums),
            "sufficient_history": len(rep_prices) >= 30 and len(premiums) >= 7,
        },
    }

    return features


def validate_feature_snapshot(features: Dict) -> Tuple[bool, List[str]]:
    """Validate feature snapshot structure."""
    errors = []

    if not isinstance(features, dict):
        errors.append("Features must be a dict")
        return False, errors

    if features.get("schema_version") != FEATURE_SCHEMA_VERSION:
        errors.append(f"Schema version must be '{FEATURE_SCHEMA_VERSION}'")

    required_sections = [
        "schema_version", "generated_at", "price_trend", "momentum",
        "volatility", "regime", "market_relation", "structure", "data_quality",
    ]
    for section in required_sections:
        if section not in features:
            errors.append(f"Missing section: {section}")

    # No BUY/SELL
    features_str = str(features).upper()
    for forbidden in ["BUY", "SELL", "RECOMMEND"]:
        if forbidden in features_str:
            errors.append(f"Features must not contain decision language: {forbidden}")

    return len(errors) == 0, errors
