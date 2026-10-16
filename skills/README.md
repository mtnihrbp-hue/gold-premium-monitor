# AI Developer Skills

The `skills/` directory contains reusable operating instructions for AI coding agents. It is a **behavior layer**, not the project architecture or sprint specification.

## Documentation authority

The reading order and the conflict rule are stated once, in `PROJECT_MEMORY.md` section 1 (mirrored
in `CLAUDE.md`). In short: the owner's current instruction sets the scope; executable evidence
(tests, KPIs, production state) outranks prose; among documents `PROJECT_MEMORY.md` wins.

When documentation conflicts with executable behavior, report the discrepancy and follow the current approved task plus repository implementation evidence.

## Required load order for a new AI coding session

1. `.project_state.json` and `PROJECT_MEMORY.md`
2. `core-engineering.md`
3. `repository-onboarding.md`
4. `sprint-execution.md`
5. Task-specific specialist skill(s)
6. The current sprint's handoff (`SP_D_HANDOFF.md`) for the task's background

Do not load every specialist skill for every task.

## Skills

- `core-engineering.md` — permanent engineering behavior
- `repository-onboarding.md` — repository orientation and source-of-truth rules
- `sprint-execution.md` — scope, branch discipline, tests, KPI, release
- `branch-management.md` — branch and Git workflow
- `market-analyst.md` — valuation, momentum, conflict and decision philosophy
- `telegram-product.md` — Telegram cockpit and read-model boundaries
- `data-and-neon.md` — raw observations, Neon persistence and data quality
- `llm-news-intelligence.md` — external intelligence and LLM boundaries
- `validation-and-release.md` — verification and completion gates
- `new-conversation-bootstrap.md` — bootstrap prompt for a fresh AI session

## Non-duplication rule

Skills should explain **how an AI agent should operate**. They should not copy the entire architecture or sprint roadmap from `PROJECT_MEMORY.md`.

When a project fact changes, update `PROJECT_MEMORY.md` first. Update a specialist skill only when its reusable behavior or boundary also changes.

## Current architecture anchors

The project must preserve these boundaries:

```text
Quantitative Engine
    = measures market facts

Intelligence Layer
    = interprets external context

Decision Engine
    = evaluates evidence
```

And:

```text
CHEAP ≠ BUY
VALUATION ≠ MOMENTUM
CANDIDATE ≠ FINAL DECISION
NEWS ≠ MARKET DATA
LLM ≠ MARKET CALCULATION
```

Telegram is the cockpit, not the brain.

Neon stores historical memory; raw observations, interpreted states, and future evaluation records remain distinct.
