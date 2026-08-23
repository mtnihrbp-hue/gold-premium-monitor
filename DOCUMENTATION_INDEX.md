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
| `C14_HANDOFF.md` | C14A/C14B implementation contracts |
| `C14C_HANDOFF.md` | C14C implementation contract |
| `C14_FEEDBACK_AND_TERMINOLOGY.md` | C14 terminology and feedback contract |
| `RESEARCH_ADOPTION.md` | External research boundaries |
| `Prompt_Guide.md` | AI engineering operating rules |
| `.project_state.json` | Machine continuity state mirror |

## Source ownership rules

- `PROJECT_MEMORY.md` remains the single architectural source of truth.
- Sprint status belongs to `MASTER_PLAN_STATUS.md`; other documents should reference it rather than duplicate milestone state.
- C14 documents define implementation contracts and do not replace architecture authority.
- Neon ownership remains governed by schema and migration discipline.

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
```
