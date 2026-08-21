-- Gold Premium Monitor — incremental Neon migration (PRE-SP-C.13)
-- Purpose:
--   1. Add the news_events table used by the Analysis Wing / C.13 Telegram news and health paths.
--   2. Expand outcome direction fields so explicit INSUFFICIENT_DATA states fit the established contract.
-- Safe for the existing production database; no data is dropped.

BEGIN;

CREATE TABLE IF NOT EXISTS news_events (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    source VARCHAR(200) NOT NULL,
    url VARCHAR(500),
    dedup_key VARCHAR(32),
    raw_headline VARCHAR(500) NOT NULL,
    raw_summary TEXT,
    event_type VARCHAR(50) NOT NULL,
    topic VARCHAR(100),
    relevance VARCHAR(20) NOT NULL,
    expected_usd_direction VARCHAR(20),
    expected_gold_direction VARCHAR(20),
    expected_duration VARCHAR(20),
    impact VARCHAR(20),
    confidence VARCHAR(20),
    uncertainty_notes TEXT,
    classification_method VARCHAR(20) NOT NULL,
    processed_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_news_events_dedup_key
    ON news_events(dedup_key);

ALTER TABLE outcome_evaluations
    ALTER COLUMN rep_gold_direction TYPE VARCHAR(20),
    ALTER COLUMN xau_usd_direction TYPE VARCHAR(20),
    ALTER COLUMN usd_irr_direction TYPE VARCHAR(20),
    ALTER COLUMN premium_direction TYPE VARCHAR(20);

COMMIT;
