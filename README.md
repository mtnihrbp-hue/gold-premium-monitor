# Gold Premium Monitor

Decision-support monitoring and analytical intelligence for the Iranian 18K physical-gold market. The system combines Iranian platform prices, XAU/USD, USD/IRR, fair value, premium/discount behavior, market structure, momentum, deterministic regime detection, historical memory, structured news, canonical observations, analysis snapshots, retrospective outcome evaluation, evidence packaging, structured interpretation, feature intelligence, an analytical read model, and a downstream consumer contract. It is not an autonomous trading bot.

## Documentation authority

| Source | Responsibility |
|---|---|
| `PROJECT_MEMORY.md` | Canonical architecture and current project state |
| `README.md` | Human-facing overview and repository map |
| `Prompt_Guide.md` | Generic AI engineering behavior |
| `.project_state.json` | Machine-readable continuity state for new sessions |
| `PROJECT_ORCHESTRATION.md` | Cross-system project orchestration protocol |
| `skills/` | Specialist reusable operating rules |
| `sql/neon_schema.sql` | Canonical target database schema |
| `sql/neon_migration_*.sql` | Idempotent migrations for an existing Neon database |
| `kpi/`, `src/`, `tests/`, CI | Executable implementation evidence |

Project-state changes belong in `PROJECT_MEMORY.md` first. `.project_state.json` mirrors current phase and continuity state; it does not create a second architecture authority.

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
├── PRE-SP-C.6 COMPLETE — Evidence Package Foundation
├── PRE-SP-C.7 COMPLETE — Interpretation Intelligence Layer
├── PRE-SP-C.8 COMPLETE — Feature Intelligence Layer
├── PRE-SP-C.9 COMPLETE — Analytical Read Model
└── PRE-SP-C.10 COMPLETE — Read Model Integration & Audit Layer

NEXT
└── PRE-SP-C.11 PLANNING — Analytical Consumer Interface / Read-Model API

SP-C
└── FUTURE — Prediction + Learning
```

## Architecture

```text
MARKET INPUTS
    ↓
VALIDATION
    ↓
CANONICAL OBSERVATION STORAGE
    ↓
DETERMINISTIC ANALYTICAL ENGINE
    ↓
EVIDENCE PACKAGE
    ↓
INTERPRETATION
    ↓
FEATURE INTELLIGENCE
    ↓
ANALYTICAL READ MODEL
    ↓
READ-MODEL CONSUMERS
    ↓
DECISION ENGINE
    ↓
FUTURE PREDICTION / LEARNING
```

The core boundaries are:

```text
FACTS          = raw market observations
EVIDENCE       = validated analytical package
INTERPRETATION = structured explanation
FEATURES       = deterministic model-ready artifacts
READ MODEL     = normalized downstream contract
DECISION       = current deterministic BUY / WAIT / SELL authority
PREDICTION     = future model output only
```

Non-negotiable rules:

```text
CHEAP ≠ BUY
VALUATION ≠ MOMENTUM
CANDIDATE ≠ FINAL DECISION
NEWS ≠ MARKET DATA
LLM ≠ MARKET CALCULATION
EVIDENCE PACKAGE ≠ DECISION
READ MODEL ≠ DECISION AUTHORITY
PREDICTION ≠ FACTS / EVIDENCE / INTERPRETATION / FEATURES
```

External BUY/SELL alerts are controlled only by `final_decision`.

## PRE-SP-C.1 through PRE-SP-C.4

The project has a canonical technical observation series, scheduled analysis snapshots, deterministic technical structure, persisted regime state, and cross-run regime hysteresis.

Representative Iranian fallback remains:

```text
Milli → Ayyareh → WallGold → UNKNOWN
```

Regime states:

```text
NORMAL
FEAR
PANIC
RELIEF
UNKNOWN
```

KPI history:

```text
C.2 14/14
C.3 20/20
C.4 19/19
```

`src/collector/invi.py` is an additional Iranian source normalized into canonical IRR/gram scale. It is not part of the representative-price fallback chain and collector failure remains isolated.

## PRE-SP-C.5 — Outcome Evaluation

C.5 is retrospective measurement infrastructure, not prediction.

Initial horizons:

```text
+1h
+6h
+24h
```

Evaluation uses nearest valid future canonical observations within tolerance, no interpolation, strict future-only selection, explicit `INSUFFICIENT_DATA`, and idempotent snapshot/horizon persistence.

Primary outcome series:

```text
REP_IRAN_GOLD
XAUUSD
USD/IRR
```

KPI: **25/25 passed**.

Persistence:

```text
outcome_evaluations
```

## PRE-SP-C.6 — Evidence Package

C.6 normalizes existing deterministic analytical outputs into an auditable evidence package.

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

Persistence:

```text
analysis_snapshots.evidence_package_json
```

KPI: **25/25 passed**.

C.6 does not implement prediction, autonomous trading, or independent BUY/SELL authority.

## PRE-SP-C.7 — Interpretation Intelligence

C.7 consumes the evidence package and produces structured deterministic interpretation.

It may explain valuation, momentum, technical, regime, news, historical, outcome, conflict, uncertainty, and provenance context.

It does not calculate market facts and does not create BUY/SELL authority.

Persistence:

```text
analysis_snapshots.intelligence_result_json
```

KPI: **25/25 passed**.

## PRE-SP-C.8 — Feature Intelligence

C.8 provides deterministic, explainable, model-ready feature structures without prediction.

Feature families include:

```text
trend
momentum
volatility
regime
market relationships
structure
```

Moving-average artifacts include:

```text
SMA / MA: 7, 15, 30
EMA: 7, 15, 30
price-vs-MA: 7, 15, 30
```

These are produced for representative Iranian gold, XAU/USD, and USD/IRR with explicit insufficient-history handling.

Other features include premium velocity/acceleration, direction persistence, volatility, range expansion, regime reuse, market relationships, divergence, platform spread, consensus, and discount-dominance features.

Persistence:

```text
analysis_snapshots.features_json
```

KPI: **25/25 passed**.

## PRE-SP-C.9 — Analytical Read Model

C.9 combines:

```text
C.6 evidence
    +
C.7 interpretation
    +
C.8 features
    ↓
C.9 analytical read model
```

It exposes normalized sections for:

```text
facts
evidence_summary
interpretation_summary
features_summary
uncertainty
outcome_history
decision (read-only reference)
provenance
```

The read model does not calculate, decide, or predict.

Persistence:

```text
analysis_snapshots.analysis_read_model_json
```

KPI: **23/23 passed**.

## PRE-SP-C.10 — Read Model Integration & Audit

C.10 establishes trustworthy retrieval of a persisted read model by snapshot ID, deterministic completeness classification, historical reconstruction, provenance preservation, and explicit no-current-data / no-future-data leakage guarantees.

Completeness states:

```text
COMPLETE
DEGRADED
INSUFFICIENT_DATA
INVALID
```

The retrieval/audit layer does not recalculate market values, generate decisions, or predict.

KPI: **22/22 passed**.

No C.10 schema change was required. Production Neon remains synchronized through C.9.

## Neon database

Neon PostgreSQL is the long-term historical store.

Repository SQL uses two roles:

```text
sql/neon_schema.sql
    = canonical TARGET schema

sql/neon_migration_*.sql
    = incremental migrations for the EXISTING database
```

Never paste the complete schema into an already-populated production database.

The production database is synchronized through C.9. `analysis_snapshots` contains:

```text
regime_state
technical_state_json
previous_regime
regime_candidate_state
regime_confirmation_count
evidence_package_json
intelligence_result_json
features_json
analysis_read_model_json
```

The corresponding analytical JSONB indexes are present.

## Telegram

Telegram remains the cockpit, not the analytical engine.

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

C.10 does not redesign Telegram. C.11 will establish the stable downstream consumer interface before any presentation expansion.

## Project continuity

New AI sessions must reconstruct project state from the repository in this order:

```text
.project_state.json
→ PROJECT_MEMORY.md
→ README.md
→ Prompt_Guide.md
→ PROJECT_ORCHESTRATION.md
→ skills/
→ relevant source / tests / KPI / SQL
```

Mandatory orchestration flow:

```text
KIMI code
   ↓
GitHub source
   ↓
schema/migration audit
   ↓
Neon production state
   ↓
KPI / smoke
   ↓
documentation
   ↓
.project_state.json
   ↓
commit
```

A phase is only complete when these states are synchronized.

## Verification

For local Windows CMD checks:

```cmd
git pull origin SP-B
python kpi\kpi_pre_sp_cX.py
```

Run prior KPI suites explicitly for regression. Do not rely on `python kpi\kpi_pre_sp_c*.py` shell expansion in Windows CMD.

Current verified evidence:

```text
PRE-SP-C.2  14/14 PASS
PRE-SP-C.3  20/20 PASS
PRE-SP-C.4  19/19 PASS
PRE-SP-C.5  25/25 PASS
PRE-SP-C.6  25/25 PASS
PRE-SP-C.7  25/25 PASS
PRE-SP-C.8  25/25 PASS
PRE-SP-C.9  23/23 PASS
PRE-SP-C.10 22/22 PASS
compileall  PASS
live smoke  PASS
Neon C.7-C.9 reconciliation PASS
```

## PRE-SP-C.11 — Analytical Consumer Interface / Read-Model API

C.11 is the next planned phase.

Objective:

Create a stable downstream application/service interface over the C.10 retrieval contract so future Telegram, API, dashboard, and other consumers can request one authoritative analytical state without rebuilding calculations.

Default database impact:

```text
NONE
```

C.11 is not prediction, ML training, forecasting, autonomous trading, or Telegram redesign.

## Future prediction boundary

No prediction model should start before the bounded intelligence/read-consumer layer is explicit, testable, historically auditable, and empirically evaluable.

The future path remains:

```text
historical observations
→ deterministic features
→ historical outcome labels
→ model training / evaluation
→ prediction output
```

Prediction output must never overwrite historical facts, evidence, interpretation, features, or deterministic decisions.

MIT License
