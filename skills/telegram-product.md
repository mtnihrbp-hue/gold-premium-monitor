# Telegram Product Skill

## Purpose

Treat Telegram as the primary user-facing cockpit of the monitor.

The analytical engine lives in code. Telegram presents the state and provides navigation into deeper analysis.

## Navigation model

The bot currently has a manual `Update` flow.

The design must remain ready for future commands/buttons such as:

- Update
- Analysis
- Sentiment
- History
- Risk
- KPI/Health

Do not put every analytical detail into the main update message. Future commands should provide deeper inspection.

## Main message hierarchy

Prefer:

```text
header
→ market
→ decision/state
→ reason
→ trends
→ momentum
→ market structure
→ input directions
→ platforms
→ timestamp
```

Keep the detailed platform table near the bottom. It is raw evidence and operational inspection data.

## Market section

Input directions belong under MARKET when they describe the current state of XAU/USD and USD/IRR.

Avoid a separate top-level section when it merely repeats market inputs.

## Decision section

Expose:

- valuation
- momentum
- structure
- conflict
- candidate decision
- final decision
- reason

Make Candidate vs Final understandable.

Example:

```text
Candidate: BUY
Final: WAIT

Reason:
BUY conditions are present, but the hysteresis/transition state has not confirmed a new BUY alert.
```

Do not hide meaningful disagreement between state and final decision.

## Human readability

Use plain analytical words:

- CHEAP
- FAIR
- EXPENSIVE
- IMPROVING
- WEAKENING
- NEUTRAL
- DISCOUNT WIDENING
- DISCOUNT NARROWING
- FEAR
- NORMAL
- PANIC

Avoid unexplained numeric scores as the primary interface.

Do not use decorative bar charts unless explicitly approved.

## Momentum candle

The candle/range view is useful when enough historical observations exist.

Do not make the candle disappear merely because the current day has no observations if a valid recent completed window exists.

A future candle representation may use compact ASCII because it can communicate range more efficiently than prose.

However:

- it must be deterministic
- it must be labeled
- it must not imply precision beyond the data
- it must have a plain-text fallback
- insufficient history must be shown explicitly

Example concept:

```text
Discount range
-4.42% ─────●──── -3.69%
             current
```

Do not implement this representation merely as cosmetic work. Add it only when the underlying candle/range semantics are clearly defined and tested.

## Formatting rules

- Exactly one application header per message.
- Do not duplicate `GOLDPremium:`.
- Do not duplicate market facts across multiple sections without a reason.
- Preserve transport failure isolation.
- Telegram formatting must never change analytical calculations.

## Future commands

When commands are added, separate:

```text
Update
= latest observation

Analysis
= deeper interpretation

Sentiment
= external/contextual intelligence

History
= historical evidence

Health/KPI
= system verification
```

Do not make one command responsible for every purpose.
