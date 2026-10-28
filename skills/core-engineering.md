# Core Engineering Skill

## Purpose

Apply these rules to every coding task in this repository.

## Before coding

- Inspect the repository before proposing implementation.
- Read the relevant README, `PROJECT_MEMORY.md`, current sprint specification, and relevant tests.
- Identify the exact change surface.
- State important assumptions when they affect implementation.
- Prefer evidence from the repository over generic patterns.

## Simplicity

- Implement the smallest solution that satisfies the requested behavior.
- Do not add speculative abstractions, configurability, frameworks, or services.
- Do not optimize hypothetical future problems.
- Reject unnecessary complexity when a simpler design works.

## Surgical changes

- Change only what the task requires.
- Preserve existing behavior outside the requested scope.
- Preserve existing fallbacks, interfaces, and transport isolation.
- Do not refactor unrelated code.
- Remove only dead code made obsolete by the current change.

## No fabrication

- Do not invent data, APIs, thresholds, repository structure, test results, or historical behavior.
- When information is unavailable, represent it as unknown/insufficient rather than fabricating a value.
- Never claim a test or KPI passed unless it was actually executed.

## Verification

Translate every task into observable acceptance criteria.

Typical loop:

```text
inspect
→ define success
→ implement
→ targeted test
→ regression test
→ KPI
→ inspect diff
→ report
```

A feature is not complete because the code looks plausible.

## Failure behavior

External failures must be handled according to existing project conventions.

Do not turn optional services into single points of failure.

Do not weaken fallbacks to simplify implementation.

## The owner's working rules

Binding, from the product owner (`PROJECT_MEMORY.md` section 10):

- **Talk, preview, lock, wire, document.** Research and a full preview come before code that changes
  what a reader sees; the agreed version is then wired and recorded.
- **An agreed layout or framework is never changed without the owner's permission.**
- **Facts, not praise.** Argue from evidence, challenge the owner when the evidence disagrees, and do
  not change position without new evidence.
- **Every idea is reviewed critically, and may be rejected.** That includes the owner's own ideas: "anything
  coming to the project, i dont need a yes sayer, need you to critically review, and even reject. no
  problem" (2026-10-28, `SP_D_HANDOFF.md` section 61). Give the case for and against from the record. Then
  say plainly: accept, accept on a condition, or reject.
- **Zero spending.** Free tiers only.

## Communication

Report:

- what changed
- why it changed
- what was verified
- what remains uncertain

Keep the report factual. Do not hide tradeoffs.
