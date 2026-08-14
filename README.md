# Gold Premium Monitor

A decision-support monitor for the Iranian 18K physical-gold market. The system combines world gold, USD/IRR, Iranian platform prices, fair-value calculations, premium/discount analysis, historical memory, and deterministic market-state logic, then presents the result through Telegram and email.

The project is being developed in controlled sprints. The current completed engineering foundation is Sprint 1 (Neon persistence) plus Sprint A (deterministic market-state and decision refinement). External news intelligence and prediction remain future work.

## Current Decision Philosophy

The system deliberately separates:

```text
Market observations
        ↓
Valuation
        ↓
Premium direction / Momentum
        ↓
Market structure
        ↓
Conflict
        ↓
Candidate decision
        ↓
Hysteresis
        ↓
Final decision
```

Important distinctions:

- **CHEAP does not automatically mean BUY.**
- Valuation and momentum are separate dimensions.
- Candidate decision and final decision are separate because hysteresis controls state transitions.
- Quantitative calculations are deterministic.
- Future LLM components will interpret external information rather than invent market values.

## What Exists Now

### Market data

The monitor collects, validates and combines:

- XAU/USD world gold price
- USD/IRR sell rate
- Iranian gold-platform prices
- fair price
- lowest executable market price
- premium/discount
- fair-price trends
- premium momentum
- market structure and platform consensus

The current collectors include Kitco/global-gold fallbacks, Bonbast USD data, and Iranian platform collectors. Existing validation and fallback mechanisms must remain intact.

### Sprint 1 — Historical Memory

Neon PostgreSQL is the long-term historical store.

Core persisted observations include:

- `market_snapshots`
- `platform_prices`
- existing system-event storage for future intelligence work

Database failure is non-fatal. The monitor must continue operating using its existing fallback/state mechanisms.

### Sprint A — Deterministic Market State

SP-A adds a normalized market-state pipeline:

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

Canonical premium terminology:

```text
DISCOUNT WIDENING
DISCOUNT NARROWING
DISCOUNT STABLE

PREMIUM WIDENING
PREMIUM NARROWING
PREMIUM STABLE
```

The existing deterministic conflict matrix is intentionally explicit and testable. SP-A does not use a weighted score or an LLM to make decisions.

### Telegram

Telegram is the primary user-facing cockpit.

The current on-demand workflow is the `Update` command. The architecture is intentionally suitable for future commands such as:

- analysis
- sentiment
- history
- risk
- health/KPI

The main market message is structured so the decision and interpreted state appear before the detailed platform evidence. The platform table remains at the bottom for inspection.

Current message hierarchy:

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

Input directions for world gold and USD are part of the **Market** context rather than a separate intelligence layer.

## Future Roadmap

### SP-B — External Market Intelligence

Planned capabilities:

- free-source/RSS news collection
- structured news-market events
- political/geopolitical context
- USD/IRR technical structure
- XAU/USD technical structure
- support/resistance
- market mood / fear-greed style context adapted to Iran
- market regime detection
- historical state analogues

SP-B must enrich the deterministic SP-A baseline rather than replace it.

### SP-C — Prediction and Learning

Future work will use the historical state and outcome data to evaluate:

- expected movement over defined horizons
- confidence based on historical evidence
- hypothesis tracking
- prediction accuracy
- model error
- regime-specific behavior
- eventual BUY / WAIT / SELL decision intelligence

The system must learn from observed outcomes rather than rely on unexplained LLM opinions.

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
              +----------+----------+
              |                     |
           Telegram              Email
              |
         Future commands
              |
         +----+----+----+
         |    |    |    |
     Analysis Risk History Health

                    Neon PostgreSQL
                       |
                Historical memory
```

## Repository Structure

```text
gold-premium-monitor/
├── config/
├── skills/                     # Reusable AI-developer behavior
├── src/
│   ├── alerts/                 # Telegram/email presentation and transport
│   ├── caluclator/             # Existing calculation/signal modules
│   ├── collector/              # Market-data collectors and fallbacks
│   ├── database/               # Neon PostgreSQL persistence
│   ├── persistence/            # Local/state-cache persistence
│   ├── validation/             # Data-quality guards
│   ├── worker/                 # Telegram trigger infrastructure
│   └── main.py
├── tests/
├── kpi/
├── PROJECT_MEMORY.md
├── Prompt_Guide.md
└── .github/workflows/
```

The existing directory name `caluclator` is intentionally preserved for compatibility.

## Configuration

The project uses environment variables for secrets and `config/config.json` for operational thresholds.

Typical secrets include:

```text
RESEND_API_KEY
EMAIL_TO
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
DATABASE_URL
```

Never commit secrets.

## Free-Tier Constraint

The project is intentionally built without paid infrastructure.

Current primary services:

- GitHub / GitHub Actions
- Neon PostgreSQL free tier
- Telegram
- existing free market-data sources
- Resend where already configured

Future LLM work is expected to use free-tier infrastructure such as Groq where practical.

## Engineering Rules

1. Inspect the repository before changing code.
2. Preserve existing fallbacks and failure isolation.
3. Make the smallest change that satisfies the requirement.
4. Do not mix future-sprint features into the current sprint.
5. Every sprint requires automated tests and an executable KPI.
6. Unknown data must remain `UNKNOWN`; never fabricate values.
7. Do not treat LLM output as quantitative truth.
8. Do not declare completion without verification.

Reusable AI-developer behavior is stored under `skills/`. Start with `core-engineering.md` and `repository-onboarding.md`, then load only the skills relevant to the task.

## Validation

Before a sprint is considered complete, the developer should verify at minimum:

```bash
python -m compileall src
```

followed by the repository test suite and the relevant sprint KPI.

The repository also contains CI smoke-test/import validation.

## Development Status

### Stable foundation

- market-data collectors and validation
- fallback strategies
- Telegram and email notifications
- scheduled and on-demand execution
- GitHub Actions state persistence
- Neon historical storage
- deterministic SP-A market-state pipeline
- SP-A conflict matrix and hysteresis
- reusable AI-developer skill files

### Pre-SP-B stabilization

The current task is to finish and verify the last SP-A presentation/documentation refinements, then freeze SP-A.

### Next

SP-B: external market intelligence.

### Later

SP-C: prediction, confidence, hypothesis evaluation, learning and decision intelligence.

## License

MIT
