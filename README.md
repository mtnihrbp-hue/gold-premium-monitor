```markdown
# Gold Premium Monitor

A decision-support monitor for the Iranian 18K physical-gold market.

The system combines:

- XAU/USD world gold price
- USD/IRR exchange rate
- Iranian gold-platform prices
- Fair-value calculation
- Premium/discount analysis
- Market momentum
- Market structure
- Deterministic market-state logic
- Historical market memory
- External news intelligence
- A future scheduled Analysis Wing

The project is deliberately designed as a resilient, explainable, free-tier decision-support system — not an autonomous trading bot.

---

## Current Status

```text
main
└── Stable baseline
    └── SP-A COMPLETE / FROZEN

SP-B
├── SP-B.1 COMPLETE — Historical Intelligence
├── SP-B.2 COMPLETE — News Intelligence
├── PRE-SP-C.1 COMPLETE — Canonical Time Series
├── SP-B.3–B.5 NOT YET IMPLEMENTED
└── PRE-SP-C DETOUR — CURRENT DEVELOPMENT PHASE

SP-C
└── FUTURE — Prediction + Learning
```

- `main` is the stable completed baseline.
- `SP-B` is the active development branch.
- Do not merge `SP-B` into `main` until the remaining SP-B scope and the PRE-SP-C detour have been completed, validated, and explicitly reviewed.

---

## Decision Philosophy

The project intentionally separates measurement, interpretation, and decision logic.

```text
Market observations
        ↓
Valuation
        ↓
Premium direction / Momentum
        ↓
Market Structure
        ↓
Conflict
        ↓
Candidate Decision
        ↓
Hysteresis
        ↓
Final Decision
```

Mandatory distinctions:

| Principle |
|-----------|
| CHEAP ≠ BUY |
| VALUATION ≠ MOMENTUM |
| CANDIDATE DECISION ≠ FINAL DECISION |
| MARKET DATA ≠ NEWS INTERPRETATION |
| LLM INTERPRETATION ≠ QUANTITATIVE CALCULATION |

The deterministic market engine remains the quantitative foundation. External intelligence enriches context. It must not silently replace deterministic market calculations.

---

## System Architecture

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
                   Market State
                         |
              +----------+----------+
              |                     |
           Valuation             Momentum
              |                     |
              +----------+----------+
                         |
                  Market Structure
                         |
                      Conflict
                         |
                 Candidate Decision
                         |
                    Hysteresis
                         |
                  Final Decision
                         |
         +---------------+---------------+
         |               |               |
      Live Wing     Analysis Wing    Intelligence
      (/Update)    (Scheduled)      (News, History)
         |               |               |
      Telegram      Analysis         Neon
         |          Snapshot         PostgreSQL
         |               |               |
         +-------+-------+-------+-------+
                 |               |
           Future Commands   Historical
           /Technical        Memory
           /Analysis
           /History
           /News
           /Radar
           /Health
```

---

## Market Data

The monitor collects, validates, and combines:

- XAU/USD world gold price
- USD/IRR sell rate
- Iranian gold-platform prices
- Fair price
- Lowest executable market price
- Premium/discount
- Fair-price trend
- Premium momentum
- Market structure
- Platform consensus

**Rules:**

- Existing collectors and fallback strategies must remain intact.
- Collector failure is isolated whenever safely possible.
- Missing information becomes `UNKNOWN` when no valid fallback exists.
- Never convert missing data into zero.

Current collectors include Kitco/global-gold fallbacks, Bonbast USD data, and Iranian platform collectors.

---

## Historical Memory

Neon PostgreSQL is the project's long-term historical memory.

The system distinguishes:

| Layer | Storage |
|-------|---------|
| Runtime continuity | Local/runtime state |
| Historical memory | Neon PostgreSQL |

Current persisted concepts:

- `market_snapshots`
- `platform_prices`
- `market_states`
- `news_events`
- `price_observations`

Future analytical snapshots and outcome/evaluation structures remain separate from raw observations.

Database failure is non-fatal. The monitor continues operating using existing fallback/state mechanisms.

---

## Deterministic Market State

The normalized market-state pipeline:

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

### Canonical Premium Terminology

```text
DISCOUNT WIDENING
DISCOUNT NARROWING
DISCOUNT STABLE

PREMIUM WIDENING
PREMIUM NARROWING
PREMIUM STABLE
```

For negative premium:
- More negative → DISCOUNT WIDENING
- Less negative → DISCOUNT NARROWING

For positive premium:
- More positive → PREMIUM WIDENING
- Less positive → PREMIUM NARROWING

### Buyer-Oriented Momentum Semantics

| Premium State | Momentum Meaning |
|---------------|------------------|
| DISCOUNT WIDENING | IMPROVING |
| DISCOUNT NARROWING | WEAKENING |
| DISCOUNT STABLE | NEUTRAL |

The existing conflict matrix is explicit and deterministic. Do not replace it with an opaque weighted score without explicit approval.

---

## Completed Sprints

### SP-A — Deterministic Market State (COMPLETE / FROZEN)

SP-A established the normalized market-state pipeline, conflict matrix, and hysteresis logic. It does not use a weighted score or an LLM to make decisions.

### SP-B.1 — Historical Intelligence (COMPLETE)

**Purpose:** Use historical market states as descriptive context.

**Hard matching requirements:**
- Valuation
- Momentum
- Premium distance within configured tolerance

**Secondary/context matching:**
- Market structure
- USD/IRR direction when known
- XAU/USD direction when known

Unknown secondary information must not be fabricated. SP-B.1 does not predict or forecast — it provides historical context only.

**KPI:** 10/10 passed, 0 failed

### SP-B.2 — News Intelligence (COMPLETE)

**Pipeline:**

```text
RSS / manual input
        ↓
Normalization
        ↓
Deduplication
        ↓
Deterministic relevance / classification
        ↓
Structured news event
        ↓
Neon
```

News intelligence is intentionally separate from quantitative calculation. The deterministic classifier uses a controlled event vocabulary and conservative `UNKNOWN` / `UNCERTAIN` states where evidence is insufficient.

**SP-B.2 does not:**
- Calculate fair price
- Calculate premium
- Predict prices
- Issue BUY/SELL decisions
- Require an LLM

**KPI:** 10/10 passed, 0 failed

### PRE-SP-C.1 — Canonical Time Series (COMPLETE)

Establishes `price_observations` as the canonical technical time-series layer.

**Conceptually supported instruments:**
- XAUUSD
- USD/IRR
- PAXG
- REP_IRAN_GOLD

**Architecture separation:**

| Layer | Purpose |
|-------|---------|
| `price_observations` | Canonical time-series data |
| `market_snapshots` | Market observations |
| `market_states` | Interpreted deterministic state |

This prevents irregular user-triggered `/Update` requests from becoming the accidental technical-analysis time series.

**KPI:** 10/10 passed, 0 failed

---

## PRE-SP-C Architecture Detour

Before SP-C prediction and learning, the project must establish analytical infrastructure between the live monitor and future evaluation.

The architecture is intentionally split into two wings.

### Live Wing

**Answers:** What is happening right now?

**Primary command:** `/Update`

```text
collect → validate → calculate → deterministic market state → Telegram
```

**Characteristics:**
- User-triggered
- Irregular
- Current
- Lightweight

It must not automatically trigger the full intelligence pipeline.

### Analysis Wing

**Answers:** What does the system currently understand about the market?

System-triggered by scheduled analysis.

**Initial target:**

| Setting | Value |
|---------|-------|
| Timezone | Asia/Tehran |
| Default interval | 30 minutes |
| Default window | 08:00 inclusive – 21:00 exclusive |
| Active days | Configurable |

The scheduler is calendar/window based rather than assuming a fixed number of daily executions.

**Future source-aware scheduling must account for:**
- Global gold availability
- Iranian gold-market availability
- USD/IRR availability
- News availability
- Holidays and overrides

**Conceptual flow:**

```text
Scheduled analysis window
        ↓
Source availability / freshness check
        ↓
Market observation
        ↓
Technical analysis
        ↓
Historical context
        ↓
News context
        ↓
Regime / market mood
        ↓
LLM interpretation
        ↓
Analysis snapshot
        ↓
Neon
```

**Key principle:** One system-generated analysis should be reusable by many Telegram users. User count must not multiply analysis execution.

### Live Snapshot vs Analysis Snapshot

| Aspect | LIVE_SNAPSHOT | ANALYSIS_SNAPSHOT |
|--------|---------------|-------------------|
| Meaning | User requested current market info | System independently analyzed the market |
| Trigger | User-triggered | System-triggered |
| Timing | Current | Timestamped |
| Depth | Lightweight | Enriched |
| Persistence | Transient | Persisted |
| Reusability | Single user | Reusable by many |
| Purpose | Immediate use | Historical evaluation, future learning |

Future prediction logic should learn from system-generated analysis snapshots, not arbitrary user `/Update` requests.

---

## Future Components

### Technical Analysis Direction

Planned command: `/Technical`

**Potential coverage:**
- XAU/USD trend
- USD/IRR trend
- Representative Iranian gold price
- Moving averages
- RSI
- ATR / volatility
- Support/resistance
- Price structure
- Market-price candle

The technical layer must be deterministic and testable. The initial design intentionally avoids importing huge indicator libraries simply because other trading repositories use them.

### Representative Iranian Gold Price

The future technical candle must represent an actual market-price series — it must NOT use premium as the candle source.

**Deterministic fallback chain:**

```text
Milli → Ayyareh → WallGold → UNKNOWN
```

The first implementation must remain deterministic and explainable. Do not blindly average all platforms.

### Candle

The current Telegram premium visualization is part of the existing momentum engine.

The future technical candle is different — it represents actual representative market price rather than premium/fair-value relationship.

**Future output format (example):**

```text
CANDLE — MILLI

O 190.24
H 191.05
L 189.90
C 190.66
```

The exact rendering belongs to the Technical layer.

### Support and Resistance

Future support/resistance must be deterministic.

**Candidate architecture:**
- Swing highs/lows
- Rolling local extrema
- Clustering/tolerance
- Timeframe
- Evidence/strength metadata

**The model must retain:**
- Support level
- Resistance level
- Timeframe
- Strength/quality
- Freshness
- Source

Do not use an LLM to invent technical levels. Do not turn support/resistance directly into BUY/SELL logic without explicit approval.

### XAU/USD and USD/IRR

Both are first-class analytical variables.

**XAU/USD:** Provides global gold context — trend, momentum, volatility, support/resistance

**USD/IRR:** Provides critical Iranian market context — trend, volatility, support/resistance, regime

Neither should silently override the deterministic local gold-state engine.

### PAXG

PAXG is an external gold-market reference.

**It is not:**
- A replacement for XAU/USD
- Part of the Iranian fair-price formula
- A direct BUY/SELL signal

PAXG may become an additional input in the global-gold context layer. The time-series schema supports PAXG. Collection and analytical integration may be added later after a reliable free source is selected.

### Regime / Market Mood

The future regime layer should be deterministic.

**Candidate states:**

```text
NORMAL
FEAR
PANIC
RELIEF
UNKNOWN
```

**Evidence families:**

| Family | Sources |
|--------|---------|
| A. Premium stress | Premium magnitude, rate-of-change |
| B. Volatility stress | ATR, normalized range, price volatility |
| C. USD / market-structure stress | USD/IRR direction/volatility, platform spread, participation, consensus |
| D. External-event stress | High-impact news, event density |

**Important invariant:** `CHEAP + PANIC` must remain a valid state. Regime must not be derived from valuation alone.

The initial design should prefer explicit rule families over an opaque weighted score. Regime hysteresis should prevent rapid oscillation caused by noise. Exact numerical thresholds require empirical calibration and should not be invented prematurely.

### News and Historical Context

SP-B.1 historical context and SP-B.2 news context are inputs to the future Analysis Wing.

**Historical context provides:**
- Similar-state count
- Sample size
- Descriptive historical statistics
- Matched characteristics

**News context provides:**
- Relevant event count
- High-impact events
- Event types
- Directional context
- Uncertainty
- Recency / time decay

Neither layer independently issues BUY/SELL.

---

## LLM Boundary

Future LLM functionality is contextual intelligence.

**LLM may:**
- Interpret
- Summarize
- Connect
- Contextualize

**LLM must NOT:**
- Calculate fair price
- Calculate premium
- Calculate technical indicators
- Invent support/resistance
- Invent historical statistics
- Override deterministic market state
- Independently issue BUY/SELL

Future Groq/free-tier infrastructure is preferred. LLM failure must degrade gracefully.

**LLM metadata should eventually preserve:**
- `llm_status`
- `llm_model`
- `llm_prompt_version`

So narratives remain auditable.

---

## Outcome Evaluation

Before SP-C begins, the project must define deterministic outcome evaluation.

**Initial horizons:** +1h, +6h, +24h

Horizon meaning is wall-clock based:

```text
Analysis at 10:00
  +1h  → target 11:00
  +6h  → target 16:00
  +24h → target next day 10:00
```

Find the nearest valid observation within a configured tolerance. Do not interpolate in the initial implementation. If no valid observation exists: `INSUFFICIENT_DATA`.

**The stored evaluation should preserve:**
- Target time
- Actual observation time
- Observation lag
- Reference price
- Actual price
- Absolute movement
- Percentage movement
- Direction
- Premium movement
- USD movement
- XAU/USD movement
- Outcome status

This is required for future empirical learning.

---

## Telegram Product Direction

Telegram remains the cockpit, not the analytical engine.

| Command | Purpose |
|---------|---------|
| `/Update` | Live snapshot |
| `/Technical` | Technical-analysis view |
| `/Analysis` | Latest analysis snapshot |
| `/History` | Historical context |
| `/News` | Recent structured news |
| `/Radar` | Combined intelligence view |
| `/Health` | System and data-quality status |

Do not dump every future analytical field into `/Update`. Detailed platform evidence should remain near the bottom of the market update.

**Current message hierarchy:**

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

---

## SP-B Closure Direction

The original SP-B.3–B.5 structure is subject to architectural review.

| Original | Intended Direction |
|----------|-------------------|
| SP-B.3: LLM Interpretation | Becomes an Analysis Wing component |
| SP-B.4: Telegram Intelligence Commands | Becomes a Telegram Read Model |
| SP-B.5: Market Intelligence Radar | Becomes a read model over the persisted Analysis Snapshot |

The original names do not have to survive unchanged. The architecture must avoid unnecessary duplicate "radar" or agent layers.

SP-B should only merge to `main` when the remaining scope is explicitly completed or formally closed.

---

## Repository Structure

```text
gold-premium-monitor/
├── config/
├── skills/
├── src/
│   ├── alerts/
│   ├── caluclator/             # Intentionally preserved spelling
│   ├── collector/
│   ├── database/
│   ├── intelligence/
│   ├── persistence/
│   ├── validation/
│   ├── worker/
│   └── main.py
├── tests/
├── kpi/
├── PROJECT_MEMORY.md
├── Prompt_Guide.md
└── .github/workflows/
```

The existing directory name `caluclator` is intentionally preserved for compatibility.

---

## Configuration

The project uses environment variables for secrets and `config/config.json` for operational thresholds.

**Typical secrets:**

```text
RESEND_API_KEY
EMAIL_TO
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
DATABASE_URL
```

Never commit secrets.

---

## Free-Tier Constraint

The project is intentionally built without paid infrastructure.

**Current primary services:**
- GitHub / GitHub Actions
- Neon PostgreSQL free tier
- Telegram
- Existing free market-data sources
- Resend where already configured

Future LLM work is expected to use free-tier infrastructure such as Groq where practical.

---

## Engineering Invariants

1. Collectors collect.
2. Calculators calculate.
3. Intelligence interprets external context.
4. Decision logic remains explicit and testable.
5. Telegram presents information; it does not become the brain.
6. Persistence stores analytical state; it does not hide calculations.
7. Unknown is preferable to fabricated information.
8. External failures are non-fatal whenever safely possible.
9. Every implementation sprint requires automated tests and an executable KPI.
10. Future-sprint functionality must not leak into the current sprint.
11. Surgical changes are preferred over broad refactors.
12. Completion requires executable verification.

Reusable AI-developer behavior is stored under `skills/`. Start with `core-engineering.md` and `repository-onboarding.md`, then load only the skills relevant to the task.

---

## Validation Standard

Before declaring a sprint complete:

```bash
python -m compileall src
```

Then:

```bash
pytest -q
```

Then the sprint-specific KPI.

Application smoke testing must also pass. No sprint is complete on code existence alone. The repository also contains CI smoke-test/import validation.

---

## Current Development Position

```text
main        = stable frozen baseline
SP-B        = active development line
SP-B.1      = COMPLETE
SP-B.2      = COMPLETE
PRE-SP-C.1  = COMPLETE
PRE-SP-C.2+ = NOT IMPLEMENTED
SP-C        = FUTURE
```

---

## Next Phase

The immediate implementation target is **PRE-SP-C.2** with dependency chain:

```text
PRE-SP-C.1  Canonical Time Series
        ↓
PRE-SP-C.2  Technical Analysis Foundation
        ↓
PRE-SP-C.3  Price Structure + Regime
        ↓
PRE-SP-C.4  Analysis Wing + Snapshot Assembly
        ↓
PRE-SP-C.5  Outcome Evaluation
        ↓
PRE-SP-C.6  Telegram Read Model + LLM Narrative
        ↓
SP-B closure review
        ↓
SP-C
```

No SP-C prediction model should be started before the PRE-SP-C gates are satisfied.

---

## License

MIT
```
