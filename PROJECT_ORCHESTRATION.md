# Gold Premium Monitor — Project Orchestration Protocol

This document defines the project-continuity and cross-system orchestration workflow. It complements `PROJECT_MEMORY.md` and `.project_state.json` and is intended to prevent state loss when work moves between conversations, AI developers, GitHub, and Neon.

## Canonical orchestration loop

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

This sequence is mandatory for every implementation phase, including phases with no database change. A schema audit must explicitly establish that no migration is required when none is needed.

## Responsibility

The orchestration layer verifies that implementation, repository state, database state, executable evidence, and documentation describe the same project state.

KIMI is the implementation agent. GitHub is the source-of-truth repository. Neon is the live persistence system. `PROJECT_MEMORY.md` is the canonical project architecture/state document. `.project_state.json` is the machine-readable continuity ledger.

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
→ documentation
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
python kpi\kpi_pre_sp_c11.py
```

For regression, run the previously required KPI suites explicitly rather than relying on a Windows shell wildcard.

`python kpi\kpi_pre_sp_c*.py` should not be treated as the authoritative Windows CMD execution method for the whole suite.

## KPI engineering standard

KPI suites are executable specifications, not decorative pass/fail wrappers.

Before writing a KPI:

1. Inspect the production implementation and identify the true source of each expected value.
2. Seed fixtures through the same structural contracts the production code consumes.
3. Mutate authoritative source inputs when testing state transitions.
4. Let production code derive computed metadata such as completeness, status, labels, or classifications.
5. Never mutate a derived metadata field in the fixture and expect production code to trust it when production code recomputes that field.
6. Use deep copies when mutating nested JSON structures so tests cannot accidentally mutate shared fixture state.
7. A KPI failure caused by a fixture that contradicts production semantics is a KPI defect first, not automatically a product defect.
8. Do not weaken production logic merely to satisfy an incorrectly constructed KPI.

The C.10 and C.11 KPI failures exposed this exact pattern. C.10/C.11 now serve as the reference standard: tests must manipulate authoritative analytical inputs and assert the classifier/interface's actual derived result.

## New-conversation onboarding

A new AI session must read, in order:

```text
.project_state.json
→ PROJECT_MEMORY.md
→ README.md
→ Prompt_Guide.md
→ PROJECT_ORCHESTRATION.md
→ skills/
→ relevant source / tests / KPI / SQL
```

Conversation history is context, not project proof. Repository files, executable verification, and live database inspection establish current truth.

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

Every implementation handoff to KIMI must state:

```text
CURRENT VERIFIED STATE
ARCHITECTURAL CONTRACT
EXACT CHANGE SURFACE
DATABASE CONTRACT
KPI CONTRACT
REGRESSION REQUIREMENTS
NON-GOALS
ACCEPTANCE CRITERIA
```

For KPI sections specifically, KIMI must also state:

```text
AUTHORITATIVE SOURCE INPUTS
DERIVED FIELDS
FIXTURE CONSTRUCTION RULES
EXPECTED FAILURE MODES
NO-METADATA-HARDCODING RULE
```

KIMI completion evidence must identify:

```text
FILES CHANGED
TESTS
KPI
DATABASE IMPACT
COMMIT
DOCUMENTATION STATE
REMAINING ISSUES
```

## State synchronization rule

When a phase changes status, update both:

```text
PROJECT_MEMORY.md
.project_state.json
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
```

C.10 establishes deterministic analytical read-model retrieval, completeness classification, historical reconstruction, provenance preservation, decision preservation, and no-current-data / no-future-data leakage.

C.11 establishes a stable consumer envelope over C.10 for downstream Telegram/API/dashboard consumers without creating another calculation or decision layer.

## Next planned phase

```text
PRE-SP-C.12 — Historical Feature Dataset and Leakage-Safe Labeling Layer
```

The purpose of C.12 is to create a deterministic, historical, model-ready dataset contract from persisted C.8 features plus retrospectively available C.5 outcomes, with strict point-in-time and label-horizon discipline.

C.12 is still feature/dataset infrastructure. It does not train a prediction model.
