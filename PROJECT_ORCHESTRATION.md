# Gold Premium Monitor — Project Orchestration Protocol

This document defines the project-continuity and cross-system orchestration workflow. It complements `PROJECT_MEMORY.md`, `.project_state.json`, `PROJECT_OPERATIONS.md`, `C14_HANDOFF.md`, and `RESEARCH_ADOPTION.md` and prevents state loss between conversations, AI developers, GitHub, Neon, scheduling, and Cloudflare.

## Canonical project orchestration loop

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

Mandatory for every implementation phase, including phases with no database change.

## Runtime control-plane loop

```text
cron-job.org / Telegram
        ↓
Cloudflare secure interconnection
        ↓
GitHub Actions
        ↓
SP-B execution
        ↓
Analysis Wing or Live Wing
        ↓
Neon / Telegram
```

`PROJECT_OPERATIONS.md` is the operational authority.

## Two-wing frontend architecture

The frontend remains exactly two user-facing wings:

```text
LIVE WING
/Update

ANALYSIS WING
/Analyze
/Forecast
/Technical
/History
/News
/Health
```

Human forecast feedback is collected inside the Analysis experience. It is not a third frontend wing.

## Phase completion rule

A phase is not complete merely because code exists or a KPI passes.

Completion requires synchronized:

```text
implementation
→ targeted tests
→ regression
→ KPI
→ schema/migration audit
→ Neon production state
→ runtime/operational state when relevant
documentation
→ .project_state.json
→ commit
```

## Local KPI verification

```cmd
git pull origin SP-B
python kpi\kpi_pre_sp_cX.py
```

Run previous KPI suites explicitly for regression. Do not rely on Windows wildcard execution as the authoritative suite runner.

## KPI engineering standard

Before writing a KPI:

1. Inspect production implementation.
2. Define canonical output contracts and exact field names.
3. Identify authoritative source inputs.
4. Seed fixtures through production-compatible contracts.
5. Mutate authoritative inputs for derived-state tests.
6. Let production code derive statuses, metadata, labels, and classifications.
7. Use deep copies for nested JSON mutation.
8. Never invent post-hoc aliases solely to satisfy a test.
9. Never weaken production semantics to satisfy a malformed fixture.

The repeated C.10–C.13 KPI issues led to this rule being treated as a permanent engineering standard.

## New-conversation onboarding

```text
.project_state.json
→ PROJECT_MEMORY.md
→ README.md
→ Prompt_Guide.md
→ PROJECT_ORCHESTRATION.md
→ PROJECT_OPERATIONS.md
→ C14_HANDOFF.md when C.14 is active
→ RESEARCH_ADOPTION.md when research context is relevant
→ skills/
→ relevant source / tests / KPI / SQL
```

Repository evidence and live Neon/runtime inspection establish current truth. Conversation history is context, not proof.

## Database discipline

Never assume repository SQL and Neon production are synchronized.

For schema-affecting work:

1. inspect Neon production
2. compare with repository intent
3. prepare incremental migration
4. test on temporary Neon branch
5. apply only after authorization
6. verify production schema
7. synchronize repository migration and documentation

Do not use `sql/neon_schema.sql` as a destructive replacement for production.

## C.14 split

C.14 is intentionally split:

```text
PRE-SP-C.14A
Candle & Market-Structure Data Infrastructure

        ↓

PRE-SP-C.14B
Forecast Features, Baselines, Evaluation & Forecast Engine
```

C.14A establishes trustworthy persistent candle infrastructure. C.14B evaluates predictive value using that infrastructure.

C.14 is not a single monolithic implementation unit.

## C.14 contracts

### Candle layer

```text
RAW PLATFORM QUOTES
   ↓
CANONICAL OBSERVATIONS
   ↓
DERIVED / SOURCE CANDLES
   ↓
CANDLE FEATURES
```

For derived candles:

```text
OPEN  = first valid observation
HIGH  = maximum valid observation
LOW   = minimum valid observation
CLOSE = last valid observation
```

No interpolation. No forward-fill. No future observations.

Platforms with explicit buy/sell semantics preserve separate sides.

Goldika provides explicit buy/sell quotes. Ayyareh raw `goldPrice` and margin/wage fields must be interpreted from the existing collector contract before deriving side prices; raw and derived values remain separate.

### Forecast layer

C.5 is authoritative for labels:

```text
UP → UP
FLAT → NEUTRAL
DOWN → DOWN
INSUFFICIENT_DATA → INSUFFICIENT_DATA
```

Forecast output may also be:

```text
ABSTAIN
```

Prediction never becomes direct BUY/WAIT/SELL authority.

## C.14 fail-safe principle

```text
MISSING
 ↓
safe deterministic fallback?
 ├─ YES → fallback + degraded provenance
 └─ NO  → INSUFFICIENT_DATA / ABSTAIN
```

Never silently extrapolate absent market data into apparently real facts.

## Human feedback contract

The system objectively evaluates forecasts first. Human feedback is a separate meta-data stream.

Forecast lifecycle:

```text
GENERATED
→ PENDING
→ ELIGIBLE_FOR_REVIEW
→ OBJECTIVELY_EVALUATED
→ USER_REVIEWED (optional)
```

System time, market/outcome time, and user feedback time remain separate.

Human feedback may support model audit and future controlled research, but it must not directly modify production model weights or labels.

Recommended progressive Telegram review:

```text
Previous forecast review
[ Very useful ]
[ Mostly useful ]
[ Direction right, timing wrong ]
[ Direction wrong ]
[ Hard to judge ]
```

Optional reason layer:

```text
[ Timing ] [ USD/IRR ] [ World Gold ] [ Local Market ]
[ Premium ] [ Price Action ] [ News ] [ Hard to judge ]
```

## Research boundaries

External sources are research inspiration only. See `RESEARCH_ADOPTION.md` for the adoption/defer matrix.

No MT5/broker execution, reinforcement-learning trading agents, autonomous trading, opaque self-modifying prediction, or direct user-feedback online training.

## Current operational truth

```text
PRE-SP-C.13 COMPLETE
KPI: 26/26 PASS
compileall: PASS
live smoke: PASS
Neon C.13 reconciliation: COMPLETE

NEXT:
PRE-SP-C.14A — Candle & Market-Structure Data Infrastructure
```
