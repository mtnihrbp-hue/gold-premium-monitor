# Branch Management Skill

## Goal

Keep `main` stable while allowing isolated sprint work.

## Simple model

Think of branches as copies of the project at different stages.

```text
main
  = stable version

SP-A
  = Sprint A work

SP-A-Edited
  = refinement of SP-A

SP-B
  = Sprint B work after SP-A is merged
```

## For normal sprint work

1. Start from `main`.
2. Create the sprint branch, for example `SP-B`.
3. Work only on that branch.
4. Run tests and KPI.
5. Review the diff.
6. Merge the sprint into `main` only after approval.

## For refinement work

If a sprint is not yet ready to merge:

```text
SP-A
  ↓
SP-A-Edited
```

Do the refinements on `SP-A-Edited`.

After verification, merge the approved changes back into `SP-A` or use the approved branch as the final merge source, according to the user's workflow.

## Beginner rule

Never make changes directly on `main` unless the user explicitly asks for that.

Never delete a branch to solve a problem.

Never force-push unless explicitly approved.

If a branch has diverged from its base, stop and inspect the differences before merging.

## Useful commands

```bash
# See current branch
git branch --show-current

# See changed files
git status

# See changes
git diff

# Switch branch
git switch SP-A-Edited

# Update local view of remote branches
git fetch origin

# Compare current branch with main
git diff main...SP-A-Edited
```

## Safe merge rule

Before merging:

```text
correct branch
+ tests pass
+ KPI passes
+ diff reviewed
+ no accidental files
= ready to merge
```
