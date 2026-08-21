/*
Gold Premium Monitor — PRE-SP-C.9 Neon Migration

Purpose:
- Add analysis_read_model_json to analysis_snapshots
- Preserve all existing C.8 data
- Idempotent and safe to run repeatedly
*/

BEGIN;

-- ============================================================
-- 1. ADD analysis_read_model_json to analysis_snapshots
-- ============================================================

ALTER TABLE analysis_snapshots
    ADD COLUMN IF NOT EXISTS analysis_read_model_json JSONB;

-- ============================================================
-- 2. INDEX for read model queries
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_read_model
    ON analysis_snapshots USING GIN (analysis_read_model_json);

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
  AND column_name = 'analysis_read_model_json';

-- ============================================================
-- 4. VERIFICATION — INDEX
-- ============================================================

SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'analysis_snapshots'
  AND indexname = 'idx_analysis_snapshots_read_model';

COMMIT;
