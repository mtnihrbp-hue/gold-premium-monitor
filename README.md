# Gold Premium Monitor

Decision-support monitoring for the Iranian 18K physical-gold market.

The system combines global gold, USD/IRR, Iranian market-platform prices, fair value, premium/discount behavior, deterministic market state, historical memory, and structured external intelligence. It is designed to be resilient and explainable, not an autonomous trading bot.

## Documentation map

This repository deliberately separates documentation by responsibility:

| File / folder | Authority | Purpose |
|---|---|---|
| `PROJECT_MEMORY.md` | Canonical project memory | Architecture, implemented state, contracts, invariants, current roadmap |
| `README.md` | Human orientation | What the system is, how the repository is organized, current development position |
| `Prompt_Guide.md` | Generic AI behavior | Coding discipline; not project-state documentation |
| `skills/` | Operational AI behavior | Specialist behavior for repository onboarding, engineering, analysis, Neon, Telegram, validation |
| `sql/neon_schema.sql` | Canonical DB schema | Repository copy of the Neon persistence foundation |
| `kpi/` | Executable acceptance evidence | Sprint-specific KPI scripts |

When these documents disagree, follow the authority order in `skills/README.md`; executable code/tests/KPI provide implementation evidence.

## Current development position

```text
main
└── SP-A COMPLETE / FROZEN

SP-B
├── SP-B.1 COMPLETE — Historical Intelligence
├── SP-B.2 COMPLETE — News Intelligence
├── PRE-SP-C.1 COMPLETE — Canonical Time Series
├── PRE-SP-C.2 IMPLEMENTATION — Analysis Snapshot + Scheduler Foundation
└── PRE-SP-C DETOUR CONTINUES

SP-C
└── FUTURE — Prediction + Learning
```

`main` is the stable baseline. `SP-B` is the active development line and must not be merged until its approved scope is validated and explicitly reviewed.

The latest PRE-SP-C.2 implementation fixes include:

- scheduler next-window boundary semantics
- deterministic final-decision alert authority
- Telegram alert guard
- email alert interface compatibility
- regression tests for alert routing
- canonical Neon schema file

The current state is **not declared complete until the KPI and regression/smoke verification pass**.

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
           Telegram           Analysis Snapshot
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

Primary flow:

```text
/Update
→ collect
→ validate
→ calculate
→ deterministic market state
→ Telegram
```

Characteristics:

- user-triggered
- irregular
- current
- lightweight

User-triggered `/Update` activity must not become the Analysis Wing's technical time series.

## Analysis Wing

Answers:

> What does the system currently understand about the market?

Initial schedule contract:

| Setting | Value |
|---|---|
| Timezone | `Asia/Tehran` |
| Interval | 30 minutes |
| Daily window | `08:00` inclusive to `21:00` exclusive |
| Active days | Configurable |

Conceptual flow:

```text
scheduled analysis window
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

A system-generated analysis should be reusable by many Telegram users. User count must not multiply analysis execution.

## Decision model

The frozen deterministic baseline is:

```text
Valuation
→ Premium Direction
→ Momentum
→ Market Structure
→ Conflict
→ Candidate Decision
→ Hysteresis
→ Final Decision
```

Canonical premium language:

```text
DISCOUNT WIDENING
DISCOUNT NARROWING
DISCOUNT STABLE

PREMIUM WIDENING
PREMIUM NARROWING
PREMIUM STABLE
```

For negative premium:

- more negative = `DISCOUNT WIDENING`
- less negative = `DISCOUNT NARROWING`

Buyer-oriented momentum:

| Premium state | Momentum |
|---|---|
| `DISCOUNT WIDENING` | `IMPROVING` |
| `DISCOUNT NARROWING` | `WEAKENING` |
| `DISCOUNT STABLE` | `NEUTRAL` |

A deeply discounted market can still be `WAIT`.

## Alert authority

External BUY/SELL alerts are controlled only by the deterministic final decision.

```text
Candidate: BUY
Final: WAIT
        ↓
NO BUY ALERT
```

This rule applies to every transport, including Telegram and email. Presentation code must not invent or reinterpret decisions.

## Data and persistence

Neon PostgreSQL is the long-term historical store.

The persistence layers remain distinct:

| Layer | Role |
|---|---|
| `market_snapshots` | Market observations |
| `platform_prices` | Platform evidence |
| `market_states` | Deterministic interpreted state |
| `news_events` | Structured external events |
| `price_observations` | Canonical raw time series |
| `analysis_snapshots` | System-generated analysis history |

The canonical repository schema is in `sql/neon_schema.sql`.

Database failure is non-fatal to the core monitor whenever safely possible. Missing values remain `UNKNOWN`/degraded rather than being converted into fake data.

## Technical-analysis direction

The future technical layer is deterministic and operates on actual market-price observations, not premium as a proxy candle.

Initial analytical areas:

- XAU/USD trend and momentum
- USD/IRR trend and volatility
- representative Iranian gold price
- moving averages / RSI / ATR where justified
- support/resistance from observable price structure
- multi-timeframe context
- representative-price candle

Do not import large indicator libraries merely because other trading repositories use them. Keep the first analytical layer small, testable, and explainable.

Representative Iranian price fallback:

```text
Milli → Ayyareh → WallGold → UNKNOWN
```

## Regime and external intelligence

Future deterministic regime states may include:

```text
NORMAL
FEAR
PANIC
RELIEF
UNKNOWN
```

Evidence families include premium stress, volatility, USD/IRR stress, market structure, and high-impact external events.

The regime layer must not be derived from valuation alone. `CHEAP + PANIC` is valid.

LLM use is bounded to context interpretation and narrative generation. The LLM must not calculate fair value, premium, indicators, support/resistance, historical statistics, or independently issue BUY/SELL.

## Telegram product model

Telegram is the cockpit, not the analytical engine.

| Command | Role |
|---|---|
| `/Update` | Live market snapshot |
| `/Technical` | Future deterministic technical view |
| `/Analysis` | Latest persisted analysis snapshot |
| `/History` | Historical evidence |
| `/News` | Structured recent news |
| `/Radar` | Combined analytical read model |
| `/Health` | System/data-quality status |

Do not turn `/Update` into a dump of every analytical feature.

## Validation

Standard verification order:

```text
python -m compileall src
→ targeted tests
→ pytest -q
→ sprint KPI
→ smoke test
→ diff review
→ branch review
```

Never declare a sprint complete from code existence alone.

Useful checks include:

```bash
python kpi/kpi_pre_sp_c1.py
python kpi/kpi_pre_sp_c2.py
python -m compileall src
pytest -q
python src/main.py
```

## Repository structure

```text
gold-premium-monitor/
├── config/                 # Operational configuration
├── kpi/                    # Executable sprint KPIs
├── skills/                 # Reusable AI developer behavior
├── src/                    # Application implementation
├── sql/                    # Canonical database schema
├── tests/                  # Repository-level tests
├── PROJECT_MEMORY.md       # Canonical architecture/state memory
├── Prompt_Guide.md         # Generic AI engineering behavior
└── README.md               # Human-facing orientation
```

The existing `src/caluclator/` spelling is intentionally preserved for compatibility.

## Free-tier operating model

Primary infrastructure remains:

- GitHub / GitHub Actions
- Neon PostgreSQL
- Telegram
- existing free market-data sources
- Resend where configured
- future free-tier LLM infrastructure where practical

Secrets must remain in environment variables and must never be committed.

## Branch discipline

```text
main = stable baseline
SP-B = active development
SP-C = future prediction/learning
```

Do not develop directly on `main`. Do not merge `SP-B` automatically. Review the branch only after implementation, regression, KPI, documentation, and diff checks are complete.

## License

MIT
