# KIMI Skills

These files are reusable behavioral modules for AI developers working on Gold Premium Monitor.

## Load order

1. `core-engineering.md`
2. `repository-onboarding.md`
3. `sprint-execution.md`
4. Task-specific skills as needed
5. The current sprint prompt / user task

Do not load every specialist skill for every task. Load only what is relevant.

## Skills

- `core-engineering.md` — permanent engineering behavior
- `repository-onboarding.md` — how to orient to a new conversation/repository state
- `sprint-execution.md` — branch, implementation, verification, KPI, release discipline
- `market-analyst.md` — market-analysis vocabulary and decision philosophy
- `telegram-product.md` — Telegram as the user-facing cockpit and command/navigation model
- `data-and-neon.md` — Neon, historical memory, data quality and persistence principles
- `llm-news-intelligence.md` — future LLM/news architecture and boundaries
- `validation-and-release.md` — tests, KPI, regression and completion gates

## Authority

`PROJECT_MEMORY.md` is the project-specific architectural memory.

The skills define AI behavior and reusable operating rules.

The current sprint prompt defines the exact task scope.

When these conflict:

1. Current explicit user requirement
2. Current sprint specification
3. `PROJECT_MEMORY.md`
4. Relevant skill
5. General engineering preference

Never silently override higher-priority project constraints.
