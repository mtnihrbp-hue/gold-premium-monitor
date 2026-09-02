[PROJECT_MEMORY.md](https://github.com/user-attachments/files/31727259/PROJECT_MEMORY.md)
# Gold Premium Monitor — Project Memory

This file is the **canonical project-specific architecture, implementation state, invariants, contracts, and roadmap** for maintainers and AI implementation agents.

---

## 1. Documentation Authority

| Source | Responsibility |
|---|---|
| `PROJECT_MEMORY.md` | Canonical project architecture, implementation state, invariants, contracts, and roadmap |
| `MASTER_PLAN_STATUS.md` | Human-readable master-plan status and milestone state |
| `DOCUMENTATION_INDEX.md` | Documentation map and current implementation references |
| `README.md` | Human-facing overview and repository map |
| `Prompt_Guide.md` | Generic AI engineering behavior |
| `skills/` | Specialist reusable operating rules |
| `sql/neon_schema.sql` | Canonical target database schema |
| `sql/neon_migration_*.sql` | Incremental migrations for the existing Neon database |
| `src/`, `tests/`, `kpi/`, CI | Executable implementation evidence |

When documentation conflicts, prefer the higher-authority source and then executable behavior as implementation evidence.

Project-state changes must be synchronized here and in the appropriate continuity/state documentation.

The former duplicated architecture-status document was consolidated into project memory and must not be recreated without an explicit architectural reason.

---

# 2. Project Purpose

Gold Premium Monitor is a decision-support analytical intelligence system for the Iranian 18K physical-gold market.

It combines:

- Iranian gold-platform prices
- XAU/USD
- USD/IRR
- fair-price calculation
- premium / discount (`Bubble`)
- momentum and market dynamics
- market structure
- deterministic regime detection
- historical market memory
- structured news
- canonical time-series observations
- scheduled analysis
- retrospective outcome evaluation
- normalized evidence
- structured interpretation
- deterministic model-ready features
- an analytical read model
- downstream consumers
- current deterministic decision authority
- future prediction / expert intelligence

It is **not an autonomous trading bot** and does not execute trades.

Long-term architecture:

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

---

# 3. Core Architectural Boundaries

The project distinguishes facts, evidence, interpretation, features, read models, decisions, and future prediction.

```text
FACTS
raw observations
    ↓
EVIDENCE
validated analytical package
    ↓
INTERPRETATION
structured explanation
    ↓
FEATURES
deterministic model-ready artifacts
    ↓
READ MODEL
normalized downstream contract
    ↓
DECISION
current deterministic authority
    ↓
FUTURE PREDICTION
future intelligence only
```

Ownership:

```text
Facts          = collected observations
Evidence       = validated analytical package
Interpretation = explanation of evidence
Features       = deterministic derived artifacts
Read Model     = normalized downstream analytical contract
Decision       = current deterministic BUY / WAIT / SELL authority
Prediction     = future model output only
```

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

Collectors collect.

Calculators calculate.

Intelligence interprets.

Feature builders derive.

Read models organize.

Presentation formats.

Persistence stores.

Unknown and insufficient data are valid states and are preferable to fabricated information.

---

# 4. Current Project State

Current authoritative state:

```text
MAIN
└── SP-A COMPLETE / FROZEN

SP-B
├── Historical Intelligence COMPLETE
├── News Intelligence COMPLETE
├── PRE-SP-C.1 Canonical Time Series COMPLETE
├── PRE-SP-C.2 Analysis Snapshot + Scheduler Foundation COMPLETE
├── PRE-SP-C.3 Price Structure + Regime COMPLETE
├── PRE-SP-C.4 Analysis Snapshot Integration COMPLETE
├── PRE-SP-C.5 Outcome Evaluation Foundation COMPLETE
├── PRE-SP-C.6 Evidence Package Foundation COMPLETE
├── PRE-SP-C.7 Interpretation Intelligence Layer COMPLETE
├── PRE-SP-C.8 Feature Intelligence Layer COMPLETE
├── PRE-SP-C.9 Analytical Read Model COMPLETE
└── PRE-SP-C.10 Read Model Integration & Audit Layer COMPLETE

C14C
└── COMPLETE — 21/21 KPI PASS

UPDATE v1
└── OPERATIONAL — lightweight user-triggered live update

ANALYSIS WING
└── Scheduled collection / analysis foundation established;
    full analytical consumer evolution continues separately.

CURRENT DIRECTION
└── Post-C14 research, calibration, empirical evidence accumulation,
    and architecture planning before the next major implementation sprint.

FUTURE
└── Expert Judgment / Prediction capability
```

### C14C status

```text
C14C = COMPLETE
KPI = 21/21 PASS
ARCHITECTURE BOUNDARY = PRESERVED
NEON MIGRATION = NOT REQUIRED
```

C14C is part of the analytical foundation. It does not introduce:

- reinforcement learning
- online model learning
- automatic model-weight changes
- autonomous LLM authority
- autonomous BUY/SELL authority

---

# 5. SP-A — Frozen Decision Baseline

The deterministic SP-A pipeline remains:

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

Do not replace the explicit conflict matrix with an opaque weighted score without explicit approval.

---

# 6. Decision and Alert Authority

`final_decision` is the sole external BUY/SELL authority.

```text
Candidate: BUY
Final: WAIT
    ↓
NO BUY ALERT
```

Legacy threshold evaluation may remain for backward-compatible tests, but it must not independently trigger external alerts.

Telegram and email must preserve this invariant.

The system remains decision-support, not execution.

---

# 7. System Wings

The project has two major operational wings.

## 7.1 Live / UPDATE Wing

Purpose:

> What is happening now?

Current user-triggered flow:

```text
/Update
    ↓
collect current market data
    ↓
validate
    ↓
perform minimum required calculations
    ↓
resolve canonical RUN / DAY baselines
    ↓
produce deterministic current market state
    ↓
Telegram presentation
```

UPDATE is:

- user-triggered
- irregular
- current
- lightweight
- presentation-oriented
- dependent on authoritative persisted data where required

UPDATE must **not** execute the complete scheduled Analysis pipeline merely to answer a user request.

Current UPDATE boundary:

```text
MARKET
PRICE & BUBBLE DYNAMICS
MARKET STRUCTURE
PLATFORMS
CURRENT DECISION
```

The current decision section may remain in UPDATE while the downstream analytical architecture evolves.

### UPDATE baseline semantics

**RUN**

```text
current observation
vs
latest previous canonical market snapshot
```

RUN is not a comparison against arbitrary previous user calls.

**DAY**

```text
current observation
vs
first controlled canonical market snapshot of today
```

During the transition period, DAY uses the first canonical `market_snapshots` record of the day.

When the Analysis Wing is fully operational, DAY may migrate to the first controlled Analysis-Wing collection of the day.

Do not use accumulated user-triggered UPDATE calls as the DAY baseline.

---

# 8. UPDATE v1 — Current Analytical Semantics

UPDATE v1 provides a compact current-state interpretation without pretending that empirical calibration already exists.

## Price direction

Price direction is independent of bubble movement.

Possible states:

```text
RISING
FALLING
STABLE
UNKNOWN
```

## Price pace

Pace is intended to answer:

> Is the market moving sharply or not sharply?

Preferred semantic vocabulary:

```text
SHARP
NOT SHARP
STABLE
N/A
```

Do not introduce "slope" as the user-facing concept.

Where insufficient calibrated history exists:

```text
Pace = N/A
```

This is intentional.

## Acceleration

Acceleration describes change in movement behavior and must be based on a valid chronological representative series.

Do not derive acceleration from the latest arbitrary raw platform rows because multiple platform observations may belong to the same collection run.

Preferred basis:

```text
canonical market snapshots
→ representative local-price series
→ chronological acceleration
```

## Bubble

Persian `حباب` is represented as:

```text
Bubble
```

Conceptually:

```text
positive bubble → market above fair price
negative bubble → market below fair price
```

Bubble movement is based on distance from fair value, not simply the direction of market price.

```text
distance from fair increasing → INCREASING
distance from fair decreasing → DECREASING
distance from fair materially unchanged → STABLE
```

Current deadband is a convention and is not yet empirically calibrated.

## Bubble pace

Bubble pace requires enough valid chronological history.

Until calibration is established:

```text
Bubble Pace = N/A
```

Do not fabricate a classification.

## Candle

User-facing candle classification is intentionally simplified:

```text
BULLISH
BEARISH
NEUTRAL
```

It must remain deterministic and must not become a second decision engine.

---

# 9. UPDATE Interpretation Boundary

Price direction and bubble movement are independent dimensions.

Example:

```text
Local price = RISING
Bubble = NEGATIVE
Bubble movement = INCREASING
```

This is a valid state.

It means local price is rising while the market is moving farther below fair value.

The system may describe the observed relationship, but must not automatically convert it into psychological claims such as:

```text
platforms are sleeping
market expects gold to rise
buyers are waiting
```

unless such interpretation is explicitly supported by a later evidence/interpretation layer.

Current deterministic interpretation should remain observational.

---

# 10. Analysis Wing

Purpose:

> What does the system understand about the market at a scheduled analytical point?

Scheduler contract:

| Setting | Value |
|---|---|
| Timezone | `Asia/Tehran` |
| Interval | 30 minutes |
| Window | `08:00` inclusive → `21:00` exclusive |
| Active days | configurable |

Exact-boundary behavior:

```text
reference boundary already consumed
09:00 → next window = 09:30
```

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
→ downstream consumer
→ Neon
```

User count must not multiply scheduled analysis execution.

The Analysis Wing is the long-term source of controlled historical analytical evidence.

---

# 11. Canonical Time Series

`price_observations` is the canonical technical time-series layer.

Conceptual instruments:

```text
XAUUSD
USD/IRR
REP_IRAN_GOLD
PAXG
```

Technical analysis must consume actual price observations.

Premium is an analytical relationship, not a substitute for the underlying price candle.

Raw observations remain separate from interpreted states.

---

# 12. Representative Iranian Gold Price

The deterministic representative-price fallback is:

```text
Milli
→ Ayyareh
→ WallGold
→ UNKNOWN
```

First valid source wins.

The selected source must remain identifiable as provenance.

This representative series is used where a single canonical Iranian-gold series is required.

It is not the same thing as the platform-average market view.

---

# 13. Iranian Platform Collection

The project currently integrates Iranian gold-platform sources including, where configured and operational:

```text
HoorGold
Parasteh
Daric
Taline
Ayyareh
Invi
MioGold
Eligold
Goldika
Milli
WallGold
```

Source failures must remain isolated.

Examples of source-specific normalization:

```text
Toman → Rial
source-specific smaller unit → canonical IRR/gram
```

Unit normalization is a data-ingestion responsibility, not a market-model adjustment.

Daric may timeout or fail independently without invalidating the remaining collection.

---

# 14. Market Calculations

Core market calculations include:

```text
Fair Price
Platform Average
Highest Platform Price
Lowest Platform Price
Platform Spread
Bubble / Premium
```

Conceptually:

```text
Bubble % = (market price / fair price - 1) × 100
```

Negative values represent a discount.

Positive values represent a premium.

The distinction between:

```text
market price direction
```

and:

```text
bubble movement
```

must remain explicit.

---

# 15. PRE-SP-C.2 — Analysis Snapshot + Scheduler Foundation

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

KPI:

```text
14/14 PASS
```

---

# 16. PRE-SP-C.3 — Price Structure + Regime

KPI:

```text
20/20 PASS
```

Established:

- representative Iranian price fallback
- deterministic support/resistance
- market regime classification

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

Regime hysteresis is separate from SP-A decision hysteresis.

Valid example:

```text
CHEAP + PANIC
```

Regime never issues BUY/SELL.

---

# 17. PRE-SP-C.4 — Analysis Snapshot Integration

Persisted C.4 state:

```text
regime_state
technical_state_json
previous_regime
regime_candidate_state
regime_confirmation_count
```

Cross-run regime hysteresis is reconstructed from persisted snapshot state.

No separate regime table and no file cache are used.

KPI:

```text
19/19 PASS
```

### Invi

`src/collector/invi.py` normalizes the source value into the canonical IRR/gram scale.

The source exposes a smaller unit and the collector normalizes it by:

```text
×1000
```

Invi is registered in the Iranian collector path but is not part of the representative-price fallback chain.

---

# 18. PRE-SP-C.5 — Outcome Evaluation

C.5 is retrospective measurement infrastructure.

It does not predict and does not alter the current decision engine.

Initial horizons:

```text
+1h
+6h
+24h
```

Evaluation:

```text
analysis snapshot
    ↓
target horizon
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

KPI:

```text
25/25 PASS
```

Persistence:

```text
outcome_evaluations
```

Uniqueness:

```text
(snapshot_id, horizon_hours)
```

---

# 19. PRE-SP-C.6 — Evidence Package

C.6 creates a deterministic, auditable evidence package from persisted analytical outputs.

Evidence families:

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

Requirements:

- explicit schema version
- deterministic validation
- provenance
- explicit missing/unknown handling
- no BUY/SELL decision embedded as a substitute for the Decision Engine

Persistence:

```text
analysis_snapshots.evidence_package_json
```

KPI:

```text
25/25 PASS
```

C.6 does not implement:

```text
multi-agent debate
autonomous trading
prediction
```

---

# 20. PRE-SP-C.7 — Interpretation Intelligence

C.7 adds structured interpretation over deterministic evidence.

Responsibilities:

- explain validated evidence
- describe observed conditions
- surface conflicting evidence
- express uncertainty
- preserve provenance
- keep facts and evidence unchanged

It must not:

- rewrite raw observations
- fabricate market facts
- invent technical levels
- replace deterministic regime state
- create independent BUY/SELL authority
- contaminate historical evidence

Persistence:

```text
analysis_snapshots.intelligence_result_json
```

KPI:

```text
25/25 PASS
```

Interpretation is not a second calculation engine.

---

# 21. PRE-SP-C.8 — Feature Intelligence

C.8 creates deterministic, explainable, model-ready feature structures.

Feature families:

## Trend

- SMA / MA
- EMA
- price-vs-moving-average relationships
- explicit insufficient-history handling

## Momentum

- premium velocity
- premium acceleration
- direction persistence
- direction change / divergence context

## Volatility

- rolling volatility
- range expansion
- instability indicators

## Regime

- existing regime state
- regime duration / transition context where available

C.8 must reuse C.4 regime primitives.

## Market relationships

- XAU/USD direction
- USD/IRR pressure
- local-gold / external-market divergence

## Structure

- spread
- platform consensus
- consensus ratio
- discount dominance

Invariants:

- deterministic
- no look-ahead leakage
- missing data explicit
- insufficient history explicit
- no BUY/WAIT/SELL output
- schema version explicit
- persistence round-trip capable
- data quality explicit

Persistence:

```text
analysis_snapshots.features_json
```

KPI:

```text
25/25 PASS
```

Implemented EMA/SMA feature windows include:

```text
7
15
30
```

for relevant representative-gold, XAU/USD, and USD/IRR series.

---

# 22. PRE-SP-C.9 — Analytical Read Model

C.9 creates a normalized, auditable, presentation-oriented read contract over:

```text
C.6 Evidence
+
C.7 Interpretation
+
C.8 Features
```

Flow:

```text
Evidence
+
Interpretation
+
Features
    ↓
Analytical Read Model
    ↓
future Telegram / API / dashboard consumers
```

The read model does not calculate, decide, or predict.

Sections include:

```text
facts
evidence_summary
interpretation_summary
features_summary
uncertainty
outcome_history
decision
provenance
```

Decision is read-only:

```text
source = existing_decision_engine
```

Persistence:

```text
analysis_snapshots.analysis_read_model_json
```

KPI:

```text
23/23 PASS
```

---

# 23. PRE-SP-C.10 — Read Model Integration & Audit

C.10 establishes stable retrieval and historical audit around the persisted read model.

Responsibilities:

- retrieve by `analysis_snapshot_id`
- classify completeness
- preserve provenance
- preserve evidence
- preserve interpretation
- preserve features
- preserve outcomes
- preserve decision context
- reconstruct historical state without current-data leakage
- preserve `UNKNOWN`
- preserve `INSUFFICIENT_DATA`
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
22/22 PASS
```

No C.10 schema change was required.

---

# 24. C14C — Current Completed Analytical Foundation

C14C is complete.

```text
C14C
21/21 KPI PASS
```

Architectural boundary:

```text
C14C strengthens analytical intelligence infrastructure.
C14C does not authorize autonomous learning or prediction.
```

No Neon migration was required for C14C.

The project should not interpret completion of C14C as evidence that prediction is ready.

The next bottleneck is empirical evidence quality and accumulated historical outcomes, not simply another layer of code.

---

# 25. Database Contract

Neon PostgreSQL is the long-term historical store.

| Table | Responsibility |
|---|---|
| `market_snapshots` | Existing market observations / canonical market state |
| `platform_prices` | Platform evidence |
| `market_states` | Deterministic interpreted market state |
| `news_events` | Structured external events |
| `price_observations` | Canonical raw technical time series |
| `analysis_snapshots` | Scheduled analytical history and analytical packages |
| `outcome_evaluations` | Retrospective +1h / +6h / +24h measurements |

`analysis_snapshots` currently carries:

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

JSONB indexes exist for the persisted analytical packages.

Uniqueness:

```text
uq_outcome_eval_snapshot_horizon
uq_analysis_snapshots_source_run_id
```

Snapshot type constraint:

```text
snapshot_type IN ('analysis', 'live')
```

---

# 26. Neon Migration Policy

Schema authority is intentionally split:

```text
sql/neon_schema.sql
    = complete canonical TARGET schema

sql/neon_migration_*.sql
    = incremental migration for EXISTING Neon
```

Never apply the complete target schema as a replacement migration against an already-populated production database.

Any future schema change requires:

```text
explicit requirement
→ incremental migration
→ temporary-branch verification
→ production application
→ verification
→ documentation/state synchronization
```

Current UPDATE v1 boundary:

```text
NO NEON MIGRATION REQUIRED
```

C14C boundary:

```text
NO NEON MIGRATION REQUIRED
```

Do not introduce a migration merely because a new feature exists. Demonstrate the persistence requirement first.

---

# 27. Historical and News Intelligence

Historical intelligence is descriptive context.

News intelligence is structured external-event context.

Neither independently calculates:

```text
fair price
premium
technical indicators
BUY/SELL
```

News failures are non-blocking.

News remains separate from market facts.

---

# 28. LLM Boundary

LLM may:

- summarize structured context
- interpret validated evidence
- express uncertainty
- explain relationships already present in the evidence

LLM must not:

- calculate fair price
- calculate premium
- calculate indicators
- invent technical levels
- invent historical statistics
- override deterministic state
- independently issue BUY/SELL
- mutate historical facts
- rewrite persisted evidence

Future intelligence may use the deterministic evidence, feature, read-model, and outcome contracts as inputs.

---

# 29. Current Forecast Boundary

The forecast engine is operational as a pipeline but is correctly conservative when historical evidence is insufficient.

Current valid state:

```text
1h  = INSUFFICIENT_DATA
6h  = INSUFFICIENT_DATA
24h = INSUFFICIENT_DATA
```

This is not a failure condition.

It is the correct output when the system lacks sufficient empirical history.

Do not replace `INSUFFICIENT_DATA` with a guessed forecast merely to make the system appear more intelligent.

---

# 30. Forecast / EJS Direction

The long-term objective is an Expert Judgment System / future intelligence capability.

The intended progression is:

```text
historical observations
→ deterministic features
→ historical outcome labels
→ empirical evaluation
→ evidence weighting
→ model / judgment architecture
→ prediction
```

Before introducing prediction, the project needs sufficient empirical evidence to answer:

- which signals actually matter
- which combinations are predictive
- how stable those relationships are
- how performance changes by regime
- how much weight should be assigned to each evidence family
- where the system should abstain
- how prediction quality is measured out-of-sample

Prediction must remain downstream.

It must never overwrite:

```text
facts
evidence
interpretation
features
read model
historical decision record
```

---

# 31. Post-C14 Research Direction

The next major phase should **not** begin as a blind implementation sprint.

Priority is:

```text
RESEARCH
→ EMPIRICAL EVIDENCE
→ CALIBRATION
→ ARCHITECTURE DECISION
→ TARGETED IMPLEMENTATION
```

Current research areas include:

## A. Momentum / pace calibration

Empirically calibrate:

```text
SHARP
NOT SHARP
STABLE
```

and acceleration behavior using real production history.

Do not hard-code arbitrary thresholds as if they were market truths.

## B. Bubble dynamics

Study:

```text
bubble level
bubble velocity
bubble acceleration
price direction
external-market movement
```

and identify meaningful regimes.

## C. Forecast evaluation

Build enough historical outcome coverage to evaluate whether current features have predictive value.

## D. Evidence weighting

Determine how:

```text
valuation
momentum
structure
regime
XAU/USD
USD/IRR
representative gold
news
historical context
```

should contribute to future judgment.

## E. Iranian market-flow research

Potential future sources include:

```text
Tindex
TSE / market-flow sources
Navasan API
other validated Iranian-market datasets
```

A possible future extension is money-flow analysis for Iranian gold ETFs and related instruments.

This is research scope, not current UPDATE scope.

---

# 32. Telegram / Presentation Boundary

Telegram is a presentation consumer.

It is not:

```text
calculation engine
evidence engine
decision engine
```

The current UPDATE presentation should remain compact and readable.

Desired conceptual sections:

```text
MARKET
PRICE & BUBBLE DYNAMICS
MARKET STRUCTURE
PLATFORMS
CURRENT DECISION
```

The presentation should expose useful RUN / DAY comparisons where valid.

Do not create analytical logic solely inside Telegram formatting code.

A duplicated application header is a presentation defect, not an architectural state change.

---

# 33. Documentation Governance

`PROJECT_MEMORY.md` is the canonical project-specific source of truth.

Rules:

1. Update `PROJECT_MEMORY.md` for every architecture/state milestone.
2. Update `MASTER_PLAN_STATUS.md` when milestone/phase status changes.
3. Update `DOCUMENTATION_INDEX.md` when documentation coverage or implementation references change.
4. Update `README.md` when the human-facing system map or current phase changes.
5. Update `Prompt_Guide.md` only when generic AI engineering behavior changes.
6. Update specialist skills only when reusable operating behavior changes.
7. Do not create duplicate sprint-status documents.
8. Do not create redundant architecture summaries when the truth belongs here.
9. Keep SQL schema/migration documentation aligned with Neon state.
10. Keep `.project_state.json` synchronized with current phase, KPI, Neon state, next phase, and completion state.
11. Executable evidence outranks prose when verifying implementation.
12. Historical project context belongs in git history unless it is still architecturally relevant.
13. Do not create a new documentation file merely to record a small implementation milestone.

---

# 34. Project Continuity Protocol

A new AI engineering session must reconstruct state from the repository.

Required read order:

```text
.project_state.json
    ↓
PROJECT_MEMORY.md
    ↓
MASTER_PLAN_STATUS.md
    ↓
DOCUMENTATION_INDEX.md
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

Mandatory implementation handoff:

```text
inspect repository
    ↓
understand architecture boundary
    ↓
identify exact change surface
    ↓
audit schema impact
    ↓
implement minimally
    ↓
targeted KPI
    ↓
regression KPI
    ↓
smoke test
    ↓
database verification when applicable
    ↓
diff review
    ↓
documentation synchronization
    ↓
.project_state synchronization
    ↓
commit / branch review
```

No implementation should start from conversation memory alone when repository evidence is available.

---

# 35. Verification Standard

Every implementation change follows:

```text
inspect
→ define change surface
→ implement minimally
→ targeted test
→ regression
→ KPI
→ smoke test
→ database verification when applicable
→ diff review
→ documentation sync
→ continuity-state sync
→ commit
```

Current verified / supplied KPI evidence:

```text
PRE-SP-C.2   14/14 PASS
PRE-SP-C.3   20/20 PASS
PRE-SP-C.4   19/19 PASS
PRE-SP-C.5   25/25 PASS
PRE-SP-C.6   25/25 PASS
PRE-SP-C.7   25/25 PASS
PRE-SP-C.8   25/25 PASS
PRE-SP-C.9   23/23 PASS
PRE-SP-C.10  22/22 PASS
C14C         21/21 PASS
compileall   PASS
live smoke   PASS
Neon reconciliation through C.9 PASS
```

For local KPI execution on Windows CMD:

```cmd
git pull origin <branch>
python kpi\kpi_<specific_test>.py
```

Run KPI files explicitly rather than relying on shell wildcard behavior.

---

# 36. SP-B Closure Mapping

Original SP-B names are architectural placeholders and do not require duplicate module boundaries.

| Original | Current role |
|---|---|
| SP-B.3 | Analysis Wing / bounded interpretation |
| SP-B.4 | Telegram analytical read models |
| SP-B.5 | Combined read model over persisted analytical state |

Do not create duplicate agent/radar layers solely to preserve historical sprint names.

---

# 37. Future Consumer Contract

The stable downstream ownership remains:

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
CONSUMER
    ↓
DECISION AUTHORITY
    ↓
FUTURE PREDICTION
```

Consumers may include:

```text
Telegram
API
dashboard
future intelligence interface
```

Consumers must not rebuild upstream analytical calculations.

---

# 38. Architecture Regression Guardrails

Any future change must explicitly answer:

```text
Does this change alter collection?
Does this change alter canonical observations?
Does this change alter calculation ownership?
Does this change create a second decision authority?
Does this change mix news with market facts?
Does this change introduce look-ahead leakage?
Does this change create a new persistence requirement?
Does this change move logic into presentation?
Does this change alter RUN / DAY semantics?
Does this change make UPDATE execute the full Analysis pipeline?
Does this change introduce prediction before empirical readiness?
```

If any answer is unclear, stop and inspect before coding.

The project prioritizes preservation of architectural boundaries over implementation speed.

---

# 39. Current Bottom Line

As of the current project state:

```text
SP-A                 COMPLETE / FROZEN
SP-B                 COMPLETE through C.10
C14C                 COMPLETE — 21/21 KPI PASS
UPDATE v1            OPERATIONAL
NEWS INGESTION       OPERATIONAL
FORECAST PIPELINE    OPERATIONAL / INSUFFICIENT_DATA
NEON MIGRATION       NOT REQUIRED FOR C14C / UPDATE v1
ARCHITECTURE         PRESERVED
```

The system has moved beyond basic collection and deterministic market-state construction.

The current strategic bottleneck is:

```text
EMPIRICAL MARKET HISTORY
+
FORECAST OUTCOME HISTORY
+
CALIBRATION
+
EVIDENCE QUALITY
```

Therefore:

```text
DO NOT BLINDLY CODE THE NEXT SPRINT.
```

The next major implementation phase should follow research and evidence review.

The long-term destination remains:

```text
COLLECT
→ VALIDATE
→ STORE
→ ANALYZE
→ EVALUATE
→ LEARN FROM HISTORY
→ BUILD EXPERT JUDGMENT
→ PREDICT
```

while preserving the deterministic and auditable architecture underneath.
