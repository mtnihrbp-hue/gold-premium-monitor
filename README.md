# Gold Premium Monitor

Decision-support monitoring for the Iranian 18K physical-gold market.

The system combines XAU/USD, USD/IRR, Iranian gold-platform prices, fair value, premium/discount behavior, deterministic market state, historical memory, structured external intelligence, canonical time-series observations, technical structure, and deterministic market regime. It is designed to be resilient and explainable, not an autonomous trading bot.

## Documentation map

| File / folder | Authority | Purpose |
|---|---|---|
| `PROJECT_MEMORY.md` | Canonical project memory | Architecture, implemented state, contracts, invariants, roadmap |
| `README.md` | Human orientation | Concise overview of the system and repository |
| `Prompt_Guide.md` | Generic AI behavior | Reusable coding discipline; not project-state authority |
| `skills/` | Specialist AI behavior | Reusable onboarding, engineering, market-analysis, Neon, Telegram, validation rules |
| `sql/neon_schema.sql` | Canonical DB schema | Repository copy of the Neon persistence foundation |
| `kpi/` | Acceptance evidence | Executable sprint KPIs |
| `src/` + `tests/` | Implementation evidence | Actual application behavior and regression tests |

Project-state changes are recorded in `PROJECT_MEMORY.md` first. README summarizes; it does not create a second architecture.

## Current development position

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

`main` is the stable baseline. `SP-B` is the active development line and must not be merged until its approved remaining scope is validated and explicitly reviewed.

## Architecture

```text
                    MARKET INPUTS
                         |
        +----------------+----------------+
        |                |                |
      XAU/USD          USD/IRR        Platforms
        |                |                |
        +----------------+----------------+
                         |
                  Quantitative Engine
                         |
        +----------------+----------------+
        |                |                |
     Valuation        Momentum        Structure
        |                |                |
        +----------------+----------------+
                         |
                  Conflict Matrix
                         |
                 Candidate Decision
                         |
                    Hysteresis
                         |
                  Final Decision
                         |
              +----------+-----------+
              |                      |
          Live Wing            Analysis Wing
          /Update              Scheduled run
              |                      |
           Telegram          Technical + Regime
                                     |
                              Analysis Snapshot
                                     |
                                    Neon
```

### Non-negotiable boundaries

```text
CHEAP ≠ BUY
VALUATION ≠ MOMENTUM
CANDIDATE ≠ FINAL DECISION
NEWS ≠ MARKET DATA
LLM ≠ MARKET CALCULATION
```

The quantitative engine measures facts. The intelligence layer interprets context. The decision engine evaluates evidence. These layers must not be collapsed.

## Live Wing

Answers:

> What is happening right now?

Flow:

```text
/Update
→ collect
→ validate
→ calculate
→ deterministic market state
→ Telegram
```

User-triggered `/Update` activity must not become the Analysis Wing's technical time series.

## Analysis Wing

Answers:

> What does the system currently understand about the market?

Current scheduler contract:

| Setting | Value |
|---|---|
| Timezone | `Asia/Tehran` |
| Interval | 30 minutes |
| Daily window | `08:00` inclusive → `21:00` exclusive |
| Active days | configurable |

Conceptual flow:

```text
scheduled window
→ source availability / freshness
→ canonical observations
→ technical structure
→ regime / market mood
→ historical/news context
→ bounded LLM interpretation
→ analysis snapshot
→ Neon
```

A system-generated analysis should be reusable by many users. User count must not multiply analytical execution.

## PRE-SP-C.1 — canonical observations

`price_observations` is the canonical technical time-series layer.

Conceptually supported instruments:

```text
XAUUSD
USD/IRR
REP_IRAN_GOLD
PAXG
```

Technical analysis operates on actual market-price observations, not premium as a proxy candle.

## PRE-SP-C.2 — analysis snapshot foundation

PRE-SP-C.2 established:

- `analysis_snapshots`
- deterministic `source_run_id` idempotency
- live-vs-analysis snapshot separation
- scheduled 30-minute analysis windows
- canonical Neon persistence foundation
- final-decision alert authority

KPI result: **14/14 passed**.

Snapshot persistence is intentionally separate from the C.3 technical/regime primitive layer. C.4 integrates those outputs into the snapshot.

## PRE-SP-C.3 — Price Structure + Regime

PRE-SP-C.3 is **COMPLETE**.

KPI result: **20/20 passed**.

### Representative Iranian price

Fixed fallback chain:

```text
Milli
  ↓
Ayyareh
  ↓
WallGold
  ↓
UNKNOWN
```

The first valid source in this order is selected. The selected source is retained as provenance. The series represents an actual Iranian market price, not premium or fair value.

### Support / resistance

The deterministic technical structure pipeline is:

```text
canonical price observations
→ rolling/local extrema
→ clustering / tolerance
→ strength metadata
→ support / resistance
```

Insufficient history remains explicit; no level is fabricated.

### Market regime

Approved states:

```text
NORMAL
FEAR
PANIC
RELIEF
UNKNOWN
```

Four evidence families:

1. Premium stress
2. Volatility stress
3. USD / market-structure stress
4. External-event stress

Regime hysteresis is separate from SP-A decision hysteresis.

`CHEAP + PANIC` is a valid state. Regime does not issue BUY/SELL decisions.

### C.3 persistence boundary

C.3 creates deterministic analytical primitives. C.4 is the integration boundary for persisting them in `analysis_snapshots`.

Planned C.4 additions:

```text
analysis_snapshots.regime_state
analysis_snapshots.technical_state_json
```

## Decision and alert integrity

External BUY/SELL alerts are controlled only by the deterministic final decision:

```text
Candidate: BUY
Final: WAIT
        ↓
NO BUY ALERT
```

This applies to Telegram and email. Presentation code must not invent or reinterpret decisions.

## Data and persistence

Neon PostgreSQL is the long-term historical store.

| Layer | Responsibility |
|---|---|
| `market_snapshots` | Market observations |
| `platform_prices` | Platform evidence |
| `market_states` | Deterministic interpreted state |
| `news_events` | Structured external events |
| `price_observations` | Canonical raw time series |
| `analysis_snapshots` | System-generated analysis history |

The repository-side schema is `sql/neon_schema.sql`.

Database failure must be non-fatal whenever safely possible. Missing data remains explicit rather than being converted into fake values.

## Telegram product model

Telegram is the cockpit, not the analytical engine.

| Command | Role |
|---|---|
| `/Update` | Live market snapshot |
| `/Technical` | Future deterministic technical read model |
| `/Analysis` | Future persisted analysis read model |
| `/History` | Historical evidence |
| `/News` | Structured news |
| `/Radar` | Combined analytical read model |
| `/Health` | System/data-quality status |

The main update should remain readable and should not become a dump of every future analytical field.

Known non-blocking presentation defect from the latest smoke test: the produced manual update still contains the application header twice (`GOLDPremium:` repeated). This is queued as a Telegram presentation cleanup and does not invalidate the C.3 analytical KPI.

## Validation standard

```text
inspect
→ define change surface
→ implement minimally
→ targeted tests
→ pytest -q
→ sprint KPI
→ smoke test
→ diff review
→ documentation sync
→ branch review
```

Never declare a sprint complete from code existence alone.

## Repository structure

```text
gold-premium-monitor/
├── config/                 # Operational configuration
├── kpi/                    # Executable sprint KPIs
├── skills/                 # Reusable AI developer behavior
├── sql/                    # Canonical database schema
├── src/                    # Application implementation
├── tests/                  # Regression tests
├── PROJECT_MEMORY.md       # Canonical architecture/state memory
├── Prompt_Guide.md         # Generic AI engineering behavior
└── README.md               # Human-facing orientation
```

The existing `src/caluclator/` spelling is intentionally preserved for compatibility.

## Current verification record

Latest supplied evidence:

```text
PRE-SP-C.3 KPI            20/20 PASS
python -m compileall src  PASS
live smoke test            PASS
```

In that smoke run, 9 of 10 platform sources were valid; Daric timed out and was isolated. XAU/USD and USD/IRR observations saved successfully. Market snapshot and market state were saved. The deterministic state remained coherent with `Candidate=BUY` and `Final=WAIT`, and no external BUY/SELL alert was sent.

A full post-C.3 `pytest -q` result was not supplied; the branch should not be described as fully regression-verified until that is executed.

## Next phase

```text
PRE-SP-C.4
Analysis Snapshot Integration
        ↓
Outcome Evaluation Foundation
        ↓
Remaining PRE-SP-C analytical/read-model work
        ↓
SP-B closure review
        ↓
SP-C prediction/learning
```

No prediction model should begin before the analytical memory and evaluation foundations are explicit, testable, and empirically evaluable.

## License

MIT
