-- Hotfix incremental Neon migration: market_daily_candles (SP-D TA track, step 1).
-- Adds one new table. No existing table, column or row is touched.
--
-- Why. Technical analysis needs real daily candles and a long history. Our own
-- platform_candles are single points (98% have open = high = low = close) and our
-- own daily history is 15 days deep. tgju.org publishes real daily candles for 18K
-- gold from 2013-07-22 (3,516 trading days) and for the dollar from 2011-11-26
-- (3,964), and its 18K daily close tracks our platforms at 0.95 daily correlation
-- (SP_C_HANDOFF.md section 41). The 11:00 and 12:00 runs of 2026-09-30 proved the
-- production runner collects them (section 41.6).
--
-- A separate table, not platform_prices or price_observations: tgju is not a
-- platform a reader can buy from, and its candles are daily aggregates, not point
-- readings. FACTS keep their source, so they are never mixed.
--
-- One row per source, instrument and trading day. Only completed days are stored
-- (never today's), first-seen values are never overwritten, and a candle whose low
-- and high do not bound its open and close is stored as published but flagged
-- INCONSISTENT (10 of 7,480 on record, 2018-2025).
--
-- Rollback is at the bottom of this file.

CREATE TABLE IF NOT EXISTS market_daily_candles (
    id SERIAL PRIMARY KEY,
    source VARCHAR(20) NOT NULL,
    instrument VARCHAR(50) NOT NULL,
    trade_date DATE NOT NULL,
    trade_date_jalali VARCHAR(10),
    open NUMERIC(20, 2) NOT NULL,
    high NUMERIC(20, 2) NOT NULL,
    low NUMERIC(20, 2) NOT NULL,
    close NUMERIC(20, 2) NOT NULL,
    unit VARCHAR(10) NOT NULL DEFAULT 'IRR',
    source_quality VARCHAR(20) NOT NULL DEFAULT 'COMPLETE',
    collected_at TIMESTAMP NOT NULL,
    CONSTRAINT uq_market_daily_candles_identity UNIQUE (source, instrument, trade_date)
);

COMMENT ON TABLE market_daily_candles IS
    'Daily OHLC candles from external market sources (tgju since 2026-09-30), one row '
    'per source, instrument and completed trading day. collected_at is UTC, and trade_date '
    'is the Tehran trading day (SP_C_HANDOFF.md section 41).';

-- --------------------------------------------------------------------------
-- Verification
-- --------------------------------------------------------------------------
-- SELECT column_name, data_type, is_nullable FROM information_schema.columns
--  WHERE table_name = 'market_daily_candles' ORDER BY ordinal_position;   -- 12 columns
-- SELECT conname FROM pg_constraint
--  WHERE conrelid = 'market_daily_candles'::regclass;                      -- pkey, identity
-- SELECT COUNT(*) FROM market_daily_candles;                               -- 0 until the first run

-- --------------------------------------------------------------------------
-- Rollback (discards every stored candle; the next run would backfill again)
-- --------------------------------------------------------------------------
-- DROP TABLE IF EXISTS market_daily_candles;
