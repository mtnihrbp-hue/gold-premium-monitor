# Gold Premium Monitor — Project Memory

## 1. Purpose

Gold Premium Monitor is a decision-support system for the Iranian 18K physical-gold market.

Its purpose is not merely to report prices. It is being built to answer:

> Given current Iranian gold pricing, USD/IRR, world gold, market structure, historical behavior and eventually external events, is buying, waiting or selling the rational action?

The project must remain explainable, testable, resilient and free-tier compatible.

---

## 2. Core Distinctions

These distinctions are architectural invariants:

```text
CHEAP ≠ BUY

VALUATION ≠ MOMENTUM

CANDIDATE DECISION ≠ FINAL DECISION

MARKET DATA ≠ NEWS INTERPRETATION

LLM INTERPRETATION ≠ QUANTITATIVE CALCULATION
```

The deterministic quantitative engine measures the market.

Future intelligence layers interpret context.

The decision engine combines evidence.

---

## 3. Current Architecture

```text
XAU/USD ────────┐
USD/IRR ────────┼──> Market Calculation
Platforms ──────┘          |
                            v
                       Fair Value
                            |
                       Premium/Discount
                            |
             +--------------+--------------+
             |              |              |
             v              v              v
        Valuation       Momentum       Structure
             |              |              |
             +--------------+--------------+
                            |
                         Conflict
                            |
                    Candidate Decision
                            |
                        Hysteresis
                            |
                      Final Decision
                            |
                    +-------+-------+
                    |               |
                 Telegram         Email
                            |
                           Neon
                     Historical Memory
```

SP-A is the deterministic baseline.

SP-B will enrich this baseline with external market intelligence.

SP-C will use historical state/outcome data for prediction and learning.

---

## 4. Data Inputs

### World Gold

Primary global gold data is collected through the existing Kitco-related collector and its fallback chain.

If live world-gold data is unavailable, the existing application may fall back to a recent cached value when the fallback rules permit it.

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

## 5. Fair Price and Premium

Theoretical fair price is derived from world gold and USD/IRR using the existing implementation.

The project currently calculates the application value using the existing `calculate_fair_price()` flow.

Premium/discount is defined as:

```text
(market_price - fair_price) / fair_price
```

Negative premium = market price below fair value = discount.

Positive premium = market price above fair value = premium.

Do not create a second fair-value calculation without explicit approval.

---

## 6. Data Quality

A market state is valid only when required inputs satisfy the existing validation rules.

The application already validates ranges and minimum market-source availability.

Missing data must become:

```text
UNKNOWN
```

when no valid fallback exists.

Never convert missing data into zero or invent a value.

Fallback behavior is a core project requirement.

---

## 7. Persistence

Neon PostgreSQL is the project's long-term historical memory.

GitHub Actions Cache continues to provide runtime state persistence for `state.json`.

These are different responsibilities:

```text
state.json / GitHub Cache
    = runtime continuity

Neon PostgreSQL
    = historical market memory and future analytics
```

Database failure is non-fatal.

The market monitor must continue operating using existing fallback/state behavior if Neon is unavailable.

---

## 8. SP-A — Deterministic Market State

SP-A establishes a normalized state pipeline:

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

### 8.1 Valuation

States:

```text
CHEAP
FAIR
EXPENSIVE
UNKNOWN
```

Existing premium thresholds remain the basis for valuation zones.

The thresholds may remain configurable.

### 8.2 Premium Direction

Canonical user-facing terminology:

```text
DISCOUNT WIDENING
DISCOUNT NARROWING
DISCOUNT STABLE

PREMIUM WIDENING
PREMIUM NARROWING
PREMIUM STABLE
```

For negative premium:

- becoming more negative = `DISCOUNT WIDENING`
- becoming less negative = `DISCOUNT NARROWING`

For positive premium:

- becoming more positive = `PREMIUM WIDENING`
- becoming less positive = `PREMIUM NARROWING`

### 8.3 Momentum

Buyer-oriented momentum states:

```text
IMPROVING
NEUTRAL
WEAKENING
UNKNOWN
```

Current interpretation:

```text
DISCOUNT WIDENING → IMPROVING
DISCOUNT NARROWING → WEAKENING
DISCOUNT STABLE → NEUTRAL
```

and the corresponding positive-premium cases use the same buyer-oriented interpretation.

"Improving" means the market opportunity is improving for the buyer; it does not mean the underlying gold price is necessarily rising.

### 8.4 Market Structure

Structure is derived from valid platform observations.

Current states:

```text
DISCOUNT_DOMINANT
PREMIUM_DOMINANT
MIXED
UNKNOWN
```

The system also tracks:

- active platform count
- platform average
- highest platform
- lowest platform
- spread
- number below fair
- number above fair

Platform average is retained as analytical data but is not an independent SP-A decision criterion.

### 8.5 Conflict Matrix

The SP-A decision matrix is deterministic and hardcoded.

Important examples:

```text
CHEAP + IMPROVING + DISCOUNT_DOMINANT
    → SUPPORTIVE
    → BUY

CHEAP + WEAKENING + DISCOUNT_DOMINANT
    → CAUTION
    → WAIT
```

Do not replace the matrix with an opaque score without explicit approval.

### 8.6 Candidate vs Final

SP-A intentionally exposes two decision stages:

```text
Candidate Decision
        ↓
Hysteresis
        ↓
Final Decision
```

It is valid for:

```text
Candidate: BUY
Final: WAIT
```

The meaning is that current market-state conditions support a BUY candidate, but the hysteresis/state-transition rules have not authorized a new BUY transition.

Do not collapse these states.

---

## 9. Telegram Product Model

Telegram is the primary user-facing cockpit.

The current operational command is `Update` for an on-demand snapshot.

The architecture should support future commands such as:

```text
Update
Analysis
Sentiment
History
Risk
Health/KPI
```

These future commands should provide deeper views rather than continually enlarging the primary message.

### Current message hierarchy

```text
Market
Decision / Market State
Trends
Momentum
Market Structure
Platforms
Timestamp
```

Input directions for world gold and USD are part of the **Market** context, not a separate intelligence section.

The platform table remains at the bottom because it is raw evidence/inspection data.

Avoid unexplained scores and decorative visualizations.

ASCII visualizations are deferred until their semantics are clearly defined and useful.

---

## 10. Telegram Terminology Rule

The Telegram layer must use the same canonical premium/discount vocabulary as the analytical engine.

Presentation code must not independently reinterpret market states.

The formatter should consume already-derived analytical state whenever possible.

This prevents the analytical engine and user interface from describing the same market condition differently.

---

## 11. News and LLM Boundary

SP-B will introduce external market intelligence.

The intended separation is:

```text
Deterministic engine
    = measures the market

LLM/news layer
    = interprets external information

Decision layer
    = combines evidence
```

The LLM must never invent:

- fair price
- premium
- USD/IRR
- XAU/USD
- support/resistance
- historical outcomes

The LLM may produce structured market events such as:

- event type
- topic
- expected USD direction
- expected Iranian-gold direction
- expected duration
- impact
- confidence
- uncertainty

LLM failure must degrade to `UNKNOWN` and never crash the market monitor.

The project remains free-tier constrained.

---

## 12. Historical Intelligence Direction

Neon should eventually allow queries such as:

```text
What happened after similar premium states?

What happened when USD was falling and gold was rising?

What happened during previous PANIC/RELIEF regimes?

How often did news expectations match subsequent price behavior?
```

Historical similarity must remain transparent and sample-size aware.

Insufficient historical data must be reported as insufficient data, not turned into artificial confidence.

---

## 13. Prediction and Learning Direction

Prediction comes after sufficient state history exists.

Future predictions should be tracked as hypotheses with:

- timestamp
- state at prediction time
- predicted direction/movement
- horizon
- confidence
- evidence/reason
- actual outcome
- prediction error

The system should learn from its own mistakes without obscuring whether an error originated in data, interpretation, regime detection or decision logic.

---

## 14. Engineering Invariants

1. Collectors collect; they do not decide.
2. Calculators calculate; they do not fetch external data.
3. Notification formatters format; they do not reimplement analytical logic.
4. Persistence stores; it does not become a hidden calculation layer.
5. Telegram is the cockpit, not the brain.
6. LLM output is contextual intelligence, not quantitative truth.
7. External failures are non-fatal whenever safely possible.
8. Unknown is preferable to fabricated data.
9. Every sprint has automated tests and an executable KPI.
10. Future-sprint functionality must not leak into the current sprint.
11. Small, surgical changes are preferred over broad refactors.

---

## 15. Branch and Sprint Model

Stable code lives on `main`.

Sprint branches are temporary development lines.

Current process:

```text
main
  ↓
SP-A
  ↓
SP-A-Edited / refinement
  ↓
verification
  ↓
merge to main
  ↓
SP-A branches can be deleted
  ↓
create next sprint branch
```

Never force-push unless explicitly required.

Never declare a sprint complete without the required tests and KPI.

---

## 16. Skills for AI Developers

Reusable AI behavior is stored under `skills/`.

The load order is:

1. `core-engineering.md`
2. `repository-onboarding.md`
3. `sprint-execution.md`
4. task-specific specialist skills
5. current sprint prompt/user requirement

The project memory describes the architecture.

The skills describe reusable AI behavior.

The current sprint prompt defines the exact task.

---

## 17. Current State Before SP-B

SP-A must be frozen before SP-B begins.

The immediate stabilization sequence is:

```text
SP-A-Edited
    ↓
Telegram/presentation verification
    ↓
README + PROJECT_MEMORY verification
    ↓
compile/import tests
    ↓
full test suite
    ↓
SP-A KPI
    ↓
merge to main
    ↓
delete temporary SP-A branches
    ↓
start SP-B
```

Do not begin SP-B until this sequence is complete.
