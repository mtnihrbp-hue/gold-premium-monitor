"""SQLAlchemy ORM models."""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text, JSON, Index, UniqueConstraint
from sqlalchemy.sql import func

from database.connection import Base


#from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text, JSON

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

##########


class NewsEvent(Base):
    """Structured news event for market intelligence.

    SP-B.2: deterministic keyword-classified external events.
    SP-B.3: may enhance with LLM interpretation.
    """

    __tablename__ = "news_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    source = Column(String(200), nullable=False)
    url = Column(String(500), nullable=True)
    dedup_key = Column(String(32), nullable=True, index=True)
    raw_headline = Column(String(500), nullable=False)
    raw_summary = Column(Text, nullable=True)

    # Classification (deterministic in SP-B.2)
    event_type = Column(String(50), nullable=False)
    topic = Column(String(100), nullable=True)
    relevance = Column(String(20), nullable=False)

    # Market direction expectations (conservative)
    expected_usd_direction = Column(String(20), nullable=True)
    expected_gold_direction = Column(String(20), nullable=True)
    expected_duration = Column(String(20), nullable=True)
    impact = Column(String(20), nullable=True)
    confidence = Column(String(20), nullable=True)
    uncertainty_notes = Column(Text, nullable=True)

    classification_method = Column(String(20), nullable=False)
    processed_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

###########


class PriceObservation(Base):
    """Canonical time-series observation for technical analysis.

    PRE-SP-C.1: dedicated time-series layer, separate from market_snapshots.
    Instruments: XAUUSD, USD/IRR, PAXG, REP_IRAN_GOLD.
    """

    __tablename__ = "price_observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instrument = Column(String(20), nullable=False)
    source = Column(String(50), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    price = Column(Numeric(20, 4), nullable=False)
    freshness = Column(String(20), nullable=False, default="UNKNOWN")
    collection_run_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_price_obs_instrument_ts", "instrument", "timestamp"),
        Index("idx_price_obs_run_id", "collection_run_id"),
    )

########



class AnalysisSnapshot(Base):
    """System-generated analysis snapshot for the Analysis Wing.

    PRE-SP-C.2: scheduled analysis foundation.
    Distinguishable from live user-triggered snapshots.
    References existing tables for lineage; stores key values for queryability.
    """

    __tablename__ = "analysis_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_type = Column(String(20), nullable=False, default="analysis")
    analysis_timestamp = Column(DateTime, nullable=False)
    source_run_id = Column(String(128), nullable=False, unique=True)
    analysis_window = Column(String(32), nullable=True)

    # Lineage: references to existing tables
    market_snapshot_id = Column(
        Integer,
        ForeignKey("market_snapshots.id"),
        nullable=True,
    )
    market_state_id = Column(
        Integer,
        ForeignKey("market_states.id"),
        nullable=True,
    )

    # Core market values (denormalized for self-containment)
    xau_usd = Column(Numeric(10, 2), nullable=True)
    usd_irr = Column(Numeric(20, 2), nullable=True)
    rep_gold_price = Column(Numeric(20, 2), nullable=True)
    premium_percent = Column(Numeric(10, 4), nullable=True)

    # Deterministic state fields (from market_state)
    valuation_state = Column(String(20), nullable=False, default="UNKNOWN")
    momentum_state = Column(String(20), nullable=False, default="UNKNOWN")
    structure_state = Column(String(20), nullable=False, default="UNKNOWN")

    # Data quality tracking (extensible)
    data_quality_json = Column(JSON, nullable=True)

    # PRE-SP-C.4: regime and technical state persistence
    regime_state = Column(String(20), nullable=False, default="UNKNOWN")
    technical_state_json = Column(JSON, nullable=True)

    # PRE-SP-C.4: regime hysteresis state for cross-run reconstruction
    previous_regime = Column(String(20), nullable=True)
    regime_candidate_state = Column(String(20), nullable=True)
    regime_confirmation_count = Column(Integer, nullable=False, default=0)
    # PRE-SP-C.6: deterministic evidence package
    evidence_package_json = Column(JSON, nullable=True)
    # PRE-SP-C.7: bounded market intelligence result
    intelligence_result_json = Column(JSON, nullable=True)
    # PRE-SP-C.8: analytical feature snapshot
    features_json = Column(JSON, nullable=True)
    # PRE-SP-C.9: analytical read model
    analysis_read_model_json = Column(JSON, nullable=True)

    
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_analysis_snap_ts", "analysis_timestamp"),
        Index("idx_analysis_snap_run_id", "source_run_id"),
    )


############

class OutcomeEvaluation(Base):
    __tablename__ = "outcome_evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_snapshot_id = Column(
        Integer,
        ForeignKey("analysis_snapshots.id"),
        nullable=False,
    )
    horizon_hours = Column(Integer, nullable=False)

    reference_time = Column(DateTime, nullable=False)
    target_time = Column(DateTime, nullable=False)
    actual_observation_time = Column(DateTime, nullable=True)

    outcome_status = Column(String(20), nullable=False, default="PENDING")

    reference_rep_gold_price = Column(Numeric(20, 4), nullable=True)
    reference_xau_usd = Column(Numeric(20, 4), nullable=True)
    reference_usd_irr = Column(Numeric(20, 4), nullable=True)
    reference_premium_percent = Column(Numeric(10, 4), nullable=True)

    actual_rep_gold_price = Column(Numeric(20, 4), nullable=True)
    actual_xau_usd = Column(Numeric(20, 4), nullable=True)
    actual_usd_irr = Column(Numeric(20, 4), nullable=True)
    actual_premium_percent = Column(Numeric(10, 4), nullable=True)

    rep_gold_movement_percent = Column(Numeric(10, 4), nullable=True)
    rep_gold_direction = Column(String(10), nullable=True)
    xau_usd_movement_percent = Column(Numeric(10, 4), nullable=True)
    xau_usd_direction = Column(String(10), nullable=True)
    usd_irr_movement_percent = Column(Numeric(10, 4), nullable=True)
    usd_irr_direction = Column(String(10), nullable=True)
    premium_movement_percent = Column(Numeric(10, 4), nullable=True)
    premium_direction = Column(String(10), nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("analysis_snapshot_id", "horizon_hours", name="uq_outcome_eval_snapshot_horizon"),
        Index("idx_outcome_eval_target_time", "target_time"),
        Index("idx_outcome_eval_status", "outcome_status"),
    )
