# Gold Premium Monitor — Project Memory

This file is the **canonical project-specific architecture and current-state memory** for maintainers and AI implementation agents.

## Documentation authority

| Source | Responsibility |
|---|---|
| `PROJECT_MEMORY.md` | Canonical architecture, invariants, implementation state, contracts, roadmap |
| `README.md` | Human-facing overview |
| `Prompt_Guide.md` | Generic AI engineering behavior |
| `skills/` | Specialist reusable operating rules |
| `sql/neon_schema.sql` | Canonical target database schema |
| `sql/neon_migration_*.sql` | Migrations for an existing Neon database |
| `src/`, `tests/`, `kpi/`, CI | Executable evidence |

When documentation conflicts, prefer the higher-authority source and then executable behavior as implementation evidence. Project-state changes are recorded here first.

## 1. Project purpose

Gold Premium Monitor is a decision-support monitor for the Iranian 18K physical-gold market. It combines XAU/USD, USD/IRR, Iranian platform prices, fair value, premium/discount analysis, momentum, market structure, historical memory, structured news, canonical observations, scheduled analysis, deterministic technical structure, deterministic market regime, analysis snapshots, retrospective outcome evaluation, and normalized evidence packaging.

It is not an autonomous trading bot.

## 2. Non-negotiable architecture

```text
CHEAP ≠ BUY
VALUATION ≠ MOMENTUM
CANDIDATE DECISION ≠ FINAL DECISION
NEWS ≠ MARKET DATA
LLM ≠ MARKET CALCULATION
EVIDENCE PACKAGE ≠ DECISION
```

Layers remain separate:

```text
Quantitative Engine = measures facts
Intelligence Layer  = interprets context
Decision Engine     = evaluates evidence
```

Collectors collect. Calculators calculate. Intelligence interprets. Presentation formats. Persistence stores.

Unknown / insufficient data is preferable to fabricated information.

## 3. Development state

```text
main
└── SP-A COMPLETE / FROZEN

SP-B
├── SP-B.1 COMPLETE — Historical Intelligence
├── SP-B.2 COMPLETE — News Intelligence
├── PRE-SP-C.1 COMPLETE — Canonical Time Series
├── PRE-SP-C.2 COMPLETE — Analysis Snapshot + Scheduler Foundation
├── PRE-SP-C.3 COMPLETE — Price Structure + Regime
├── PRE-SP-C.4 COMPLETE — Analysis Snapshot Integration
├── PRE-SP-C.5 COMPLETE — Outcome Evaluation Foundation
└── PRE-SP-C.6 COMPLETE — Evidence Package + Market Intelligence Foundation

NEXT
└── Market Intelligence interpretation / bounded LLM layer

SP-C
└── FUTURE — Prediction + Learning
```

`SP-B` is the active development line and must not be merged into `main` until approved scope, regression, KPI, documentation, and diff review are complete.

## 4. Frozen SP-A baseline

```text
Valuation
→ Premium Direction
→ Momentum
→ Market Structure
→ Conflict Matrix
→ Candidate Decision
→ SP-A Hysteresis
→ Final Decision
```

For negative premium:

```text
more negative → DISCOUNT WIDENING
less negative → DISCOUNT NARROWING
stable        → DISCOUNT STABLE
```

Buyer-oriented momentum:

```text
DISCOUNT WIDENING → IMPROVING
DISCOUNT NARROWING → WEAKENING
DISCOUNT STABLE → NEUTRAL
```

Do not replace the explicit conflict matrix with an opaque weighted score without approval.

## 5. Alert authority

`final_decision` is the sole external BUY/SELL authority.

```text
Candidate: BUY
Final: WAIT
    ↓
NO BUY ALERT
```

Legacy threshold evaluation may remain for backward-compatible tests but must not independently trigger external alerts. Telegram and email must preserve this invariant.

## 6. Live Wing

Purpose: what is happening now?

```text
/Update
→ collect
→ validate
→ calculate
→ deterministic market state
→ Telegram
```

It is user-triggered, irregular, current, lightweight, and not the Analysis Wing's technical history.

## 7. Analysis Wing

Purpose: what does the system currently understand about the market?

Scheduler contract:

| Setting | Value |
|---|---|
| Timezone | `Asia/Tehran` |
| Interval | 30 minutes |
| Window | `08:00` inclusive → `21:00` exclusive |
| Active days | configurable |

`get_next_analysis_windows()` treats the reference boundary as already consumed; exact `09:00` therefore yields `09:30` as the next window.

Conceptual flow:

```text
scheduled window
→ source availability / freshness
→ canonical observations
→ technical structure
→ regime
→ historical/news context
→ Analysis Snapshot
→ Outcome Evaluation
→ Evidence Package
→ Neon
```

The future intelligence layer consumes the normalized evidence package; it does not replace the deterministic analytical pipeline.

User count must not multiply scheduled analysis execution.

## 8. PRE-SP-C.1 — canonical observations

`price_observations` is the canonical technical time-series layer.

Conceptual instruments:

```text
XAUUSD
USD/IRR
REP_IRAN_GOLD
PAXG
```

Technical analysis consumes actual price observations, not premium as a proxy candle.

Raw observations remain separate from interpreted states.

## 9. PRE-SP-C.2 — snapshot foundation COMPLETE

Established:

- `analysis_snapshots`
- deterministic `source_run_id` idempotency
- LIVE vs ANALYSIS snapshot distinction
- scheduled analysis windows
- canonical Neon persistence
- final-decision alert authority
- alert-routing regression coverage

KPI: **14/14 passed**.

## 10. PRE-SP-C.3 — Price Structure + Regime COMPLETE

KPI: **20/20 passed**.

### Representative Iranian price

Fixed fallback:

```text
Milli → Ayyareh → WallGold → UNKNOWN
```

First valid source wins. Selected source is retained as provenance. This layer uses canonical observations and does not average all platforms.

### Support / resistance

```text
price observations
→ local extrema
→ clustering / tolerance
→ deterministic strength metadata
→ support / resistance
```

Insufficient history remains explicit. No fabricated levels.

### Regime

States:

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

Regime hysteresis is distinct from SP-A decision hysteresis.

`CHEAP + PANIC` is valid. Regime never issues BUY/SELL.

## 11. PRE-SP-C.4 — Analysis Snapshot Integration COMPLETE

C.4 integrates C.3 primitives into persisted `analysis_snapshots`.

Persisted C.4 state:

```text
regime_state
technical_state_json
previous_regime
regime_candidate_state
regime_confirmation_count
```

Cross-run regime hysteresis is reconstructed from persisted snapshot state. No separate regime table and no file cache are used.

KPI: **19/19 passed**.

C.4 includes the Invi collector integration without altering the approved representative fallback chain.

## 12. Invi collector contract

`src/collector/invi.py` is an additional Iranian market source.

Collector contract:

```python
{
    "platform": "Invi",
    "price": <canonical IRR/gram numeric value>,
    "status": "OK",
}
```

The source exposes `current_price` in a smaller unit. The collector normalizes it by `×1000` before validation. This is a unit normalization, not a market-model adjustment.

Invi is registered in the Iranian platform collector path but is **not** part of the representative-price fallback chain.

Collector failure must remain isolated.

## 13. Neon persistence

Neon PostgreSQL is the long-term historical store.

| Table | Responsibility |
|---|---|
| `market_snapshots` | Existing market observations |
| `platform_prices` | Platform evidence |
| `market_states` | Deterministic interpreted state |
| `news_events` | Structured external events |
| `price_observations` | Canonical raw technical time series |
| `analysis_snapshots` | Scheduled analytical history + normalized evidence package |
| `outcome_evaluations` | Retrospective +1h/+6h/+24h measurements |

Schema authority is split intentionally:

```text
sql/neon_schema.sql
    = idempotent canonical TARGET schema

sql/neon_migration_*.sql
    = idempotent migrations for EXISTING Neon database
```

Never use the complete target schema as a replacement migration against an already-populated Neon database.

C.4 `analysis_snapshots` fields include:

```text
regime_state
technical_state_json
previous_regime
regime_candidate_state
regime_confirmation_count
```

C.5 adds:

```text
outcome_evaluations
```

with one row per `(analysis_snapshot_id, horizon_hours)` for the initial horizons `1`, `6`, and `24` hours.

C.6 adds:

```text
evidence_package_json JSONB
```

with a GIN index for future evidence-component queries.

Required uniqueness:

```text
uq_analysis_snapshots_source_run_id
uq_outcome_eval_snapshot_horizon
```

Required snapshot-type constraint:

```text
snapshot_type IN ('analysis', 'live')
```

Database failure must degrade gracefully and must not become a hidden calculation layer.

## 14. Historical and news intelligence

SP-B.1 is descriptive historical context only.

SP-B.2 is structured external-news context only.

Neither independently calculates fair price, premium, technical indicators, or BUY/SELL.

## 15. LLM boundary

LLM may summarize and interpret structured context.

LLM must not:

- calculate fair price
- calculate premium
- calculate indicators
- invent technical levels
- invent historical statistics
- override deterministic state
- independently issue BUY/SELL

C.6 itself does not call an LLM. It creates the deterministic evidence contract consumed by the future intelligence layer.

## 16. Telegram product model

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

Known non-blocking presentation defect: duplicated `GOLDPremium:` application header in manual updates. This is a Telegram presentation cleanup, not an analytical correctness failure.

C.5/C.6 do not add outcome or evidence-package detail to `/Update`; the Live Wing remains separate from the Analysis/Evaluation Wing.

## 17. PRE-SP-C.5 — Outcome Evaluation COMPLETE

C.4 answers:

> What did the system know at time T?

C.5 answers:

> What happened after time T?

Implementation includes:

```text
analysis snapshot
    ↓
+1h / +6h / +24h target
    ↓
nearest valid future canonical observation within tolerance
    ↓
movement + direction + actual observation time
    ↓
outcome_evaluations
```

Rules:

- target is anchored to `analysis_timestamp`
- future observation must be strictly after the snapshot timestamp
- no interpolation
- missing target data becomes `INSUFFICIENT_DATA`
- one unavailable series does not invalidate other series
- evaluation is idempotent by snapshot + horizon
- historical backfill is supported
- Invi does not enter representative-price outcome fallback

KPI: **25/25 passed**.

C.5 is retrospective measurement infrastructure only. It does not predict and does not alter the current decision engine.

## 18. PRE-SP-C.6 — Evidence Package + Market Intelligence Foundation COMPLETE

C.6 creates a deterministic, auditable evidence package from already-computed and persisted analytical outputs.

Core flow:

```text
canonical facts
    ↓
validated analytical outputs
    ↓
normalized evidence package
    ↓
future intelligence interpretation
    ↓
decision engine
```

The evidence package is not a decision and must not create BUY/SELL behavior.

Evidence families include:

```text
valuation
momentum
technical_structure
regime
xau_usd
usd_irr
representative_gold
platform_structure
news_context
historical_context
outcome_context
data_quality
provenance
```

The package has an explicit schema version and deterministic validation. Missing/optional evidence remains explicit rather than fabricated. The package must not contain a decision field as a substitute for the Decision Engine.

C.6 persistence is via `analysis_snapshots.evidence_package_json`.

KPI: **25/25 passed**.

C.6 is an analytical foundation. It does not yet implement bounded LLM interpretation, multi-agent debate, or prediction.

## 19. Documentation rules

1. Update `PROJECT_MEMORY.md` for every architecture/state change.
2. Update `README.md` when the human-facing system map changes.
3. Update a specialist skill only when reusable operating behavior changes.
4. Do not duplicate sprint-specific facts into every skill.
5. Keep database schema and migration files synchronized with the intended Neon state.
6. Executable evidence outranks prose when verifying implementation.

## 20. Verification standard

Every change:

```text
inspect
→ define change surface
→ implement minimally
→ targeted test
→ regression
→ KPI
→ smoke test
→ diff review
→ documentation sync
→ branch review
```

Never claim COMPLETE without verified evidence.

Current verified evidence supplied:

```text
PRE-SP-C.2 KPI  14/14 PASS
PRE-SP-C.3 KPI  20/20 PASS
PRE-SP-C.4 KPI  19/19 PASS
PRE-SP-C.5 KPI  25/25 PASS
PRE-SP-C.6 KPI  25/25 PASS
compileall       PASS
live smoke        PASS
```

Latest C.6 smoke behavior includes:

- Invi collected and normalized into canonical IRR/gram scale
- invalid/failed collectors remain isolated
- XAU/USD and USD/IRR observations saved
- market snapshot/state saved
- Candidate/Final separation preserved
- no false external BUY/SELL alert when Final=WAIT

The full regression suite must still be run as the final pre-merge gate for SP-B.

## 21. SP-B closure direction

Original SP-B.3/B.4/B.5 names are architectural placeholders, not mandatory module boundaries.

Approved direction remains:

| Original | Current role |
|---|---|
| SP-B.3 | Analysis Wing / bounded LLM interpretation |
| SP-B.4 | Telegram analytical read models |
| SP-B.5 | Combined read model over persisted analysis snapshots/evidence |

C.6 evidence packaging is now complete and is the input contract for the future bounded intelligence layer.

Do not create duplicate agent/radar layers solely to preserve old sprint names.

## 22. SP-C gate

Before SP-C prediction/learning:

```text
canonical observations
→ analysis snapshots
→ technical layer
→ regime layer
→ historical/news context
→ outcome evaluation
→ evidence package
→ bounded intelligence/read models
→ prediction/learning
```

No prediction model should start before those foundations are explicit, testable, and empirically evaluable.
