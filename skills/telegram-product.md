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
→ final decision + where it sits in its own range
→ the headline figures (bubble, position, momentum, structure, trend)
→ market table
→ price and bubble dynamics
→ market structure
→ platforms
→ timestamp
```

Keep detailed raw platform evidence near the bottom.

## Decision section

The decision leads the message. A reader deciding whether to act should not have to
pass several hundred characters of detail to find the answer.

Expose, in this order:

- final decision, first line
- where the reading sits in its own recent range
- candidate decision **only when it differs from final**
- momentum and structure, in the block carrying the headline figures

A trailing block repeating valuation, momentum, structure, conflict, candidate and
final was removed in SP-C. It duplicated everything the message already stated
earlier, and valuation in particular carried no information: it read CHEAP on 204 of
204 recorded states because the fixed threshold sat outside the entire distribution.

**Candidate and final must remain distinguishable**, but showing both on every
message when they agree is noise. Surface the candidate when it disagrees, which is
exactly when the confirmation rule has done something worth knowing. In production
81 of 205 states carried a BUY candidate against a WAIT final, so this is not a rare
case.

**Alert rule, unchanged:** external BUY/SELL alerts are driven only by the
deterministic `final_decision`. A `Candidate: BUY` with `Final: WAIT` is not a BUY
alert.

## Relative position

Where a reading sits in its own recent distribution is reported as a rank out of 100,
not as a z-score. The bubble distribution is left-skewed, so a long tail of deep
discounts inflates the standard deviation and a z-score will describe a reading at 76
of 100 as normal. Rank survives skew.

Wording is graduated rather than three-valued. Describing anything from the 40th to
the 80th percentile as "middle" overstates the case.

Always show confidence when it is LOW. A position without the amount of history
behind it invites more trust than it has earned.

## Formatting rules

- Exactly one application header per message.
- Do not duplicate `GOLDPremium:`.
- Do not recompute market facts in presentation code.
- Preserve transport failure isolation.
- Formatting must never alter analytical calculations.
- Prefer deterministic plain-language labels over unexplained scores.
