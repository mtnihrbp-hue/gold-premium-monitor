# Telegram Product Skill

## Purpose

Telegram is the user-facing cockpit. Analytical truth lives in the quantitative, intelligence, and decision layers; Telegram presents it and provides read-only navigation.

## Current command model

Implemented today:

- `/Update` — live, user-triggered market snapshot

Planned Analysis Wing read models:

- `/Technical` — deterministic technical analysis
- `/Analysis` — latest persisted analysis snapshot
- `/History` — historical context
- `/News` — structured recent news
- `/Radar` — combined read model over persisted analytical state
- `/Health` — system/data-quality status

Do not invent commands such as Sentiment or Risk as current product contracts unless `PROJECT_MEMORY.md` explicitly adds them.

## Live vs Analysis

```text
/Update
= current user-triggered observation

/Analysis and future read models
= persisted system-generated analytical state
```

A user request must not silently become an Analysis Wing execution or historical learning observation.

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

Keep detailed raw platform evidence near the bottom.

## Decision section

Expose:

- valuation
- momentum
- structure
- conflict
- candidate decision
- final decision
- reason

Candidate and final must remain visibly distinct.

**Alert rule:** external BUY/SELL alerts are driven only by the deterministic `final_decision`. A `Candidate: BUY` with `Final: WAIT` is not a BUY alert.

## Formatting rules

- Exactly one application header per message.
- Do not duplicate `GOLDPremium:`.
- Do not recompute market facts in presentation code.
- Preserve transport failure isolation.
- Formatting must never alter analytical calculations.
- Prefer deterministic plain-language labels over unexplained scores.
