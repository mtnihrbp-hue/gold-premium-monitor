# Gold Premium Monitor — Project Memory

This file is the **canonical project-specific architecture and current-state memory** for maintainers and AI implementation agents.

Documentation responsibilities are intentionally separated:

| Document | Authority | Purpose |
|---|---|---|
| `PROJECT_MEMORY.md` | Canonical project memory | Architecture, invariants, implemented state, contracts, current roadmap |
| `README.md` | Human orientation | Concise system/repository overview |
| `Prompt_Guide.md` | Generic AI behavior | Reusable engineering discipline; not sprint-state authority |
| `skills/` | Specialist operating rules | Reusable AI behavior by domain |
| `sql/neon_schema.sql` | Repository DB schema | Canonical repository-side Neon schema |
| `src/`, `tests/`, `kpi/`, CI | Executable evidence | Actual implementation and verification |

When documentation conflicts, use the higher-authority source above; use executable behavior as implementation evidence.

## 1. Project purpose

Gold Premium Monitor is a decision-support monitor for the Iranian 18K physical-gold market.

It combines:

- XAU/USD world gold
- USD/IRR
- Iranian gold-platform prices
- fair-value calculation
- premium/discount analysis
- momentum and market structure
- deterministic market-state logic
- historical market memory
- structured news intelligence
- canonical market observations
- scheduled Analysis Wing infrastructure
- deterministic technical structure
- deterministic market regime
- future outcome evaluation
- eventual prediction/learning

It is **not** an autonomous trading bot.

## 2. Architecture invariants

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

Unknown / insufficient data is preferable to fabricated information.

## 3. Branch and sprint state

```text
main
└── SP-A COMPLETE / FROZEN

SP-B
├── SP-B.1 COMPLETE — Historical Intelligence
├── SP-B.2 COMPLETE — News Intelligence
├── PRE-SP-C.1 COMPLETE — Canonical Time Series
├── PRE-SP-C.2 COMPLETE — Analysis Snapshot + Scheduler Foundation
├── PRE-SP-C.3 COMPLETE — Price Structure + Regime
└── PRE-SP-C.4 NEXT — Analysis Snapshot Integration

SP-C
└── FUTURE — Prediction + Learning
```

`SP-B` is the active development line. Do not merge it into `main` until the approved remaining scope, regression tests, KPI, documentation, and diff review are explicitly satisfied.

## 4. Frozen SP-A decision baseline

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
SP-A Hysteresis
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

Do not replace the explicit conflict matrix with an opaque weighted score without approval.

## 5. Alert authority

The deterministic `final_decision` is the **single authority** for external BUY/SELL alerts.

```text
Candidate: BUY
Final: WAIT
        ↓
NO BUY ALERT
```

Legacy premium-threshold evaluation may remain for backward-compatible tests, but it must not independently trigger external alerts.

Telegram and email must respect the same rule when a deterministic `signal_state` is available.

## 6. Live Wing

Purpose:

> What is happening right now?

Primary flow:

```text
/Update
→ collect
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

User-triggered `/Update` requests must not become the Analysis Wing's technical history.

## 7. Analysis Wing

Purpose:

> What does the system currently understand about the market?

System-triggered analysis is reusable by many Telegram users.

Current scheduling contract:

| Setting | Value |
|---|---|
| Timezone | `Asia/Tehran` |
| Interval | 30 minutes |
| Window | `08:00` inclusive → `21:00` exclusive |
| Active days | configurable |

The scheduler's `get_next_analysis_windows()` treats the reference timestamp as already consumed. An exact `09:00` reference therefore produces `09:30` as the next window.

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

## 8. PRE-SP-C.1 — canonical time series

`price_observations` is the canonical technical time-series layer.

Conceptually supported instruments:

```text
XAUUSD
USD/IRR
REP_IRAN_GOLD
PAXG
```

Raw observations remain separate from interpreted states.

Technical analysis must consume actual market-price observations, not premium as a proxy candle.

## 9. PRE-SP-C.2 — analysis snapshot foundation COMPLETE

The foundation establishes `analysis_snapshots` with deterministic `source_run_id` idempotency.

Conceptual distinction:

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

PRE-SP-C.2 KPI: **14/14 passed**.

`regime_state` and `technical_state_json` are intentionally **not yet persisted**. Their addition belongs to PRE-SP-C.4, when the snapshot builder integrates the C.3 outputs.

## 10. PRE-SP-C.3 — Price Structure + Regime COMPLETE

PRE-SP-C.3 creates deterministic analytical primitives without changing the SP-A decision engine and without creating autonomous BUY/SELL logic.

### 10.1 Representative Iranian price

The fixed fallback chain is:

```text
Milli
  ↓
Ayyareh
  ↓
WallGold
  ↓
UNKNOWN
```

Rules:

- first valid source in that order wins
- invalid/missing prices are skipped
- all three unavailable → `UNKNOWN`
- selected source is retained as provenance
- the module is based on canonical `price_observations`, not the live `markets` dict

This is an actual Iranian market-price series, not premium, fair value, or an all-platform average.

### 10.2 Support / resistance

The technical structure layer is deterministic and uses real market-price observations.

Initial architecture:

```text
price observations
→ local extrema
→ clustering / tolerance
→ strength metadata
→ support / resistance levels
```

Level metadata includes the analytical evidence needed for reproducibility, including side, level, source/timeframe context, contribution count/strength, and freshness where available.

Insufficient history is explicit. No technical level is fabricated.

### 10.3 Regime

Approved regime states:

```text
NORMAL
FEAR
PANIC
RELIEF
UNKNOWN
```

Four evidence families are explicitly separated:

| Family | Evidence |
|---|---|
| A. Premium Stress | premium magnitude and change |
| B. Volatility Stress | normalized/volatility measures |
| C. USD / Market Structure Stress | USD/IRR change, spread, structure evidence |
| D. External Event Stress | high-impact news/event density |

Regime classification is deterministic, configurable, explainable, and uses separate hysteresis from SP-A decision hysteresis.

Mandatory invariant:

```text
Valuation = CHEAP
Regime = PANIC
```

is valid.

Regime does **not** issue BUY/SELL decisions.

### 10.4 C.3 persistence boundary

PRE-SP-C.3 creates analytical primitives only.

Persistence integration belongs to PRE-SP-C.4:

```text
C.3 primitives
    ↓
C.4 snapshot builder integration
    ↓
analysis_snapshots.regime_state
analysis_snapshots.technical_state_json
```

Do not move this boundary earlier without explicit approval.

PRE-SP-C.3 KPI: **20/20 passed**.

The supplied smoke test also compiled the new analysis modules successfully and completed a live run with market snapshot/state persistence.

## 11. Neon persistence model

Neon PostgreSQL is the long-term historical store.

| Table | Responsibility |
|---|---|
| `market_snapshots` | Existing market observations |
| `platform_prices` | Platform evidence |
| `market_states` | Deterministic interpreted state |
| `news_events` | Structured external events |
| `price_observations` | Canonical raw technical time series |
| `analysis_snapshots` | System-generated analysis history |

Canonical repository schema:

```text
sql/neon_schema.sql
```

Database failure must degrade gracefully and must not become a hidden calculation layer.

## 12. Technical direction after C.3

The technical layer remains deterministic and intentionally small.

Approved future coverage includes:

- XAU/USD trend and momentum
- USD/IRR trend and volatility
- representative Iranian price
- moving averages / RSI / ATR where justified
- support/resistance
- multi-timeframe context
- representative market candle

Do not introduce a large indicator library merely because other trading repositories use one.

## 13. Regime direction after C.3

Regime thresholds must remain explainable and calibratable.

Do not replace the four-family rule structure with a hidden weighted score.

Do not derive regime from valuation alone.

Do not use regime as a direct trading signal.

## 14. Historical and news intelligence

SP-B.1 is descriptive historical context only.

SP-B.2 is structured external-news context only.

Neither layer independently calculates fair price, premium, technical indicators, or BUY/SELL decisions.

Both are future Analysis Wing inputs.

## 15. LLM boundary

LLM may:

- interpret external information
- summarize structured evidence
- connect contextual factors
- produce bounded narrative

LLM must not:

- calculate fair price
- calculate premium
- calculate indicators
- invent support/resistance
- invent historical statistics
- override deterministic market state
- independently issue BUY/SELL

## 16. Telegram product model

Telegram is the cockpit, not the analytical engine.

Current command:

```text
/Update
```

Planned analytical read models:

```text
/Technical
/Analysis
/History
/News
/Radar
/Health
```

The main update should remain readable and should not become a dump of every future analytical field.

Known non-blocking presentation defect from the latest smoke test:

```text
GOLDPremium:
GOLDPremium:
```

The application header is currently duplicated in the produced manual-update message. This is a Telegram presentation defect, not a PRE-SP-C.3 analytical failure, and remains queued for a dedicated cleanup.

## 17. Outcome evaluation foundation

Before SP-C prediction/learning, deterministic outcome evaluation must exist.

Initial horizons:

```text
+1h
+6h
+24h
```

Use wall-clock targets, nearest valid observations within configured tolerance, no interpolation initially, and explicit `INSUFFICIENT_DATA` when target data is unavailable.

## 18. Documentation architecture

The documentation system has distinct responsibilities:

```text
PROJECT_MEMORY.md
    = canonical project state/architecture

README.md
    = human-facing summary

Prompt_Guide.md
    = generic AI engineering rules

skills/
    = specialist operating instructions

sql/neon_schema.sql
    = repository DB schema
```

Rules:

1. Update `PROJECT_MEMORY.md` whenever project architecture/state changes.
2. Update `README.md` when a completed capability changes the human-facing system map.
3. Do not copy sprint-specific facts into every specialist skill.
4. Update a specialist skill only when reusable operating behavior changes.
5. Keep executable evidence in code/tests/KPI; do not replace it with prose.

## 19. Verification standard

Every implementation change follows:

```text
inspect
→ define change surface
→ implement minimally
→ targeted test
→ regression suite
→ KPI
→ diff review
→ documentation sync
→ branch review
```

Required completion evidence is explicit:

```text
PASS
FAIL
UNKNOWN
NOT RUN
```

Never claim a sprint is complete when a mandatory validation layer is still unverified.

## 20. Current verification record

Latest user-provided PRE-SP-C.3 evidence:

- PRE-SP-C.3 KPI: **20/20 passed**
- `python -m compileall src`: **PASS**
- live smoke execution: **PASS**
- 9/10 platform sources valid in the smoke run; Daric timed out and was isolated
- XAU/USD and USD/IRR observations persisted successfully
- market calculation completed
- market snapshot persisted
- market state persisted
- SP-A state remained coherent: `Candidate=BUY`, `Final=WAIT`
- no external BUY/SELL alert was emitted for the `Final=WAIT` state
- Telegram delivered the manual update
- duplicated `GOLDPremium:` header remains a presentation defect

A full `pytest -q` result for the post-C.3 branch was not provided in the latest evidence; do not label the whole branch fully verified until it is run.

## 21. SP-B closure direction

Original SP-B.3/B.4/B.5 labels are architectural placeholders, not mandatory module boundaries.

Approved direction:

| Original | Current role |
|---|---|
| SP-B.3 | Analysis Wing / bounded LLM interpretation |
| SP-B.4 | Telegram analytical read models |
| SP-B.5 | Combined read model over persisted analysis snapshots |

Do not create duplicate agent/radar layers solely to preserve old sprint naming.

## 22. Next phase — PRE-SP-C.4

PRE-SP-C.4 integrates the C.3 analytical primitives into the scheduled Analysis Wing and persisted `analysis_snapshots` layer.

Approved persistence additions:

```text
analysis_snapshots.regime_state
analysis_snapshots.technical_state_json
```

C.4 is the persistence/integration boundary, not C.3.

## 23. SP-C gate

SP-C prediction/learning starts only after:

```text
canonical observations
→ analysis snapshots
→ technical layer
→ regime layer
→ historical/news context
→ outcome evaluation
→ verified read models
→ prediction/learning
```

No prediction model should start before those foundations are explicit, testable, and empirically evaluable.
