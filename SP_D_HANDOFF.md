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

## 7. Safe tag and merge to main (2026-10-03)

The owner, on v6: "much better, go ahead with the tag and push".

- **CI first.** `kpi-suite.yml` dispatched on `sp-d-direction` (run 37131408592): install
  (TA-Lib 0.8.1 wheel included), compile check and the full KPI suite passed on GitHub's
  runner. `main` has never installed TA-Lib before; this run is the evidence it can.
- **Safe tag.** `v1.4safe` (annotated) on `main` at cc9431d, pushed before the merge:
  "main before the SP-D Direction merge (2026-10-03): the last state of main without
  SP-D, kept as the rollback point". Rollback: `git push --force origin
  v1.4safe^{}:main` and nothing else, since `direction_snapshots` is additive and
  unread by the old code.
- **Merge.** `main` was an ancestor of `sp-d-direction`, so `main` and `SP-D` were
  fast-forwarded to it: the tree CI passed plus the worker file, its README and these
  records (no Python change; `kpi_direction` 34/34 locally), and `kpi-suite.yml` runs
  again on the push to `main`.
- **Worker** (`src/worker/telegram-trigger.js`): the `Direction` command (mode
  `direction`), and the two improvements its README held for the next edit -- one
  `TARGET_REF`, and `Status` scoped to `gold-monitor.yml` on that ref. The owner
  deploys it (Cloudflare dashboard, paste the file, Save and deploy).
- **cron-job.org needs no change.** It already dispatches `mode=analyze` on `main` every
  hour; the precompute runs inside that path, at the first run from 06:00 and from
  13:00 Tehran. The first run after the merge stores today's 13:00 panel.

**To verify:** the first post-merge ANALYZE run logs `DIRECTION: 13:00 panel 1 stored`
and writes one row to `direction_snapshots`; then `/Direction` after the worker deploy.

## 8. Health check 2026-10-04 10:15, and a stale-series fix

**Since the merge** (2026-10-03 18:35 to 2026-10-04 10:15 Tehran): 9 scheduled ANALYZE
runs, all successful, 6-9 minutes each as before; one market snapshot and one analysis
snapshot per run; 36 outcomes, 350 news items, 153 price observations. The worker is
deployed: `/Direction` at 18:36 and 18:47 answered "No panel computed yet" (the first
panel came at 19:01), at 08:32 it sent panel 2. Verified as designed:

- `direction_snapshots`: panel 1 (10-03, slot 13:00, stored 19:01), panel 2 (10-04, slot
  06:00, stored 06:01); both STRONG BULLISH, 4 forecasts each, none due yet.
- tgju: the 10-03 candles for 18K (26.23M) and the dollar (267,900) collected at 06:02.
- Two BUY candidates held by the confirmation, both correctly: 10-03 18:50 (`/Update`,
  only Milli showed the discount; MioGold not heavily discounted on its own record) and
  10-04 10:01 (the dollar had not updated today; Taline confirmed the discount). The
  10:01 discount was real: every platform's price decreased 0.5-1.0% together while the
  dollar and world gold were unchanged (weekend).
- Known and unchanged: Daric 403 to the runner (their side); one MioGold timeout (21:00);
  Taline discarded once by its 1% band (09:01, -1.22%) an hour before every platform
  moved the same way -- likely a leading price, not a stale one; one case, noted.

**Defect: world gold "+0%".** World gold's tgju history (`ons`, 12,156 days from 1979) is
backfilled oldest first, 1,000 days per run; on 10-04 10:02 it reached 2010-11-23. Both
dates of the rally landed on that last close, so `xau_since_start` was 0.0 in panels 1
and 2 and `/Direction` at 08:32 printed "Driven by the dollar: dollar +73%, world gold
+0%". The real figure is about -4%. The dollar part and the tag were right.

Fix (`hotfix-direction-stale-series`, cut from `main`): `_move_between` returns None
when the series has no close within 5 days of either date (a weekend or a holiday run
fits; a backfill does not), the dollar's move uses the same function, and the message
prints "world gold: not available" rather than a number. Fail-safe law: unknown, not
fabricated. `kpi_direction.test_23f`; 35/35; full suite 29/29, exit 0. Against the real
data: with world gold as stored now, unknown; with the full history, -4.4% (dollar
+66.8% either way). The backfill completes around 15:00 on 10-04 by itself.

The owner approved the fix ("go ahead with the fix push"): `v1.5safe` tagged `main` at
3a93300 and was pushed, then `main` and `SP-D` were fast-forwarded to b1e61eb at 10:37;
`kpi-suite.yml` passed on `main` (run 37184855090).

## 9. The PAPER portfolio: the scenario, the contract, v0 and its harness (2026-10-04)

**The scenario** (owner, 2026-10-04): give the system a hypothetical 100,000,000 toman;
it buys and sells whole grams of 18K on one platform, at most once a day, holds what it
buys, pushes every trade, reports every evening, and is reviewed per Persian quarter on
the money it ends with. "Even in such an economy there are buy sell decisions to be
made": 18K went from 20.61M (2026-01-29) to 15.65M (2026-06-16), -24.1% over 113 trading
days, before rising 69%. The analyst is to decide from all the data and history, the
news included, and the runs where it cannot decide are what it learns from.

**The contract** (agreed 2026-10-04; `analysis/paper.py` holds it):

```text
 1  capital        100,000,000 toman cash on the start day (go-live)
 2  venue          one platform: buy at its buy price, sell at its sell price, one reading
                   (Goldika now; Daric from a quarter boundary once an Iranian route works)
 3  units          whole grams, at least 1 g a trade; the residue stays as cash
 4  frequency      at most one trade per Tehran day, at ANY scheduled run (06:00-21:00)
 5  no borrowing, no short selling
 6  fresh price    no trade without a venue quote that passed validation, with both sides
 7  report         21:00: gold (grams, value at the sell price), cash, total, and the
                   profit or loss against the quarter's first day
 8  push           every trade, labelled PAPER (the system's own BUY alert keeps its
                   authority; this account reports what it did)
 9  log            every analyst run with its inputs; UNDECIDED where signals conflict
10  quarters       Persian seasons: 1 Farvardin, Tir, Mehr, Dey. The first runs from
                   go-live to 30 Azar 1405 (2026-12-21); the next 1 Dey (2026-12-22) to
                   29 Esfand (2027-03-20)
11  rule changes   only at a quarter boundary, under a new policy version
```

**Venues, measured 2026-10-04.** Of the collectors, Daric, Ayyareh, Goldika, Milli and
WallGold read an API (Invi a page's embedded JSON); HoorGold, Parasteh, Taline, MioGold
and Eligold scrape pages. Both sides: Daric (order book: best bid 26.39M, best offer
26.46M, 0.26% apart) and Goldika (buy 26.76M, sell 26.13M, 2.37% apart, with a source
time stamp). Ayyareh: one price plus `buyWageValue`/`sellWageValue` 0.02 (likely a 2%
fee each way). WallGold: the same price for `side=buy` and `side=sell`. Milli: one price.
Both sides were fetched for Goldika and dropped by `collector/iran._run_collector`, so
Goldika's BUY/SELL observations and candles (which `intelligence/candles.py` was built
to expect) were never written; both sides now pass through, and Daric returns its bid
and offer. Daric from the runner: 93-100% of runs answered until 09-24, then 0% on
09-25, 09-26, 10-02 and 10-04 and 6% on 09-27 and 10-03; through Psiphon (a foreign
address) it answered 403 on 10-04. Daric blocks foreign addresses on some days, so a
Cloudflare route, also foreign, is unlikely to be reliable: the route is a relay inside
Iran.

**The evidence for v0** (`research/rd_paper_v0.py`; whole grams, 100M, one trade a day,
signal at day i's close, trade at day i+1's close, Persian quarters against holding):

```text
                          2014-2023 x / quarters better-worse   2024-2026 x / better-worse
Goldika's cost (2.37% round trip)
buy and hold              x25.40                                x9.67
stance 1/1/.5/0/0         x 5.38   9-30                         x4.42  3-9
out on a confirmed break  x12.71   6-13                         x8.15  1-7
Daric's cost (0.30%)
buy and hold              x25.92                                x10.01
stance 1/1/.5/0/0         x12.10  11-27                         x5.59  3-9
out on a confirmed break  x19.63   7-12                         x9.76  3-6
2026-01-29 -> 06-16 at Daric's cost: hold -24.1%, stance -11.1% (then +26.6% to 10-01
against hold's +64.1%), confirmed break -18.5% (then +46.8%)
```

No tested rule beat holding. Exposure from the stance halves the drop and misses the
recovery; the costs of a platform decide how much an active analyst can do at all (the
same stance rule: x5.4 at Goldika's cost, x12.1 at Daric's). v0 is therefore "invested
by default, out on a confirmed break" -- the baseline the R&D has to beat, not a claim
of an edge. Signals use completed tgju candles only.

**The harness.**
- `timeutil`: the Persian calendar (`to_jalali`, `from_jalali`, `persian_quarter`), the
  jalaali algorithm, checked against all 13,549 Persian dates tgju publishes beside its
  candles (1979-2026, 0 mismatches) and 54,787 consecutive days round-tripped.
- `analysis/paper.py`: the contract, `analyst_target` (v0), `decide` (whole grams, the
  band, one trade a day, a fresh two-sided quote), the shadow accounts (buy-and-hold,
  and the system's own final BUY/SELL), and the conflicts logged as UNDECIDED.
- `paper_accounts` and `paper_activity` (`sql/neon_migration_paper.sql`, additive). The
  database holds two clauses itself: one TRADE and one REPORT per account per Tehran
  day (partial unique indexes).
- `main._paper_run` in every scheduled run after the Direction precompute; the first run
  from 21:00 writes the REPORT rows and sends the analyst's report. Never raises.
- `alerts/telegram_paper.py`: the trade push and the 21:00 report (drafts, below).
- `kpi_paper` 18/18; full suite 30/30 files, runner exit 0.
- Verified on the temporary branch `temp-paper-test` (br-noisy-union-agpgixj6) with
  Goldika's live quote and production's candles: analyst and buy-and-hold bought 3 g at
  26.77M at the first run, the system account held cash (WAIT), later runs logged
  "already traded today", the 21:00 run wrote one report per account and one message,
  a second evening run none. 13.8 s a run through the tunnel.

```text
GOLDPremium: PAPER BUY
Bought 3 g at 26.77M (Goldika) · 12 Mehr 11:36
Why: uptrend intact: no confirmed break
Now: 3 g gold + 19.70M cash = 98.10M

GOLDPremium: PAPER · 12 Mehr 1405, 21:00
Gold: 3 g = 78.40M (Goldika pays 26.13M a gram)
Cash: 19.70M
Total: 98.10M
This quarter (since 12 Mehr): −1.90%
Holding from the start instead: 98.10M (−1.90%)
Today: bought 3 g at 26.77M (11:36)
Analyst: invested; sells only on a confirmed break (below 24.13M and the 50-day average, now 22.19M)
```

The day-one -1.90% is the venue's buy/sell gap, not a market move: the gold is valued at
what Goldika would pay for it. With 100M and a gram near 26.8M, whole grams allow 3 g
(about 80%); about 19.7M stays in cash whatever the analyst decides, in the benchmark too.

**Data for a sharper analyst** (research, not built):
- TSETMC (the Tehran exchange's data site) publishes, for each gold fund, daily prices
  and volume (عیار, Mofid's gold fund: 2,000 days) and the money flow split between
  individuals and institutions (1,704 days from 2018-06-09; on 10-03 individuals bought
  a net 134 billion toman of عیار). This is the money flow PROJECT_MEMORY lists under
  Tindex; Tindex itself publishes no API. Gold funds found: عیار (34144395039913458),
  طلا (46700660505281786), کهربا (25559236668122210), زر (33254899395816171), گوهر
  (12390706505809150). Libraries: `5j9/tsetmc` (async, needs Python 3.13) and
  `mahs4d/tsetmc-api`; the JSON API (cdn.tsetmc.com/api) is simple enough to read
  directly. TSETMC does not answer foreign addresses (timed out through Psiphon): it
  needs the same Iranian relay as Daric.
- Navasan (api.navasan.tech) answers foreign addresses; it needs an API key.
- News: ingested, but `high_impact_count` is still a constant (SP_C_HANDOFF.md 33.3).
- Charts: rendering a chart into the report is straightforward; deciding from chart
  patterns needs testing (the candle patterns failed in section 2).

**Open:** the owner's review of the two messages; the production migration
(authorization); the temporary branch's deletion (authorization); the capital and the
3 g granularity; the Iranian relay for Daric and TSETMC (where to host it).

## 10. A brave trader, a venue chain, a relay, and continuity (2026-10-04)

**The owner's review of section 9.** Venues: Daric preferred, Goldika and Ayyareh as
backups; try a Cloudflare route for Daric ("the Iran geo-IP blocking is kinder to
Cloudflare than to GitHub"). Continuity: "if the internet goes Iran-access-only, there
should be a continuity resolution". The benchmark line "Holding from the start instead"
was not clear. The analyst was too strict: "maybe today it buys at 26.77 and sells at
27.00 and then buys back at 26.500 ... the system trader is a brave one, not a
conservative person". The GitHub libraries for TSETMC: "give it a hard try in a test
environment, or via Cloudflare". Capital: strict numbers with a residue of 1-2%.
Temporary resources may be deleted freely once used, and reported (a standing rule).

**From GitHub's runner** (a temporary push-triggered workflow on a temporary branch, no
secrets, no database, 2026-10-04 11:57; both deleted): runner in the US (Azure).
Goldika, Ayyareh, Milli, WallGold and tgju answered. Daric: 403. TSETMC: every endpoint
(cdn.tsetmc.com, old.tsetmc.com, members.tsetmc.com) timed out at connect, so the
runner's addresses are refused outright; `tsetmc-api` (mahs4d) installed and failed the
same way; `tsetmc` (5j9) did not import on 3.12 or 3.13. Navasan answers (needs a key).
Ayyareh's fee was 0.01 a side at 11:57 against 0.02 at 10:35: it moves, so it is read
each run.

**The brave analyst (v1).** Evidence (`research/rd_swing_hourly.py`,
`rd_fair_lag_daily.py`, `rd_swing_daily.py`, `rd_swing_targets.py`):

```text
hourly, 62 days (610 readings): after fair value moved >= 1%, platforms kept moving that
  way by +0.3-0.4% over the next ~9 readings (a day) -- a lag inside the day
daily, 12 years: no lag at all (today's fair-vs-18K gap against tomorrow's move:
  correlation +0.01 in 2014-2023, +0.04 in 2024-2026): 18K absorbs fair moves the same day
core + swing on stretches over EMA20 (Daric's cost): about -1.0 pp a quarter in-sample
the owner's example as a rule, core 80% + swing 20% (whole account; continuous shares):
                                     2014-2023                       2024-2026 holdout
  buy and hold (Daric's cost)        x25.94                          x10.04
  v0, out on a confirmed break       x19.65                          x9.83
  swing at +5%, back -2% or 5 days   x25.89 (q 8-7, -0.1 pp, 10/yr)  x9.36 (q 1-9, -0.8 pp, 22/yr)
  the same at Goldika's cost         x21.70 best (-0.6 pp)           -1.0 to -2.5 pp a quarter
```

The swing rule is the first active rule that keeps pace with holding at Daric's cost;
v0's exit on a confirmed break is the costly part (x19.65 against x25.94), so v1 never
sells its core on technicals. v1: on day one it buys every whole gram the cash covers and
marks about a fifth (1 of 5) as its swing; it sells the swing once a venue pays +5% over
its cost, buys it back 2% under the sale or after 5 trading days at the latest, and buys
more whenever the cash covers another gram. Prices are checked at every run, so a +5%
inside the day is taken (the backtest used closes only). v0 continues as the shadow
account "cautious"; four accounts start together: analyst (v1, pushes), cautious (v0),
buy-and-hold, system.

**Capital: 135,000,000 toman.** At 2026-10-04's prices 5 g leave 2.0% at Daric's offer
(26.46M) and 0.85% at Goldika's buy (26.77M); 110M leaves 2.7-3.8% (4 g), 120M and 150M
about 11%. The residue changes with the price and with every trade.

**Venue chain:** Daric, then Goldika, then Ayyareh; each trade runs on the first venue
with a fresh two-sided quote and records it. Ayyareh's sides are its published price
plus its buy fee and minus its sell fee (`collector/ayyareh.py`; its `price` is
unchanged for every other consumer).

**The relay** (`src/worker/data-relay.js`, a separate Cloudflare Worker; not deployed):
read-only GETs to an allowlist (Daric's price API and three TSETMC endpoints), guarded by
a token, with `/probe` reporting each source's status from Cloudflare's side.
`collector/relay.get_json` tries a source directly and, when it is refused and
`RELAY_URL`/`RELAY_TOKEN` are set (GitHub secrets, passed by `gold-monitor.yml`), asks the
relay. Unset, collectors behave as before. Daric uses it now; a TSETMC collector follows
once the relay is shown to reach it.

**Continuity if the internet becomes Iran-only** (a design for the owner, not built): in
a national-only cut the runner abroad reaches no Iranian platform, Neon (Frankfurt) and
Telegram are unreachable from inside Iran, and world gold stops at its last price. One
small server inside Iran (Liara, ArvanCloud or a VPS) would serve two roles. Normally it
is the relay for Daric and TSETMC. In a cut, when the runner has reached no Iranian
platform for several runs, it becomes the collector: the same code, with Iranian sources
(platforms, tgju's dollar and its world-gold page while tgju updates it, else the last
price, flagged), a local database, and messages through Bale's bot API (Telegram-
compatible, domestic). One writer at a time, through a lease, so the account never trades
twice. When the cut ends, its rows are merged into Neon and the runner is primary again;
the one-trade-a-day indexes refuse a duplicate.

`kpi_paper` 21/21; full suite 30/30 files, exit 0. Rendered from Daric's live quote
(266.90M buy, 265.88M sell, 0.38% apart, 2026-10-04 13:00):

```text
GOLDPremium: PAPER BUY
Bought 5 g at 26.69M on Daric · 12 Mehr 13:01
Why: opening: 5 g, 1 g of them to trade
Now: 5 g gold + 1.55M cash = 134.49M
Next: sell 1 g if a venue pays 28.02M or more (+5% over its cost)

GOLDPremium: PAPER · 12 Mehr 1405, 21:00
Gold: 5 g = 132.94M (Daric pays 26.59M a gram)
Cash: 1.55M
Total: 134.49M
This quarter (since 12 Mehr): −0.38%
Bought on day 1, never traded: 134.49M (−0.38%)
Today: bought 5 g at 26.69M on Daric (13:01)
Plan: sell 1 g if a venue pays 28.02M or more (+5% over its cost)

GOLDPremium: PAPER SELL           (an illustration: Daric at +5.5% three days later)
Sold 1 g at 28.16M on Daric · 15 Mehr 14:01
Why: +5.5% over its 26.69M cost: profit taken
Now: 4 g gold + 29.71M cash = 142.34M
Next: buy 1 g back at 27.60M or less, or on 21 Mehr at the latest
```

**Open:** the owner deploys the relay worker and sets its token; the relay probe from
Cloudflare's side; then the GitHub secrets, the TSETMC collector, the production
migration (authorization), the continuity server (a decision), and the merge after the
safe tag.

## 11. Toward a senior analyst: the drivers, the data, the evidence (2026-10-04)

**The owner's review of section 10.** "It's not buying 5 grams, hold 4, trade 1; maybe you
trade 2 or 3; it depends on the comprehensive analysis." The analyst must compute the
chart and its support and resistance; volume profile, LIT and AMD may come alive with
TSETMC's data; the news leg: the analyst can see the news; in a downtrend like 20 -> 15
"buying it even in sprinkle mode was a bad idea"; "so far it has been so weak R&D"; the
analyst "is so junior". The owner is building the Cloudflare relay meanwhile.

**New data: the gold funds on the Tehran exchange** (`research/fetch_tsetmc_gold_funds.py`,
from an Iranian connection; research/data, git-ignored). 20 commodity funds, of which 19
hold gold (سافرون is saffron): daily OHLC, volume, value traded and trade count, and the
money flow split between individuals and institutions -- طلا 2,239 days (from 2017), زر
2,160, گوهر 2,119, عیار 2,001, كهربا 1,252, سافرون excluded, and 14 younger funds.

**What drove the 2026 drop** (`research/rd_downtrend_2026.py`): world gold, not the
dollar. 2026-01-29 -> 06-16: 18K -24.1%, world gold -19.7% ($5,278 in February ->
$4,013 in June), the dollar -2.2%. The rally after it was the dollar (+67% to 10-03,
world gold -4%). The stance and v0 read 18K's own trend and the dollar's; neither read
world gold's. Individuals bought a net 39,268 billion toman of gold funds in May, in the
middle of the fall.

**The comprehensive model** (`research/rd_analyst_model.py`): 18K's trend, momentum and
range position; the dollar's and world gold's trends and drawdowns; 18K's gap to fair
value; the gold funds' net individual flow and value traded (2019 onward). Gradient
boosting refitted each year on earlier years only, scored on the next:

```text
                              2016-2023 (2019-23 with funds)      2024-2026
drop 8%+ within 20 days   18K+dollar  AUC 0.64                    AUC 0.66
                          all prices  AUC 0.64                    AUC 0.56
                          + funds     AUC 0.79 (556 days)         AUC 0.58
rise 8%+ / higher in 20d  AUC 0.45-0.60 throughout: no skill
Brier skill against the base rate: negative everywhere (probabilities too extreme)
```

Drop risk can be ranked a little; rises cannot. As a policy (the share in gold from
P(rise) - P(drop), five steps, Daric's cost) it halved the 2026 drop (x0.90 against
holding's x0.80) and ended level with holding from 01-29 to 10-01 (x1.30 / x1.29), but
trailed it over 2016-2023 (x17.1 / x22.3) and 2024-2026 (x8.5 / x9.9), trading about 40
times a year. As a risk switch (cut to 50% or out when the drop risk is in its top band)
it protected the 2026 drop (x0.90-1.00) and cost far more elsewhere (x11.7 / x22.3).

**Sizing by the drivers** (`research/rd_driver_regimes.py`: the share in gold by how many
of the dollar, world gold and 18K are in a confirmed downtrend): worse than holding in
every span, the 2026 drop included (x0.72 / x0.80). A trend confirmed down is a fall
already made, and the rebound after it is missed.

So: every price-based timing approach tested -- single rules (sections 9-10), the full
model, the risk switch, driver regimes -- trails holding after costs over the long run;
only the swing rule keeps pace (section 10). On the owner's question: buying into the
2026 drop looks bad in hindsight, but no price signal of the time separated it from the
dips that recovered, and the signals that would have kept the account out of it also
kept it out of the rebounds. What did change first was world gold, a global event; an
earlier warning has to come from information prices do not hold yet.

**Support and resistance with real volume** (`research/rd_volume_profile.py`): the gold
funds' value traded spread over 18K's daily range, 120 days, 1% bins. A support holds
when 18K never closes 2% below it within 20 days, against a level with no history:

```text
                        2019-2023 support / resistance     2024-2026 support / resistance
value area low          +6 pp / +7 pp                      +15 pp (6 days) / +18 pp (8 days)
value area high         +11 pp / -11 pp                    +5 pp / -4 pp
POC                     -19 pp / -2 pp                     +11 pp / -1 pp
HVN                     -16 pp / +10 pp                    +1 pp / +3 pp
```

The value area's edges carry a modest edge; the POC and HVNs are inconsistent. Today
(10-01, 18K 25.69M) the 120-day value area spans 18.65-25.64M, POC 23.91M.
`caluclator/technical.volume_profile` computes it.

**The chart** (`alerts/chart.py`, a draft, not sent by any message yet): 120 daily candles,
EMA20 and EMA50, the swing supports and resistances with their prices, the value area
where volume exists, the PAPER trades, and the live price; PNG for Telegram's sendPhoto
(matplotlib, to be pinned in requirements.txt when it is wired). `research/chart_preview.py`
renders it from the stored history.

**The news leg as stored:** 6,928 headlines from 2026-08-24, 10 sources (دنیای اقتصاد,
تجارت نیوز, Tehran Times, Google News queries on the gold price, the rial and Middle East
strikes, investing.com and others). Classified by keywords only: impact UNKNOWN on 88%,
gold direction RISING 696 against FALLING 34, topic empty on every row -- a degenerate
classifier of the kind CLAUDE.md lists. Six weeks cannot be tested. A real news leg needs
an event classification (an LLM may classify and summarise headlines; it never computes
prices or decides) and a long history to test against (GDELT's event database covers
Iran from 2015).

**The senior analyst, as designed (not built):** the grams it holds, from 0 to all, set by
an assessment of every leg, each leg weighted by its measured evidence and logged:
world gold's and the dollar's regimes (the drivers); the drop-risk model as a risk
overlay; 18K's gap to fair value inside the day for the entry time (the +0.3-0.4%
follow-through, section 10); support, resistance and the value area for the targets,
in place of the fixed +5% and -2%; the gold funds' flows once the relay brings TSETMC;
news once it is classified and tested. It goes live only after it beats v1 in a replay,
and is then judged live by the quarter.

**Next R&D, in order:** (1) world gold's own early warning (its trend, momentum and
drawdown against 18K's next 20-60 days); (2) the news leg: GDELT's Iran event history and
an LLM classification of our headlines; (3) level-based swing targets (sell at
resistance or the value area's high, buy back at support or its low) against v1's fixed
ones; (4) intraday entry timing on the fair-value gap; (5) TSETMC flows, live, through
the relay.

## 12. The relay tested, branches cleaned, paper tables live, and the quant analyst (2026-10-04)

**The relay** (`gold-data-relay.mtnihrbp.workers.dev`, deployed by the owner; token as
proposed). The worker runs and accepts the token, but from Cloudflare's side on
2026-10-04 Daric answered 403 (0.4 s) and TSETMC 522, connection timed out (40-58 s) --
the same refusals as GitHub's runner. Cloudflare is not treated more kindly, on this
day at least; Daric's block varies by day, so the relay can still help on open days.
`/probe` checks sources one after another and outlived a 60 s client timeout behind
TSETMC; single `?url=` requests are the test to use. A reliable route for Daric and
TSETMC needs a server inside Iran (section 10's continuity server). The GitHub secrets
RELAY_URL/RELAY_TOKEN wait for the merge. (Local note: Windows uses Psiphon as its
system proxy here, so a "direct" request from this machine goes through Psiphon unless
the session ignores the environment.)

**Branches.** The nine `hotfix-*` branches, every one already contained in `main` and
referenced by nothing (cron-job.org and the worker dispatch `main`), were deleted from
GitHub and locally at the owner's request. Left: `main`, `SP-D`, `sp-d-paper` (active);
`SP-B`, `SP-C`, `safezone-v1.2`, `sp-d-direction` (all contained in `main`); `sp1` (one
commit of 2026-08-04 not in `main`).

**Paper tables in production** (owner: "yes the paper tables should come to alive in the
db"): `paper_accounts` (8 columns) and `paper_activity` (13 columns, the one-trade and
one-report partial unique indexes) created 2026-10-04 afternoon, 0 rows; existing tables
unchanged (700 market snapshots, 3 Direction panels). The code that writes them arrives
with the merge.

**The quant analyst** (`research/rd_quant.py`, `research/rd_quant_drivers.py`). The owner:
"the goal is to maximize the money it has at the beginning of the period vs the last
day ... maybe going back to more statistical and mathematical science ... slopes,
integrals". Maximizing end-of-period money, over many periods, is maximizing expected
log wealth (Kelly / Merton): the growth-optimal share in gold is f* = clip(mu/sigma^2, 0,
1) with cash at 0 and no borrowing or shorting, and with a cost c a no-trade band of
half-width (3/2 c f*^2 (1-f*)^2)^(1/3) around it (Davis-Norman). The analyst's whole job
becomes the drift mu, the slope of log 18K. Four estimates, fitted only on earlier years
(refitted every year 2016-2026) and filtered forward, never smoothed; sigma^2 the EWMA of
squared daily returns; Daric's 0.30% round trip:

```text
                                  2016-2023          2024-2026        2026 drop        01-29 -> 10-01
holding                           x26.19             x9.91            x0.79            x1.29
A Kalman slope (MLE)              x24.13             x9.91            x0.79            x1.29
B slope + its 10-day change       x22.68             x9.91            x0.79            x1.29
C dollar + world gold slopes      x10.39             x4.30            x0.84            x1.29
  + pull of the fair gap (OU)
D 18K's two regimes (Markov)      x30.91 (+18%)      x9.84            x0.79            x1.28
E dollar's + world gold's regimes x18.33             x9.92            x0.77            x1.25
  (each on its own trading days)
full Kelly; half Kelly lower everywhere but the 2026 drop (D: x0.80, E: x0.78)
```

What the mathematics says. The estimated drift is about +37% a year and almost never
negative (A: 1% of days), and against a daily variance near 0.06-0.09 a year mu/sigma^2
comes to 4-6, far above 1: the growth-optimal share is 100% nearly always. That is why
every timing rule of sections 9-11 trailed holding. D, the only estimate to beat holding
out of sample (+18% over 2016-2023), owes all of it to one year: 2018, the currency
crisis (x2.77 against x2.37, 119 trades, 140 days under 90% in gold); every other year it
trailed by about 0.3%. Its two regimes are calm and storm, both rising (+19% and +85% a
year): D is a volatility brake -- when swings explode, f* = mu/sigma^2 itself falls --
not a direction call. World gold's own two regimes, fitted properly on its own trading
days, are calm and volatile too, both rising (+10.8% and +8.6% a year); through 2026
its estimated drift never went below +8.6% a year. No estimate from returns -- slopes,
their change, regimes, the drivers' sum -- foresaw the 2026 fall, which began at world
gold's peak, a global turning point.

So the growth-optimal analyst is fully invested except in a volatility storm, and an
edge beyond that has to come from a better drift estimate, from information returns do
not hold: news, the funds' flows, world gold's turn. The framework prices it: any
signal that moves mu moves the grams through f* = mu/sigma^2, and its worth is the
growth it adds after costs. (Fitted on the first try with aligned calendars, world
gold's second "regime" was the Iranian weekend itself, zero variance and zero drift;
`native()` fits each driver on its own trading days.)

**The stale-series fix in production:** the 13:00 panel of 2026-10-04 (id 3) has world
gold's move as null, where panels 1 and 2 carried 0.0. World gold's tgju history had
reached 2022-05-31 (11,000 rows) and completes with the next two runs.

**Open:** which analyst pushes (the quant engine, or v1 with the quant engine as a
shadow); the news leg (GDELT history, an event classification); the Iranian server; the
GitHub relay secrets and the merge after the safe tag.

## 13. The brave trader under the brake, the chart in the report, free routes (2026-10-04)

**The owner's decisions.** (1) The brave trader pushes and trades; the quant engine runs
silently beside it. "With a good trading routine, instead of gaining 30 percent, user can
gain 50%; that's the key to beat the inflation." (2) "The core under this whole system is
being free: buying a server is a red line." (3) Start the news leg with GDELT. (4) Keep
the remaining branches for now. The efficient frontier and the chart in the message were
raised; the initial decision matrix (the system's own BUY/WAIT/SELL) is legacy and is not
to be touched -- the analyst/trader with the paper money is the new, separate thing. An
LLM through Groq may come in "if it helps; no help, no add".

**Trading more** (`research/rd_trade_more.py`, Daric's cost, against holding):

```text
                                         2016-2023                 2024-2026
volatility brake alone (quant engine)    +13.1%, 16 trades/yr      -0.7%, 4/yr
swing 20%, +5%, -2% or 5d, + brake       +11.2%, 26/yr             -7.0%, 25/yr
the same swing without the brake         +0.7%, 12/yr              -6.5%, 22/yr
swing 20%, +3%, -1.5% or 5d, + brake     +6.1%, 31/yr              -12.1%, 27/yr
swing 40%, +3%, -2% or 5d, + brake       -11.8%, 31/yr             -24.7%, 26/yr
```

The brake adds about 10 pp over 2016-2023 (2018's storm) for 0.5 pp over 2024-2026;
trading more -- a tighter target, a larger swing -- measurably costs more, because in a
steady rise every swing sold is gold that keeps rising. So the pushing trader is v1.1:
the +5% / -2% / 5-day swing under the quant engine's brake.

**Built** (`analysis/quant.py`, `analysis/paper.py`, `main.py`): the quant engine sizes at
f* = clip(mu/sigma^2, 0, 1), mu from 18K's two regimes (fitted once per Persian quarter,
the fitted parameters kept in the quant account's rows, filtered each run: 3.5 s to fit,
instant to filter), sigma^2 the EWMA variance, inside the Davis-Norman band for the
venue's own buy/sell gap. Its f* caps the brave trader's gold: above the cap the brake
sells down ("volatility brake: the growth-optimal share is 60%"), and buys stop at it.
Five accounts: analyst (v1.1, pushes), quant, cautious (v0), buy-and-hold, system. The
21:00 report gains "Quant engine, same money: ..." and goes out as the chart with the
report as its caption (353 characters against Telegram's 1,024), the text alone if the
chart fails. statsmodels 0.14.4 and matplotlib 3.10.3 pinned. On 2026-10-04's data the
engine reads a drift of +67% a year at 29% volatility: f* = 1.00, fully invested.
`kpi_paper` 24/24; full suite 30/30 files, exit 0.

**The efficient frontier, gold and the dollar** (tgju, 2014-2023): log drift 38% against
32% a year, volatility 30% against 36%, correlation 0.51; the growth-maximizing mix is
100% gold (x28.1 against x24.5 at 50/50 and x16.8 all dollar; 2024-2026 x10.2 / x7.4 /
x5.1). The dollar held up in the 2026 drop (x0.97 against x0.78). Under the contract
(gold or toman cash) the frontier is the Kelly line already used; a dollar sleeve -- the
brake parking in dollars rather than toman -- would be a contract change, the owner's
call.

**Free routes around the geo-blocking.** Measured: Daric refuses foreign addresses on
some days (GitHub's and Cloudflare's alike), TSETMC on all of them; GDELT is filtered
from Iran; and this machine, on an Iranian address, reaches Neon over plain HTTPS
(Neon's SQL-over-HTTP endpoint answered in 5.3 s, 2026-10-04), so no Postgres port is
needed. The options, all free:

```text
1  an Iran-side node on a device the owner already has and keeps on (an office or home
   PC, or an old Android phone with Termux): every hour it fetches Daric and TSETMC and
   writes them to Neon over HTTPS; the runner reads them from Neon. It is also the
   continuity node: in an Iran-only cut it keeps collecting into a local file and sends
   through Bale's bot API (domestic), and syncs to Neon when the link returns.
2  the same device as a GitHub self-hosted runner (free): workflows, or their Iran-only
   steps, run on it.
3  the Cloudflare relay, already deployed: Daric on the days it lets foreign addresses in.
4  free tiers of Iranian platforms (Liara, Hamravesh, ArvanCloud): to be checked; free
   credit is not the same as free forever.
```

The strongest is 1 (with 2 as its extension): it is free, it reaches every Iranian
source, and it is the continuity plan of section 10 without a rented server. It needs a
device that stays on and online.

**GDELT** (the news leg). Filtered from Iran; through Psiphon's shared exit it answers 429.
From GitHub's runner, one request per theme and year took 90 minutes for two and a half
themes (429s and slow answers) and was cancelled before its artifact step: nothing was
kept. The fetch now asks for 2017-2026 in one request per theme and mode, 10 s apart,
saves after every theme and uploads whatever it has. `research/rd_news_gdelt.py` is
written for the result: an event study of coverage jumps and tone falls against the
dollar's, world gold's and 18K's next 5 and 20 days, and the walk-forward drop detector
with and without news.

## 14. Faster, two trades a day, trend lines, GDELT's answer (2026-10-04)

**The owner.** "Faster is better, I can even expand the buy sell window from one daily to
max 2 daily; but I know this doesn't help that much." The chart needs trend lines (lows
joined to lows, highs to highs) and other tools. "Parking in dollars" needed explaining.

**Faster, and two trades a day.** The brave trader now takes its profit at +3% and buys
back 1.5% under the sale (5 trading days at the latest), under the same brake; at most
two trades per Tehran day for every account (`MAX_TRADES_PER_DAY`). Measured cost, from
section 13's grid: +3% / -1.5% with the brake came to +6.1% over 2016-2023 and -12.1% over
2024-2026 against holding (+5% / -2%: +11.2% and -7.0%). The owner's call, recorded.
The database held one trade a day with a partial unique index; `trade_no` (1 or 2) now
numbers each day's trades, `uq_paper_trade_slot` replaces `uq_paper_one_trade_a_day`, and
`ck_paper_trade_no` refuses a third (`sql/neon_migration_paper_two_trades.sql`). Verified
on the temporary branch temp-two-trades-test (since deleted): two trades accepted, a
third refused by the check, a duplicate number by the index. Not yet applied to
production.

**Trend lines and Fibonacci** (`caluclator/technical.trendlines`, `fibonacci`): of every
pair of confirmed swing lows (highs) whose line no later close crosses by more than 0.5%,
the support is the one closest under today's close and the resistance the one closest
over it -- as a chartist draws them. On 2026-10-01: support through the 06-17 and 07-26
lows, +0.50% a day, 21.99M today and 22.76M in ten days; resistance through the 07-18 and
09-10 highs, +0.63% a day, 26.55M and 27.77M. Fibonacci retracements of the current rally
(15.65M on 06-16 to 25.69M): 23.32 / 21.86 / 20.67 / 19.49M. The 21:00 chart draws both
lines from their first swing, projected ten days ahead (dotted), and the Fibonacci levels.
These are the chartist's tools, not tested signals; their edge is a matter for the
quarterly record.

**Parking in dollars, measured.** When the brake sells gold, the cash sits in toman. Held
in dollars instead (valued at tgju's dollar), the brake-only policy would have made x23.41
over 2016-2023 against x29.62 in toman (holding: x26.27), and x2.13 against x2.73 in 2018.
The brake fires in storms, and Iran's storms are dollar spikes that then correct: in 2018
it sold near the peak, and toman kept the correction that dollars would have taken. The
parking stays in toman.

**GDELT's answer** (`research/rd_news_gdelt.py`; fetched from GitHub's runner in one request
per theme, 2017-01-01 -> 2026-10-02, 3,530 days; some modes missing to rate limits):

```text
next 20 trading days after...            dollar     world gold   18K
all days                                 +3.58%     +1.05%       +4.60%
Iran military coverage jump (117 days)   +1.19%     +1.59%       +2.50%
Iran nuclear talks jump (122)            +2.15%     +0.80%       +2.42%
Iran coverage jump (118)                 +1.51%     +1.60%       +2.60%
Federal Reserve coverage jump (41)       +3.29%     +2.16%       +5.50%
drop detector (8%+ in 20 days), walk-forward: AUC 0.55 / 0.51 on prices alone,
0.53 / 0.54 with the news features (2019-2023 / 2024-2026)
```

Spikes in Iran coverage came near local peaks: 18K's next month was about 2 pp weaker than
usual. The counts and tone add nothing to the drop detector. Headline classification by an
LLM is the stronger form of the news leg; it can only be judged going forward, recorded
live and scored after a quarter.

**Routes.** Tunnels and proxies to get around the platforms' geo-blocking are not
pursued. The route that remains is a collector on a device the owner has inside Iran,
where the sources are normally reachable, writing to Neon over HTTPS (section 13).

**Temporary resources deleted:** the git branch probe-gdelt (its data kept locally,
git-ignored), the Neon branch temp-two-trades-test.

`kpi_paper` 26/26; full suite 30/30 files, exit 0.

## 15. A second trade, the chart's accuracy, Fibonacci, smart money; the LLM trader defined (2026-10-04)

**The owner.** The trader should act like a human expert, with no fixed rule: "I am setting
up a system and giving everything the system needs and then see what the system does."
How accurate is the chart, and how can its accuracy be locked above 95%? Does a second
trade a day (a maximum, not a must) increase profit significantly? Does Fibonacci help
the trader decide, or is it only drawn? Parking in dollars is not possible in reality:
dropped. Smart money and hot money in the gold funds (Ayyar and the like: volume
profile, LIT) would be a better call than the news alone. Groq runs from GitHub; first
define what we want from an LLM.

**A second trade a day** (`research/rd_two_trades.py`, production's hourly readings,
2026-08-04 -> 10-04; Daric's own series has 32 of the 62 days, the runner was refused on
the rest). The swing rules of sections 10-14, replayed at every reading, came to the same
money with one or two trades allowed (Daric 184.5-185.3M with either, Goldika
181.0-182.5M; holding 187.3M and 186.4M): the second slot fired on at most one day. The
ceiling is a trader who knew every coming price, all in or all out:

```text
end value from 135M toman              hold     1 a day   2 a day   the second adds
Daric, its own 32 days                 188.1M   226.3M    229.4M    +1.4%
median platform, Daric's 0.30%, 62 d   195.2M   264.7M    280.8M    +6.1%
median platform, Goldika's 2.37%       191.2M   207.7M    207.7M     0.0%
```

The money is in being right about the direction, not in trading more often; even perfect
foresight gains 1-6% from the second slot over two months, and nothing at Goldika's cost.
The maximum stays at two: it costs nothing when unused.

**The chart's accuracy** (`research/rd_chart_accuracy.py`, tgju daily 2014-2026, every
line drawn as the 21:00 chart draws it, from the days before only). Each line against a
CONTROL: the same kind of line at a distance from the price taken from another day, so it
carries no information about this day's swings.

```text
                         10-day projection held   bounced at the first touch (3% off before 2% through)
trend line, support      79.0%  (control 78.8%)   34.6% of 335  (control 48.2%)
trend line, resistance   67.2%  (control 67.2%)   20.0% of 489  (control 27.8%)
swing level, support     81.7%  (control 76.2%)   56.0% of 350  (control 54.7%)
swing level, resistance  57.1%  (control 55.8%)   20.9% of 479  (control 24.9%)

a line with no history, 10-day projection held:
support     1% away 60%, 2% 73%, 3% 81%, 5% 90%, 8% 95%, 10% 97%
resistance  1% away 39%, 2% 49%, 3% 59%, 5% 74%, 8% 86%, 10% 90%
```

A line's "accuracy" is set by its distance from the price: any support 8% under the price
holds 95% of ten-day spans. 95% can therefore be had by drawing lines far away, and it would
say nothing. What counts is the edge over the control, and on 18K the trend lines and swing
levels have none; at the touch, trend lines did worse than the control. The value-area
edges of the volume profile remain the only level with a measured edge (section 11).

**Fibonacci** is drawn, not used, and the record does not argue for using it: inside a
rally (8% ZigZag), the first touch of a retracement from above bounced 61.0% of 292 times
at 23.6/38.2/50/61.8% against 63.8% of 475 at 15/30/44/56/70%.

**Smart money and hot money** (`research/rd_smart_money.py`; 19 gold funds, 1,665 days,
2017-06 -> 2026-09; entry one trading day after the flow is public). Individuals' net
inflow, buyer power (individuals' value per buyer over value per seller) and value-traded
surges, against 18K's next 1, 5 and 20 days. Buyer power was the one signal with the same
sign in both periods (top against bottom 10% of days, 5 days on: +1.44% / -0.31% in
2019-2022, +1.66% / +0.35% in 2023-2026). It does not survive the checks: removing 18K's
own last 1/5/20 days and a circular-shift bootstrap that keeps the autocorrelation, its
IC falls to +0.05 (5 days) and +0.06 (20 days), which luck matches 28% and 37% of the time;
5-day inflow +0.09, 13%. The funds follow 18K (18K yesterday against the funds today +0.42;
the funds today against 18K tomorrow -0.01). Daily flows carry no usable lead; intraday
flows (the order book, LIT's sweeps) have no history to test, and TSETMC refuses the
runner.

**What the LLM is for: the discretionary trader, defined.** No single tool has an edge on
18K over twelve years -- lines, levels, Fibonacci, news counts, fund flows -- and the
owner's experiment is the one that remains: give a judge everything, and record what it
does. Proposed, not built:

```text
account     llm-analyst-v1, a sixth PAPER account, same contract and money
when        each scheduled run (06:00-21:00 Tehran), one request; well inside Groq's free tier
input       an evidence brief the system computes, never the model: both sides per venue,
            the book, trades left today, 18K's last 120 days in summary, levels, trend lines,
            Fibonacci, value area, dollar and world gold, the quant engine's share, news
            headlines, the measured reliability of each input (this section), the quarter's
            goal and its result so far
output      JSON only: action BUY/SELL/HOLD, whole grams, confidence, reasons naming the
            inputs, what would change its mind
checks      the contract decides: cash, grams, two a day, a fresh two-sided quote; a malformed
            or impossible answer is HOLD with the reason logged; every answer stored in the
            EVAL row's inputs, with the model name
scope       PAPER only; never final_decision, the alerts, or the legacy matrix
judged      forward only, at the quarter's end against holding, the brave trader and the
            quant engine; a backtest is contaminated, because the model has read the history
```

`CLAUDE.md`'s rule that an LLM never acquires BUY/SELL authority is about the system's
decisions; this account would be an explicit, owner-approved exception confined to PAPER.
No schema change: accounts are rows and the EVAL row's `inputs` is JSON.

**Routes.** Unchanged from section 14: no tunnels or proxies around the sources'
geo-blocking.

## 16. Groq checked, one front office, sideways markets, fixed-income parking (2026-10-04)

**The owner.** GROQ_API_KEY is added. The owner will look into an Arvan or Liara service
personally. One trader faces the owner: "the front office is one person buying, holding or
selling"; a BUY or SELL is pushed, a HOLD appears in the 21:00 message with a summary, and
any other decision makers stay in the back office. Can the system understand a sideways
market ("for a long time the price was in 18m channel, up down side, then it jumped up up
up ... knowing the side and the start of the new jump is a key decision")? And park cash
in a fixed-income ETF such as Afran.

**Groq, from GitHub's runner** (temporary branch probe-groq, since deleted; the key never
printed). The key answers. Text models offered: openai/gpt-oss-120b, openai/gpt-oss-20b,
qwen/qwen3.8-27b (131k context). Free-tier limits on gpt-oss-120b: 1,000 requests a day,
8,000 tokens a minute. All three returned a valid decision under a strict JSON schema;
gpt-oss-120b needs room to reason (600 completion tokens failed, 4,000 with medium
reasoning used 1,287 in 2.1 s). Its answer was sound (HOLD: the cash could not cover a whole
gram) but named Daric's sell price as its buy price: the contract, not the model, has to
check every number.

**One front office.** Already so in code: only the analyst account pushes, and the 21:00
report shows its book with two comparison lines (holding, the quant engine). The other
accounts are the back office: the yardsticks that say whether the front office is any good,
with buy-and-hold the bar to beat. The owner's rule recorded: the front office pushes BUY
and SELL; HOLD and its reason go into the 21:00 message.

**Fixed income** (`research/fetch_tsetmc_fixed_income.py`, from Iran, direct; 21 funds;
`research/rd_sideways.py` section 1; a distribution counted at the fund's usual accrual):

```text
            2016   2017   2018   2019   2020   2021   2022   2023   2024   2025   2026*
index      23.1%  23.2%  20.6%  23.2%  38.9%  19.5%  22.2%  25.9%  29.1%  33.6%  26.2%
18K        18.0%  21.2% 139.8%  43.5% 141.4%  12.0%  43.4%  36.5% 105.0% 171.4%  81.0%
Afran                                  46.6%  22.1%  23.6%  27.7%  31.5%  36.1%  27.8%
* to 2026-10-03. Afran over the last 12 months: 38.5%.
```

Fixed income beat 18K in 3 of 11 years (2016, 2017, 2021). TSETMC refuses GitHub's runner,
so Afran's daily price can reach production only from an Iranian connection.

**Sideways, measured** (`rd_sideways.py` section 2). Kaufman's efficiency ratio (net move /
total movement) against a random walk's 1/sqrt(N); the main definition, 60 days under a
random walk (0.13), was fixed before any policy was run. A fixed range cap misses 1405, when
18K moved 2-3% a day: the owner's channel spans 19-23% over 40 days.

```text
since 2014, next 20 / 60 days         18K               fixed income
all days                              +3.70% / +11.59%  +1.61% / +4.95%
sideways (37% of days)                +1.70% /  +7.81%
other days                            +4.93% / +14.04%
the 1405 channel (2026-02-01 -> 08-17): 74% of its days flagged sideways
18K beat fixed income over the next 60 days on 54% of sideways days
```

In 1405 the detector flagged the channel from 1404/12/28, called a break down on 1405/03/25
at 16.3M (false: 60 days later +36%) and a break up on 1405/05/20 at 19.2M (+20% in 20
days). Since 1393, a break out of a sideways market is followed by an ordinary month:

```text
                                  events  next 20 days   next 60 days   back through the middle in 20 days
up out of a range                 20      +3.58% (+3.70)  +11.75% (+11.59)  15%
down out of a range               16      +4.18%          +11.14%           38%
new 60-day high, no range         24      +7.39%          +13.56%            0%
```

The system can see a sideways market, and in it 18K has earned about what fixed income
earns (+1.7% against +1.6% over 20 days). It cannot tell the start of the jump from a false
break: up-breaks average the same as any day, and down-breaks are mostly false in toman. What
carries forward is a new high inside a trend (+7.4% over 20 days): selling into strength,
as the brave trader's +3% take-profit does, sells into the strongest stretch.

**Policies with the parking** (signal at day i, trade at day i+1's close, Daric's 0.30%; a
sale's cash reaches the fund 2 trading days later and comes back 2 days after it is called;
the fund's round trip 0.10%):

```text
against holding               2016-2023 (x26.19)          2024-2026 (x9.91)           1405 channel and jump (x1.43)
cash: idle | parked | parked after 5 idle days
brake only                    +12.6% | +4.0% | +17.5%     -0.6% | -1.3% | -1.0%       -0.6% | -0.9% | -0.9%
brave + brake                  -2.0% | -8.1% |  -0.7%    -16.1% |-17.0% |-16.4%       -0.1% | -0.7% | -0.5%
sideways: 50% out             -23.4% | -4.1% |  -9.1%    -15.1% | -7.4% | -7.0%      -10.4% | -6.6% | -4.2%
sideways: 100% out            -43.7% |-12.5% | -20.0%    -29.0% |-16.3% |-15.2%      -20.7% |-14.5% | -9.8%
trade the channel (40%)        -8.6% | -6.1% |  -9.3%     -4.5% | -3.1% | -4.6%       -2.6% | -0.4% | -0.8%
```

Parking idle cash in fixed income helps every policy that leaves cash out for weeks (the
brake: +12.6% to +17.5% against holding over 2016-2023), and costs those that trade within
days (the 2-day transfers). Leaving gold for fixed income because the market is sideways
lost in every period: the jump comes without warning, and toman's sideways markets end up
more often than down. Trading the channel (selling in its top quarter, buying back in its
bottom quarter, all in outside it) lost far less than the brave trader in 2024-2026.

**Proposed, for the owner's decision:**

- The front office is the LLM trader of section 15, the one that weighs everything; the
  brave trader, the quant engine and the system's own decision go to the back office;
  buy-and-hold stays the bar. The 21:00 message: the trader's day (what it did, or HOLD and
  why), the book against the quarter's start, and one line for holding.
- Cash idle 5 trading days goes to fixed income (Afran), 2 days each way, 0.10% the round
  trip. Afran's price needs an Iranian connection: until the Iran-side collector exists,
  the parked cash accrues at Afran's last published 12-month return, marked as an estimate,
  and is settled when the real price arrives. Not built; the contract changes before
  PAPER goes live, not mid-quarter.
- The sideways state, its 60-day range and any break go into the trader's evidence as
  facts with their measured record, not as rules.

## 17. The convergent front office, parking the sale in fixed income, and the way back to gold (2026-10-04)

**The owner.** "The front office can be a convergent decision made at back office,
including the llm; explore the idea." The contract: the system buys 5 grams, sells 2 and
holds 3; the 2 grams' cash goes directly into fixed income; when it wants to buy, it pulls
the money out, buys, and adds to the 3 grams. On the sideways market: "understanding the
move is a key; we have to find a proper answer to this, to take the money out of fixed
income and buy gold. This is one of the key questions."

**The question, made precise.** With cash in fixed income the growth-optimal share in gold
is f* = (mu - r) / sigma^2, r the fixed-income return; section 12 had r = 0, so f* was 100%
nearly always. Taking the money out of fixed income is a call that gold will beat fixed
income from here. Target: 18K over the fixed-income index over the next 20 and 60 trading
days. Gold beat fixed income over 60 days on 57% of days in 2018-07 -> 2023, 71% in
2024-2026, 29% inside the 1405 channel and its jump; over 2018-07 -> 2023, 1 toman became
x10.48 in gold and x3.50 in fixed income, over 2024-2026 x9.91 and x2.17.

**The candidates** (`research/rd_rebuy.py`; rank correlation with gold over fixed income,
and how often a circular shift that keeps the autocorrelation does as well):

```text
on sideways days                      2016-2020 20d / 60d          2021-2026 20d / 60d
real dollar (dollar / fixed income    -0.00 (100%) / -0.01 (99%)   -0.20 (8%) / -0.43 (0%)
  against its 500 days; low = behind)
fair gap (18K to world gold x dollar) +0.13 (43%) / +0.06 (76%)    -0.27 (0%) / -0.22 (1%)
dollar's last 20 days                 +0.35 (0%) / +0.32 (10%)     +0.01 (93%) / +0.09 (49%)
real gold, world gold 60 days, quiet, sideways age: no consistent sign
```

Inside sideways markets in 2021-2026, gold beat fixed income by +8.4% over 60 days in the
fifth of days with the dollar furthest behind the cost of money, against -1.9% in the fifth
with it furthest ahead; nothing of the kind in 2016-2020, when the dollar's own momentum led
instead. What says gold will beat fixed income changes with the era.

**The committee** (`research/rd_committee.py`; the members above, z-scored on their own 500
days; weights from outcomes known at the time). VOTE averages the members with the sign of
their record, RECORD weights them by it, RIDGE regresses gold over fixed income on all of
them. Out of sample: no skill in 2018-2023 (IC -0.02 to -0.07, the sign right 49-51%), a
little in 2024-2026 (IC +0.05 to +0.09). The records reverse with the era: the dollar ahead
of the cost of money pointed to gold at +0.76 in 2018 and away from it at -0.56 from 2021,
so a record-weighted committee follows the last era's lesson and is wrong at the turns.

**The contract, as the owner set it** (a core in gold and a swing that sits in gold or in
fixed income; sales go to fixed income and buys come out of it, at once -- lag 0 -- or in
2 trading days each way; Daric's 0.30% and fixed income's 0.10%):

```text
against holding gold                      2018-07 -> 2023     2024-2026          1405 channel and jump
lag 0 | lag 2
core 60%, swing always in fixed income    -28.6% | -27.5%     -42.6% | -42.8%    -4.4% | -9.6%
swing by RIDGE                            -15.1% | -14.9%      -2.6% |  -6.7%    +2.4% | -10.9%
all or nothing by RIDGE                   -36.9% | -43.2%      -9.5% | -12.6%    +6.0% | -11.0%
consensus to leave, doubt to return (the swing leaves on 4 of 5 members with economic
  signs, returns when 1 or none remain)   +14.1% | +16.5%      -1.9% |  -6.6%    +1.7% | -8.1%
  the same with signs from the record     -19.8% | -17.5%      -8.7% | -10.1%   +10.5% | +4.9%
```

Every variant trails holding in at least one period; the best, consensus on economic signs,
beat it over 2018-2023 and trailed over 2024-2026, and it is the best of twelve variants,
so the number flatters it. In the 1405 channel RIDGE said "gold" throughout, while fixed
income beat gold by 3-13% over 60 days. A 2-day transfer costs 8-13 pp in a market moving
like 1405.

**So, on the key question.** The system can see a sideways market (section 16). Nothing in
prices, the dollar, world gold, the fair gap, the funds' flows or the age of the range says
when the jump out of it begins, consistently across eras. The jumps on record (1397, 1399,
1404, 1405) were the dollar's, after political and economic events; the one member that
could see such events coming is the news, read live by an LLM and scored forward.

**The convergent front office, proposed:**

```text
back office (each logs its view at every run, scored against what follows):
  the brake (volatility), the market state (sideways or trend, the range), the drivers
  (real dollar, fair gap, world gold, the dollar's momentum, each with its economic sign),
  the LLM (the headlines and everything above), holding (the bar)
front office, one decision:
  default: the grams stay in gold, since gold beat fixed income by x3 over 2018-2026
  sell part (the 2 of 5 grams) only on consensus: a supermajority of members, the LLM among them
  the money goes straight to fixed income (Afran)
  bring it back as soon as the consensus breaks: leaving gold is the expensive mistake,
  returning the cheap one
  equal weights, since the records reverse with the era; the records kept and shown, so
  the owner sees who has been right
the LLM's place: one vote, with the reasons in words; it never computes a number
```

Not built; the owner's decision. `kpi_paper` and the suite unchanged.

## 18. Weights for the stronger members, extrapolation, smart money, and ArvanCloud (2026-10-04)

**The owner.** "From these committee members there are some who tend to be stronger; let's
give them a heavier weight, and later on we can adjust, as we learn and see the quality of
decisions." "Something I like to see is extrapolation, and bringing the money flow and smart
money insight in." ArvanCloud's free offer: arvancloud.ir/fa/products/vps/free and
/en/pricing/free.

**ArvanCloud.** Both pages, and docs.arvancloud.ir, answer every client that is not a full
browser with a JavaScript check ("Transferring to the website..."): from Anthropic's fetcher
and from this machine in Iran alike. It was not bypassed. Public sources give paid plans
(eco-small2: 1 vCPU, 2 GB, 25 GB SSD, about 6 EUR a month) and mention a free offer without
its terms. What decides its use here, for the owner to read off the page: free for good or
for a trial (a trial that ends is a paid server, the red line); size (1 vCPU, 1 GB and Linux
are enough); identity checks (the owner's call); whether it reaches Neon abroad, and what it
does when international traffic is cut; whether Daric and TSETMC treat its address as
Iranian. Its role: a collector that reads Daric, TSETMC (the funds' flows, their NAV, Afran)
and writes its own readings to Neon under a role that may only insert into its tables -- not
a relay for GitHub's requests. Its tables are a schema change (migration, temporary branch,
authorization).

**Weights.** Measured strength (sections 12, 16, 17) sets the starting weights; nothing was
strong in both eras, and weights chosen from the whole record flatter any replay of them, so
their test is forward. Proposed:

```text
member                          weight   evidence
the brake (volatility)          2.0      the only member to beat holding out of sample (2018)
fair gap (18K / fair value)     1.5      2021-2026 sideways days: IC -0.27 (20d), luck 0%
real dollar (dollar / cost      1.5      2021-2026 sideways days: IC -0.43 (60d), luck 0%
  of money)
market state (sideways, trend)  1.5      sideways days earn about fixed income; a new high in
                                         a trend +7.4% in 20 days against +3.7%
dollar's momentum (20 days)     1.0      2016-2020: IC +0.33, luck 0%; weak since
the LLM                         1.0      no record yet
world gold (60 days)            0.5      weak; the 2026 fall began with it
money flow (gold funds)         0.5      no lead once 18K's own moves are removed (section 15)
```

The swing leaves gold when the members favouring fixed income hold at least 60% of the
weight, the LLM among them, and returns when they hold 30% or less. At each quarter's end
every weight is multiplied by (1 + its score), the score its share of right calls minus 50%,
bounded 0.25-3; the new weights apply from the next quarter, like every rule change.

**Extrapolation** (`research/rd_extrapolation.py`, walk-forward 2016-2026). A direction cannot
be called 95% of the time; a band can be built to hold the price 95% of the time:

```text
held the price (80% band | 95% band)   2016-2020            2021-2026            95% band, about
bell curve           5 days             77% | 90%            80% | 91%            +/- 7.6%
                    20 days             73% | 90%            73% | 89%            +/-15.8%
18K's own history    5 days             78% | 95%            80% | 95%            +/- 9.5%
                    20 days             79% | 93%            79% | 95%            +/-19.9%
                    60 days             68% | 86%            81% | 95%            +/-49.9%
```

The band from 18K's own past moves (filtered historical simulation) holds what it says at 5
and 20 days; the bell curve does not (18K's tails are fat). The centre line: extrapolating
the quant drift misses by a little less than "no change" at 20 days (3.9% / 4.3% typical
miss in 2016-2020, 5.3% / 5.7% in 2021-2026) and by more at 60; extrapolating the 60-day
line is worse at every horizon, and its direction is right 58-65% of the time against
18K's 68-75% of rising. From 1405/07/09 (25.69M): in 20 trading days the centre is 26.85M,
80% between 24.58 and 31.05M, 95% between 23.31 and 32.89M; in 60, 95% between 23.24 and
46.83M. A preview with the cone: research/data/extrapolation_preview.png (the 21:00 chart is
unchanged).

**Smart money.** The funds' premium over their NAV is the hot-money reading (units bought
faster than the gold under them). TSETMC publishes today's NAV only: on 2026-10-04 Ayyar's
redemption NAV was 716,994 rial against its close of 746,487 the day before, about +4%. A proxy
from prices (the funds' close against 18K the day before, against their own 60 days) showed
nothing (IC +0.00 at 5 and 20 days, luck 81-89%) and read -7.1% on 2026-09-30: it does not
measure the premium. The real premium's record has to be built from now on, daily, by a
collector in Iran; the funds' flows were tested in section 15 (no lead). Proposed: the
premium, individuals' net money into the gold funds and buyer power as one line in the 21:00
message and as the money-flow member (weight 0.5), scored as its record grows.

## 19. NEoWave, the other tools for this market, and where tomorrow starts (2026-10-04)

**The owner.** For the record, to close the day: does the NEoWave method help us? Are there
other techniques that help in this market, or to equip the committee of experts?

**NEoWave** (Glenn Neely's rule-bound extension of Elliott waves) labels each swing as a
wave and reads the next one from the count, the waves' price ratios (Fibonacci) and their
time ratios. Its pieces were measured here: the swings (ZigZag legs, section 4), Fibonacci
retracements (no edge, 61.0% against 63.8% at other depths, section 15), the levels drawn from
swings (no edge over a control, section 15). The count itself is discretionary: two
practitioners count the same chart differently, and a count is revised once the next swing
shows it wrong, so a replay of it is hindsight. No published out-of-sample test known to us
shows Elliott or NEoWave beating a simple benchmark. It does not join the committee. A
mechanical version (ZigZag swings, Neely's rules as code, a call made only on confirmed
swings) could be tested like any member; it ranks below the candidates that follow.

**Candidates for the committee, in the order proposed for testing** (data: R = reachable from
GitHub's runner now, I = needs the collector in Iran):

```text
1  dollar in Tether (USDT/IRR on Iranian exchanges, 24/7)   I   leads the bazaar's dollar on nights, Fridays and
                                                                holidays: the first sign of a dollar jump
2  the coin's bubble (Emami coin over its 7.32 g of gold)   R   tgju's coin prices; the Iranian market's own fear
                                                                and demand gauge, years of history
3  the dollar's gap to the official rates (exchange        R   tgju; devaluation pressure building before the
   centre, NIMA)                                                free market moves
4  change-point detection (Bayesian online, Adams-MacKay)   R   math on the prices we have: the end of a sideways
                                                                market, faster than a fixed 60-day window
5  the money's rotation: Tehran stock index against gold    R/I money leaving one market for the other
6  bond yields (government bills on TSETMC): expected      I   the market's own inflation expectation; rising
   inflation                                                    yields, a weaker rial ahead
7  the scheduled-event calendar (talks, IAEA boards,        R   known in advance; the LLM keeps it; Iran coverage
   sanctions deadlines), read by the LLM                        spikes came near local peaks (section 14)
8  the platforms' order book (Daric's best bid and ask,     I   the physical market's own order flow, the LIT/AMD
   their spread and depth)                                      idea on 18K itself; forward record only
9  meta-labelling (a second model judges whether to trust  R   on the committee's own calls once their record exists
   a member's call)
```

For the decision layer the mathematics already in place stays: the growth-optimal share with
fixed income as the bar (sections 12, 17), the bands from 18K's own history (section 18), and
weights moved by each member's record at the quarter's end (section 18).

**Where tomorrow starts.** Open for the owner: the weights and the 60% / 30% rule (section
18); the cone on the 21:00 chart and its line (section 18); ArvanCloud's terms (section 18);
the two-trades migration on production (section 14); the merge after the owner's review,
with a safe tag first. Research first: candidates 2, 3 and 4 above, all testable from
GitHub's runner's data. Build after the owner's answers: the committee members' logging,
the LLM member on Groq (openai/gpt-oss-120b, section 16), fixed-income parking (lag 0, Afran's
price an estimate until the collector), and the 21:00 message.

## 20. Health check 2026-10-05 10:15, made a routine

**The routine** is now `PROJECT_OPERATIONS.md` section 15: runs, freshness, platforms, why a
platform is missing (the run log), decisions and the degenerate check, daily candles, PAPER,
a one-line verdict.

**Since the last check** (2026-10-04 10:15 to 2026-10-05 10:15 Tehran): every scheduled
ANALYZE ran and succeeded, 16 on 10-04 (06:00-21:00) and 06:00-10:00 on 10-05, 5-10 minutes
each; the owner's UPDATE at 10:24, 13:35 and 15:51 and DIRECTION at 13:37. In the last 24
hours: 19 market snapshots and market states, 16 analysis snapshots, 48 outcomes, 214 price
observations, 458 news items; Direction panels for 10-04 06:00 and 13:00 and 10-05 06:00;
tgju's 18K and dollar candles to 10-04 (collected 06:03), world gold to 10-03 (the
weekend). `paper_activity` 0 rows, as expected before the merge.

**Platforms.** Nine of eleven in every reading. **Daric**: 403 on every run since
2026-10-03 18:50 (its side, refusing the runner); PAPER's first venue, so PAPER falls to
Goldika. **Taline**: in 6 of 19 readings; the other 13 discarded by its 1% band ("stale copy
suspected", -1.15% to -2.43% from the median, 10-04 07:00-17:00 and 10-05 07:00). On 10-05 it
reported 263,855,000 at 06:01, 08:01 and 09:01 while the others moved: the frozen copy the
Iranian CDN serves the runner. The band caught it at 07:00; the 06:01, 08:01 and 09:01 copies
were within 1% (-0.23% to -0.31%) and were stored. Small, noted, not fixed: the repeat rule
defers a repeat only beyond 1.0 pp from its usual position, by design. **Goldika**:
discarded once (10-04 07:00, priced 19 hours earlier by its own time stamp), otherwise in.

**Decisions.** WAIT on every reading; one BUY candidate (10-04 10:01, heavily discounted,
held by the confirmation: the dollar was not yet today's, section 8). `final_decision` WAIT
637, BUY 4 since the start; `structure_state` DISCOUNT_DOMINANT throughout (registered).

**Verdict:** healthy. Open: Daric refused from the runner (the Iran-side collector);
Taline's frozen copies within the band.

## 21. The chartist (2026-10-05)

**The owner.** "We are missing a chartist in the committee room, the one who can read
charts, identify trends, sideways and so on. Explore this idea: a system that can see
channels, and technically analyze the chart."

**What it reads** (`research/chartist.py`, causal; `research/rd_chartist.py` tests it):
swings from a ZigZag whose threshold is 3 x ATR(14) as a share of the price (bounded 3-15%,
so a swing means the same in a calm year and in 1405; 6-14 swings a year); Dow structure
from the last two swing highs and lows (UP, DOWN, CONTRACTING, EXPANDING, RANGE); ADX and
the 50-day EMA's slope; the channel of the current leg (from the last confirmed swing:
slope, R^2, the price's place in it); the sideways box; patterns -- breakout and breakdown,
Wyckoff's spring and upthrust (against the box as it stood that day), bear and bull traps
(a close through the last swing, back within 10 days), double top and bottom, squeeze,
divergence with RSI, a flag; the phase (MARKUP, MARKDOWN, ACCUMULATION, DISTRIBUTION, by the
leg into the range; a breakout carried by a rising EMA50 is MARKUP before its swing
confirms). The view: a textbook chartist's score, fixed before the test (phase +/-0.5 or
0.25, breakout and spring +0.5, breakdown and upthrust -0.5, the rest +/-0.25, clipped to
+/-1). Three corrections after reading its own charts, before scoring: the phase rule (the
leg into the range, not 120 days back), the spring's box (that day's), and the channel's
start (the current leg, not the one before).

**1405 as it read it:** markup through the winter; a breakdown and double top at the
1404/12/24 gap (20.12M to 16.92M); markdown in Farvardin; a breakout in Ordibehesht that
failed; a breakdown on 1405/03/25 at 16.30M and a bear trap on 1405/04/07; the box 15.7-20.3M;
the break on 1405/05/31 at 21.04M read as MARKUP, score +1.00, held since; today a rising
channel from the 15.65M low, +0.55% a day, the price at 0.64 of it
(research/data/chartist_preview.png).

**What it is worth** (gold over fixed income in the next 20 / 60 days):

```text
                      2016-2020          2021-2026          last 2 years (2024-10-05 -> 2026-10-01)
all days              +2.02 / +5.90      +2.15 / +6.28      +4.20 / +12.06
after a breakout      -0.91 / -5.11 (12) +3.27 / +10.86 (15) +7.75 / +17.07 (5)
after a flag          +5.15 / +16.33 (11) -0.05 / +4.90 (10) +2.52 / +6.14 (5)
after a bear trap     -5.55 / -2.81 (6)  +1.42 / +1.48 (13) +2.56 / +2.56 (6)
after a squeeze       -4.59 / -2.03 (10) -1.53 / +1.41 (18) +4.49 / +17.65 (4)
days in ACCUMULATION  -3.81 / -2.64      -1.49 / +1.90      +1.69 / -0.94
the view's rank correlation: +0.04 / +0.12 (luck 81% / 56%), +0.10 / +0.10 (38% / 57%), +0.00 / +0.01
at swing thresholds of 2, 4 and 5 x ATR: +0.03 to +0.22 over 2016-2026, -0.14 to +0.18 in the
last two years
```

It reads a chart coherently and in a chartist's words, and its view leans the right way over
ten years at every threshold tried, weakly; no pattern keeps its sign across the eras (a
breakout was followed by -5.1% against fixed income over 60 days in 2016-2020 and +10.9% in
2021-2026). As a decision maker alone it never beat holding in any two-year window (section 22).
Its place: the describer of the chart for the owner and for the LLM chair, and a light
member of the committee.

## 22. The committee room replayed: who should decide (2026-10-05)

**The owner.** "Back testing the committee room for the last two years and see which one
could be a better judge and DM to call on buy sell."

**The replay** (`research/rd_committee_2y.py`). The owner's contract: 135M toman on 1403/07/14
(2024-10-05), whole grams of 18K at tgju's close with Daric's 0.30% round trip, all in gold on
day one; the swing is 40% of the grams (the owner's 2 of 5); a sale's cash goes straight into
Afran at its own daily total return and comes back for the next buy (0.10% in and out); to
1405/07/09. 18K rose 520% over the two years, Afran 86%. The members' leans (+1 gold, -1 fixed
income, 0 none), all causal: the brake (f* under 0.9), the market state (sideways without a new
60-day high; a new 60-day high), the fair gap, the real dollar, the dollar's 20 days, world
gold's 60 days, the gold funds' buyer power (20-day mean), the chartist (section 21). The
engine agrees with hand calculations (holding 825.2M against 835.1M by hand, the difference
the whole grams; 60/40 throughout 591.7M against 603.1M).

**The last two years**, each decision maker acting daily: market state alone +6.4% against
holding (878.1M against 825.2M, 21 trades, 6 of 10 exits right), the channel trader +2.9%, the
brake -1.2%, the committee with the proposed weights -1.7% (7 trades; it read +3.9% before the
chartist's channel was corrected -- one window's number moves 5-6 points on one member's
detail), equal weights -3.6%, learned weights -10.6%, each member alone -7% to -22%, the brave
trader -23.1%. The quarters show where: being out in 1405 Q1 (world gold's fall, +6.5 to
+9.6 points) and out at the start of the jump in 1405 Q2 (-7 to -12 points).

**As judges, against the base rate** (gold beat fixed income over 20 days on 69% of the two
years' days): when it said fixed income, fixed income won -- money flow 53% (87 days), market
state 44% (180), dollar 20d 42%, real dollar 35%, fair gap 34%, chartist 26%, world gold 25%
(the last two below a coin's 31%).

**Every two-year window** (18 windows starting each Persian quarter, 1399 Q2 -> 1403 Q3, Afran;
consecutive windows share most of their days, so they amount to about three independent
periods): acting daily, the committee with the proposed weights +1.9% median against holding
(56% of windows), the channel trader +0.4% (67%), every member alone below holding (market
state -7.1%, chartist -5.0% and never ahead), learned weights -6.7%, follow-the-leader -7.7%.
Leave-one-out (`rd_committee_ablation.py`): without the market state the committee falls to
-2.2% (17% of windows), without the fair gap -1.3%, without money flow -1.4%; without the
chartist +2.2%, without the dollar's 20 days +1.2% (they add nothing); without the brake +4.5%
but its worst window -9.2% and the last two years -10.6% (the brake is insurance).

**The finding: act on the consensus every two to four weeks, not every day**
(`rd_committee_cadence.py`, `rd_committee_cadence2.py`; the committee's view moves every day,
the swing moves only on the decision day; every offset of each cadence run):

```text
median gain over holding (range over offsets) | windows beating holding | worst window
                         Afran windows from 2020 (18)            fixed-income index from 2018 (27)
proposed, every day      +1.9%          56%        -5.2%         +1.9%          63%        -9.2%
proposed, every 5 days   +5.8 to +7.6%  78-94%     -3.4%         +5.7 to +7.8%  81-93%    -15.3%
proposed, every 10 days  +6.7 to +9.0%  94-100%    -2.9%         +5.5 to +8.9%  85-93%    -21.2%
proposed, every 20 days  +7.6 to +9.7%  89-100%    -3.3%         +7.2 to +8.6%  85-89%    -13.9%
equal,    every 10 days  +4.5 to +7.7%  67-100%    -6.5%         +4.7 to +8.1%  70-93%    -21.7%
equal,    every 20 days  +4.2 to +8.6%  72-100%    -9.1%         +6.7 to +8.1%  74-89%    -16.7%
leave every 10 days, back at once (proposed)
                         +4.6 to +7.3%  83-94%     -6.0%         +3.7 to +5.9%  85-96%    -12.0%
```

The daily committee flickers around its thresholds; checked every two to four weeks it stays
on the slow moves and trades less. The result holds at every offset, with equal weights
(so not only through the hindsight in the proposed weights) and from 2018 with the index.
Its tail is real: a window that began before 2018's currency spike lost 21% against holding,
out of gold during the jump. Coming back to gold at once when the consensus breaks halves
that tail (-12%) for 2-3 points of median.

**The LLM chair**: section 23.

## 23. The LLM as the committee's chair, replayed (2026-10-05)

**Why it can be replayed.** openai/gpt-oss-120b's knowledge ends in mid-2024 by its model
card; the window starts in October 2024. The briefs (`research/rd_llm_judge.py build`) also
carry no dates and no price levels: 18K, the dollar and world gold appear as indexes (today =
100) and changes. One brief every 5 trading days (115), about 870 tokens: the contract (the
40% swing, gold or fixed income, for the next 5 trading days), the position it chose last
(fed back on the runner), 18K's path and moves, volatility, fixed income's yield, the dollar,
world gold, the fair gap, the chartist's reading, and each member's lean with its record so
far against the base rate. Run on GitHub's runner (temporary branch probe-llm-judge,
`probe/llm_judge.py`), strict JSON, reasoning effort low: 115 of 115 valid, no rate-limit
stop, about 1,470 tokens a decision (free tier: 1,000 requests a day, 8,000 tokens a minute).

**gpt-oss-120b as chair**, the last two years, the same contract (`rd_llm_judge.py score`,
`rd_llm_quarters.py`):

```text
                                        1403Q3 1403Q4 1404Q1 1404Q2 1404Q3 1404Q4 1405Q1 1405Q2 1405Q3  2 years
holding's quarter                       +17.6  +64.9  -16.2  +37.8  +45.4  +29.1   -8.3  +47.8   +7.3   825.2M
LLM chair (gpt-oss-120b), weekly         +0.0   +0.0   +1.3   -0.4   -0.8   -0.5   +7.2  -12.5   -0.1    -1.1%
committee, acting weekly, same days      +0.0   -3.3   +4.1   +0.1   +0.1   -0.4   +6.6   -7.4   -0.1    +4.4%
(points against holding's quarter)
```

It chose gold 96 times and fixed income 19, 17 trades, 5 of 8 exits right; when it chose fixed
income, fixed income won 32% of the time over the next 20 days (the base rate 31%); median
confidence 0.71. Its reasons are mostly the committee's count ("4 of 7 active members favour
fixed income", "all eight members ... favour FIXED_INCOME") and fixed income's yield; once it
miscounted ("fixed-income supporters (~51%) exceed those of gold supporters (~60%)"). It
read the 2026 fall like the committee (+7.2 points in 1405 Q1) and stayed out longer at the
jump (-12.5 in 1405 Q2): 5.5 points behind the committee on the same days. Only this one
window is clean of its training data, so it cannot be run on the earlier windows.

**gpt-oss-20b**, the same 115 briefs (23 rate-limit waits, 1 decision missing): 3.0% behind
holding (1405 Q1 +2.5, Q2 -3.4 points); its fixed-income calls right 36% against the 31% base;
it agreed with gpt-oss-120b on 101 of 115 decisions. Neither LLM chair beat the committee acting on
the same days (+4.4%). The temporary branch probe-llm-judge is deleted.

## 24. TSETMC, with access assumed: volume profile, LIT, the order book, smart money (2026-10-05)

**The owner.** The Iran-side server is the owner's to provide; for the R&D, read TSETMC from this
machine and see how its data can polish the model: "the volume profile, lit and so on are back in
game."

**What TSETMC gives** (cdn.tsetmc.com/api, direct from Iran; probed on Ayyar, 2026-10-04):

```text
every trade            Trade/GetTradeHistory/{ins}/{day}/false   224,204 trades (45 MB) on 10-04
intraday snapshots     ClosingPrice/GetClosingPriceHistory/...    19,896 a day (4 MB): price, cumulative
                                                                  volume, value and trades
the order book         BestLimits/{ins}/{day}                     89,020 changes of the top five levels
the flow               ClientType/GetClientTypeHistory            individuals / institutions, daily
holders, the NAV       Shareholder/{ins}/{day}, Fund/GetETFByInsCode   the big holders; today's NAV only
the index              Index/GetIndexB2History/32097828799138957  TEDPIX daily from 2008
coin certificates      the bank-vault tamam sekeh certificates on the commodity exchange, daily, 2018 ->
                       1404/12 (none liquid since)
```

History reaches at least 2020 for trades and the book, lighter in earlier years (22,220 trades on
2024-10-05). The funds' session runs 12:00-18:00 Tehran now (12:00-15:00 in 1403). A fund's
`zTitad` is its registered unit ceiling, raised in steps (Ayyar 1.15 bn units in 2024-05, 5.365 bn
on 2026-10-04), not its daily creations. Fetched (`research/fetch_tsetmc_intraday.py`,
`fetch_tsetmc_book.py`, condensed as they arrive, git-ignored): one-minute bars for Ayyar and Tala
on 703 sessions each (2023-10-01 -> 2026-10-04), trades by ticket size and the book every 8th
session, the book's daily summary on every session, the coin certificates daily.

**Inside the session** (`rd_fund_intraday.py`, Ayyar 698 sessions and Tala 703; after 18K's own
last 1, 5 and 20 days and the fund's own day; circular-shift luck):

```text
                                  Ayyar                         Tala
close vs VWAP -> 18K tonight      +0.09 (luck 3%)               +0.06 (12%)
close vs its 20-day POC -> 18K    20 days +0.16 (8%)            20 days +0.29 (0%), 5 days +0.19 (0%),
                                  gold-FI 60 days +0.19 (0%)    from tomorrow 5 days +0.21 (0%)
LIT sweep (beyond yesterday's high or low, back inside): -0.01 to +0.04, nothing
trend day, last hour, POC migration, volume surge: |IC| under 0.10
the fund's last hour -> the platforms' next hour: +0.06 (53 hours, 2026-08 -> 10)
```

The session's shape tells 18K's close the same evening, not the days after. The volume profile --
the funds' close against the point of control of their last 20 sessions' minute volume -- leads
18K's next 5-20 days on both funds, after 18K's own moves. Built from daily data instead (each
day's value over its low..high, all gold funds, 2017 on: `rd_vp_member.py`) it tracks the minute
version (correlation +0.87, the same sign on 87% of days).

**The order book and the big tickets** (`rd_fund_book.py`, `rd_book_close.py`): within the session,
bids far deeper than asks were followed by +0.034% over 30 minutes and the opposite by -0.028%
(15,012 book minutes; the book also echoes the last 10 minutes, +0.11) -- far under any cost. The
closing hour's imbalance, +0.34 against 18K's next 5 days on the first 65 sampled days, is +0.07
(luck 10%) on all 696 sessions; the whole session's imbalance +0.10 (luck 2%). Big tickets (over 1B
toman a trade) carry 4% of the value on a median day.

**The coin and the stock market** (`rd_coin_bubble.py`, `rd_tedpix.py`): the coin's bubble over its
7.32 g of gold (the certificates' price unit moved by powers of ten, normalised) ran about +20% in
2018, +3-5% in 2020-21, +20-23% in 2023-24, +11% in 2025; in 2022-2026 a high bubble came before a
weaker 18K (-0.17 over 20 days, luck 10%), nothing in 2018-2021. TEDPIX's last 20-60 days led 18K's
next 20 days in 2020-2026 at +0.20 to +0.26 and gold over fixed income at +0.26 to +0.28 (luck 0-7%)
after 18K's, the dollar's and world gold's own moves; strongest in 2020-2022 (+0.25 to +0.41),
weaker since 2023 (+0.12 to +0.21, luck 27-75%); nothing in 2014-2019.

**In the committee room** (`rd_committee_stocks.py`, `rd_vp_member.py`, `rd_committee_veto.py`,
`rd_committee_reentry.py`; the committee acting every 10 / 20 days, every offset; median gain over
holding, windows beating it, worst window):

```text
                                   Afran windows from 2020 (18)          index windows from 2018 (27)
the room as it is, every 10 days   +6.7 to +9.0%   94-100%   -2.9%        +5.5 to +8.9%  85-93%  -21.2%
   + stocks as a voter             +3.0 to +5.8%   83-94%    -4.1%        +3.3 to +5.5%  78-89%  -26.1%
   + volume profile as a voter     +3.3 to +7.8%   67-100%   -5.7%        +5.7 to +8.2%  70-89%  -21.0%
   volume profile as a veto        +6.0 to +7.8%   89-100%   -3.1%        +5.0 to +6.9%  81-89%  -20.9%
   back early when stocks rise     +5.1 to +8.0%   83-100%   -4.6%        +4.8 to +7.6%  78-96%  -12.6%
   back early when the profile is strong  +3.8 to +6.0%  67-94%  -11.4%   +3.4 to +5.5%  74-89%  -17.5%
every 20 days: as it is +7.6 to +9.7% / -3.3% and +7.2 to +8.6% / -13.9%; back early when stocks
rise +5.9 to +8.2% / -2.4% and +5.0 to +7.3% / -9.3%; the last two years +0.6% to +7.2%
```

What a member is worth to the room is its calls to leave gold, not its correlation with gold's
future. When each member said fixed income, fixed income won over the next 20 days (base rate 40%
in 2018-2021, 39% in 2022-2026): market state 58% / 51%, dollar 20d 55% / 51%, fair gap 51% / 42%,
volume profile 46% / 55%, money flow 40% / 54%, world gold 47% / 42%, stocks 43% / 48%, brake 44% /
-, real dollar 32% / 41%, chartist 39% / 26% (`rd_exit_skill.py`). The volume profile and the stock
index lead gold mostly on the way up -- the room is already in gold then -- and their votes for
fixed income come in dips that recover in toman. As voters and as vetoes they lower the room's
result; the stock index earns a place as the way back: coming back to gold as soon as it rises keeps
the median within 1-2 points and shrinks the 2018 tail from -21% to -13% (every 10 days) and from
-14% to -9% (every 20).

**For the model, then:** the room stays as it is, acting every two to four weeks; the stock index
is the candidate for an early return to gold (a choice of tail against median, the owner's); the
volume profile and the funds' flows belong in the evidence the owner and the LLM read (levels, hot
money, the coin's bubble, today's NAV premium) rather than in the vote. Every TSETMC input waits for
the Iran-side collector; TEDPIX and the funds' daily data are the cheapest to collect.

## 25. Lessons registered, the websites, AMD, and how to shape the room (2026-10-05)

**The owner.** A summary to close and register the lessons; what is good, why, and how it helps;
fipiran, tablokhani and etfbaz for Iran's gold ETFs; session liquidity and AMD; "how to shape the room
to get the most of it. Buying and holding is the easiest; what's the hard and more beneficial piece?
For example, gold enters a sideways channel for a while, so the room should transfer a part of the
gold into the fixed-income ETF, and then, understanding the next move, add the gold back."

**Lessons registered:** `LESSONS_LEARNED.md` sections 20-28 (a line's accuracy is its distance; a good
predictor can be a bad member; one window's number is not a result; the sample that flatters; a
pattern needs a shuffled baseline; learning the weights chases the last era; a model cannot be tested
on what it has read; a unit that moves by powers of ten; in toman, leaving gold is the expensive
mistake).

**The websites** (from Iran, direct; each site's own calls, read from its scripts):

```text
fipiran.ir   POST /services/fund/fundcompare {"date"}: every fund on that day -- issue / redemption /
             statistical NAV, net assets, units outstanding; from 2019 at least (Ayyar 95.6 M units
             on 2019-10-05, 5,100 M on 2026-10-03). GET /services/fund/fundlistbrief (567 funds),
             /services/efficiency/fundefficiencychart?regNos= (daily NAV returns), /fund/fundlistissue
             (today's issue and redemption NAV). Open, no key. Fetched daily 2019 -> 2026-10 for the
             gold (type 5) and fixed-income (type 4) funds: research/fetch_fipiran.py.
tablokhani   api.tablokhani.com/public/: smart-money-averages (every symbol: individuals' 10-day per-
             capita buy and sell, buyer and seller counts, RSI14, MA20), volume-averages,
             market-indices, fund-categories, symbol-names -- today's values, open; everything else
             behind a login and a paid plan.
etfbaz       api.etfbaz.com: /instrument/landing (world gold, 18K, the union's cash quote for melted
             gold), /instrument/category/{id}, /instrument/search (the funds and ready-made "bubble"
             instruments: Ayyar's, 18K's); its history cards (the funds' bubble, net inflow, average
             bubble) load from code a script cannot reach without the browser's session -- not pursued.
```

fipiran is the one that matters: units outstanding are the money that really entered or left the
gold ETFs, and the exchange price against the redemption NAV is the premium -- the hot-money record
TSETMC does not keep. A collector needs one request a day.

**AMD and session liquidity** (`research/rd_amd.py`; Ayyar 698 and Tala 702 sessions, the first hour
as the accumulation, a break of one side as the manipulation, a close beyond the other as the
distribution; against the same days with their minutes shuffled):

```text
                      Ayyar real / shuffled     Tala real / shuffled
AMD (either way)      1.3% / 9.9%               2.3% / 9.6%
continuation          42.4% / 53.0%             41.5% / 55.3%
inside the first hour 56.3% / 37.1%             56.3% / 35.1%
ran yesterday's high (low), closed back inside: 12.6% / 12.6% (12.8% / 13.2%); Tala the same
```

AMD is rarer than chance: market makers hold the funds' price to its NAV, inside the opening range.
Liquidity sweeps come at chance. In our own market (production's hourly readings, 62 days of a
rising 2026-08 -> 10), the platforms' median price at 06:00-13:00 sat 0.2-0.65% under the same
day's evening price (07:00 -0.65%), 14:00-21:00 within +/-0.3% of it: the morning dollar carried
from the day before and the day's drift. If it holds over a longer record, buying in the morning and
selling in the late afternoon is worth about Daric's whole round trip; to be measured as production
collects.

**What the room did in the owner's example** (`rd_room_1405.py`; every 10 trading days): on
1405/01/05 at 17.55M seven of eight members favoured fixed income and 40% of the grams went to
fixed income; they stayed there through the channel (the dip to 15.65M missed) and came back on
1405/05/31 at 21.04M, after the break from 19.2M. Over 1404/11/01 -> 1405/07/09: +58.1% against
holding's +61.8%; over the two years, +10.4% against holding. With the early return on the stock
index it churned (six round trips) for +59.4%. An early return on the dollar's 20-day momentum was
worse everywhere (median +3.5 to +5.9%, worst -14%).

**What is good, why, and how it helps:**

```text
fixed income for idle cash        cash earns 20-39% a year instead of nothing; the brake policy
                                  went from +12.6% to +17.5% against holding over 2016-2023
the room, slow                    leaving gold on a broad consensus, acted on every 10-20 trading
                                  days: median +5.5 to +9.7% against holding per two years, ahead in
                                  85-100% of windows, at every offset, with equal weights too; why:
                                  it leaves only when most of the evidence agrees and does not
                                  flicker; it earns in falls like 1405 Q1 and pays at jumps
the early return on stocks        halves the worst window (-21% -> -13%) for 1-2 points of median
the bands                         18K's own past moves give a range that holds 93-95% at 5-20 days:
                                  the honest "95%", for the plan and the targets
the brake                         insurance in storms; leaving it out raises the median and deepens
                                  the worst window to -9% and the last two years to -11%
the volume profile, fipiran's     evidence for the owner and the LLM (levels, hot money, the premium),
premium and flows, the chartist   not votes; each must earn a vote inside the room first
execution: mornings to buy        about 0.3-0.6% a round trip if it holds; being measured
```

**The hard piece.** Buying and holding takes the inflation drift (18K x6.2 in two years). Leaving
gold for fixed income in a sideways market is the part the room already does well. The hard,
valuable piece is the return: coming back at the start of the next move, not after it. In 1405 the
room returned one breakout late, and that alone cost it 3.7 points against holding over the episode.
No price, chart, flow or LLM reading has called the start of a jump; the stock index helps the tail.
fipiran's real money into the gold ETFs is the next candidate (below).

**fipiran's money and premium, tested** (`research/rd_fipiran_flows.py`; units outstanding daily to
2020-02 and weekly after, 762 dates; each gold fund's daily NAV rebuilt from its NAV-return history
and anchored to the reported redemption NAV; 18 gold funds, 168 fixed-income funds):

```text
the gold funds' premium over NAV (by net assets): 2019 +1.1%, 2020 +9.3% (to +27.8%), 2021-2026
-0.6% to -1.6%; their 28-day net creations, median +0.2% (2021) to +5.7% (2024) of assets
after 18K's own moves               2019-2022                        2023-2026
premium -> 18K 5 / 20 days          +0.20 (luck 0%) / +0.31 (0%)     +0.09 (13%) / +0.02 (84%)
gold inflow 7 days -> 18K 5 days    +0.11 (9%)                       +0.03 (63%)
gold inflow 28 days, fixed-income inflow, gold vs safety: |IC| 0.13 or less, luck 24-99%
in the room (14 two-year windows from 1400 Q1, every 10 days): as it is +6.1 to +9.4%; with the
premium (leaning fixed income when high, fixed in advance) +3.0 to +5.9%; with the gold inflow
+4.4 to +9.6%; with the safety inflow +1.6 to +3.7%; all three -1.0 to +2.3%; the safety inflow as
the early return +1.1 to +3.7%
```

A high premium came before a stronger 18K in 2019-2022, the opposite of the contrarian direction
fixed in advance (in that era hot money was momentum), and weakly since; the real money in and out
of the gold and fixed-income funds leads nothing. Not re-signed after the fact. fipiran's premium and
flows belong in the evidence -- how hot the crowd is, where the money is going -- not in the vote.

## 26. The owner's common-sense room, the runner and the Iranian sites, and what is wrong (2026-10-05)

**The owner.** No to the room as proposed: "the room should have a common sense, like a human. I am not
calling to always park an amount in fixed income: if the trend is bullish, all out to gold; if
sideways, it should be able to extrapolate and sell some gold into fixed income and keep the rest, and
keep a sharp eye to rebuy the sold gold back." Yes to the early return on the stock index. Is the
Iran-side server resolved by fipiran, tablokhani and etfbaz? "Still the room isn't ready to give it
the paper money, and what you have done so far is not satisfying; there is something wrong, and I
don't know what. What's your call?"

**From GitHub's runner** (temporary branch probe-iran-sites, deleted): tablokhani 200 (0.9-1.3 s:
market indices, smart-money averages), etfbaz 200 (1.7 s: the landing prices); fipiran timeout,
TSETMC timeout, Nobitex refused, Daric 403. tablokhani and etfbaz serve the runner; fipiran, TSETMC,
Nobitex and Daric still need the Iran-side collector.

**The owner's room, as written** (`research/rd_room_human.py`; the chartist's phase as known each day:
MARKUP all in gold; ACCUMULATION / DISTRIBUTION keep 60%, the 40% swing to fixed income in the box's
upper part (at or over 60%), back in its lower part (30% or less), on a break upward or when the stock
index rises; MARKDOWN held, or the swing out; acted on daily):

```text
against holding           2016-2023        2024-2026       last 2 years    two-year windows (18, Afran)
downtrend held            -4.7%            -3.3%           -2.2%           median -2.9%, 11% ahead, worst -5.3%
downtrend out             -17.3%           -8.9%           -6.2%           median -6.3%, 6% ahead, worst -10.1%
the committee, 10 days    +7.1%            +5.9%           +10.7%          median +8.5%, 94% ahead, worst -0.3%
by phase, points against holding (downtrend held / out): 2016-2023 sideways -4.4 / -3.1, downtrend
-0.1 / -13.1; 2024-2026 sideways -0.6 / -2.9, downtrend -0.1 / -4.1
```

**What is wrong.** The rules are a trader's; the phase they are fed is late. A chart's phase is known
only from confirmed swings: a sideways market is recognised after part of the range has passed, a
downtrend after the fall (the exit sells low), a bull after the jump (the return buys high). Selling
the box's top in toman sells before the break up more often than before the break down (section 16).
A human's sense of the phase comes ahead of the chart, from what prices do not yet hold: the news, the
dollar's mood, the bazaar. The committee does better not by reading the phase from the chart but
because several of its members (the fair gap, the real dollar, money flow, the market state's
valuation) are partly ahead of the price, and it acts slowly. It is the owner's room with the phase
read from the evidence: all in gold by default, 40% to fixed income only when most of the evidence
favours it, back when that breaks.

## 27. The room, built: the PAPER front office (2026-10-05, sp-d-paper)

**The owner.** "Go ahead. For now we park fipiran, TSETMC and so on, and use etfbaz and tablokhani;
later on we can add the server and fill the void. If you agree, go ahead, else argue. Also, I need the
message drafts to see."

**What production can feed the room from GitHub's runner** (section 26): tgju (18K, the dollar, world
gold, as before); tablokhani (the stock index; each fund's last close and smart-money averages --
Afran's close values the fixed income); etfbaz (Tether USDT/IRR, the dollar, the union's melted-gold
quote, 18K, world gold, the index). Today's values only: the histories the members need (TEDPIX from
2008; the cost of money from 2015 -- the fixed-income index until Afran exists, Afran's price after;
Afran is accumulating, its price is its total return) are seeds in `src/seed/`
(`research/build_seeds.py`), and production appends one reading a day (`_collect_room_inputs`,
`market_daily_candles` under the sources "tablokhani" and "etfbaz": new instruments in the existing
table, the first value of a day kept). On Afran the real-dollar member leans as on the index on 96% of
days since 2022.

**Money flow waits.** Without TSETMC's client types the room loses its money-flow member: median +3.7
to +6.2% against holding instead of +5.1 to +8.0% (`research/rd_room_prod.py`). tablokhani's 10-day
per-capita recipe agreed with it on 51% of days and lowered the room further (+2.1 to +4.2%,
`research/rd_flow_tablokhani.py`), so the member sits out until the Iran-side collector.

**The sharp eye, with common sense.** The first drafts showed the room selling on a review day and
buying back the next morning, four times in 1405, because the stock index was already rising. The rule
now: no sale while the stock index's last 20 days lean to gold, and while out, back to gold early only
on the first day they turn to gold after the sale (`research/rd_room_reentry_sense.py`):

```text
every 10 days, no money flow     Afran windows from 2020 (18)            index windows from 2018 (27)
as first built                   +3.7 to +6.2%  78-100%  worst -6.7%     +3.8 to +6.0%  74-89%  -13.8%
back early on a new turn only    +3.8 to +6.4%  83-100%  worst -5.2%     +4.0 to +6.4%  81-89%  -21.2%
no sale while rising + new turn  +4.0 to +5.7%  83-100%  worst -3.3%     +3.9 to +5.6%  81-93%  -11.3%
the last two years: +8.9% with 17 trades and 5 round trips under 3 days; +9.5% with 7 trades and none
```

**The code** (`sp-d-paper`): `src/analysis/room.py` (the seven members, the committee's 60% / 30%
view, the review every 10 trading days from the account's start, the veto and the early return, the
20-day range from 18K's own past moves, the reasons in plain words); `src/caluclator/chartist.py` (the
chartist, ported); `src/collector/tablokhani.py`, `src/collector/etfbaz.py` (bounded, never raise);
`analysis/quant.growth_path` (the brake's daily f* and the drift); `analysis/paper.py` (the ROOM
account, the only one that pushes; `room_trade`: SWING_OUT sells 40% of the grams and puts the cash
straight into Afran in whole units at its last close, ALL_GOLD takes every unit back out and buys whole
grams; the units live in the activity row's `inputs`, so no schema change); `main.py`
(`_collect_room_inputs` after tgju's candles; `_room_state`, `_room_view_at`, `_room_view`; the room's
branch in `_paper_run`; the 21:00 report from the front office); `alerts/telegram_paper.py`
(`build_room_trade_message`, `build_room_report_message`). Without enough history the room holds its
default, all in gold, and says so. **NEON MIGRATION REQUIRED = NO** for the room; the two-trades
migration of section 14 is still to be applied before the merge (the brave analyst can trade twice a
day, and production still holds the one-trade index).

**Checks.** The production room against the research room on the same data: every member, the stock
index and the posture the same on 100% of days (`research/check_room_parity.py`). End to end through
`_paper_run` on the real history (a scratch database): 3.8 s for the first run of the day (the
quarter's fit), 1.9 s after; day one buys 5 g, all in gold, pushes, and reports at 21:00 with the
chart. `kpi_paper` 33/33 (new: the replay and its rules, `room_trade`, the members and their words,
the messages, the collectors, the wiring and the seeds, the brake's path); suite 30/30; compileall.

**The drafts** (`research/render_room_drafts.py`: the room's account from 1403/07/14 on the real
history, Daric's 0.30% around tgju's close; nothing sent). Its trades over the two years: one round
trip in 1404 (out 1404/01/08, back 1404/01/23), two in 1405 -- out on 5 Farvardin at 17.52M, back on
4 Khordad at 18.29M (the stock index turned up), out on 23 Tir at 17.87M, back on 15 Mordad at 18.61M,
before the jump; 901.4M against holding's 823.3M. As it would have pushed them, and as it reports
tonight:

```text
GOLDPremium: PAPER · the room
Sold 14 g at 17.52M on Daric · 5 Farvardin 07:01
Moved to Afran (fixed income): 250.13M
Why: the market is stormy; the market is moving sideways
Kept in gold: 21 g
Back to gold: when the stock index turns up, or at the review on 17 Farvardin
Total: 618.08M (this quarter −0.52%)

GOLDPremium: PAPER · the room
Bought 14 g at 18.29M on Daric · 4 Khordad 07:01
Paid from Afran (fixed income): 264.32M
Why: the stock index turned up: back to gold early
Now all in gold: 35 g
Total: 646.42M (this quarter +4.05%)

GOLDPremium: PAPER · 13 Mehr 1405, 21:00
Phase: rising (markup), up from 15.65M on 26 Khordad
Posture: all in gold · 35 g (Daric pays 25.66M a gram)
Today: no trade
Total: 901.40M · this quarter +7.30%
Holding instead: +7.31%
Next 20 trading days: most likely 24.50M to 30.84M
The room: 1 of 7 lean to fixed income, 4 to gold · next review 16 Mehr
```

The 21:00 message keeps the chart of section 13, with the room's trades on it. Open for the owner: the
drafts' review; the two-trades migration; then the safe tag and the merge. Next: the news leg (an LLM
reading the headlines live), Tether as a member once its record exists, the Iran-side collector for
money flow, Daric and fipiran.

## 28. Go-live: the migration, the merge, two defects found by the first runs (2026-10-05)

**The owner.** "Go ahead, authorized." And: "when does the room sit? On a daily basis based on the
analyze schedule, or what?"

**The two-trades migration, applied** (`sql/neon_migration_paper_two_trades.sql`, one transaction,
15:50 Tehran): paper_activity held 0 rows; after it `trade_no SMALLINT`, `uq_paper_trade_slot`
(account, day, trade number, TRADE rows) in place of `uq_paper_one_trade_a_day`, and
`ck_paper_trade_no` (1 or 2); no other table touched (720 market snapshots, unchanged).

**The merge.** `v1.6safe` tags `main` at b1e61eb, pushed first; `main` and `SP-D` fast-forwarded to
2957699 (sp-d-paper, 20 commits) at 15:57 Tehran.

**Two defects, found by the first runs, both failing safe:**

- *The KPI suite failed on `main`* (run 37309647298): GitHub's runner resolved the newest scipy and
  pandas, which statsmodels 0.14.4 is not compatible with (`scipy._lib._util._lazywhere`, removed in
  scipy 1.16; pandas 3's `deprecate_kwarg`). This machine runs scipy 1.15.1 and pandas 2.2.3, so the
  suite passed here. In production the quant engine reported itself unavailable: the brake member read
  "gold" and the quant account held. Fix: `scipy==1.15.3` and `pandas==2.2.3` pinned with statsmodels.
- *The first live PAPER run failed* (16:00 Tehran, run 37310024426): `paper_accounts.venue` is
  VARCHAR(20) and ">".join(VENUES) is "Daric>Goldika>Ayyareh", 21 characters, since the venue chain was
  set on 2026-10-04; the tests run on SQLite, which does not enforce lengths. Nothing was written and
  nothing sent; the room's inputs before it were stored (AFRAN_LAST 54,490, TSE_TEDPIX 7,790,017).
  Fix: `paper.VENUE_LABEL` "Daric>Goldika>Ayyar"; `kpi_paper.test_29` checks every text the PAPER and
  room code writes against its column's length in the models.

Both on `hotfix-scipy-pin` (cut from `main`): the KPI suite green on GitHub (run 37311429313, 3fbcdfd)
and here (30/30; kpi_paper 34/34). Awaiting the owner's review for the fast-forward, with a safe tag on
`main` (2957699) first. **Done the same day:** `v1.7safe` tags 2957699; `main`, `SP-D` and `sp-d-paper`
at 04a37e1 from 17:07 Tehran (section 29).

**At Goldika's cost.** Daric refuses the runner, so PAPER trades on Goldika (2.37% between buying and
selling) until the Iran-side collector. Replayed at that cost (`research/rd_room_cost.py`): median +1.3
to +3.1% against holding per two years (against +4.0 to +5.7% at Daric's 0.30%), ahead in 67-83% of
windows, worst -4.6%, the last two years +7.1%. Daric is where most of the room's edge is.

**When the room sits.** It reads at every scheduled ANALYZE run, hourly 06:00-21:00 Tehran
(cron-job.org), and logs its view each time. Its evidence is the completed daily candles, so the view
moves once a day, at the first run of the morning when yesterday's candle arrives. It decides on a
review day, every 10 trading days from its first day (about every two weeks); between reviews only the
sharp eye acts: back to gold on the first morning the stock index turns up after a sale. A trade runs at
the first scheduled run that day with a fresh two-sided quote (normally 06:00-07:00); the 21:00 run
reports, with the next review's date.

## 29. The lost transcript, go-live closed, health check 2026-10-06, where the threads stand (2026-10-06)

**The owner.** The chat history is gone. "Check everything: the GitHub, the Neon, the cron, the
worker, every inch of work." Housekeeping first, if safe; write section 29 and bring the documents up
to date. "The LLM is live now; I don't know if the news, GDELT, TEDPIX or other stuff are taken care
of." Termux on an Android device was discussed; decisions about the next steps are open: "your call,
based on the history."

**The transcript.** The Claude Code session of 2026-09-27 to 10-05 (c61d59c3, "Project status
review", last prompt "health check report") was lost on 2026-10-06, when the local `~/.claude`
folder was recreated at 13:13 Tehran; the disk is an SSD with TRIM, so it is not recoverable. The
2026-09-12 to 09-25 session (535d3b29) survived in a backup and is restored. **Nothing of the project
was lost:** every decision, measurement and rejection of those days is in this file, committed and on
GitHub. The continuity protocol held: the repo, not the conversation, is the memory. On this
workstation transcripts are now kept indefinitely (`cleanupPeriodDays` 36500; the default deleted them
after 30 days) and copied daily to `D:\claude-history-backup` (task ClaudeHistoryBackup, 18:00,
copy only, never deletes).

**Go-live, closed** (section 28 ended awaiting the review). `v1.7safe` tags `main` at 2957699;
`main`, `SP-D` and `sp-d-paper` fast-forwarded to 04a37e1, pushed 17:07 Tehran 2026-10-05; KPI Suite
green on `main` and `SP-D` (runs 37318234182, 37318234401). The 17:00 run still ran 2957699; the first
on the fix was 18:00 (run 37325274751): the six accounts opened at 18:01; the room, the analyst, the
quant, the cautious account and buy-and-hold each bought 5 g at 268,196,931 on Goldika (Daric 403),
`system` holds its cash (`final_decision` WAIT). The room's trade message went out at 18:02 and the
21:00 report with its chart (run 37348953519). HOLD on every run since; the room reads "the market is
calm; 18K made a new 60-day high (all in gold)". Value 1,329.9M against 1,350M: -1.5%, Goldika's
2.37% between buying and selling, as section 28 expected.

**Health check 2026-10-06 16:00 Tehran** (since 2026-10-05 10:15; `PROJECT_OPERATIONS.md` section 15):

- **Runs.** Every scheduled ANALYZE ran and succeeded: 16 on 10-05 (06:00-21:00) and 06:00-16:00 on
  10-06, 5-9 minutes each. The owner's UPDATE at 10-05 16:29 and 10-06 11:35, 11:43, 15:02; DIRECTION
  at 08:10 and 15:02. All on `main`, which also verifies the cron job (ref `main`, mode analyze) and the
  worker (ref `main`, `/Direction` answering: the redeploy noted as pending on 10-03 is done).
- **Freshness** (24 hours to 16:45): 19 market snapshots and states (16 scheduled, 3 UPDATE), 16
  analysis snapshots, 48 outcomes, 237 price observations, 521 news items, Direction panels at 06:00 and
  13:00. `market_daily_candles`: tgju's 18K, dollar and world gold to 10-05 (collected 06:03);
  tablokhani's TSE_TEDPIX and AFRAN_LAST for 10-06; etfbaz once, at 21:01 on 10-05 (by design: read only
  at the 21:00 run, `main._collect_room_inputs`).
- **Platforms.** Nine of eleven. Daric 403 on every run since 10-03 18:50. HoorGold 503 once (10-05
  21:00). Taline in 12 of 19 readings; its band discarded the rest (-1.03% to -1.91% from the median).
  **Taline stored 267,410,000 in six readings, 10-06 09:01 to 14:01,** while the others moved (Milli
  264.70M to 264.21M, WallGold 266.11M to 265.27M, HoorGold 266.5M to 266.9M): the frozen copy of
  section 20, within the 1% band and within 1.0 pp of its usual position, so the repeat rule does not
  defer it. Second time on record; it puts stale readings into the record every such day, against the
  owner's rule of 2026-10-02 ("it contaminates our DB").
- **Decisions.** WAIT on every reading, valuation FAIR. The premium narrowed from -3.10% (10-05 16:01)
  to -1.21% (10-06 09:01); -2.46% at 16:01. Since the start: `final_decision` WAIT 663, BUY 4;
  `candidate_decision` WAIT 532, BUY 135. The push armed and below its level (gap 2.0, fire at 3.37).
  The seven UNKNOWN valuations of 10-01 are the correction of 2026-10-03, not a fault.
- **Direction.** Seven panels since 10-03, STRONG BULLISH on all seven (18K at a record, strong trend);
  none resolved yet (20 trading days, the first in early November). Seven rows cannot tell a constant
  from a trend: run the `GROUP BY` again at 30.
- **Afran's date.** tablokhani's `closing_1d_ago` is a close from before the latest session: the row
  stored for 10-05 (54,490, read at 16:00) equals the seed's close for 10-03
  (`fixed_income.json` level / `afran_scale` = 54,490.0), and the row for 10-06 (54,567) was read at
  06:01, before the market opened. Each production row carries an earlier session's close under a later
  date, so the fixed-income member and Afran's unit value run one to two trading days behind, about
  0.1% of value. Small; to be fixed with the next change to the room (date the value by its session).
- **KPI.** 30/30 files, exit 0, on this machine at 04a37e1.
- **Verdict:** healthy. Open: Taline's frozen copies stored; Daric refused from the runner; Afran's date.

**Housekeeping.** Local `main` and `SP-D` fast-forwarded to 04a37e1; the merged local branches
`docs-ta-track` and `sp-d-direction` deleted (both inside `main`; `sp-d-direction` also on origin);
the untracked home briefing of 2026-09-27 (`HANDOFF.md`) moved out of the repo. **Left for the owner:**
five temporary workflows (probe-gdelt, probe-groq, probe-iran-sites, probe-iran-sources,
probe-llm-judge) are still registered as active although their files are on no branch, so they cannot
run; disable them on the Actions page. The repository is public: no secret is exposed, but the room and
the research can be read by anyone. Whether that is intended is the owner's call.

**Where the threads stand** (the owner asked):

```text
the LLM      DESIGNED AS A COMMITTEE MEMBER, NOT YET BUILT. Sections 17-18 give it a vote, weight
             1.0, "the LLM among them" in the 60% / 30% consensus, reading the headlines and
             everything the others see, never computing a number. Section 15 defined the LLM
             trader; section 16 checked Groq from the runner; section 23 replayed gpt-oss-120b as
             the CHAIR (it decides alone): -1.1% against holding, the committee +4.4% on the same
             days, so the chair was not adopted. As ONE VOTE it was never replayed: only the
             window after its training cut-off is clean. The room built in section 27 has seven
             members and no LLM; section 27 lists it as the next build. Nothing in src/ calls
             Groq (src/intelligence/event_interface.py is a stub); briefs and answers of the
             replay are kept in research/data/llm_*.json.
news         9 RSS sources, about 520 items a day, keyword classifier, every row KEYWORD; in no
             message (measured, nothing found, SP_C_HANDOFF 27.7); high_impact_count still 0 (33.3)
GDELT        the owner's choice to start the news leg (section 13); fetched 2017-2026 from the
             runner and tested (section 14): Iran coverage jumps came near local peaks (18K about
             2 pp weaker the next month), counts and tone add nothing to the drop detector. Kept
             as research (research/data/gdelt.json); never in production. The finding moved the
             news leg to the LLM reading headlines live
TEDPIX       live: tablokhani daily from 2026-10-05 (from 13:00, after the close), seed from 2008,
             etfbaz's index as a fallback; the room's early return and its sale veto read it
Tether       etfbaz's USDT/IRR stored daily from 2026-10-05; a member once its record exists
Termux       proposed in section 13: an old Android phone (or a PC that stays on) as the Iran-side
             node, fetching Daric, TSETMC and fipiran hourly into Neon over HTTPS, with Bale for an
             Iran-only cut. Not built; needs the owner's device
broadcast    rollout step 4 (SP_C_HANDOFF 29.3): designed, not built
```

**Next, proposed from the record** (the owner decides):

1. **Taline's frozen copies.** Data integrity first, by the owner's rule of 2026-10-02. Measure on the
   record how often a platform repeats one price for three hours or more while the others' median moves,
   propose a rule, replay it, then code. Afran's date goes in the same change.
2. **The Iran-side node.** The largest single gain: Daric is most of the room's edge (+4.0 to +5.7%
   against holding at its 0.30% cost, +1.3 to +3.1% at Goldika's 2.37%, section 28), and money flow,
   fipiran and TSETMC all wait for it. The owner chooses the device; then a write-only Neon role and a
   table for its readings (a migration, verified on a temporary branch first).
3. **The LLM member** (sections 17-18, as designed): gpt-oss-120b on Groq reads the headlines and the
   brief the system computes, and casts one vote, weight 1.0, in the room's consensus, with its reasons
   in words. Its view logged at every run and scored like every member's. Start early: only time builds
   its record.
4. Then broadcast, and the queue: the ANALYZE percentages, the basis divergence.

**The owner's answers, the same evening.** Taline: agreed, first. Termux: tomorrow (2026-10-07).
Broadcast: **parked** until the committee and the PAPER trades have shown their performance. The
Direction message: not satisfying, **to be revamped totally** (tomorrow). The LLM: the owner remembered
it as a heavy member of the room -- the record above confirms it was designed into the room (weight 1.0)
and not yet built; the first section-29 draft understated that, corrected here.

**NEON MIGRATION REQUIRED = NO** for this section: read-only queries only.
