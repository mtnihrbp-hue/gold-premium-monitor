# Sprint Execution Skill

## Purpose

Keep sprint work isolated, measurable, reversible, and independently verifiable.

## Branch model

```text
main                      production; cron-job.org and the worker dispatch ref main
 └── SP-D                 the current sprint (SP-A to SP-C are merged and closed)
      └── sp-de           the current sub-sprint, one branch each (SP-Da ... SP-De)
           └── sp-de-*    short-lived topic branches, when useful
```

Never develop directly on `main`. A defect found in production is fixed on a short branch cut from
`main`, reviewed the same way.

The sub-sprints and their merges are listed at the top of `SP_D_HANDOFF.md`.

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

The owner reviews the work, including any new message's layout, before it reaches `main`.

A batch reaches SP-D and `main` by fast-forward, and **`main` is tagged with a safe tag first**
(`v1.24safe` the latest), pushed before the merge, so production always has an instant rollback point.

Standing authorization (owner, 2026-10-15): work the owner has approved is tagged and pushed to SP-D
and `main` without asking again. It covers the push, not the approval: work the owner has not
approved still waits.

Before merge, verify the branch is based on the intended stable branch and reconcile any newer commits deliberately.

## Rollback discipline

Avoid squashing unrelated work into sprint branches.

Keep commits understandable enough that a failed sprint can be reverted or the branch abandoned without damaging `main`.
