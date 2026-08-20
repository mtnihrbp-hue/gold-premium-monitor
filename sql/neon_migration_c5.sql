-- Gold Premium Monitor — PRE-SP-C.5 Neon Migration
--
-- Purpose: Idempotently add outcome_evaluations to an existing Neon database.
-- Run this against the active Neon branch/database.
-- Do not use sql/neon_schema.sql as a migration against an already-populated database.

-- ============================================================
-- 1. OUTCOME EVALUATIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS outcome_evaluations (
    id SERIAL PRIMARY KEY,
    analysis_snapshot_id INTEGER NOT NULL REFERENCES analysis_snapshots(id),
    horizon_hours INTEGER NOT NULL,

    reference_time TIMESTAMP NOT NULL,
    target_time TIMESTAMP NOT NULL,
    actual_observation_time TIMESTAMP,

    outcome_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',

    -- Reference values from analysis snapshot
    reference_rep_gold_price NUMERIC(20, 4),
    reference_xau_usd NUMERIC(20, 4),
    reference_usd_irr NUMERIC(20, 4),
    reference_premium_percent NUMERIC(10, 4),

    -- Actual values from future canonical observations
    actual_rep_gold_price NUMERIC(20, 4),
    actual_xau_usd NUMERIC(20, 4),
    actual_usd_irr NUMERIC(20, 4),
    actual_premium_percent NUMERIC(10, 4),

    -- Movement calculations
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

-- ============================================================
-- 2. INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_outcome_eval_target_time
    ON outcome_evaluations(target_time);

CREATE INDEX IF NOT EXISTS idx_outcome_eval_status
    ON outcome_evaluations(outcome_status);

-- ============================================================
-- 3. VERIFICATION
-- ============================================================

SELECT
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_schema = 'public'
    AND table_name = 'outcome_evaluations'
ORDER BY ordinal_position;
