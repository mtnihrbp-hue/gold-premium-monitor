# PRE-SP-C.14 — KIMI Engineering Handoff

This is the canonical implementation handoff for the split C.14 work.

## Phase split

```text
PRE-SP-C.14A
Candle & Market-Structure Data Infrastructure

        ↓

PRE-SP-C.14B
Forecast Features, Baselines, Evaluation & Forecast Engine

        ↓

PRE-SP-C.14C
Forecast Resolution, Human Review & Closed-Loop Audit
```

C.14A establishes trustworthy persistent inputs. C.14B evaluates predictive value. C.14C closes the forecast lifecycle through objective resolution, optional human review, calibration, and audit.

## Contract boundary

Prediction remains separate from Decision.

```text
FACTS → EVIDENCE → INTERPRETATION → FEATURES → READ MODEL → PREDICTION → DECISION
```

Forecast never rewrites facts, evidence, interpretation, features, read model, or current final_decision.

## C.14A and C.14B contracts

C.14A preserves deterministic candle construction:

```text
OPEN  = first valid observation
HIGH  = maximum valid observation
LOW   = minimum valid observation
CLOSE = last valid observation
```

Rules:

- no interpolation
- no forward-fill
- no future observations
- preserve explicit buy/sell semantics
- preserve provenance

C.14B forecast contract:

```text
UP
NEUTRAL
DOWN
```

C.5 mapping remains authoritative:

```text
UP → UP
FLAT → NEUTRAL
DOWN → DOWN
INSUFFICIENT_DATA → INSUFFICIENT_DATA
```

Additional operational states:

```text
ABSTAIN
INSUFFICIENT_DATA
```

Forecast never directly generates BUY/WAIT/SELL.

## C.14C closed-loop audit contract

Lifecycle:

```text
GENERATED
→ PENDING
→ ELIGIBLE_FOR_REVIEW
→ OBJECTIVELY_EVALUATED
→ USER_REVIEWED (optional)
```

Preserve separate clocks:

```text
forecast_time
market_outcome_time
feedback_time
```

Objective market outcome and human assessment are separate datasets.

Human feedback is metadata/audit evidence. It is not direct label replacement and not online model training.

## Human review interaction

Preferred compact review:

```text
Previous forecast review
[ Very useful ]
[ Mostly useful ]
[ Direction right, timing wrong ]
[ Direction wrong ]
[ Hard to judge ]
```

Optional reason layer:

```text
[ Timing ] [ USD/IRR ] [ World Gold ] [ Local Market ]
[ Premium ] [ Price Action ] [ News ] [ Hard to judge ]
```

## User-facing terminology

Avoid opaque labels:

```text
DISCOUNT WIDENING
DISCOUNT NARROWING
```

Prefer observable statements:

- Iranian gold is increasing more slowly than its external drivers.
- Iranian gold is catching up faster than its external drivers.

Internal quantitative terms may use:

```text
price level
rate of change
relative rate of change
acceleration
```

Do not claim causal explanations without evidence.

## Fail-safe rule

```text
MISSING
 ↓
safe deterministic fallback?
 ├─ YES → fallback + degraded provenance
 └─ NO  → INSUFFICIENT_DATA / ABSTAIN
```

## External research boundary

External research informs analysis only.

Deferred:

- MT5/broker execution
- autonomous trading
- reinforcement-learning execution
- online self-modifying models
- direct user-feedback weight updates
