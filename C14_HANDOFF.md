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

C.14A must be complete and verified before C.14B begins.
C.14B must be evaluated before C.14C operationalizes forecast resolution and human review.

## Two-wing frontend architecture

LIVE WING = /Update and current deterministic market interaction.

ANALYSIS WING = scheduled analysis, evidence, interpretation, features, read model, dataset, candles, forecast, and audit.

Human forecast review remains inside the Analysis Telegram experience. It is not a third frontend wing.

## Decision boundary

Prediction remains separate from Decision.

```text
FACTS → EVIDENCE → INTERPRETATION → FEATURES → READ MODEL → PREDICTION → DECISION
```

Forecast never rewrites facts, evidence, interpretation, features, read model, or current final_decision.

## C.14A objective

Build persistent, deterministic platform candle infrastructure from canonical point observations.

Primary Iranian sources:

- Goldika
- Ayyareh
- Milli
- WallGold

Preserve BUY and SELL separately when explicitly available. Goldika exposes explicit buy/sell prices. Ayyareh exposes goldPrice plus margin/wage fields; inspect the existing collector before deriving side prices and preserve raw and derived values separately.

For single-price sources use SINGLE_PRICE semantics.

Unless a platform provides official OHLC, candles are DERIVED_FROM_POINT_OBSERVATIONS.

```text
OPEN  = first valid observation
HIGH  = maximum valid observation
LOW   = minimum valid observation
CLOSE = last valid observation
```

No interpolation. No forward-fill. No future observations.

Initial canonical timeframe: 30m.

Backfill existing price_observations where coverage exists, preserve explicit backfill provenance, then continue forward collection.

C.14A requires an incremental Neon platform_candles table with provenance and idempotency. Raw price_observations remain authoritative facts.

## C.14B objective

Evaluate whether C.8 features contain predictive signal and whether candle/price-action features add incremental out-of-sample value.

Baseline = C.8 features.

Extended = C.8 + platform candle/price-action features + non-redundant MACD-style momentum.

Forecast target:

UP / NEUTRAL / DOWN

C.5 mapping:

UP → UP
FLAT → NEUTRAL
DOWN → DOWN
INSUFFICIENT_DATA → INSUFFICIENT_DATA

Do not redefine C.5 labels.

Forecast also supports INSUFFICIENT_DATA and ABSTAIN.

Candidate context includes XAU/USD, USD/IRR, Iranian gold, premium/discount, platform consensus/dispersion, regime, volatility, momentum, MA/SMA/EMA, candle structure, price action, MACD-style momentum, relative rate of change, and acceleration/deceleration.

For XAU/USD, do not make C.14 dependent on an unverified historical Gold API endpoint. Existing point observations may form deterministic candles initially. Any external OHLC source must pass reliability, rate-limit, cost, licensing, and provenance review.

## Forecast evaluation

Use chronological walk-forward evaluation. Do not use random train/test splitting as final evidence.

Measure at minimum accuracy, balanced accuracy, precision/recall by class, macro F1, confusion matrix, baseline comparison, Brier score, calibration, coverage, abstention rate, and sample count.

Allowed empirical outcomes: USEFUL, WEAK, NO_SIGNAL, INSUFFICIENT_DATA.

## Fail-safe law

```text
MISSING
 ↓
safe deterministic fallback?
 ├─ YES → fallback + degraded provenance
 └─ NO  → INSUFFICIENT_DATA / ABSTAIN
```

Never silently extrapolate absent market data into apparently real facts.

## C.14C human review and closed-loop audit

User flow:

/Update → live market
/Analyze → analysis/evidence/interpretation/technical context
/Forecast → forecast + probability + horizon
Later /Forecast → if a matured previous forecast exists, offer compact review.

The system objectively evaluates the forecast first. Human review is separate metadata.

Recommended progressive interaction:

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

Store separately:

- objective outcome
- probabilistic forecast quality
- human perceived usefulness

Human feedback is not online model training and must not directly modify model weights or labels.

Lifecycle:

GENERATED → PENDING → ELIGIBLE_FOR_REVIEW → OBJECTIVELY_EVALUATED → USER_REVIEWED (optional)

Keep separate forecast_time, market_outcome_time, and feedback_time. Review eligibility follows forecast horizon and actual observation availability, not a fixed wall-clock interval.

## User-facing terminology

Avoid opaque labels such as DISCOUNT WIDENING and DISCOUNT NARROWING.

Prefer observable statements such as:

- Iranian gold is increasing more slowly than its external drivers.
- Iranian gold is catching up faster than its external drivers.

Internal quantitative analysis may use price level, rate of change, relative rate of change, and acceleration. Do not assert a causal explanation unless evidence establishes it.

## KPI engineering rule

Freeze canonical contracts first. Seed authoritative inputs. Let production logic derive metadata. Use deep copies for nested mutation. Do not add aliases to satisfy tests. Do not weaken production code to satisfy malformed fixtures.

## External research boundaries

Research sources:

- 3aLaee/xauusd-trading-bot
- JonusNattapong/Ai-XAUUSD-Trading
- michael-chow-arch/goldfxgraph
- vctb12/GoldTickerLive

Use them for analytical inspiration only. MT5, broker execution, RL execution, order management, and autonomous trading are out of scope. See RESEARCH_ADOPTION.md for the adoption/defer matrix.
