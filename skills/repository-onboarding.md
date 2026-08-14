# Repository Onboarding Skill

## Purpose

Use this when starting a new AI-development conversation or when repository context may be stale.

## Orientation sequence

1. Identify the current branch.
2. Identify its base/stable branch.
3. Read `README.md`.
4. Read `PROJECT_MEMORY.md`.
5. Read `Prompt_Guide.md` if it still contains active guidance.
6. Read `skills/README.md` and the relevant specialist skills.
7. Inspect the current sprint specification/task.
8. Inspect the relevant implementation files.
9. Inspect relevant tests and KPI checks.
10. Compare the current branch against its base when behavior depends on recent changes.

## Do not code during orientation

First produce a compact state report:

- branch
- base branch
- current sprint
- implemented capabilities
- unresolved issues
- relevant files
- available tests/KPIs
- risks or inconsistencies

Then proceed only within the explicit task scope.

## Source-of-truth rule

The repository is the implementation source of truth.

Conversation history is context, not proof.

If repository behavior contradicts an earlier conversation claim, report the discrepancy and follow the current approved repository/task specification.

## New conversation rule

Assume the previous AI conversation may not be available.

Reconstruct enough context from the repository before making changes.

Do not ask the user to repeat information that is already documented in the repository.
