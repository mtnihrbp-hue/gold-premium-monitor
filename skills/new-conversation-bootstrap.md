# New Conversation Bootstrap

Use this prompt when starting a fresh AI-development session.

```text
You are continuing work on Gold Premium Monitor.

Repository:
https://github.com/mtnihrbp-hue/gold-premium-monitor

The repository is the implementation source of truth. Do not assume prior conversation context exists.

Documentation authority:
1. Current user/task requirement
2. PROJECT_MEMORY.md
3. README.md
4. Prompt_Guide.md
5. Relevant skills under skills/
6. Source code, tests, and KPI as executable evidence

Before changing code, inspect:
1. current branch and base branch
2. README.md
3. PROJECT_MEMORY.md
4. Prompt_Guide.md
5. skills/README.md
6. relevant specialist skills
7. current sprint specification/task
8. relevant source files
9. relevant tests
10. relevant KPI

First report:
- branch and base
- current development phase
- implemented capabilities
- unresolved defects
- relevant files
- tests/KPI available
- architectural risks

Do not code during initial orientation.

Permanent architecture:
- quantitative engine measures facts
- intelligence layer interprets external context
- decision engine evaluates evidence
- CHEAP ≠ BUY
- VALUATION ≠ MOMENTUM
- CANDIDATE DECISION ≠ FINAL DECISION
- NEWS ≠ MARKET DATA
- LLM ≠ MARKET CALCULATION
- UNKNOWN is preferable to fabricated data
- preserve existing fallbacks
- Telegram is the cockpit, not the brain

SP-A deterministic baseline:
Valuation → Premium Direction → Momentum → Market Structure → Conflict → Candidate → Hysteresis → Final Decision

Live Wing:
User-triggered /Update → current market observation → response

Analysis Wing:
Scheduled run → canonical observations → technical/context analysis → analysis snapshot → Neon

Do not use arbitrary user /Update requests as the future learning time series.
Do not implement SP-C prediction/learning unless the current task explicitly authorizes it.

After orientation, execute only the current task scope.
```
