/*
Gold Premium Monitor — PRE-SP-C.7 Neon Migration

Purpose:
- Add intelligence_result_json to analysis_snapshots
- Preserve all existing C.6 data
- Idempotent and safe to run repeatedly
*/

BEGIN;

-- ============================================================
-- 1. ADD intelligence_result_json to analysis_snapshots
-- ============================================================

ALTER TABLE analysis_snapshots
    ADD COLUMN IF NOT EXISTS intelligence_result_json JSONB;

-- ============================================================
-- 2. INDEX for intelligence queries
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_intelligence
    ON analysis_snapshots USING GIN (intelligence_result_json);

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
  AND column_name = 'intelligence_result_json';

-- ============================================================
-- 4. VERIFICATION — INDEX
-- ============================================================

SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'analysis_snapshots'
  AND indexname = 'idx_analysis_snapshots_intelligence';

COMMIT;
