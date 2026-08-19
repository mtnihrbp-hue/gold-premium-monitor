# Prompt Guide

This file defines reusable AI coding behavior. It is **not** a record of project architecture or sprint status.

For project truth, use `PROJECT_MEMORY.md`. For human-facing orientation, use `README.md`. For specialist execution behavior, use `skills/`.

## Operating priorities

When sources conflict:

1. Current user/task requirement
2. `PROJECT_MEMORY.md`
3. `README.md`
4. Relevant skill
5. General engineering preference

Never silently override a higher-priority constraint.

## Before coding

1. Inspect the repository and current branch.
2. Read the relevant project memory and specialist skill.
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

## Financial-system boundaries

For this repository specifically:

```text
Quantitative engine = market facts
Intelligence layer  = context
Decision engine     = evidence evaluation
```

Never collapse:

```text
CHEAP ≠ BUY
VALUATION ≠ MOMENTUM
CANDIDATE ≠ FINAL DECISION
NEWS ≠ MARKET DATA
LLM ≠ MARKET CALCULATION
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
