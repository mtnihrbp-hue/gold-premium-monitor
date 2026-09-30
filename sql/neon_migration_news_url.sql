-- Hotfix incremental Neon migration: news_events.url VARCHAR(500) -> TEXT.
-- Preserves all existing production state. Widening only; no row is rewritten.
--
-- Why. Google News article links and percent-encoded Persian links (each Persian
-- letter becomes six characters, e.g. donya-e-eqtesad.com) exceed 500 characters.
-- An item whose link is longer fails to save with StringDataRightTruncation, so the
-- whole news item is lost, not just its link; the same items were retried and
-- failed again every run. On 2026-09-30, 45 unique items failed across six runs,
-- about 10-15% of the day's news, from donya-e-eqtesad.com and the three Google
-- News feeds. 139 stored donya-e-eqtesad links already sit at 450-499 characters.
--
-- Alternatives rejected (SP_C_HANDOFF.md section 40): truncating the link stores a
-- broken link (fabricated data); saving the item without it loses provenance;
-- decoding percent-encoding helps Persian links but not Google's and mixes two
-- formats; resolving Google redirects costs a network request per item.
--
-- Nothing in the system reads `url` for logic (deduplication hashes the title), no
-- index or view uses it, and VARCHAR -> TEXT is binary-compatible in PostgreSQL:
-- a catalogue change, not a table rewrite.
--
-- Rollback is at the bottom of this file.

ALTER TABLE news_events ALTER COLUMN url TYPE TEXT;

COMMENT ON COLUMN news_events.url IS
    'Source link as published. TEXT since 2026-09-30: Google News and percent-encoded '
    'Persian links exceed 500 characters (SP_C_HANDOFF.md section 40).';

-- --------------------------------------------------------------------------
-- Verification
-- --------------------------------------------------------------------------
-- SELECT data_type, character_maximum_length FROM information_schema.columns
--  WHERE table_name = 'news_events' AND column_name = 'url';     -- text, NULL
-- SELECT COUNT(*) FROM news_events;                               -- unchanged

-- --------------------------------------------------------------------------
-- Rollback (fails if any stored link is now longer than 500 characters)
-- --------------------------------------------------------------------------
-- ALTER TABLE news_events ALTER COLUMN url TYPE VARCHAR(500);
