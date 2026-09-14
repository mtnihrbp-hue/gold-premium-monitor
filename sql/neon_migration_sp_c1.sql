-- SP-C.1 incremental Neon migration.
-- Preserves all existing production state. Additive only.
--
-- Two things cannot be derived from what is already stored.
--
-- 1. Whether a reading came from a scheduled run or a user-triggered update.
--    Nothing records it, and it cannot be recovered retroactively, so every
--    statistic drawn from market_snapshots is currently computed over a sample
--    biased toward moments a user happened to look. Existing rows are therefore
--    left as 'unknown' rather than guessed at.
--
-- 2. What the system knew when it made a decision. market_states records the
--    decision and the older state labels, but not the relative valuation that
--    will drive decisions from SP-C onward. Without it the scorecard can say a
--    decision was right but never why the system believed it.
--
-- Rollback is at the bottom of this file.

-- --------------------------------------------------------------------------
-- 1. Collection provenance
-- --------------------------------------------------------------------------

ALTER TABLE market_snapshots
    ADD COLUMN IF NOT EXISTS collection_mode VARCHAR(20) NOT NULL DEFAULT 'unknown';

ALTER TABLE price_observations
    ADD COLUMN IF NOT EXISTS collection_mode VARCHAR(20) NOT NULL DEFAULT 'unknown';

COMMENT ON COLUMN market_snapshots.collection_mode IS
    'scheduled | user | unknown. Rows written before SP-C.1 remain unknown because '
    'the distinction was never recorded and cannot be reconstructed.';

COMMENT ON COLUMN price_observations.collection_mode IS
    'scheduled | user | unknown. See market_snapshots.collection_mode.';

CREATE INDEX IF NOT EXISTS idx_market_snapshots_mode_time
    ON market_snapshots(collection_mode, timestamp);

CREATE INDEX IF NOT EXISTS idx_price_observations_mode_time
    ON price_observations(collection_mode, timestamp);

-- --------------------------------------------------------------------------
-- 2. Decision context
-- --------------------------------------------------------------------------

ALTER TABLE market_states
    ADD COLUMN IF NOT EXISTS valuation_context_json JSONB;

COMMENT ON COLUMN market_states.valuation_context_json IS
    'Relative valuation as it stood when this decision was made: percentile, band, '
    'boundaries, window size, sample size, confidence and drift. Stored so the '
    'scorecard can attribute an outcome to what the system actually knew. A single '
    'JSONB column is used rather than fixed columns so the context can evolve '
    'without a migration per field.';

CREATE INDEX IF NOT EXISTS idx_market_states_valuation_context
    ON market_states USING GIN (valuation_context_json);

-- --------------------------------------------------------------------------
-- Verification
-- --------------------------------------------------------------------------
--
--   SELECT collection_mode, count(*) FROM market_snapshots GROUP BY 1;
--     -> expect every existing row to report 'unknown'
--
--   SELECT count(*) FROM market_states WHERE valuation_context_json IS NOT NULL;
--     -> expect 0 until the first decision is written after this migration
--
--   SELECT count(*) FROM market_snapshots;
--   SELECT count(*) FROM price_observations;
--   SELECT count(*) FROM market_states;
--     -> must match the counts taken immediately before applying
--
-- --------------------------------------------------------------------------
-- Rollback
-- --------------------------------------------------------------------------
--
-- DROP INDEX IF EXISTS idx_market_states_valuation_context;
-- DROP INDEX IF EXISTS idx_price_observations_mode_time;
-- DROP INDEX IF EXISTS idx_market_snapshots_mode_time;
-- ALTER TABLE market_states     DROP COLUMN IF EXISTS valuation_context_json;
-- ALTER TABLE price_observations DROP COLUMN IF EXISTS collection_mode;
-- ALTER TABLE market_snapshots   DROP COLUMN IF EXISTS collection_mode;
--
-- The migration only adds columns and indexes, so rollback cannot lose any data
-- that existed before it was applied.
