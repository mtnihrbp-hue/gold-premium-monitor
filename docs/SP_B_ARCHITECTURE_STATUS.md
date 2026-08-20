# Gold Premium Monitor SP-B Architecture Status

## Current milestone

SP-B has completed PRE-SP-C.7.

Completed intelligence foundation:

- PRE-SP-C.4 — Regime intelligence and persisted analytical state
- PRE-SP-C.5 — Outcome evaluation and historical measurement
- PRE-SP-C.6 — Evidence package architecture
- PRE-SP-C.7 — Interpretation intelligence layer

## Architecture boundary

The system follows this separation:

```text
FACTS
(raw market observations)
        |
        v
EVIDENCE
(validated analytical package)
        |
        v
INTERPRETATION
(structured explanation layer)
        |
        v
DECISION
(current deterministic decision output)
        |
        v
FUTURE PREDICTION
(not implemented)
```

## Facts

Facts contain only collected observations:

- Iranian platform prices
- XAU/USD
- USD/IRR
- timestamps
- source quality
- collection provenance

Facts cannot be rewritten by intelligence or prediction components.

## Evidence

Evidence packages normalize validated analytical outputs:

- valuation
- momentum
- structure
- regime
- market relationships
- historical outcomes
- data quality
- provenance

Evidence is auditable and deterministic.

## Interpretation

Interpretation explains evidence without changing it.

It may describe:

- regime unchanged
- discount narrowing
- conflicting evidence
- uncertainty

Interpretation cannot become a replacement for facts or evidence.

## Decision

The decision layer remains separate.

BUY / WAIT / SELL outputs are controlled by decision logic only.

Evidence and interpretation provide context but do not directly issue trading decisions.

## Prediction policy

Prediction models are future components only.

They are not implemented in the current architecture.

When introduced, prediction models must not:

- modify raw observations
- alter evidence packages
- rewrite interpretation history
- bypass decision rules

## PRE-SP-C.8 direction

The next phase is Feature Intelligence Layer.

Initial scope:

- trend features
- momentum features
- volatility features
- market relationship features
- structure features

No prediction model will be introduced during PRE-SP-C.8.

The objective is deterministic, explainable feature infrastructure for future intelligence capability.
