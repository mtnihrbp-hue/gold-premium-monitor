# PRE-SP-C.14C — CLOSED-LOOP INTELLIGENCE, HUMAN REVIEW & NEWS IMPACT

Status: **PLANNING**
Branch: `SP-B`

C.14C is the next phase after verified C.14A and C.14B.

## 1. Objective

C.14C creates the audit/learning loop around the forecast system without allowing uncontrolled online learning.

```text
FORECAST
   ↓
OBSERVE
   ↓
OBJECTIVELY RESOLVE
   ↓
OPTIONAL HUMAN REVIEW
   ↓
AUDIT
   ↓
WEEKLY ADMIN INTELLIGENCE
   ↓
CONTROLLED MODEL / FEATURE REVIEW
```

The frontend remains two-wing only:

```text
LIVE WING
/Update

ANALYSIS WING
/Analyze
/Forecast
```

Human review lives inside the Analysis experience and is not a third frontend wing.

## 2. Forecast resolution

Every forecast should preserve:

- forecast ID / lineage
- snapshot ID
- forecast timestamp
- target market
- horizon
- direction
- probability vector
- model version
- feature schema version
- regime
- reference market values

Lifecycle:

```text
GENERATED
→ PENDING
→ ELIGIBLE_FOR_REVIEW
→ OBJECTIVELY_EVALUATED
→ USER_REVIEWED (optional)
```

Keep separate clocks:

```text
forecast_time
market_outcome_time
feedback_time
```

Review eligibility follows actual observation availability and forecast horizon. Do not use a blind fixed 48-hour rule.

## 3. Objective outcome vs human feedback

The system computes objective outcome from market data first.

Human review is separate metadata.

```text
OBJECTIVE OUTCOME
≠
HUMAN ASSESSMENT
```

Suggested progressive Telegram review:

```text
Previous forecast review
[ Very useful ]
[ Mostly useful ]
[ Direction right, timing wrong ]
[ Direction wrong ]
[ Hard to judge ]
```

Optional second layer:

```text
[ Timing ] [ USD/IRR ] [ World Gold ] [ Local Market ]
[ Premium ] [ Price Action ] [ News ] [ Hard to judge ]
```

Do not turn this into a questionnaire.

Do not use raw human answers as immediate labels.

Do not update model weights online from user input.

## 4. Forecast quality dimensions

Keep distinct:

1. Objective directional accuracy
2. Probability calibration
3. Human perceived usefulness

Do not compress them into one opaque score.

## 5. News/Event Intelligence

C.14C should extend the existing `news_events` infrastructure into empirical event-impact analysis.

Do not reduce news to generic sentiment.

Preferred flow:

```text
NEWS EVENT
→ source lineage / provenance
→ event classification
→ expected impact hypothesis
→ market observation window
→ observed response
→ abnormal/local response
→ historical event profile
→ empirical source/event weighting
```

Existing event metadata is useful:

```text
event_type
topic
relevance
expected_usd_direction
expected_gold_direction
expected_duration
impact
confidence
classification_method
```

A classification is a hypothesis. It is not market truth.

## 6. Event provenance and deduplication

Do not count reposts as independent confirmations.

Distinguish:

```text
ORIGINAL_EVENT
REPOST
COMMENTARY
REACTION
```

Preserve original source lineage where available.

A single underlying event repeated by ten sources must not become ten independent predictive signals.

## 7. Event-impact measurement

For meaningful events, evaluate windows such as:

```text
T-30m
T0
T+30m
T+60m
T+2h
T+6h
T+24h
```

Use actual available observation frequency and market calendars; do not assume every window exists.

Measure:

- raw movement
- relative movement
- response speed
- response magnitude
- persistence
- reversal
- regime dependence
- local-market response

Where feasible, distinguish:

```text
OBSERVED LOCAL MOVE
-
EXPECTED MOVE FROM EXTERNAL DRIVERS
=
ABNORMAL / INCREMENTAL LOCAL RESPONSE
```

Do not claim causality without sufficient evidence.

## 8. Event duration / decay

Different event families may have different persistence.

The system should eventually estimate empirical impact duration rather than hard-code one universal news window.

Conceptually:

```text
immediate shock
→ decays
```

or:

```text
slow policy event
→ persists longer
```

These are hypotheses to be measured.

## 9. News weighting

Do not start with arbitrary source weights.

Do not hard-code:

```text
source A = 0.8
source B = 0.5
```

Instead accumulate historical event outcomes and estimate whether source/event characteristics add incremental information.

Candidate future features:

```text
news_expected_direction
news_confidence
historical_event_effect
historical_source_reliability
event_duration_profile
event_regime_interaction
cross-source-confirmation
```

News weighting must be earned empirically.

## 10. Regime-conditioned audit

Reuse the existing regime detector.

Do not create another regime engine.

Evaluate forecast/news behavior by regime where enough data exists.

A useful outcome may be:

```text
forecast works in stable trends
forecast weakens during transitions
news response is stronger during high-volatility regimes
```

Regime remains context/segmentation, never an override and never a BUY/SELL authority.

## 11. Weekly admin intelligence

Produce a structured weekly report rather than a headline accuracy number.

Suggested sections:

```text
FORECASTS ISSUED
FORECASTS RESOLVED
DIRECTIONAL PERFORMANCE
PROBABILITY CALIBRATION
HUMAN REVIEW SUMMARY
MODEL/HUMAN DISAGREEMENT
NEWS EVENTS ANALYZED
STRONGEST EVENT FAMILIES
WEAKEST EVENT FAMILIES
REGIME-SPECIFIC WEAKNESSES
DATA QUALITY ISSUES
RECOMMENDED INVESTIGATIONS
```

The report should identify evidence-backed areas for surgical investigation, not automatically modify production logic.

## 12. Fail-safe rules

```text
missing market observation
→ do not fabricate
→ INSUFFICIENT_DATA / unresolved

missing news context
→ forecast may continue without news
→ explicit provenance / degraded context

ambiguous event linkage
→ preserve ambiguity
→ do not force a causal attribution

insufficient event sample
→ INSUFFICIENT_DATA
```

## 13. Neon impact

C.14C may require schema changes because forecast lineage, human review, and event-impact persistence may become valuable audit artifacts.

Do not change Neon schema during initial design silently.

Before any migration, provide:

- table proposal
- field proposal
- uniqueness/idempotency rule
- indexes
- retention implications
- backward compatibility
- migration SQL

Then test on Neon temporary branch and verify production.

## 14. Terminology refactor

Avoid exposing:

```text
DISCOUNT WIDENING
DISCOUNT NARROWING
```

Prefer observable market language:

```text
Iranian gold is increasing more slowly than its external drivers.
Iranian gold is catching up faster than its external drivers.
Local prices are lagging the global/FX move.
Local prices are moving faster than the external drivers.
```

Internal analytical mathematics may use premium/discount, relative rate of change, velocity, and acceleration.

Do not infer a cause merely from the observed relationship.

## 15. Non-goals

C.14C must NOT introduce:

- autonomous online retraining
- uncontrolled self-modifying models
- automatic BUY/SELL generation
- broker execution
- MT5
- reinforcement-learning execution
- LLM market-price calculation
- arbitrary news sentiment weighting

## 16. Pre-coding gate

Before coding, inspect:

```text
news_events
src/intelligence/event_classifier.py
src/collector/news/
src/analysis/outcome_evaluator.py
src/intelligence/consumer.py
C.14B forecast contract
C.14B model provenance
Telegram command routing
Neon current production schema
```

Return a compact report containing only:

```text
FORECAST RESOLUTION CONTRACT
HUMAN REVIEW CONTRACT
NEWS EVENT CONTRACT
EVENT WINDOWS
REGIME AUDIT
WEEKLY REPORT CONTRACT
NEON IMPACT
KPI PLAN
BLOCKERS
```

Maximum ~600 words.

Do not code until the contract is frozen.
