# SP-D Handoff

SP-D was branched from `main` on 2026-09-29 (`SP_C_HANDOFF.md` section 36); its code
work opened on 2026-10-03. SP-C is closed: its handoff (`SP_C_HANDOFF.md`) keeps SP-C and
the pre-SP-D hotfixes on `main` (its sections 37-45), and everything from SP-D's first
deliverable on is recorded here (owner, 2026-10-03: "that sprint is closed, anything now
is SP-D"). Sections 1-4 were written as `SP_C_HANDOFF.md` sections 46-49 and moved here
on 2026-10-03 unchanged, apart from their numbers.

## 1. SP-D opens: Direction, the first deliverable (2026-10-03)

**Why first.** The owner, 2026-10-03: "we have enough data and history, but there is no
decision or prediction available ... are we going up, or down? whats the probability?
when we started the project the gold was around 18 now its around 26 and we are just
watching ... if i know the up trend, i will transform my rial into gold and maintain my
money value." The diagnosis is the system's own: the decision engine has a valuation leg
and a premium-momentum leg, and **nothing looks at the price trend itself**, so a +44%
move with a premium near -2% read FAIR/WAIT for weeks. The question to answer is not
BUY/SELL but "convert now, or wait for a better entry?", with the evidence for each part.
The existing C.14B forecast engine predicts the next hour's direction from two months of
hourly data and is shown nowhere: it does not answer this.

**First read of tgju's 13-year daily 18K history** (as of 2026-10-01, research):

```text
close 25.69 M toman; +37% in 60 trading days, +124% in 250
trend UPTREND (price > 50-day 22.04 M > 200-day 19.30 M, 50-day rising); RSI 75
stretch +16.6% above the 50-day average; no resistance above (record high)
support 24.43 M (-4.9%, tested twice, last 09-20), 23.11 M, 22.44 M

price vs 50-day average   higher 20d later   median 20d   fell 5%+ meanwhile
below it                        57%            +0.6%           21%
0-5% above                      67%            +1.8%           11%
5-10% above                     76%            +6.2%           14%
10-15% above                    82%            +8.9%           21%
15%+ above (now)                65%            +4.1%           47%   (13 episodes)
all days 2014-2026              67%            +2.3%           19%
```

In toman, 18K is higher 20 trading days later on two days in three because the rial
loses value, so every conditional figure is shown beside that base rate.

**Entry timing**, the owner's actual decision. In days like now (uptrend, 15%+ above the
50-day average), waiting up to 20 days for a dip, else converting then, against
converting at once:

```text
wait for 2% dip   came 68% of the time   cost 3.0% more on average
wait for 3% dip   came 62%               cost 3.2% more
wait for 5% dip   came 47%               cost 3.9% more
```

When the dip did not come the price ran away, and those misses outweighed the dips
caught: in this state delay was the expensive choice. Thirteen episodes: a lean sample,
kept measured rather than treated as law.

**Built** (branch `sp-d-direction` from SP-D):

- `caluclator/technical.py`: TA-Lib for the standard indicators (SMA 20/50/200, RSI 14;
  TA-Lib 0.8.1, binary wheels with the C library for the runner's Linux/py3.12 and
  Windows/py3.13; 201 functions incl. 61 candlestick patterns for step 3); trend state;
  stretch; support/resistance from one year of 5-day swings clustered within 2%, named by
  position. **Causal**: a swing counts only once confirmed (5 days after), so levels never
  use days that had not happened yet. MetaTrader 5's Python package was considered and
  rejected: Windows-only, needs a running terminal and a broker account, and no broker
  carries Iranian 18K in rial.
- `analysis/direction.py`: the view, the odds over similar past days (same trend state and
  stretch band; widened to the trend alone below 30 cases) for 5/20/60 days, the base
  rate beside each, the 5% pullback risk, and the entry-timing measure. **Causal**: day i
  counts only past days whose outcome was known by day i.
- `alerts/telegram_direction.py`: the DIRECTION section for ANALYZE, a **draft** not wired
  into any message until the owner approves its layout.
- `kpi/kpi_direction.py` 17/17: TA-Lib definitions, trend states, confirmed swings only,
  levels by position, later data never changing an earlier view, outcomes only once
  happened, base rate and sample beside every figure, both entry-timing directions, no
  decision authority, no instruction in the text, the draft not wired. Using unconfirmed
  swings fails 8 tests; counting outcomes not yet happened fails 5. Suite 29/29.

Direction is EVIDENCE: no BUY/SELL authority (CLAUDE.md invariants) until validated as
one. **Next:** a walk-forward check that the conditional odds beat the base rate out of
sample, year by year, before any of it is relied on; a split conversion (part now, part on
a dip) as a third entry option; the owner's layout approval, then ANALYZE; later, the
combination with the valuation leg ("heavily discounted + uptrend + near support") as a
measured condition.

### 1.1 Walk-forward check: what holds out of sample (2026-10-03)

Every day from 2016, judged with only what was known that day (similar past cases whose
outcome had happened), against what followed. Brier score, lower is better.

```text
higher 20 trading days later    conditional 0.229 vs base rate 0.222   skill -3.1%   NO
                                 (better in 5 of 11 years; days forecast 0-40% rose 94%)
fell 5%+ within 20 days         conditional 0.160 vs base rate 0.162   skill +1.2%   weak yes
                                 (better in 7 of 11 years)
entry: always wait for a 3% dip, against converting at once    +4.05% paid on average,
                                 a cost in every year 2016-2026 (+1.2% .. +7.8%)
near a support (within 2%)      higher after 20d 70% = all days 70%; level broke by 2%+
                                 within 20d on 26% (3+ times tested: 19%)
near a resistance (within 2%)   higher after 20d 71%; broke on 61% (3+ tested: 55%)
```

**What this means.** Classic trend and stretch states do not predict 18K's direction in
toman better than its base rate (higher a month later on about 70% of days since 2016,
the rial's depreciation). Support and resistance do not predict direction either; they
describe where pullbacks tended to stop (well-tested supports held about 4 times in 5).
The one robust, decision-relevant finding is the cost of delay: for preserving value,
converting promptly beat waiting for a dip in every year on record.

So the draft DIRECTION section's conditional "higher after 20d" figures must not be shown
as a forecast. The section is to be rebuilt around what held: the trend and the levels as
context, the base rate stated plainly, the pullback risk with its weak skill, and the
entry-timing record. Where the system has a real, immediate edge is *where and when in the
day* to convert -- the platform spread and the discount to fair value (SP_C_HANDOFF.md section 15) -- not
whether to wait. Further direction research (time-series momentum over 3-12 months, the
USD/IRR trend as a lead, 60-day horizons) is to be tested the same way before anything is
claimed.

## 2. SP-D R&D: decision anchors, R1 data and R2 event studies (2026-10-03)

**The owner's brief.** Not descriptive text but decision anchors a person can lock in:
will the uptrend resume and by how much, where in the trend we are (distance to the
SMA/EMA), the crosses in prices and indicators, candles, and probability methods, after
"a clean R&D before moving in". Approved plan: R1 data, R2 event studies, R3 probability
models, R4 anchor report (decision gate with the owner), R5 product. Production stays on
`main`; SP-D work reaches it only through the owner's review.

**Anchor panel, 18K at the close of 2026-10-01** (rank in 2014-2026 history):

```text
distance  SMA20 +6.8% (88th pct of uptrend days)  EMA20 +7.0%  SMA50 +16.6% (91st)
          EMA50 +14.5%  SMA200 +33.1% (77th); SMA50-SMA200 spread +14.2% (62nd)
trend     SMA50 above SMA200 since 2023-11-29: 813 trading days, +936%; longer than 5 of
          the 6 completed uptrends since 2014 (only 2016-2019 ran longer: 938 days)
crosses   price above SMA20 08-05, SMA20 above SMA50 07-20, MACD above its signal 09-30,
          RSI above 70 09-29
momentum  RSI 74.8 (90th), ADX 46.6 (88th), ROC60 +36.9% (90th); ATR 2.0% a day;
          price at 111% of the 20-day Bollinger band
legs      the dollar +20.6% above its 50-day, +14% in 20 days, +34% in 60, at 52-week
          highs; world gold (USD) -5.4% below its 50-day, -8.2% below its 200-day.
          18K's rise is the dollar's: world gold is correcting.
```

**R1, data.** tgju's world gold (`ons`, USD per ounce) has 12,156 daily candles from
1979-12-26 with a real range, reachable from Iran and from abroad. Added to the tgju
collector as `TGJU_XAU_USD` (unit USD), with each market's own calendar for the
once-a-day check: Iran trades Saturday to Thursday, world gold Monday to Friday. Once
merged to `main` the runner backfills it a page per run (about 13 runs).

**R2, event studies.** 110 event types with 8 or more cases: crosses of price and SMA
20/50/200, SMA 20/50 and 50/200, EMA 20/50, MACD and signal, RSI 70 and 30, Bollinger
bands, new 52-week highs and lows -- on 18K and, as leads, on the dollar and world gold --
and TA-Lib's 61 candle patterns in both directions (on candles with a real range only).
Measured: 18K's 5/20/60-day move and 5% pullbacks against the same period's base;
bootstrap significance, Benjamini-Hochberg across all 110, confirmation on held-back
2024-2026.

```text
passed (q <= 0.10 in 2014-2023 and same sign, half the size or more, on 2024-2026)
  18K new 52-week high            +3.22% over 20d, +13 pp higher (98)   holdout +2.63%, +11 pp (43)
  dollar falls below its 50-day   -3.21%, -18 pp; 5% pullback +25 pp (63) holdout -2.90% (19)
  18K falls below its 50-day      -2.88%, -14 pp (56)                    holdout -5.48% (11)
significant in-sample, not confirmed
  candle belt-hold, marubozu, long line (bullish); dollar new 52-week high
failed
  every other candle pattern; RSI, MACD, Bollinger and moving-average crosses
```

The anchors with evidence are trend continuation (new highs), trend breaks (losing the
50-day average) and, the strongest warning, the dollar's own break below its 50-day.
None is triggered against the uptrend on 10-01: 18K made five new 52-week highs in the
last 20 days, and both 18K and the dollar sit well above their 50-day averages.

Next: R3, probability models (the 10/50/90% range of 20 and 60-day moves, the chance of a
new high and of a pullback) from these anchors and the dollar and world-gold legs, walk-
forward against the plain historical range; then R4 with the owner.

## 3. SP-D R&D: R3 probability models, R4 verdicts, and the message draft (2026-10-03)

**R3, walk-forward.** Each year 2017-2026 predicted by models fitted only on earlier
years with known outcomes (regularised logistic regression and gradient boosting,
scikit-learn), from 24 causal anchors: 18K's distances to the averages, trend age,
momentum, range position and days since a new high, plus the dollar's and world gold's
own trends (world gold taken from the previous day). Scored against the plain record
known at the same time. `research/rd_models.py`, `rd_models_followup.py`,
`rd_calibration.py`, `rd_today.py`.

```text
question (next 20 trading days)          best skill vs plain record    verdict
new 52-week high                         +26.0%  AUC 0.78              PREDICTIVE
new 52-week high clearing it by 2%+      +19.0%  AUC 0.78              PREDICTIVE
new 52-week high clearing it by 5%+       +5.9%  AUC 0.62              too weak
higher 20 days later                     -27.3%  AUC 0.49              fails
fell 5% or more on the way                -8.0%  AUC 0.58              fails
how much: modelled 10/50/90% range       -2..-17% pinball, 51% cover   fails
how much: volatility-scaled range        +11% / +0% / +18% pinball,    CALIBRATED
                                         79% of outcomes in the 10-90% band (target 80)
```

The new-high forecasts rank well but are over-confident at the top: days forecast
80-100% made a new high 81% of the time (608 days), forecast 0-20% did so 23% of the
time. Only the measured rate of the forecast's band is shown, never the raw output.
The volatility-scaled range takes the historical spread of 20/60-day moves in units of
the recent daily volatility, times today's volatility; it fits the record far better
than the plain spread (64% coverage) because the market's volatility changes by period.
Its middle is no better than the plain one: consistent with direction being unpredictable.

**R4, anchor verdicts** (R2 and R3 together):

```text
PREDICTIVE   18K new 52-week high (continuation, +3.2% over 20d vs normal)
             dollar falls below its 50-day average (-3.2%; 5% pullbacks +25 pp)
             18K falls below its 50-day average (-2.9%)
             chance of a new high, and of one 2%+ above the record, within 20 days
             waiting for a dip against converting at once (a cost in every year)
CALIBRATED   the 10/50/90% range of 20 and 60-day moves, volatility-scaled
CONTEXT      distances to SMA/EMA 20/50/200 and their rank; trend age and gain against
             past uptrends; support/resistance (does not predict direction; well-
             tested supports held about 4 in 5); RSI, ADX, MACD and their crosses
DROPPED      up/down odds, pullback odds, every candle pattern
```

**Today's values** (close 2026-10-01, 25.69 M toman, a record): new high within 20
trading days 81% (base 41%); new high 2%+ above the record (26.21 M) about 70% (base
32%); 20-day range 10% / 50% / 90%: -6.3% / +3.3% / +17.0% (24.07 / 26.54 / 30.06 M);
60-day: -6.7% / +10.7% / +44.5%; 18K would break its 50-day average 14% lower
(22.04 M), the dollar 17% lower.

**Message draft for the owner's review** (DIRECTION, numbers only; delivery to be
decided: a daily message once the new tgju candle arrives, an on-demand command, a
section of ANALYZE, or several):

```text
DIRECTION · 18K · close 10-01
Price             25.69M   record high
Trend             up · day 813 · +936%
                  longer than 5 of the 6 uptrends since 2014

WHERE IN THE TREND                 rank since 2014
vs SMA 20         +6.8%            88th
vs SMA 50         +16.6%           91st
vs SMA 200        +33.1%           77th
RSI 14  75   ADX 47 (strong)

TESTED ANCHORS (2014-2023, confirmed 2024-2026)
New 52-week high      ON   5 in the last 20 days    then +3.2% vs normal
18K below its 50-day  off  14% away (22.04M)        if it breaks: -2.9%
Dollar below 50-day   off  17% away                 if it breaks: -3.2%

NEXT 20 TRADING DAYS
New high              81%   (all days 41%)
New high 2%+ (26.21M) 70%   (all days 32%)
Range 10/50/90%       -6.3% / +3.3% / +17.0%
                      24.07M / 26.54M / 30.06M
Next 60 days          -6.7% / +10.7% / +44.5%

LEVELS
Resistance            none (record)
Support               24.43M (-4.9%, tested 2x) · 22.44M (-12.7%, tested 2x)

TIMING
Waiting for a 3% dip cost 4.1% more than converting
at once, in every year 2016-2026.

Up/down is not forecast: no tested signal beat the
70% base rate. Historical record, not advice.
```

Next, after the owner's polish: implement the panel in `analysis/direction.py` from the
stored tgju candles (the models refitted daily, a few seconds), its KPIs, then the safe
tag and the merge to `main`.

## 4. SP-D Direction v2: the panel, its ledger, and /Direction (2026-10-03, sp-d-direction)

The owner's review of the section-3 draft (2026-10-03) rejected its shape, not its
evidence: an 813-day trend says nothing about where a reader stands; yesterday's close is
a day behind the market; "tested anchors" belong in a status view, not the message; the
words were too many and too vague; and a 5-case "18 to 608 more days, +73% to +169%" was
meaningless (it was: min..max of five rallies, and the gain counted from the rally's
start, not from today). The owner chose analyst option (a), "System says X, Analyst says
Y; the reader adjusts", an on-demand `/Direction` command computed once or twice a day, a
new table, and self-learning from day one with safeguards. LLM set aside.

### 4.1 Research behind v2 (`research/rd_gap_and_stall.py`, `rd_r2b.py`, `rd_stance.py`, `rd_leg_maturity.py`)

```text
RALLY LEGS (8% ZigZag, 2014-2026)  30 rallies, median 39 days, +41%; 31 corrections,
                                   median 17 days, -14% from the peak (half -11% to -19%)
DOES A MATURE RALLY END?           no: at every gain-rank bucket 10-16% ended within 20
                                   days, against 12% for all rally days
THE STALL CLOCK                    days in a major uptrend (50-day above the 200-day)
                                   since the last 52-week closing high -> next 20 days:
  days without a new high          2014-2023 new high / ended    2024-2026 holdout
  0                                92% / 4%                      95% / 4%
  1-4                              76% / 12%                     81% / 16%
  5-9                              68% / 13%                     65% / 28%
  10-19                            58% / 21%                     58% / 35%
  20-39                            32% / 47%                     29% / 71%
GAP TO THE 20-DAY (9%+ above)      closed in all 183 past cases, median 12 days; 68% by a
                                   dip, price at the touch a median -3.3%
GAP TO THE 50-DAY (15%+ above)     closed in 83% within 120 days, median 46 days; mostly
                                   by the average rising (price +3.9% at the touch)
WAITING FOR A 3% DIP               on stretched uptrend days the dip came 52-71% of the
                                   time, yet waiting still cost +2.3..+3.8% on average:
                                   when it does not come, the rally runs far. All days:
                                   costlier in 12 of 13 years 2014-2026 (2015: -0.4%);
                                   section 3's "every year" held for 2016-2026 only
ANALYST RULEBOOK (fixed, not fitted) trend up +1 / below the 50-day -1; new high in the
                                   last 4 days +1 / none for 20+ days -1; dollar above its
                                   50-day +1 / below -1; rally broken -1. >=3 STRONG
                                   BULLISH .. <=-3 STRONG BEARISH. Past STRONG BULLISH
                                   days: 76% higher 20 days later (all days 67%)
R2b TRADING PRINCIPLES             swing supports +4..+9 pp against a level with no
                                   history; time-at-price zones (the volume-profile proxy:
                                   no source publishes volume) +3/+14 pp near the price;
                                   failed breakouts (a liquidity-sweep proxy) were
                                   followed by gains, not reversals: dropped; fair value
                                   gaps refill in 1-2 days with no direction edge:
                                   dropped; AMD has no session structure on daily candles
20-DAY RANGE, OUT OF SAMPLE        quantiles from 2014-2023 held 72% of 2024-2026
                                   outcomes inside 10-90% (target 80), 22% above: short on
                                   the upside in a strong market. 60-day: 81% inside but
                                   17% above and 2% below, and as wide as the range the
                                   owner rejected (to +44%): kept in the ledger, not shown
```

### 4.2 What was built

- `caluclator/technical.py`: `rally_legs` (causal ZigZag), `days_since_high`,
  `time_at_price_zones`.
- `analysis/direction.py` (rewritten): `build_panel` -> one `DirectionPanel` with RALLY
  (leg number in the uptrend, start, age, gain, peak, end line at peak x 0.92, rank among
  past rallies, the stall ladder), POSITION (distances to SMA/EMA 20/50/200, rank among
  uptrend days, RSI, ADX, gap-closing statistics, tags), STANCE (rulebook, reasons,
  triggers with the stance each would leave, the stance's past record), OUTLOOK (new
  high within 20 days from the stall clock's band, against the uptrend base rate; the
  volatility-scaled 20- and 60-day range), LEVELS, CONVERT, the system's own decision
  (passed in, never computed), and the forecasts it commits to.
- Today's price is live: the platform median at tgju's level (+0.19%, SP_C_HANDOFF.md section 41.4) as a
  provisional close. It never enters a historical count, and ADX/ATR use completed
  candles only (the live bar has no range); `kpi_direction.test_10`.
- Tags, each with one definition: RECORD (a new 52-week closing high), STRONG TREND
  (ADX >= 30 in a trend), STRETCHED (9%+ above the 20-day), STALLING (10+ days without a
  new high), CORRECTION (inside an 8% correction), DOLLAR-DRIVEN (the dollar's 60-day
  rise at least 3/4 of 18K's).
- `analysis/direction_ledger.py`: the self-learning safeguards the owner asked for.
  Every forecast is stored with its panel before its outcome exists and never rewritten;
  it is resolved against tgju's candles only, never our own platform readings; one per
  Tehran day enters the record; the rates are re-counted from the whole history at every
  computation and nothing is fitted on the live record; the gate keeps a figure in the
  message only while its live record holds (the new-high rate must beat the base rate on
  Brier score, the range must hold 65-92% of outcomes, bullish stances must rise more
  often than all days). Below 30 resolved days a figure shows as "learning"; a failing one
  is demoted (the message falls back to the base rate or marks it with a warning) and the
  alarm is printed in the run log.
- `direction_snapshots` (`sql/neon_migration_direction.sql`, additive, one table, 14
  columns, unique on Tehran day and slot). Verified on the temporary branch
  `temp-direction-test` (br-sparkling-truth-agd8jbnb) 2026-10-03: table created, the
  real precompute stored the 13:00 panel from production's 17:01 prices in 6.0 s, the
  second run in the same slot was a 1.0 s no-op, and `/Direction` rendered it back.
  Not applied to production at the time; applied 2026-10-03 on the owner's
  authorization (section 5).
- `main.py`: `_direction_precompute` in the scheduled path after the tgju collection,
  for the first run from 06:00 and from 13:00 Tehran (`DIRECTION_SLOTS`); it resolves
  due forecasts, computes, gates and stores, and never raises. `DIRECTION_ONLY` mode
  (`mode=direction` in `gold-monitor.yml`) renders the stored panel and returns before
  any collection. The worker maps `/Direction` to it (the owner deploys the worker).
- `alerts/telegram_direction.py`: the v4 message (VIEW, RALLY, POSITION, OUTLOOK, LEVELS,
  CONVERT, NEXT, footer), about 3,300 characters, checked against the wording rules by
  `kpi_direction.test_23`. NEXT is a first draft for the deep-dive with the owner.
- The decision reason printed under "Reason:" in the daily recap, the SELL alert and the
  e-mail said "Discount widening"/"narrowing" (`caluclator/conflict.py`): now
  "increased"/"decreased", and "deeply discounted" is now "heavily discounted";
  `kpi_sp_c6.test_26b`.
- `kpi_direction` 30/30; full suite 29/29 files, runner exit 0.

### 4.3 Open

- The owner's review of the v4 message, and the NEXT section designed with the owner.
- Production migration (authorization), then the temp branch's deletion (authorization).
- Where the tested-anchor table lives: a `/Direction record` view, or the docs only.
- The new-high figure is the stall clock's plain rate (93% at a record), not the
  section-3 model (whose 80-100% band made a new high 81% of the time over a wider set
  of days). The model can run in shadow through the same ledger once there is a live
  record to compare it with.
- Then: the safe tag on `main` (`v1.4safe`), the merge, and verification.

Closed by section 5: the migration (applied), the temp branch (deleted), the v4 message
(replaced by v5).

## 5. The owner's review of v4, the EMA cross, and the v5 message (2026-10-03)

**The review.** v4 was too long for a phone ("user will review or see the msg on a mobile
telegram platform"), and four sections carried no decision the owner could read: the
stall ladder, the gap-closing statistics, the outlook range and the NEXT list. The
owner's question: what is the package for, what do we want to show the user? And one
addition: the EMA cross, e.g. 20 and 50 day. Authorization granted for the migration and
the temp branch's deletion. SP-C is closed; SP-D is recorded here from now on (sections
1-4 moved from `SP_C_HANDOFF.md`).

**The purpose, stated.** For a rial holder deciding when to convert into gold: is the
uptrend intact, how late and stretched is it, which prices or events would change the
picture, and has waiting for a dip paid. Every line of the message answers one of those
four; the evidence behind each (the ladder, the gap statistics, the range and its
calibration, the supports) stays in the stored panel and in this file.

**EMA 20/50** (`research/rd_ema_cross.py`; next 20 trading days):

```text
                                 2014-2023                     2024-2026 holdout
all days                         64% higher, 5% drop 17%       75% higher, 5% drop 22%
EMA20 above EMA50                68% higher                    74% higher
EMA20 below EMA50                56% higher                    81% higher
fresh golden cross (0-4 days)    64% higher, +1.5%             36% higher, -3.1%
fresh death cross (0-4 days)     5% drop 33%                   5% drop 32%
crosses since 2014               22 golden, 21 death, 5 reversed within 10 days
```

The state is not a direction signal: its edge reversed out of sample, and a fresh golden
cross whipsawed. The death cross is a risk signal in both periods: a 5% drop within 20
days about 1 in 3 times, against about 1 in 5. So the message reports the state and its
date as context, and the death cross as a line to watch with its measured risk. Today:
EMA20 above EMA50 since 2026-07-18, gap +7.4%.

**v5** (`alerts/telegram_direction.py`, from production's 17:01 prices): 941 characters
against v4's 3,300, short lines, no padded columns (they do not align in a phone's
proportional font), odds as "N in 100", and the stall clock as two dates rather than a
table (the 5th and 20th trading day without a new high, Fridays skipped, holidays not
known, hence "~"):

```text
GOLDPremium: DIRECTION
18K 26.57M · 17:01 · record high
[STRONG TREND] [STRETCHED] [DOLLAR-DRIVEN]

VIEW
System: WAIT · usual discount
Analyst: STRONG BULLISH
trend up · new highs · dollar above its 50-day
Past such days: 76 in 100 higher 20 days later (all days 67)

WHERE WE ARE
Rally #10 · day 86 · +70% from 15.65M
+9.9% above its 20-day avg (stretched: top 9%)
EMA 20/50: bullish since 07-18 (gap +7.4%)
60 days: 18K +46% · dollar +38%

NEXT 20 DAYS (past cases like today)
New high: 93 in 100
3% dip (to 25.77M): 63 in 100
Waiting for it paid 2.6% more on avg

LINES TO WATCH
▼ 24.45M: rally ends (−8%) · support → BULLISH
▼ 22.20M: trend breaks (50-day) → NEUTRAL
▼ EMA20 under EMA50: 5% drop 33 in 100 (usual 19)
▼ Dollar below 214,232 (its 50-day) → NEUTRAL
⏳ No new high by ~10-08 → BULLISH
⏳ No new high by ~10-26: rally ended 54 in 100

Computed 17:01 from live prices · self-check 0/30 · not an up/down forecast
```

A raw "<" in the first v5 draft ("Dollar < 214,232") would have been rejected by
Telegram's HTML parser and swallowed the lines after it; `kpi_direction.test_23b` now
checks that only `<b>` and `<i>` appear and that "<", ">" and "&" never appear bare.

**Production.** `direction_snapshots` applied to production 2026-10-03 about 17:20 Tehran on the
owner's authorization: 14 columns, `uq_direction_snapshots_slot`, 0 rows; existing
tables untouched (686 market snapshots, 7,484 daily candles before and after). The
temporary branch `temp-direction-test` was deleted; only the production branch remains.
`main` does not yet write to the table: the precompute arrives with the merge.

`kpi_direction` 33/33; full suite 29/29 files, runner exit 0.

**Open:** the owner's polish of v5; then the safe tag `v1.4safe` on `main`, the merge,
the worker redeploy (owner), and the first 06:00 and 13:00 panels verified.

## 6. v6: plain words (2026-10-03)

**The review of v5.** "76 in 100 you mean 76%? then what does it mean higher 20 days
later?"; "60 days ... why not 59, why not 61? and how could this data help the user
decide?"; "3% dip mean 3 percent drop? so instead of dip let's say drop"; "waiting for it
paid 2.6% more on avg, so don't wait, ha?"; the EMA cross to get a proper place: above or
below, and by how much. The same notion applies to every line: plainly readable.

**What changed.**

- Odds are percentages ("93% chance"); 20 trading days is "a month" (stated once:
  "NEXT MONTH (20 trading days, from past days like today)"); "dip" is "drop".
- The stance's record reads as a sentence: "After past days like this, 18K was higher a
  month later 76% of the time (any day: 67%)."
- The 60-day window was arbitrary and is gone. The source of the rise is measured over
  the rally itself, and the DOLLAR-DRIVEN tag with it: since 06-16 the dollar rose 67%
  (155,000 to 258,465 toman, tgju) and world gold fell 4% ($4,334 to $4,143), while the
  platforms' gap to fair value went from -3.4% to -0.5%. The rally is the dollar's, which
  is what a rial holder needs to know: the dollar line in WATCH is the one that matters.
- The wait-for-a-drop result is the plain comparison: "Buy now or wait for that drop? On
  average, buying now was 2.6% better." It is an average over 197 past days like today,
  on which the drop came 63% of the time; when it did not come, the rally ran far.
- MOVING AVERAGES (EMA) is its own section: the price against the 20- and 50-day EMA, the
  20-day against the 50-day with the date of the cross, and the stretch as a rank (now
  measured on EMA20: price this far above it on only 7% of uptrend days).
- Every break in WATCH carries the same measured consequence, the chance of a 5% drop
  within a month in the 5 days after it, against 19% on any day (2014-2026): 18K below its
  50-day 28% (242 days), the EMA20 under the EMA50 33% (104), the dollar below its 50-day
  33% (228).

```text
GOLDPremium: DIRECTION
18K 26.57M · 17:01 · record high
[STRONG TREND] [STRETCHED] [DOLLAR-DRIVEN]

VIEW
System: WAIT (platforms at their usual discount to fair value)
Analyst: STRONG BULLISH
Why: uptrend · new record highs · dollar above its 50-day average
After past days like this, 18K was higher a month later 76% of the time (any day: 67%).

TREND
Rally 10 of the uptrend since 2023-11: +70% since 06-16 (86 trading days)
Driven by the dollar: dollar +67%, world gold −4%

MOVING AVERAGES (EMA)
Price is 9.5% above the 20-day and 17.6% above the 50-day
20-day is 7.4% above the 50-day: bullish since 07-18
Stretched: price was this far above its 20-day on only 7% of uptrend days

NEXT MONTH (20 trading days, from past days like today)
New record high: 93% chance
3% drop (to 25.77M): 63% chance
Buy now or wait for that drop? On average, buying now was 2.6% better.

WATCH (chance of a 5% drop within a month: usually 19%)
Below 24.45M (−8%): rally over; past corrections −14% median. Analyst → BULLISH
Below 22.20M (50-day avg): uptrend broken; chance of a 5% drop 28%. Analyst → NEUTRAL
20-day EMA under the 50-day: chance of a 5% drop 33%.
Dollar below 214,232 (its 50-day avg): chance of a 5% drop 33%. Analyst → NEUTRAL
No new record by ~10-08: Analyst → BULLISH
No new record by ~10-26: the rally then ended 54% of the time.

Computed 17:01 from live prices · history since 2014 · not a price forecast · track record 0 of 30 days checked
```

1,467 characters. `resolve_direction` now also loads world gold (`TGJU_XAU_USD`).
`kpi_direction` 34/34 (`test_23e`: the source and the tag over the rally, every watched
break with its consequence); full suite 29/29 files, runner exit 0.

**Open:** the owner's polish of v6; then the safe tag, the merge, the worker redeploy and
the first panels verified.
