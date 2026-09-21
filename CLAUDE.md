# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project purpose

Gold Premium Monitor is a decision-support analytical intelligence system for the Iranian 18K physical-gold market. It combines Iranian gold-platform prices, XAU/USD, USD/IRR, fair-price calculation, premium/discount ("Bubble") behavior, momentum, market structure, deterministic regime detection, historical/news context, and a forecast pipeline. **It is not an autonomous trading bot and does not execute trades.**

## Required reading order (do this before implementing anything)

This repo's documentation is itself a strict authority hierarchy. A new session must reconstruct state from the repo, not from conversation memory:

```
.project_state.json      (machine-readable continuity/phase state)
→ PROJECT_MEMORY.md       (canonical architecture + current state — highest authority)
→ MASTER_PLAN_STATUS.md
→ DOCUMENTATION_INDEX.md
→ README.md
→ Prompt_Guide.md         (generic AI engineering behavior, not project state)
→ PROJECT_ORCHESTRATION.md
→ PROJECT_OPERATIONS.md   (runtime/scheduler/Cloudflare/cron-job.org control plane)
→ skills/                 (specialist operating rules, load only what's task-relevant)
→ relevant source / tests / KPI / sql
```

When docs conflict, `PROJECT_MEMORY.md` wins, then executable evidence (tests/KPI/production DB state) outranks any prose. Do not create new top-level status/architecture docs — update the existing authority file instead (see `DOCUMENTATION_INDEX.md` for exact ownership per file).

`skills/` load order for a fresh session: `core-engineering.md` → `repository-onboarding.md` → `sprint-execution.md` → then only the specialist skill for the current task (`market-analyst.md`, `telegram-product.md`, `data-and-neon.md`, `llm-news-intelligence.md`, `validation-and-release.md`, `branch-management.md`).

## Commands

Run everything from the repo root (test/KPI files use relative `sys.path.insert(0, "src")` or path relative to `__file__`).

Run the app locally (manual `/Update`-style run):
```
python src/main.py
```

Run a single test or KPI file (all use `unittest`, run directly — not via pytest):
```
python tests/test_momentum.py
python kpi/kpi_pre_sp_c14c.py
```

Run the entire KPI suite (26 files) — this is the regression check before calling any phase complete:
```
python kpi/run_all.py
```

It runs each suite in an isolated subprocess against an in-memory database and forces UTF-8 for child output. That last part matters on Windows: the KPI scripts print status emoji which raise `UnicodeEncodeError` under the console codepage *after* assertions pass, making a passing suite report as failed. Prefer the runner over invoking files individually.

Compile check (also run in CI):
```
python -m compileall src
```

Install deps:
```
pip install -r requirements.txt
```

CI workflows (`.github/workflows/`):
- `kpi-suite.yml` — full KPI suite + `compileall`, on SP-C pushes, PRs, and manual dispatch. Never given `DATABASE_URL`, so it cannot reach production Neon. Safe to run freely.
- `gold-monitor.yml` — the live app (`src/main.py`). **Not sandboxed on any branch**: it uses repository secrets, so running it from a feature branch still writes to production Neon and sends real Telegram messages. Treat every run as production.
- `test-task-c.yml` — runs two unit test files on manual dispatch.

Required environment variables (see `.github/workflows/gold-monitor.yml` and `src/database/connection.py`, `src/alerts/*`): `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `RESEND_API_KEY`, `EMAIL_TO`. `SCHEDULED_RUN=true` switches `src/main.py` from the lightweight UPDATE path into the full scheduled Analysis path.

## Architecture

### Two frontend wings (must stay architecturally separate)

**Live Wing** — user-triggered, current-state only, lightweight:
```
Telegram /Update → collect → validate → minimum calculation → current deterministic state → Telegram
```
Must NOT execute the full scheduled Analysis pipeline just to answer a user request.

**Analysis Wing** — scheduled (external `cron-job.org`, not GitHub's native `schedule`), builds the long-term historical/analytical record:
```
scheduled window → canonical observations → technical structure → regime
→ analysis_snapshots → outcome_evaluations → evidence package → interpretation
→ feature intelligence → analytical read model → downstream consumers
→ C.14A candles → C.14B forecast → C.14C forecast resolution/human review/audit
```

### Layered data-flow contract

```
FACTS (raw observations) → EVIDENCE (validated package) → INTERPRETATION (structured explanation)
→ FEATURES (deterministic model-ready artifacts) → READ MODEL (normalized downstream contract)
→ DECISION (current deterministic BUY/WAIT/SELL authority) → FUTURE PREDICTION (model output only)
```

Ownership: Collectors collect. Calculators calculate. Intelligence interprets. Feature builders derive. Read models organize. Presentation formats. Persistence stores. `UNKNOWN` / `INSUFFICIENT_DATA` are valid, preferred outputs over fabricated values.

### Time

Everything stored is UTC; everything displayed or grouped by day is Iran local time.
`src/timeutil.py` holds the single fixed UTC+3:30 offset (Iran abolished DST in 2022,
and the tz database is not reliably present on every runner). Never call
`datetime.now()` for a value a reader sees or for a day boundary — grouping by the
stored UTC date cuts each day at 03:30 local.

### Valuation basis

The discount shown to a reader is the mean of the three cheapest platforms
(`analysis/bubble_position.cheap_basis_price`). `market_snapshots.premium_percent` is
still computed from the single cheapest and is what the decision engine,
`outcome_evaluations` and `analysis_snapshots` consume. This split is deliberate and
documented in `SP_C_HANDOFF.md` section 15.1 — do not compare a displayed discount
against a stored one without accounting for it, and do not "fix" one to match the
other without the phase and approval that change requires.

### The deep-discount level

`Deep discount` appears in UPDATE, in ANALYZE and in the push, and it is one number.
It is resolved by `analysis/bubble_position.deep_discount_threshold()` at
`DEEP_DISCOUNT_PERCENTILE` over the pool returned by `reference_readings()` — settled
days, user rows excluded. `analyze_report.DEEP_ZONE_PERCENTILE` and
`push_trigger.FIRE_PERCENTILE` are aliases of that constant, not independent copies.

Until 2026-09-21 each surface chose its own rank and the same words carried 3.29% and
3.70% on the same day. Do not reintroduce a local rank, a local percentile formula, or
a second pool for this quantity — `kpi_sp_c4.test_23c` and `kpi_sp_c6.test_24d` read
the source to stop it. The rule: **the number a reader is shown is the number the
system acts on.** See `SP_C_HANDOFF.md` section 24.

`Bigger than X%` is a different question — it ranks the current reading and gates
nothing — so it keeps the scheduled-preference pool of `resolve_relative_valuation`.
That difference is deliberate and documented; it is not drift to be tidied up.

Thresholds that get compared against readings (`fire_at`, `rearm_at`, the deep-zone
threshold) are never rounded: gaps land on values like `8.999999999999996`, and
rounding to `9.0` excludes the readings the threshold was drawn from. Round at render.

### Cross-cutting coherence

`kpi/kpi_coherence.py` is the only KPI that checks modules **against each other**.
Every other file checks one module or one surface against the market, which is how 25
passing files coexisted with `Deep discount` meaning 3.29% in one message and 3.70% in
another. When you fix a defect that spans two modules, the assertion belongs there.

It also carries `ACCEPTED`, the register of divergences that are real and deliberately
unfixed — each naming what diverges, why, and the document that records it. **An entry
whose divergence has been fixed fails the suite**, which forces the register to be
retired rather than left asserting a state that no longer exists. Do not add an entry
to silence a failure; add one only with the approval that the underlying change needs.

Three entries are currently registered. Two more closed in SP-C.15, and closing them
failed the suite until they were retired — that is the mechanism working, not a bug.
See `SP_C_HANDOFF.md` §25 and §26.

### The valuation leg

`market_states.valuation_state` is the first input to the conflict matrix. It is a
**rank with a direction gate**, produced only by
`caluclator/valuation.classify_valuation`:

```
CHEAP       rank < CHEAP_PERCENTILE       AND  premium <= buy_premium_percent
EXPENSIVE   rank >= EXPENSIVE_PERCENTILE  AND  premium >= sell_premium_percent
FAIR        anything else
UNKNOWN     no rank — the matrix then abstains
```

The direction gate is load-bearing. A percentile-EXPENSIVE reading means "less
discounted than usual", **not** "above fair value", and the matrix turns
`EXPENSIVE + WEAKENING` into `SELL` — on rank alone this engine would sell a market
trading 1.6% *below* fair value. On the record the sell gate never opens, because the
highest premium ever stored is −1.52%. That is correct, not a dead bound to tidy away.

There is deliberately **no fixed-threshold fallback**: below `MIN_OBSERVATIONS` the
answer is `UNKNOWN`. A fallback that always answers is how this leg spent months
reading `CHEAP` on 364 of 364 rows. `build_signal_state` receives the state rather than
computing it, because ranking needs a session and a calculator must not open one.

It ranks the **stored** `premium_percent` against a window of stored `premium_percent`,
on the settled non-user pool. See `SP_C_HANDOFF.md` §26 and `LESSONS_LEARNED.md` §14.

### Degenerate classifiers

This codebase has produced four classifiers that emitted a single value for months
without error: `valuation_state=CHEAP`, `regime_state=PANIC`, `final_decision=WAIT`,
news `relevance=UNKNOWN`. Before trusting or reporting any categorical output, run
`SELECT <column>, COUNT(*) ... GROUP BY 1` against production. One row means the
column is a constant and any metric computed over it is meaningless. See
`LESSONS_LEARNED.md` sections 1-3.

### Non-negotiable invariants

These are enforced throughout the codebase and its KPIs — do not collapse them when implementing or reviewing:

```
CHEAP ≠ BUY
VALUATION ≠ MOMENTUM
CANDIDATE DECISION ≠ FINAL DECISION
NEWS ≠ MARKET DATA
LLM ≠ MARKET CALCULATION
EVIDENCE PACKAGE ≠ DECISION
READ MODEL ≠ DECISION AUTHORITY
PREDICTION ≠ FACTS / EVIDENCE / INTERPRETATION / FEATURES
```

`final_decision` (from the SP-A pipeline: Valuation → Premium Direction → Momentum → Market Structure → Conflict Matrix → Candidate Decision → SP-A Hysteresis → Final Decision) is the sole external BUY/SELL alert authority — legacy/candidate signals must never independently trigger an alert.

LLM/intelligence layers may summarize, interpret, and express uncertainty over already-validated evidence; they must never calculate fair price/premium/indicators, invent levels or stats, or acquire independent BUY/SELL authority.

Fail-safe law used throughout collection/analysis: on missing data, use a safe deterministic fallback with degraded provenance if one exists, otherwise return `INSUFFICIENT_DATA`/`ABSTAIN` — never silently extrapolate.

### Source layout

- `src/collector/` — per-platform Iranian gold price collectors (HoorGold, Parasteh, Daric, Taline, Ayyareh, Invi, MioGold, Eligold, Goldika, Milli, WallGold) plus `kitco.py` (XAU/USD), `bonbast.py` (USD/IRR), `news/` (RSS ingestion). Representative Iranian price fallback order is `Milli → Ayyareh → WallGold → UNKNOWN`; source failures must stay isolated from each other. Unit normalization (e.g. Toman→Rial) is a collector-level responsibility, not a market-model adjustment.
- `src/caluclator/` (sic — existing spelling, keep it) — deterministic market math: fair price, premium/bubble, momentum, signal/decision state, trends, structure, conflict resolution.
- `src/validation/` — input validation gates before values enter calculation.
- `src/analysis/` — the Analysis Wing pipeline: scheduler, snapshot builder, regime detection, structure, outcome evaluation, runner.
- `src/intelligence/` — evidence package, interpretation, feature intelligence, read model (+ integration/audit), forecast engine/features/readiness, C.14C diagnostics (error classification, regime-conditioned analysis, feature reliability, event interpretation — read-only, no adaptation).
- `src/database/` — SQLAlchemy models/connection/repository against Neon Postgres.
- `src/alerts/` — Telegram and email/resend delivery; `telegram_update_v1.py` is the current UPDATE presentation surface.
- `src/update/` — RUN/DAY baseline resolution for the UPDATE v1 Telegram surface.
- `src/persistence/state.py` — lightweight JSON state (`state.json`) used by the Live Wing between runs (separate from Neon).
- `kpi/` — one executable KPI spec per phase (`kpi_pre_sp_cN.py`, `kpi_sp_bN.py`, etc.); these are the authoritative acceptance tests for each phase, not just unit tests.
- `sql/neon_schema.sql` is the canonical **target** schema; `sql/neon_migration_*.sql` are incremental migrations for the **existing** populated Neon database. Never apply the full target schema as a migration against production.

### Database / Neon migration policy

Neon Postgres is the long-term historical store (`market_snapshots`, `platform_prices`, `market_states`, `news_events`, `price_observations`, `analysis_snapshots`, `outcome_evaluations`, `platform_candles`). Any schema-affecting change requires: inspect production → compare migration intent → write incremental migration → verify on a temporary Neon branch → explicit authorization → apply to production → verify → sync docs/`.project_state.json`. Do not introduce a migration merely because a feature exists — demonstrate the persistence requirement first, and explicitly record `NEON MIGRATION REQUIRED = NO` when a phase needs none.

### Phase completion discipline

A phase/task is not "done" on green tests alone. The full loop this repo expects: inspect → define change surface → implement minimally (surgical diffs only, no drive-by refactors) → targeted test → regression (prior KPIs + compileall) → KPI → Neon verification when applicable → diff review → update `PROJECT_MEMORY.md`/`MASTER_PLAN_STATUS.md`/`.project_state.json` as relevant → commit. Current branch policy: `main` is the active development branch (SP-B has been closed/merged); do not create a parallel long-lived branch without explicit direction.
