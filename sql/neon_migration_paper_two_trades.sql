-- SP-D incremental Neon migration: up to two PAPER trades a day (owner, 2026-10-04).
-- Changes paper_activity only: one nullable column, one index replaced, one CHECK.
-- No other table is touched; paper_activity held 0 rows when this was written.
--
-- Why. The contract allowed one trade per account per Tehran day, held by the partial
-- unique index uq_paper_one_trade_a_day. The owner widened it to two ("I can even expand
-- the buy sell window from one daily to max 2 daily"). Each TRADE row now carries its
-- number in the day, 1 or 2; the database refuses a third, and a duplicate number.
--
-- Rollback is at the bottom of this file.

ALTER TABLE paper_activity ADD COLUMN IF NOT EXISTS trade_no SMALLINT;

DROP INDEX IF EXISTS uq_paper_one_trade_a_day;

CREATE UNIQUE INDEX IF NOT EXISTS uq_paper_trade_slot
    ON paper_activity (account_id, local_date, trade_no) WHERE kind = 'TRADE';

ALTER TABLE paper_activity ADD CONSTRAINT ck_paper_trade_no
    CHECK (kind <> 'TRADE' OR trade_no IN (1, 2));

-- --------------------------------------------------------------------------
-- Verification
-- --------------------------------------------------------------------------
-- SELECT indexname FROM pg_indexes WHERE tablename = 'paper_activity';
--   -- ix_paper_activity_account_at, paper_activity_pkey, uq_paper_one_report_a_day,
--   -- uq_paper_trade_slot
-- SELECT conname FROM pg_constraint WHERE conrelid = 'paper_activity'::regclass AND contype = 'c';
--   -- ck_paper_trade_no

-- --------------------------------------------------------------------------
-- Rollback (back to one trade a day; only while no day holds two trades)
-- --------------------------------------------------------------------------
-- ALTER TABLE paper_activity DROP CONSTRAINT IF EXISTS ck_paper_trade_no;
-- DROP INDEX IF EXISTS uq_paper_trade_slot;
-- CREATE UNIQUE INDEX uq_paper_one_trade_a_day ON paper_activity (account_id, local_date) WHERE kind = 'TRADE';
-- ALTER TABLE paper_activity DROP COLUMN IF EXISTS trade_no;
