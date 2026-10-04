-- SP-D incremental Neon migration: the PAPER portfolio (paper_accounts, paper_activity).
-- Adds two new tables and their indexes. No existing table, column or row is touched.
--
-- Why. The owner's scenario (2026-10-04): the analyst trades a hypothetical 100,000,000
-- toman in whole grams of 18K, at most once a day, reports at 21:00 and is reviewed per
-- Persian quarter. An account's state (cash, grams), its trades, its daily values and
-- every run's decision with its inputs must outlive runs and state.json, and the
-- quarterly review reads them back, so they belong in Neon.
--
-- paper_accounts: one row per account (the analyst, buy-and-hold, the system's own final
-- BUY/SELL), with its policy version and venue. Money in rial, as everywhere else.
-- paper_activity: one row per evaluation, trade or daily report. cash and holding are the
-- state after the row. Two clauses of the contract are held by the database itself: one
-- trade and one report per account per Tehran day (partial unique indexes).
--
-- Rollback is at the bottom of this file.

CREATE TABLE IF NOT EXISTS paper_accounts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(32) NOT NULL UNIQUE,
    policy VARCHAR(40) NOT NULL,
    venue VARCHAR(20) NOT NULL,
    start_cash NUMERIC(20, 2) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    pushes BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS paper_activity (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES paper_accounts(id),
    at TIMESTAMP NOT NULL,
    local_date DATE NOT NULL,
    kind VARCHAR(12) NOT NULL,
    action VARCHAR(12),
    grams INTEGER,
    price NUMERIC(20, 2),
    cash NUMERIC(20, 2) NOT NULL,
    holding INTEGER NOT NULL,
    value NUMERIC(20, 2),
    reason TEXT,
    inputs JSONB
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_paper_one_trade_a_day
    ON paper_activity (account_id, local_date) WHERE kind = 'TRADE';

CREATE UNIQUE INDEX IF NOT EXISTS uq_paper_one_report_a_day
    ON paper_activity (account_id, local_date) WHERE kind = 'REPORT';

CREATE INDEX IF NOT EXISTS ix_paper_activity_account_at
    ON paper_activity (account_id, at);

COMMENT ON TABLE paper_accounts IS
    'Hypothetical accounts trading whole grams of 18K under the owner contract of 2026-10-04 '
    '(SP_D_HANDOFF.md section 9). Money in rial.';

COMMENT ON TABLE paper_activity IS
    'Every evaluation, trade and 21:00 report of a paper account. cash and holding are the '
    'state after the row. at is UTC, local_date the Tehran day.';

-- --------------------------------------------------------------------------
-- Verification
-- --------------------------------------------------------------------------
-- SELECT table_name, COUNT(*) FROM information_schema.columns
--  WHERE table_name IN ('paper_accounts', 'paper_activity') GROUP BY 1;    -- 8 and 13 columns
-- SELECT indexname FROM pg_indexes WHERE tablename = 'paper_activity';      -- pkey + 3
-- SELECT COUNT(*) FROM paper_accounts;                                     -- 0 until the first run

-- --------------------------------------------------------------------------
-- Rollback (discards every paper account and its whole record)
-- --------------------------------------------------------------------------
-- DROP TABLE IF EXISTS paper_activity;
-- DROP TABLE IF EXISTS paper_accounts;
