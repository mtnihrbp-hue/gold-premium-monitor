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
| `C14C_IMPLEMENTATION.md` | Verified C14C implementation reference, KPI boundary, and supporting operational news-ingestion work |
| `RESEARCH_ADOPTION.md` | External research boundaries |
| `Prompt_Guide.md` | AI engineering operating rules |
| `.project_state.json` | Machine continuity state mirror |

## Source ownership rules

- `PROJECT_MEMORY.md` remains the single architectural source of truth.
- Sprint status belongs to `MASTER_PLAN_STATUS.md`; other documents reference it rather than duplicate milestone state.
- C14 documents define implementation contracts and do not replace architecture authority.
- `C14C_IMPLEMENTATION.md` records verified C14C implementation scope and supporting operational work; it does not create a competing architecture source.
- C14 terminology and feedback decisions are maintained inside the C14 handoff contract.
- Neon ownership remains governed by schema and migration discipline.

## Current verified state

```text
C14A  COMPLETE — 26/26 KPI
C14B  COMPLETE — 36/36 KPI
C14C  COMPLETE — 21/21 KPI
```

C14C is the **Adaptive Intelligence Foundation**. It is downstream of C14B and remains diagnostic/analytical. It does not introduce reinforcement learning, online learning, automatic model-weight changes, LLM decision authority, or BUY/SELL authority changes.

### C14C supporting work — operational news ingestion

The existing RSS collector, deterministic event classifier, repository persistence, and downstream snapshot consumer are now wired through a thin runtime ingestion orchestrator. The runtime invokes news ingestion before `build_analysis_snapshot()`.

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

The forecast runtime remains data-gated: current `1h`, `6h`, and `24h` forecasts may return `INSUFFICIENT_DATA` while chronological production history is sparse. This is expected and must not be bypassed by lowering sufficiency controls.

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
