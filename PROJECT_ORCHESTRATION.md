# Gold Premium Monitor — Project Orchestration Protocol

This document defines continuity workflow only. It does not compete with `PROJECT_MEMORY.md` for architecture authority.

## Documentation authority

Navigation authority:

```text
DOCUMENTATION_INDEX.md
```

Architecture authority:

```text
PROJECT_MEMORY.md
```

Milestone authority:

```text
MASTER_PLAN_STATUS.md
```

Operational authority:

```text
PROJECT_OPERATIONS.md
```

C14 implementation contracts:

```text
C14_HANDOFF.md
C14C_HANDOFF.md
C14_FEEDBACK_AND_TERMINOLOGY.md
```

## Canonical continuity loop

```text
repository source
↓
schema / migration audit
↓
Neon production state
↓
KPI / smoke verification
↓
documentation
↓
.project_state.json
↓
commit
```

## Branch discipline

```text
ACTIVE DEVELOPMENT = SP-B
WRITE / COMMIT = SP-B only
MAIN MERGE = explicit SP-B close approval only
```

Do not merge main only to synchronize documentation.

## Current project position

```text
SP-B.1 COMPLETE
SP-B.2 COMPLETE
PRE-SP-C.1 through PRE-SP-C.13 COMPLETE
PRE-SP-C.14A COMPLETE
PRE-SP-C.14B COMPLETE
NEXT: PRE-SP-C.14C
```

## C14 boundary

```text
C14A
Candle & Market-Structure Infrastructure

↓

C14B
Forecast Features, Baselines, Evaluation & Forecast Engine

↓

C14C
Forecast Resolution, Human Review & Closed-Loop Audit
```

C14 contracts preserve:

- no future leakage
- no interpolation for market reconstruction
- no prediction authority over BUY/WAIT/SELL
- objective outcome separate from human feedback
- Neon schema ownership through migration discipline

## New session loading order

```text
.project_state.json
→ DOCUMENTATION_INDEX.md
→ PROJECT_MEMORY.md
→ MASTER_PLAN_STATUS.md
→ PROJECT_ORCHESTRATION.md
→ PROJECT_OPERATIONS.md
→ C14 contracts
→ relevant source/tests/KPI/SQL
```

Repository evidence and production state establish truth. Conversation history is context only.
