-- Gold Premium Monitor — PRE-SP-C.6 Neon Migration
--
-- Purpose: Idempotently add evidence_package_json to analysis_snapshots.
-- Run this against the active Neon branch/database.

-- ============================================================
-- 1. ADD evidence_package_json to analysis_snapshots
-- ============================================================

ALTER TABLE analysis_snapshots
    ADD COLUMN IF NOT EXISTS evidence_package_json JSONB;

-- ============================================================
-- 2. INDEX for evidence package queries
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_evidence
    ON analysis_snapshots USING GIN (evidence_package_json);

-- ============================================================
-- 3. VERIFICATION
-- ============================================================

SELECT
    column_name,
    data_type
FROM information_schema.columns
WHERE table_schema = 'public'
    AND table_name = 'analysis_snapshots'
    AND column_name = 'evidence_package_json';
