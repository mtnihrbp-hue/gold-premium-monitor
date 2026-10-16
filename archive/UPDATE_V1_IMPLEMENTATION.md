# UPDATE v1 — Surgical Implementation Record

Status: implemented on `main` as a transitional/pre-C15 boundary correction.

## Scope

UPDATE is the fast, user-triggered operational wing. ANALYZE is the scheduled historical/analytical wing.

```text
User /update
    ↓
Collect current market
    ↓
Validate
    ↓
Persist canonical observations
    ↓
Calculate current SP-A state
    ↓
Resolve RUN / DAY baselines
    ↓
Persist current market snapshot
    ↓
Telegram UPDATE v1
```

Scheduled ANALYZE continues to own news ingestion and analysis-snapshot construction.

## Baselines

Updated 2026-09-14. The transitional definitions below were replaced once the Analyze
wing began running on a real cadence, exactly as this document anticipated.

### RUN

Latest **scheduled** `market_snapshots` record available before the current UPDATE
snapshot is persisted.

Previously this was the latest record of any kind. On the UPDATE path that is the
user's own previous request, so RUN measured the interval between two clicks rather
than market movement, which is why it routinely displayed `+0.00%`.
`PROJECT_MEMORY.md` already required that accumulated user-triggered calls not serve
as a baseline, but no column existed to enforce it until the SP-C.1 migration added
`collection_mode`.

### DAY

First **scheduled** `market_snapshots` record of the current calendar day.

### Fallback

Both fall back to a record of any collection mode when no scheduled record exists, so
history predating the migration still resolves a baseline rather than none.

## UPDATE data model

Restructured 2026-09-14. The decision now leads the message; it previously sat at the
foot, below several hundred characters of detail, so a reader deciding whether to act
had to reach the end to find the answer.

Section order:

```text
verdict          final decision, where the reading sits in its own range,
                 and the candidate only when it differs from final
THE NUMBER       bubble, position out of 100, the favourable boundary,
                 confidence when LOW, momentum, structure, bubble moving averages,
                 market low, fair value
MARKET           XAU/USD, USD/IRR, Fair, Platform, Bubble
                 against Now / Run / Day / 7D, plus lowest, highest and spread
DYNAMICS         local price direction and change, gap direction and size,
                 bubble candle, plain-language interpretation
PLATFORMS        per-platform price, Run delta, change against Day
timestamp
```

Two sections were removed rather than shortened. `CURRENT DECISION` repeated
valuation, momentum, structure, conflict, candidate and final, all of which the
message now states earlier; valuation in particular read CHEAP on 204 of 204 recorded
states because the fixed threshold sat outside the entire distribution.
`MARKET STRUCTURE` repeated the spread and the consensus count, and its only unique
content — which platform is highest and lowest — moved beside those values in the
market section.

### Width constraint

Telegram renders `<pre>` blocks in a monospace font that fits roughly 32 characters on
a phone. Both tables are fixed at **33 characters on every row**, header and separator
included. Cell content that overflows its column shears the whole table, which is what
made the earlier 48-character layout unreadable.

To hold four comparison columns inside that budget the delta cells carry no unit
suffix; a six-character cell cannot hold `+0.04%` and still leave a gutter, and columns
that touch cannot be read. Units are stated once in the footnote beneath the table.

### Relative position

The message reports where the bubble sits in its own recent distribution as a rank out
of 100, sourced from `src/analysis/bubble_position.py`. Rank is used rather than a
z-score because the distribution is left-skewed: the long tail of deep discounts
inflates the standard deviation, so a z-score describes a reading at 84 of 100 as
normal. Confidence is always shown when LOW.

Price pace and bubble pace remain `N/A` until sufficient empirical history exists to calibrate defensible thresholds.

## Important analytical correction

Local-price acceleration is calculated from the arithmetic platform average of canonical market snapshots. It is intentionally not calculated from the raw `REP_IRAN_GOLD` observation stream because that stream contains multiple platform observations and Goldika BUY/SELL observations. Treating those records as consecutive prices can manufacture false acceleration from source ordering or bid/ask spread.

## Threshold status

| Primitive | Current rule | Calibration |
|---|---|---|
| Bubble movement | 0.05 percentage-point dead-band | Existing project convention; not empirically calibrated |
| Price direction | 0.01% relative dead-band | Placeholder; not calibrated |
| Price acceleration | 0.01% relative dead-band | Placeholder; not calibrated |
| Price pace | `N/A` | Deferred |
| Bubble pace | `N/A` | Deferred |

## Architecture boundary

UPDATE must not execute:

- news ingestion
- full C.3–C.10 analytical pipeline
- analysis snapshot construction
- forecast generation
- outcome evaluation

Those operations remain owned by the scheduled ANALYZE path.

## Neon

No schema migration is required for UPDATE v1.

## Safety / reversibility

The change is a surgical presentation/execution-boundary correction on `main`. Existing legacy Telegram formatting remains available as a fallback. SP-A decision logic and the database schema were not modified.

## Validation status

Repository-level inspection identified and corrected the initial KIMI integration defects before validation:

1. `src/main.py` had been concatenated with a duplicate/legacy file body and was syntactically invalid.
2. The proposed main path referenced a non-existent `save_price_observations()` repository function and wrong collector module names.
3. The initial acceleration implementation used raw mixed-platform observations, which could interpret source ordering or Goldika BUY/SELL spread as temporal acceleration.
4. The UPDATE formatter was isolated into `src/alerts/telegram_update_v1.py` so the legacy Telegram module remains intact.
5. The existing alert, daily recap, persistence, and scheduled Analyze paths were restored rather than silently removed.

The full KPI suite still requires execution in the project runtime after this surgical repair. No claim of KPI pass is made here until that execution is observed.
