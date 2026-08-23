# Gold Premium Monitor — Master Plan Status

Branch: `SP-B`

This document is the compact continuity map of the completed architecture, verified implementation, and remaining C.14 work. It is designed for onboarding a new conversation without relying on chat history.

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

## 7. Neon production position

Latest reconciled schema includes:

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

C.14B did not require a new schema change.

Future schema changes require the established Neon migration/verification workflow and approval.

## 8. C.14C — Remaining phase

C.14C is now the next development target.

It should be treated as the closed-loop intelligence/audit layer around C.14B, not as another uncontrolled feature dump.

Planned components:

```text
C.14C.1 Forecast Resolution
C.14C.2 Human Review inside Telegram Analysis experience
C.14C.3 News/Event Provenance + Deduplication
C.14C.4 Event-Impact Measurement
C.14C.5 Calibration / Forecast Audit
C.14C.6 Regime-conditioned audit
C.14C.7 Weekly admin intelligence report
```

### Human feedback

The system first computes objective market outcome.

Human input is separate meta-data:

```text
OBJECTIVE OUTCOME
≠
HUMAN ASSESSMENT
```

No online model-weight updates from raw user feedback.

Forecast lifecycle:

```text
GENERATED
→ PENDING
→ ELIGIBLE_FOR_REVIEW
→ OBJECTIVELY_EVALUATED
→ USER_REVIEWED (optional)
```

Keep three clocks separate:

```text
forecast_time
market_outcome_time
feedback_time
```

### News/event intelligence

News is not reduced to headline sentiment.

Preferred model:

```text
NEWS EVENT
→ provenance/classification
→ expected impact hypothesis
→ market observation window
→ abnormal/local response
→ historical event profile
→ empirical event/source weighting
```

Do not treat reposts as independent confirmations.

Do not infer causality without evidence.

Use event windows and compare local response against external drivers where possible.

### Regime

The existing regime detector remains the canonical regime engine.

C.14C uses regime for contextual and diagnostic segmentation:

```text
stable trend
range
stress
transition
```

(or the exact project labels).

Regime does not override the forecast and does not issue BUY/SELL.

## 9. User-facing terminology refactor

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

## 10. What remains before SP-B can close

The project is not ready to merge SP-B → main yet.

Remaining work is primarily:

1. C.14C implementation and verification.
2. Final terminology/user-facing Telegram curation.
3. Forecast readiness based on accumulated real production history.
4. Closed-loop human review and news/event audit.
5. Full regression across all phase KPIs.
6. Final Neon schema/data audit.
7. Final GitHub diff/documentation/state review.
8. Final operational review of cron-job.org + Cloudflare + GitHub Actions.
9. Explicit SP-B close approval.
10. Only then merge SP-B → main and later create SP-C.

## 11. Branch safety

```text
ACTIVE DEVELOPMENT = SP-B
main WRITE = forbidden
main MERGE = forbidden until explicit SP-B close approval
```

Never merge `main` into SP-B as a shortcut. Reconcile specific artifacts only.

## 12. Continuity protocol

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
