# Validation and Release Skill

## Purpose

Prevent AI developers from declaring work complete without objective evidence.

## Required verification layers

### 1. Syntax

```bash
python -m compileall src
```

### 2. Imports

Explicitly verify application/module imports used by the production entry point.

### 3. Targeted tests

Run tests for the changed behavior first.

### 4. Regression suite

Run the repository's full test suite.

### 5. KPI

Run the current sprint KPI.

A KPI must verify behavior, not file existence.

### 6. Diff review

Inspect:

```bash
git status
git diff
```

and verify every changed file is intentional.

### 7. Branch state

Confirm:

- current branch
- intended base branch
- commits ahead/behind if relevant
- no accidental changes

## Completion rule

Never claim `COMPLETE` when any mandatory check fails.

Use explicit results:

```text
PASS
FAIL
UNKNOWN
NOT RUN
```

## KPI quality

Bad:

```text
file exists → PASS
```

Good:

```text
fixture input
→ execute real behavior
→ verify expected output
→ PASS
```

## Regression discipline

A fix for one issue must not weaken unrelated tests.

If a test expectation changes because approved behavior changed, document why.

## Release gate

A sprint is ready for merge only when:

```text
implementation
AND tests
AND KPI
AND documentation
AND diff review
AND branch review
```
all pass.

If any part is missing, the correct status is not complete.
