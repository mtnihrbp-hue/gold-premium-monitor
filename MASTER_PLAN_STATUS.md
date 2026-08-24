# Gold Premium Monitor — Master Plan Status

Branch: `SP-B`

This document is the compact continuity map of the completed architecture, verified implementation, and remaining work. It is designed for onboarding a new conversation without relying on chat history.

## 1. Locked top architecture

```text
LIVE WING
Telegram /Update
→ collect → validate → calculate → current deterministic state → Telegram

ANALYSIS WING
scheduled trigger
→ observations
→ snapshots
→ outcomes
→ evidence
→ interpretation
→ features
→ read model
→ dataset
→ candles
→ forecast
→ forecast resolution / audit
```

There are **two frontend wings only**. Human forecast review is embedded in the Analysis Telegram experience; it is not a third wing.

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

SP-A is complete/frozen and has the safe checkpoint tag `v1.1-safe`. It remains the deterministic decision baseline:

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

## 3. Completed SP-B phases

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

Operational smoke: analysis snapshot creation, candle creation, and Telegram delivery succeeded. Source timeouts were isolated and remaining valid sources continued.

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

C.14B includes:

- C.8 baseline feature configuration
- C.14A candle/price-action feature configuration
- deterministic majority baseline
- previous-valid-direction persistence baseline
- C.8 deterministic baseline
- LogisticRegression
- small DecisionTree
- expanding-window walk-forward evaluation
- point-in-time/leakage protection
- probability validation
- multiclass Brier scoring
- confusion matrix
- baseline comparison
- regime-conditioned evaluation
- model/feature/label versioning
- provenance
- no decision generation

KPI: **36/36 PASS**.

`scikit-learn` is already recorded in `requirements.txt`.

### C.14B production-readiness boundary

The code and evaluation contract are complete, but this does **not** mean production forecast readiness.

Current Neon history remains intentionally sparse. Therefore the model must continue to return `INSUFFICIENT_DATA` / `NOT_READY` until enough real chronological history exists for meaningful evaluation and calibration.

C.14B required **no Neon schema migration**.

## 7. C.14C — Adaptive Intelligence Foundation

Status: **COMPLETE — 21/21 KPI PASS**.

C.14C is the verified downstream intelligence foundation around C.14B. It is diagnostic and analytical, not autonomous.

Implemented capabilities:

- deterministic forecast error classification
- direction, confidence, timing, regime, and data-quality error categories
- regime-conditioned forecast analysis
- feature reliability analysis
- feature separation checks
- single-forecast analysis
- historical batch analysis
- structural event-interpreter interface/stubs for future event intelligence
- explicit protection against decision-authority escalation
- explicit future-leakage protection

C.14C consumes existing analytical/forecast artifacts. It does not modify the C.14B forecast contract or the deterministic decision engine.

Architecture boundary:

```text
Forecast Engine
      ↓
Forecast Result
      ↓
Outcome Evaluation
      ↓
C.14C Intelligence Analysis
```

C.14C may measure, classify, compare, explain, and identify areas for future investigation.

C.14C does **not**:

- perform reinforcement learning
- perform online learning
- automatically modify model weights
- automatically change thresholds
- modify BUY/WAIT/SELL authority
- call an LLM for market decisions
- create an autonomous trading policy

Forecast memory is currently reconstructed from existing persisted analytical artifacts. Immutable forecast-history persistence is deferred until production forecast lifecycle and data volume justify it.

Error classification is currently computed analytically rather than persisted as a new database field.

The event interpreter is an architectural extension point only; actual LLM/event-model integration is future scope.

KPI: **21/21 PASS**.

## 8. Neon production position

Latest reconciled production schema includes:

```text
outcome_evaluations
analysis_snapshots.evidence_package_json
analysis_snapshots.intelligence_result_json
analysis_snapshots.features_json
analysis_snapshots.analysis_read_model_json
analysis_snapshots regime/hysteresis fields
price_observations.quote_side
platform_candles
news_events
```

C.14A schema migration is applied and verified in production.

C.14B required no schema change.

C.14C required **no schema migration**. Existing production tables are sufficient for the implemented C.14C foundation.

Live Neon verification on 2026-08-24 confirmed the expected core structures and preserved historical data. No database mutation was performed during the C.14C reconciliation.

Future schema changes require the established Neon migration/verification workflow and explicit approval.

## 9. C.14C deferred intelligence extensions

The following concepts remain intentionally deferred rather than being falsely recorded as implemented:

```text
immutable forecast event persistence
human review persistence/UI
news/event provenance and deduplication
empirical event-impact measurement
weekly administrative intelligence reporting
controlled adaptive weighting
LLM event interpretation
reinforcement learning / bandit optimization
```

These are future architecture work and must be evaluated separately against accumulated production evidence.

## 10. User-facing terminology refactor

Do not expose opaque internal labels such as:

```text
DISCOUNT_WIDENING
DISCOUNT_NARROWING
```

Prefer observable statements such as:

```text
Iranian gold is increasing more slowly than its external drivers.
Iranian gold is catching up faster than its external drivers.
Local prices are lagging the global/FX move.
Local prices are moving faster than the external drivers.
```

Internal mathematics may retain premium/discount, relative rate of change, slope, velocity, and acceleration.

Causal explanation requires evidence.

## 11. What remains before SP-B can close

The project is not ready to merge SP-B → main yet.

Remaining work is primarily:

1. Decide the next post-C14C intelligence scope from evidence, not speculation.
2. Accumulate sufficient real production history for forecast readiness.
3. Evaluate whether immutable forecast persistence is justified.
4. Design and verify any human-review/news-impact extension separately.
5. Full regression across all phase KPIs before SP-B closure.
6. Final Neon schema/data audit at SP-B close.
7. Final GitHub diff/documentation/state review.
8. Final operational review of cron-job.org + Cloudflare + GitHub Actions.
9. Explicit SP-B close approval.
10. Only then merge SP-B → main and later create SP-C.

## 12. Branch safety

```text
ACTIVE DEVELOPMENT = SP-B
main WRITE = forbidden
main MERGE = forbidden until explicit SP-B close approval
```

Never merge `main` into SP-B as a shortcut. Reconcile specific artifacts only.

## 13. Continuity protocol

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

This sequence is mandatory for every substantive phase.
