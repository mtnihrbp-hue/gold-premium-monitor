# Telegram Product Skill

## Purpose

Telegram is the user-facing cockpit. Analytical truth lives in the quantitative, intelligence, and decision layers; Telegram presents it and provides read-only navigation.

## Current command model

Implemented (`PROJECT_MEMORY.md` section 3):

- `/Update` — live, user-triggered market snapshot
- `/Analyze` — what the record shows, read-only over persisted state; says so when the database is
  out of reach
- `/Direction` — the trend, buy now or wait, support and resistance, what to watch, gold demand

- `Status` — the latest run, and the service line the last scheduled run left (database, world gold,
  dollar, platforms; `SP_D_HANDOFF.md` 37.15)

Scheduled, not commanded:
- SERVICE, when a service stops or comes back, once two runs agree;
- the room's 21:00 report, with the day's chart as a photo;
- the room's trades;
- the BUY signal;
- the deep-discount push, parked until Neon returns.

The daily recap is parked.

SP-C's plan named `/Technical`, `/History`, `/News`, `/Radar` and `/Health`. None was built, and none is
a product contract. Do not add a command unless the owner asks for it and `PROJECT_MEMORY.md` records
it. The advisor (C, `SP_D_HANDOFF.md` 38.4) is the proposed next surface.

## Live vs Analysis

```text
/Update
= current user-triggered observation

/Analysis and future read models
= persisted system-generated analytical state
```

A user request must not silently become an Analysis Wing execution or historical learning observation.

## Main message hierarchy

UPDATE, as of SP-C.8:

```text
header
→ the gap, its side, and the basis it rests on
→ its movement and what that means for a buyer
→ where it ranks in its own recent range
→ market table
→ platforms
→ timestamp
```

Keep detailed raw platform evidence near the bottom.

PRICE & BUBBLE DYNAMICS and MARKET STRUCTURE were dissolved in SP-C.5. Every figure
they carried is stated once in the headline block, in the same vocabulary as the rest
of the message; the sections restated them in a second, sign-based vocabulary, which
is what made the two halves of the message appear to disagree.

## Decision section

**UPDATE carries no decision.** Removed in SP-C.8. The chain that produces one --
valuation, premium direction, momentum, structure, conflict, hysteresis -- is not in
that message, so the word alone asked to be trusted rather than understood. It
belongs in ANALYZE beside its reasoning, and appears there only once the engine has
decided often enough to be scored.

`final_decision` is unchanged as the sole alert authority and is still computed and
stored on every run. Only its display moved.

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

**The BUY message** (`alerts/telegram_signal.py`, approved 2026-09-29) replaced the
SP-A alert layout for BUY. The old layout printed the single-cheapest `Premium`, which
contradicted UPDATE's three-cheapest basis, and it printed internal labels. The new
message:

- reuses UPDATE's helpers, so `Discount`, `Bigger than` and `Deep discount` carry the
  same numbers as UPDATE;
- says why (valuation, momentum, platforms) and what was checked (second platform,
  dollar, world gold);
- ends with "Decision support, not an instruction to trade."

A CHEAP valuation is shown as **"heavily discounted"**, never "cheap": a large discount
is not a cheap market (owner, 2026-09-29). SELL keeps the old layout until a SELL
message is designed.

## Relative position

Where a reading sits in its own recent distribution is reported as a rank, not as a
z-score.

The original justification was skew: a long tail of deep discounts inflated the
standard deviation, so a z-score described a reading at 76 of 100 as normal. That tail
was the single cheapest platform, and the trimmed basis introduced in SP-C.5 removed
it -- measured Pearson skew on the current basis is -0.09, near-symmetric, and p85
agrees with median + 1 SD to within 0.02 pp.

The conclusion stands on robustness rather than on present skew: a rank cannot be
wrong about frequency, it answers "how often" directly, and it survives the
distribution skewing again.

Wording is graduated rather than three-valued. Describing anything from the 40th to
the 80th percentile as "middle" overstates the case.

### A level printed to a reader is the level the system acts on

Binding. `Deep discount` named 3.29% in UPDATE and 3.70% in ANALYZE and the push on
2026-09-21, because each surface chose its own rank. A reader at 3.40% was told they
were in deep discount and received no push.

The level is resolved once, by `bubble_position.deep_discount_threshold`, over one
pool, and every surface that prints or acts on it calls that function. A new surface
needing the same concept calls the same function. It does not declare a constant of
the same value: three constants that agree are three definitions, not one.

Where a rank is genuinely a different question -- `Bigger than X%` ranks the current
reading, it does not gate anything -- it may use its own pool, and that difference is
recorded in `SP_C_HANDOFF.md` section 24.4 rather than left to be rediscovered.

A label that asserts a direction ("discount") is shown only when the reading is on
that side. The threshold is a size, and a size alone cannot carry the claim.

Confidence is **not** surfaced as a label. Withheld by product decision in SP-C.5
section 15.6: the window the reading is ranked against is stated directly, and a bare
"LOW" beside it was noise a reader could not act on. Sample size and sampling quality
appear in ANALYZE's DATA section instead, which is where a reader can weigh them.

## Locked layouts

An agreed layout is locked. These are changed only with the owner's permission, after a full preview:
- UPDATE and Direction v7;
- the room's report, with the GOLD FUNDS block (`SP_D_HANDOFF.md` 47);
- the evening message (47): the box with the road out of each side, the funds' block, and the expected
  return of the database;
- the chart: support and resistance with the patterns, "both worlds". The closest resistance line is
  solid and the longer, most-touched one thin and dashed (option C, 49). The patterns shown are only the
  ones that worked on 18K (`patterns.shown`, 49.2).

The advisor's lines locked on 10-17 and 10-18 wait for it to be built (47.4, 49.4).

## Wording (owner)

The readers are Persian and the text is English, so plain words beat idioms. The goal: "the user,
once he/she reads the msg, gets informed, and can make a decision."

- **The discount** "increased" or "decreased", never "widening", "deepening" or "shrinking". It is
  shown as a positive number below fair value; a premium has its own words, above fair value.
- **Plain words:** "typical" rather than "median"; "heavily discounted" rather than "cheap" for the
  discount's size.
- **Never "dear", "dearer" or "dearest"**, in messages, docs or chat: "expensive", "more expensive",
  "most expensive". For prices going down: "cheaper" or "down trend" (owner, 2026-10-16, restating an
  earlier agreement).
- **Every change says against what:** the last scheduled run, today's first reading, 7 days. Seven days
  is the system's convention for averages a reader sees.
- **A figure with a record shows the record** ("14 of 19 flags since 2014"), not a confidence word. A
  statistic without enough data stays hidden until it holds.
- **The phone:** readable at its width, with no wide tables.
- **No admin detail:** sampling notes and data health go to the docs or an admin report, not the
  reader.
- **No generalising** beyond the evidence without saying so.

## Telegram's limits

- A text message holds 4,096 characters.
- A photo's caption holds 1,024: `telegram_paper.send_paper_report` sends the chart with the report
  as its caption, or the text alone when the caption is too long or the photo fails.
- Check a new message's length against its limit at its longest, not on today's values.

## Formatting rules

- Exactly one application header per message.
- Do not duplicate `GOLDPremium:`.
- Do not recompute market facts in presentation code.
- Preserve transport failure isolation.
- Formatting must never alter analytical calculations.
- Prefer deterministic plain-language labels over unexplained scores.
