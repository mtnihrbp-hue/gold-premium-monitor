# Data and Neon Skill

## Purpose

Preserve the project's historical memory and data-quality discipline.

## Database authority

Neon PostgreSQL is the production historical store for the monitor.

The canonical repository schema is:

```text
sql/neon_schema.sql
```

When database structure changes, update the repository schema file as part of the same approved change and keep the Neon database synchronized.

A change to the live database goes through `sql/neon_migration_*.sql`, verified on a temporary Neon
branch, applied only with the owner's authorization. Never apply the target schema to production
(`PROJECT_MEMORY.md` section 7).

## Data layers

Keep these separate:

```text
raw market observations
        ≠
interpreted market states
        ≠
analysis snapshots
        ≠
future prediction/outcome records
```

### Current core tables

- `market_snapshots` — each reading: fair value, the stored premium, the decision; `collection_mode`
  separates scheduled from user readings
- `platform_prices` — the platforms' prices of each reading
- `market_states` — the decision chain's states and `valuation_context_json`
- `price_observations` — the canonical time series; BUY and SELL rows for the two-sided platforms
- `news_events` — structured external events
- `analysis_snapshots`, `outcome_evaluations` — the scheduled analysis and its +1h/+6h/+24h outcomes
- `market_daily_candles` — daily series from tgju, tablokhani, etfbaz, never mixed with platform prices
- `direction_snapshots` — the Direction panels
- `paper_accounts`, `paper_activity` — PAPER
- `iran_node_readings` — what the owner's phone reads (Daric, TSETMC)

Raw observations must remain queryable. Interpreted states must remain queryable. Future evaluation records should link back to the analysis snapshot that generated the hypothesis.

## PRE-SP-C observation rules

Canonical instruments include:

- `XAUUSD`
- `USD/IRR`
- `REP_IRAN_GOLD`
- `PAXG` when a reliable collector exists

Irregular user-triggered `/Update` calls must not become the canonical technical time series.

## Data quality

Unknown is better than fabricated.

Use explicit states such as:

- `UNKNOWN`
- `INSUFFICIENT_DATA`
- `DEGRADED`

Do not turn missing values into zero unless zero is semantically valid.

## The transfer cap

Neon's free plan allows **5 GB of outbound transfer a month**. Going over it suspended production
from 2026-10-13 to the month's end (`SP_D_HANDOFF.md` section 34). Every read spends it.
- Load only the columns used: `get_analysis_snapshots(columns=...)`. `kpi_coherence.test_36` fails if a
  reader names a snapshot document.
- Read daily candles through `persistence/candle_cache.py`, never the whole history each run.
- Watch the month-to-date figure in the health check (`PROJECT_OPERATIONS.md` 15).
- Before adding a reader, estimate its bytes per run × 16 runs a day × 30.

## Outages

While Neon is out of reach, what a run cannot write waits in the spool (`persistence/spool.py`,
`record_spool.jsonl` in the Actions cache). Each scheduled run flushes it first, re-checking held
readings against the stale-quote rules before writing (`SP_D_HANDOFF.md` 35.4, 37.1). The phone keeps a
spool of its own.

The phone writes as the role `iran_node`, INSERT only, made with SQL, never through Neon's API or
console, whose roles join `neon_superuser`.

## Where the data comes from

What a platform's `price` means differs by platform: a buyer's price, a mid, an unknown side, or a
gallery's reference (`PROJECT_MEMORY.md` section 5). Know which before comparing two.

Some sources serve GitHub's non-Iranian runner a stale copy while Iran sees the live price. Check a
source from the runner's side, not from Iran (lesson 18).

## External failures

Neon failure must not crash the core market monitor.

Collectors may fail independently. Optional intelligence may become `UNKNOWN` while quantitative monitoring continues.

## Numeric integrity

Do not allow an LLM to invent:

- USD/IRR
- XAU/USD
- fair price
- premium
- platform prices
- support/resistance
- historical returns

These belong to deterministic code and stored data.

## Historical analysis

Always expose sample size before interpreting historical evidence. Count independent episodes, not
overlapping days: neighbouring hourly readings share most of the same 24 hours (`SP_D_HANDOFF.md`
35.10, 36.2).

Prefer:

```text
sample size
→ observed outcome
→ uncertainty
```

over opaque confidence numbers.
