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

- `market_snapshots` — market observations used by the existing monitor
- `platform_prices` — platform-level market evidence
- `market_states` — deterministic interpreted state
- `news_events` — structured external events
- `price_observations` — canonical raw time-series observations
- `analysis_snapshots` — system-generated analytical snapshots

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

Always expose sample size before interpreting historical evidence.

Prefer:

```text
sample size
→ observed outcome
→ uncertainty
```

over opaque confidence numbers.
