# Gold Premium Monitor — Master Plan Status

Branch: `main`

This document is the compact continuity map of the completed architecture, verified implementation, and remaining work. It is designed for onboarding a new conversation without relying on chat history.

## 1. Locked top architecture

```text
LIVE / UPDATE WING
User-triggered Telegram /Update
→ collect → validate → calculate → current deterministic state → baseline resolution → Telegram

ANALYZE WING
cron-job.org scheduled trigger
→ observations → snapshots → outcomes → evidence → interpretation → features → read model → dataset → candles → forecast → forecast resolution / audit
```

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

Current work requires **no Neon migration**.

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
CURRENT WORK = main surgical stabilization / documentation
NEXT MAJOR PHASE = SP-C on a new branch after scope approval
```

No major C15/SP-C implementation should begin until the architecture/research review identifies the actual bottleneck and scope is explicitly locked.

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
