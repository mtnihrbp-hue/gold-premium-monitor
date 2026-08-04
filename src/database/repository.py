"""Database repository for market snapshot operations.

All database writes are wrapped in transactions.
Read operations return None / [] when the database is unavailable.
"""

from datetime import datetime, timedelta

from database.connection import get_session
from database.models import MarketSnapshot, PlatformPrice


def save_market_snapshot(
    timestamp,
    fair_price,
    premium_percent,
    world_gold_usd=None,
    usd_irr=None,
    signal=None,
    confidence=None,
    platform_prices=None,
):
    """Save a market snapshot and associated platform prices.

    Args:
        timestamp: datetime of the observation
        fair_price: calculated fair price (IRR)
        premium_percent: premium percentage
        world_gold_usd: world gold price in USD/oz (optional)
        usd_irr: USD sell rate in IRR (optional)
        signal: BUY / SELL / HOLD / None (optional)
        confidence: model confidence 0-1 (optional, SP1 always None)
        platform_prices: list of dicts with keys:
            platform_name (str), price_irr (int/float), change_irr (optional)

    Returns:
        snapshot id (int)

    Raises:
        RuntimeError: if database is not configured
        Exception: re-raised after rollback on write failure
    """
    session = get_session()
    if session is None:
        raise RuntimeError("Database not configured (DATABASE_URL missing)")

    try:
        snapshot = MarketSnapshot(
            timestamp=timestamp,
            fair_price=fair_price,
            premium_percent=premium_percent,
            world_gold_usd=world_gold_usd,
            usd_irr=usd_irr,
            signal=signal,
            confidence=confidence,
        )
        session.add(snapshot)
        session.flush()  # assign id

        if platform_prices:
            for pp in platform_prices:
                session.add(
                    PlatformPrice(
                        snapshot_id=snapshot.id,
                        platform_name=pp["platform_name"],
                        price_irr=pp["price_irr"],
                        change_irr=pp.get("change_irr"),
                        timestamp=timestamp,
                    )
                )

        session.commit()
        return snapshot.id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_latest_market_snapshot():
    """Return the most recent market snapshot, or None if unavailable."""
    session = get_session()
    if session is None:
        return None
    try:
        return (
            session.query(MarketSnapshot)
            .order_by(MarketSnapshot.timestamp.desc())
            .first()
        )
    finally:
        session.close()


def get_snapshots(days=30):
    """Return market snapshots from the last N days.

    Returns:
        List of MarketSnapshot objects, newest first.
        Empty list if database is unavailable.
    """
    session = get_session()
    if session is None:
        return []
    try:
        since = datetime.now() - timedelta(days=days)
        return (
            session.query(MarketSnapshot)
            .filter(MarketSnapshot.timestamp >= since)
            .order_by(MarketSnapshot.timestamp.desc())
            .all()
        )
    finally:
        session.close()
