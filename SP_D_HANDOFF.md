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
