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

Run the entire KPI suite (29 files) — this is the regression check before calling any phase complete:
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
- `kpi-suite.yml` — full KPI suite + `compileall`, on `main`, SP-C and SP-D pushes, PRs, and manual dispatch. Never given `DATABASE_URL`, so it cannot reach production Neon. Safe to run freely.
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
and the tz database is not reliably present on every runner). Grouping by the stored
UTC date cuts each Iranian day at 03:30 local — use `local_date`.

**`datetime.now()` must not appear anywhere in `src/`**, and `kpi_coherence.test_19`
enforces that. It returns the runner's local time while every stored timestamp is
UTC, so a filter written against it is correct only while the runner happens to be
UTC. CI runners are, which is exactly why 74 such calls survived across 14 modules
until SP-C.16. Use `datetime.utcnow()`.

### Shared tolerances

`src/tolerances.py` holds `UNCHANGED_DEADBAND_PP` and `COMPARABLE_BAND_FRACTION`, one
definition each, for the same reason `timeutil` holds one definition of time. They
existed as six constants under four names across four modules until SP-C.16. Import
them; do not restate them. `kpi_coherence.test_20` fails on a local redefinition.

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

Five entries are currently registered. Two closed in SP-C.15 and two were added in
SP-C.16; closing one fails the suite until its entry is retired — that is the
mechanism working, not a bug. See `SP_C_HANDOFF.md` §25, §26 and §27.

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
highest premium ever stored is +0.75% (2026-09-29 10:00, after the stale-quote
correction of §45), against a +3.0% gate. That is correct, not a dead bound to tidy
away. All four positive readings on record sit between 10:00 and 12:01 (09-24, 09-28
twice, 09-29) and are most likely a stale morning USD/IRR input rather than a real
premium (`SP_C_HANDOFF.md` §34.3). Morning readings, before about 11:00 Tehran, can carry the
previous day's dollar.

There is deliberately **no fixed-threshold fallback**: below `MIN_OBSERVATIONS` the
answer is `UNKNOWN`. A fallback that always answers is how this leg spent months
reading `CHEAP` on 364 of 364 rows. `build_signal_state` receives the state rather than
computing it, because ranking needs a session and a calculator must not open one.

It ranks the **stored** `premium_percent` against a window of stored `premium_percent`,
on the settled non-user pool. See `SP_C_HANDOFF.md` §26 and `LESSONS_LEARNED.md` §14.

### Degenerate classifiers

This codebase has produced five classifiers that emitted a single value for months
without error: `valuation_state=CHEAP`, `regime_state=PANIC`, `final_decision=WAIT`,
news `relevance=UNKNOWN`, and `structure_state=DISCOUNT_DOMINANT` (measured in SP-C.17
and deliberately left alone — a rare-event detector). A sixth constant of the same
shape, found 2026-09-27 and still open: evidence `news_context.high_impact_count` is 0 on
every analysis snapshot because it reads `relevance` for values only `impact` holds
(`SP_C_HANDOFF.md` §33.3). Before
trusting or reporting any categorical output, run
`SELECT <column>, COUNT(*) ... GROUP BY 1` against production. One row means the column
is a constant and any metric computed over it is meaningless.

Then run the same query on the **quantity the classifier consumes**, because the two
cases need opposite fixes and look identical from the output side:

- the input varies but the output does not → the bound is stale, replace it with a
  rank (this was `valuation_state`, fixed in SP-C.15)
- the input does not vary → the *measure* is wrong, and a rank will look like a fix
  while achieving nothing, because a percentile of a point mass is the point mass
  (this is `structure_state`, registered in SP-C.16)
- the input varies, the output does not, and no bound is involved → the code reads the
  wrong field; the fix is the field, not a rank (this is `high_impact_count`)

See `LESSONS_LEARNED.md` sections 1-3, 13, 15 and 16.

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

`final_decision` (from the SP-A pipeline: Valuation → Premium Direction → Momentum → Market Structure → Conflict Matrix → Candidate Decision → Confirmation → SP-A Hysteresis → Final Decision) is the sole external BUY/SELL alert authority — legacy/candidate signals must never independently trigger an alert.

### Signal confirmation

Added 2026-09-29, after the first live BUY rested on one stale platform quote
(`SP_C_HANDOFF.md` §37, §38). `analysis/confirmation.resolve_signal_confirmation` is
checked between the candidate and hysteresis; the conflict matrix itself is unchanged.
A BUY needs the **second-cheapest platform** to be heavily discounted on its own settled
30-day record, judged by `classify_valuation` over `reference_readings`, the same
classifier and pool as the valuation leg (`kpi_coherence.test_28`). Any signal needs the
**dollar rate to be today's** (not live before 11:00 Tehran; between 11:00 and 13:00 only
if it has moved since the open; live from 13:00) and **world gold to be live**. A held
candidate stays recorded as the candidate, `final_decision` becomes WAIT, and the stored
reason says why.

It **fails closed**: a check that cannot run holds the signal. That is deliberate and
the opposite of the push, which fails open. A BUY is a recommendation and must be able
to show its evidence. Do not make it fail open to "unblock" signals. A BUY that reaches
the reader goes through `alerts/telegram_signal.py`, which reuses UPDATE's helpers and
prints "heavily discounted", never "cheap".

**Stale platform quotes are deferred** (owner's principle, 2026-09-29: "if a platform is
stale, it should be deferred"; 2026-10-02: "rectified once for all, it contaminates our
DB"; §38.7, §39, §44). Iranian CDNs (Sotoon serves Goldika, Taline and Daric) can hand
the non-Iranian runner a copy days or weeks old while Iran gets the live price: from
2026-10-01 Goldika's served the runner a price from 2026-09-13. **The data depends on
where you stand: check a platform from the runner's side (Psiphon), not from Iran.** In
`validation/data.validate_market_prices`, for that reading only:

- **Source time.** Goldika (`createdAt`, UTC) and Milli (`date`, Tehran) publish when
  they set the price; the collectors return it as `quoted_at` and a quote priced more
  than `MAX_QUOTE_AGE_HOURS` (6) ago is discarded at first sight. Use a source's own
  stamp wherever one exists: it is exact, the rules below are inferred.
- **Repeat.** Any platform is deferred when it repeats a price it reported in an
  earlier reading, at least 45 minutes and at most 60 days ago, **and** sits more than
  1.0 pp from its own 14-day usual position against the other platforms' median. The
  window was 3-48 hours until 2026-10-02: a new frozen value passed for three hours,
  and a deferred one, never stored, slipped back in once its stored copy aged out.
- **Jump.** A quote more than 3 pp from its usual position is held until it is seen to
  move (holds remembered in `state.json`): a live price that jumped moves and is
  accepted at the next reading, a copy repeats and stays held. It fired once in two
  months of replay; it is a backstop, not an outlier filter.
- **Taline** is also discarded when more than 1.0% from the median.

Staleness is not distance. A fresh price far from the others is information, and
platforms have natural offsets (Goldika about +1.1%, Milli about -0.9%). Do not turn
this into an outlier filter. The history read fails open; the signal confirmation
fails closed. **The push needs the deep discount without its cheapest platform too**
(`push_trigger.corroborate`): both false pushes on record rested on one stale quote.

LLM/intelligence layers may summarize, interpret, and express uncertainty over already-validated evidence; they must never calculate fair price/premium/indicators, invent levels or stats, or acquire independent BUY/SELL authority.

Fail-safe law used throughout collection/analysis: on missing data, use a safe deterministic fallback with degraded provenance if one exists, otherwise return `INSUFFICIENT_DATA`/`ABSTAIN` — never silently extrapolate.

### Source layout

- `src/collector/` — per-platform Iranian gold price collectors (HoorGold, Parasteh, Daric, Taline, Ayyareh, Invi, MioGold, Eligold, Goldika, Milli, WallGold) plus `kitco.py` (XAU/USD), `bonbast.py` (USD/IRR), `news/` (RSS ingestion), and `tgju.py` (tgju's daily candles for technical analysis, stored by `main` in `market_daily_candles`, never mixed with platform prices). Representative Iranian price fallback order is `Milli → Ayyareh → WallGold → UNKNOWN`; source failures must stay isolated from each other. Unit normalization (e.g. Toman→Rial) is a collector-level responsibility, not a market-model adjustment.
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

Neon Postgres is the long-term historical store (`market_snapshots`, `platform_prices`, `market_states`, `news_events`, `price_observations`, `analysis_snapshots`, `outcome_evaluations`, `platform_candles`, `market_daily_candles`). Any schema-affecting change requires: inspect production → compare migration intent → write incremental migration → verify on a temporary Neon branch → explicit authorization → apply to production → verify → sync docs/`.project_state.json`. Do not introduce a migration merely because a feature exists — demonstrate the persistence requirement first, and explicitly record `NEON MIGRATION REQUIRED = NO` when a phase needs none.

### Phase completion discipline

A phase/task is not "done" on green tests alone. The full loop this repo expects: inspect → define change surface → implement minimally (surgical diffs only, no drive-by refactors) → targeted test → regression (prior KPIs + compileall) → KPI → Neon verification when applicable → diff review → update `PROJECT_MEMORY.md`/`MASTER_PLAN_STATUS.md`/`.project_state.json` as relevant → commit. Current branch policy: `main` is production. cron-job.org and the Telegram worker dispatch `ref: main` since 2026-09-28, when SP-C was merged (tag `v1.3safe` marks `main` before the merge; `SP_C_HANDOFF.md` §35). The next sprint, **SP-D**, was branched from `main` on 2026-09-29. SP-D is for the next phase, whose code work opens on 2026-10-03 (`SP_C_HANDOFF.md` §36). Until then, by the owner's direction of 2026-09-29, anything found is fixed **on `main`**, through a short-lived branch cut from `main` and fast-forwarded after the owner's review (`sprint-execution.md`: never develop directly on `main`). The first was `hotfix-signal-confirmation` (§38). Never commit to or merge into `main` without the product owner's review. Do not create a parallel long-lived branch without explicit direction.
