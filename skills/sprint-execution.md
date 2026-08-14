# Sprint Execution Skill

## Purpose

Keep sprint work isolated, measurable, reversible, and independently verifiable.

## Branch model

```text
main
 ├── SP-A
 │    └── SP-A-Edited
 ├── SP-B
 └── SP-C
```

Use a dedicated branch for each sprint or approved refinement branch.

Never develop directly on `main`.

A refinement branch may sit under a sprint branch when the parent sprint is not yet ready to merge.

## Execution order

```text
scope
→ design
→ implement
→ test
→ KPI
→ review diff
→ merge
```

Do not start the next sprint until the current sprint has passed its KPI.

## Scope discipline

Every sprint has explicit non-goals.

Do not add future sprint functionality because it appears useful while implementing the current sprint.

Log deferred ideas rather than implementing them.

## Definition of done

A sprint is complete only when:

- intended behavior is implemented
- regression tests pass
- new tests pass
- KPI passes
- required documentation is updated
- branch diff is reviewed
- no accidental files are changed
- working tree/branch state is understood

## Merge discipline

The user reviews the sprint branch before merge.

Do not merge automatically.

Before merge, verify the branch is based on the intended stable branch and reconcile any newer commits deliberately.

## Rollback discipline

Avoid squashing unrelated work into sprint branches.

Keep commits understandable enough that a failed sprint can be reverted or the branch abandoned without damaging `main`.
