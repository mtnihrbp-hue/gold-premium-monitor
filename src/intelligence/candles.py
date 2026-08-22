"""Platform Candle Builder — PRE-SP-C.14A

Deterministic candle aggregation from canonical price observations.
No interpolation. No forward-fill. Point-in-time safe.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

from database.repository import (
    get_price_observations_by_instrument,
    save_platform_candle,
)

DEFAULT_TIMEFRAME = "30m"
TIMEFRAME_MINUTES = {"5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}


def _timeframe_delta(timeframe: str) -> timedelta:
    return timedelta(minutes=TIMEFRAME_MINUTES.get(timeframe, 30))


def _bucket_start(dt: datetime, timeframe: str) -> datetime:
    """Floor datetime to bucket boundary. Handles day boundaries correctly."""
    minutes = TIMEFRAME_MINUTES.get(timeframe, 30)
    # Continuous minutes from datetime.min to handle midnight crossing safely
    delta_from_min = dt - datetime.min
    total_minutes = int(delta_from_min.total_seconds() // 60)
    bucket_minutes = (total_minutes // minutes) * minutes
    return datetime.min + timedelta(minutes=bucket_minutes)


def _extract_price(obs) -> Optional[float]:
    """Safely extract float price from observation."""
    if obs.price is None:
        return None
    try:
        return float(obs.price)
    except (TypeError, ValueError):
        return None


def build_candles_from_observations(
    platform: str,
    instrument: str,
    timeframe: str = DEFAULT_TIMEFRAME,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    quote_side: str = "SINGLE",
    min_observations: int = 1,
    collection_run_id: str = None,
    candle_type: str = "DERIVED_FROM_POINT_OBSERVATIONS",
) -> List[Dict[str, Any]]:
    """Build deterministic candles from price observations.

    Args:
        platform: source platform name (matches price_observations.source)
        instrument: instrument code
        timeframe: candle timeframe
        start: optional start boundary (inclusive)
        end: optional end boundary (inclusive)
        quote_side: BUY, SELL, or SINGLE
        min_observations: minimum observations for a valid candle
        collection_run_id: provenance trace ID
        candle_type: provenance label for the candle

    Returns:
        list of candle dicts
    """
    delta = _timeframe_delta(timeframe)

    # Fetch observations for this instrument
    # When start is provided (backfill), fetch without hours filter to cover all history
    if start is not None:
        obs = get_price_observations_by_instrument(instrument, limit=50000)
    else:
        obs = get_price_observations_by_instrument(instrument, limit=5000, hours=720)
    if not obs:
        return []

    # Filter to matching source, quote_side, and time range
    filtered = []
    for o in obs:
        if o.source != platform:
            continue
        # Gracefully handle pre-C.14A observations without quote_side
        obs_quote_side = getattr(o, "quote_side", "SINGLE") or "SINGLE"
        if obs_quote_side != quote_side:
            continue
        if start and o.timestamp < start:
            continue
        if end and o.timestamp > end:
            continue
        price = _extract_price(o)
        if price is not None:
            filtered.append((o.timestamp, price))

    if not filtered:
        return []

    # Sort by timestamp ascending
    filtered.sort(key=lambda x: x[0])

    # Group into buckets
    buckets: Dict[datetime, List[Tuple[datetime, float]]] = {}
    for ts, price in filtered:
        bs = _bucket_start(ts, timeframe)
        buckets.setdefault(bs, []).append((ts, price))

    candles = []
    for bs in sorted(buckets.keys()):
        bucket_obs = buckets[bs]
        be = bs + delta

        prices = [p for _, p in bucket_obs]
        obs_count = len(prices)

        if obs_count < min_observations:
            continue

        # Deterministic O/H/L/C
        open_price = prices[0]
        high_price = max(prices)
        low_price = min(prices)
        close_price = prices[-1]

        # Mark incomplete if coverage is thin
        source_quality = "COMPLETE"
        if obs_count == 1:
            source_quality = "INCOMPLETE"
        elif (bucket_obs[-1][0] - bs).total_seconds() < (delta.total_seconds() * 0.5):
            source_quality = "INCOMPLETE"

        candles.append({
            "platform": platform,
            "instrument": instrument,
            "timeframe": timeframe,
            "bucket_start": bs,
            "bucket_end": be,
            "open": round(open_price, 4),
            "high": round(high_price, 4),
            "low": round(low_price, 4),
            "close": round(close_price, 4),
            "candle_type": candle_type,
            "quote_side": quote_side,
            "source_quality": source_quality,
            "observation_count": obs_count,
            "collection_run_id": collection_run_id,
        })

    return candles


def persist_candles(candles: List[Dict[str, Any]]) -> Tuple[int, int]:
    """Persist a list of candle dicts to the database.

    Idempotent: skips duplicates based on identity constraint.

    Returns:
        (saved_count, skipped_count)
    """
    saved = 0
    skipped = 0
    for c in candles:
        result = save_platform_candle(
            platform=c["platform"],
            instrument=c["instrument"],
            timeframe=c["timeframe"],
            bucket_start=c["bucket_start"],
            bucket_end=c["bucket_end"],
            open_price=c["open"],
            high_price=c["high"],
            low_price=c["low"],
            close_price=c["close"],
            candle_type=c["candle_type"],
            quote_side=c["quote_side"],
            source_quality=c["source_quality"],
            observation_count=c["observation_count"],
            collection_run_id=c.get("collection_run_id"),
        )
        if result > 0:
            saved += 1
        else:
            skipped += 1
    return saved, skipped


def backfill_platform_candles(
    platform: str,
    instrument: str = "REP_IRAN_GOLD",
    timeframe: str = DEFAULT_TIMEFRAME,
    quote_side: str = "SINGLE",
    min_observations: int = 1,
) -> Dict[str, Any]:
    """Backfill candles from all existing observations for a platform/quote_side.

    Returns:
        dict with backfill statistics
    """
    candles = build_candles_from_observations(
        platform=platform,
        instrument=instrument,
        timeframe=timeframe,
        start=datetime(2000, 1, 1),
        quote_side=quote_side,
        min_observations=min_observations,
        candle_type="BACKFILLED_FROM_POINT_OBSERVATIONS",
    )
    saved, skipped = persist_candles(candles)
    return {
        "platform": platform,
        "instrument": instrument,
        "timeframe": timeframe,
        "quote_side": quote_side,
        "candles_built": len(candles),
        "candles_saved": saved,
        "candles_skipped": skipped,
    }


def run_candle_build_for_snapshot(
    collection_run_id: str = None,
    timeframe: str = DEFAULT_TIMEFRAME,
) -> Dict[str, Any]:
    """Build and persist candles for all known platform configurations.

    Called from the Analysis Wing after snapshot creation.
    Idempotent: repeated runs skip existing candles.

    Returns:
        dict with build statistics per platform/quote_side
    """
    # Platforms with SINGLE_PRICE semantics
    single_platforms = [
        "milli", "wallgold", "taline", "hoorgold", "parasteh",
        "miogold", "eligallery", "daric", "invi", "ayyareh",
    ]

    # Goldika has explicit BUY/SELL
    goldika_sides = ["BUY", "SELL"]

    results = []
    total_saved = 0

    for platform in single_platforms:
        try:
            candles = build_candles_from_observations(
                platform=platform,
                instrument="REP_IRAN_GOLD",
                timeframe=timeframe,
                quote_side="SINGLE",
                min_observations=1,
                collection_run_id=collection_run_id,
            )
            saved, _ = persist_candles(candles)
            total_saved += saved
            results.append({
                "platform": platform,
                "quote_side": "SINGLE",
                "saved": saved,
                "status": "OK",
            })
        except Exception as e:
            results.append({
                "platform": platform,
                "quote_side": "SINGLE",
                "saved": 0,
                "status": f"ERROR: {e}",
            })

    for side in goldika_sides:
        try:
            candles = build_candles_from_observations(
                platform="goldika",
                instrument="REP_IRAN_GOLD",
                timeframe=timeframe,
                quote_side=side,
                min_observations=1,
                collection_run_id=collection_run_id,
            )
            saved, _ = persist_candles(candles)
            total_saved += saved
            results.append({
                "platform": "goldika",
                "quote_side": side,
                "saved": saved,
                "status": "OK",
            })
        except Exception as e:
            results.append({
                "platform": "goldika",
                "quote_side": side,
                "saved": 0,
                "status": f"ERROR: {e}",
            })

    # XAU/USD candles from existing observations
    try:
        candles = build_candles_from_observations(
            platform="kitco_fallback",
            instrument="XAUUSD",
            timeframe=timeframe,
            quote_side="SINGLE",
            min_observations=1,
            collection_run_id=collection_run_id,
        )
        saved, _ = persist_candles(candles)
        total_saved += saved
        results.append({
            "platform": "kitco_fallback",
            "instrument": "XAUUSD",
            "quote_side": "SINGLE",
            "saved": saved,
            "status": "OK",
        })
    except Exception as e:
        results.append({
            "platform": "kitco_fallback",
            "instrument": "XAUUSD",
            "quote_side": "SINGLE",
            "saved": 0,
            "status": f"ERROR: {e}",
        })

    # USD/IRR candles from existing observations
    try:
        candles = build_candles_from_observations(
            platform="bonbast",
            instrument="USD/IRR",
            timeframe=timeframe,
            quote_side="SINGLE",
            min_observations=1,
            collection_run_id=collection_run_id,
        )
        saved, _ = persist_candles(candles)
        total_saved += saved
        results.append({
            "platform": "bonbast",
            "instrument": "USD/IRR",
            "quote_side": "SINGLE",
            "saved": saved,
            "status": "OK",
        })
    except Exception as e:
        results.append({
            "platform": "bonbast",
            "instrument": "USD/IRR",
            "quote_side": "SINGLE",
            "saved": 0,
            "status": f"ERROR: {e}",
        })

    return {
        "timeframe": timeframe,
        "collection_run_id": collection_run_id,
        "total_saved": total_saved,
        "platform_results": results,
    }
