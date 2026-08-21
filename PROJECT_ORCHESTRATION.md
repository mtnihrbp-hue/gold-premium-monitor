# Gold Premium Monitor — Project Orchestration Protocol

This document defines the project-continuity and cross-system orchestration workflow. It complements `PROJECT_MEMORY.md` and `.project_state.json` and prevents state loss across conversations, KIMI, GitHub, Neon, and local execution.

## Canonical orchestration loop

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

Mandatory for every phase, including phases with no schema change.

## Project wings

### Live Wing

```text
/Update
→ collect
→ validate
→ calculate
→ current deterministic market state
→ Telegram
```

Current production Telegram behavior remains primarily SP-A/Live-Wing oriented.

### Analysis Wing

```text
scheduled analysis
→ canonical observations
→ technical/regime analysis
→ analysis_snapshots
→ outcome_evaluations
→ evidence
→ interpretation
→ features
→ read model
→ consumer interface
→ historical dataset
→ future forecast
```

Do not mix the wings. Forecasting belongs downstream of the Analysis Wing and must not alter Live-Wing calculation or decision authority.

## Phase completion rule

A phase is not complete merely because code exists or a KPI passes.

Completion requires:

```text
implementation
→ targeted tests
→ regression
→ KPI
→ schema/migration audit
→ Neon production state
→ documentation
→ .project_state.json
→ commit
```

## Local KPI routine

```cmd
git pull origin SP-B
python kpi\kpi_pre_sp_cX.py
```

Run prior required KPI suites explicitly for regression. Do not rely on `python kpi\kpi_pre_sp_c*.py` as the authoritative Windows CMD runner.

## KPI engineering standard

KPIs are executable specifications.

Before writing a KPI:

1. Identify the production contract and authoritative source inputs.
2. Define the canonical output schema and field names first.
3. Seed fixtures through the same contracts production consumes.
4. Mutate authoritative inputs for transition tests.
5. Let production logic derive completeness, status, labels, classifications, and other derived metadata.
6. Never hard-code a derived field in a fixture when production recomputes it.
7. Use `deepcopy` for nested JSON mutations.
8. Do not alter production semantics to satisfy a malformed KPI.
9. Keep generic aliases only when they are explicitly part of the phase contract; otherwise preserve canonical upstream names.
10. Add leakage tests for every historical/model-ready phase.

Recent C.10-C.12 iterations demonstrated that contract-shape ambiguity creates avoidable rework. Therefore every future KIMI prompt must define canonical field names before implementation and before KPI authoring.

## Compact KIMI handoff template

Pre-coding reports should be short and operational. KIMI should not restate project history unless a specific conflict exists.

```text
PRE-CODING INSPECTION

CURRENT STATE
- only relevant existing contracts

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
- phase-specific exclusions only

IMPLEMENTATION PLAN
- 3–7 concrete steps

BLOCKERS
- only genuine ambiguities
```

For KPI design specifically, KIMI must identify:

```text
AUTHORITATIVE SOURCE INPUTS
DERIVED FIELDS
FIXTURE CONSTRUCTION
EXPECTED FAILURE MODES
LEAKAGE MODEL
```

## New-conversation onboarding

```text
.project_state.json
→ PROJECT_MEMORY.md
→ README.md
→ Prompt_Guide.md
→ PROJECT_ORCHESTRATION.md
→ skills/
→ relevant source / tests / KPI / SQL
```

Conversation history is context, not proof. Repository state, executable evidence, and live Neon inspection establish truth.

## Database discipline

Never assume repository SQL and Neon production are synchronized.

For schema-affecting phases:

1. inspect production
2. compare repository migration intent
3. prepare incremental migration
4. test on temporary Neon branch
5. obtain authorization
6. apply to production
7. verify production
8. synchronize documentation/state

When no schema change is required, record that explicitly.

## Verified state

```text
PRE-SP-C.10 COMPLETE — 22/22
PRE-SP-C.11 COMPLETE — 25/25
PRE-SP-C.12 COMPLETE — 30/30
```

C.12 provides the historical dataset contract from persisted C.8 features plus C.5 outcomes with leakage-safe labels.

## Production data-readiness gate

At the latest Neon production audit:

```text
analysis_snapshots   = 0
outcome_evaluations  = 0
price_observations   = 134
```

Therefore the repository has feature/dataset infrastructure, but production does not yet contain an empirical analysis/outcome history suitable for forecasting evaluation.

A forecast model must not be declared reliable or deployed as a decision-support signal until this gate is satisfied.

## PRE-SP-C.13 — Next phase

```text
Analysis Wing Operationalization + Telegram Analytical Commands + Scheduler/cron Integration
```

Objective:

- make scheduled analysis actually produce persisted `analysis_snapshots`
- ensure C.5 outcome evaluation runs from those snapshots
- connect C.9/C.10/C.11 contracts to Telegram consumers
- add analytical commands without changing `/Update` semantics
- establish the actual external scheduler/cron invocation and idempotency
- verify the Analysis Wing independently of the Live Wing

No prediction model in C.13.

## Forecast direction

The long-term forecast target is a three-state directional engine:

```text
UP
NEUTRAL
DOWN
```

It should be probabilistic and calibrated, not a forced categorical certainty. It must include an explicit abstain/insufficient-data state and remain separate from BUY/WAIT/SELL authority.

The forecast gate requires:

```text
sustained analysis snapshots
→ sustained outcome evaluations
→ leakage-safe C.12 dataset
→ walk-forward backtesting
→ baseline comparison
→ calibration
→ uncertainty / abstention
→ historical performance report
→ only then downstream forecast consumption
```

No forecast component may rewrite facts, evidence, interpretation, features, historical outcomes, or deterministic decisions.
