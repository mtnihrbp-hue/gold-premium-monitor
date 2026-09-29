# Market Analyst Skill

## Purpose

Maintain the analytical philosophy of Gold Premium Monitor.

This system supports decisions in the Iranian physical gold market. It is not a generic stock-trading bot.

## Core distinction

```text
Quantitative engine
= measures the market

Intelligence layer
= interprets external context

Decision engine
= determines what action the evidence supports
```

Never collapse these layers.

## Mandatory distinctions

```text
CHEAP ≠ BUY

VALUATION ≠ MOMENTUM

CANDIDATE DECISION ≠ FINAL DECISION

ABSOLUTE PREMIUM ≠ PREMIUM DIRECTION

NEWS INTERPRETATION ≠ MARKET DATA

LLM INTERPRETATION ≠ QUANTITATIVE CALCULATION
```

## Premium language

For a negative premium:

- `DISCOUNT WIDENING` = current premium is becoming more negative
- `DISCOUNT NARROWING` = current premium is becoming less negative
- `DISCOUNT STABLE` = materially unchanged

For a positive premium:

- `PREMIUM WIDENING`
- `PREMIUM NARROWING`
- `PREMIUM STABLE`

Do not use ambiguous phrases such as `Premium Expanding` or `Discount Deepening` in new analytical output.

### Internal versus user-facing

The labels above are **internal analytical vocabulary**. They are correct in calculation
code, state values, evidence packages, and persisted fields.

They must **not** be surfaced raw in Telegram output. `C14_HANDOFF.md`,
`C14C_HANDOFF.md`, `RESEARCH_ADOPTION.md` and `.project_state.json` all require
user-facing text to prefer observable relationships:

```text
Iranian gold is increasing more slowly than its external drivers.
Iranian gold is catching up faster than its external drivers.
Local prices are lagging the global/FX move.
```

Earlier revisions of this skill did not draw that distinction, which produced UPDATE
messages carrying a compliant label and a non-compliant sentence describing the same
movement. Analytical layers use the labels; presentation translates them.

## SP-A baseline

The deterministic baseline is:

```text
Valuation
→ Premium Direction
→ Momentum
→ Market Structure
→ Conflict
→ Candidate Decision
→ Confirmation
→ Hysteresis
→ Final Decision
```

Confirmation was added on 2026-09-29, with the owner's approval, after the first live
BUY rested on one stale platform quote (`SP_C_HANDOFF.md` §37, §38). It does not change
the matrix. It checks the evidence under a BUY/SELL candidate: a second platform
confirms a discount, the dollar is today's, and world gold is live. It fails closed.
A deep discount on one platform is not a market-wide opportunity.

The conflict matrix is explicit and testable. Do not replace it with a weighted score without explicit approval.

## Interpretation

A deep discount is evidence of valuation, not proof of a buying opportunity.

A weakening discount can justify WAIT even when the market is very cheap.

A BUY/SELL decision should be explainable in terms of observable evidence.

## Future intelligence

SP-B may add:

- news events
- macro context
- support/resistance
- historical analogues
- market mood
- market regime

These must inform the deterministic baseline rather than erase it.

## Future LLM use

Use the LLM primarily to interpret external information and explain context.

Do not let it invent prices, fair value, support, resistance, historical outcomes, or quantitative confidence.

## Historical learning

When historical evidence is introduced, always expose sample size and data sufficiency.

`INSUFFICIENT DATA` is a valid result.

Do not manufacture confidence from a small sample.
