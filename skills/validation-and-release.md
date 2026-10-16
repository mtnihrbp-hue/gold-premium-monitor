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

Run the repository's full test suite:

```bash
python tests/run_all.py     # the unit tests
python kpi/run_all.py       # every KPI file, each in its own process, in-memory database
```

Both run in CI (`kpi-suite.yml`). Prefer the runners to single files: they force UTF-8, without
which a passing KPI reports a failure on Windows.

### 5. KPI

Run the current sprint KPI.

A KPI must verify behavior, not file existence. An assertion that spans two modules belongs in
`kpi/kpi_coherence.py`.

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

A phase is not complete while `.project_state.json` or the documents disagree with the executable
evidence.

**Production liveness.** A KPI passes against fixtures and cannot see a component the runtime never
reaches, or one that runs on no usable data. Record how many real production cases a component has
processed. If none, it is `IMPLEMENTED`, not `COMPLETE`.
- The C.14C news collector was built and never reached.
- The Analyze trigger was misrouted.
- The decision scorecard was built and never called from `main`.

Use explicit results:

```text
PASS
FAIL
UNKNOWN
NOT RUN
```

## KPI quality

**A check must be seen to fail.** Before relying on a new check, feed it a known offender.
`kpi_coherence.test_27` passed for weeks because it searched text in which its target never
appeared (`SP_D_HANDOFF.md` 37.8). A check that has never rejected anything is quoted as evidence,
and it is none.

Writing a KPI:
1. identify the production contract and its inputs;
2. build fixtures through the same contracts production consumes;
3. let production logic derive statuses and labels; never hard-code a derived field;
4. use `deepcopy` for nested mutations;
5. never change production semantics to satisfy a malformed KPI;
6. include leakage tests for anything historical or model-ready.

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

If a test expectation changes because approved behavior changed, document why, in the test and in
the handoff.

A passing new KPI does not prove regression safety: run the prior suites and the unit tests too.

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
