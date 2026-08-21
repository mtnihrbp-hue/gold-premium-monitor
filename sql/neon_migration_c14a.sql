-- Gold Premium Monitor — incremental Neon migration (PRE-SP-C.14A)
-- Purpose:
--   1. Add quote_side to price_observations for platform buy/sell semantics.
--   2. Create platform_candles table for canonical derived candle storage.
-- Safe for the existing production database; no data is dropped.

BEGIN;

-- 1. Add quote_side to price_observations
ALTER TABLE price_observations
    ADD COLUMN IF NOT EXISTS quote_side VARCHAR(10) DEFAULT 'SINGLE';

-- 2. Create platform_candles table
CREATE TABLE IF NOT EXISTS platform_candles (
    id SERIAL PRIMARY KEY,
    platform VARCHAR(50) NOT NULL,
    instrument VARCHAR(50) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    bucket_start TIMESTAMP NOT NULL,
    bucket_end TIMESTAMP NOT NULL,
    open NUMERIC(30, 8) NOT NULL,
    high NUMERIC(30, 8) NOT NULL,
    low NUMERIC(30, 8) NOT NULL,
    close NUMERIC(30, 8) NOT NULL,
    candle_type VARCHAR(50) NOT NULL DEFAULT 'DERIVED_FROM_POINT_OBSERVATIONS',
    quote_side VARCHAR(10) NOT NULL DEFAULT 'SINGLE',
    source_quality VARCHAR(20) NOT NULL DEFAULT 'COMPLETE',
    observation_count INTEGER NOT NULL DEFAULT 0,
    collection_run_id VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 3. Unique constraint for idempotency
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_platform_candles_identity'
          AND conrelid = 'platform_candles'::regclass
    ) THEN
        ALTER TABLE platform_candles
            ADD CONSTRAINT uq_platform_candles_identity
            UNIQUE (platform, instrument, timeframe, bucket_start, quote_side);
    END IF;
END $$;

-- 4. Indexes
CREATE INDEX IF NOT EXISTS idx_platform_candles_lookup
    ON platform_candles(platform, instrument, timeframe, quote_side, bucket_start);

CREATE INDEX IF NOT EXISTS idx_platform_candles_bucket
    ON platform_candles(bucket_start, bucket_end);

CREATE INDEX IF NOT EXISTS idx_platform_candles_quality
    ON platform_candles(source_quality);

COMMIT;
