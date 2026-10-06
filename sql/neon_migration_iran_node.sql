-- SP-D incremental Neon migration: the Iran-side node's readings (SP_D_HANDOFF.md section 30).
-- Adds one table and one index. No existing table is touched.
--
-- Why. Daric refuses GitHub's runner (403 since 2026-10-03) and Cloudflare's addresses; TSETMC
-- and fipiran time out from abroad. From an Iranian connection they answer. The owner's phone
-- (Samsung S10, Termux) reads them from Iran and writes each reading here over Neon's HTTPS
-- endpoint; production reads them from this table. Daric first: it is most of the PAPER room's
-- edge (SP_D_HANDOFF.md section 28).
--
-- The phone logs in as its own role, iran_node, and may only INSERT into this table: it cannot
-- read or change anything else, so a lost phone exposes nothing. Create the role with SQL, as
-- below, NEVER through Neon's API or console: those roles join neon_superuser, which holds
-- pg_read_all_data and pg_write_all_data (verified on temp-iran-node-test, 2026-10-06).
--
-- Rollback is at the bottom of this file.

CREATE TABLE IF NOT EXISTS iran_node_readings (
    id           BIGSERIAL PRIMARY KEY,
    node         VARCHAR(20)   NOT NULL,          -- which device, e.g. 's10'
    source       VARCHAR(20)   NOT NULL,          -- 'daric'; later 'tsetmc', 'fipiran'
    instrument   VARCHAR(40)   NOT NULL,          -- 'DARIC_18K'
    observed_at  TIMESTAMP     NOT NULL,          -- UTC, when the node read it
    bid          NUMERIC(20,2),                   -- rial; what a seller is paid
    ask          NUMERIC(20,2),                   -- rial; what a buyer pays
    value        NUMERIC(20,4),                   -- a single-valued reading (an index, a NAV)
    status       VARCHAR(10)   NOT NULL,          -- OK or ERROR
    detail       TEXT,                            -- the error, or a short note
    payload      JSONB,                           -- the source's own answer, for audit
    received_at  TIMESTAMP     NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS ix_iran_node_readings_lookup
    ON iran_node_readings (source, instrument, observed_at DESC);

-- --------------------------------------------------------------------------
-- The node's role (SQL only; the password: 32 random characters, given to the phone alone)
-- --------------------------------------------------------------------------
-- CREATE ROLE iran_node WITH LOGIN PASSWORD '<generated>';
-- GRANT USAGE ON SCHEMA public TO iran_node;
-- GRANT INSERT ON iran_node_readings TO iran_node;
-- GRANT USAGE ON SEQUENCE iran_node_readings_id_seq TO iran_node;
--
-- Nothing else is granted: no SELECT anywhere, so the node cannot read even its own rows.

-- --------------------------------------------------------------------------
-- Verification
-- --------------------------------------------------------------------------
-- SELECT column_name, data_type FROM information_schema.columns
--   WHERE table_name = 'iran_node_readings' ORDER BY ordinal_position;   -- 12 columns
-- SELECT grantee, privilege_type FROM information_schema.role_table_grants
--   WHERE table_name = 'iran_node_readings' AND grantee = 'iran_node';    -- INSERT only

-- --------------------------------------------------------------------------
-- Rollback
-- --------------------------------------------------------------------------
-- DROP TABLE IF EXISTS iran_node_readings;
-- DROP ROLE IF EXISTS iran_node;
--
-- Tested 2026-10-06 on temp-iran-node-test (copied from production, since deleted): from an
-- Iranian connection node.py read Daric and inserted two rows through the HTTPS endpoint in
-- about two seconds; the role was refused SELECT on market_snapshots and on this table, and
-- DELETE on this table.
