"""Forecast Feature Extension — PRE-SP-C.14B

Modular feature vector builder.
Consumes C.8 persisted features + C.14A platform candles.
Produces flat numeric feature vectors for scikit-learn.

Point-in-time safe: only uses data at or before analysis_timestamp.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import math

FEATURE_SCHEMA_VERSION = "1"

# Categorical mappings — deterministic, no leakage
_DIRECTION_MAP = {"UP": 1.0, "DOWN": -1.0, "FLAT": 0.0, "NEUTRAL": 0.0, "UNKNOWN": 0.0}
_REGIME_MAP = {"NORMAL": 0.0, "FEAR": 1.0, "PANIC": 2.0, "RELIEF": 3.0, "UNKNOWN": -1.0}
_ALIGNMENT_MAP = {"ALIGNED": 1.0, "DIVERGENT": -1.0, "SAME": 1.0, "OPPOSITE": -1.0, "UNKNOWN": 0.0}


def _safe_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _encode_value(key: str, value: Any) -> Optional[float]:
    """Encode a feature value to a float for model consumption."""
    if value is None:
        return float("nan")

    if isinstance(value, bool):
        return 1.0 if value else 0.0

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        # Direction-like fields
        if key.endswith("_direction") or key.endswith("_state"):
            return _DIRECTION_MAP.get(value, _REGIME_MAP.get(value, float("nan")))
        if key.endswith("_alignment") or key.endswith("_pressure"):
            return _ALIGNMENT_MAP.get(value, float("nan"))
        if key == "current_regime" or key == "previous_regime":
            return _REGIME_MAP.get(value, float("nan"))
        return float("nan")

    return float("nan")


def flatten_c8_features(features_json: Optional[dict]) -> dict:
    """Flatten nested C.8 feature snapshot into a flat dict.

    Preserves original values; encoding happens at vectorization time.
    """
    flat = {}
    if not isinstance(features_json, dict):
        return flat

    for section, values in features_json.items():
        if section in ("schema_version", "generated_at", "data_quality"):
            continue
        if not isinstance(values, dict):
            continue
        for k, v in values.items():
            flat[f"c8_{section}_{k}"] = v
    return flat


def derive_candle_features(candles: List[Any]) -> dict:
    """Derive price-action features from C.14A candles. Pure function.

    Args:
        candles: list of candle objects/dicts, sorted ascending by bucket_start.
                 Must have open, high, low, close attributes/keys.

    Returns:
        dict of derived candle features.
    """
    if len(candles) < 2:
        return {
            "candle_return": None,
            "candle_body": None,
            "candle_body_percent": None,
            "candle_upper_wick": None,
            "candle_lower_wick": None,
            "candle_range": None,
            "candle_range_percent": None,
            "candle_close_position": None,
            "candle_consecutive_bullish": 0,
            "candle_consecutive_bearish": 0,
            "candle_range_expansion_percent": None,
            "candle_return_volatility_10": None,
        }

    def _get(c, attr):
        return getattr(c, attr, None) if hasattr(c, attr) else c.get(attr)

    latest = candles[-1]
    o = _safe_float(_get(latest, "open"))
    h = _safe_float(_get(latest, "high"))
    l = _safe_float(_get(latest, "low"))
    c = _safe_float(_get(latest, "close"))

    if None in (o, h, l, c):
        return {
            "candle_return": None,
            "candle_body": None,
            "candle_body_percent": None,
            "candle_upper_wick": None,
            "candle_lower_wick": None,
            "candle_range": None,
            "candle_range_percent": None,
            "candle_close_position": None,
            "candle_consecutive_bullish": 0,
            "candle_consecutive_bearish": 0,
            "candle_range_expansion_percent": None,
            "candle_return_volatility_10": None,
        }

    body = c - o
    range_val = h - l
    body_pct = (body / o) * 100 if o != 0 else None
    range_pct = (range_val / o) * 100 if o != 0 else None
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    close_position = (c - l) / range_val if range_val and range_val > 0 else None

    # Consecutive direction counts
    directions = []
    for can in candles:
        co = _safe_float(_get(can, "open"))
        cc = _safe_float(_get(can, "close"))
        if co is None or cc is None:
            directions.append(0)
        elif cc > co:
            directions.append(1)
        elif cc < co:
            directions.append(-1)
        else:
            directions.append(0)

    consec_bull = 0
    for d in reversed(directions):
        if d == 1:
            consec_bull += 1
        else:
            break

    consec_bear = 0
    for d in reversed(directions):
        if d == -1:
            consec_bear += 1
        else:
            break

    # Range expansion: current vs average of prior 5
    ranges = []
    for can in candles:
        ch = _safe_float(_get(can, "high"))
        cl = _safe_float(_get(can, "low"))
        if ch is not None and cl is not None:
            ranges.append(ch - cl)
        else:
            ranges.append(0.0)

    range_expansion = None
    if len(ranges) >= 6:
        current_range = ranges[-1]
        avg_prior = sum(ranges[-6:-1]) / 5
        if avg_prior > 0:
            range_expansion = ((current_range - avg_prior) / avg_prior) * 100

    # Return volatility over last 10 candles
    returns = []
    for i in range(1, len(candles)):
        prev_close = _safe_float(_get(candles[i - 1], "close"))
        curr_close = _safe_float(_get(candles[i], "close"))
        if prev_close is not None and prev_close != 0 and curr_close is not None:
            returns.append((curr_close - prev_close) / prev_close)

    vol = None
    if len(returns) >= 10:
        recent = returns[-10:]
        mean_ret = sum(recent) / len(recent)
        variance = sum((r - mean_ret) ** 2 for r in recent) / len(recent)
        vol = (variance ** 0.5) * 100

    return {
        "candle_return": round(body / o * 100, 4) if o != 0 else None,
        "candle_body": round(body, 4),
        "candle_body_percent": round(body_pct, 4) if body_pct is not None else None,
        "candle_upper_wick": round(upper_wick, 4),
        "candle_lower_wick": round(lower_wick, 4),
        "candle_range": round(range_val, 4),
        "candle_range_percent": round(range_pct, 4) if range_pct is not None else None,
        "candle_close_position": round(close_position, 4) if close_position is not None else None,
        "candle_consecutive_bullish": consec_bull,
        "candle_consecutive_bearish": consec_bear,
        "candle_range_expansion_percent": round(range_expansion, 4) if range_expansion is not None else None,
        "candle_return_volatility_10": round(vol, 4) if vol is not None else None,
    }


def _ema_series(values: List[float], window: int) -> List[float]:
    """Compute EMA series. Pure function."""
    if len(values) < window:
        return []
    alpha = 2.0 / (window + 1)
    ema = [values[0]]
    for v in values[1:]:
        ema.append(alpha * v + (1 - alpha) * ema[-1])
    return ema


def derive_macd_features(
    closes: List[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict:
    """Compute MACD-style features from close price series.

    Uses 12/26/9 windows — distinct from C.8 EMA7/15/30 to avoid redundancy.
    Pure function. Point-in-time safe.
    """
    if len(closes) < slow:
        return {
            "macd_line": None,
            "macd_signal": None,
            "macd_histogram": None,
            "macd_above_signal": None,
            "macd_histogram_direction": None,
        }

    ema_fast = _ema_series(closes, fast)
    ema_slow = _ema_series(closes, slow)

    # Align series: both must have same length
    min_len = min(len(ema_fast), len(ema_slow))
    ema_fast = ema_fast[-min_len:]
    ema_slow = ema_slow[-min_len:]

    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    macd_signal_series = _ema_series(macd_line, signal)

    if len(macd_signal_series) < 2:
        return {
            "macd_line": round(macd_line[-1], 6) if macd_line else None,
            "macd_signal": None,
            "macd_histogram": None,
            "macd_above_signal": None,
            "macd_histogram_direction": None,
        }

    latest_macd = macd_line[-1]
    latest_signal = macd_signal_series[-1]
    latest_hist = latest_macd - latest_signal

    prev_hist = (macd_line[-2] - macd_signal_series[-2]) if len(macd_line) >= 2 and len(macd_signal_series) >= 2 else None

    hist_direction = None
    if prev_hist is not None:
        if latest_hist > prev_hist:
            hist_direction = "UP"
        elif latest_hist < prev_hist:
            hist_direction = "DOWN"
        else:
            hist_direction = "FLAT"

    return {
        "macd_line": round(latest_macd, 6),
        "macd_signal": round(latest_signal, 6),
        "macd_histogram": round(latest_hist, 6),
        "macd_above_signal": 1.0 if latest_macd > latest_signal else 0.0,
        "macd_histogram_direction": hist_direction,
    }


def build_forecast_feature_vector(
    snapshot,
    config: Optional[dict] = None,
) -> Optional[dict]:
    """Build a flat feature vector for forecast model consumption.

    Supports three configurations via config flags:
        include_c8: bool = True      (C.8 baseline features)
        include_candles: bool = False (C.14A price-action features)
        include_macd: bool = False    (MACD-style momentum features)

    Point-in-time safe: only uses candles with bucket_end <= snapshot timestamp.

    Args:
        snapshot: AnalysisSnapshot ORM object or compatible dict.
        config: feature configuration dict.

    Returns:
        dict with feature_names, feature_values, feature_groups, feature_dict,
        or None if insufficient data.
    """
    if config is None:
        config = {}

    include_c8 = config.get("include_c8", True)
    include_candles = config.get("include_candles", False)
    include_macd = config.get("include_macd", False)

    # Extract analysis_timestamp safely
    analysis_ts = getattr(snapshot, "analysis_timestamp", None)
    if analysis_ts is None:
        return None

    vector = {}
    feature_groups = []

    # --- C.8 baseline features ---
    if include_c8:
        features_json = getattr(snapshot, "features_json", None) or {}
        c8_flat = flatten_c8_features(features_json)
        vector.update(c8_flat)
        feature_groups.extend(["c8"] * len(c8_flat))

    # --- C.14A candle features ---
    candle_list = []
    if include_candles or include_macd:
        from database.repository import get_platform_candles

        candle_platform = config.get("candle_platform", "milli")
        candle_instrument = config.get("candle_instrument", "REP_IRAN_GOLD")
        candle_timeframe = config.get("candle_timeframe", "30m")
        candle_quote_side = config.get("candle_quote_side", "SINGLE")
        candle_lookback = config.get("candle_lookback", 50)

        candles = get_platform_candles(
            platform=candle_platform,
            instrument=candle_instrument,
            timeframe=candle_timeframe,
            quote_side=candle_quote_side,
            limit=candle_lookback,
        )

        # Point-in-time filter: only candles fully known at analysis time
        if candles:
            candles = [c for c in candles if getattr(c, "bucket_end", None) and getattr(c, "bucket_end") <= analysis_ts]
            candles = sorted(candles, key=lambda c: getattr(c, "bucket_start", datetime.min))

        candle_list = candles

        if include_candles and candles:
            candle_feats = derive_candle_features(candles)
            vector.update(candle_feats)
            feature_groups.extend(["candle"] * len(candle_feats))

    # --- MACD-style features ---
    if include_macd and candle_list:
        closes = []
        for c in candle_list:
            close_val = _safe_float(getattr(c, "close", None))
            if close_val is not None:
                closes.append(close_val)

        if len(closes) >= config.get("macd_slow", 26):
            macd_feats = derive_macd_features(
                closes,
                fast=config.get("macd_fast", 12),
                slow=config.get("macd_slow", 26),
                signal=config.get("macd_signal", 9),
            )
            vector.update(macd_feats)
            feature_groups.extend(["macd"] * len(macd_feats))

    # --- Vectorize: convert to numeric arrays ---
    names = []
    values = []
    groups = []

    for k, v in vector.items():
        encoded = _encode_value(k, v)
        if math.isnan(encoded):
            # Keep the feature name but mark as nan — imputation happens at model time
            pass
        names.append(k)
        values.append(encoded)
        # Determine group from position or key prefix
        if k.startswith("c8_"):
            groups.append("c8")
        elif k.startswith("candle_"):
            groups.append("candle")
        elif k.startswith("macd_"):
            groups.append("macd")
        else:
            groups.append("unknown")

    if not names:
        return None

    return {
        "schema_version": FEATURE_SCHEMA_VERSION,
        "snapshot_id": getattr(snapshot, "id", None),
        "analysis_timestamp": analysis_ts.isoformat() if analysis_ts else None,
        "feature_dict": vector,
        "feature_names": names,
        "feature_values": values,
        "feature_groups": groups,
        "config": {
            "include_c8": include_c8,
            "include_candles": include_candles,
            "include_macd": include_macd,
        },
    }
