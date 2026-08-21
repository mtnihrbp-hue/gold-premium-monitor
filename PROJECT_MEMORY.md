# Gold Premium Monitor — Project Memory

This file is the **canonical project-specific architecture, implementation state, invariants, contracts, and roadmap** for maintainers and AI implementation agents.

## Documentation authority

| Source | Responsibility |
|---|---|
| `PROJECT_MEMORY.md` | Canonical architecture, implementation state, invariants, contracts, roadmap |
| `README.md` | Human-facing overview and repository map |
| `Prompt_Guide.md` | Generic AI engineering behavior |
| `skills/` | Specialist reusable operating rules |
| `sql/neon_schema.sql` | Canonical target database schema |
| `sql/neon_migration_*.sql` | Migrations for the existing Neon database |
| `src/`, `tests/`, `kpi/`, CI | Executable implementation evidence |

When documentation conflicts, prefer the higher-authority source and then executable behavior as implementation evidence. Project-state changes are recorded here first.

The former `docs/SP_B_ARCHITECTURE_STATUS.md` was consolidated into this file and removed because it duplicated architectural truth.

## 1. Project purpose

Gold Premium Monitor is a decision-support analytical intelligence system for the Iranian 18K physical-gold market. It combines Iranian platform prices, XAU/USD, USD/IRR, local premium/discount analysis, momentum, market structure, deterministic regime detection, historical memory, structured news, canonical observations, scheduled analysis, retrospective outcome evaluation, normalized evidence packaging, structured interpretation, a feature foundation, an analytical read model, and a downstream consumer contract for future intelligence capability.

It is not an autonomous trading bot and does not execute trades.

The long-term architecture is:

```text
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
FEATURE INTELLIGENCE
    ↓
ANALYTICAL READ MODEL
    ↓
READ-MODEL CONSUMERS
    ↓
DECISION ENGINE
    ↓
FUTURE INTELLIGENCE / PREDICTION
```

## 2. Non-negotiable facts/evidence/interpretation/decision/prediction boundary

The analytical contract is:

```text
FACTS
(raw market observations)
        ↓
EVIDENCE
(validated analytical package)
        ↓
INTERPRETATION
(structured explanation layer)
        ↓
FEATURES
(model-ready analytical features)
        ↓
READ MODEL
(normalized downstream contract)
        ↓
DECISION
(current deterministic decision output)
        ↓
FUTURE PREDICTION
(not implemented)
```

The layers have distinct ownership:

```text
Facts          = collected observations
Evidence       = validated analytical package
Interpretation = explanation of evidence
Features       = deterministic model-ready derived artifacts
Read Model     = normalized downstream analytical contract
Decision       = current deterministic BUY / WAIT / SELL authority
Prediction     = future model output only
```

Prediction is not part of the current implementation. When prediction models are introduced, they must never rewrite facts, evidence, interpretation history, feature history, or current deterministic decision inputs.

Non-negotiable invariants:

```text
CHEAP ≠ BUY
VALUATION ≠ MOMENTUM
CANDIDATE DECISION ≠ FINAL DECISION
NEWS ≠ MARKET DATA
LLM ≠ MARKET CALCULATION
EVIDENCE PACKAGE ≠ DECISION
READ MODEL ≠ DECISION AUTHORITY
PREDICTION ≠ FACTS / EVIDENCE / INTERPRETATION / FEATURES
```

Collectors collect. Calculators calculate. Intelligence interprets. Feature builders derive. Read models organize. Presentation formats. Persistence stores. Unknown or insufficient data is preferable to fabricated information.

## 3. Development state — authoritative current position

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

CURRENT DIRECTION
└── PRE-SP-C.11 PLANNING — Analytical Consumer Interface / Read-Model API

FUTURE
└── SP-C — Prediction + Learning
```

`SP-B` is the active development line. It must not be merged into `main` until approved scope, regression, KPI, documentation, Neon state, and diff review are complete.

## 4. Frozen SP-A baseline

```text
Valuation
→ Premium Direction
→ Momentum
→ Market Structure
→ Conflict Matrix
→ Candidate Decision
→ SP-A Hysteresis
→ Final Decision
```

For negative premium:

```text
more negative → DISCOUNT WIDENING
less negative → DISCOUNT NARROWING
stable        → DISCOUNT STABLE
```

Buyer-oriented momentum:

```text
DISCOUNT WIDENING → IMPROVING
DISCOUNT NARROWING → WEAKENING
DISCOUNT STABLE → NEUTRAL
```

Do not replace the explicit conflict matrix with an opaque weighted score without approval.

## 5. Alert authority

`final_decision` is the sole external BUY/SELL authority.

```text
Candidate: BUY
Final: WAIT
    ↓
NO BUY ALERT
```

Legacy threshold evaluation may remain for backward-compatible tests but must not independently trigger external alerts. Telegram and email must preserve this invariant.

## 6. Live Wing

Purpose: what is happening now?

```text
/Update
→ collect
→ validate
→ calculate
→ deterministic market state
→ Telegram
```

The Live Wing is user-triggered, irregular, current, lightweight, and separate from the Analysis Wing's historical pipeline.

Telegram is the cockpit, not the analytical engine.

Current command:

```text
/Update
```

Planned analytical read models remain:

```text
/Technical
/Analysis
/History
/News
/Radar
/Health
```

A duplicated `GOLDPremium:` application header remains a non-blocking presentation defect and is separate from analytical correctness.

## 7. Analysis Wing

Purpose: what does the system understand about the market at a scheduled analytical point?

Scheduler contract:

| Setting | Value |
|---|---|
| Timezone | `Asia/Tehran` |
| Interval | 30 minutes |
| Window | `08:00` inclusive → `21:00` exclusive |
| Active days | configurable |

`get_next_analysis_windows()` treats the reference boundary as already consumed; exact `09:00` therefore yields `09:30` as the next window.

Conceptual flow:

```text
scheduled window
→ source availability / freshness
→ canonical observations
→ technical structure
→ regime
→ historical/news context
→ Analysis Snapshot
→ Outcome Evaluation
→ Evidence Package
→ Interpretation
→ Feature Layer
→ Analytical Read Model
→ Read Model Consumer
→ Neon
```

Future intelligence consumes persisted analytical outputs; it does not replace the deterministic collection, validation, calculation, or storage pipeline.

User count must not multiply scheduled analysis execution.

## 8. PRE-SP-C.1 — Canonical observations COMPLETE

`price_observations` is the canonical technical time-series layer.

Conceptual instruments:

```text
XAUUSD
USD/IRR
REP_IRAN_GOLD
PAXG
```

Technical analysis consumes actual price observations, not premium as a proxy candle. Raw observations remain separate from interpreted states.

## 9. PRE-SP-C.2 — Analysis Snapshot + Scheduler Foundation COMPLETE

Established:

- `analysis_snapshots`
- deterministic `source_run_id` idempotency
- LIVE vs ANALYSIS snapshot distinction
- scheduled analysis windows
- 30-minute `Asia/Tehran` schedule
- exact-boundary next-window semantics
- canonical Neon persistence
- final-decision alert authority
- alert-routing regression coverage

KPI: **14/14 passed**.

## 10. PRE-SP-C.3 — Price Structure + Regime COMPLETE

KPI: **20/20 passed**.

### Representative Iranian price

Fixed fallback:

```text
Milli → Ayyareh → WallGold → UNKNOWN
```

First valid source wins. Selected source is retained as provenance. This layer uses canonical observations and does not average all platforms.

### Support / resistance

```text
price observations
→ local extrema
→ clustering / tolerance
→ deterministic strength metadata
→ support / resistance
```

Insufficient history remains explicit. No fabricated levels.

### Regime

States:

```text
NORMAL
FEAR
PANIC
RELIEF
UNKNOWN
```

Four evidence families:

1. Premium stress
2. Volatility stress
3. USD / market-structure stress
4. External-event stress

Regime hysteresis is distinct from SP-A decision hysteresis. `CHEAP + PANIC` is valid. Regime never issues BUY/SELL.

## 11. PRE-SP-C.4 — Analysis Snapshot Integration COMPLETE

Persisted C.4 state:

```text
regime_state
technical_state_json
previous_regime
regime_candidate_state
regime_confirmation_count
```

Cross-run regime hysteresis is reconstructed from persisted snapshot state. No separate regime table and no file cache are used.

KPI: **19/19 passed**.

### Invi collector

`src/collector/invi.py` is an additional Iranian market source. Its source value is normalized into the monitor's canonical IRR/gram scale before validation.

Collector contract:

```python
{
    "platform": "Invi",
    "price": <canonical IRR/gram numeric value>,
    "status": "OK",
}
```

The source exposes `current_price` in a smaller unit. The collector normalizes it by `×1000` before validation. This is unit normalization, not a market-model adjustment.

Invi is registered in the Iranian platform collector path but is **not** part of the representative-price fallback chain. Collector failure must remain isolated.

## 12. PRE-SP-C.5 — Outcome Evaluation Foundation COMPLETE

C.5 is retrospective measurement infrastructure. It does not predict and does not alter the current decision engine.

Initial horizons:

```text
+1h
+6h
+24h
```

Evaluation flow:

```text
analysis snapshot
    ↓
+1h / +6h / +24h target
    ↓
nearest valid future canonical observation within tolerance
    ↓
movement + direction + actual observation time
    ↓
outcome_evaluations
```

Rules:

- target is anchored to `analysis_timestamp`
- future observation must be strictly after the snapshot timestamp
- no interpolation
- missing target data becomes `INSUFFICIENT_DATA`
- one unavailable series does not invalidate other series
- evaluation is idempotent by snapshot + horizon
- historical backfill is supported
- Invi does not enter representative-price outcome fallback

Primary outcome series:

```text
REP_IRAN_GOLD
XAUUSD
USD/IRR
```

Representative historical fallback remains:

```text
Milli → Ayyareh → WallGold → UNKNOWN
```

KPI: **25/25 passed**.

Persistence:

```text
outcome_evaluations
```

with one row per `(analysis_snapshot_id, horizon_hours)` for the initial horizons `1`, `6`, and `24`.

## 13. PRE-SP-C.6 — Evidence Package Foundation COMPLETE

C.6 creates a deterministic, auditable evidence package from already-computed and persisted analytical outputs.

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

The package has an explicit schema version, deterministic validation, provenance, and explicit missing/unknown handling. It must not contain a BUY/SELL decision as a substitute for the Decision Engine.

Persistence:

```text
analysis_snapshots.evidence_package_json
```

KPI: **25/25 passed**.

C.6 does not implement multi-agent debate, autonomous trading, or prediction.

## 14. PRE-SP-C.7 — Interpretation Intelligence Layer COMPLETE

C.7 adds a structured interpretation layer over the deterministic evidence package.

Interpretation responsibilities include:

- explaining validated evidence
- describing observed conditions such as discount narrowing or regime persistence
- surfacing conflicting evidence
- expressing uncertainty explicitly
- preserving provenance
- keeping facts and evidence unchanged

Interpretation is not a second calculation engine.

It must not:

- rewrite raw observations
- fabricate market facts
- invent technical levels
- replace deterministic regime state
- create independent BUY/SELL authority
- contaminate historical evidence

The decision layer remains separate.

Persistence:

```text
analysis_snapshots.intelligence_result_json
```

KPI: **25/25 passed** as supplied by the completed C.7 implementation milestone.

## 15. PRE-SP-C.8 — Feature Intelligence Layer COMPLETE

C.8 converts historical observations and existing analytical state into deterministic, explainable, model-ready feature structures. It is feature infrastructure, not prediction.

Feature families include:

### Trend

- SMA / MA features
- EMA features
- price-vs-moving-average relationships
- explicit insufficient-history handling

### Momentum

- premium velocity
- premium acceleration
- direction persistence
- direction change / divergence context

### Volatility

- rolling volatility
- range expansion
- instability indicators

### Regime

- reuse of existing regime state
- regime duration / transition context where available

C.8 must reuse C.4 regime primitives rather than create a duplicate regime system.

### Market relationships

- XAU/USD direction
- USD/IRR pressure
- local-gold / external-market divergence

### Structure

- spread
- platform consensus
- consensus ratio
- discount dominance / structure context

C.8 invariants:

- deterministic output
- no look-ahead leakage
- missing data is explicit
- insufficient history is explicit
- feature generation does not issue BUY/WAIT/SELL
- schema version is explicit
- persistence can round-trip the feature package
- data quality is represented explicitly

Persistence:

```text
analysis_snapshots.features_json
```

KPI supplied and accepted:

```text
25/25 passed
```

EMA artifacts are implemented for windows 7, 15, and 30, alongside SMA/MA windows 7, 15, and 30 and price-vs-moving-average distances, for representative Iranian gold, XAU/USD, and USD/IRR.

## 16. PRE-SP-C.9 — Analytical Read Model COMPLETE

C.9 creates a normalized, auditable, presentation-oriented read contract over already-computed C.6 evidence, C.7 interpretation, and C.8 features.

The read model does not calculate, decide, or predict.

Core flow:

```text
C.6 EVIDENCE
     +
C.7 INTERPRETATION
     +
C.8 FEATURES
     ↓
C.9 ANALYTICAL READ MODEL
     ↓
future Telegram / API / UI consumers
```

The model exposes structured sections for:

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

Decision semantics remain read-only:

```text
source = existing_decision_engine
```

C.9 must not create another BUY/WAIT/SELL authority and must not mutate facts, evidence, interpretation, or features.

Persistence:

```text
analysis_snapshots.analysis_read_model_json JSONB
```

KPI: **23/23 passed**.

## 17. PRE-SP-C.10 — Read Model Integration & Audit Layer COMPLETE

C.10 establishes the stable retrieval and historical-audit contract around the persisted C.9 read model.

Core responsibilities:

- retrieve a read model by `analysis_snapshot_id`
- classify completeness deterministically
- preserve provenance
- preserve evidence, interpretation, features, outcomes, and decision context
- reconstruct historical analytical state without current-data leakage
- explicitly preserve `UNKNOWN` and `INSUFFICIENT_DATA`
- keep `final_decision` read-only
- perform no new market calculations
- perform no prediction

Completeness states:

```text
COMPLETE
DEGRADED
INSUFFICIENT_DATA
INVALID
```

Historical reconstruction must use only persisted state associated with the selected snapshot and its outcome evaluations.

KPI:

```text
22/22 passed
```

No C.10 schema change was required. Production Neon remains synchronized through C.9.

## 18. Database and persistence contract

Neon PostgreSQL is the long-term historical store.

| Table | Responsibility |
|---|---|
| `market_snapshots` | Existing market observations |
| `platform_prices` | Platform evidence |
| `market_states` | Deterministic interpreted market state |
| `news_events` | Structured external events |
| `price_observations` | Canonical raw technical time series |
| `analysis_snapshots` | Scheduled analytical history + C.4 state + C.6 evidence + C.7 interpretation + C.8 features + C.9 read model |
| `outcome_evaluations` | Retrospective +1h/+6h/+24h measurements |

Schema authority is split intentionally:

```text
sql/neon_schema.sql
    = complete canonical TARGET schema

sql/neon_migration_*.sql
    = idempotent migrations for the EXISTING Neon database
```

Never use the complete target schema as a replacement migration against an already-populated Neon database.

Persisted `analysis_snapshots` analytical fields are now:

```text
regime_state
technical_state_json
previous_regime
regime_candidate_state
regime_confirmation_count
evidence_package_json JSONB
intelligence_result_json JSONB
features_json JSONB
analysis_read_model_json JSONB
```

Corresponding JSONB indexes are present for the four persisted analytical packages.

Production Neon was reconciled from its C.6 state through C.7, C.8, and C.9 with a temporary-branch migration test before production application. Post-migration verification confirmed the four persisted analytical JSONB fields and their indexes.

C.5 uniqueness:

```text
uq_outcome_eval_snapshot_horizon
```

Analysis snapshot uniqueness:

```text
uq_analysis_snapshots_source_run_id
```

Snapshot type constraint:

```text
snapshot_type IN ('analysis', 'live')
```

Database failure must degrade gracefully and must not become a hidden calculation layer.

Any future schema change requires an explicit incremental migration, temporary-branch verification, production application, and documentation/state synchronization.

## 19. Historical and news intelligence

SP-B.1 is descriptive historical context only.

SP-B.2 is structured external-news context only.

Neither independently calculates fair price, premium, technical indicators, or BUY/SELL.

## 20. LLM boundary

LLM may summarize and interpret structured context.

LLM must not:

- calculate fair price
- calculate premium
- calculate indicators
- invent technical levels
- invent historical statistics
- override deterministic state
- independently issue BUY/SELL

The deterministic C.6 evidence package, C.8 feature layer, C.9 read model, and C.10 retrieval/audit contract are upstream contracts for future intelligence use. They are not LLM-controlled calculation layers.

## 21. Read-model consumer boundary

C.9 defines the persisted analytical read object.

C.10 defines trustworthy retrieval and historical audit of that object.

The next consumer phase must not duplicate analytical calculation.

Correct ownership is:

```text
FACTS
    ↓
EVIDENCE
    ↓
INTERPRETATION
    ↓
FEATURES
    ↓
READ MODEL
    ↓
READ-MODEL CONSUMER
    ↓
DECISION AUTHORITY
```

The persisted read model is not Telegram markup and is not an independent decision engine.

## 22. Documentation governance

`PROJECT_MEMORY.md` is the single source of truth for project-specific architecture and state.

Rules:

1. Update `PROJECT_MEMORY.md` for every architecture/state milestone.
2. Update `README.md` when the human-facing system map or current phase changes.
3. Update `Prompt_Guide.md` only when generic AI engineering behavior changes.
4. Update a specialist skill only when reusable operating behavior changes.
5. Do not create duplicate sprint-status documents that compete with project memory.
6. Do not create redundant `docs/` architecture summaries when the same truth belongs in project memory.
7. Keep SQL schema and migration documentation aligned with the intended Neon state.
8. Keep `.project_state.json` synchronized with current phase, KPI, Neon state, next phase, and completion state.
9. Executable evidence outranks prose when verifying implementation.
10. Historical project context may be preserved in git history; active documentation must describe the current architecture.

The `docs/` architecture-status file was consolidated into `PROJECT_MEMORY.md` and removed.

## 23. Project continuity protocol

A new AI engineering session must reconstruct project state from the repository, not conversation memory.

Required read order:

```text
.project_state.json
    ↓
PROJECT_MEMORY.md
    ↓
README.md
    ↓
Prompt_Guide.md
    ↓
PROJECT_ORCHESTRATION.md
    ↓
skills/
    ↓
relevant source / tests / KPI / SQL
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

A phase is not COMPLETE while any one of these remains inconsistent.

## 24. Verification standard

Every implementation change follows:

```text
inspect
→ define change surface
→ implement minimally
→ targeted test
→ regression
→ KPI
→ smoke test
→ database verification
→ diff review
→ documentation sync
→ continuity-state sync
→ branch review
```

For local KPI checks on Windows CMD:

```cmd
git pull origin SP-B
python kpi\kpi_pre_sp_cX.py
```

Run regression KPI files explicitly rather than relying on `python kpi\kpi_pre_sp_c*.py` shell expansion.

Current verified / supplied evidence:

```text
PRE-SP-C.2 KPI  14/14 PASS
PRE-SP-C.3 KPI  20/20 PASS
PRE-SP-C.4 KPI  19/19 PASS
PRE-SP-C.5 KPI  25/25 PASS
PRE-SP-C.6 KPI  25/25 PASS
PRE-SP-C.7 KPI  25/25 PASS
PRE-SP-C.8 KPI  25/25 PASS
PRE-SP-C.9 KPI  23/23 PASS
PRE-SP-C.10 KPI 22/22 PASS
compileall       PASS
live smoke       PASS
Neon C.7-C.9 reconciliation PASS
```

The latest C.10 KPI result was supplied from local execution and passed 22/22 tests.

## 25. SP-B closure direction

Original SP-B.3/B.4/B.5 names are architectural placeholders, not mandatory module boundaries.

Current role mapping:

| Original | Current role |
|---|---|
| SP-B.3 | Analysis Wing / bounded interpretation |
| SP-B.4 | Telegram analytical read models |
| SP-B.5 | Combined read model over persisted analysis snapshots, evidence, interpretation, features, outcomes, and decision context |

Do not create duplicate agent/radar layers solely to preserve old sprint names.

## 26. PRE-SP-C.11 — Analytical Consumer Interface / Read-Model API — PLANNING

C.11 is the next planned phase.

Objective:

Create a stable downstream consumer interface over the C.10 retrieval/audit contract so future Telegram, API, dashboard, and other consumers can consume one analytical state without rebuilding calculations.

C.11 must remain downstream of:

```text
C.6 evidence
→ C.7 interpretation
→ C.8 features
→ C.9 read model
→ C.10 retrieval/audit
```

C.11 must not:

- recalculate market facts
- recreate evidence
- recreate interpretation
- recreate features
- create a new BUY/WAIT/SELL authority
- introduce prediction
- introduce ML training
- redesign Telegram presentation
- add a database table without an explicit demonstrated requirement

Default database impact:

```text
NONE
```

The preferred initial implementation is an application/service contract that exposes the validated C.10 read model. Persistence changes require separate schema audit and approval.

The next implementation handoff must begin with inspection and produce an exact change-surface report before coding.

## 27. Future prediction boundary

No prediction model should start before the bounded intelligence/read-consumer architecture is explicit, testable, historically auditable, and empirically evaluable.

The future learning path remains:

```text
historical observations
→ deterministic features
→ historical outcome labels
→ model training / evaluation
→ prediction output
```

Prediction output will be an additional downstream layer and must never overwrite historical facts, evidence, interpretation, features, or decisions.
