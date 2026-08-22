# Gold Premium Monitor — Operational Control Plane

This document records the runtime control plane around the application. It is distinct from `PROJECT_MEMORY.md` (architecture/state), `PROJECT_ORCHESTRATION.md` (continuity), `C14_HANDOFF.md` (C.14 implementation contract), and `RESEARCH_ADOPTION.md` (research adoption/defer decisions).

## 1. Two frontend wings

### Live Wing

```text
Telegram /Update
   ↓
Cloudflare interconnection
   ↓
GitHub execution path
   ↓
collect → validate → calculate
   ↓
current deterministic state
   ↓
Telegram response
```

The Live Wing is user-triggered and current. It does not require cron scheduling.

### Analysis Wing

```text
cron-job.org
   ↓
external protected trigger
   ↓
GitHub Actions
   ↓
Analysis execution
   ↓
canonical observations
   ↓
analysis_snapshots
   ↓
outcome_evaluations
   ↓
evidence / interpretation / features
   ↓
read model / consumer
   ↓
historical dataset
   ↓
C.14A candles
   ↓
C.14B forecast
   ↓
C.14C forecast resolution / human review / closed-loop audit
```

The Analysis Wing is scheduled and independent of the number of Telegram users.

Human forecast review is collected inside the Analysis Wing Telegram experience. It is not a third frontend wing.

## 2. External scheduler policy

The intended scheduler is `cron-job.org`, not GitHub's internal `schedule` event.

```text
https://console.cron-job.org/jobs/8179679
Job ID: 8179679
```

The external scheduler exists so schedule control is outside GitHub Actions and can be inspected/manually operated independently.

GitHub Actions should retain a manual trigger for testing. The production Analysis Wing schedule should stop depending on GitHub's internal schedule only after the external trigger is verified end-to-end.

Current legacy internal GitHub schedule:

```text
30 14 * * * UTC
```

This is not the final production scheduling policy.

## 3. Intended Analysis cadence

```text
Timezone: Asia/Tehran
Start: 08:00
End: 21:00 exclusive
Interval: 30 minutes
```

Expected windows:

```text
08:00
08:30
09:00
...
20:30
```

The application scheduler remains authoritative for whether an analysis window is valid.

## 4. Analysis guardrails

```text
scheduled run
→ deterministic source_run_id
→ idempotent execution
→ duplicate trigger protection
→ analysis snapshot
```

Manual `/Update` remains independent from scheduled Analysis runs.

### World-gold / XAUUSD calendar guardrail

The historical discussion included the remembered wording:

```text
skip world-gold call on Saturday and Monday
```

This remains UNVERIFIED and must not be encoded as a production rule until the actual source calendar is confirmed.

Safe generic rule:

```text
source unavailable / market closed
    ↓
do not fabricate XAUUSD
    ↓
persist data-quality state
    ↓
allow independent valid sources to continue
```

## 5. Cloudflare role

Cloudflare is an interconnection/control layer, not an analytical engine.

```text
Telegram request
    ↓
Cloudflare Worker / secure gateway
    ↓
validated command or trigger
    ↓
GitHub execution endpoint
```

Potential scheduled path:

```text
cron-job.org
    ↓
Cloudflare Worker
    ↓
GitHub Actions
    ↓
Analysis Wing
```

Cloudflare must not calculate gold price, premium, regime, features, or forecast.

Current status:

```text
Cloudflare architecture = documented
Cloudflare live control = NOT YET CONNECTED IN THIS CHAT
```

## 6. Telegram analytical surface

C.13 established these analytical commands:

```text
/Analysis
/Technical
/History
/News
/Health
```

The broader two-wing user workflow is:

```text
/Update
→ live market state

/Analyze
→ evidence / interpretation / market structure / technical context

/Forecast
→ probabilistic directional forecast when enabled
```

`/Forecast` remains gated until forecast-readiness criteria are satisfied.

## 7. Forecast review and human feedback

The user should not fill a questionnaire.

After a forecast matures, a later `/Forecast` request may surface a compact review of the previous forecast.

Conceptual lifecycle:

```text
GENERATED
→ PENDING
→ ELIGIBLE_FOR_REVIEW
→ OBJECTIVELY_EVALUATED
→ USER_REVIEWED (optional)
```

The system first computes objective outcome quality from actual observations.

Human review is separate meta-data measuring perceived usefulness/timing/direction quality.

Human feedback must not directly update model weights or replace objective labels.

## 8. Fail-safe data policy

Global rule:

```text
MISSING
 ↓
safe deterministic fallback?
 ├─ YES → fallback + degraded provenance
 └─ NO  → INSUFFICIENT_DATA / ABSTAIN
```

Never silently extrapolate absent market facts.

This applies to prices, candles, features, outcomes, and forecast inputs.

## 9. C.14 operational scope

C.14 is split:

```text
PRE-SP-C.14A
Candle & Market-Structure Data Infrastructure

PRE-SP-C.14B
Forecast Features, Baselines, Evaluation & Forecast Engine

PRE-SP-C.14C
Forecast Resolution, Human Review & Closed-Loop Audit
```

C.14A is now VERIFIED COMPLETE.

C.14B must not begin until the C.14A gate is closed and documented.

## 10. C.14A verified state

C.14A establishes persistent deterministic 30-minute candles from canonical point observations.

Verified:

```text
KPI: 26/26 PASS
compileall: PASS locally
live smoke: PASS
Neon schema: APPLIED_AND_VERIFIED_IN_PRODUCTION
```

The latest live smoke created:

```text
Analysis snapshot 5
9 platform candles saved
Telegram delivery PASS
```

The live smoke discarded two unavailable sources:

```text
Invi — timeout
Daric — timeout
```

Nine valid Iranian gold sources remained, so the run completed normally.

The GitHub Actions compileall stage was cancelled after the source compilation output had completed; this is recorded as `CANCELLED`, not a source compile failure.

## 11. Candle semantics

Initial canonical timeframe:

```text
30m
```

For derived candles from point observations:

```text
OPEN  = first valid observation
HIGH  = maximum valid observation
LOW   = minimum valid observation
CLOSE = last valid observation
```

No interpolation, no forward-fill, no future observations.

For sources with explicit BUY/SELL quotes, preserve separate sides.

Goldika exposes explicit buy/sell quotes.

Ayyareh exposes `goldPrice` plus platform margin/wage fields. The existing collector contract is authoritative for how side estimates are derived; raw values and derived side values remain separate.

C.14A backfills existing `price_observations` where coverage exists, then continues forward. Historical reconstruction uses explicit historical bounds; normal runtime candle construction remains bounded to the recent observation window.

Unless a platform explicitly supplies official OHLC, the provenance identifies candles as derived from point observations.

## 12. Forecast readiness gate

Forecast target:

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

Also allow:

```text
ABSTAIN
```

Minimum production-readiness evidence:

```text
sustained analysis snapshots
+
sustained outcome evaluations
+
walk-forward evaluation
+
leakage audit
+
baseline comparison
+
probability calibration
+
abstention / insufficient-data behavior
+
no direct BUY/SELL authority
```

Current forecast status:

```text
NOT READY FOR DEPLOYMENT
```

## 13. C.13 completion state

```text
PRE-SP-C.13
KPI: 26/26 PASS
compileall: PASS
live smoke: PASS
analysis snapshot creation: PASS
Telegram delivery: PASS
Neon C.13 reconciliation: COMPLETE
```

## 14. Operational truth rule

For a new conversation:

```text
cron-job.org current configuration
↓
Cloudflare connection / Worker state
↓
GitHub Actions workflow trigger state
↓
SP-B source code
↓
Neon production row counts/schema
↓
Telegram command behavior
```

Document every resulting operational state change.
