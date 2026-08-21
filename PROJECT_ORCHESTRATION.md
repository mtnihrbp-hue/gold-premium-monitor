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
