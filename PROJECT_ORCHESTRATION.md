
# Gold Premium Monitor — Project Orchestration Protocol

This document defines project continuity and cross-system orchestration. It complements `PROJECT_MEMORY.md` and `.project_state.json` and does not compete with `PROJECT_MEMORY.md` for architecture authority.

## Documentation authority

Navigation authority:

```text
DOCUMENTATION_INDEX.md
```

Architecture authority:

```
PROJECT_MEMORY.md
```

Milestone authority:

```
MASTER_PLAN_STATUS.md
```

Operational authority:

```
PROJECT_OPERATIONS.md
```

C14 implementation contracts:

```
C14_HANDOFF.md
C14C_HANDOFF.md
C14_FEEDBACK_AND_TERMINOLOGY.md
```

Repository evidence, executable tests, and verified production state establish truth. Conversation history is context only.

## Canonical continuity loop

```
repository source
↓
schema / migration audit
↓
Neon production state
↓
targeted tests / regression / KPI
↓
documentation
↓
.project_state.json
↓
commit
```

This applies to every phase, including phases with no schema change.

## Branch discipline

```
ACTIVE DEVELOPMENT = SP-B
WRITE / COMMIT = SP-B only
MAIN MERGE = explicit SP-B close approval only
```

Do not merge main merely to synchronize documentation.

## Project wings

### Live Wing

```
/Update
→ collect
→ validate
→ calculate
→ current deterministic market state
→ Telegram
```

The Live Wing owns current deterministic market-state calculation and user-facing live updates.

### Analysis Wing

```
scheduled analysis
→ canonical observations
→ technical/regime analysis
→ analysis_snapshots
→ outcome_evaluations
→ evidence
→ interpretation
→ features
→ read model
→ historical dataset
→ forecast
```

The two wings must remain architecturally separate.

Forecasting belongs downstream of the Analysis Wing and must not alter Live-Wing calculation or deterministic decision authority.

## Phase completion rule

A phase is not complete merely because code exists or a KPI passes.

Completion requires:

```
implementation
→ targeted tests
→ regression
→ KPI
→ schema/migration audit
→ Neon production verification when applicable
→ documentation
→ .project_state.json
→ commit
```

When no schema change is required, that fact must be explicitly recorded.

## Current project position

```
SP-A                         COMPLETE
SP-B.1 / SP-B.2             COMPLETE
PRE-SP-C.1 – PRE-SP-C.13    COMPLETE
PRE-SP-C.14A                COMPLETE
PRE-SP-C.14B                COMPLETE
PRE-SP-C.14C                COMPLETE
C14C supporting work        COMPLETE where explicitly verified
CURRENT BOUNDARY             POST-C14C ARCHITECTURE / OPERATIONALIZATION
```

C14C closed the diagnostic intelligence foundation.

Operational news ingestion subsequently wired the existing:

```
RSS collection
→ deterministic classification
→ deduplication
→ news_events persistence
→ analysis consumption
```

The news ingestion path is non-blocking and does not introduce new Neon schema requirements.

C14C supporting audit modules include:

```
forecast_readiness.py
event_impact.py
```

These are read-only diagnostics.

They do not modify the database, change model weights, alter thresholds, or acquire decision authority.

## C14 architecture boundary

```
C14A
Candle & Market-Structure Infrastructure
        ↓
C14B
Forecast Features, Baselines, Evaluation & Forecast Engine
        ↓
C14C
Forecast Resolution, Human Review & Closed-Loop Audit
```

The C14 contracts preserve:

-   no future leakage
-   no interpolation for market reconstruction
-   no forward-fill of missing market observations
-   provenance preservation
-   objective outcome separate from human feedback
-   prediction separate from BUY/WAIT/SELL authority
-   Neon schema ownership through migration discipline

## Live Wing / Analysis Wing separation

The architectural boundary is:

```
LIVE WING
current market collection
→ validation
→ deterministic calculation
→ current state
→ Telegram live update

ANALYSIS WING
historical/current observations
→ snapshots
→ outcomes
→ evidence
→ interpretation
→ features
→ read model
→ historical dataset
→ forecast
```

Analysis must not rewrite deterministic Live-Wing facts.

Forecast must not become a hidden decision engine.

## Database discipline

Never assume repository SQL and Neon production are synchronized.

For schema-affecting phases:

1.  inspect production
2.  compare repository migration intent
3.  prepare incremental migration
4.  test on a temporary Neon branch
5.  obtain explicit authorization
6.  apply to production
7.  verify production
8.  synchronize documentation and state

For no-schema-change phases:

```
NEON MIGRATION REQUIRED = NO
SCHEMA CHANGE REQUIRED = NO
```

must be recorded when applicable.

## KPI engineering standard

KPIs are executable specifications.

Before writing a KPI:

1.  identify authoritative production contract and source inputs
2.  define canonical output schema and field names
3.  construct fixtures through the same contracts production consumes
4.  mutate authoritative inputs for transition tests
5.  allow production logic to derive statuses, labels, classifications, and metadata
6.  never hard-code derived fields in fixtures when production recomputes them
7.  use `deepcopy` for nested mutations
8.  do not alter production semantics merely to satisfy a malformed KPI
9.  preserve canonical upstream field names unless aliases are explicitly part of the contract
10.  include leakage tests for historical/model-ready phases

Every future implementation prompt should define canonical field names before implementation and before KPI authoring.

## Regression discipline

A new phase must preserve all previously verified contracts unless the phase explicitly changes one.

Regression must include:

```
targeted tests
+
relevant prior KPI suites
+
compileall
+
architecture-boundary checks
```

A passing new KPI does not prove regression safety.

## Compact KIMI handoff template

Pre-coding reports should be operational and limited to the relevant scope.

```
PRE-CODING INSPECTION

CURRENT STATE
- relevant existing contracts only

ROOT CAUSE
- exact defect or missing architectural link

CHANGE SURFACE
- exact files/modules

DATABASE
- NONE
or
- exact schema delta + reason

CANONICAL CONTRACT
- exact output fields and names

KPI
- exact tests and authoritative fixtures

REGRESSION
- required prior KPIs/tests

NON-GOALS
- phase-specific exclusions

IMPLEMENTATION PLAN
- 3–7 concrete steps

BLOCKERS
- only genuine ambiguities
```

For KPI design specifically, identify:

```
AUTHORITATIVE SOURCE INPUTS
DERIVED FIELDS
FIXTURE CONSTRUCTION
EXPECTED FAILURE MODES
LEAKAGE MODEL
```

## New-conversation onboarding

Use this order:

```
.project_state.json
→ DOCUMENTATION_INDEX.md
→ PROJECT_MEMORY.md
→ MASTER_PLAN_STATUS.md
→ PROJECT_ORCHESTRATION.md
→ PROJECT_OPERATIONS.md
→ C14 contracts
→ relevant source / tests / KPI / SQL
```

Repository evidence and executable verification outrank conversation memory.

## Forecast boundary

The long-term forecast target remains:

```
UP
NEUTRAL
DOWN
```

Forecasting must be probabilistic and calibrated rather than forced categorical certainty.

Operational states include:

```
ABSTAIN
INSUFFICIENT_DATA
```

Forecast never directly generates:

```
BUY
WAIT
SELL
```

Prediction remains separate from decision authority.

The architectural information flow remains:

```
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
PREDICTION
↓
DECISION
```

Forecast never rewrites facts, evidence, interpretation, features, read-model state, historical outcomes, or deterministic decisions.

## Forecast readiness gate

A forecast should not be treated as deployment-ready merely because the forecast engine exists.

The evidence gate is:

```
sustained analysis snapshots
→ sustained outcome evaluations
→ leakage-safe historical dataset
→ walk-forward evaluation
→ baseline comparison
→ calibration
→ uncertainty / abstention
→ historical performance evidence
→ only then downstream forecast consumption
```

Production data readiness must be determined from actual Neon state, not historical documentation values.

The `forecast_readiness.py` diagnostic is read-only and reports:

-   usable training examples by horizon
-   readiness gate state
-   exact gating reasons
-   temporal coverage
-   observed cadence
-   estimated time to readiness when mathematically supportable

It must not manufacture readiness from hardcoded assumptions.

## Event-impact boundary

The `event_impact.py` diagnostic is read-only.

It may report:

-   relevant news events
-   regime at event time
-   subsequent observed market direction
-   agreement/disagreement between classified expected direction and observed direction
-   insufficient outcome data

Event impact must explicitly remain:

```
TEMPORAL ASSOCIATION
NOT CAUSATION
```

The diagnostic must not convert temporal association into causal claims.

## Human forecast review

Human review remains separate from objective forecast evaluation.

The lifecycle is:

```
GENERATED
→ OUTCOME_EVALUATED
→ USER_REVIEWED (optional)
```

Preserve separate clocks:

```
forecast_time
market_outcome_time
feedback_time
```

Objective market outcome and human assessment are separate concepts.

Human feedback is audit/evidence metadata first.

It is not objective ground truth, direct label replacement, or online model training.

## Fail-safe law

```
MISSING
 ↓
safe deterministic fallback?
 ├─ YES → fallback + degraded provenance
 └─ NO  → INSUFFICIENT_DATA / ABSTAIN
```

Never silently extrapolate missing market data into apparently real data.

## User-facing terminology

Avoid opaque causal-sounding labels when observable descriptions are sufficient.

Prefer statements such as:

-   Iranian gold is increasing more slowly than its external drivers.
-   Iranian gold is catching up faster than its external drivers.

Internal quantitative analysis may use:

```
price level
rate of change
relative rate of change
acceleration
```

Do not claim causal explanations without evidence.

## External research boundary

External research informs analytical design only.

The project does not include:

-   MT5 execution
-   broker execution
-   autonomous trading
-   reinforcement-learning execution
-   order management
-   online self-modifying models
-   direct user-feedback weight updates

Research-derived techniques must be evaluated against the project's own data, contracts, leakage rules, and operational constraints before adoption.

## Architectural operating principle

The system must evolve by strengthening the evidence chain rather than by adding uncontrolled intelligence.

The intended direction is:

```
TRUSTWORTHY DATA
→ PERSISTENT ANALYSIS
→ OBJECTIVE OUTCOMES
→ HISTORICAL EVIDENCE
→ DIAGNOSTICS
→ FORECASTING
→ CONTROLLED CONSUMPTION
```

No downstream intelligence component may silently bypass an upstream contract.