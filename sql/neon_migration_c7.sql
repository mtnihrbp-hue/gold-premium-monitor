/*
Gold Premium Monitor — PRE-SP-C.7 Neon Migration

Purpose:
- Add persisted deterministic interpretation results to analysis_snapshots
- Preserve all existing C.6 data
- Idempotent and safe to run repeatedly

IMPORTANT:
- Incremental migration for an existing Neon database.
- Do not use sql/neon_schema.sql as a replacement migration.
*/

BEGIN;

ALTER TABLE analysis_snapshots
    ADD COLUMN IF NOT EXISTS intelligence_result_json JSONB;

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_intelligence
    ON analysis_snapshots USING GIN (intelligence_result_json);

COMMIT;
