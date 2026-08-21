# Gold Premium Monitor

Decision-support analytical monitoring for the Iranian 18K physical-gold market. The system combines Iranian platform prices, XAU/USD, USD/IRR, fair value, premium/discount behavior, momentum, market structure, deterministic regime detection, historical memory, structured news, canonical observations, analysis snapshots, retrospective outcome evaluation, evidence packaging, interpretation, and model-ready feature infrastructure.

It is not an autonomous trading bot and does not execute trades.

## Documentation authority

| Source | Responsibility |
|---|---|
| `PROJECT_MEMORY.md` | Canonical architecture, current state, invariants, contracts, roadmap |
| `README.md` | Human-facing overview and repository map |
| `Prompt_Guide.md` | Generic AI engineering behavior |
| `skills/` | Specialist reusable operating rules |
| `sql/neon_schema.sql` | Canonical target database schema |
| `sql/neon_migration_*.sql` | Migrations for an existing Neon database |
| `kpi/`, `src/`, `tests/`, CI | Executable implementation evidence |

Project-state changes belong in `PROJECT_MEMORY.md` first. README is a summary and must not become a competing architecture source.

The former `docs/SP_B_ARCHITECTURE_STATUS.md` duplicated project memory and has been removed.

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
└── PRE-SP-C.8 COMPLETE — Feature Intelligence Layer

CURRENT DIRECTION
└── Bounded intelligence/read models over persisted evidence and features

FUTURE
└── SP-C — Prediction + Learning
```

## Architecture

```text
MARKET INPUTS
    ↓
COLLECTION
    ↓
VALIDATION
    ↓
OBSERVATION STORAGE
    ↓
ANALYTICAL ENGINE
    ↓
EVIDENCE ENGINE
    ↓
INTERPRETATION ENGINE
    ↓
FEATURE FOUNDATION
    ↓
DECISION ENGINE
    ↓
FUTURE PREDICTION / LEARNING
```

The analytical ownership boundary is:

```text
FACTS
(raw observations)
    ↓
EVIDENCE
(validated analytical package)
    ↓
INTERPRETATION
(structured explanation)
    ↓
DECISION
(current deterministic BUY / WAIT / SELL authority)
    ↓
PREDICTION
(future model output only)
```

Prediction is not implemented. Future prediction models must not rewrite facts, evidence, interpretation history, or deterministic decision inputs.

Non-negotiable boundaries:

```text
CHEAP ≠ BUY
VALUATION ≠ MOMENTUM
CANDIDATE ≠ FINAL DECISION
NEWS ≠ MARKET DATA
LLM ≠ MARKET CALCULATION
EVIDENCE PACKAGE ≠ DECISION
PREDICTION ≠ FACTS / EVIDENCE / INTERPRETATION
```

External BUY/SELL alerts are controlled only by `final_decision`. `Candidate: BUY` with `Final: WAIT` must not produce a BUY alert.

## Analytical wings

### Live Wing

Purpose: what is happening now?

```text
/Update
→ collect
→ validate
→ calculate
→ deterministic market state
→ Telegram
```

Telegram is the cockpit, not the analytical engine.

### Analysis Wing

Purpose: what does the system understand about the market at a scheduled point?

```text
scheduled window
→ canonical observations
→ technical structure
→ regime
→ historical/news context
→ Analysis Snapshot
→ Outcome Evaluation
→ Evidence Package
→ Interpretation
→ Feature Layer
→ Neon
```

The Live Wing and Analysis Wing remain separate. Analysis history must not be reconstructed from Telegram output.

## Completed foundations

### PRE-SP-C.1 — Canonical observations

`price_observations` is the canonical technical time-series layer. Technical analysis consumes actual observations rather than premium as a proxy candle.

Conceptual instruments:

```text
XAUUSD
USD/IRR
REP_IRAN_GOLD
PAXG
```

### PRE-SP-C.2 — Snapshot + scheduler

Established:

- `analysis_snapshots`
- deterministic `source_run_id` idempotency
- LIVE vs ANALYSIS separation
- 30-minute `Asia/Tehran` scheduling
- exact-boundary semantics
- final-decision alert authority
- Telegram/email alert guards
- canonical Neon persistence

KPI: **14/14 passed**.

### PRE-SP-C.3 — Price structure + regime

Representative fallback:

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

Regime hysteresis is separate from SP-A decision hysteresis. `CHEAP + PANIC` is valid. Regime never issues BUY/SELL.

KPI: **20/20 passed**.

### PRE-SP-C.4 — Analysis snapshot integration

Persisted regime/technical state includes:

```text
regime_state
technical_state_json
previous_regime
regime_candidate_state
regime_confirmation_count
```

KPI: **19/19 passed**.

The Invi source is normalized into canonical IRR/gram units and is not part of the approved representative fallback chain.

### PRE-SP-C.5 — Outcome evaluation

Measures what actually happened after an analysis snapshot.

Initial horizons:

```text
+1h
+6h
+24h
```

Rules include nearest valid future observation within tolerance, no interpolation, no look-ahead leakage, explicit `INSUFFICIENT_DATA`, and idempotent persistence.

Primary outcome series:

```text
REP_IRAN_GOLD
XAUUSD
USD/IRR
```

KPI: **25/25 passed**.

### PRE-SP-C.6 — Evidence package

Creates deterministic, auditable evidence from computed analytical outputs.

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

Evidence is not a decision.

### PRE-SP-C.7 — Interpretation intelligence

C.7 separates explanation from facts and evidence. It may describe conditions such as discount narrowing, regime persistence, conflicting evidence, and uncertainty while preserving provenance.

It does not calculate market facts, invent levels, override deterministic state, or issue independent BUY/SELL decisions.

KPI: **25/25 passed** as supplied by the completed milestone.

### PRE-SP-C.8 — Feature intelligence

C.8 provides deterministic, explainable, model-ready feature infrastructure without implementing prediction.

Feature families include:

```text
Trend
    SMA / MA
    EMA
    price-vs-moving-average relationships

Momentum
    premium velocity
    premium acceleration
    direction persistence
    divergence / direction change

Volatility
    rolling volatility
    range expansion
    instability

Regime
    existing regime state
    regime duration / transition context

Market relationships
    XAU/USD direction
    USD/IRR pressure
    local/external divergence

Structure
    spread
    platform consensus
    consensus ratio
    discount/structure context
```

C.8 invariants include determinism, no look-ahead, explicit missing/insufficient data, decision separation, schema versioning, persistence roundtrip, data-quality metadata, and reuse of existing regime primitives.

Supplied KPI result:

```text
25/25 passed, 0 failed
PRE-SP-C.8 COMPLETE
```

## Database

Neon PostgreSQL is the long-term historical store.

| Table | Responsibility |
|---|---|
| `market_snapshots` | Existing market observations |
| `platform_prices` | Platform evidence |
| `market_states` | Deterministic interpreted market state |
| `news_events` | Structured external events |
| `price_observations` | Canonical raw technical series |
| `analysis_snapshots` | Scheduled analytical history + regime state + evidence package |
| `outcome_evaluations` | Retrospective +1h/+6h/+24h measurements |

SQL roles are intentionally separate:

```text
sql/neon_schema.sql
    = canonical target schema

sql/neon_migration_*.sql
    = incremental migrations for the existing database
```

Do not use the complete target schema as a replacement migration against a populated database. Any future Neon schema change requires an explicit incremental migration and approval.

Known snapshot persistence includes:

```text
regime_state
technical_state_json
previous_regime
regime_candidate_state
regime_confirmation_count
evidence_package_json JSONB
```

## Telegram

Current cockpit command:

```text
/Update
```

Planned read models:

```text
/Technical
/Analysis
/History
/News
/Radar
/Health
```

Outcome evaluation, evidence packaging, interpretation, and feature infrastructure belong to the Analysis/Intelligence side and are not mixed into `/Update`.

## Prediction policy

Prediction and learning are future components only.

They must not:

- modify raw observations
- rewrite evidence packages
- alter interpretation history
- override deterministic state
- bypass the Decision Engine
- become a hidden calculation layer

No prediction model should start before the bounded intelligence/read-model layer is explicit, testable, historically auditable, and empirically evaluable.

## Validation

```bash
python -m compileall src
pytest -q
python kpi/kpi_pre_sp_c2.py
python kpi/kpi_pre_sp_c3.py
python kpi/kpi_pre_sp_c4.py
python kpi/kpi_pre_sp_c5.py
python kpi/kpi_pre_sp_c6.py
python kpi/kpi_pre_sp_c7.py
python kpi/kpi_pre_sp_c8.py
python src/main.py
```

Never declare a milestone complete without relevant executable evidence.

## Repository map

```text
gold-premium-monitor/
├── .github/
├── config/
├── kpi/
├── skills/
├── sql/
├── src/
├── tests/
├── PROJECT_MEMORY.md
├── Prompt_Guide.md
├── README.md
└── requirements.txt
```

The existing `src/caluclator/` spelling is intentionally preserved for compatibility.

## Current next phase

PRE-SP-C.8 is complete. The next architectural phase is the **bounded intelligence/read-model layer** over persisted evidence and features.

This layer must remain explainable, deterministic where calculation is involved, auditable against historical evidence, and strictly separated from future prediction.

See `PROJECT_MEMORY.md` for the canonical detailed architecture and project state.

MIT License
