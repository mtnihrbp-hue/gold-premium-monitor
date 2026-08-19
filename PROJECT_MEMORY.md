# Gold Premium Monitor — Project Memory

This file is the **canonical project-specific architecture and state memory** for AI developers and maintainers.

`README.md` is the human-facing orientation document. `Prompt_Guide.md` contains generic AI engineering behavior. `skills/` contains reusable specialist operating instructions. They must not become competing architecture documents.

## 1. Project purpose

Gold Premium Monitor is a decision-support system for the Iranian 18K physical-gold market.

It combines:

- XAU/USD world gold
- USD/IRR
- Iranian gold-platform prices
- fair-value calculation
- premium/discount analysis
- momentum and market structure
- deterministic market-state logic
- historical market memory
- structured external news
- a scheduled Analysis Wing
- future technical/regime analysis
- future empirical outcome evaluation
- eventual prediction/learning

It is not an autonomous trading bot.

## 2. Architecture invariants

These are mandatory:

```text
CHEAP ≠ BUY
VALUATION ≠ MOMENTUM
CANDIDATE DECISION ≠ FINAL DECISION
NEWS ≠ MARKET DATA
LLM ≠ MARKET CALCULATION
```

The layers remain separate:

```text
Quantitative Engine
    = measures market facts

Intelligence Layer
    = interprets external context

Decision Engine
    = evaluates evidence
```

Collectors collect. Calculators calculate. Intelligence interprets. Presentation formats. Persistence stores.

Unknown is preferable to fabricated information.

## 3. Branch and development state

```text
main
└── SP-A COMPLETE / FROZEN

SP-B
├── SP-B.1 COMPLETE — Historical Intelligence
├── SP-B.2 COMPLETE — News Intelligence
├── PRE-SP-C.1 COMPLETE — Canonical Time Series
├── PRE-SP-C.2 IMPLEMENTATION — Snapshot/Scheduler Foundation
└── PRE-SP-C DETOUR CONTINUES

SP-C
└── FUTURE — Prediction + Learning
```

`SP-B` is the active development line. Do not merge it into `main` until approved scope, tests, KPI, documentation, and diff review all pass.

## 4. SP-A deterministic baseline

The frozen decision pipeline is:

```text
Valuation
    ↓
Premium Direction
    ↓
Momentum
    ↓
Market Structure
    ↓
Conflict Matrix
    ↓
Candidate Decision
    ↓
Hysteresis
    ↓
Final Decision
```

For negative premium:

- more negative → `DISCOUNT WIDENING`
- less negative → `DISCOUNT NARROWING`
- materially unchanged → `DISCOUNT STABLE`

Buyer-oriented momentum:

```text
DISCOUNT WIDENING → IMPROVING
DISCOUNT NARROWING → WEAKENING
DISCOUNT STABLE → NEUTRAL
```

The conflict matrix is explicit and deterministic. Do not replace it with an opaque weighted score without explicit approval.

## 5. Alert authority

The deterministic `final_decision` is the **single authority** for external BUY/SELL alerts.

```text
Candidate: BUY
Final: WAIT
        ↓
NO BUY ALERT
```

Legacy premium-threshold logic may exist for backward-compatible unit tests, but it must not independently trigger external alerts.

Telegram and email transport layers must defend the same invariant: when a `signal_state` is supplied, they may send only when `signal_state.final_decision` is `BUY` or `SELL`.

## 6. Live Wing

Purpose:

> What is happening right now?

Primary command:

```text
/Update
```

Flow:

```text
collect
→ validate
→ calculate
→ deterministic market state
→ Telegram
```

Properties:

- user-triggered
- irregular
- current
- lightweight
- not a learning time series

## 7. Analysis Wing

Purpose:

> What does the system currently understand about the market?

The Analysis Wing is system-triggered and reusable by many users.

Initial scheduling contract:

| Setting | Value |
|---|---|
| Timezone | `Asia/Tehran` |
| Interval | 30 minutes |
| Window | `08:00` inclusive → `21:00` exclusive |
| Active days | configurable |

The next-window function treats the reference timestamp as already consumed. Therefore an exact `09:00` boundary produces `09:30` as the next window.

Conceptual flow:

```text
scheduled window
→ source availability / freshness
→ canonical observations
→ technical analysis
→ historical context
→ news context
→ regime / market mood
→ bounded LLM interpretation
→ analysis snapshot
→ Neon
```

User-triggered `/Update` requests must not become the Analysis Wing's technical series.

## 8. PRE-SP-C.2 foundation

The current foundation establishes a persistent `analysis_snapshots` layer with deterministic `source_run_id` idempotency.

Conceptual separation:

```text
LIVE_SNAPSHOT
    = user-triggered current observation

ANALYSIS_SNAPSHOT
    = system-triggered analytical observation
```

Current snapshot fields include:

- snapshot type
- analysis timestamp
- source run ID
- analysis window
- market snapshot linkage
- market-state linkage
- XAU/USD
- USD/IRR
- representative Iranian gold price
- premium percent
- valuation state
- momentum state
- structure state
- data-quality metadata

`source_run_id` is unique for idempotent scheduled analysis.

## 9. Scheduler contract

Source file:

```text
src/analysis/scheduler.py
```

Current default:

```text
Asia/Tehran
30 minutes
08:00–21:00
```

`get_next_analysis_windows()` returns strictly future windows relative to `from_time`. Exact schedule boundaries are not returned as the next window.

## 10. Persistence model

Neon PostgreSQL is the long-term historical store.

Canonical raw/derived separation:

| Table | Responsibility |
|---|---|
| `market_snapshots` | market observations used by existing monitor |
| `platform_prices` | individual platform evidence |
| `market_states` | deterministic interpreted market state |
| `news_events` | structured external events |
| `price_observations` | canonical raw technical time series |
| `analysis_snapshots` | system-generated analytical history |

Canonical repository schema:

```text
sql/neon_schema.sql
```

The schema file is the repository source for the PRE-SP-C persistence foundation and should remain synchronized with the Neon database.

Database failure must degrade gracefully and must not become a hidden source of calculations.

## 11. Canonical observations

Conceptually supported instruments:

```text
XAUUSD
USD/IRR
REP_IRAN_GOLD
PAXG
```

`PAXG` is an external global-gold reference and is not part of the Iranian fair-price formula unless an explicitly approved analytical layer says otherwise.

Representative Iranian technical-price fallback:

```text
Milli → Ayyareh → WallGold → UNKNOWN
```

Technical candles must use actual market-price observations, not premium as the candle source.

## 12. Historical Intelligence — SP-B.1 COMPLETE

Purpose: descriptive historical context.

Hard match requirements:

- valuation
- momentum
- premium distance within configured tolerance

Secondary/context matches:

- market structure
- USD/IRR direction when known
- XAU/USD direction when known

Unknown secondary data must not be fabricated and must not automatically block comparison.

SP-B.1 does not predict.

## 13. News Intelligence — SP-B.2 COMPLETE

Flow:

```text
RSS / manual input
→ normalization
→ deduplication
→ deterministic relevance/classification
→ structured news event
→ Neon
```

News does not calculate fair price, premium, technical indicators, or BUY/SELL.

## 14. Technical layer — PRE-SP-C future work

The technical layer must be deterministic and independently testable.

Candidate coverage:

- XAU/USD trend and momentum
- USD/IRR trend and volatility
- representative Iranian gold price
- moving averages
- RSI
- ATR / volatility
- support/resistance
- price structure
- multi-timeframe context
- representative market candle

Do not import a large indicator library without an architectural reason.

Support/resistance should preserve:

- level
- side
- timeframe
- evidence/strength
- freshness
- source

Never let an LLM invent technical levels.

## 15. Regime / market mood

Future initial candidate states:

```text
NORMAL
FEAR
PANIC
RELIEF
UNKNOWN
```

Evidence families:

- premium stress
- volatility stress
- USD/IRR and market-structure stress
- external event stress

`CHEAP + PANIC` is valid.

Regime should use explicit rule families and empirical calibration, not an opaque weighted score invented in advance.

## 16. LLM boundary

LLM may:

- interpret external information
- summarize structured evidence
- connect contextual factors
- produce bounded narrative

LLM must not:

- calculate fair price
- calculate premium
- calculate technical indicators
- invent support/resistance
- invent historical statistics
- override deterministic market state
- independently issue BUY/SELL

LLM metadata should eventually preserve model and prompt versions for auditability.

## 17. Outcome evaluation foundation

Before SP-C prediction/learning, evaluation must be deterministic.

Initial horizons:

```text
+1h
+6h
+24h
```

Horizon semantics are wall-clock based. Find the nearest valid observation within configured tolerance. Do not interpolate initially. Missing target data becomes `INSUFFICIENT_DATA`.

Future evaluation should preserve target time, actual time, lag, reference price, actual price, movement, direction, premium movement, USD movement, XAU/USD movement, and outcome status.

## 18. Telegram product model

Telegram is the cockpit, not the brain.

Current command:

```text
/Update
```

Planned read models:

```text
/Technical
/Analysis
/History
/News
/Radar
/Health
```

Do not put every future analytical field into `/Update`.

Main message hierarchy:

```text
Market
Decision / Market State
Trends
Momentum
Market Structure
Input Directions
Platforms
Timestamp
```

## 19. Documentation architecture

The documentation system intentionally has four layers:

```text
PROJECT_MEMORY.md
    = canonical project architecture/state

README.md
    = human-facing orientation

Prompt_Guide.md
    = generic AI engineering behavior

skills/
    = specialist AI operating instructions
```

Rules:

1. Project facts change in `PROJECT_MEMORY.md` first.
2. README summarizes; it does not create alternate architecture.
3. Prompt Guide contains reusable behavior, not changing sprint facts.
4. Skills explain execution behavior and boundaries; they do not duplicate the entire roadmap.
5. `sql/neon_schema.sql` is canonical database schema evidence for the repository.
6. Source code, tests, KPI, and CI are executable evidence.

## 20. Verification standard

Every implementation change follows:

```text
inspect
→ define change surface
→ implement minimally
→ targeted test
→ regression suite
→ KPI
→ diff review
→ branch review
```

Required baseline checks:

```bash
python -m compileall src
pytest -q
python kpi/kpi_pre_sp_c2.py
python src/main.py
```

Never claim completion unless the relevant checks actually ran and passed.

## 21. Current known verification state

The last provided smoke test showed:

- Python compilation: PASS
- `price_observations` persistence: PASS after Neon schema update
- market snapshot persistence: PASS
- market state persistence: PASS
- decision calculation: internally coherent
- scheduler KPI: previously failed exact-boundary next-window behavior
- alerting: previously violated Candidate vs Final separation
- email alert: previously failed because of a `momentum` keyword mismatch

The current `SP-B` branch now contains code changes addressing those three implementation defects plus regression coverage. Final status remains **NOT COMPLETE** until the KPI, regression suite, and smoke test are rerun successfully.

## 22. SP-B closure direction

The original labels `SP-B.3`, `SP-B.4`, and `SP-B.5` are architectural placeholders rather than mandatory module boundaries.

The approved direction is:

| Original | Current architectural role |
|---|---|
| SP-B.3 | Analysis Wing / bounded LLM interpretation |
| SP-B.4 | Telegram analytical read models |
| SP-B.5 | Combined read model over persisted analysis snapshots |

Do not create duplicate "radar" or agent layers solely to preserve old sprint naming.

## 23. SP-C gate

SP-C prediction/learning starts only after the PRE-SP-C foundation is explicit, testable, and empirically evaluable.

Minimum gate:

```text
canonical observations
→ analysis snapshots
→ technical layer
→ regime layer
→ historical/news context
→ outcome evaluation
→ verified read models
→ then prediction/learning
```
