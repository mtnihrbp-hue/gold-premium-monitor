# Branch Management Skill

## Goal

Keep `main` stable while allowing isolated sprint work.

## Simple model

Think of branches as copies of the project at different stages.

```text
main
  = production

SP-D
  = the current sprint

sp-de
  = the current sub-sprint (SP-De), cut from SP-D
```

## For normal sprint work

1. Work on the sub-sprint's branch (`sp-de`), or a topic branch cut from it.
2. Run the unit tests and the KPI suite.
3. Review the diff.
4. After the owner's approval: tag `main` with the next safe tag, push the tag, then fast-forward
   SP-D and `main` to the branch (`sprint-execution.md`).

## For a production defect

Cut a short branch from `main`, fix, test, and fast-forward `main` after review, with a safe tag
first; then bring SP-D up to it.

## Beginner rule

Never make changes directly on `main` unless the user explicitly asks for that.

Never force-add git-ignored data to a temporary branch and then switch away from it: switching to a
branch that does not track the files deletes them from the working tree (a year of Telegram posts,
2026-10-15, restored from the commit). Commit such data from a separate `git worktree`, and take
results back with `git show origin/<branch>:<path>`, never a checkout.

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
git switch sp-de

# Update local view of remote branches
git fetch origin

# Compare current branch with main
git diff origin/main...sp-de
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
