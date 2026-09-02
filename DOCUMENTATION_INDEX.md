# Documentation Index — SP-B

This file is the navigation authority for repository documentation. It identifies ownership boundaries and prevents overlapping architectural sources.

## Authority hierarchy

| Document | Responsibility |
|---|---|
| `PROJECT_MEMORY.md` | Canonical architecture and current project state authority |
| `README.md` | Human onboarding overview and repository navigation |
| `MASTER_PLAN_STATUS.md` | Milestone and delivery status tracking |
| `PROJECT_ORCHESTRATION.md` | Continuity protocol and synchronization workflow |
| `PROJECT_OPERATIONS.md` | Operational control plane |
| `C14_HANDOFF.md` | C14A/C14B contracts, terminology, feedback, and audit rules |
| `C14C_HANDOFF.md` | C14C architecture and implementation contract |
| `C14C_IMPLEMENTATION.md` | Verified C14C implementation reference, KPI boundary, supporting operational news-ingestion work, and UPDATE v1 wing-boundary record |
| `RESEARCH_ADOPTION.md` | External research boundaries |
| `Prompt_Guide.md` | AI engineering operating rules |
| `.project_state.json` | Machine continuity state mirror |

## Source ownership rules

- `PROJECT_MEMORY.md` remains the single architectural source of truth.
- Sprint status belongs to `MASTER_PLAN_STATUS.md`; other documents reference it rather than duplicate milestone state.
- C14 documents define implementation contracts and do not replace architecture authority.
- `C14C_IMPLEMENTATION.md` records verified C14C implementation scope and the subsequent UPDATE v1 surgical boundary; it does not create a competing architecture source.
- C14 terminology and feedback decisions are maintained inside the C14 handoff contract.
- Neon ownership remains governed by schema and migration discipline.
- UPDATE v1 presentation is a consumer concern; it must not become a second analytical or decision authority.

## Current verified state

```text
C14A  COMPLETE — 26/26 KPI
C14B  COMPLETE — 36/36 KPI
C14C  COMPLETE — 21/21 KPI
UPDATE v1  SURGICAL IMPLEMENTATION / VALIDATION
```

C14C is the **Adaptive Intelligence Foundation**. It is downstream of C14B and remains diagnostic/analytical. It does not introduce reinforcement learning, online learning, automatic model-weight changes, LLM decision authority, or BUY/SELL authority changes.

### C14C supporting work — operational news ingestion

The existing RSS collector, deterministic event classifier, repository persistence, and downstream snapshot consumer are wired through a thin runtime ingestion orchestrator. The runtime invokes news ingestion before `build_analysis_snapshot()` on the scheduled ANALYZE path.

The supporting work is operational plumbing only:

```text
configured RSS sources
→ collect / normalize
→ classify
→ existing deduplicate
→ persist `news_events`
→ downstream news context
```

Source failures are non-blocking. No new table, migration, LLM, event-impact learning, or decision authority was introduced.

Neon verification for the C14C foundation and supporting work remains **no migration required**. Existing production/history data remains intact.

### UPDATE v1 — current operational boundary

UPDATE is user-triggered and intentionally lightweight. It does not execute the full ANALYZE pipeline merely to produce a Telegram update.

```text
USER /UPDATE
→ current collection
→ validation
→ canonical observation persistence
→ minimum current calculations
→ SP-A current state
→ RUN/DAY baseline resolution
→ Telegram
```

During the current transition period:

```text
RUN = current observation vs latest previous canonical market snapshot
DAY = current observation vs first canonical market snapshot of today
```

When the Analyze wing is fully operational, DAY may move to the first controlled Analyze-wing collection of the day without changing the UPDATE presentation contract.

UPDATE v1 currently exposes:

```text
MARKET
PRICE/BUBBLE DYNAMICS
MARKET STRUCTURE
PLATFORMS
CURRENT DECISION
```

Price Pace and Bubble Pace remain deferred where historical evidence is insufficient. Bubble movement uses the existing 0.05 percentage-point convention and is not empirically calibrated.

The current UPDATE surgery requires **no Neon migration**.

## Continuity loading order

```text
.project_state.json
→ PROJECT_MEMORY.md
→ DOCUMENTATION_INDEX.md
→ README.md
→ MASTER_PLAN_STATUS.md
→ PROJECT_ORCHESTRATION.md
→ PROJECT_OPERATIONS.md
→ C14 contracts
→ research and AI guidance
→ C14C_IMPLEMENTATION.md
```

## Post-C14 direction

The next major phase is not another blind implementation sprint. The intended sequence is:

```text
production history accumulation
→ empirical research
→ identify actual forecasting bottleneck
→ evidence/analytical improvements where justified
→ Expert Judgment System design
→ implementation only after scope lock
```

Potential future ETF money-flow data is a deferred extension, not part of current UPDATE v1 scope.
