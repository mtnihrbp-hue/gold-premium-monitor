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

KPI: `kpi/kpi_sp_c1.py` — **55/55 PASS**

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

`bubble_position` is wired into the UPDATE message as of 2026-09-14, and its output
is persisted with every decision in `market_states.valuation_context_json`.
`decision_scorecard` remains unwired: it is admin-facing and has nothing meaningful
to report while every recorded decision is the same, so it waits until decisions
begin to vary.

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

## 11. UPDATE message — wired 2026-09-14

The relative valuation now reaches the reader. `src/analysis/bubble_position.py`
gained three further primitives for it, all covered by `kpi_sp_c1.py` (**55/55**).

```text
resolve_bubble_trend      moving averages of the bubble, not of the price
resolve_bubble_speed      rate expressed against its own typical daily move
resolve_zone_episodes     how often the cheap zone occurs and how long it lasts
```

`resolve_bubble_trend` takes averages on the bubble deliberately. A moving average of
the local price mostly tracks currency devaluation, so it reports an uptrend almost
permanently and carries no information. A short average above the long one means the
discount has been shrinking, which is gold becoming more expensive against fair value.

Position is reported as a rank out of 100 rather than a z-score. The distribution is
left-skewed — mean -4.08 against median -3.83 — so the deep-discount tail inflates the
standard deviation and the z-score described a reading at 84 of 100 as NORMAL. The
z-score is still computed and still drives trigger recalculation; it no longer reaches
a reader.

Message contract changes are recorded in `UPDATE_V1_IMPLEMENTATION.md`.
`skills/telegram-product.md` was updated rather than contradicted: it previously
required a trailing decision section and placed the decision mid-message.

### Defects found while wiring

Three, all caught by rendering against production data rather than by reading code.

**Typical daily move read 7.28pp** when the bubble's entire observed range is 6.4pp.
The rate was derived from consecutive readings, so a small change across a gap of
minutes extrapolated to an enormous daily figure. Now measured over genuine 24-hour
intervals, giving 0.85pp, which matches an independent calculation. Regression test
added.

**RUN compared against the user's own previous request.** `_get_latest_market_snapshot`
took the latest row of any kind, so on the UPDATE path the baseline was the user's
prior click and RUN measured the gap between two clicks. This is why it so often read
`+0.00%`. Both RUN and DAY now prefer scheduled readings.

**The daily recap fired on every scheduled run.** Tolerable at one run a day, but at
hourly cadence it would have produced roughly 24 emails and 24 Telegram messages
daily. It now fires on the first scheduled run of a calendar day, tracked in
`state.json`, and marks the day complete only once a channel actually delivered so a
transient failure retries rather than silently dropping the day.

### Process failure recorded

The user agreed a message template, then asked for two specific changes: narrow the
tables for mobile, and remove a redundant section. Alongside those the implementation
also dropped a data column, renamed two metrics and relocated two lines — none
requested. The user's response: *"the msg gets worse each time you change it"*, and
then *"never ever change an agreed framework without my permission"*.

The dropped column compounded it. `Run` looked useless because it read `+0.00%`, but
it was broken for a fixable reason, and deleting the symptom removed something the
user needed while hiding a real defect.

**Rule for this project: implement exactly what was agreed. Anything else is raised as
a question first, including changes that appear obvious while working on something
else.**

## 12. Operational state — collection cadence

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

### Verified 2026-09-15

The scheduler is confirmed working. Gaps between scheduled snapshots:

```text
1.00 h   x6      hourly firing inside the window
9.00 h   x1      21:00 to 06:00 Tehran, the configured overnight pause
```

Runs appear at :30 UTC because minute 0 in Asia/Tehran is minute 30 UTC.

### Open defect — outcome evaluation never revisits a snapshot

Raising the cadence did not resolve the horizons. All 213 evaluations remain
`INSUFFICIENT_DATA` despite hourly readings being available, so cadence was not the
only cause.

`snapshot_builder.py` line 390 calls `run_outcome_evaluation_for_snapshot()` against
the snapshot it has just created. That snapshot's +1h, +6h and +24h targets are all in
the future, so the call can only ever record `INSUFFICIENT_DATA`. Nothing returns to
the snapshot once its horizons mature.

`backfill_outcome_evaluations()` in `src/analysis/outcome_evaluator.py` does exactly
what is required — it is documented as safe to run repeatedly and evaluates only
snapshots that lack a complete evaluation — and the runtime never calls it.

This is the fifth occurrence of the same pattern in this project: the C14C news
collector, the Analyze trigger, the unenforced analysis window, the RUN baseline, and
now this. Capability is built and tested, and the runtime path never reaches it. The
production liveness rule in `PROJECT_ORCHESTRATION.md` exists because of it.

Fixed 2026-09-15. `backfill_outcome_evaluations()` now runs on the scheduled path
after per-snapshot evaluation. The first production run reported **72 evaluations
resolved**, taking the COMPLETE count from zero to 19: nine at +1h, two at +6h, eight
at +24h. The remainder belong to the sparse era and have no reachable partner, so they
are correctly unresolvable rather than pending.

Covered by `kpi/kpi_sp_c3.py` (**8/8**), which asserts reachability rather than
arithmetic. The arithmetic was never broken — `kpi_pre_sp_c5.py` already covered
backfill, idempotency, tolerance and look-ahead protection and passed throughout. What
had no coverage was whether the runtime reaches any of it, which is the gap all five
occurrences of this pattern share.

### Follow-on finding — the bubble has no outcome

Resolving the horizons exposed that `outcome_evaluations` never measures the bubble.

```python
# outcome_evaluator.py line 192
act_premium = None  # Cannot reconstruct without historical fair value
```

It is hardcoded, and `test_21_premium_insufficient` in the C.5 KPI asserts it, so this
is contract rather than defect. The consequence is that outcome evaluation measures
gold, XAU/USD and USD/IRR while never measuring the single quantity the system exists
to track.

The stated reason appears no longer to hold. `market_snapshots` carries
`premium_percent` and `fair_price` on all 309 rows, so historical fair value is
available and premium could be resolved by the same nearest-observation method already
used for the price series.

`decision_scorecard.py` is unaffected because it computes bubble outcomes directly from
`market_snapshots`. C.14B and C.14C are affected: they consume `outcome_evaluations`,
so their view permanently excludes the bubble.

Left unchanged pending a decision, since it is a documented and asserted contract.

### Merge checklist

Carry these out when SP-C merges into main:

```text
1. tag main as v1.3safe before merging
2. merge SP-C into main after user review
3. change the cron-job.org body ref from "SP-C" to "main"
4. ~~remove the legacy GitHub native schedule~~ DONE 2026-09-20, c1799fe on main from gold-monitor.yml
   once the external trigger is confirmed running on main
5. update the Cloudflare worker to accept /Analyze and pass
   inputs mode=analyze, which only works once main carries the input
```

Step 3 matters: the body pins `ref` to `SP-C`, so after a merge the scheduler would
keep running the feature branch rather than main.

## 13. Deferred

```text
half-life measurement to select the window   needs ~120 days
tightening the comparable band               needs more history
regime recalibration
news classifier repair
immutable forecast-event persistence
collection_mode migration                    requires approval
```

---

## 14. Known limitation

`market_snapshots` does not distinguish scheduled runs from user-triggered updates.
Both the distribution and the scorecard therefore draw on a mixed sample, biased
toward moments when a user happened to look. This resolves with the `collection_mode`
migration, which is a schema change and needs explicit approval.

---

## 15. SP-C.5 — one vocabulary, a trimmed basis, and the reader's own clock

Five changes landed together on 2026-09-16. Four alter agreed behaviour, so each
records what it was, what it became, and the evidence that justified the move.

### 15.1 Valuation basis: minimum → mean of the three cheapest

**Was.** The discount was computed from the single cheapest platform, on the grounds
that a buyer transacts at the lowest available price. That argument was made and
accepted earlier in SP-C and is not wrong about execution.

**Is.** The valuation shown to the reader is computed from the mean of the three
cheapest platforms. The single cheapest is still resolved and still displayed, now
labelled as the market low — the execution price.

**Why.** Measured across 332 snapshots holding 3,240 platform quotes:

```text
cheapest platform sits >3 MADs below the median of the rest   205 of 332   62%

basis                  median level   hourly sd   jumps >1pp   max jump
minimum                       3.93%       0.438       8 / 197       2.12
2nd cheapest                  3.33%       0.276       1 / 197       1.02
median                        2.97%       0.283       1 / 197       1.11
mean of 3 cheapest            3.47%       0.273       1 / 197       1.28
```

The minimum is a tail point in 62% of readings, not a market level. It carried 60%
more hour-to-hour noise than the trimmed basis and eight times as many jumps larger
than 1 pp between consecutive readings. A move that size in an hour is a quote
artefact, not the market repricing.

The failure was observed in production. On 2026-09-15 a stale MioGold quote moved the
reported discount 2.07 pp and the message read "unusually large, cheaper than 94% of
the last 30 days" while the market had not moved: local average -0.16%, fair value
-0.16%. The quote refreshed the next morning and the discount fell from 5.35% to
3.77% with no market event. Staleness is structural, not incidental:

```text
platform     quotes   unchanged     %   longest freeze
Parasteh        320         215    67%          89.4h
HoorGold        323         210    65%          26.0h
MioGold         325         167    52%          46.8h
Milli           326          21     6%           8.5h
Taline          331          21     6%           3.5h
```

The platforms that normally set the low are fresh (Milli 68.7% of snapshots at 6%
stale, Taline 12.2% at 6%). A stale platform taking over the low is the signature of
a quote that stopped updating while the market moved away from it.

Three is a trim, the standard treatment for a skewed cross-section, and the same
reasoning that put percentile ahead of z-score in SP-C.2. It keeps the buyer's side
of the distribution (3.47%) rather than retreating to a middle nobody transacts at
(2.97%).

**Scope.** Display path only. `premium_percent` in `market_snapshots` is still
computed from the minimum and still feeds the decision engine, `outcome_evaluations`
and `analysis_snapshots`. Changing it at source requires recomputing 332 rows and
touches decision authority, so it is a phase of its own and is NOT part of this
change. The window the reader's percentile is drawn from is rebuilt from
`platform_prices` on the same trimmed basis, so reading and window never mix bases.

**Tested and rejected.** Whether an isolated cheapest platform predicts an artefact
jump: 4.83 MADs before a jump against 4.00 without, n=8. Not a discriminator. No
early-warning flag was added.

### 15.2 Distribution sample: all rows → scheduled, gated on count *and* span

**Was.** The 30-day window used every stored reading regardless of provenance.

**Is.** Scheduled readings only, once there are at least 30 of them covering at least
14 distinct local days. Until both hold, all rows are used.

**Why the span condition.** A count alone is insufficient. At 16 scheduled runs a day,
30 readings is under two days, and a line reading "of the last 30 days" would be
measuring against Tuesday. Observed directly: at 31 scheduled readings over 3 days the
same instant ranked 14% on the full window and 0% on the scheduled one.

The Iranian week also has a shape:

```text
day     n    median discount   vs overall
Sat    44             3.50%        +0.03
Sun    56             3.33%        -0.14
Mon    52             3.38%        -0.09
Tue    60             3.36%        -0.12
Wed    57             3.43%        -0.04
Thu    31             3.75%        +0.28
Fri    33             3.87%        +0.40
```

The Thursday-Friday weekend runs 0.28 and 0.40 pp deeper than the weekday median,
against a 0.55 pp spread across the whole week — larger than a typical hourly move. A
seven-day span either contains a weekend or does not, and that alone shifts the
median. Fourteen days always contains two.

**Fail-safe check.** The all-rows path is a fallback, and `CLAUDE.md` requires a
fallback to carry degraded provenance to the reader. Reviewed and found not to apply:
nothing is extrapolated, every reading in the window is a real observation, and the
line claims only "the last 30 days", which is true on either path. The claim would
need qualifying if the text ever said "hourly" or "scheduled". The path, sample size
and coverage days are recorded in `market_states.valuation_context_json` under
`valuation`, so an audit can tell the two apart.

### 15.3 Times and day boundaries: UTC → the reader's clock

**Was.** The runner and the database keep UTC; the footer printed it, and everything
that grouped readings "by day" used the UTC date.

**Is.** `src/timeutil.py` holds a single fixed UTC+3:30 offset — Iran abolished
daylight saving in 2022, and the tz database is not reliably present on every runner.
Applied to the message footer and reference times, `trend_resolver` day grouping and
its seven-completed-days window, and the `vs Today` baseline in `baseline_resolver`.

**Why it became urgent.** The footer had been UTC for a while, but the reference
footnote added on 2026-09-15 names clock times. A reader told changes are measured
"vs the 02:31 reading" checks it against their own clock showing 06:01. The
day-grouping error was silent: a "day" ran 03:30 to 03:30 local, which happened to
work only because the cron window (06:00-21:00 local) falls inside one UTC date. A
user pressing Update between midnight and 03:30 local would have been compared
against the previous day.

The 7D column moved visibly when this landed — `Fair 7D` went from -2.69 to -1.30 —
because the day boundary moved, not the market.

**Unchanged and verified:** the 7D average remains an average of daily averages, each
day weighted equally regardless of how many readings it holds, and returns `None`
rather than averaging a partial week. `trend_resolver._seven_day_metric`.

### 15.4 The verdict left UPDATE

**Was.** `WAIT` sat at the top of the message with a band sentence beneath it and,
when they disagreed, a line naming the candidate decision.

**Is.** Neither appears. UPDATE is a view of the market.

**Why.** The chain that produces a decision — valuation, momentum, structure,
conflict, hysteresis — is not in this message, so the word on its own asked to be
trusted rather than understood. It belongs in ANALYZE next to its reasoning. The band
sentence went too: "Below its own recent average" restated what "Bigger than 29% of
the last 30 days" says one line later, in vaguer terms and without the figure.

`final_decision` remains the sole BUY/SELL authority and is still computed and stored
on every run. Nothing about decision authority changed, only where it is displayed.

### 15.5 Wording and layout

```text
was                                   is
Cheaper than 29% of the last 30 days  Bigger than 29% of the last 30 days
Day (table column)                    Today, matching "vs Today" in THE NUMBER
Platform (table row)                  Cheap 3, matching the block's basis
Local price <average>                 Cheapest 3 <names> / <prices>
two footnote blocks, 7 lines          one footnote in MARKET, 4 lines
```

"Cheaper than" left the reader asking cheaper than what. The subject is the discount,
and the footnote already defines a bigger discount as the cheaper one, so one word
carries both.

### 15.6 Parked, with reasons

```text
skew statistic in UPDATE        the trimmed basis is the treatment; a coefficient
                                would be jargon. Deeper treatment belongs in ANALYZE.
7D / 15D median or average      the percentile places the reading against history and
lines in UPDATE                 carries more than a midpoint; "Deep discount If X"
                                already supplies the distance. Parked by the product
                                owner as clutter, may be recalled.
Confidence line                 withheld; the window is stated, and a bare "LOW" was
                                noise the reader could not act on.
"What this means" translation   parked by the product owner, may be recalled later.
premium_percent at source       see 15.1 Scope. Own phase, own approval.
```

### 15.7 Open, needing a decision

1. **A single-vendor move is read as a market valuation move by the decision engine.**
   The matrix at `caluclator/conflict.py` maps (CHEAP, IMPROVING, DISCOUNT_DOMINANT)
   to BUY. On 2026-09-15 that combination held on the strength of one stale quote. The
   message now makes the source visible; the engine still cannot tell a vendor from a
   market. Structural, belongs in the Analyze wing.
2. **The decision engine has no measured edge.** Scorecard: 55.2% hit rate against a
   55.2% always-WAIT baseline. Edge 0.0.
3. **`quote_side` is `SINGLE` for all 2,215 observations.** Whether a platform price
   is what they sell at or what they buy at is never recorded. If these are bid
   prices, part of the persistent discount is dealer spread and available to nobody.
4. **Convergence after a divergence is real but small.** Where the cheapest sat >1%
   below the median of the rest: at +24h the outlier rose 1.06% and the pack 0.86%,
   closing the gap 0.199 pp; the outlier rose in 62 of 81 cases, the pack fell in 31.
   The direction favours convergence over the outlier leading the market down, but
   0.2 pp a day is below any plausible execution cost.

---

## 16. SP-C.6 — three latches (2026-09-18)

Three defects found by asking why the Analyze wing's outputs never varied. All three
had shipped, passed their tests, and run in production for weeks without raising an
error. Failure patterns are generalised in `LESSONS_LEARNED.md`.

### 16.1 The decision engine was latched off

`caluclator/signals.apply_hysteresis` suppressed a repeat of the same decision with no
time bound. `cooldown_hours` was present in the signature and documented as "reserved
for future use"; the time dimension was never implemented.

`state.json` persists across runs through `actions/cache@v4`
(`.github/workflows/gold-monitor.yml`), and the latch clears only when a *different*
alert fires — a SELL, which requires an EXPENSIVE valuation that has never occurred in
338 readings. So the first BUY ever sent disabled every BUY thereafter.

```text
final=WAIT  candidate=WAIT   164
final=WAIT  candidate=BUY    100   <- every BUY candidate, suppressed
distinct final_decision values ever issued: WAIT only, 264 of 264
```

**Consequence beyond the missing alerts.** The decision scorecard reported a 55.2% hit
rate against a 55.2% always-WAIT baseline and an edge of 0.0. That was reported to the
product owner as evidence the strategy does not work. It was not: the scorecard was
scoring a constant against a constant. The engine had not been disproven, it had never
run. The conflict matrix, valuation bands and momentum logic are therefore **untested
in production**, not failed.

**Fix.** `apply_hysteresis` gains `last_alert_at` and honours `cooldown_hours`,
defaulting to 24 — a starting value taken from the collection cadence (hourly, 06:00
to 21:00 local, DAY anchored to the first scheduled reading), to be re-derived from
measured zone-episode durations once `resolve_zone_episodes` has enough history.
`main._last_alert_time` reads the timestamp from the persisted alert history.

**Failure direction is deliberately open.** An unknown alert time is treated as an
expired cooldown, not a live one. Failing closed reinstates the exact latch being
fixed: one missing timestamp would disable alerting permanently. A duplicate alert is
noise; silence already cost a hundred signals.

**The conflict matrix is untouched.** `skills/market-analyst.md` forbids replacing it
with a weighted score without explicit approval. This change is to the gate after it.

### 16.2 Regime stress thresholds never varied

`analysis/regime.py` evaluated four evidence families against fixed constants. Two
were satisfied by essentially every reading this market produces:

```text
threshold            value        fired over the 30-day window (252 snapshots)
premium_magnitude      2.0        250 of 252   99.2%     range is 1.82 - 8.19
platform_spread    500,000        252 of 252  100.0%     normal spread ~3,300,000
```

With two of four families permanently stressed and regime hysteresis latching the
outcome, `regime_state` read PANIC on all 96 analysis snapshots ever written.

**Fix.** `resolve_stress_thresholds(session)` calibrates `premium_magnitude`,
`premium_change` and `platform_spread` to the 80th percentile of the market's own
30-day distribution — the same percentile as `bubble_position.EXPENSIVE_PERCENTILE`,
so "stressed" means what "expensive" means there: the top fifth of its own range.

```text
threshold            old         calibrated      fires after
premium_magnitude   2.00            4.9049       50 of 252  19.8%
premium_change      1.00            0.5984
platform_spread   500,000       8,076,648       50 of 252  19.8%
```

Calibration is a module-level function, deliberately separate from `RegimeClassifier`,
so the classifier stays a pure deterministic function of its inputs and its injected
thresholds. Explicitly configured thresholds still win; calibration fills only what
the caller has not pinned. Below 30 observations it returns `{}` and the fixed
defaults stand.

`volatility` (1.5) and `usd_change` (0.5) are **left alone**. Nothing has measured
whether those two constants are wrong, and replacing a threshold on suspicion is how
the other two got here.

### 16.3 An unbounded subprocess was eating scheduled runs

`collector/bonbast.get_usd_sell_rate` ran a third-party CLI through `subprocess.run`
with no `timeout=`. The CLI performs its own network calls and sets no timeout either.

```text
8 of the last 70 workflow runs: cancelled
cancelled runtimes: 10.3, 10.3, 20.4, 20.4, 10.3, 20.4, 10.4, 20.3 minutes
successful runtimes: n=62, min 1.0, median 4.4, max 14.0
```

Log of run 35307235950:

```text
04:31:05  MODE: ANALYZE
04:31:05  World Gold  gold-api.com  FAILED (NameResolutionError)
04:50:54  ##[error]The operation was canceled.
```

A DNS failure on the preceding collector, then 19m49s of silence, then the job
timeout. Those eight runs are the missing hourly readings — the 2–3 hour gaps observed
on 09-16, 09-17 and 09-18.

**Fix.** `COLLECT_TIMEOUT_SECONDS = 60`. The caller already wraps this in
`except Exception` and degrades USD/IRR to `None`, and `TimeoutExpired` is an
`Exception`, so a timeout now costs one input instead of the whole run.

All eleven HTTP collectors already had timeouts. The single subprocess did not, and it
was the one that took the system down.

### 16.4 Coverage

`kpi/kpi_sp_c5.py`, 23 assertions. Suite is 24 files.

The assertions are written as *does the output still vary* rather than *does it
compute*, because all three defects produced correct-looking constants. `test_11`
drives five simulated days through the gate and requires both BUY and WAIT to appear;
`test_20` requires two regime inputs to reach different states; `test_16` documents
the old fixed threshold firing on more than 90% of the observed range so the defect
is recorded rather than remembered.

### 16.5 Open

- **`kpi_pre_sp_c4.py` makes a real network call** and fails intermittently with a
  socket timeout. It passes on retry. Pre-existing; a KPI should not depend on the
  internet.
- **The repaired engine has not yet issued a decision.** Everything downstream — track
  record, expectancy, the ANALYZE feedback loop — needs an engine that has actually
  decided something. Observation period before building on top.
- `volatility` and `usd_change` regime thresholds remain unverified constants.
- News is keyword-classified only; 70% `UNKNOWN` relevance. Lowest priority.


### 16.6 Follow-up, 2026-09-19 — the regime fix was inert

Verification a day after 16.2 found `regime_state` still PANIC on all 147 snapshots,
18 of them after the fix. Calibration was running and logging correctly in production:

```text
14:32:18  Regime thresholds calibrated: {'premium_magnitude': 4.7311,
          'premium_change': 0.5783, 'platform_spread': 7981279.0}
```

`config/config.json` pinned the same three keys at their original fixed values, and
the merge in `snapshot_builder` lets explicit configuration win over calibration. The
calibrated values were computed, logged, and discarded on every run.

The unit tests could not see it: they construct `RegimeClassifier` directly and never
load the shipped config file.

**Fix.** The three calibrated keys are removed from `config/config.json`, with a note
in the file explaining that re-adding them silently disables calibration.
`volatility`, `usd_change` and `news_density` stay, since calibration does not compute
them. The override behaviour itself is kept and asserted — a threshold set on purpose
should beat a calibrated one; what was wrong was shipping defaults in that slot.

`kpi_sp_c5.test_18b` now asserts against `config/config.json` itself. Suite 24/24,
25 assertions in this file.

Verified against live data after the change: zero of four families stressed, raw
candidate RELIEF, confirmation count 1. The next scheduled run confirms and the regime
leaves PANIC for the first time in its recorded history.

### 16.7 What the repaired decision engine did

The hysteresis fix worked on the first day.

```text
since the fix:  final=WAIT candidate=WAIT   17
                final=WAIT candidate=BUY     4     suppressed by the 24h cooldown
                final=BUY  candidate=BUY     1     <- first BUY ever issued
all-time distinct final_decision values:  WAIT 322, BUY 2
```

Two BUY decisions exist where 264 readings had produced none. The cooldown then held
the following four candidates, which is the intended behaviour rather than the latch.

### 16.8 The collection timeout worked

```text
before the fix   34 runs   28 success   6 cancelled
after the fix    26 runs   25 success   1 cancelled
runtimes after: min 1.2, median 5.8, max 10.3 minutes
```

2026-09-19 collected hours 2 through 14 with no gaps — the first clean day.


---

## 17. SP-C.7 - the reference level stopped moving under the reader (2026-09-20)

The product owner noticed `Deep discount` reading 3.36 in one message and 3.35 in
another 35 minutes later, and asked why a reference level moves within a day.

Three causes, only one of them legitimate.

**1. The percentile index advances as the window grows.** `deep_at` is
`ordered[int(0.40 * n)]`. Each new reading raises n, and every second or third
reading advances the index one place onto a different value:

```text
n=277  index=110  value=3.3333
n=278  index=111  value=3.3211
n=280  index=112  value=3.3198
```

**2. The reader's own Update calls were inside the window.** 16 of 278 rows were
collection_mode 'user', and removing them shifted the threshold 0.0134 pp. One click
on 2026-09-19 moved it 0.0106 pp:

```text
09-19 14:39   user   n=272   3.3597
09-19 15:14   user   n=271   3.3491   -0.0106
```

`PROJECT_MEMORY.md` already required that accumulated user-triggered calls not serve
as a baseline. The scheduled-only gate enforces it, but that gate is not yet active
(14 days of coverage required, 6 available), and the fallback sample defined in
section 15.2 did not exclude them. An under-specification in SP-C.5, not a new defect.

**3. Genuine market drift**, 3.3701 to 3.3211 over three days. This should be visible.

### 17.1 The fix

**A - user rows are excluded from the fallback sample**, not only the clean one.
Unlabelled pre-migration rows still cannot be filtered this way, which is what the
scheduled-only gate eventually resolves.

**B - the reference distribution ends at the last completed local day**, with the
window measured back from that boundary. Ranking today's reading against a pool that
already contained today is what let the pool move under the reading being ranked.
This is the convention `trend_resolver` already uses for the 7D average.

Measured over three days, counting changes in the displayed two-decimal value:

```text
option                        changes
current (all rows, live)           15
A alone                            17
B alone                             3
A + B                               2
```

Day by day, A+B:

```text
2026-09-14   14 readings   3.43   constant
2026-09-15   22 readings   3.40   constant
2026-09-16   17 readings   3.44   constant
2026-09-17   18 readings   3.42   constant
2026-09-18   20 readings   3.37   constant
2026-09-19   21 readings   3.37   constant
2026-09-20    7 readings   3.35   constant
```

A alone makes the displayed value marginally less stable (17 against 15). It is kept
regardless: it is a correctness fix, not a stability one. The act of reading a number
must not change it.

### 17.2 What deliberately still moves

`Bigger than X%` ranks the current reading and continues to update every run. Only
the distribution it is ranked against is frozen. Verified: two different current
readings against the same settled pool give the same deep_at and different
bigger_than.

### 17.3 Trade-off, accepted by the product owner

The reference ignores the current partial day. For a 30-day level that is immaterial,
and it is the same rule the 7D column already follows.

### 17.4 Coverage

`kpi_sp_c4.py` gains six assertions (50 total): constant across one local day, steps
at the boundary, today's readings excluded, user rows excluded, and the live rank
still responding. Suite 24/24.


---

## 18. SP-C.8 - world gold provenance, and a false alarm corrected (2026-09-20)

Prompted by a third-party audit of SP-C. Three findings reviewed; one confirmed.

### 18.1 SP-C-001 rejected, and why it was filed

The audit reported that scheduled runs take the UPDATE path and produce no analytical
history. That was true until 2026-09-13 and is documented in `PROJECT_MEMORY.md` --
including the sentence stating it was fixed. The reviewer read the defect narrative as
current state.

Verified current: the workflow declares `inputs.mode`, cron-job.org sends
`mode=analyze`, `main.py:253` routes on it, and `analysis_snapshots` records 16-17 per
day with news ingestion at ~350 events per 24h.

**Consequence taken:** `PROJECT_MEMORY.md` now carries a **Resolved defects index** at
the top. A document that narrates failures in detail needs a place to check before
reading one as live.

### 18.2 SP-C-002 partially confirmed, narrowed

The audit's framing -- `main.py` as a growing orchestration hotspot -- is not supported
by its own criteria. 480 lines, 10 functions, decision logic properly delegated,
Update/Analyze cleanly separated.

One real violation, which the audit missed: `calculate_fair_price` documented itself as
returning IRR while returning Tomans, with the x10 correction applied 300 lines away in
`main.py`. Any second caller trusting the docstring would be out by a factor of ten.

**Fixed:** the docstring, and a comment at the call site naming the unit contract.
**Not fixed:** the location of the x10. Relocating it changes where a stored-value
semantic is applied and breaks `src/tests/test_gold.py`; same class as the
premium_percent basis split, so it gets its own phase.

### 18.3 SP-C-003 confirmed

Two provenance channels for world gold, both inert:

```text
source      literal "kitco_fallback" whether live or cached   266 of 266 rows
freshness   evaluate_freshness(now, now, ...)                 3,316 of 3,316 FRESH
```

`world_from_fallback` was set in `main.py` and used once, to render a Telegram
warning. It never reached persistence. The fail-safe law in `CLAUDE.md` requires a
fallback to carry degraded provenance; it was carried to the human and not to the
system.

**Fixed.** Both fallbacks return `(price, observed_at)` instead of discarding the age.
`source` is `kitco` or `kitco_cached`. `freshness` is evaluated against the real
observation time. No migration: both columns already existed for this purpose.

Platform observations deliberately keep `(now, now)`. They are fetched live, and a
platform does not disclose the age of its own quote, so anything but FRESH there is
invented precision.

**A bug introduced and caught during this change:** the first edit made the fallbacks
return tuples while the call site still read
`_fallback_world_from_history(...) or _fallback_world_from_db(...)`. `(None, None)` is
truthy, so the tuple itself would have been assigned as the world gold price.
`test_27` now guards the shape.

### 18.4 Severity revised down, and a false alarm corrected

SP-C-003 was initially rated High on the grounds that 36 of 39 consecutive XAU/USD
readings were identical, suggesting the fallback fired constantly.

**That was wrong.** The sample was taken on a Saturday and consisted almost entirely
of weekend readings. The product owner identified the cause immediately: the world
gold market closes at the weekend, and USD/IRR goes stale on the Iranian weekend.
Measured:

```text
XAU/USD frozen:   Sat 89%   Sun 90%   Mon-Fri 0-3%
USD/IRR frozen:   Thu 61%   Fri 62%   other days 23-35%
```

Both exactly as described. Severity drops to **Medium**: the defect is real, but there
is no evidence the fallback fires often.

A check was also run on whether the Thu/Fri discount deepening -- used to justify the
14-day coverage gate in section 15.2 -- is an artifact of the frozen USD rate. It is
not: USD frozen 3.34% against USD moving 3.38%. That decision stands.

### 18.5 What the question actually surfaced

Closed-market readings are a structurally different population:

```text
XAU frozen   n=128   median gap 3.06%
XAU moving   n=292   median gap 3.44%
```

Nothing marks them, so they sit in the same 30-day distribution. Measured distortion:

```text
threshold bias, open-only vs pooled     mean +0.091 pp   max +0.171 pp
rank shift, open-market readings        mean  5.0 points
rank shift, closed-market readings      mean 13.8 points   max 27
readings whose rank moves >= 10 points  24 of 120  (20%)

sample sizes if split:  pooled 257   open 179   closed 78
```

Session marking is approved in principle. The design is open and carries at least one
hard constraint: a 30-day window contains only 8-9 weekend days, so a closed-session
sample can never satisfy `MIN_SCHEDULED_COVERAGE_DAYS = 14`. See section 19 when
written.

### 18.6 Coverage

`kpi_sp_c5.py` grows to 33 assertions. Suite 24/24.


---

## 19. Market sessions - investigated, deliberately not implemented (2026-09-20)

An investigation that ended in no code change. Written down because the reasoning is
the deliverable, and because two of the wrong turns are attractive enough that someone
will take them again.

### 19.1 The structural fact

Iran and the world gold market keep different calendars, and they are almost exactly
out of phase. Saturday is the **first** day of the Iranian working week, not a
weekend. Measured over 42 days, as the share of consecutive same-day readings where
each input changed:

```text
day     n    XAU moves   USD moves   fair moves   what drives fair value
Sat    58          0%         60%          60%    currency alone
Sun    68          0%         74%          74%    currency alone
Mon    46        100%         70%         100%    both
Tue    53         98%         60%          98%    both
Wed    61         97%         72%          97%    both
Thu    42        100%         29%         100%    world gold alone
Fri    46         98%         28%          98%    world gold alone
```

**The two drivers take turns.** Iran's busiest days are the world's quietest and the
reverse. Thursday and Friday are the Iranian weekend, which is why USD/IRR goes quiet
while world gold trades normally.

### 19.2 Fair value is NOT frozen when world gold is closed

This is the correction most likely to be needed by a future reader. It is tempting to
assume that with XAU frozen on Sat/Sun, fair value is pinned to Friday's close. It is
not. Fair value is XAU x USD, and USD moves on 60-74% of weekend readings.

Cumulative fair-value movement across each observed closure, with XAU frozen
throughout:

```text
week 32   19.55M -> 19.45M Tomans   -0.54%    USD 186,700 -> 185,700
week 33   19.74M -> 19.68M Tomans   -0.32%    USD 187,000 -> 186,400
week 34   21.26M -> 22.12M Tomans   +4.02%    USD 191,500 -> 199,200
week 35   21.65M -> 22.17M Tomans   +2.38%    USD 201,500 -> 206,300
week 36   23.74M -> 24.06M Tomans   +1.35%    USD 222,200 -> 225,200
week 37   24.89M -> 24.04M Tomans   -3.41%    USD 237,300 -> 229,200
week 38   24.14M -> 24.41M Tomans   +1.14%    USD 228,600 -> 231,200
```

A 4% move in fair value over a weekend with the world market shut the whole time.
**Any message or model that describes weekend fair value as stale is wrong.** The gold
component is stale; the number is live.

### 19.3 Why closed-market readings are NOT split out

Closed-market readings are a structurally different population:

```text
XAU moving   n=292   median gap 3.44%
XAU frozen   n=128   median gap 3.06%
```

Splitting the distribution by session was approved in principle and then rejected on
measurement. Three reasons, in descending order of weight.

**1. The user's decision spans sessions.** The question is never "is this a good
Saturday", it is "buy now or wait". From Saturday, waiting means Monday. Ranking a
Saturday only against other Saturdays destroys exactly the comparison the decision
requires.

**2. The correction is smaller than the noise.** Pairing each weekend's last reading
with the following Monday's first, over six transitions:

```text
re-rate on reopen    mean -0.205 pp   median -0.174 pp   sd 0.524
                     deeper 2/6, shallower 4/6
XAU move over closure  mean -0.085%   sd 0.664
```

Mean -0.205 with a standard error of 0.214 is indistinguishable from zero. There is no
detectable bias to correct. Meanwhile the weekend/weekday systematic difference is
0.28 pp and the uncertainty around reopen is 0.52 pp -- **the noise is roughly twice
the signal.** Session ranking would apply precision that is not present.

**3. These are Iran's most active days, not degraded observations.** Quarantining
Sat/Sun would isolate the busiest days of the Iranian working week into their own
small bucket.

Had it been implemented, the measured effect would have been:

```text
threshold bias, open-only vs pooled     mean +0.091 pp   max +0.171 pp
rank shift, open-market readings        mean  5.0 points
rank shift, closed-market readings      mean 13.8 points   max 27
sample sizes if split:  pooled 257   open 179   closed 78
```

It also carried a hard arithmetic blocker: a 30-day window contains only 8-9 weekend
days, so a closed session can never satisfy MIN_SCHEDULED_COVERAGE_DAYS = 14.

**Sample size caveat.** Six reopen transitions is thin. The conclusion "no bias" is
provisional. Re-test when a dozen closures are available; the finding may change and
this section should be revisited rather than cited.

### 19.4 Also rejected: a user-facing driver line

A line naming the active driver -- "World gold closed. Fair value is moving on the
currency." -- was designed and dropped. It changes no number. The discount, the
threshold and the rank are identical with or without it.

The reasoning that killed it is worth keeping: **the data is already correct.** If a
buyer transacts in Tehran on Saturday, the world value of that gold *is* Friday's
close; there is no better reference in existence. Fair value computed from a live USD
rate and a last-close XAU is the right number, not an approximation of one.

### 19.5 The one place this may actually matter

**Outcome evaluation horizons are session-dependent.** A 24-hour outcome measured
Saturday to Sunday captures Iranian-side movement against a frozen gold reference. The
same horizon measured Wednesday to Thursday captures both drivers. They are not the
same measurement.

The ANALYZE feedback loop rests entirely on those evaluations. With ~500 resolved
outcomes expected by end of September this becomes testable: **do closure-spanning
horizons behave differently from open-market ones?** If yes, ANALYZE must account for
it. If no, this whole section is trivia.

That question is the only actionable output of this investigation, and it belongs to
the ANALYZE phase.


---

## 20. SP-C.9 - the collector ceiling that did not bind (2026-09-21)

One scheduled run still died at the job timeout after the bonbast fix: 2026-09-21
05:30 UTC, cancelled at 20.3 minutes, having written nothing. That hourly reading does
not exist. Cancellation rate had fallen from 18% to 4%, so the remaining cause was
different from the one fixed in 16.3.

The GitHub log was unreachable from this machine (TLS handshake timeout to the Actions
log receiver, three attempts), so the diagnosis is from code and from the absence of a
snapshot at that slot.

### 20.1 The defect

`collector/iran.get_market_prices` documented a hard 20-second ceiling and did not have
one:

```python
with ThreadPoolExecutor(max_workers=len(COLLECTORS)) as executor:
    ...
    done, not_done = wait(..., timeout=GLOBAL_COLLECTOR_TIMEOUT, ...)
    for future in not_done:
        future.cancel()          # no-op: the future is already running
```

Two independent reasons it failed:

1. `future.cancel()` only cancels a future that has **not started**. `max_workers`
   equals the collector count, so all eleven start immediately and none is cancellable.
2. Leaving the `with` block calls `executor.shutdown(wait=True)`, which blocks until
   the slowest thread finishes. The capped `wait()` was followed immediately by an
   uncapped one.

The trigger is that `requests`' `timeout=` **does not bound DNS resolution**. On a
degraded runner a collector thread hangs indefinitely, so the process sat until the
job timeout and no snapshot, no message and no analysis were produced.

This is the fourth instance in this project of a bound that is documented and does not
bind, after the decision hysteresis, the regime hysteresis and the bonbast subprocess.

### 20.2 The fix

Daemon threads with a single shared deadline. `join()` takes a real timeout, and a
daemon thread cannot hold the interpreter open at exit -- which a `ThreadPoolExecutor`
worker can, because `concurrent.futures` registers an atexit hook that joins them.

One deadline rather than one timeout per join: eleven sequential joins of
`GLOBAL_COLLECTOR_TIMEOUT` would permit eleven times the intended ceiling.

A hung collector now costs one platform instead of the whole run.

### 20.3 The flaky KPI, fixed by the same reasoning

`kpi_pre_sp_c4.test_15_invi_failure_isolated` called `get_market_prices()` against all
eleven live sites. It failed intermittently on a socket timeout, and it could never
fail for the reason it was written to catch, because a healthy network makes the
isolation path unreachable. It was a network test wearing a unit test's name.

Now substitutes two stub collectors, one of which raises, and asserts the isolation
property directly. Ran three times consecutively, green each time.

### 20.4 Coverage

`kpi_sp_c5.py` gains three assertions (36 total): the ceiling binds against a
deliberately hanging collector, the threads are daemons, and the ceiling is a single
deadline. Suite 24/24.


---

## 21. SP-C.10 - the news feed was collecting the wrong news (2026-09-21)

`EVENT_STRESS` is one of four regime families and had never fired: 0 HIGH or CRITICAL
events in 72 hours. That was filed as "the keyword classifier needs replacing with an
LLM". It was not a classifier problem.

### 21.1 What was actually being collected

Per-source yield over seven days, recoverable only by parsing URLs because
`news_events.source` was the literal string `rss` on every row:

```text
host                    items   relevance
mehrnews.com            1,987   100% UNKNOWN
tehrantimes.com           230   161 RELEVANT
kingworldnews.com          51    31 RELEVANT
goldbroker.com             10    10 RELEVANT
```

Sample headlines from the dominant source: a health budget review, a baker fined in
North Khorasan, a hiking trail cleanup, 2kg of opium seized, basketball players
exempted from military service, a wind forecast for Ilam.

**A national general-news firehose, ingested at ~280 items a day, yielding nothing.**
No classifier can extract market signal from an opium seizure report.

Three further configured feeds returned nothing at all. The product owner identified
the cause immediately: they are geoblocked from a GitHub runner outside Iran.
Confirmed by probe -- Tasnim gives `RemoteDisconnected`, CBI gives `ConnectionReset`,
Eghtesad Online returns an empty document.

**Half the source list was dead and nobody could see it**, because per-source yield
was not measurable without parsing URLs by hand.

### 21.2 What the system could not see

On 2026-09-20 the regime moved NORMAL to FEAR to RELIEF driven entirely by USD/IRR,
while world gold was closed. There were also Middle East attack rumours that did not
materialise, and gold fell 0.92% over 72 hours. None of that reached the system.

A probe of candidate feeds returned, on the first try:

```text
google:iran rial currency   "Rial Slides to 232,000 as Retirees March and Parliament..."
google:middle east ...      "Middle East braces for more violence as Iran claims US..."
donya-e-eqtesad.com         "قیمت طلا امروز... /کاهش قیمت طلا"   (gold price falls today)
```

The first names 232,000 -- the exact USD level that drove the FEAR episode.

### 21.3 The new source list

```text
kept      goldbroker.com, kingworldnews.com, tehrantimes.com
added     investing.com/rss/commodities.rss
          news.google.com  q=gold price          (2-day window)
          news.google.com  q=iran rial currency  (7-day window)
          news.google.com  q=middle east strike OR attack  (2-day window)
          donya-e-eqtesad.com, tejaratnews.com
removed   mehrnews.com, tasnimnews.com, eghtesadonline.com, cbi.ir
```

**Targeted queries rather than firehoses.** A topic query sets signal-to-noise at the
source instead of ingesting a nation's news and filtering afterwards. Verified
end-to-end: all nine sources return parseable, on-topic items, 160 per cycle before
deduplication.

**The two Iranian feeds are unproven from a GitHub runner.** They parse from inside
Iran. Reachability from outside is the same unknown that silently killed Tasnim, and
it can only be settled by a real scheduled run. Watch their per-source yield -- which
is now possible, because of the next item.

### 21.4 Feed identity is recorded

`news_events.source` was `rss` on all 4,019 rows: a sixth degenerate column.
`source_label()` now derives a stable identity from the URL, carrying the query for
Google News feeds so three topic feeds sharing one host stay distinguishable.

**The dedup key deliberately did not change.** It was hashed over `source`, which was
always the constant `rss`, so in practice it has always been a hash of the title
alone. Hashing real identity would re-key the entire corpus as new, and would stop the
same story arriving from two feeds from deduplicating at all. `DEDUP_NAMESPACE` is
pinned to the historical value on purpose.

### 21.5 Database cleanup

2,861 Mehr rows deleted, approved by the product owner. Verified before and after:

```text
news_events          4,040 -> 1,179     (2,861 deleted, 0 of them ever RELEVANT)
foreign keys referencing news_events: 0
market_snapshots, platform_prices, market_states, price_observations,
analysis_snapshots, outcome_evaluations, platform_candles:  all unchanged

remaining by host: tehrantimes 624, goldbroker 361, kingworldnews 194
```

### 21.6 A bug found while building this

`source_label` returned `unknown` for every Google News feed. The cause was a missing
`import re`, and a bare `except Exception: return "unknown"` swallowed the `NameError`
silently -- the exact silent-degradation pattern this change exists to remove. The
handler now prints what it caught.

### 21.7 Coverage

`kpi_sp_c5.py` grows to 43 assertions, including two that read `config/config.json`
directly: the retired feeds must not reappear, and the targeted queries must be
present. Suite 24/24.


---

## 22. SP-C.11 - the preference filter that discarded good readings (2026-09-21)

Found while designing ANALYZE. `outcome_evaluations` carried 26 rows whose
`outcome_status` was `COMPLETE` while `premium_direction` was `INSUFFICIENT_DATA` --
a row asserting it was complete and that its primary leg was not.

### 22.1 The defect

`_get_nearest_recorded_premium` prefers scheduled readings so an irregular
user-triggered request cannot become an outcome. The preference was applied to the
whole window **before** the nearest row was selected:

```python
base = query(...).filter(timestamp > after_time,
                         timestamp <= target_time + tolerance)   # upper bound only
candidates = base.filter(collection_mode == "scheduled").all()
if not candidates:
    candidates = base.all()                                      # never reached
nearest = min(candidates, key=lambda s: abs(s.timestamp - target_time))
if abs(nearest.timestamp - target_time) <= tolerance: ...
```

Two compounding faults:

1. **The window was bounded on one side only.** It ran from `after_time` -- a whole
   horizon earlier -- to `target + tolerance`, so rows hours from the target were
   candidates.
2. **The preference ran before proximity.** If any scheduled row existed anywhere in
   that wide window the fallback never executed, `min` picked the nearest *scheduled*
   row, and if that was beyond tolerance the function returned `None`.

So a scheduled reading an hour away shadowed an unscheduled one four minutes away,
and the function returned nothing although a usable row existed:

```text
target        nearest ANY        nearest SCHEDULED
09-17 22:02      8m unknown          61m scheduled
09-16 21:51      4m unknown          50m scheduled
09-15 11:20      7m user             19m scheduled
```

The preference exists to stop a user's click *becoming* an outcome. Ordering it ahead
of proximity made it discard a good reading in favour of nothing.

### 22.2 Why it mattered now

Nothing in `src/` reads the premium leg of `outcome_evaluations` -- `dataset.py`
labels on `rep_gold_direction`. Instance nine of built-but-not-wired, and the ANALYZE
feedback loop is about to become its first consumer. The defect was harmless only
because nobody had looked.

It was also live, not historical: 11 of the 26 post-date the fallback being wired.

### 22.3 The fix

Bound the window on both sides of the target, then rank on `(distance, scheduled)` so
**proximity decides and provenance only breaks a tie**. The preference survives in the
form it was actually meant to take.

### 22.4 The repair

All 26 were recoverable -- a snapshot carrying a premium sat within 15 minutes of
every target. Backfilled with before/after verification:

```text
COMPLETE rows with no premium leg   26 -> 0
premium_direction on COMPLETE       UP 142, DOWN 104, FLAT 6   (no INSUFFICIENT_DATA)
outcome_evaluations / market_snapshots / analysis_snapshots / market_states
                                    row counts unchanged
```

Recovered movements are sensible, spanning -2.21 to +2.50 pp with both directions
represented.

### 22.5 Coverage

`kpi_sp_c5.py` grows to 50 assertions. `test_39` is the defect itself: a row four
minutes away must beat one sixty-one minutes away. `test_40` holds the tie-break so
the fix cannot be "simplified" into dropping the preference. `test_41` guards the
lower bound. Suite 24/24.


---

## 23. SP-C.12 - ANALYZE and the deep-discount push (2026-09-21)

UPDATE says where the market is. The question it raises and never answers is whether
that matters. ANALYZE answers it from the record: counts and ranks over readings that
already happened, and no forecast.

### 23.1 What ANALYZE says

Three sections and a data footer.

**WHEN THE DISCOUNT WAS AT THIS LEVEL.** Past readings whose discount sat near the
current one, and what the following 24 hours did to each. "At this level" is printed
as a band so it is a number rather than a claim. The heading went through three
drafts: "AFTER READINGS LIKE TODAY" was read as "after today's reading", and today
supplies only the level -- nothing about today as a period is involved.

**THE LAST 30 DAYS.** Range, typical level, where today sits, and the deep zone: its
threshold, how often it opened, how long it stayed open.

**PRICE MOVEMENT.** How fast the price a buyer actually pays moves, hour to hour, and
what counts as sharp. Measured on the trimmed basis price rather than the discount,
because exposure is to what you pay. Both directions reported without comment: a
sharp fall is an opportunity to one reader and a reason to sell to another.

**DATA.** Sample size, sampling quality, how much of the outcome record has resolved.

The decision record is built and **hidden** until it has a sample. Three decisions is
an anecdote, and `skills/market-analyst.md` forbids manufacturing confidence from a
small one.

### 23.2 The read-only wing

`skills/telegram-product.md`: *a user request must not silently become an Analysis
Wing execution or historical learning observation.*

So `/Analyze` is a third workflow mode, `report`, carried by its own `REPORT_ONLY`
environment variable rather than derived from `SCHEDULED_RUN`. `main.py` returns
before any collection happens: no prices fetched, no snapshot, no outcome, no row of
any kind. `kpi_sp_c6.test_20` asserts the row counts are unchanged across a report,
and `test_21` asserts the module contains no write call at all.

### 23.3 The push, and why a bare threshold does not work

The deep zone typically stays open **two hours**, longest observed **five**. A reader
who looks when they remember to look will miss most of them. That is the entire
justification for interrupting; nothing else the system knows earns it.

Firing on a threshold crossing produces a burst per episode. Measured at the 85th
percentile over 44 days: 23 crossings, median duration twelve minutes. On 8-9 August
a single episode that went nowhere produced four alerts in 41 hours, two of them 35
minutes apart.

So the trigger is a thermostat. Fire at the high level; re-arm only once the discount
has returned below a lower one. Same data: 9 alerts instead of 23, never closer than
23 hours, 14 flickers suppressed. `kpi_sp_c6.test_10` replays those exact readings
and requires the naive count to be 4 and the banded count to be 1.

### 23.4 Why the band is a width, not a second percentile

The obvious design is "fire p85, re-arm p50". Measured, the distance between those
two percentiles ranged **0.24 to 0.84 pp** across the observation period, while the
90th-percentile reading-to-reading change is **0.46 pp**. At the narrow end the band
would have been half the noise it exists to filter.

A percentile pair has a width that drifts independently of what it is filtering. The
re-arm level is therefore `fire - 1.5 x (p90 of the step size)`, with a floor of
0.25 pp so a very quiet market cannot collapse it to nothing. The multiple is the
elbow of a measured sweep: below it flicker survives, above it separate episodes
merge.

### 23.5 Both levels move

The 85th percentile of the discount moved **0.81 pp** in six weeks: 4.49% on 13
August, 3.70% on 21 September. A level fixed at either date is wrong at the other,
which is the failure that produced `valuation_state=CHEAP` on every reading and
`regime_state=PANIC` on every snapshot. Both levels are recomputed from completed
days only, so they hold still within a day and step at the boundary.

Worth recording: at the current distribution `p85` and `median + 1 standard
deviation` agree to within **0.02 pp**, the distribution having become near-symmetric
(Pearson skew -0.09) once the trimmed basis removed the outlier tail. The product
owner's instinct arrived at the same level from the other direction. It is
implemented as a rank because that is the ruler the rest of the system uses and
because a rank survives the distribution skewing again.

### 23.6 The gate fails open

The armed flag lives in `state.json`, carried between runs by the Actions cache --
the same cache whose loss latched `last_alert` into a permanent WAIT and suppressed
100 consecutive BUY candidates.

**Unknown state means armed.** A lost cache costs a duplicate message, which is
noise. The opposite costs silence, which nothing alerts on and which this project has
already paid for once. `kpi_sp_c6.test_06` is the assertion.

**A bug caught during wiring:** `save_state` runs before the analysis snapshot is
built, so the armed flag set by the push was being discarded. Left that way the gate
would read unknown every run, fail open every run, and fire on every reading above
the level -- the exact flicker the band exists to prevent. `test_29` guards the save.

### 23.7 Neither surface recommends

`skills/telegram-product.md` reserves external BUY/SELL alerts to the deterministic
`final_decision`. ANALYZE and the push carry no BUY, SELL or WAIT, no recommendation
and no forecast. `test_22` and `test_24` assert the absence.

### 23.8 A measurement error found and fixed

Deep-zone duration first reported **15 hours**. Collection runs 06:00 to 21:00 local,
so the series carries a nightly gap of roughly nine hours: 66 of 264 intervals exceed
three hours against a median spacing of one. Two readings either side of a night were
joining into one episode, and the reported duration was mostly unobserved time.

Episodes now break across any gap above three hours. Typical duration reads **2
hours**, longest **5** -- observed time only, and the number the push is justified by.

### 23.9 Coverage

`kpi/kpi_sp_c6.py`, 30 assertions. Suite is 25 files.

### 23.10 Documentation contradictions found and resolved

`skills/telegram-product.md` was written against the pre-SP-C message and contradicted
the current system in five places. All five are resolved in that file:

```text
was                                             now
/Analysis as the planned command                /Analyze -- the workflow input, the
                                                run-name and the merge checklist all
                                                already said analyze
"the decision leads the message"                removed from UPDATE in SP-C.8; it
                                                belongs with its reasoning, which is
                                                not in that message
message hierarchy listing PRICE & BUBBLE        both sections dissolved in SP-C.5
DYNAMICS and MARKET STRUCTURE
"always show confidence when it is LOW"         withheld by product decision, SP-C.5
                                                section 15.6
"the bubble distribution is left-skewed"        measured -0.09 on the trimmed basis;
                                                the conclusion (use rank) still holds
                                                for robustness, the justification
                                                does not
```

The binding rule in that file -- external BUY/SELL alerts driven only by
`final_decision` -- is unchanged and shaped this work rather than conflicting with it.

---

## 24. SP-C.13 - one label was carrying two numbers (2026-09-21)

Found by the product owner, reading the three production messages side by side the
day after SP-C.12 shipped.

### 24.1 The defect

```text
surface   line                                 value    definition
UPDATE    Deep discount  If 3.29% or more      3.29%    CHEAP_PERCENTILE (40) of the
                                                        SIGNED gap
ANALYZE   Deep discount      3.70% or more     3.70%    DEEP_ZONE_PERCENTILE (85) of
                                                        the SIZE
push      fires at                             3.70%    FIRE_PERCENTILE (85) of the
                                                        SIZE
```

Same two words, same day, two numbers, in two messages a reader is expected to read
together. The consequence is concrete rather than cosmetic: at a discount of 3.40%
UPDATE tells the reader they are in deep discount, ANALYZE tells them they are not,
and no push arrives.

This is the two-vocabulary problem SP-C.5 removed, in a form that surface did not
cover. SP-C.5 hunted two words for one quantity. This is one word for two
quantities, and it survived because each surface was reviewed against the market
rather than against the other surface.

**Provenance.** `CHEAP_PERCENTILE` is a valuation band boundary from SP-C.2. It was
never an action threshold. The word "deep" was attached to it during an UPDATE
wording pass in SP-C.5, at a point when nothing else in the system used the word.
SP-C.12 then introduced the push and gave the same word to the level the push acts
on, without checking that the word was already taken.

### 24.2 The rule that resolved it

> The number a reader is shown is the number the system acts on.

Anything else is a promise the system does not keep. The product owner chose this
over renaming UPDATE's line back to `Cheap below`, which would have kept two
concepts alive under two names.

### 24.3 One definition, not three equal constants

Making the three constants equal would have fixed the number for one day. The level
is now resolved in one function that all three surfaces call:

```python
# analysis/bubble_position.py
DEEP_DISCOUNT_PERCENTILE = 85

def reference_readings(series, reference_end): ...
def deep_discount_threshold(readings): ...
```

`analyze_report.DEEP_ZONE_PERCENTILE` and `push_trigger.FIRE_PERCENTILE` are now
aliases of `DEEP_DISCOUNT_PERCENTILE`, and all three call sites take their value
from `deep_discount_threshold`. `kpi_sp_c4.test_23c` and `kpi_sp_c6.test_24d` assert
the equality **and** read the source to assert the shared call, because equal
constants in three files is precisely the state that produced this defect.

`analyze_report._percentile` was a byte-identical copy of
`bubble_position._value_at_percentile`. It is now an alias. One concept, two
definitions, is the shape every disagreement in this system has started as.

### 24.4 The pool had to be shared too, not just the rank

The same rank over two samples is still two numbers.

`resolve_relative_valuation` ranks against a scheduled-only pool once its gate opens
(`MIN_SCHEDULED_READINGS`, `MIN_SCHEDULED_COVERAGE_DAYS`, SP-C.5). ANALYZE and the
push use the settled non-user pool. Measured on 2026-09-21:

```text
pool                    n     p85
settled, non-user     265   3.70%
scheduled only         99   3.64%
gate opens in                7 days
```

So unifying only the rank would have split the number again on 2026-09-28. The
threshold is drawn from the settled non-user pool on every surface, through
`reference_readings`. The **ranking** (`Bigger than N%`) keeps its own gated pool:
ranking and thresholding answer different questions, and only the threshold has to
match across surfaces, because the push acts on it.

Residual, accepted and recorded: at a reading exactly on the threshold, `Bigger than`
can read 13% or 15% rather than exactly 15%, because it is ranked against the other
pool. Removing that would mean either dropping the scheduled gate the product owner
agreed in SP-C.5, or narrowing ANALYZE's episode analysis from 265 readings to 99.
Neither is worth a two-point wobble on a line that is not an action threshold.

### 24.5 A premium is not a deep discount

Found while wiring the above. `evaluate_push` compared `abs(current_gap)` against the
threshold, so a sustained premium regime would have fired a message headed
**DEEP DISCOUNT** on a market trading *above* fair value. UPDATE had the mirror of
the same bug through its signed `deep_at`.

Latent, not live: all 437 readings on record are discounts, maximum -0.83%, so it has
never fired. Both surfaces now require the discount side. Re-arming is left
sign-blind, so a flip to premium re-arms the gate rather than holding it closed --
the fail-open rule from SP-C.12.

The `Cheap zone` branch in UPDATE, which handled a positive `deep_at`, is removed. It
became unreachable when the threshold became a size, and a premium market needs the
sell-side mirror, which is deliberately deferred rather than half-implied.

### 24.6 Rounding lifted the level above its own source reading

Found by `kpi_sp_c6.test_17` failing during this change, not by inspection.

Gaps are computed from prices and land on values like `8.999999999999996`. Rounding
the resolved threshold to 4 decimals produced `9.0`, and `abs(gap) >= threshold` then
excluded the very readings the threshold was drawn from. A deep zone containing eight
readings measured **zero** episodes.

`deep_discount_threshold` returns unrounded, and `fire_at` / `rearm_at` are no longer
rounded either -- they are compared against readings. `band_pp` and `noise_pp` stay
rounded; they are only displayed. Everything formats to two decimals at render.

Pre-existing and now also removed: `evaluate_push` compared against a rounded
`fire_at` while `resolve_deep_zone` compared against an unrounded one, so ANALYZE's
`Right now: inside it` and the push could disagree at the boundary. The magnitude was
5e-5 pp. The class is the same one this whole section is about.

### 24.7 The KPI runner crashed while reporting a failure

`kpi/run_all.py` forces UTF-8 on the child process but printed the captured failure
report through the parent console, which is cp1252 on Windows. The first failing
suite that contained an emoji raised `UnicodeEncodeError` **after** the summary line,
so the run named the failing file and then died before saying what the failure was.

It now writes the report to `sys.stdout.buffer` as UTF-8 bytes with `errors="replace"`.
This is why it took a stash-and-rerun to find out what had broken.

### 24.8 Verification

```text
all three surfaces, live production, 2026-09-21
  shared resolver    3.70%
  ANALYZE deep zone  3.70%
  push fire_at       3.70%   rearm_at 2.93%
  scheduled-only pool n=99 -> threshold unchanged at 3.70%
  gap -4.50% -> fire=True  reason=FIRED
  gap +4.50% -> fire=False reason=NOT_A_DISCOUNT

UPDATE, rendered live
  Bigger than      19% of the last 30 days
  Deep discount    If 3.70% or more  (30D)

KPI suite 25/25 files. kpi_sp_c4 50 -> 53, kpi_sp_c6 30 -> 33.
```

### 24.9 Open, not closed by this change

- `Bigger than N%` and the threshold rank against different pools (24.4). Bounded at
  roughly two percentile points, accepted deliberately.
- A sustained premium regime has no surface. The sell-side mirror of the push stays
  deferred until the buy-side trigger has proved itself.
- UPDATE renders `If 3.70% or more`, ANALYZE renders `3.70% or more`. Same statement,
  two renderings. The approved UPDATE wording is kept; the substantive defect was the
  number, and that is now one number.
