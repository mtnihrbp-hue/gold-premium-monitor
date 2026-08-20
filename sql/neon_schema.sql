-- Gold Premium Monitor — canonical Neon schema (PRE-SP-C.6)
--
-- This file is the repository-side canonical target schema.
-- For an existing Neon database, use the incremental migration files
-- (for example sql/neon_migration_c4.sql, sql/neon_migration_c5.sql,
-- and the current C.6 migration) rather than this complete schema.
-- Do not use this complete schema as a destructive replacement migration.

-- ============================================================
-- 1. MARKET SNAPSHOTS (SP-A)
-- ============================================================

CREATE TABLE IF NOT EXISTS market_snapshots (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    fair_price NUMERIC(20, 2) NOT NULL,
    premium_percent NUMERIC(10, 4) NOT NULL,
    world_gold_usd NUMERIC(10, 2),
    usd_irr NUMERIC(20, 2),
    signal VARCHAR(10),
    confidence NUMERIC(5, 4),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 2. PLATFORM PRICES (SP-A)
-- ============================================================

CREATE TABLE IF NOT EXISTS platform_prices (
    id SERIAL PRIMARY KEY,
    snapshot_id INTEGER REFERENCES market_snapshots(id) NOT NULL,
    platform_name VARCHAR(50) NOT NULL,
    price_irr NUMERIC(20, 2) NOT NULL,
    change_irr NUMERIC(20, 2),
    timestamp TIMESTAMP NOT NULL
);

-- ============================================================
-- 3. MARKET STATES (SP-A)
-- ============================================================

CREATE TABLE IF NOT EXISTS market_states (
    id SERIAL PRIMARY KEY,
    snapshot_id INTEGER REFERENCES market_snapshots(id),
    valuation_state VARCHAR(20) NOT NULL,
    momentum_state VARCHAR(20) NOT NULL,
    premium_direction VARCHAR(30) NOT NULL,
    structure_state VARCHAR(20) NOT NULL,
    platform_average NUMERIC(20, 2),
    platform_high NUMERIC(20, 2),
    platform_low NUMERIC(20, 2),
    platform_spread NUMERIC(20, 2),
    platforms_below_fair INTEGER,
    platforms_above_fair INTEGER,
    conflict_state VARCHAR(30) NOT NULL,
    candidate_decision VARCHAR(10) NOT NULL,
    final_decision VARCHAR(10) NOT NULL,
    reason TEXT,
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 4. SYSTEM EVENTS
-- ============================================================

CREATE TABLE IF NOT EXISTS system_events (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    source VARCHAR(100),
    description TEXT,
    metadata_json TEXT
);

-- ============================================================
-- 5. MARKET HYPOTHESES / FUTURE EVALUATION FOUNDATION
-- ============================================================

CREATE TABLE IF NOT EXISTS market_hypotheses (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    hypothesis_type VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    expected_outcome VARCHAR(100),
    horizon_hours INTEGER,
    basis_json TEXT,
    predicted_at TIMESTAMP,
    resolved_at TIMESTAMP,
    actual_outcome VARCHAR(100),
    result VARCHAR(20),
    failure_reason TEXT,
    model_version VARCHAR(20),
    source VARCHAR(50)
);

-- ============================================================
-- 6. NEWS EVENTS (SP-B.2)
-- ============================================================

CREATE TABLE IF NOT EXISTS news_events (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    source VARCHAR(200) NOT NULL,
    url VARCHAR(500),
    dedup_key VARCHAR(32),
    raw_headline VARCHAR(500) NOT NULL,
    raw_summary TEXT,
    event_type VARCHAR(50) NOT NULL,
    topic VARCHAR(100),
    relevance VARCHAR(20) NOT NULL,
    expected_usd_direction VARCHAR(20),
    expected_gold_direction VARCHAR(20),
    expected_duration VARCHAR(20),
    impact VARCHAR(20),
    confidence VARCHAR(20),
    uncertainty_notes TEXT,
    classification_method VARCHAR(20) NOT NULL,
    processed_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_news_events_dedup_key
    ON news_events(dedup_key);

-- ============================================================
-- 7. CANONICAL PRICE OBSERVATIONS (PRE-SP-C.1)
-- ============================================================

CREATE TABLE IF NOT EXISTS price_observations (
    id SERIAL PRIMARY KEY,
    instrument VARCHAR(50) NOT NULL,
    source VARCHAR(100) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    price NUMERIC(30, 8) NOT NULL,
    freshness VARCHAR(30),
    collection_run_id VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_price_observations_instrument_timestamp
    ON price_observations(instrument, timestamp);

CREATE INDEX IF NOT EXISTS idx_price_observations_source_timestamp
    ON price_observations(source, timestamp);

CREATE INDEX IF NOT EXISTS idx_price_observations_collection_run
    ON price_observations(collection_run_id);

-- ============================================================
-- 8. ANALYSIS SNAPSHOTS (PRE-SP-C.2 + PRE-SP-C.4)
-- ============================================================

CREATE TABLE IF NOT EXISTS analysis_snapshots (
    id SERIAL PRIMARY KEY,
    snapshot_type VARCHAR(30) NOT NULL DEFAULT 'analysis',
    analysis_timestamp TIMESTAMP NOT NULL,
    source_run_id VARCHAR(100) NOT NULL,
    analysis_window VARCHAR(50),
    market_snapshot_id INTEGER REFERENCES market_snapshots(id),
    market_state_id INTEGER REFERENCES market_states(id),
    xau_usd NUMERIC(30, 8),
    usd_irr NUMERIC(30, 8),
    rep_gold_price NUMERIC(30, 8),
    premium_percent NUMERIC(20, 8),
    valuation_state VARCHAR(20),
    momentum_state VARCHAR(20),
    structure_state VARCHAR(30),

    regime_state VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN',
    technical_state_json TEXT,
    previous_regime VARCHAR(20),
    regime_candidate_state VARCHAR(20),
    regime_confirmation_count INTEGER NOT NULL DEFAULT 0,

    data_quality_json TEXT,
    evidence_package_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_analysis_snapshots_source_run_id
        UNIQUE (source_run_id)
);

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_timestamp
    ON analysis_snapshots(analysis_timestamp);

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_type_timestamp
    ON analysis_snapshots(snapshot_type, analysis_timestamp);

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_market_snapshot
    ON analysis_snapshots(market_snapshot_id);

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_market_state
    ON analysis_snapshots(market_state_id);

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_evidence
    ON analysis_snapshots USING GIN (evidence_package_json);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_analysis_snapshot_type'
          AND conrelid = 'analysis_snapshots'::regclass
    ) THEN
        ALTER TABLE analysis_snapshots
            ADD CONSTRAINT chk_analysis_snapshot_type
            CHECK (snapshot_type IN ('analysis', 'live'));
    END IF;
END $$;

-- ============================================================
-- 8.5. OUTCOME EVALUATIONS (PRE-SP-C.5)
-- ============================================================

CREATE TABLE IF NOT EXISTS outcome_evaluations (
    id SERIAL PRIMARY KEY,
    analysis_snapshot_id INTEGER NOT NULL REFERENCES analysis_snapshots(id),
    horizon_hours INTEGER NOT NULL,

    reference_time TIMESTAMP NOT NULL,
    target_time TIMESTAMP NOT NULL,
    actual_observation_time TIMESTAMP,

    outcome_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',

    reference_rep_gold_price NUMERIC(20, 4),
    reference_xau_usd NUMERIC(20, 4),
    reference_usd_irr NUMERIC(20, 4),
    reference_premium_percent NUMERIC(10, 4),

    actual_rep_gold_price NUMERIC(20, 4),
    actual_xau_usd NUMERIC(20, 4),
    actual_usd_irr NUMERIC(20, 4),
    actual_premium_percent NUMERIC(10, 4),

    rep_gold_movement_percent NUMERIC(10, 4),
    rep_gold_direction VARCHAR(10),
    xau_usd_movement_percent NUMERIC(10, 4),
    xau_usd_direction VARCHAR(10),
    usd_irr_movement_percent NUMERIC(10, 4),
    usd_irr_direction VARCHAR(10),
    premium_movement_percent NUMERIC(10, 4),
    premium_direction VARCHAR(10),

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,

    CONSTRAINT uq_outcome_eval_snapshot_horizon
        UNIQUE (analysis_snapshot_id, horizon_hours)
);

CREATE INDEX IF NOT EXISTS idx_outcome_eval_target_time
    ON outcome_evaluations(target_time);

CREATE INDEX IF NOT EXISTS idx_outcome_eval_status
    ON outcome_evaluations(outcome_status);

-- ============================================================
-- 9. VERIFICATION
-- ============================================================

SELECT
    table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
      'market_snapshots',
      'platform_prices',
      'market_states',
      'system_events',
      'market_hypotheses',
      'news_events',
      'price_observations',
      'analysis_snapshots',
      'outcome_evaluations'
  )
ORDER BY table_name;
