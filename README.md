# Gold Premium Monitor

Decision-support monitoring for the Iranian 18K physical-gold market. The system combines XAU/USD, USD/IRR, Iranian platform prices, fair value, premium/discount behavior, historical memory, structured news, canonical observations, technical structure, deterministic market regime, analysis snapshots, retrospective outcome evaluation, and a normalized evidence package. It is not an autonomous trading bot.

## Documentation authority

| Source | Responsibility |
|---|---|
| `PROJECT_MEMORY.md` | Canonical architecture and current project state |
| `README.md` | Human-facing overview and repository map |
| `Prompt_Guide.md` | Generic AI engineering behavior |
| `skills/` | Specialist reusable operating rules |
| `sql/neon_schema.sql` | Canonical target database schema |
| `sql/neon_migration_*.sql` | Idempotent migrations for an existing Neon database |
| `kpi/`, `src/`, `tests/`, CI | Executable implementation evidence |

Project-state changes belong in `PROJECT_MEMORY.md` first. README summarizes; it does not create an alternate architecture.

## Current development position

```text
main
└── SP-A COMPLETE / FROZEN

SP-B
├── SP-B.1 COMPLETE — Historical Intelligence
├── SP-B.2 COMPLETE — News Intelligence
├── PRE-SP-C.1 COMPLETE — Canonical Time Series
├── PRE-SP-C.2 COMPLETE — Analysis Snapshot + Scheduler Foundation
├── PRE-SP-C.3 COMPLETE — Price Structure + Regime
├── PRE-SP-C.4 COMPLETE — Analysis Snapshot Integration
├── PRE-SP-C.5 COMPLETE — Outcome Evaluation Foundation
└── PRE-SP-C.6 COMPLETE — Evidence Package + Market Intelligence Foundation

NEXT
└── Bounded Market Intelligence / interpretation layer

SP-C
└── FUTURE — Prediction + Learning
```

## Architecture

```text
MARKET INPUTS
    ↓
Quantitative Engine
    ↓
Valuation / Momentum / Market Structure
    ↓
Conflict Matrix
    ↓
Candidate Decision
    ↓
SP-A Hysteresis
    ↓
Final Decision

Live Wing (/Update)
    → current deterministic market state
    → Telegram

Analysis Wing (scheduled)
    → canonical observations
    → technical structure
    → regime
    → historical/news context
    → Analysis Snapshot
    → Outcome Evaluation
    → Evidence Package
    → Neon

Future Intelligence Layer
    → structured interpretation
    → bounded intelligence/read models
```

Non-negotiable boundaries:

```text
CHEAP ≠ BUY
VALUATION ≠ MOMENTUM
CANDIDATE ≠ FINAL DECISION
NEWS ≠ MARKET DATA
LLM ≠ MARKET CALCULATION
EVIDENCE PACKAGE ≠ DECISION
```

External BUY/SELL alerts are controlled only by `final_decision`. `Candidate: BUY` with `Final: WAIT` must not produce a BUY alert.

## PRE-SP-C.1 — canonical observations

`price_observations` is the canonical technical time-series layer. Technical analysis consumes actual price observations, not premium as a proxy candle.

Supported conceptual instruments include:

```text
XAUUSD
USD/IRR
REP_IRAN_GOLD
PAXG
```

## PRE-SP-C.2 — snapshot foundation

Established:

- `analysis_snapshots`
- deterministic `source_run_id` idempotency
- live-vs-analysis separation
- 30-minute `Asia/Tehran` scheduler
- exact-boundary next-window semantics
- final-decision alert authority
- Telegram/email alert guards
- canonical Neon schema

KPI: **14/14 passed**.

## PRE-SP-C.3 — Price Structure + Regime

KPI: **20/20 passed**.

Representative Iranian fallback:

```text
Milli → Ayyareh → WallGold → UNKNOWN
```

Support/resistance uses local extrema, clustering/tolerance, and deterministic strength metadata. Insufficient history remains explicit.

Regime states:

```text
NORMAL
FEAR
PANIC
RELIEF
UNKNOWN
```

Evidence families:

1. Premium stress
2. Volatility stress
3. USD / market-structure stress
4. External-event stress

Regime hysteresis is separate from SP-A decision hysteresis. `CHEAP + PANIC` is valid. Regime never issues BUY/SELL.

## PRE-SP-C.4 — Analysis Snapshot Integration

C.4 integrates the C.3 primitives into persisted `analysis_snapshots`.

Persisted C.4 fields:

```text
regime_state
technical_state_json
previous_regime
regime_candidate_state
regime_confirmation_count
```

The regime transition state is persisted so hysteresis survives independent scheduled processes.

KPI: **19/19 passed**.

### Invi collector

`src/collector/invi.py` is an additional Iranian market source. Its source value is normalized into the monitor's canonical IRR/gram scale before validation.

It is registered in the main platform collector path but is **not** part of the approved representative-price fallback chain. If its source value is invalid, the collector is isolated and the remaining market sources continue.

## PRE-SP-C.5 — Outcome Evaluation Foundation

C.5 measures what actually happened after a persisted analysis snapshot. It is retrospective evaluation infrastructure, not prediction.

Initial horizons:

```text
+1h
+6h
+24h
```

The evaluator uses:

- wall-clock target times
- nearest valid future canonical observations within tolerance
- explicit `INSUFFICIENT_DATA`
- no interpolation
- no look-ahead leakage
- idempotent `(analysis_snapshot_id, horizon_hours)` persistence
- historical backfill support

The primary outcome series are:

```text
REP_IRAN_GOLD
XAUUSD
USD/IRR
```

Representative historical fallback remains:

```text
Milli → Ayyareh → WallGold → UNKNOWN
```

Invi is not added to that fallback chain.

C.5 KPI: **25/25 passed**.

## PRE-SP-C.6 — Evidence Package + Market Intelligence Foundation

C.6 is complete.

Its purpose is to normalize already-computed deterministic outputs into a structured, auditable evidence package for a future intelligence layer.

Core flow:

```text
canonical facts
    ↓
validated analytical outputs
    ↓
normalized evidence package
    ↓
future intelligence interpretation
    ↓
decision engine
```

Evidence families include:

```text
valuation
momentum
technical_structure
regime
xau_usd
usd_irr
representative_gold
platform_structure
news_context
historical_context
outcome_context
data_quality
provenance
```

The evidence package has an explicit schema version, deterministic validation, provenance, and explicit missing/unknown handling. It must not contain a BUY/SELL decision as a substitute for the Decision Engine.

Persistence:

```text
analysis_snapshots.evidence_package_json
```

KPI: **25/25 passed**.

C.6 does not implement bounded LLM interpretation, multi-agent debate, prediction, machine learning, or autonomous trading.

## Neon database

The repository intentionally separates two SQL roles:

```text
sql/neon_schema.sql
    = complete canonical TARGET schema

sql/neon_migration_*.sql
    = safe/idempotent migrations for the EXISTING Neon database
```

Do not use the complete schema file as a migration against a populated database. For the active database, run only the appropriate incremental migration and verify its result.

Core persistence responsibilities:

| Table | Responsibility |
|---|---|
| `market_snapshots` | Existing market observations |
| `platform_prices` | Platform evidence |
| `market_states` | Deterministic interpreted market state |
| `news_events` | Structured external events |
| `price_observations` | Canonical raw technical series |
| `analysis_snapshots` | Scheduled analytical history + C.4 state + C.6 evidence package |
| `outcome_evaluations` | Retrospective +1h/+6h/+24h measurement |

Database failure should degrade gracefully and never become a hidden calculation layer.

## Telegram

Telegram is the cockpit, not the analytical engine.

Current command:

```text
/Update
```

Planned analytical read models:

```text
/Technical
/Analysis
/History
/News
/Radar
/Health
```

A duplicated `GOLDPremium:` application header remains a known presentation defect and is separate from analytical correctness.

C.5/C.6 do not change `/Update`: outcome evaluation and evidence packaging belong to the Analysis Wing and are not mixed into live user-triggered reporting.

## Validation

```bash
python -m compileall src
pytest -q
python kpi/kpi_pre_sp_c2.py
python kpi/kpi_pre_sp_c3.py
python kpi/kpi_pre_sp_c4.py
python kpi/kpi_pre_sp_c5.py
python kpi/kpi_pre_sp_c6.py
python src/main.py
```

Never declare a sprint complete without the relevant evidence.

## Repository map

```text
gold-premium-monitor/
├── config/
├── kpi/
├── skills/
├── sql/
├── src/
├── tests/
├── PROJECT_MEMORY.md
├── Prompt_Guide.md
└── README.md
```

The existing `src/caluclator/` spelling is intentionally preserved for compatibility.

## Next phase

The next architecture step is the **bounded Market Intelligence / interpretation layer**.

It consumes the persisted evidence package and may use an LLM for structured contextual interpretation, but it must not:

- calculate market facts
- invent technical levels
- override deterministic states
- create an independent BUY/SELL authority
- replace the Decision Engine

The later SP-C prediction/learning layer comes only after this intelligence/read-model foundation is verified.

MIT License
