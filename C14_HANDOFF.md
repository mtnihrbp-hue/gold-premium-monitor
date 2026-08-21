# PRE-SP-C.14 — KIMI Engineering Handoff

This is the canonical implementation handoff for the split C.14 work.

## Phase split

```text
PRE-SP-C.14A
Candle & Market-Structure Data Infrastructure

        ↓

PRE-SP-C.14B
Forecast Features, Baselines, Evaluation & Forecast Engine
```

C.14A must be complete and verified before C.14B begins.

## Top architecture

```text
LIVE WING
Telegram /Update
→ current collection / validation / calculation
→ current deterministic state

ANALYSIS WING
cron / scheduled execution
→ canonical observations
→ analysis snapshots
→ outcomes
→ evidence
→ interpretation
→ C.8 features
→ C.9 read model
→ C.10 retrieval/audit
→ C.11 consumer
→ C.12 historical dataset
→ C.14A candle infrastructure
→ C.14B forecast
```

Prediction remains separate from Decision.

```text
FACTS
 ↓
EVIDENCE
 ↓
INTERPRETATION
 ↓
FEATURES
 ↓
READ MODEL
 ↓
PREDICTION
 ↓
DECISION
```

Forecast never rewrites facts, evidence, interpretation, features, read model, or current `final_decision`.

## C.14A objective

Build persistent, deterministic platform candle infrastructure from canonical point observations.

Primary Iranian sources:

- Goldika
- Ayyareh
- Milli
- WallGold

For platforms with explicit transaction-side quotes, preserve BUY and SELL separately.

Goldika exposes explicit `buy` and `sell` prices.

Ayyareh exposes `goldPrice` plus platform margin/wage fields. The existing collector contract must be inspected before deriving side prices. Preserve raw fields and derived side estimates separately.

For sources with only one reliable price, create a `SINGLE_PRICE` candle.

Unless a platform supplies official OHLC, candles are explicitly:

```text
DERIVED_FROM_POINT_OBSERVATIONS
```

Candle aggregation:

```text
OPEN  = first valid observation in bucket
HIGH  = maximum valid observation
LOW   = minimum valid observation
CLOSE = last valid observation
```

No interpolation. No forward-fill. No future observations.

Canonical initial timeframe: `30m`.

Backfill existing `price_observations` where coverage exists, then continue forward collection.

Backfilled provenance must remain explicit.

### C.14A Neon target

Add an incremental `platform_candles` table with provenance and idempotency. Exact schema must be derived from repository conventions and approved through Neon temporary-branch migration verification.

The source-of-truth raw observation layer remains `price_observations`.

Candle rows are derived analytical storage and must not replace raw observations.

## C.14B objective

Evaluate whether the existing analytical feature set contains predictive signal and whether platform candle/price-action features add incremental value.

Baseline:

```text
C.8 features
```

Extended:

```text
C.8 features
+
platform candle / price-action features
+
MACD-style momentum where non-redundant
```

Target forecast:

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

Do not redefine C.5 label semantics.

Forecast also supports:

```text
INSUFFICIENT_DATA
ABSTAIN
```

Do not connect prediction directly to BUY/SELL authority.

## Economic + technical model context

The model research space combines:

- XAU/USD pressure
- USD/IRR pressure
- Iranian gold value
- premium / discount
- platform consensus and dispersion
- market regime
- volatility
- momentum
- MA/SMA/EMA structure
- candle structure
- price action
- MACD-style momentum where it adds information

The system should evaluate whether platform candle features add information beyond C.8 rather than assuming they do.

For XAU/USD, do not make C.14 dependent on an unverified historical Gold API endpoint. Existing point observations may be used to construct deterministic candles initially. A dedicated OHLC source is optional and must pass reliability/rate-limit/cost/provenance review.

## Forecast evaluation

Use chronological walk-forward evaluation.

Do not use random train/test splitting as final evidence.

Measure at minimum:

- accuracy
- balanced accuracy
- precision / recall by class
- macro F1
- confusion matrix
- baseline comparison
- Brier score
- calibration
- coverage
- abstention rate
- sample count

The system must be allowed to conclude:

```text
USEFUL
WEAK
NO_SIGNAL
INSUFFICIENT_DATA
```

No fabricated confidence.

## Fail-safe law

```text
MISSING
 ↓
safe deterministic fallback?
 ├─ YES → use fallback + degraded provenance
 └─ NO  → INSUFFICIENT_DATA / ABSTAIN
```

Never silently extrapolate missing market data into apparently real data.

## Human forecast review

Frontend remains exactly two wings. Human review is a Telegram interaction inside the Analysis experience, not a third frontend wing.

User flow:

```text
/Update
→ live market

/Analyze
→ analysis / evidence / interpretation / technical context

/Forecast
→ forecast + probability + horizon + model context

later /Forecast
→ if a matured previous forecast exists, automatically offer review
```

User feedback must never be treated as objective ground truth.

The system objectively evaluates the previous forecast against actual market outcomes first.

Human review is a separate meta-data stream.

Recommended progressive interaction:

```text
Previous forecast review

[ Very useful ]
[ Mostly useful ]
[ Direction right, timing wrong ]
[ Direction wrong ]
[ Hard to judge ]
```

Only when useful, request a simple reason:

```text
[ Timing ]
[ USD/IRR ]
[ World Gold ]
[ Local Market ]
[ Premium ]
[ Price Action ]
[ News ]
[ Hard to judge ]
```

Store three separate concepts:

```text
objective outcome
probabilistic forecast quality
human perceived usefulness
```

Human feedback is not online model training. It is audit/evidence first and may become a candidate feature only after controlled statistical validation.

### Forecast lifecycle

```text
GENERATED
→ PENDING
→ ELIGIBLE_FOR_REVIEW
→ OBJECTIVELY_EVALUATED
→ USER_REVIEWED (optional)
```

Keep separate timestamps for:

```text
system forecast time
market/outcome time
user feedback time
```

The review window must be based on the forecast horizon and actual market observation availability, not a fixed 48-hour wall-clock rule.

## KPI engineering rule

Before the C.14 KPI:

1. freeze canonical contracts
2. seed authoritative source inputs
3. let production code derive statuses and metadata
4. use deep copies for nested mutations
5. do not add aliases later to satisfy tests
6. do not weaken production code to satisfy malformed fixtures

## External research boundaries

Research sources:

- `3aLaee/xauusd-trading-bot`
- `JonusNattapong/Ai-XAUUSD-Trading`
- `michael-chow-arch/goldfxgraph`
- `vctb12/GoldTickerLive`

Use them for analytical inspiration only. MT5, broker execution, RL execution, order management, and autonomous trading are out of scope.

Detailed adoption/defer decisions are recorded in `RESEARCH_ADOPTION.md`.
