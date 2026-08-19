-- Gold Premium Monitor — PRE-SP-C.4 Neon Migration
--
-- Purpose:
--   Idempotently add PRE-SP-C.4 fields to an existing Neon database.
--
-- IMPORTANT:
--   Run this migration against the active Neon branch/database.
--   Do not use sql/neon_schema.sql as a migration against an already-populated
--   database; that file documents the canonical target schema.

-- ============================================================
-- 1. ENSURE analysis_snapshots EXISTS
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
    data_quality_json TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_analysis_snapshots_source_run_id
        UNIQUE (source_run_id)
);

-- ============================================================
-- 2. PRE-SP-C.4 COLUMNS
-- ============================================================

ALTER TABLE analysis_snapshots
    ADD COLUMN IF NOT EXISTS regime_state VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN',
    ADD COLUMN IF NOT EXISTS technical_state_json TEXT,
    ADD COLUMN IF NOT EXISTS previous_regime VARCHAR(20),
    ADD COLUMN IF NOT EXISTS regime_candidate_state VARCHAR(20),
    ADD COLUMN IF NOT EXISTS regime_confirmation_count INTEGER NOT NULL DEFAULT 0;

-- ============================================================
-- 3. INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_timestamp
    ON analysis_snapshots(analysis_timestamp);

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_type_timestamp
    ON analysis_snapshots(snapshot_type, analysis_timestamp);

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_market_snapshot
    ON analysis_snapshots(market_snapshot_id);

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_market_state
    ON analysis_snapshots(market_state_id);

-- ============================================================
-- 4. SNAPSHOT TYPE CONSTRAINT
-- ============================================================

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
-- 5. VERIFICATION
-- ============================================================

SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'analysis_snapshots'
ORDER BY ordinal_position;
