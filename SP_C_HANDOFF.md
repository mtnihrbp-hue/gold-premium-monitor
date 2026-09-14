# SP-C — Relative Valuation and Self-Scoring

Branch: `SP-C`

Status: **IN PROGRESS**

This is the implementation contract for SP-C. It follows the pattern of
`C14_HANDOFF.md` and does not compete with `PROJECT_MEMORY.md` for architecture
authority.

---

## 1. Objective

Replace fixed valuation thresholds with a reference that moves with the market,
then make the system score its own decisions against what actually happened.

```text
fixed threshold        →   relative position
no track record        →   scored decisions with baselines
```

---

## 2. Why — the fixed threshold carried no information

Verified against production on 2026-09-13.

```text
buy_premium_percent            -1.5
bubble range, 278 readings     -8.19  ..  -1.82
readings below the threshold   278 of 278
```

The threshold sits outside the entire distribution. It is always triggered.

Consequences observed in production:

```text
valuation_state    CHEAP  on 204 of 204 recorded states
final_decision     WAIT   on 204 of 204 recorded states
candidate_decision BUY on 81, WAIT on 124
```

The layers beneath discriminate correctly. `IMPROVING` momentum (81) maps to
`SUPPORTIVE` conflict (81) maps to `BUY` candidate (81). Hysteresis then
suppresses every one of them.

A market that sits permanently outside a constant needs a reference that moves.

---

## 3. Where the decision trigger actually is

Forward 24h outcome by percentile band, computed from the same 278 readings.

```text
percentile   bubble range       n   avg 24h move   discount shrank
   0-10     -8.19 .. -5.17     21      +0.84pp          71%
  10-20     -5.15 .. -4.74     17      +0.35pp          76%
  20-30     -4.74 .. -4.39     21      +0.22pp          57%
  30-40     -4.37 .. -4.13     20      +0.04pp          65%
  ----------------------------- sign flips -----------------------
  40-50     -4.13 .. -3.97     14      -0.13pp          36%
  50-60     -3.96 .. -3.78     17      -0.34pp          29%
  60-70     -3.78 .. -3.60     21      -0.05pp          62%
  70-80     -3.60 .. -3.38     19      -0.24pp          37%
  80-90     -3.38 .. -2.96     16      -0.93pp          13%
 90-100     -2.94 .. -1.82     15      -1.25pp           0%
```

The crossing sits near the 40th percentile in this sample.

**This number must never be hardcoded.** It is where the sign flips in 41 days of
data. With more history it will move. The implementation recomputes its reference
every run for exactly this reason.

Caveats on the table: 14 to 21 cases per band, overlapping forward windows, one
regime, in-sample. The monotonic gradient from +0.84pp to -1.25pp across all ten
bands is the credible part, not any single row.

---

## 4. Method and its source

The problem is a security trading at a persistent discount to fair value where the
discount mean-reverts. That is closed-end fund discount behaviour, and the standard
instrument there is a z-score against a rolling mean and standard deviation.

```text
z = (bubble now  −  rolling average)  ÷  rolling standard deviation
```

Conventional levels are ±2 standard deviations. These are taken as published and
are **not** tuned to this project's data, which would be overfitting on 41 days.

Research also establishes two constraints applied here:

- Signals of this class use 120 to 180 days. Below that, confidence is reported LOW.
- Local premium under capital controls is structural, driven by import friction,
  supply and currency expectations. The mean therefore drifts, so the reference
  itself must be monitored, not only the distance from it.

Sources are recorded in `RESEARCH_ADOPTION.md`.

---

## 5. Implemented — `src/analysis/bubble_position.py`

KPI: `kpi/kpi_sp_c1.py` — **27/27 PASS**

```text
resolve_bubble_position(session, current_bubble=None, window_days=30, now=None)
    → BubblePosition
```

Zones, from the z-score. A deeper discount is the cheap side, so negative z is cheap.

```text
z <= -2.0    VERY_CHEAP
z <= -1.0    CHEAP
-1.0 .. 1.0  NORMAL
z >=  1.0    EXPENSIVE
z >=  2.0    VERY_EXPENSIVE
```

Confidence, from actual calendar coverage.

```text
< 30 readings        INSUFFICIENT_DATA
< 60 days            LOW
< 120 days           MEDIUM
otherwise            HIGH
```

Drift compares the window's two halves against its own spread.

```text
STABLE
TOWARD_LESS_DISCOUNT
TOWARD_MORE_DISCOUNT
UNKNOWN
```

```text
resolve_similar_outcomes(session, current_bubble, spread, horizon_hours=24, ...)
    → SimilarOutcomes
```

Reports what the bubble did after comparable past readings. Direction is expressed
as `became_cheaper` and `became_pricier`, not as a signed number, because the
decision-relevant question is whether waiting or buying was better. The phrase
"the discount closed" does not convey that to a reader.

Comparable band is ±0.5 × spread, so it adapts to volatility.

Production reading at implementation time:

```text
bubble        -3.81        average  -4.09     spread 1.09
normal range  -5.18 .. -3.00
z-score       +0.26        zone NORMAL        drift STABLE
confidence    LOW          204 readings, 30 days

+24h   123 cases   67 became cheaper / 53 became pricier   avg -0.20pp
 +6h    76 cases   45 became cheaper / 30 became pricier   avg -0.17pp
```

---

## 6. Implemented — `src/analysis/decision_scorecard.py`

KPI: `kpi/kpi_sp_c2.py` — **19/19 PASS**

```text
score_decisions(session, horizon_hours=24, tolerance_hours=2.0)
    → DecisionScorecard
```

### Scoring rule

The intuitive rule is wrong and would manufacture confidence.

```text
fair price rose      107 of 183 resolvable cases    58%
bubble rose           86 of the same 183            47%
```

The local price rises on its own. Scoring "said BUY, price went up" would credit a
system that always says BUY with 58% while it knows nothing. The bubble has no
built-in direction, so the bubble is scored.

Each decision is a choice between acting now and waiting.

```text
BUY    correct when the discount shrank afterwards
WAIT   correct when the discount grew afterwards
SELL   correct when the discount grew afterwards
```

Moves inside the 0.05pp dead-band are `INCONCLUSIVE`, not forced into a verdict.

### Baselines are mandatory

A hit rate alone is not interpretable. `always-BUY` and `always-WAIT` are scored on
the identical resolved sample, and edge is reported against the stronger.

Production result at implementation time:

```text
+24h    scored 175     hit rate 55.2%
        always-WAIT    55.2%
        edge            0.0
```

Correct behaviour. A system whose `final_decision` is WAIT on every recorded state
has a hit rate identical to the always-WAIT baseline by construction, and the
scorecard reports no skill rather than flattering it.

### Persistence

No new table. `market_states` already records each decision with its inputs, so the
scorecard joins it to later `market_snapshots`. Immutable forecast-event persistence
remains deferred as recorded in `C14C_HANDOFF.md`.

---

## 7. Boundaries

```text
bubble_position     reports position. Emits no BUY/WAIT/SELL.
decision_scorecard  measures. Tunes nothing.
```

Both are asserted by KPI. A scorecard that retuned thresholds would overfit its own
history and then report confidence in itself, which the C14C adaptive boundary
forbids.

Neither module is wired into any message yet.

---

## 8. Sequencing constraint

Nothing is scorable while every decision is the same.

```text
relative valuation  →  decisions vary  →  scorecard has something to score
```

The scorecard is built first so that evidence accumulates from the moment
decisions begin to differ.

---

## 9. Findings that changed the plan

**Regime is dead as calibrated.** `regime_state` is PANIC on 61 of 61 snapshots.
The `premium_magnitude` stress threshold is 2.0 and the bubble is always above it,
so stress fires permanently. Same failure mode as `buy_premium_percent`. Dropped
from the message design. Recalibration is SP-C work, not a message concern.

**News is not usable yet.** The schema is rich but the keyword classifier barely
matches.

```text
expected_gold_direction   UNKNOWN 322,  RISING 8
topic                     NULL on all 330
impact                    UNKNOWN 204,  MEDIUM 3,  HIGH 3
```

A news line in the message would say nothing today. The classifier needs work before
news earns space.

**Two RSS sources are permanently broken** from GitHub runners. `tasnimnews.com`
fails DNS resolution; `goldbroker.com` and `cbi.ir` reset the connection. Four of
seven feeds are actually working.

---

## 10. Applied migration — SP-C.1

`sql/neon_migration_sp_c1.sql`, applied to production on 2026-09-14 with explicit
authorisation. Additive only.

```text
market_snapshots.collection_mode      VARCHAR(20) NOT NULL DEFAULT 'unknown'
price_observations.collection_mode    VARCHAR(20) NOT NULL DEFAULT 'unknown'
market_states.valuation_context_json  JSONB

idx_market_snapshots_mode_time
idx_price_observations_mode_time
idx_market_states_valuation_context   GIN
```

Verified either side of the change:

```text
                        before    after
market_snapshots          291      291
price_observations       1685     1685
market_states             217      217
analysis_snapshots         62       62
platform_candles         1205     1205
news_events              1578     1578
outcome_evaluations       180      180
```

No row count changed. Existing rows report `collection_mode = 'unknown'`, and
`valuation_context_json` was null on all 217 existing states, as intended.

### Why these two additions could not be avoided

Neither fact is derivable from stored data.

**Collection provenance.** Nothing recorded whether a reading came from a scheduled
run or a user-triggered update, and it cannot be reconstructed. Every statistic in
this phase is therefore computed over a sample biased toward the moments a user
happened to look. `skills/data-and-neon.md` requires that irregular user-triggered
calls not become the canonical technical time series; without this column the two
were indistinguishable. Historical rows stay `unknown` rather than being guessed at,
so the bias is visible instead of hidden.

**Decision context.** `market_states` recorded the decision and the older state
labels but not the relative valuation that drives decisions from SP-C onward. The
scorecard could therefore say a decision was right but never why the system believed
it. A single JSONB column carries the context so it can evolve without a migration
per field.

### Code wired in the same change

```text
models.py            three columns added
repository.py        save_market_snapshot, save_price_observation take collection_mode
                     save_market_state takes valuation_context
main.py              mode resolved from SCHEDULED_RUN: scheduled | user
                     _build_valuation_context captures position at decision time
neon_schema.sql      canonical target schema updated to match
```

`_build_valuation_context` is non-blocking and returns None on any failure, because
a missing context must never stop a decision being persisted.

Data written from this point is clean. Everything before it remains mixed and is
marked as such.

## 11. Operational state — collection cadence

cron-job.org job 8179679 was reconfigured on 2026-09-14.

```text
schedule     every 1 hour        (was: once daily at 20:00)
body         {"ref":"SP-C","inputs":{"mode":"analyze"}}
headers      Content-Type: application/json
             X-GitHub-Api-Version: 2022-11-28
responses    saved to job history
```

The `inputs` object is what makes `SCHEDULED_RUN` resolve true. Without it the
dispatch produces an UPDATE and no analytical history, which is the defect this
phase corrected.

Hourly is sufficient for every outcome horizon. C.5 allows ±15 minutes around a
target, and hourly runs put the +1h, +6h and +24h targets exactly on later runs.
Thirty minutes would double the sample count but is not required for the horizons
to resolve.

### Merge checklist

Carry these out when SP-C merges into main:

```text
1. tag main as v1.3safe before merging
2. merge SP-C into main after user review
3. change the cron-job.org body ref from "SP-C" to "main"
4. remove the legacy GitHub native schedule from gold-monitor.yml
   once the external trigger is confirmed running on main
5. update the Cloudflare worker to accept /Analyze and pass
   inputs mode=analyze, which only works once main carries the input
```

Step 3 matters: the body pins `ref` to `SP-C`, so after a merge the scheduler would
keep running the feature branch rather than main.

## 12. Deferred

```text
half-life measurement to select the window   needs ~120 days
tightening the comparable band               needs more history
regime recalibration
news classifier repair
immutable forecast-event persistence
collection_mode migration                    requires approval
```

---

## 11. Known limitation

`market_snapshots` does not distinguish scheduled runs from user-triggered updates.
Both the distribution and the scorecard therefore draw on a mixed sample, biased
toward moments when a user happened to look. This resolves with the `collection_mode`
migration, which is a schema change and needs explicit approval.
