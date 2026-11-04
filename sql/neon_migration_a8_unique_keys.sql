-- SP-E0 incremental Neon migration: one unique key on each table of the record (the audit's A8,
-- SP_D_HANDOFF.md sections 51, 68 and 89). Adds five unique constraints; deletes the later copies
-- of news items stored more than once. No column is added or changed; no other table is touched.
--
-- Why. The record's tables had no key but their id, so nothing in the database stopped a reading,
-- an observation, a news item or a phone row from being stored twice: only the code's checks did
-- (repository.spool_writers, get_stored_dedup_keys). The keys are the same ones those checks use,
-- so the database now holds what the code assumes. A write refused by a key fails alone:
--   - save_snapshot, save_price_observation and save_news_event each write in their own session,
--     and an IntegrityError is not "unreachable" (persistence/spool.unreachable), so it is never held;
--   - the spool's flush drops the one refused write and goes on (spool.flush);
--   - the phone sets a refused row aside (class 23, node.py ROW_ERRORS; A9, section 52.4).
--
-- Production, 2026-11-01 (read-only GROUP BY on each key):
--   market_snapshots    1,144 rows   0 repeated
--   platform_prices    11,469 rows   0 repeated
--   price_observations 12,747 rows   0 repeated
--   iran_node_readings 14,205 rows   0 repeated (with detail: one phone run sends several trading
--                                    days of one fund, stamped with the run's time; detail is the day)
--   news_events        11,575 rows   720 keys stored 2 to 39 times, 2,126 later copies, all stored
--                                    from 08-24 to 10-12 by the 24-hour window that get_stored_dedup_keys
--                                    replaced on 10-17 (section 45). The first copy stored is kept: the
--                                    time the item became known.
--
-- NULLS NOT DISTINCT where a NULL is a value: a Daric row has no detail, and a resent one is the
-- same row. Not on news: an item without a dedup key is not deduplicated today, and stays so.
--
-- Run as one transaction, between two scheduled runs. Rollback is at the bottom of this file.

BEGIN;

-- The later copies of a news item, kept outside the database before this runs (section 89).
DELETE FROM news_events n
 USING news_events f
 WHERE n.dedup_key = f.dedup_key
   AND f.id < n.id;

ALTER TABLE market_snapshots ADD CONSTRAINT uq_market_snapshots_reading
    UNIQUE NULLS NOT DISTINCT (timestamp, collection_mode);

ALTER TABLE platform_prices ADD CONSTRAINT uq_platform_prices_snapshot_platform
    UNIQUE NULLS NOT DISTINCT (snapshot_id, platform_name);

ALTER TABLE price_observations ADD CONSTRAINT uq_price_observations_identity
    UNIQUE NULLS NOT DISTINCT (instrument, source, timestamp, quote_side);

ALTER TABLE news_events ADD CONSTRAINT uq_news_events_dedup_key
    UNIQUE (dedup_key);

ALTER TABLE iran_node_readings ADD CONSTRAINT uq_iran_node_readings_identity
    UNIQUE NULLS NOT DISTINCT (node, source, instrument, observed_at, detail);

COMMIT;

-- --------------------------------------------------------------------------
-- Verification
-- --------------------------------------------------------------------------
-- SELECT conrelid::regclass, conname FROM pg_constraint WHERE contype = 'u' AND conname IN
--   ('uq_market_snapshots_reading', 'uq_platform_prices_snapshot_platform', 'uq_price_observations_identity',
--    'uq_news_events_dedup_key', 'uq_iran_node_readings_identity');
--   -- five rows
-- SELECT count(*) FROM news_events;
--   -- the count before, less the later copies deleted
-- SELECT dedup_key FROM news_events GROUP BY 1 HAVING count(*) > 1;
--   -- no rows

-- --------------------------------------------------------------------------
-- Rollback (the keys only; the deleted copies come back from the file kept before the run)
-- --------------------------------------------------------------------------
-- ALTER TABLE market_snapshots DROP CONSTRAINT IF EXISTS uq_market_snapshots_reading;
-- ALTER TABLE platform_prices DROP CONSTRAINT IF EXISTS uq_platform_prices_snapshot_platform;
-- ALTER TABLE price_observations DROP CONSTRAINT IF EXISTS uq_price_observations_identity;
-- ALTER TABLE news_events DROP CONSTRAINT IF EXISTS uq_news_events_dedup_key;
-- ALTER TABLE iran_node_readings DROP CONSTRAINT IF EXISTS uq_iran_node_readings_identity;
