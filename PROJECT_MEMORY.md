# Gold Premium Monitor — Project Memory

## 1. Purpose

Gold Premium Monitor is a decision-support system for the Iranian 18K physical-gold market.

Its purpose is not merely to report prices. It is being built to answer:

> Given current Iranian gold pricing, USD/IRR, world gold, market structure, historical behavior and eventually external events, is buying, waiting or selling the rational action?

The project must remain explainable, testable, resilient and free-tier compatible.

---

## 2. Core Distinctions

These are architectural invariants:

```text
CHEAP ≠ BUY

VALUATION ≠ MOMENTUM

CANDIDATE DECISION ≠ FINAL DECISION

MARKET DATA ≠ NEWS INTERPRETATION

LLM INTERPRETATION ≠ QUANTITATIVE CALCULATION
```

The deterministic quantitative engine measures the market.

External intelligence interprets context.

The decision engine combines evidence.

---

## 3. Current Status

```text
SP-A              COMPLETE / FROZEN
SP-B.1            COMPLETE
SP-B.2            COMPLETE
SP-B.3–B.5        NOT IMPLEMENTED
PRE-SP-C DETOUR   NEXT
SP-C              FUTURE
```

SP-A is already part of the completed `main` baseline and should be treated as frozen. Future work enriches the baseline rather than redesigning it.

The active development branch is currently `SP-B`.

SP-B must not be merged into `main` until the pre-SP-C architecture detour is completed, validated, and the remaining SP-B scope is explicitly reviewed.

---

## 4. Current Architecture

```text
XAU/USD ────────┐
USD/IRR ────────┼──> Quantitative Market Engine
Platforms ──────┘               |
                                v
                           Fair Value
                                |
                         Premium/Discount
                                |
                  +-------------+-------------+
                  |             |             |
                  v             v             v
             Valuation      Momentum      Structure
                  |             |             |
                  +-------------+-------------+
                                |
                             Conflict
                                |
                        Candidate Decision
                                |
                            Hysteresis
                                |
                          Final Decision
                                |
                         Historical Memory
                                |
                   +------------+-------------+
                   |                          |
                Live Wing                Analysis Wing
                   |                          |
                /Update                 scheduled system run
                   |                          |
                   +------------+-------------+
                                |
                               Neon
```

The next architecture stage adds an explicit intelligence/analysis wing around the frozen deterministic baseline.

---

## 5. Data Inputs

### World Gold

Primary global gold data is collected through the existing Kitco-related collector and its fallback chain.

If live world-gold data is unavailable, the existing application may fall back to a recent cached value when fallback rules permit it.

### USD/IRR

USD sell rate is collected through the existing Bonbast implementation.

### Iranian Market Platforms

Existing collectors include API and HTML-based sources such as:

- Milli
- Goldika
- WallGold
- Taline
- HoorGold
- Parasteh
- Miogold
- Ayyareh
- Eligallery
- Daric

Collector failures must remain isolated and must not crash the whole monitor.

---

## 6. Fair Price and Premium

Theoretical fair price is derived from world gold and USD/IRR using the existing implementation.

Premium/discount is:

```text
(market_price - fair_price) / fair_price
```

Negative premium = discount.

Positive premium = premium.

Do not introduce a second fair-price calculation without explicit approval.

---

## 7. Data Quality and Fallbacks

A market state is valid only when required inputs satisfy existing validation rules.

Missing data must become:

```text
UNKNOWN
```

when no valid fallback exists.

Never convert missing data into zero or fabricate a value.

Collector failures, RSS failures, LLM failures and Neon failures must be isolated whenever safely possible.

Fallback behavior is a core project requirement.

---

## 8. Persistence

Neon PostgreSQL is the project's long-term historical memory.

Runtime state and historical memory are different responsibilities:

```text
state.json / GitHub Cache
    = runtime continuity

Neon PostgreSQL
    = historical market memory and future analytics
```

Current persisted concepts include:

- `market_snapshots`
- `platform_prices`
- `market_states`
- `news_events`

Future analysis-snapshot and hypothesis/outcome structures must remain separate from raw market observations.

---

## 9. Deterministic Market State Baseline

The frozen market-state pipeline is:

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

For a negative premium:

- more negative = `DISCOUNT WIDENING`
- less negative = `DISCOUNT NARROWING`

For a positive premium:

- more positive = `PREMIUM WIDENING`
- less positive = `PREMIUM NARROWING`

Momentum remains buyer-oriented:

```text
DISCOUNT WIDENING → IMPROVING
DISCOUNT NARROWING → WEAKENING
DISCOUNT STABLE → NEUTRAL
```

"Improving" means the opportunity is improving for a buyer. It does not mean gold price itself is necessarily rising.

The conflict matrix is deterministic. Do not replace it with an opaque weighted score without explicit approval.

---

## 10. Historical Intelligence — SP-B.1 COMPLETE

SP-B.1 provides deterministic historical state comparison.

Matching uses:

### Hard requirements

- valuation
- momentum
- premium distance within configured tolerance

### Soft/context matches

- market structure
- USD/IRR direction when known
- XAU/USD direction when known

If a secondary field is unknown on either side, it must not fabricate a value and must not block the comparison solely because it is unavailable.

SP-B.1 does not predict or forecast.

It is historical context only.

---

## 11. News Intelligence — SP-B.2 COMPLETE

SP-B.2 provides a structured external-news pipeline:

```text
RSS / manual input
        ↓
Normalization
        ↓
Deduplication
        ↓
Deterministic relevance/classification
        ↓
Structured news event
        ↓
Neon
```

The deterministic classifier uses a controlled event vocabulary and conservative `UNKNOWN` / `UNCERTAIN` outcomes.

Current news configuration is free-source and configurable.

SP-B.2 does not:

- issue BUY/SELL decisions
- predict prices
- run LLM narratives

---

## 12. Remaining SP-B Scope

The original SP-B roadmap contains:

### SP-B.3 — LLM Interpretation

Not implemented.

Planned role:

- interpret structured news
- combine news with SP-A state and historical context
- create bounded narrative
- degrade gracefully when Groq is unavailable

### SP-B.4 — Telegram Intelligence Commands

Not implemented.

Planned commands include:

```text
/Analysis
/History
/News
/Radar
```

`/Update` remains the live snapshot.

### SP-B.5 — Market Intelligence Radar

Not implemented.

Planned role:

```text
SP-A state
+
historical context
+
news context
+
regime / market mood
        ↓
Radar
```

Prediction and learning remain outside SP-B.

---

## 13. Pre-SP-C Architecture Detour

Before SP-C prediction/learning begins, the project must define the architecture between the live market monitor and the future learning system.

The detour will establish:

- live user-triggered snapshots versus system-generated analysis snapshots
- scheduled analysis cadence, initially expected around 30–60 minutes
- technical-analysis data model
- representative Iranian market-price candle source and fallback chain
- support/resistance architecture
- XAU/USD technical context
- USD/IRR technical context
- future PAXG reference-input role
- analysis read models for Telegram
- historical outcome/evaluation contract
- separation of user-triggered data collection from reusable system analysis

This is architecture/design work first.

No prediction model should be implemented until these contracts are explicit and testable.

---

## 14. Live Wing vs Analysis Wing

### Live Wing

Primary command:

```text
/Update
```

Meaning:

> What is happening in the market right now?

The live path should remain relatively lightweight and current.

Conceptually:

```text
collect
→ validate
→ calculate
→ frozen market state
→ display
```

### Analysis Wing

System-triggered on a scheduled cadence.

Initial target:

```text
30–60 minutes
```

Meaning:

> What does the system currently understand about the market?

Eventually:

```text
current market
+
SP-A state
+
technical analysis
+
historical context
+
news intelligence
+
regime / market mood
+
LLM narrative
        ↓
analysis snapshot
        ↓
Neon
```

The analysis snapshot is system-generated and reusable by multiple Telegram users.

Prediction/learning should use analysis snapshots, not arbitrary user-request snapshots.

---

## 15. Technical Analysis Direction

Technical analysis will be an independent analytical layer.

Planned Telegram command:

```text
/Technical
```

Potential inputs:

- XAU/USD
- USD/IRR
- representative Iranian gold price
- trend
- moving averages
- RSI
- ATR / volatility
- support/resistance
- price structure
- representative-market candle

The candle must represent a market-price series, not the premium series.

Initial representative-platform fallback concept:

```text
Milli
  ↓
Ayyareh
  ↓
WallGold
```

A robust future reference-price method may be evaluated later, but the first implementation must remain deterministic and explainable.

---

## 16. PAXG Role

PAXG is an external gold-market reference input, not a replacement for the Iranian fair-price calculation.

Its eventual role belongs in the global-gold context layer of the Analysis Wing.

The Iranian market model must remain anchored in its own local USD/IRR and platform data.

---

## 17. Telegram Product Model

Telegram is the presentation/cockpit layer.

Current command:

```text
/Update
```

Future commands may include:

```text
/Technical
/Analysis
/History
/News
/Radar
/Health
```

The main update message should not become the dumping ground for every analytical feature.

Detailed platform evidence remains near the bottom.

Presentation code should consume analytical state rather than recompute it.

---

## 18. Analysis Snapshot Contract — Future

The exact schema is to be designed during the pre-SP-C detour.

The conceptual distinction is:

```text
LIVE_SNAPSHOT
    = user-triggered current observation

ANALYSIS_SNAPSHOT
    = system-triggered analytical observation
```

The two must remain distinguishable in persistent storage.

A future analysis snapshot is expected to reference:

- market observation
- market state
- technical state
- historical context
- news context
- regime/mood
- analytical narrative
- data-quality status

Do not implement this schema before the detour is approved.

---

## 19. Prediction and Learning — SP-C Future

SP-C will eventually evaluate hypotheses and observed outcomes.

Future prediction records must preserve:

- prediction timestamp
- source analysis snapshot
- prediction horizon
- predicted movement/state
- confidence based on evidence
- evidence/reason
- actual outcome
- error
- model/version information

The system should learn from observed outcomes without hiding whether an error originated in:

- data
- technical analysis
- news interpretation
- regime detection
- decision logic
- model assumptions

SP-C must not begin until the pre-SP-C detour defines the outcome/evaluation contract.

---

## 20. Engineering Invariants

1. Collectors collect; they do not decide.
2. Calculators calculate; they do not fetch external news.
3. Intelligence interprets context; it does not invent quantitative truth.
4. Notification formatters format; they do not reimplement analytical logic.
5. Persistence stores; it does not become a hidden calculation layer.
6. Telegram is the cockpit, not the brain.
7. Unknown is preferable to fabricated data.
8. External failures are non-fatal whenever safely possible.
9. Every sprint/sub-sprint requires automated tests and an executable KPI.
10. Future-sprint functionality must not leak into the current task.
11. Small, surgical changes are preferred over broad refactors.
12. Do not declare completion without executable verification.

---

## 21. Skills for AI Developers

Reusable AI behavior is under `skills/`.

Load order:

1. `core-engineering.md`
2. `repository-onboarding.md`
3. `sprint-execution.md`
4. task-specific specialist skills
5. current sprint prompt/user requirement

`PROJECT_MEMORY.md` describes project-specific architecture.

Skills describe reusable AI behavior.

The current task/prompt defines the exact implementation scope.

---

## 22. Branch and Sprint Model

Stable code lives on `main`.

Sprint development happens on dedicated branches.

Current active development branch:

```text
SP-B
```

Do not merge SP-B into `main` yet.

The pre-SP-C architecture detour will be designed and validated on the active development line first.

After that detour is complete, review the remaining SP-B.3–B.5 scope and explicitly decide whether to:

- complete it before merging, or
- redefine/close it based on the approved architecture.

Never force-push unless explicitly required.

Never delete stable tags.

---

## 23. Current Next Step

The next task is:

```text
PRE-SP-C ARCHITECTURE DETOUR
```

The detour must produce:

1. Analysis Wing architecture
2. Live vs Analysis separation
3. analysis-snapshot contract
4. technical-analysis contract
5. representative-price/candle contract
6. support/resistance design boundary
7. PAXG integration boundary
8. Telegram analytical read-model design
9. historical outcome/evaluation contract
10. WBS with independent KPIs

No prediction model should be implemented during this detour.
