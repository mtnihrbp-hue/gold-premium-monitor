"""Analysis Snapshot builder.

PRE-SP-C.2: assembles analysis snapshots from existing market data.
Separates system-triggered analysis from user-triggered live snapshots.
"""

from datetime import datetime
from typing import Optional

from database.repository import (
    save_analysis_snapshot,
    analysis_snapshot_exists,
    get_latest_market_snapshot,
    get_latest_market_state,
)
from analysis.scheduler import generate_source_run_id


def build_analysis_snapshot(
    analysis_timestamp: Optional[datetime] = None,
    config: Optional[dict] = None,
) -> int:
    """Build and save an analysis snapshot from the latest market data.

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

    if analysis_snapshot_exists(source_run_id):
        print(f"Analysis snapshot {source_run_id} already exists — skipping")
        return -1

    market_snapshot = get_latest_market_snapshot()
    market_state = get_latest_market_state()

    data_quality = {
        "market_snapshot": "AVAILABLE" if market_snapshot else "UNAVAILABLE",
        "market_state": "AVAILABLE" if market_state else "UNAVAILABLE",
        "xau_usd": "AVAILABLE" if market_snapshot and market_snapshot.world_gold_usd else "UNAVAILABLE",
        "usd_irr": "AVAILABLE" if market_snapshot and market_snapshot.usd_irr else "UNAVAILABLE",
    }

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
    structure_state = "UNKNOWN"
    market_state_id = None
    if market_state:
        valuation_state = market_state.valuation_state or "UNKNOWN"
        momentum_state = market_state.momentum_state or "UNKNOWN"
        structure_state = market_state.structure_state or "UNKNOWN"
        market_state_id = market_state.id

    rep_gold_price = None

    return save_analysis_snapshot(
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
        structure_state=structure_state,
        data_quality_json=data_quality,
    )
