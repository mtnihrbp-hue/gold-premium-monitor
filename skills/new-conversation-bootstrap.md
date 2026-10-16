# New Conversation Bootstrap

Use this prompt when starting a fresh AI-development session.

```text
You are continuing work on Gold Premium Monitor, a decision-support system for the Iranian
18K physical-gold market. It informs one reader on Telegram; it executes nothing.

Repository:
https://github.com/mtnihrbp-hue/gold-premium-monitor

The repository is the implementation source of truth. Do not assume prior conversation context exists.

Read, in order (PROJECT_MEMORY.md section 1):
1. .project_state.json           branch, tags, production, open items
2. PROJECT_MEMORY.md             the system as it runs; highest authority
3. SP_D_HANDOFF.md               the current sprint: its sub-sprint table, then the latest sections
4. PROJECT_OPERATIONS.md         the runtime, when the task touches it
5. LESSONS_LEARNED.md            the defect patterns met in production
6. skills/: core-engineering, repository-onboarding, sprint-execution, then the specialist skill
7. the relevant source, tests, KPI and SQL

Executable evidence outranks prose. archive/ holds superseded documents only.

First report:
- branch and base
- the current sub-sprint and what it has merged
- production's state (is Neon reachable; what is parked)
- unresolved defects (PROJECT_MEMORY.md section 9)
- relevant files, tests and KPIs
- risks

Do not code during initial orientation.

Permanent rules:
- CHEAP ≠ BUY; VALUATION ≠ MOMENTUM; CANDIDATE ≠ FINAL DECISION; NEWS ≠ MARKET DATA;
  LLM ≠ MARKET CALCULATION; PREDICTION ≠ FACTS
- UNKNOWN is preferable to fabricated data; preserve existing fallbacks
- final_decision is the only BUY/SELL alert authority
- the number a reader is shown is the number the system acts on
- every workflow run is production, on any branch
- research, preview, lock, wire, document; never change an agreed layout without the owner
- count episodes, not days; compare with a control; show the sample size

After orientation, execute only the current task scope.
```
