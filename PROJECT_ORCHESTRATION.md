# Gold Premium Monitor — Project Orchestration Protocol

This document defines the project-continuity and cross-system orchestration workflow. It complements `PROJECT_MEMORY.md`, `.project_state.json`, and `PROJECT_OPERATIONS.md` and is intended to prevent state loss when work moves between conversations, AI developers, GitHub, Neon, external scheduling, and Cloudflare.

## Canonical project orchestration loop

```text
KIMI code
   ↓
GitHub source
   ↓
schema/migration audit
   ↓
Neon production state
   ↓
KPI / smoke
   ↓
documentation
   ↓
.project_state.json
   ↓
commit
```

This sequence is mandatory for every implementation phase, including phases with no database change.

## Runtime control-plane loop

The project also has a separate operational chain:

```text
cron-job.org / Telegram
        ↓
Cloudflare secure interconnection
        ↓
GitHub Actions
        ↓
SP-B execution
        ↓
Analysis Wing or Live Wing
        ↓
Neon / Telegram
```

`PROJECT_OPERATIONS.md` is the operational authority for this control plane.

## Responsibility

The orchestration layer verifies that implementation, repository state, database state, executable evidence, documentation, and external runtime state describe the same project state.

KIMI is the implementation agent. GitHub is the source-of-truth repository. Neon is the live persistence system. `PROJECT_MEMORY.md` is the canonical project architecture/state document. `.project_state.json` is the machine-readable continuity ledger. `PROJECT_OPERATIONS.md` records runtime scheduling and external-control details.

## Phase completion rule

A phase is not complete merely because code exists or a KPI passes.

Completion requires synchronized:

```text
implementation
→ targeted tests
→ regression
→ KPI
→ schema/migration audit
→ Neon production state
→ runtime/operational state when relevant
documentation
→ .project_state.json
→ commit
```

## Local KPI verification routine

Normal local verification should begin from the current SP-B branch:

```cmd
git pull origin SP-B
```

Then run the target KPI explicitly:

```cmd
python kpi\kpi_pre_sp_cX.py
```

For regression, run the previously required KPI suites explicitly rather than relying on a Windows shell wildcard.

`python kpi\kpi_pre_sp_c*.py` should not be treated as the authoritative Windows CMD execution method for the whole suite.

## KPI engineering standard

KPI suites are executable specifications, not decorative pass/fail wrappers.

Before writing a KPI:

1. Inspect the production implementation and identify the true authoritative source of each expected value.
2. Define the canonical contract and field names before writing fixtures.
3. Seed fixtures through the same structural contracts the production code consumes.
4. Mutate authoritative source inputs when testing state transitions.
5. Let production code derive computed metadata such as completeness, status, labels, or classifications.
6. Never mutate a derived metadata field in the fixture and expect production code to trust it when production code recomputes that field.
7. Use deep copies when mutating nested JSON structures.
8. A KPI failure caused by a fixture that contradicts production semantics is a KPI defect first, not automatically a product defect.
9. Do not weaken production logic merely to satisfy an incorrectly constructed KPI.

C.10, C.11, and C.12 are the reference examples for this rule.

## New-conversation onboarding

A new AI session must read, in order:

```text
.project_state.json
→ PROJECT_MEMORY.md
→ README.md
→ Prompt_Guide.md
→ PROJECT_ORCHESTRATION.md
→ PROJECT_OPERATIONS.md
→ skills/
→ relevant source / tests / KPI / SQL
```

Conversation history is context, not project proof. Repository files, executable verification, live database inspection, and operational-system inspection establish current truth.

## Database discipline

Never assume repository SQL and Neon production are synchronized.

For every schema-affecting phase:

1. Inspect the live Neon production schema.
2. Compare it with repository migration/schema intent.
3. Prepare an incremental migration when required.
4. Test the migration on a temporary Neon branch.
5. Apply only after authorization.
6. Verify production schema after application.
7. Record the resulting database state in project documentation and `.project_state.json`.

When no schema change is required, record that explicitly.

Never use the complete target schema as a destructive replacement for an existing production database.

## Handoff discipline

Every implementation handoff to KIMI must state only the information needed to execute the current phase:

```text
CURRENT STATE
CURRENT CONTRACT
CHANGE SURFACE
DATABASE IMPACT
KPI CONTRACT
REGRESSION REQUIREMENTS
NON-GOALS
ACCEPTANCE CRITERIA
```

Avoid generic architecture repetition when the canonical documents already contain it.

For KPI sections specifically:

```text
AUTHORITATIVE SOURCE INPUTS
CANONICAL FIELD NAMES
DERIVED FIELDS
FIXTURE CONSTRUCTION RULES
EXPECTED FAILURE MODES
```

KIMI completion evidence must identify:

```text
FILES CHANGED
TESTS
KPI
DATABASE IMPACT
RUNTIME IMPACT
COMMIT
DOCUMENTATION STATE
REMAINING ISSUES
```

## State synchronization rule

When a phase or runtime component changes status, update:

```text
PROJECT_MEMORY.md
.project_state.json
PROJECT_ORCHESTRATION.md
PROJECT_OPERATIONS.md when operational state changes
```

Update `README.md` when the human-facing architecture or current development position changes.

Do not create competing architecture-status documents.

## Current verified milestones

```text
PRE-SP-C.10 COMPLETE
KPI: 22/22 PASS
DATABASE CHANGE: NONE

PRE-SP-C.11 COMPLETE
KPI: 25/25 PASS
DATABASE CHANGE: NONE

PRE-SP-C.12 COMPLETE
KPI: 30/30 PASS
DATABASE CHANGE: NONE
```

C.10 establishes deterministic analytical read-model retrieval, completeness classification, historical reconstruction, provenance preservation, decision preservation, and no-current-data / no-future-data leakage.

C.11 establishes a stable consumer envelope over C.10 for downstream Telegram/API/dashboard consumers without creating another calculation or decision layer.

C.12 establishes a deterministic historical feature dataset and leakage-safe labeling contract for future model training.

## Next planned phase

```text
PRE-SP-C.13 — Analysis Wing Operationalization + Telegram Analytical Commands + Scheduler/cron Integration
```

C.13 must operationalize the existing Analysis Wing, establish the external scheduler control plane, expose analytical Telegram commands, and preserve Live Wing isolation.

C.13 must not implement forecasting.
