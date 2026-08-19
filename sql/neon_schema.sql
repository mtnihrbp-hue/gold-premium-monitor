-- Gold Premium Monitor — canonical Neon schema used by PRE-SP-C.
-- Apply to the project's active Neon branch/database.

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
    data_quality_json TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_analysis_snapshots_source_run_id UNIQUE (source_run_id),
    CONSTRAINT chk_analysis_snapshot_type CHECK (snapshot_type IN ('analysis', 'live'))
);

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_timestamp
    ON analysis_snapshots(analysis_timestamp);

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_type_timestamp
    ON analysis_snapshots(snapshot_type, analysis_timestamp);

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_market_snapshot
    ON analysis_snapshots(market_snapshot_id);

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_market_state
    ON analysis_snapshots(market_state_id);
