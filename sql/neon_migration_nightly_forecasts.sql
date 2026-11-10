-- SP-D incremental Neon migration: nightly_forecasts (SP_D_HANDOFF.md section 109).
-- Adds one new table. No existing table, column or row is touched.
--
-- Why. The nightly message commits to numbers a reader can check: the 3-day line and, from a
-- fund week's third session, the funds' line. To be judged they must be written down before
-- their outcome exists, by the run that showed them. The 21:00 run cannot write to the branch
-- forward-ledger, whose one writer is forward-test.yml, and state.json can be lost with the
-- Actions cache, so the record belongs in Neon. Owner's approval: 2026-11-10.
--
-- One row per Tehran day and forecaster ('three_day', 'funds_week'; later the challengers and
-- the AI's forecast). forecast holds the numbers as the message showed them and is never
-- rewritten; only outcome and resolved_at are filled in, once, on or after due_date. A pull of
-- the same message before 21:00 writes nothing.
--
-- Rollback is at the bottom of this file.

CREATE TABLE IF NOT EXISTS nightly_forecasts (
    id SERIAL PRIMARY KEY,
    local_date DATE NOT NULL,
    forecaster VARCHAR(32) NOT NULL,
    version VARCHAR(24) NOT NULL,
    recorded_at TIMESTAMP NOT NULL,
    base_price NUMERIC(20, 2) NOT NULL,
    due_date DATE NOT NULL,
    forecast JSONB NOT NULL,
    outcome JSONB,
    resolved_at TIMESTAMP,
    CONSTRAINT uq_nightly_forecasts_day UNIQUE (local_date, forecaster)
);

COMMENT ON TABLE nightly_forecasts IS
    'The forecasts the 21:00 nightly message showed, written before their outcome. local_date and '
    'due_date are Tehran days, recorded_at and resolved_at UTC, base_price rial per gram of 18K '
    '(the figure of the message''s own NOW line). SP_D_HANDOFF.md section 109.';

-- --------------------------------------------------------------------------
-- Verification
-- --------------------------------------------------------------------------
-- SELECT column_name, data_type, is_nullable FROM information_schema.columns
--  WHERE table_name = 'nightly_forecasts' ORDER BY ordinal_position;     -- 10 columns
-- SELECT conname FROM pg_constraint
--  WHERE conrelid = 'nightly_forecasts'::regclass;                       -- pkey, day
-- SELECT COUNT(*) FROM nightly_forecasts;                                -- 0 until the first night

-- --------------------------------------------------------------------------
-- Rollback (discards every recorded forecast)
-- --------------------------------------------------------------------------
-- DROP TABLE IF EXISTS nightly_forecasts;
