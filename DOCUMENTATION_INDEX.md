# Documentation Index

Which file owns which fact. A fact is updated in the file that owns it, and other files point to it
rather than repeat it. The reading order and the conflict rule are in `PROJECT_MEMORY.md` section 1
(and `CLAUDE.md`).

Consolidated on 2026-10-16 (`SP_D_HANDOFF.md` section 37.9): five files each stated an authority order,
and they differed. The superseded files are in `archive/`.

## Live documents

| Document | Owns |
|---|---|
| `.project_state.json` | Machine-readable state: branch, tags, production, KPI evidence, open items |
| `PROJECT_MEMORY.md` | The system as it runs: purpose, surfaces, the run, the data's meaning, decisions, the measured record, the defects index, how work is done. Highest authority |
| `SP_D_HANDOFF.md` | SP-D, open: its sub-sprints, research, contracts, builds and their evidence, dated |
| `SP_C_HANDOFF.md` | SP-C and the pre-SP-D hotfixes on `main`, closed. Cited for the valuation basis (15.1), the deep-discount level (24), the valuation leg (26), confirmation (37, 38) and the stale-quote rules (39, 44, 45) |
| `PROJECT_OPERATIONS.md` | The runtime: cron-job.org, the workflows and their modes, Cloudflare, the routine health check (15), the Iran-side node (16) |
| `LESSONS_LEARNED.md` | The defect patterns met in production, as patterns. Appended to when a new class is found |
| `RESEARCH_ADOPTION.md` | Which external research was adopted, and its boundaries |
| `CLAUDE.md` | Claude Code's entry point: commands, the architecture's load-bearing rules, pointers here |
| `README.md` | A short orientation for a person |
| `skills/` | How an agent works here: engineering, onboarding, sprints, and the specialist rules |
| `sql/neon_schema.sql` | The target schema |
| `sql/neon_migration_*.sql` | Incremental migrations for the live database |
| `src/`, `tests/`, `kpi/`, CI | Executable evidence, which outranks every document |

## Archive

Superseded and kept unchanged in `archive/`, so a citation in a handoff still resolves. Nothing there
describes the current system.

| Document | Was | Superseded by |
|---|---|---|
| `archive/PROJECT_MEMORY_HISTORY.md` | `PROJECT_MEMORY.md` to 2026-10-15: SP-A to SP-C, the PRE-SP-C phases, the C.14 research, the SP-C changelog, the full defects list | `PROJECT_MEMORY.md` |
| `archive/MASTER_PLAN_STATUS.md` | Milestone status to C.14C and UPDATE v1 | `.project_state.json` and the sub-sprint table of `SP_D_HANDOFF.md` |
| `archive/PROJECT_ORCHESTRATION.md` | The continuity protocol, the C.14 boundaries, the forecast readiness gate, a KIMI handoff template | `PROJECT_MEMORY.md` 1 and 10; `skills/validation-and-release.md` |
| `archive/Prompt_Guide.md` | Generic AI engineering behaviour | `skills/core-engineering.md` |
| `archive/C14_HANDOFF.md` | The C.14A and C.14B contracts: candles, forecast features, terminology | parked with the Analysis Wing (`PROJECT_MEMORY.md` 3) |
| `archive/C14C_HANDOFF.md` | The C.14C contract: forecast resolution, error analysis, human review | as above |
| `archive/C14C_IMPLEMENTATION.md` | C.14C's verified scope, news ingestion's wiring, UPDATE v1's boundary | as above |
| `archive/UPDATE_V1_IMPLEMENTATION.md` | UPDATE v1's first build | `SP_C_HANDOFF.md` 15, 18 and the locked layout in `alerts/telegram_update_v1.py` |

Bringing back a parked part of the Analysis Wing means reading its contract here first.

## Rules

- A sprint's record goes into its handoff. SP-D sections are never added to `SP_C_HANDOFF.md`.
- `PROJECT_MEMORY.md` changes when what runs changes, and `.project_state.json` with it.
- No new top-level status or architecture document. A superseded file moves to `archive/` unchanged.
- A handoff's citation of an archived file stays as written: the file name still finds it.
