"""SQLAlchemy ORM models."""

from datetime import datetime

from sqlalchemy import Column, Integer, SmallInteger, String, Numeric, Date, DateTime, ForeignKey, Text, JSON, Index, UniqueConstraint, Boolean, CheckConstraint, text
from sqlalchemy.sql import func

from database.connection import Base


#from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text, JSON

class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    fair_price = Column(Numeric(20, 2), nullable=False)
    premium_percent = Column(Numeric(10, 4), nullable=False)
    # scheduled | user | unknown. Rows written before the SP-C.1 migration stay
    # 'unknown' because the distinction was never recorded and cannot be recovered.
    collection_mode = Column(String(20), nullable=False, default="unknown")
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
    # Relative valuation as it stood when this decision was made, so the scorecard
    # can attribute an outcome to what the system actually knew at the time.
    valuation_context_json = Column(JSON)

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
    # TEXT since 2026-09-30 (sql/neon_migration_news_url.sql): Google News and
    # percent-encoded Persian links exceed 500 characters, and an item whose link
    # did not fit was lost entirely.
    url = Column(Text, nullable=True)
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
    quote_side = Column(String(10), nullable=False, default="SINGLE")
    freshness = Column(String(20), nullable=False, default="UNKNOWN")
    collection_mode = Column(String(20), nullable=False, default="unknown")
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
########

class PlatformCandle(Base):
    """Canonical derived candle from platform price observations.

    PRE-SP-C.14A: deterministic candle aggregation with provenance.
    """

    __tablename__ = "platform_candles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False)
    instrument = Column(String(50), nullable=False)
    timeframe = Column(String(10), nullable=False)
    bucket_start = Column(DateTime, nullable=False)
    bucket_end = Column(DateTime, nullable=False)
    open = Column(Numeric(30, 8), nullable=False)
    high = Column(Numeric(30, 8), nullable=False)
    low = Column(Numeric(30, 8), nullable=False)
    close = Column(Numeric(30, 8), nullable=False)
    candle_type = Column(String(50), nullable=False, default="DERIVED_FROM_POINT_OBSERVATIONS")
    quote_side = Column(String(10), nullable=False, default="SINGLE")
    source_quality = Column(String(20), nullable=False, default="COMPLETE")
    observation_count = Column(Integer, nullable=False, default=0)
    collection_run_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_platform_candles_lookup", "platform", "instrument", "timeframe", "quote_side", "bucket_start"),
        Index("idx_platform_candles_bucket", "bucket_start", "bucket_end"),
        Index("idx_platform_candles_quality", "source_quality"),
    )
    #########


class MarketDailyCandle(Base):
    """A daily candle as an external market source published it (tgju since 2026-09-30).

    SP-D technical-analysis track (SP_C_HANDOFF.md section 41). Not a platform price
    and never mixed with one: tgju is not a platform a reader can buy from. One row
    per source, instrument and completed trading day; trade_date is the Tehran day,
    collected_at is UTC. First-seen values are never overwritten. A candle whose low
    and high do not bound its open and close is kept as published, flagged
    INCONSISTENT.
    """

    __tablename__ = "market_daily_candles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(20), nullable=False)
    instrument = Column(String(50), nullable=False)
    trade_date = Column(Date, nullable=False)
    trade_date_jalali = Column(String(10), nullable=True)
    open = Column(Numeric(20, 2), nullable=False)
    high = Column(Numeric(20, 2), nullable=False)
    low = Column(Numeric(20, 2), nullable=False)
    close = Column(Numeric(20, 2), nullable=False)
    unit = Column(String(10), nullable=False, default="IRR")
    source_quality = Column(String(20), nullable=False, default="COMPLETE")
    collected_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("source", "instrument", "trade_date", name="uq_market_daily_candles_identity"),
    )


class DirectionSnapshot(Base):
    """The DIRECTION panel as computed by a scheduled run, with its forecast ledger.

    SP-D (SP_D_HANDOFF.md section 4). One row per Tehran day and slot ("06:00" or
    "13:00"): the first scheduled run from each hour computes it, /Direction only reads
    it. `panel` is never rewritten; `outcomes` and `resolved_at` are filled in once each
    forecast's horizon has passed on tgju's candles.
    """

    __tablename__ = "direction_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    local_date = Column(Date, nullable=False)
    slot = Column(String(8), nullable=False)
    computed_at = Column(DateTime, nullable=False)
    candle_date = Column(Date, nullable=True)
    price = Column(Numeric(20, 2), nullable=True)
    price_source = Column(String(8), nullable=True)
    status = Column(String(24), nullable=False)
    model_version = Column(String(24), nullable=False)
    stance = Column(String(24), nullable=True)
    panel = Column(JSON, nullable=False)
    forecasts = Column(JSON, nullable=False)
    outcomes = Column(JSON, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("local_date", "slot", name="uq_direction_snapshots_slot"),
    )


class PaperAccount(Base):
    """A hypothetical account trading whole grams of 18K under the owner's contract.

    SP-D (SP_D_HANDOFF.md section 9). Three accounts start together: the analyst (pushes
    its trades and the 21:00 report), buy-and-hold and the system's own final BUY/SELL
    (both silent, for the quarterly review). Money is in rial, as everywhere else.
    """

    __tablename__ = "paper_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(32), nullable=False, unique=True)
    policy = Column(String(40), nullable=False)
    venue = Column(String(20), nullable=False)
    start_cash = Column(Numeric(20, 2), nullable=False)
    started_at = Column(DateTime, nullable=False)
    pushes = Column(Boolean, nullable=False, default=False)
    status = Column(String(16), nullable=False, default="ACTIVE")


class PaperActivity(Base):
    """One evaluation, trade or daily report of a paper account.

    `cash` and `holding` are the account's state after the row, so the latest row is the
    account. TRADE carries the grams and the price paid or received; REPORT the value at
    the venue's sell price at 21:00; EVAL the analyst's decision at a run with its inputs.
    The database itself holds two clauses of the contract: at most two trades (trade_no 1
    or 2, owner 2026-10-04) and one report per account per Tehran day.
    """

    __tablename__ = "paper_activity"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("paper_accounts.id"), nullable=False)
    at = Column(DateTime, nullable=False)
    local_date = Column(Date, nullable=False)
    kind = Column(String(12), nullable=False)
    action = Column(String(12), nullable=True)
    grams = Column(Integer, nullable=True)
    price = Column(Numeric(20, 2), nullable=True)
    cash = Column(Numeric(20, 2), nullable=False)
    holding = Column(Integer, nullable=False)
    value = Column(Numeric(20, 2), nullable=True)
    reason = Column(Text, nullable=True)
    inputs = Column(JSON, nullable=True)
    trade_no = Column(SmallInteger, nullable=True)

    __table_args__ = (
        Index("uq_paper_trade_slot", "account_id", "local_date", "trade_no", unique=True,
              postgresql_where=text("kind = 'TRADE'"), sqlite_where=text("kind = 'TRADE'")),
        CheckConstraint("kind <> 'TRADE' OR trade_no IN (1, 2)", name="ck_paper_trade_no"),
        Index("uq_paper_one_report_a_day", "account_id", "local_date", unique=True,
              postgresql_where=text("kind = 'REPORT'"), sqlite_where=text("kind = 'REPORT'")),
        Index("ix_paper_activity_account_at", "account_id", "at"),
    )


class IranNodeReading(Base):
    """One reading by the Iran-side node: the owner's phone in Iran reads what GitHub's
    runner is refused (Daric first) and inserts it here as the INSERT-only role
    iran_node (iran_node/node.py; SP_D_HANDOFF.md section 30). Production reads it.
    Prices in rial; observed_at is when the node read the source, in UTC.
    """

    __tablename__ = "iran_node_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    node = Column(String(20), nullable=False)
    source = Column(String(20), nullable=False)
    instrument = Column(String(40), nullable=False)
    observed_at = Column(DateTime, nullable=False)
    bid = Column(Numeric(20, 2), nullable=True)
    ask = Column(Numeric(20, 2), nullable=True)
    value = Column(Numeric(20, 4), nullable=True)
    status = Column(String(10), nullable=False)
    detail = Column(Text, nullable=True)
    payload = Column(JSON, nullable=True)
    received_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("ix_iran_node_readings_lookup", "source", "instrument", "observed_at"),
    )
