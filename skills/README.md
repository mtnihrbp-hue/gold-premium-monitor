# AI Developer Skills

The `skills/` directory contains reusable operating instructions for AI coding agents. It is a **behavior layer**, not the project architecture or sprint specification.

## Documentation authority

Use the repository documents in this order:

1. **Current user/task requirement** — exact scope for the current change.
2. **`PROJECT_MEMORY.md`** — canonical project architecture, implemented state, invariants, contracts, and current development position.
3. **`README.md`** — human-facing project orientation, setup, navigation, and concise status.
4. **`Prompt_Guide.md`** — generic AI engineering behavior; it must not be used as a project-state record.
5. **`skills/`** — reusable execution behavior and specialist guidance.
6. **Source code, tests, and KPI** — executable implementation truth and verification evidence.

When documentation conflicts with executable behavior, report the discrepancy and follow the current approved task plus repository implementation evidence.

## Required load order for a new AI coding session

1. `core-engineering.md`
2. `repository-onboarding.md`
3. `sprint-execution.md`
4. `PROJECT_MEMORY.md`
5. Task-specific specialist skill(s)
6. Current sprint prompt/task

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
