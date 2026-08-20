/*
Gold Premium Monitor — PRE-SP-C.8 Neon Migration

Purpose:
- Add features_json to analysis_snapshots
- Preserve all existing C.7 data
- Idempotent and safe to run repeatedly
*/

BEGIN;

-- ============================================================
-- 1. ADD features_json to analysis_snapshots
-- ============================================================

ALTER TABLE analysis_snapshots
    ADD COLUMN IF NOT EXISTS features_json JSONB;

-- ============================================================
-- 2. INDEX for feature queries
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_features
    ON analysis_snapshots USING GIN (features_json);

-- ============================================================
-- 3. VERIFICATION — COLUMN
-- ============================================================

SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'analysis_snapshots'
  AND column_name = 'features_json';

-- ============================================================
-- 4. VERIFICATION — INDEX
-- ============================================================

SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'analysis_snapshots'
  AND indexname = 'idx_analysis_snapshots_features';

COMMIT;
