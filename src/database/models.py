"""SQLAlchemy ORM models for the Gold Premium Monitor database.

Tables:
- market_snapshots: one row per complete market calculation cycle
- platform_prices: one row per platform price observation
- system_events: future intelligence events (created empty for SP2+)
- market_hypotheses: reasoning snapshots for meta-learning (SP3 foundation)
"""

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
