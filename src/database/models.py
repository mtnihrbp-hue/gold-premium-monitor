"""SQLAlchemy ORM models."""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text, JSON
from sqlalchemy.sql import func

from database.connection import Base


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    fair_price = Column(Numeric(20, 2), nullable=False)
    premium_percent = Column(Numeric(10, 4), nullable=False)
    world_gold_usd = Column(Numeric(10, 2), nullable=True)
    usd_irr = Column(Numeric(20, 2), nullable=True)
    signal = Column(String(10), nullable=True)
    confidence = Column(Numeric(5, 4), nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class PlatformPrice(Base):
    __tablename__ = "platform_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(Integer, ForeignKey("market_snapshots.id"), nullable=False)
    platform_name = Column(String(50), nullable=False)
    price_irr = Column(Numeric(20, 2), nullable=False)
    change_irr = Column(Numeric(20, 2), nullable=True)
    timestamp = Column(DateTime, nullable=False)


class SystemEvent(Base):
    __tablename__ = "system_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    event_type = Column(String(50), nullable=False)
    source = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)


class MarketHypothesis(Base):
    __tablename__ = "market_hypotheses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, server_default=func.now())
    hypothesis_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    expected_outcome = Column(String(100), nullable=True)
    horizon_hours = Column(Integer, nullable=True)
    basis_json = Column(JSON, nullable=True)
    predicted_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    actual_outcome = Column(String(100), nullable=True)
    result = Column(String(20), nullable=True)
    failure_reason = Column(Text, nullable=True)
    model_version = Column(String(20), nullable=True)
    source = Column(String(50), nullable=True)


class MarketState(Base):
    """Interpreted market state for a single snapshot.

    Kept separate from market_snapshots because:
      - market_snapshots = raw observations (stable schema)
      - market_states    = interpreted state (evolves with intelligence)
      - SP-B will add columns here without touching raw data
    """

    __tablename__ = "market_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(
        Integer,
        ForeignKey("market_snapshots.id"),
        nullable=False,
    )

    # Valuation
    valuation_state = Column(String(20), nullable=False)

    # Momentum
    momentum_state = Column(String(20), nullable=False)
    premium_direction = Column(String(30), nullable=False)

    # Structure
    structure_state = Column(String(20), nullable=False)
    platform_average = Column(Numeric(20, 2))
    platform_high = Column(Numeric(20, 2))
    platform_low = Column(Numeric(20, 2))
    platform_spread = Column(Numeric(20, 2))
    platforms_below_fair = Column(Integer)
    platforms_above_fair = Column(Integer)

    # Conflict & Decision
    conflict_state = Column(String(30), nullable=False)
    candidate_decision = Column(String(10), nullable=False)
    final_decision = Column(String(10), nullable=False)
    reason = Column(Text)

    timestamp = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
