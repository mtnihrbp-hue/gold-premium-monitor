# Prompt Guide

This file defines reusable AI coding behavior. It is **not** a record of project architecture or sprint status.

For project truth, use `PROJECT_MEMORY.md`. For machine-readable continuity state, use `.project_state.json`. For human-facing orientation, use `README.md`. For specialist execution behavior, use `skills/`.

## Operating priorities

When sources conflict:

1. Current user/task requirement
2. `PROJECT_MEMORY.md`
3. `.project_state.json` for machine-readable phase/continuity state
4. `README.md`
5. Relevant skill
6. General engineering preference

Never silently override a higher-priority constraint.

## Continuity protocol

Every new AI session must begin with:

```text
.project_state.json
→ PROJECT_MEMORY.md
→ README.md
→ Prompt_Guide.md
→ relevant skills
→ relevant source/tests
```

`.project_state.json` is the machine-readable continuity ledger. Keep it synchronized with the repository's actual verified state.

At the end of every development phase, synchronize:

```text
implementation
+ tests
+ regression
+ KPI
+ database state
+ documentation
+ .project_state.json
+ commit
```

A phase is not COMPLETE if `.project_state.json` and project documentation disagree with executable evidence.

## Before coding

1. Inspect the repository and current branch.
2. Read `.project_state.json`, `PROJECT_MEMORY.md`, and the relevant specialist skill.
3. Inspect the actual implementation and tests.
4. Define the exact change surface.
5. State material assumptions.
6. Identify observable acceptance criteria.

Do not code during initial architecture orientation unless the task explicitly asks for implementation.

## Simplicity

- Implement the smallest solution that satisfies the approved behavior.
- Do not add speculative abstractions, frameworks, services, or configuration.
- Do not solve future-sprint problems early.
- Preserve existing interfaces and fallbacks unless the task requires changing them.

## Surgical changes

- Every changed line should have a traceable reason.
- Do not perform drive-by refactors or formatting sweeps.
- Match the repository's existing style.
- Remove only dead code made obsolete by the current change.

## Repository truth

- Conversation history is context, not proof.
- Do not invent test results, thresholds, APIs, data, or file structure.
- When data is unavailable, use `UNKNOWN` or `INSUFFICIENT_DATA` where the architecture defines it.
- GitHub repository state, executable tests/KPIs, and verified database state outrank conversational assumptions.

## Financial-system boundaries

For this repository specifically:

```text
Quantitative engine = market facts
Evidence layer      = validated analytical package
Intelligence layer  = context / interpretation
Decision engine     = current deterministic decision authority
Prediction layer    = future model output only
```

Never collapse:

```text
CHEAP ≠ BUY
VALUATION ≠ MOMENTUM
CANDIDATE ≠ FINAL DECISION
NEWS ≠ MARKET DATA
LLM ≠ MARKET CALCULATION
EVIDENCE PACKAGE ≠ DECISION
PREDICTION ≠ FACTS / EVIDENCE / INTERPRETATION
```

## Verification loop

Use:

```text
inspect
→ define success
→ implement
→ targeted test
→ regression test
→ KPI
→ database-state review
→ documentation sync
→ .project_state.json sync
→ diff review
→ branch review
```

Never claim completion without executable verification.

Use explicit status labels:

```text
PASS
FAIL
UNKNOWN
NOT RUN
```

## Failure behavior

External failures must degrade according to project conventions. Do not turn optional services into single points of failure and do not weaken existing fallback behavior.

## Communication

Report only verified facts:

- what changed
- why it changed
- what was verified
- what remains unresolved
