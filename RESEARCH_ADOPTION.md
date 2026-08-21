# Research Sources — Adoption / Defer Matrix

These repositories are research references, not architectural authorities.

| Source | Concepts adopted / useful | Explicitly deferred / out of scope |
|---|---|---|
| `3aLaee/xauusd-trading-bot` | MACD/price-action concepts as candidate analytical features; technical trigger ideas subject to walk-forward validation | MT5, broker execution, order management, position sizing, automated trading |
| `JonusNattapong/Ai-XAUUSD-Trading` | Market-regime detection ideas; technical feature engineering; adaptive/ensemble concepts as research candidates | Reinforcement learning, live trading stack, broker/execution infrastructure |
| `michael-chow-arch/goldfxgraph` | Historical relationship visualization and analytical graph ideas | UI architecture copied into core analytical engine |
| `vctb12/GoldTickerLive` | Live gold-data/visualization and source-integration ideas where compatible with existing collectors and provenance rules | Copying application architecture or replacing project data contracts |

## Project-side implementations influenced by this research

Already implemented in SP-B include:

- deterministic regime detection and hysteresis
- MA/SMA/EMA feature infrastructure
- premium momentum / acceleration / persistence features
- volatility and range-expansion features
- XAU/USD and USD/IRR relationship features
- platform structure / consensus features
- analytical read model and downstream consumer contract
- historical outcome evaluation
- upcoming platform candle / price-action evaluation

## C.14 research position

Research is now converging into a testable extended forecast feature family:

```text
C.8 BASE FEATURES
+
PLATFORM CANDLES
+
PRICE ACTION
+
MACD-STYLE MOMENTUM (only when non-redundant)
+
REGIME / VOLATILITY / ECONOMIC CONTEXT
```

These are candidate features, not assumed predictors.

The extended family must demonstrate incremental out-of-sample value against the C.8 baseline before adoption into a production forecast model.

## Deferred items

The following remain explicitly deferred:

- MT5 / broker execution
- reinforcement-learning trading agents
- autonomous trade execution
- LLM self-modifying forecast logic
- opaque black-box prediction pipelines
- direct user-feedback-to-model online learning
- automatic BUY/SELL generation from forecast output

## Human-feedback research adoption

The project does not copy a single existing repository implementation. Instead, it adopts these principles from forecast-evaluation and human-review research:

- objective forecast outcome must be evaluated independently of human opinion
- probability calibration matters in addition to directional accuracy
- performance should be segmented by horizon/regime/confidence where data supports it
- human review should be a separate meta-data stream
- human feedback is evidence first, not immediate model training
- abstention is valid when evidence is insufficient

The frontend remains two-wing:

```text
LIVE WING
/Update

ANALYSIS WING
/Analyze
/Forecast
```

Human forecast review is a Telegram interaction within the Analysis experience, not a third frontend wing.
