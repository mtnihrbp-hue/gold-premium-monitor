# C14C Implementation Reference

Branch: `SP-B`

Status: **COMPLETE — 21/21 KPI PASS**

C14C is the verified Adaptive Intelligence Foundation around C14B. It is a downstream diagnostic/analytical layer. It is not an autonomous learning or trading layer.

## 1. Architecture position

```text
Forecast Engine
      ↓
Forecast Result
      ↓
Outcome Evaluation
      ↓
C14C Intelligence Analysis
```

C14C consumes existing analytical and forecast artifacts. It does not modify the C14B forecast contract or the deterministic decision engine.

## 2. Verified capabilities

C14C KPI coverage includes:

- C14B contract preservation
- deterministic forecast error classification
- direction error classification
- confidence error classification
- regime error classification
- timing error classification
- data-quality error classification
- stable error-category contract
- insufficient-data regime handling
- normal-regime analysis
- regime calibration analysis
- feature reliability analysis
- feature separation
- structural event-interpreter abstraction
- event-interpreter stub classification
- event-interpreter stub summarization
- single-forecast analysis
- historical batch analysis
- decision-authority protection
- future-leakage protection
- compile validation

KPI result:

```text
21/21 PASS
```

## 3. Error intelligence

Forecast failures are classified analytically rather than persisted as a new database field.

Current categories:

```text
DIRECTION_ERROR
CONFIDENCE_ERROR
TIMING_ERROR
REGIME_ERROR
DATA_QUALITY_ERROR
```

Classification is diagnostic. It does not automatically modify the forecasting model.

## 4. Regime intelligence

C14C reuses the existing regime system rather than creating a second regime engine.

Regime is used for:

- performance segmentation
- calibration analysis
- reliability analysis
- contextual investigation

Regime does not override forecasts and does not issue BUY/WAIT/SELL decisions.

## 5. Feature reliability

C14C measures historical feature usefulness and separation.

It may identify observations such as:

```text
feature reliability differs by regime
```

It does not automatically change feature weights, thresholds, or model configuration.

## 6. Forecast memory boundary

C14C currently reconstructs historical forecast context from existing persisted analytical artifacts.

It does not introduce a `forecast_history` table.

This is intentional. Immutable forecast-event persistence is deferred until forecast lifecycle, production volume, and audit requirements justify a dedicated persistence contract.

Historical reconstruction must not be represented as immutable original forecast storage.

## 7. Event intelligence boundary

C14C establishes an event-interpreter abstraction/stub for future event intelligence.

There is no production LLM integration in C14C.

Future architecture may evolve toward:

```text
News/Event
    ↓
Structured Event Interpretation
    ↓
Historical Event Memory
    ↓
Observed Market Response
    ↓
Forecast Context
```

An event interpretation remains evidence/hypothesis until validated against market outcomes.

## 8. C14C supporting work — operational news ingestion

The C14C foundation initially contained the news event schema, RSS collector, deterministic event classifier, persistence functions, and downstream snapshot consumer, but the runtime path did not invoke them. This left `news_events` empty despite the underlying components existing.

The surgical supporting-work change wires the existing components without changing the C14C architecture:

```text
config.news
    ↓
collector.news.ingest
    ↓
RSS collection / normalization
    ↓
event_classifier
    ↓
existing deduplication
    ↓
repository.save_news_event
    ↓
news_events
    ↓
snapshot_builder news context
```

Implementation:

- `src/collector/news/ingest.py` is a thin orchestration layer.
- `src/main.py` invokes ingestion before `build_analysis_snapshot()`.
- Source failures are isolated; news ingestion is non-blocking to the market pipeline.
- Existing deduplication is reused rather than introducing another persistence mechanism.
- `news.enabled` and configured RSS sources are honored.
- No LLM is introduced.
- No event-impact learning or adaptive weighting is introduced.
- No forecast or decision authority is changed.
- No Neon migration is required.

This is operational plumbing, not completion of future news intelligence. It makes existing raw structured news available to downstream analytical context; it does not claim that news is predictive or that event impact has been learned.

## 9. Explicit non-goals

C14C does not implement:

- reinforcement learning
- bandit optimization
- online model training
- automatic model-weight modification
- automatic threshold tuning
- autonomous strategy modification
- LLM market-price calculation
- LLM BUY/SELL authority
- broker execution
- decision-engine replacement
- empirical event-impact learning

## 10. Neon impact

C14C and its operational news-ingestion supporting work require **no Neon migration**.

Existing production structures are sufficient:

```text
analysis_snapshots
outcome_evaluations
platform_candles
news_events
```

Live Neon reconciliation confirmed the expected production structures and preserved historical data. No database mutation was performed for C14C or the news-ingestion wiring.

Future schema changes remain subject to the established inspection → compare → migration → verify → document workflow.

## 11. Regression boundary

C14C explicitly protects:

```text
C14B forecast contract
future-leakage boundary
decision authority boundary
```

The deterministic decision engine remains the sole BUY/WAIT/SELL authority.

The news-ingestion supporting work must also remain failure-isolated: an unavailable RSS source must not prevent market collection, calculation, snapshot creation, or alert delivery.

## 12. Deferred extensions

The following remain future work, not C14C completion criteria:

- immutable forecast persistence
- human review UI/persistence
- news provenance beyond the existing event/dedup contract
- empirical event-impact measurement
- weekly administrative intelligence reporting
- controlled adaptive weighting
- LLM event interpretation
- reinforcement learning / bandit optimization
