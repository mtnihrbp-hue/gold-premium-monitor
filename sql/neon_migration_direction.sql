-- SP-D incremental Neon migration: direction_snapshots (the DIRECTION panel and its ledger).
-- Adds one new table. No existing table, column or row is touched.
--
-- Why. /Direction answers on demand from a panel computed twice a day (the first
-- scheduled run from 06:00 and from 13:00 Tehran), so a reader's request never computes
-- anything and never writes. The owner asked for self-learning from day one with
-- safeguards (2026-10-03): every forecast a panel shows is stored with it before its
-- outcome exists, resolved later against tgju's daily candles, and its live record
-- decides whether the figure keeps its place in the message. That record has to
-- survive between runs and outlive state.json, so it belongs in Neon.
--
-- One row per Tehran day and slot. panel is the full computed panel as rendered,
-- forecasts the commitments it makes (new high within 20 days, the 20- and 60-day
-- ranges, the stance), outcomes their resolution once the horizon has passed.
-- A panel is never rewritten after it is stored, and only outcomes and resolved_at
-- are filled in later.
--
-- Rollback is at the bottom of this file.

CREATE TABLE IF NOT EXISTS direction_snapshots (
    id SERIAL PRIMARY KEY,
    local_date DATE NOT NULL,
    slot VARCHAR(8) NOT NULL,
    computed_at TIMESTAMP NOT NULL,
    candle_date DATE,
    price NUMERIC(20, 2),
    price_source VARCHAR(8),
    status VARCHAR(24) NOT NULL,
    model_version VARCHAR(24) NOT NULL,
    stance VARCHAR(24),
    panel JSONB NOT NULL,
    forecasts JSONB NOT NULL,
    outcomes JSONB,
    resolved_at TIMESTAMP,
    CONSTRAINT uq_direction_snapshots_slot UNIQUE (local_date, slot)
);

COMMENT ON TABLE direction_snapshots IS
    'The DIRECTION panel, computed by the scheduled run from 06:00 and from 13:00 Tehran, '
    'with the forecasts it showed and their outcomes against tgju candles. computed_at and '
    'resolved_at are UTC, local_date is the Tehran day (SP_C_HANDOFF.md section 49).';

-- --------------------------------------------------------------------------
-- Verification
-- --------------------------------------------------------------------------
-- SELECT column_name, data_type, is_nullable FROM information_schema.columns
--  WHERE table_name = 'direction_snapshots' ORDER BY ordinal_position;   -- 14 columns
-- SELECT conname FROM pg_constraint
--  WHERE conrelid = 'direction_snapshots'::regclass;                      -- pkey, slot
-- SELECT COUNT(*) FROM direction_snapshots;                               -- 0 until the first run

-- --------------------------------------------------------------------------
-- Rollback (discards every stored panel and its forecast record)
-- --------------------------------------------------------------------------
-- DROP TABLE IF EXISTS direction_snapshots;
