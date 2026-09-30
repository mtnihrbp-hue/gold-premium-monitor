# Gold Premium Monitor — Master Plan Status

Branch: `main` (production since 2026-09-28; SP-C merged and closed; the next sprint, SP-D, branches from `main`)

Last reconciled: 2026-09-27.

This document is the compact continuity map of the completed architecture, verified implementation, and remaining work. It is designed for onboarding a new conversation without relying on chat history.

## 1. Locked top architecture

```text
LIVE / UPDATE WING
User-triggered Telegram /Update
→ collect → validate → calculate → current deterministic state → baseline resolution → Telegram

ANALYZE WING
scheduled trigger
→ observations → snapshots → outcomes → evidence → interpretation → features → read model → dataset → candles → forecast → forecast resolution / audit
```

### Intended versus actual Analyze trigger

> **RESOLVED 2026-09-13, kept as history.** cron-job.org job 8179679 now dispatches
> `ref=SP-C, mode=analyze` hourly 06:00–21:00 Tehran, `mode` resolves
> `SCHEDULED_RUN=true`, and the GitHub native schedule was removed on 2026-09-20.
> Hourly Analyze runs have been continuous since 2026-09-14. The text below describes
> the state before the fix.

The intended design is that cron-job.org drives the Analyze wing. **It did not.**
Verified against run history and source on 2026-09-13:

```text
cron-job.org  → POST .../workflows/gold-monitor.yml/dispatches
              → github.event_name = workflow_dispatch
              → SCHEDULED_RUN = false
              → src/main.py takes the UPDATE path
              → no news ingestion, no build_analysis_snapshot()
```

The daily 20:00 Tehran job therefore sends an extra UPDATE message and produces no
analytical history. Analysis snapshots come only from the GitHub native `schedule`
event this document elsewhere calls legacy, which fires roughly three hours late and
was cancelled on about half of recent days.

Correcting this trigger is an SP-C item. Until then, treat the Analyze wing as running
irregularly rather than on the documented cadence.

There are **two frontend wings**: UPDATE and ANALYZE. The Analyze wing is scheduled; the Update wing is user-triggered and intentionally lightweight.

The semantic boundary is:

```text
FACTS
→ EVIDENCE
→ INTERPRETATION
→ FEATURES
→ READ MODEL
→ PREDICTION
→ DECISION
```

Prediction never becomes independent BUY/WAIT/SELL authority.

## 2. SP-A baseline

SP-A is complete/frozen and remains the deterministic decision baseline:

```text
Valuation
→ Premium/relative local state
→ Momentum
→ Structure
→ Conflict
→ Candidate
→ Hysteresis
→ Final Decision
```

Future forecast work must not rewrite this authority.

## 3. Completed phases

```text
SP-B.1                   COMPLETE
SP-B.2                   COMPLETE
PRE-SP-C.1               COMPLETE
PRE-SP-C.2               COMPLETE
PRE-SP-C.3               COMPLETE
PRE-SP-C.4               COMPLETE
PRE-SP-C.5               COMPLETE
PRE-SP-C.6               COMPLETE
PRE-SP-C.7               COMPLETE
PRE-SP-C.8               COMPLETE
PRE-SP-C.9               COMPLETE
PRE-SP-C.10              COMPLETE
PRE-SP-C.11              COMPLETE
PRE-SP-C.12              COMPLETE
PRE-SP-C.13              COMPLETE
PRE-SP-C.14A             COMPLETE — 26/26 KPI
PRE-SP-C.14B             COMPLETE — 36/36 KPI
PRE-SP-C.14C             COMPLETE — 21/21 KPI
```

## 4. C.8 feature foundation

Implemented model-ready deterministic features include:

- MA/SMA 7, 15, 30
- EMA 7, 15, 30
- price-vs-moving-average relationships
- premium velocity
- premium acceleration
- direction persistence
- volatility and range expansion
- existing regime state/context
- XAU/USD and USD/IRR relationships
- local-gold divergence/alignment
- platform structure and consensus

No feature layer issues BUY/WAIT/SELL.

## 5. C.14A — Candle & Market-Structure Infrastructure

Verified:

- deterministic 30m candle construction from point observations
- OHLC semantics: first/max/min/last
- no interpolation
- no forward-fill
- no future leakage
- Goldika BUY/SELL preservation
- Ayyareh semantics preservation
- single-price source support
- historical backfill
- duplicate protection/idempotent persistence
- provenance and source quality
- Neon `platform_candles`
- Neon `price_observations.quote_side`

KPI: **26/26 PASS**.

## 6. C.14B — Forecast Features, Baselines, Evaluation & Forecast Engine

Verified contract:

```text
UP
NEUTRAL
DOWN
```

C.5 mapping:

```text
UP → UP
FLAT → NEUTRAL
DOWN → DOWN
INSUFFICIENT_DATA → INSUFFICIENT_DATA
```

Additional states:

```text
INSUFFICIENT_DATA
ABSTAIN
```

C.14B includes deterministic baselines, LogisticRegression, DecisionTree, expanding-window walk-forward evaluation, leakage protection, probability validation, multiclass Brier scoring, confusion matrix, baseline comparison, regime-conditioned evaluation, and versioned provenance.

KPI: **36/36 PASS**.

### C.14B production-readiness boundary

The code and evaluation contract are complete, but this does **not** mean production forecast readiness.

Current production history remains intentionally sparse. Forecasts must continue to return `INSUFFICIENT_DATA` / `NOT_READY` until enough real chronological history exists for meaningful evaluation and calibration.

C.14B required **no Neon schema migration**.

## 7. C.14C — Adaptive Intelligence Foundation

Status: **COMPLETE — 21/21 KPI PASS**.

C14C is the verified downstream intelligence foundation around C14B. It is diagnostic and analytical, not autonomous.

Implemented capabilities include deterministic forecast error classification, regime-conditioned forecast analysis, feature reliability/separation analysis, single and historical batch analysis, structural event-interpreter abstraction/stubs, decision-authority protection, and future-leakage protection.

Architecture boundary:

```text
Forecast Engine
      ↓
Forecast Result
      ↓
Outcome Evaluation
      ↓
C14C Intelligence Analysis
```

C14C does **not** perform reinforcement learning, online learning, automatic model-weight changes, automatic threshold changes, LLM market decisions, or autonomous trading.

KPI: **21/21 PASS**.

## 8. C14C supporting work — operational news ingestion

Existing RSS collection, deterministic event classification, deduplication, persistence, and downstream news context were wired into the scheduled analysis runtime.

```text
configured RSS sources
→ collect / normalize
→ classify
→ deduplicate
→ persist `news_events`
→ analysis snapshot news context
```

Source failures remain non-blocking. No new news table, migration, LLM, event-impact learning, or decision authority was introduced.

## 9. UPDATE v1 — user-triggered operational wing

A post-C14C surgical correction established the UPDATE/ANALYZE execution boundary.

### UPDATE contract

```text
User /Update
    ↓
current market collection
    ↓
validation
    ↓
canonical observation persistence
    ↓
minimum current calculations
    ↓
SP-A current deterministic state
    ↓
RUN/DAY baseline resolution
    ↓
Telegram UPDATE
```

The UPDATE path intentionally skips the deep Analyze pipeline, including:

```text
news ingestion
build_analysis_snapshot()
full C.3–C.10 analysis construction
forecast generation
retrospective outcome evaluation
```

The purpose is operational speed and a clean architectural boundary, not merely message formatting.

### UPDATE baseline contract

During the current transition period:

```text
RUN = current observation vs latest previous canonical market snapshot
DAY = current observation vs first canonical market snapshot of today
```

RUN is resolved before saving the current snapshot so the current observation cannot become its own baseline.

When the Analyze wing is fully operational, DAY may move to the first controlled Analyze-wing collection of the day without changing the UPDATE presentation contract.

### UPDATE v1 presentation

Current Telegram sections are:

```text
MARKET
PRICE & BUBBLE DYNAMICS / MOMENTUM & GAP
MARKET STRUCTURE
PLATFORMS
CURRENT DECISION
```

The presentation distinguishes:

- XAU/USD and USD/IRR
- Fair Price
- Platform Average
- signed Bubble/GAP
- RUN and DAY comparisons
- local-price direction
- local-price acceleration
- Bubble/GAP movement by absolute distance from fair value
- candle direction
- platform-level RUN and DAY changes

Price Pace and Bubble Pace remain deferred where historical evidence is insufficient. The implementation must not invent arbitrary thresholds to create qualitative labels.

Bubble movement currently uses the existing **0.05 percentage-point** dead-band as a project convention and is explicitly **not empirically calibrated**.

The legacy Telegram formatter remains preserved while UPDATE v1 is validated.

## 10. Architecture boundary for current development

The project now treats the two operational wings as follows:

```text
                 MARKET DATA
                     │
            ┌────────┴────────┐
            │                 │
         UPDATE            ANALYZE
       user-triggered     cron-triggered
            │                 │
       fast snapshot     history + intelligence
            │                 │
           SP-A          features / forecasts
            │                 │
            └────────┬────────┘
                     │
                shared Neon
```

UPDATE may consume persisted analytical state in future extensions, but UPDATE must not execute the Analyze pipeline merely to produce a user update.

The Analyze wing is the accumulating evidence/history engine that will eventually support stronger Decision Support and the planned Expert Judgment System.

## 11. Neon production position

SP-C.1 applied the first migration since C.14A, on 2026-09-14 with explicit
authorisation: `collection_mode` on `market_snapshots` and `price_observations`,
and `valuation_context_json` on `market_states`. Additive only, all seven table
counts identical before and after. Details in `SP_C_HANDOFF.md` section 10.

Prior C.14B, C.14C and UPDATE v1 work required no migration.

2026-09-30: `news_events.url` widened from VARCHAR(500) to TEXT
(`sql/neon_migration_news_url.sql`), because news items with longer links were
lost entirely. A catalogue change only, verified on a temporary branch first, with
the owner's authorization. Details in `SP_C_HANDOFF.md` section 40.

Relevant existing structures include:

```text
analysis_snapshots
outcome_evaluations
platform_candles
news_events
market_snapshots
platform_prices
price_observations
```

Future schema changes require the established inspection → compare → migration → verify → document workflow and explicit approval.

## 12. Deferred intelligence direction

The next major scope is not another blind implementation sprint.

The post-C14 direction is to:

1. accumulate sufficient empirical production history;
2. inspect forecast and market evidence empirically;
3. identify the actual forecasting bottleneck;
4. improve evidence quality and analytical primitives where justified;
5. design a robust Expert Judgment System around validated evidence and historical outcomes.

Potential future extensions remain intentionally deferred until evidence supports them:

```text
immutable forecast event persistence
human forecast review persistence/UI
empirical news/event impact measurement
controlled adaptive weighting
LLM event interpretation
reinforcement learning / bandit optimization
ETF money-flow / retail-vs-institutional flow
Expert Judgment System implementation
```

The planned Iranian gold-ETF money-flow capability is a future data-extension candidate. It is not part of the current UPDATE surgery and must not be introduced prematurely.

## 13. Forecast runtime boundary

Current forecast execution may return:

```text
1h  → INSUFFICIENT_DATA
6h  → INSUFFICIENT_DATA
24h → INSUFFICIENT_DATA
```

This is expected while chronological production history is sparse. Sufficiency gates must not be weakened merely to produce numerical forecasts.

## 14. Regression boundary

Every substantive change must preserve:

```text
SP-A decision authority
C14B forecast contract
C14C analytical boundary
future-leakage protection
canonical observation authority
unknown / insufficient-data semantics
UPDATE ≠ ANALYZE
no unnecessary Neon schema mutation
```

## 15. Branch safety

```text
CURRENT WORK = SP-C branch
MAIN MERGE = after user review, tagged v1.3safe first
```

The gate on this section has been satisfied. The bottleneck was identified with
evidence rather than assumed: collection cadence, not analytical capability. The
Analyze wing was not running at all because an external scheduler posting to the
dispatches endpoint produced `workflow_dispatch` rather than `schedule`, and the
candle build scaled with total stored history until it exceeded the job timeout.

SP-C scope is recorded in `SP_C_HANDOFF.md`. Completed so far:

```text
Pre-SP-C stabilization        KPI suite into CI, five UPDATE defects, doc reconciliation
Analyze trigger               fixed, mode input declared by the caller
Candle build performance      11m19s → 1m53s, no longer grows with history
SP-C.1 relative valuation     bubble_position.py, collection_mode migration 2026-09-14
SP-C.2 decision scorecard     decision_scorecard.py (computed, not wired to a surface)
SP-C.3 outcome backfill       wired into the scheduled path
SP-C.5 one vocabulary         trimmed (3-cheapest) display basis, Iran local time
SP-C.6 three latches          hysteresis timer, regime calibration, bonbast 60 s bound
SP-C.7 settled reference      completed local days, user rows excluded
SP-C.8 world-gold provenance  kitco vs kitco_cached reaches storage
SP-C.9 collector deadline     one shared deadline over the eleven platforms
SP-C.10 news sources          replaced; source records feed identity
SP-C.11 outcome premium leg   proximity decides, scheduled breaks ties
SP-C.12 ANALYZE and the push  read-only REPORT mode; buy-side thermostat push
SP-C.13 one deep-discount     one level for UPDATE, ANALYZE and the push
SP-C.14 coherence KPI         kpi_coherence.py and the ACCEPTED register (5 entries)
SP-C.15 valuation leg         rank + direction gate, no fixed fallback
SP-C.16 tidy pass             one clock, shared tolerances, news classifier repaired
SP-C.17 structure leg         measured, deliberately left alone
SP-C.18 deep-zone survival    comparison windows, ANALYZE wording
```

Last code change 2026-09-22. Full suite: **26/26 files**, green locally
(2026-09-27, exit 0) and in CI.

Rollout (`SP_C_HANDOFF.md` section 29), state on 2026-09-27:

```text
1 observe     CLOSED 2026-09-27 by the product owner (section 33.1)
2 merge       DONE 2026-09-28 -- 2b7c5f8; main tagged v1.3safe before it; merged
              tree identical to SP-C; KPI 26/26 on main (section 35)
3 repoint     DONE 2026-09-28 -- cron-job.org 8179679 and the worker send ref main;
              first /Analyze and /Update on main succeeded
4 broadcast   TELEGRAM_BROADCAST_IDS + audience per message type (section 29.3)
```

SP-D also carries a Technical Analysis track for ANALYZE (agreed 2026-09-30,
`SP_C_HANDOFF.md` section 41): step 1 data research now (tgju's 13-year daily
history tracks our platforms at 0.95 daily correlation); step 2 fixes and shows
support/resistance and a moving-average crossing after the reliability phase; step 3
long averages and candle patterns when history allows. TA is evidence, never a
decision, until validated.

SP-D: code work opens Saturday 2026-10-03, after a settle period on `main`; R&D
starts with the morning dollar (agreed 2026-09-29, `SP_C_HANDOFF.md` section 36). The
`SP-D` branch exists from 2026-09-29 for R&D records and docs.

After the merge, in the order agreed on 2026-09-28 (section 34.7):

```text
1 reliability phase   world-gold deadline (the diagnosed stalls), high_impact_count
                      with a precision check, news dedup (window and Google suffix);
                      Daric if still down
2 morning dollar      research only, no code: second dollar source, bias on the pool
                      and ranks, structure-leg re-measure; then a fix decision
3 broadcast           rollout step 4
4 basis divergence    premium_percent at source; own phase and approval
5 ANALYZE percentages section 31
6 research            6h horizon, quote_side
```

## 15a. Progress toward the product goal (assessed 2026-09-29)

The product goal, in the owner's words (September 2026):

- an expert system that reads its own data: *"This discount is in the 12th percentile.
  The last 23 times it got this deep, it closed within a day 61% of the time"*;
- it learns from itself: it records each decision, checks it against what happened,
  and builds a confidence score;
- news and sentiment as an input;
- served to 30-50 friends: UPDATE on demand, ANALYZE for intelligence, push alerts;
- later, Iranian gold-ETF money flow.

The table below is an engineering judgment, not a measurement. Re-assess it at each
phase close.

| Pillar | Status | What is missing |
|---|---|---|
| Data foundation (prices, fair value, discount) | Solid: hourly, 11 platforms, stable on `main` | Morning dollar (about a third of readings off by 0.71 pp on average, SP_C_HANDOFF 34.3, 36.2); the Kitco hang (33.2); stale platform quotes such as Taline's (37) |
| "Where does today sit" (the 12th-percentile part) | Done: rank against 30 days, one deep-discount level on every surface, scheduled-only sampling since the D gate | Nothing beyond the morning-dollar effect on the history |
| "What happened next" (the 61% part) | Built (ANALYZE), statistics thin | About 44 independent days; the 09-25 re-measure reversed a lean in two days (33.6); percentages designed, not built (31) |
| Decision engine | Repaired, working; confirmation check added 2026-09-29 | The first live BUY (2026-09-29) rested on one stale platform (37); fixed by a fail-closed confirmation check (38), under which all 4 BUYs ever sent would have been held. No confirmed BUY yet; its verdict is deliberately not shown in UPDATE |
| Learning / confidence score | Early | The scorecard exists but has almost nothing to score; calibration needs about 171 independent days, so February 2027 at the earliest |
| News | Collecting well (9 sources, about 420 a day) | No relationship to market moves found yet; classifier precision; re-measure from about 2026-10-22 |
| Friends | Designed, not built | Broadcast (29.3); a per-user `/Update` needs requester identity (29.1) |
| ETF money flow | Not started | Deferred (section 12) |

**Summary.** The data layer and the "where does today sit" layer can be trusted. The
"what happens next" and "learning" layers exist but need time and a varied decision
history, which code cannot shorten. The largest reachable gains are clean inputs (the
morning dollar, stale platform quotes, the Kitco hang), a decision that is confirmed
before it alerts, and delivery to readers.

## 16. Continuity protocol

```text
KIMI code
↓
GitHub source
↓
schema/migration audit
↓
Neon production state
↓
KPI / smoke
↓
documentation
↓
.project_state.json
↓
commit
```

This sequence remains mandatory for every substantive phase.
