# PRE-SP-C.14 — Forecast Feedback, Closed-Loop Audit & User Terminology

## Purpose

This document preserves architectural decisions made for C.14 so they survive conversation changes and AI handoffs.

## C.14 split

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

C.14A establishes trustworthy persistent inputs. C.14B evaluates predictive value. C.14C closes the forecast lifecycle without permitting uncontrolled online learning.

## Two frontend wings only

### Live Wing

```text
/Update
→ current collection
→ validation
→ deterministic current state
```

### Analysis Wing

```text
/Analyze
→ evidence / interpretation / technical context

/Forecast
→ probabilistic directional forecast
```

Human review happens inside the Analysis Wing. There is no third user-facing wing.

## Forecast target

Initial target:

```text
UP
NEUTRAL
DOWN
```

C.5 remains authoritative:

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

## Closed-loop forecast lifecycle

```text
FORECAST GENERATED
        ↓
PENDING
        ↓
30-minute Analysis Wing observations
        ↓
OBJECTIVE MARKET PATH
        ↓
FORECAST RESOLUTION
        ↓
USER REVIEW (optional)
        ↓
FORECAST AUDIT
        ↓
WEEKLY ADMIN REPORT
        ↓
CONTROLLED MODEL / FEATURE REVIEW
```

Every forecast should preserve three distinct clocks:

```text
forecast_time
market_outcome_time
feedback_time
```

Do not use a fixed 48-hour wall-clock rule blindly. Review eligibility must respect forecast horizon, actual observation availability, market closure and data freshness.

## Objective evaluation vs human feedback

These are separate datasets.

### Objective outcome

Derived from actual market observations and C.5 outcome semantics.

Examples:

```text
DIRECTION_CORRECT
DIRECTION_WRONG
TIMING_EARLY
TIMING_LATE
MAGNITUDE_TOO_LOW
MAGNITUDE_TOO_HIGH
PROBABILITY_OVERCONFIDENT
PROBABILITY_UNDERCONFIDENT
INSUFFICIENT_DATA
```

### Human assessment

Human feedback is about perceived usefulness/quality, not ground truth.

Preferred progressive Telegram interaction after a forecast matures:

```text
Previous forecast review
[ Very useful ]
[ Mostly useful ]
[ Direction right, timing wrong ]
[ Direction wrong ]
[ Hard to judge ]
```

Only expose a second reason layer when it adds value:

```text
[ Timing ]
[ USD/IRR ]
[ World Gold ]
[ Local Market ]
[ Premium / Relative Price ]
[ Price Action ]
[ News ]
[ Hard to judge ]
```

Do not use a long questionnaire.

## Human feedback guardrail

Human feedback is:

```text
meta-data / audit evidence first
```

It is NOT:

```text
immediate ground truth
immediate label replacement
immediate model-weight update
```

Any future use of human feedback as a predictive feature requires separate statistical validation.

## Weekly admin audit

The system should eventually produce a weekly semantic audit, not a single accuracy percentage.

Minimum sections:

```text
FORECASTS ISSUED
RESOLVED
PENDING
OBJECTIVE DIRECTION ACCURACY
BASELINE COMPARISON
CALIBRATION / BRIER
HUMAN REVIEW COUNT
HUMAN USEFULNESS SUMMARY
MODEL/HUMAN DISAGREEMENT
LARGEST ERROR CLUSTERS
REGIME / HORIZON CLUSTERS
RECOMMENDED INVESTIGATION
```

The report is for controlled engineering review. It must not automatically modify production behavior.

## User-facing terminology

Internal quantitative terms may remain available for engineering, but user-facing language should avoid opaque or mistrusted terminology such as:

```text
DISCOUNT WIDENING
DISCOUNT NARROWING
```

These labels can obscure the actual observed relationship.

### Preferred analytical concept

Use measurable relative movement concepts:

```text
PRICE LEVEL
RATE OF CHANGE
RELATIVE RATE OF CHANGE
ACCELERATION
```

Example:

```text
Iranian gold price ↑
XAU/USD ↑
USD/IRR ↑

Iranian gold is increasing more slowly than its external drivers.
```

or:

```text
Iranian gold is catching up faster than its external drivers.
```

The system must describe observable relationships, not invent causal explanations.

Do not claim why Iranian platforms react differently unless the evidence explicitly establishes the reason.

## Quantitative formulation

A useful internal formulation is:

```text
P(t) = Iranian representative gold price
F(t) = external fair-value proxy
Premium(t) = P(t) / F(t) - 1
```

Then derive:

```text
d(Premium)/dt
```

and potentially:

```text
d²(Premium)/dt²
```

Also compare:

```text
local price velocity
vs
external fair-value velocity
```

The goal is to distinguish:

```text
local price rising but lagging external drivers
```

from:

```text
local price rising faster than external drivers
```

These are observations, not causal explanations.

## Fail-safe rule

```text
MISSING
 ↓
safe deterministic fallback?
 ├─ YES → fallback + degraded provenance
 └─ NO  → INSUFFICIENT_DATA / ABSTAIN
```

Never silently extrapolate missing market information into apparently valid facts.

## Research conclusions preserved

R&D on external repositories supports:

- proper probabilistic scoring
- calibration
- baseline comparison
- chronological / walk-forward evaluation
- explicit abstention
- forecast provenance
- human review as secondary evidence
- segmentation by horizon/regime

Deferred:

- reinforcement learning
- autonomous trading
- MT5/broker execution
- online self-modifying models
- direct user-feedback weight updates

## Architectural principle

The closed loop is:

```text
FORECAST
   ↓
OBSERVE
   ↓
RESOLVE
   ↓
REVIEW
   ↓
AUDIT
   ↓
CONTROLLED MODEL / FEATURE REVIEW
   ↓
RE-EVALUATE
```

It is a closed audit loop, not an uncontrolled self-training loop.
