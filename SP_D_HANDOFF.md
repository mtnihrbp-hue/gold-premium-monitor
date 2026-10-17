# SP-D Handoff

SP-D was branched from `main` on 2026-09-29 (`SP_C_HANDOFF.md` section 36); its code
work opened on 2026-10-03. SP-C is closed: its handoff (`SP_C_HANDOFF.md`) keeps SP-C and
the pre-SP-D hotfixes on `main` (its sections 37-45), and everything from SP-D's first
deliverable on is recorded here (owner, 2026-10-03: "that sprint is closed, anything now
is SP-D"). Sections 1-4 were written as `SP_C_HANDOFF.md` sections 46-49 and moved here
on 2026-10-03 unchanged, apart from their numbers.

**SP-D's sub-sprints** (owner, 2026-10-15: "mark the sprints SP-Da, SP-Db, SP-Dc and so on"; most
items of one batch belong to one sub-sprint, not several):

```text
SP-Da  Direction                                   sections 1-8     merged 2026-10-03 (v1.4safe), 10-04 (v1.5safe)
SP-Db  PAPER and the room                          sections 9-29    merged 2026-10-05 (v1.6safe, v1.7safe)
SP-Dc  the Iran-side node, the sanity ranges       sections 30-31   merged 2026-10-07 (v1.8safe)
SP-Dd  money flow, the phone's reads, the trend    sections 32-34   branch sp-d-trend-rd, merged 2026-10-15 (v1.9safe)
       R&D, Neon's transfer cuts
SP-De  the quant fit, the room alert at 3 and its  section 35 on    branch sp-de; 35.1-35.2 merged 2026-10-15 (v1.10safe);
       push, Direction's EMA lines, Tether as a                     35.4 (the spool) merged 2026-10-15 (v1.11safe);
                                                                   35.5-35.6 merged 2026-10-15 (v1.12safe);
                                                                   35.8 merged 2026-10-15 (v1.13safe);
                                                                   35.11 Direction v7 merged 2026-10-15 (v1.14safe);
                                                                   36 the audit; 37.1-37.3 merged 2026-10-16 (v1.15safe);
                                                                   37.4-37.5 the patterns merged 2026-10-16 (v1.16safe);
                                                                   37.7 both price sides merged 2026-10-16 (v1.17safe);
                                                                   37.8 the unit tests merged 2026-10-16 (v1.18safe);
                                                                   37.9 the documents merged 2026-10-16 (v1.19safe);
                                                                   CLAUDE.md's tag line 2026-10-16 (v1.20safe, see 37.10);
                                                                   37.11-37.12 the labels, the mirror merged 2026-10-16 (v1.21safe);
                                                                   37.13 the Iranian news, news held merged 2026-10-16 (v1.22safe);
                                                                   37.14 the state cache restored merged 2026-10-16 (v1.23safe);
                                                                   37.15 the SERVICE notice merged 2026-10-16 (v1.24safe);
                                                                   its outage date from the record merged 2026-10-16 (v1.25safe)
       member, the LLM member
```

A sub-sprint's work lives on one branch named after it (`sp-de`), short-lived topic branches cut
from it when useful (`sp-de-tether`), and reaches `main` as one reviewed batch with a safe tag first.

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

## 30. The sanity ranges, the probe workflows, and the Iran-side node on the owner's phone (2026-10-06)

**The owner.** "Why reject above 5,000? Strange; fix the issue." "You can get rid of the probe
workflows if harmless." "I'm ready to go for Termux now; I have installed it on my S10."

**The sanity ranges** (`validation/data.py`, branch `hotfix-validation-bounds`, edff4c8). A reading
outside them is dropped: world gold falls back to a stored price for up to six hours, then fair value
is lost; a platform is discarded. They were written for an older market and never revisited:

```text
range              was           2026-10-06     room    now            room
world gold $/oz    1,000-5,000   4,146          1.2x    1,000-20,000   4.8x
18K rial/gram      1M-500M       269M           1.9x    1M-5,000M      18.6x
dollar toman       10k-1M        269,300        3.7x    unchanged      3.7x
```

18K rose 70% in four months, so its ceiling was the nearer of the two: past it every platform is
discarded. The dollar's stays because it also catches a rial slip (ten times the rate) while the rate
is above 100,000; revisit it when the rate passes 500,000. Its comment said IRR; the value is toman
(`market_snapshots.usd_irr` holds 269,300). `kpi_signal_confirmation.test_47` keeps every ceiling at
least three times the market of 2026-10-06, still refuses a price per gram of gold and a rial slip,
and keeps 18K at twice today's price; it fails on the old bounds (46/47) and passes on the new.
Awaiting the owner's review; then `v1.8safe` on `main` and the fast-forward.

**A flaky KPI, found on the way.** One full run failed `kpi_paper.test_28`: `quant.fit_regimes` fits
with `search_reps=5`, random starting points with no seed, and once the SVD did not converge. Four
reruns passed. Production's quant engine is not exactly reproducible run to run, and a failed fit
makes it report itself unavailable (the brake reads gold, section 28). Open: seed the search, or
retry on a failed fit.

**The probe workflows.** Disabled (owner's approval): probe-gdelt, probe-groq, probe-iran-sites,
probe-iran-sources, probe-llm-judge. Their files were on no branch; only Gold Premium Monitor, KPI
Suite and Task C Tests remain active.

**The Iran-side node** (sections 13, 18, 29; branch `sp-d-iran-node`). Daric first: it is most of
the room's edge, and it refuses GitHub's runner and Cloudflare. From this machine's Iranian
connection Daric answered at bid 266.45M, ask 267.62M rial: a 0.44% spread against Goldika's 2.37%.

- `iran_node/node.py`: Python and `requests` only. Reads Daric, inserts one row through Neon's HTTPS
  endpoint (no Postgres port), keeps unsent readings in `~/iran_node_spool.jsonl` and sends them with
  the next run, so a cut of the international link loses nothing. `--test` reads and sends nothing.
  Its password lives in `~/.iran_node.env` on the phone, never in the repository (public).
- `iran_node/setup.sh`: one command on the phone. Installs what is missing, takes the wake lock,
  writes the Termux:Boot script (`termux-wake-lock`, `crond`), sets the 15-minute schedule, runs one
  reading. Written after long commands pasted into Termux from a messenger arrived with curly quotes
  and left the shell waiting.
- `sql/neon_migration_iran_node.sql`: the table `iran_node_readings` (node, source, instrument,
  observed_at UTC, bid and ask in rial, value, status, detail, the source's own answer as JSONB) and
  the role `iran_node`, INSERT only.
- **A role made through Neon's API or console joins `neon_superuser`, which holds
  `pg_read_all_data` and `pg_write_all_data`** (seen on the temporary branch). The node's role is
  therefore created with SQL; one made so had no memberships and no attributes.
- Tested on `temp-iran-node-test` (copied from production, deleted after, owner's approval): two
  readings inserted from this machine in about two seconds; the role was refused SELECT on
  `market_snapshots` and on its own table, and DELETE on its own table.
- **The owner's S10** (Termux, Iranian connection, no VPN): `--test` read Daric at 15:24Z (bid
  266,651,140); `setup.sh` ran clean; the schedule reads every 15 minutes into the phone's spool.

**Not yet** (the owner's choice): the table and role in production. Until then readings wait on the
phone, with their own times, and go up when the node receives its `NEON_URL`. Production does not
read the node yet: the next change makes Daric's quote come from the node when the runner is refused
(freshness checked as for any platform), and moves PAPER back to Daric.

**NEON MIGRATION REQUIRED = YES** for the node (`sql/neon_migration_iran_node.sql`), verified on a
temporary branch, **not applied**: awaiting the owner's authorization. **Applied 2026-10-07** (section 31).

## 31. Health check 2026-10-07, Neon access without the connector, the node in production (2026-10-07)

**The owner.** The day's list: the health check as the daily routine; the Termux node; ideas for the
room (trend identification: candle momentum, price action, the distance from the EMAs, divergence of
price peaks against MACD or RSI) after an account of how much of the lost chat's research is recorded;
whether the home Huawei B612 can replace the phone; which Raspberry Pi. "The Neon access is totally on
you." Then: "go go go" -- the authorization for the node's migration and the list in order.

**Health check 2026-10-07 11:00 Tehran** (since 10-06 16:00): every scheduled ANALYZE succeeded, 6 on
10-06 (16:00-21:00) and 06:00-11:00 on 10-07, 5-9 minutes; the owner's UPDATE at 17:55. 24 hours: 20
market snapshots and states (16 scheduled, 4 user), 16 analysis snapshots, 48 outcomes, 251 price
observations, 488 news items, Direction at 13:00 and 06:00 (STRONG BULLISH on 8 of 8 panels, none
resolved); candles to 10-06. Decisions FAIR / WAIT / WAIT on all 20; premium -2.46% to -1.26%. PAPER: 16
EVAL rows per active account, a REPORT each at 21:00 (sent with its chart), no trade; 1,314.4M against
1,350M, valued at Goldika's sell price. Platforms: Daric 403 on every run; MioGold timed out once; Taline
discarded once and otherwise alternating between two frozen values (267.41M, the frozen value of 10-06,
at 06:00 and 08:00; 266.85M at 07:00, 09:00, 10:00); **HoorGold 267,990,000 in all ten readings from 10-06
17:00 to 10-07 10:00** while Milli and Ayyareh moved -- 6 distinct prices in 24 hours. Verdict: healthy;
open: Daric (addressed below), Taline and HoorGold frozen copies (next in the list).

**Neon without the connector.** The claude.ai Neon connector disconnected with the new session and
cannot be re-attached from inside one. The route now: `neonctl` (Neon's CLI, `npx neonctl`), signed in
once in the owner's browser. Neon's sign-in server refuses Iranian addresses (403 through Cloudflare's
Frankfurt edge), and Node ignores the workstation's proxy unless told: `NODE_USE_ENV_PROXY=1` (Node 24)
sends it through `HTTPS_PROXY`, the local proxy on 127.0.0.1:18080 that exits in the United States.
Production's connection string is kept in `~/.gpm_neon_url` (outside the repository, never printed);
the Postgres endpoint itself answers this workstation directly, and health checks open it read-only.

**The research record** (the owner asked how much of the lost chat is kept): all 72 research scripts
are committed; 65 are cited by name in this file, `SP_C_HANDOFF.md` or `LESSONS_LEARNED.md`, and the
seven that are not carry their section in their own header and have their results in sections 1.1, 2,
4 and 9. What exists only on this machine is `research/data` (75 MB, git-ignored); it is now copied
daily to `D:\claude-history-backup\gold-premium-research-data`. On the owner's trend ideas the record
already holds: the distances to the SMA/EMA 20/50/200 (context, no edge over the base rate: sections
1.1, 2, 3); the EMA 20/50 cross (its edge reversed out of sample; the death cross a risk signal: section
5); MACD and RSI crosses and every candle pattern (failed: section 2); RSI divergence inside the chartist
(+/-0.25 of a view that correlates +0.04 to +0.12 with what follows: section 21); simple trend rules
(none beat holding: section 9); acting daily against every 10-20 days (daily lost: section 22).
Untested: time-series momentum over 3-12 months (listed in 1.1, never run), MACD divergence, the EMA
distance as the size of the swing rather than its timing, and divergence as a member of the room.

**The B612 and a Raspberry Pi.** The Huawei B612 is an LTE router on closed firmware: no shell, no
Python, no scheduler, so it cannot run the node; it can be the connection the node uses. A Raspberry Pi
5 1GB ($45, the one model the 2025-26 memory-price rises spared) runs the node and small scheduled jobs;
2 GB ($77.50) is the floor for a database or containers. A home Pi cannot take connections from the
internet behind the carrier's NAT without a tunnel, and its uptime is the home's power and LTE link:
GitHub Actions and Neon stay the always-on part. The owner's decision is open.

**The node in production** (the owner's authorization, 2026-10-07). `sql/neon_migration_iran_node.sql`
applied in one transaction at about 12:15 Tehran: `iran_node_readings` (12 columns, its index) and the role
`iran_node` made by SQL -- not superuser, no role attributes, no memberships, INSERT on that table only;
`market_snapshots` 755 rows before and after. From this workstation's Iranian connection, as
`iran_node` over Neon's HTTPS endpoint: one Daric reading inserted (node `pc`, 12:19 Tehran: bid
261,583,680, ask 262,799,360); SELECT on `market_snapshots` and on its own table, and DELETE, refused.
The phone's `~/.iran_node.env` takes `NEON_URL=postgresql://iran_node:<password>@<pooled host>/neondb`
(letters and digits only, so it survives being typed or pasted).

**Production reads the node** (`sp-d-iran-node`, 0dd60fc). `main._daric_from_node`: when Daric's own
collector fails, the newest OK node reading of the last `NODE_MAX_AGE_MINUTES` (30; the node reads
every 15) becomes Daric's two-sided quote, its read time the quote's time, before
`validate_market_prices` -- so the stale-quote rules apply to it as to any platform. Fails open: without
the database or a recent reading Daric stays out as before. The model `IranNodeReading`, the target
schema and the migration declare one table, and the role may only insert (`kpi_coherence.test_35`); the
fallback in `kpi_signal_confirmation.test_48-51`. PAPER's venue chain (Daric > Goldika > Ayyareh) takes
Daric with no change: its trades and its value move from Goldika's 2.37% spread to Daric's, so the
accounts' value steps up on the first run with Daric (Daric's bid, not Goldika's, values the grams).
The branch also carries the sanity ranges of section 30 (merged from `hotfix-validation-bounds`).
Suite 30/30, compileall. **Merged** on the owner's review: `v1.8safe` tags `main` at 04a37e1; `main` and `SP-D`
at cf3c520 from 12:45 Tehran; KPI Suite green on both.

**NEON MIGRATION REQUIRED = YES**, applied (above).

**Later the same day.**
- *The phone is live.* `node.py --setup` (0cba828) asks for a 14-character password and writes the
  settings (typing the URL failed twice); the role's password was changed to it. The S10 has sent four
  readings an hour without a gap since 10-06 19:28; 9 of 79 Daric readings are Daric's own failures
  (7 connection errors, 2 empty order-book sides), stored as ERROR and never used. **The 14:00 run took
  Daric from the phone** ("Daric: from the Iran node (s10, read 1 min ago)", 262,176,670), the first
  since 10-03; the 13:00 run, before the phone's settings, discarded it as before.
- *The node also reads Taline, HoorGold and MioGold* (e69d482) through the repository's collectors,
  to set what Iran sees against what the runner is served. **The first comparison, 14:00:** the runner
  was given Taline at about 266.86M (discarded, +1.64% from the median 262.56M) while the phone read
  262.63-262.70M in Iran: a copy, the same value the runner stored at 07:00, 09:00 and 10:00 that
  morning, inside the 1% band while the market stood higher. HoorGold (263.10M) and MioGold (261.95M)
  were identical on both sides. `research/rd_frozen_copies.py` (the stored record since 09-14): HoorGold
  held one price for 3 hours or more while the others moved in 27% of its readings, MioGold 10%, the
  rest 0-3%; returning to an exact earlier price is common to all (4-11%; Taline 16%) and is not by
  itself a signature. The rule waits for a day of side-by-side readings.
- *TSETMC is not collected anywhere in production.* The money-flow member stays out of the room until
  the node reads TSETMC's client types (sections 24, 27); the only TSETMC data are the research pulls
  in `research/data`, copied daily to D:.
- *Today's fall* was the dollar's (269,100 to 263,800 toman, 06:00-13:00; fair value -2.6%, the premium
  unchanged). The room at 13:01: ALL_GOLD, 35.3% of the weight for fixed income against the 60% needed
  on the review of 2026-10-17; its evidence ends at the 10-06 candle by design. The dollar stood 22%
  above its 50-day average at the 10-06 close, 18K 18%: the measured warning (the dollar under its
  50-day, section 2) is far off.

## 32. Trend identification in the room: pre-registered (2026-10-07)

**The owner.** The room is to replace a senior trader who identifies trends and acts promptly: follow
the momentum of candles and price action, the distance between the price and its EMAs, the divergence
between price peaks and MACD or RSI. "A whole heavy load R&D" -- full authority while the owner is in a
meeting. What the record already holds is listed in section 31 (the distances, the EMA cross, MACD and
RSI crosses, candle patterns, simple trend rules, acting daily: tested, none an edge). What it does not
hold is tested here. **Written and committed before any of it was run.**

**Candidates** (18K is tgju's daily close; fixed income is the index of `rd_rebuy.fi_log`; every
signal causal, known at day i's close):

```text
TSMOM k        time-series momentum against the cost of money: 18K's log return over the last k
               trading days minus fixed income's over the same days; > 0 leans gold (+1), < 0 fixed
               income (-1). k = 63, 126, 252 (3, 6, 12 months), and the majority of the three
RSI div        divergence at confirmed swings (the chartist's ZigZag, section 21): on the day a swing
               high is confirmed, a higher high than the previous swing high with RSI(14) at it 2
               points or more lower leans fixed income (-1) for 20 trading days; the mirror at swing
               lows leans gold (+1); otherwise 0
MACD div       the same with the MACD line (12/26/9) as a share of the price, lower at the higher high
               (any amount), higher at the lower low
stretch size   when the room swings out, the share sold depends on 18K's distance from its EMA50,
               z-scored against its last 500 days: z >= +1 sells 60% of the grams, z <= 0 sells 20%,
               otherwise 40% as now; when it swings out is unchanged
```

**Tests.**
1. *Alone:* gold over fixed income in the next 20 trading days (`X20`) on the days each member leans
   -1, +1, and on all days, 2016-2020 and 2021-2026 apart. For the two divergences, the 20 days after
   each event against 1,000 shuffles of as many dates in the same era (lesson 24); outside the 5-95%
   band of the shuffles counts as a difference.
2. *In the room:* the production room (`rd_room_reentry_sense`, "veto + turn": reviews every 10 trading
   days, the stock-index veto and early return, weights of section 27 without money flow) with each
   candidate as a member at weight 1.0 -- stretch size as its sizing rule -- against the room as built,
   window by window: the 18 Afran windows from 2020 and the 27 index windows from 2018 (two years, one
   starting each Persian quarter), all 10 review offsets, at Daric's 0.30% and at Goldika's 2.37%.

**Acceptance, fixed now.** A candidate is adopted only if, at both costs and in both sets of windows,
its paired difference against the room as built is +0.5 points or more at the median over offsets,
improves 60% of the windows or more, and does not lower the worst window by more than 1 point.
Anything else is recorded and rejected. The last two years are reported, not used to decide.

Research only: production unchanged. **NEON MIGRATION REQUIRED = NO.**

### 32.1 Results (`research/rd_trend_room.py`, run after d519da5)

The script's room reproduces `rd_room_reentry_sense.variant("veto + turn")` exactly (end values equal
at every offset of a test window) before any candidate was added.

**How often each leans** (gold / none / fixed income, 2016-2026): TSMOM 63 and 126 61 / 0 / 39%, 252
68 / 2 / 30%, the vote 64 / 1 / 34%; each divergence 1 / 92 / 7%. Since 2014 the chartist's swings
give RSI 10 bearish and 2 bullish divergences, MACD 11 and 3.

**Alone** (gold over fixed income in the next 20 trading days, log %; all days +2.02 in 2016-2020,
+2.15 in 2021-2026):

```text
                  2016-2020: when gold / when fixed income     2021-2026: when gold / when fixed income
TSMOM 63          +2.74 (776) / +0.90 (501)                    +3.13 (982) / +0.62 (627)
TSMOM 126         +3.49 (725) / +0.08 (552)                    +1.87 (1035) / +2.66 (574)   reversed
TSMOM 252         +3.19 (728) / +0.39 (488)                    +2.05 (1232) / +2.49 (377)   reversed
TSMOM vote        +3.37 (744) / +0.15 (498)                    +2.27 (1116) / +1.89 (493)
divergences       every era and kind inside the 5-95% band of 1,000 shuffles; bullish ones too few
                  (0 and 1 events); after RSI's bearish ones 2016-2020 gold beat fixed income by +2.68
```

TSMOM 63 separates in both eras, 126 and 252 reverse after 2020. Even on TSMOM 63's fixed-income
days gold still beat fixed income on average (+0.90, +0.62): a lean to leave that is right in rank is
still wrong in sign.

**In the room** (paired against the room as built; median over offsets, share of windows improved,
change of the worst window):

```text
                   Daric 0.30%                                  Goldika 2.37%
                   Afran (18)              index (27)            Afran (18)              index (27)
room as built      +4.0..+5.7%, worst -3.3  +3.9..+5.6, -11.3     +1.3..+3.1, -4.6         +1.1..+2.8, -16.1
+ TSMOM 63         -4.81 pp, 13%, -4.27     -3.96, 20%, -0.28     -5.34, 7%, -5.87         -4.39, 14%, +0.41
+ TSMOM 126        -6.35, 3%, -4.98         -4.65, 11%, -0.84     -7.03, 5%, -7.52         -3.61, 11%, -0.11
+ TSMOM 252        -4.44, 5%, -0.95         -4.12, 17%, +4.69     -3.76, 8%, -2.12         -2.92, 24%, +6.59
+ TSMOM vote       -5.94, 6%, -3.93         -5.50, 13%, +0.01     -6.49, 8%, -6.10         -5.21, 14%, +1.39
+ RSI div          +0.00, 9%, 0             +0.00, 24%, 0         +0.00, 9%, 0             +0.00, 24%, 0
+ MACD div         +0.00, 14%, 0            +0.00, 29%, 0         +0.00, 16%, 0            +0.00, 32%, 0
stretch size       -2.31, 31%, -2.68        -2.61, 24%, -6.83     -1.17, 35%, -1.95        -1.29, 29%, -5.25
the last two years (offset 0, Daric; reported, not used): as built +9.5%, TSMOM 63 -2.9%, 126/252/vote
-0.3%, the divergences +9.5%, stretch size +15.3%
```

**Verdict under the bar fixed in advance: every candidate is rejected** (0 of 4 conditions met by
any). Why, from the numbers:
- *Time-series momentum* leans to fixed income on 30-39% of days, so it carries the committee over
  60% far more often; each extra exit leaves gold, and gold beat fixed income even on those days. It
  costs 3-7 points per two years and lowers the share of winning windows from 83-100% to 3-61%. The
  12-month version alone lifts the worst index window (+4.7 to +6.6 points) at -3 to -4 points of
  median: insurance at a price the bar does not accept.
- *Divergences* are too rare at the chartist's swing size (12-14 events in twelve years) to move a
  committee of seven: no change at the median, no change to the worst window; alone they are
  indistinguishable from random dates. A finer swing would give more events; it was not
  pre-registered and is not tested here.
- *Stretch sizing* sells more of the grams when 18K is far above its EMA50, which in an uptrend means
  selling more at the start of extended legs: -1.2 to -2.6 points at the median, the worst window
  2-7 points lower. Its last two years (+15.3% against +9.5%) are the flattering window of lesson 23.

**What this adds to the record.** Section 31 listed what was already tested; with this, every element
of the owner's trend idea that the data can test has been tested: the distances, the crosses, the
candles, simple trend rules, time-series momentum, divergence of RSI and MACD, stretch as size. None
improves the room, in toman, against holding gold. It is the same finding from another side as
section 25's ("no price, chart, flow or LLM reading has called the start of a jump") and lesson 28
(leaving gold is the expensive mistake): a trend member's value would come from leaving gold before a
fall, and in this market the falls are short and the drift is strong. The room's remaining open
inputs are those that are not functions of 18K's own price: money flow (TSETMC, through the node),
the news read by the LLM member, Tether.

## 33. Money flow joins the room: TSETMC through the phone (2026-10-07)

**The owner.** "Let's do the TSETMC on the phone", then: "I'm ready for the next step, adding the member
and so on; and yes, you can seed the history from the research. Go ahead."

**On the phone** (`iran_node/node.py`, 82d0dd9). TSETMC answers Iranian addresses only. The per-day
endpoint `ClientType/GetClientTypeHistory/{insCode}/{yyyymmdd}` returns one fund's day with values in
375 bytes (the whole history is 549 KB a fund; the "today" endpoint has volumes and counts but no
values, and returns HTTP 500 for a day until it has closed). Once an hour (the run in the first quarter
of the hour), for each of the last 7 days not yet fetched, the node asks for each of the 19 funds of the
research record and sends one row per fund and day (`source` "tsetmc", `instrument`
"CLIENTTYPE_{insCode}", `detail` the trading day, `payload` TSETMC's record); what it fetched is
remembered in `~/.iran_node_state.json`. From this workstation in Iran the first test read 76 fund-days
(19 funds, 10-03 to 10-06) in 14 seconds in all.

**The member, measured before it was built.** Section 27's figures for money flow (+5.1 to +8.0% against
holding) were measured on an earlier room, before the stock index's veto and its early return. On the
room as it runs, paired window by window (`rd_trend_room.room`, all offsets):

```text
                         as built                       + money flow at 0.5             paired
Daric,   Afran (18)      +4.0..+5.7%, worst -3.3        +5.0..+9.0%, worst -3.7         +0.83 pp; better 52%, worse 11%
Daric,   index (27)      +3.9..+5.6%, worst -11.3       +5.6..+7.8%, worst -10.2        +1.42 pp; better 54%, worse 10%
Goldika, Afran (18)      +1.3..+3.1%, worst -4.6        +2.5..+6.9%, worst -4.9         +0.97 pp; better 53%, worse 11%
Goldika, index (27)      +1.1..+2.8%, worst -16.1       +2.4..+5.5%, worst -16.5        +0.67 pp; better 53%, worse 11%
the last two years (offset 0, Daric): +9.5% either way
```

Against section 32's bar it clears the median (+0.67 to +1.42) and the worst window (within a point),
and not the 60% of windows improved: about 36% of windows do not change at all (the member rarely tips
a vote of eight), and improvements outnumber worsenings five to one. It is section 18's designed member
and the owner's decision; the shortfall is recorded, not hidden.

**Built** (`sp-d-trend-rd`):
- `src/seed/gold_fund_flows.json` (`research/build_flow_seed.py`): each day's buyer power --
  individuals' value per buyer over value per seller, summed over the funds that traded -- for 1,711
  days, 2017-07-30 to 2026-10-03, and the 19 funds. The other seeds are untouched.
- `analysis/room.py`: `money flow` at weight 0.5 (`WEIGHTS`), `money_flow()` (the 20-day mean over the
  funds' days, carried to 18K's days while under a week old), `member_leans(flow=...)` (z-scored over 500
  days, +1 above +0.5), its words in `WHY` ("buyers / sellers in the gold funds are stronger than
  usual"); `FLOW_MIN_FUNDS` = 15, fixed before any data from the phone was seen.
- `main._room_flow`: the seed, then the node's days after it -- a fund's latest copy of a day, a day
  only when 15 of the 19 funds have it; `_room_state` passes it to the room and, if it cannot be built,
  the member has no view and the room carries on with seven.
- `repository.get_node_rows`.
- **Parity** (`research/check_room_parity.py`, now with the flow): production's eight members match the
  research room on 100.00% of days since 2018, money flow included, and the posture on all 575 days of
  the last two years.
- `kpi_paper` 37/37: test_24 (eight members, money flow at 0.5), test_30 (the research construction),
  test_31 (the phone's days after the seed: 15 of 19, the latest copy, the seed's days kept), test_32
  (the seed, the wiring, the fail-safe). Suite 30/30, compileall.

**What the owner will see.** The room's 21:00 line counts the members, so it reads "of 8" instead of "of
7"; when money flow is among the reasons, its words appear. No layout changes.

**NEON MIGRATION REQUIRED = NO** (the node's table of section 31). Awaiting the owner's review; then a
safe tag and the merge.

## 34. Neon suspended: the month's 5 GB of transfer spent by mid-month (2026-10-14)

**The owner** (2026-10-14, a week after section 33): "there are a bunch of stuff outstanding and
everything looks like shit now. Broken."

**What broke.** Every GitHub run succeeded (16 ANALYZE a day from 10-07 to 10-13, the owner's UPDATE,
DIRECTION and REPORT), so nothing failed visibly. Production's database refuses every connection:
"Your account or project has exceeded the quota." The project's period runs 2026-10-01 to 11-01 and its
`data_transfer_bytes` stood at 5.92 GB (2.26 GB on 10-06). Neon's free plan includes 5 GB of public
network transfer a month per project; past it the compute is suspended, connections drop, and the
suspension is not lifted by the next connection -- it holds until the period rolls over or the plan
changes ([Neon, free plan limits](https://neon.com/faqs/free-plan-limits-and-quotas)). The first run
refused: **2026-10-13 21:00 Tehran** (run 38439212761, 185 quota errors); every run since has collected
prices and stored nothing. The app fails open on the database, so the runs stayed green; PAPER, the
push, ANALYZE's history and the phone's uploads are down, and the phone keeps its readings in its
spool.

**Why.** About 450 MB a day left the database. Every hourly run read the last week's analysis snapshots
whole -- six JSON documents a row (evidence, features, read model, intelligence, technical state, data
quality) -- to use an id, a timestamp, a regime or four prices:

```text
outcome backfill        the last 168 h of snapshots, whole; then each needing work again, whole, in
                        evaluate_snapshot -- about 80 a run, the retries of SP-C's open item (3-4 min)
regime features         up to 500 snapshots, whole, for regime_state
evidence package        2 x context snapshots, whole, for id and timestamp
```

The month before PAPER and Direction (10-03, 10-05) added the room's and Direction's full candle reads
(about 20,000 small rows a run); those are a smaller share and were not changed.

**Fixed** (`hotfix-neon-egress`, 1d8ae50, cut from `main`; merged into `sp-d-trend-rd`):
`repository.get_analysis_snapshots(columns=...)` loads only the columns given (`load_only`); the
regime features ask for id, timestamp and regime; the evidence package for id and timestamp; the
backfill for id and timestamp, and `evaluate_snapshot` for the five values it reads. Behaviour is
unchanged. `kpi_coherence.test_36` records the SQL those readers send and fails if any names a snapshot
document; on `main`'s code it fails (the backfill's SELECT carries all six). Suite 30/30. The size of the
saving can be measured only when the database is reachable again (`data_transfer_bytes` across one run).

**The phone** (7661ed5, `sp-d-iran-node`): its spool held 3,000 rows -- seven days at about 400 rows a
day since TSETMC joined -- and would have dropped the oldest; it now holds 30,000, the month with room.
The owner pulls it once (`git pull`).

**The decision for the owner.** Production stays suspended until 2026-11-01 (18 days without storage:
no PAPER, no push, a hole in every 30-day window) unless the plan changes. Neon's Launch plan has no
monthly minimum and bills use -- about $0.106 a compute-hour, 100 GB of transfer included, by
third-party pricing pages -- which at this project's 60 or so compute-hours a month is roughly $6-10.
Upgrading restores production at once; with the fix above the project should fall back under the free
plan's 5 GB, to be confirmed on the first measured run, and November can return to free. Paying from
Iran is the owner's question. Waiting costs nothing in money and 18 days of record.

**NEON MIGRATION REQUIRED = NO.**

### 34.1 The owner's decision, and the second cut (2026-10-15)

**The owner.** "Will we ever face such an issue, or is it because we pulled and stored large amounts of
data previously? If it's a one-time issue, let's wait for the reset, as I planned to move on this
project with zero penny." The answer: not one-time. The cap counts what the database **sends**, every
month; stored history mattered only because each run read it again, so the old code would reach 5 GB
by mid-month every month (about 460 MB a day). After the first cut the estimate is 2.5-4 GB a month --
under the cap without a wide margin. **Decided:** wait for 2026-11-01; merge the fix before it; a
second cut; measure on the first day and watch the month-to-date figure in every health check.

**The second cut** (`src/persistence/candle_cache.py`). tgju's daily candles -- 18K up to three times a
run, the dollar, world gold's 12,000 days, about 26,000 rows a run -- are kept between runs in a file
the workflow caches beside `state.json` (`CANDLE_CACHE_FILE`). Each read asks the database only for the
instrument's count and latest day: equal to the copy's, no candle row is read; newer, only the days
after the copy's are read; anything else, the copy is dropped and the instrument read in full. The
candles are stored first-seen and never revised, which is what makes a copy safe. Readers:
`direction.load_series` (Direction, the quant engine's 18K, the Direction ledger), `main._room_state`,
the 21:00 chart. Without the variable (tests, local runs) every read goes to the database as before.
`kpi_coherence.test_37`: the four cases against a real table, each equal to a direct read; the wiring.
Suite 30/30.

**Measure on 2026-11-01.** `data_transfer_bytes` from Neon's API (`PROJECT_OPERATIONS.md` section 15,
step 9) before the 06:00 run and after the 07:00 run; the difference is one run's transfer plus the
phone's spool flush (inserts send little back); projected over a month against the 5 GB.

**SP-Dd merged** on the owner's approval ("yes on all 4 items"): `v1.9safe` tags `main` before it.

## 35. SP-De: the quant fit, then the room alert, Direction's EMA lines, Tether, the LLM member (2026-10-15)

**The owner** (2026-10-07 and 10-15): fix the quant fit's random starts ("retry is better, what's your
call?"); the room alert at 3 of 8 with its push; Direction's EMA lines as previewed; Tether as a member
("a must to have, do it"); the LLM member onboarded; most of these under one sprint. Production's
database is suspended until 2026-11-01 (section 34), so SP-De is built and tested on `sp-de` and
reaches `main` before the reset, as one reviewed batch.

**35.1 The quant fit** (`analysis/quant.fit_regimes`). The two-regime fit searches 5 random starting
points from numpy's global generator, unseeded: two fits of the same returns could differ, and on
2026-10-07 one search failed (an SVD that did not converge) and the engine reported itself
unavailable. A retry alone keeps the randomness; a seed alone keeps the failure. Both: each attempt
draws from a fixed seed (`FIT_SEEDS` 0, 1, 2), a failed attempt is retried from the next, numpy's random
state is restored afterwards, and only when all three fail is the engine unavailable as before. The
seed used is kept with the fit. `kpi_paper.test_33` (the same fit every time, the program's random
state untouched) and `test_34` (a failed search retried from the next seed); kpi_paper 39/39, suite
30/30.

**35.2 The 21:00 chart without the database** (the owner, 10-15: "the important part for the nightly
msg for me is the chart, is that possible now? if yes, we should, overall, design a try and error
route that if the NEON is down, then another route can survive mostly"). Since 10-13 21:00 no 21:00
message has gone out: PAPER keeps its accounts in Neon, `_paper_run` fails at its first query, and the
report and its chart go with it. The chart needs only 18K's daily candles, and tgju serves those to the
runner directly.

- **The route.** `main._evening_fallback` runs after `_paper_run` on scheduled runs from 21:00 Tehran.
  It asks the database `SELECT 1` (`_database_reachable`). If that answers, PAPER's own report carries
  the chart and the fallback sends nothing. If it doesn't, it does four things:
  1. fetches 18K's candles from tgju (`persistence/candle_cache.direct`: one request, 1,000 days,
     dropping today's incomplete candle and rows without a valid price, classified as `main` stores
     them);
  2. draws the report's own chart (`_chart_png`, now shared with `_paper_chart`), titled "18K daily",
     with no trades and the live line at the platforms' tgju-level price that Direction uses;
  3. sends it with the caption below;
  4. records the Tehran day in `state.json` (`evening_fallback_date`), so it goes out once a day.

  It never raises.
- **Depth, measured** on tgju's full 18K history (3,529 days to 10-14): from 400 days up, the last N
  days give the same chart as all 3,529. That covers the EMAs, swing levels, trendlines, Fibonacci and
  the chartist's reading. EMA50 differs by 5e-7 at 400 days and by 0 at 1,000. Fetching 1,000 days
  takes 0.9-1.2 s.
- **Only the chart reads tgju directly.** The room and the quant engine replay the whole history; fed
  1,000 days, they would decide on less without saying so (`kpi_paper.test_37`).
- **The caption**, previewed 10-15 on live data:
  ```
  GOLDPremium: EVENING · 23 Mehr 1405, 21:00
  18K 26.34M · rising (markup), up from 15.65M on 26 Khordad
  Channel +0.55%/day, price in its lower half
  3.1% above the 20-day (was 2.2%), 10% above the 50-day
  PAPER resumes when the database is back
  ```
  - The phase words are the room report's ("Phase: ...").
  - The EMA distances are computed as Direction computes them: the live price is taken as a
    provisional close, and "was" is the distance at the last completed close.
  - A correction to the first preview: it said PAPER resumes "(1 Aban)", but Neon resets on
    1 November, which is **10 Aban**. The caption carries no date, since a future outage has none.
- **KPIs.** `kpi_paper` 43/43, suite 30/30:
  - `test_35`: nothing before 21:00 or with the database up; with it down, one chart with its
    caption, once a day;
  - `test_36`: the direct candles' shape;
  - `test_37`: only the chart reads tgju directly;
  - `test_38`: the caption, line by line.
- **Locked** by the owner on 10-15 ("fine"), with the merge before that evening's 21:00 run. `main` was
  tagged `v1.10safe` first, then fast-forwarded to `sp-de` with 35.1 and 35.2.

**35.3 What survives a Neon outage: production's runs of 10-15, and the proposed routes.** Every
database call fails in about 0.9 s and is caught. Runs stay green. From the logs of the 16:00 ANALYZE
and the 13:22 UPDATE:

| What | During the outage | Proposed route (not locked) |
|---|---|---|
| 21:00 chart | nothing sent | built, 35.2 |
| Deep-discount push | cannot fire: `PUSH ... fire_at=None -> NO_DATA` | the last thresholds kept in `state.json`, used for a few days |
| UPDATE: deep-discount level, "Bigger than", trend | missing (bubble queries fail) | the kept threshold; "Bigger than" stays missing |
| UPDATE: RUN and DAY baselines | `RUN=N/A DAY=N/A` | `state.json` already holds the last 30 readings |
| The hourly record (snapshots, platform prices, states) | lost, about 16 readings a day | a spool in the Actions cache, flushed when Neon returns, as the phone spools its readings |
| Stale-quote check | skipped: it fails open, so a frozen copy can pass | the spool and `state.json` history give the repeat rule part of its window |
| Daric | lost: the runner gets 403, and the node's rows are in Neon | the phone keeps them in its spool; no route to the runner without a second store |
| Direction, the room's inputs, tgju candles | fail | the candle cache plus tgju's days after it (exact, unlike 1,000 days alone) |
| BUY signal | held: confirmation fails closed | unchanged, by design |
| News | 0 stored; 2.5 minutes a run spent failing to save | dedup in `state.json`, with the news wing |
| PAPER | paused | none: the accounts live in Neon |

The record matters beyond the outage. The deep-discount pool is 30 settled days, so in early November
it will hold 10-02 to 10-13 and whatever arrives after the reset, unless the spool fills the gap.

**35.4 The spool: the record kept while Neon is out of reach** (the owner, 10-15: "ok" to the spool
first, then the kept push level). This is 35.3's first route.

- **What is held.** Some writes fail because the database cannot be reached: a SQLAlchemy
  `OperationalError` or `InterfaceError`, as every write since 10-13 21:00 has failed. Those writes
  are appended to `record_spool.jsonl`, one JSON line each, with their datetimes kept
  (`persistence/spool.py`, on when `RECORD_SPOOL_FILE` is set). Three kinds are held:
  - **the reading** (`main._hold_reading`): the snapshot, its platform prices and the market state,
    as `save_market_state` would store them (`repository.market_state_fields`, now shared). The
    relative-valuation context is left out, because computing it reads the database.
  - **each price observation** (`save_price_observation`).
  - **the room's daily inputs** (`_collect_room_inputs`): the stock index, Afran and etfbaz's five,
    including Tether, whose history the owner wants for its member. Each instrument is held once a
    day, matching the stored rule that the first value seen is the day's.

  A row the database rejects is not held, because it would be rejected again.
- **Where it lives.** The workflow keeps `record_spool.jsonl` in its Actions cache beside
  `state.json` and `candle_cache.json`. If an UPDATE overlaps a scheduled run, one cache can replace
  the other's. That is the same exposure `state.json` has always had.
- **Writing back.** It runs at the start of scheduled runs only (`main._flush_spool`), before the run
  takes its own time and before the stale-quote check reads the platform history:
  - writes go oldest first, with their original times;
  - a reading or a day's input is committed alone, observations in batches of 50;
  - a run spends at most 240 s on it, and the rest wait for the next run;
  - a rejected batch is retried one write at a time, and only the rejected write is dropped;
  - an unreachable database stops the flush and keeps everything not yet written;
  - readings and observations already stored, at the same time and kind, are skipped, so a flush cut
    off before its file was rewritten does not store anything twice. Day inputs are skipped by
    `save_daily_candles` itself.

  The UPDATE path never writes back: a reader's Update does not wait on the record.
- **What it cannot recover.** It keeps only what the runner collected. The following stay missing
  for the outage:
  - analysis snapshots and outcome evaluations (derived later from stored state);
  - Direction panels;
  - PAPER;
  - news, until the news wing keeps its own state.

  Daric comes back through the phone's own spool. tgju's candles backfill themselves on the first
  run (`_tgju_requests`).
- **Expected volume.** For the rest of this outage, from the merge to 11-01: about 16 readings and a
  few hundred observations a day, and a few day inputs. That comes to a few thousand lines and
  1-3 MB, stored within the first one or two runs after the reset. Writes are inbound transfer; the two
  range queries that check for stored rows return nothing for the outage. `NEON MIGRATION REQUIRED = NO`.
- **KPIs.** `kpi_coherence` 35/35, suite 30/30:
  - `test_38`: a reading, an observation and two day inputs are held on an unreachable database and
    not on a rejected row; written back with their times; held again, still stored once;
  - `test_39`: a rejected write is dropped; an unreachable database keeps the rest; the time bound;
  - `test_40`: the wiring (scheduled runs only, before the run's time and the stale-quote check; the
    workflow's cache and variable).
- **Merged** on 10-15 with the owner's approval ("approved: push sp-de to SP-D and main"): `main` tagged
  `v1.11safe` first, then fast-forwarded with 35.4.

**35.5 The news wing: the owner's channels read from GitHub's side, and the runner pinned** (10-15).

**The owner's channels:**
- betasahm1
- trade_fundd
- bourse24ir
- fundbase_ir
- bidarbourse
- radpoool
- khabarfouri

The owner: "you can add to this list as you wish, but i propose not to over pollute it". The routing,
agreed:
- Telegram channels are read by GitHub's runner;
- geoblocked Iranian sites (Tasnim, cbi.ir; both removed from the RSS list on 09-21 for refusing the
  runner) are read by the phone.

The reader is `collector/news/telegram_channels.py`. It reads the channel's public web preview,
`t.me/s/<channel>`, paging back with `?before=<id>`; not wired yet.

**Probe from the runner** (`research/probe_telegram.py`, temporary branch `probe-telegram`, deleted).
Results were read as check-run notices through `api.github.com`, because the log host timed out from
the workstation. Posts from 10-08 00:00 UTC to 10-15 15:00 UTC:

| Channel | Posts | A day | Read in |
|---|---|---|---|
| khabarfouri | 1,105 | 160 | 30 s |
| bourse24ir | 841 | 112 | 21 s |
| betasahm1 | 440 | 59 | 10 s |
| bidarbourse | 178 | 24 | 8 s |
| trade_fundd | 159 | 22 | 5 s |
| fundbase_ir | 89 | 12 | 3 s |
| radpoool | 1,200 in 6.6 hours | about 4,400 | 32 s, cut at 60 pages |

- **All seven answer the runner.**
- **radpoool is a price ticker, not news.** 1,197 of its 1,200 posts carry a rate. It is left out
  of the news; as a free-market rate source it may have another use, unexamined.
- **Without it, about 400 posts a day.** That averages 17 an hour and more in trading hours.
- **Keywords cannot classify them.** "ارز" (currency) is also the start of "ارزش" (value), so the
  stock channels' "ارزش معاملات" (trading value) counted as dollar news. The keyword classifier has
  read `KEYWORD` on every stored event since SP-C (§27.5's register entry), and this is its failure
  in the new sources too.
- **The real movers are there.** The samples include the exchange centre's new rates
  (khabarfouri, 10-11 10:03 Tehran), the remittance dollar (betasahm1, bidarbourse), Hormuz
  tanker costs and the war's toll on households.

Whether the channels carried the news behind 10-09 to 10-13's -4.4% is to be read against the
dollar's hourly record once the wing runs. The record of those days is in Neon, out of reach until
11-01.

**The design proposed to the owner (not locked):**
1. **Sources.**
   - Telegram: six channels, read each scheduled run from the last post seen; the seen ids kept in
     `state.json`, so no database is needed.
   - RSS: keep Google News "iran rial" and "middle east strike", donya-e-eqtesad and tejaratnews;
     drop goldbroker (a median of 26 days old) and kingworldnews (off-topic).
   - The phone: Tasnim, from 11-01, as `iran_node_readings` rows (no migration).
2. **Reading.** One Groq request a run (`openai/gpt-oss-120b`, the free tier; section 16 reached it
   from the runner) reads each new post and returns, in a strict format:
   - relevance to the dollar and gold;
   - the dollar's likely direction;
   - event type;
   - impact;
   - a one-line English gist.

   It never produces a price. The keyword path stays as a labelled fallback.
3. **Out.**
   - a push for high-impact posts, rate-limited (preview to be locked);
   - the news block of the revamped Direction;
   - stored with `classification_method = LLM`. This retires the keyword constant and fixes
     `high_impact_count`, so §33.3 and the register entry close.
4. **A forward record.** Each label is scored against the dollar's next 6 and 24 hours. That record
   is the LLM member's evidence (sections 17-18).

**The runner pinned.** `ubuntu-latest` moves to Ubuntu 26 from 2026-10-19 (the probe run's notice).
A runner change under pinned packages broke production once already (section 28, scipy).
`gold-monitor.yml`, `kpi-suite.yml` and `test-task-c.yml` now run on `ubuntu-24.04`, which is what
`ubuntu-latest` is today, so nothing changes until the move. It needs to reach `main` before 10-19.

**The kept push level, reconsidered.** The push threshold, ANALYZE's deep zone and UPDATE's level are
all computed from the stored readings, and nothing keeps a copy outside Neon. A kept level exists
only if a run with Neon up has saved one, and none has since 10-13, so it would do nothing for this
outage. It is deferred to after 11-01, as a copy refreshed every run for the next outage.

**35.6 The owner's decisions on the news wing, the recap parked** (10-15).

- **Sources approved.** The six channels; radpoool stays out ("if there is no way through, ok keep it
  out"). The owner on the channels' bias toward the stock market: they are "the valuable source for
  gold etfs in tsetmc as well". So the reading also judges each post's relevance to the gold funds
  (the ETFs the money-flow member reads, section 33), not only to the dollar and gold.
- **Reading approved** as proposed (35.5).
- **What GitHub cannot reach goes to the phone**, as TSETMC did: cbi.ir, Tasnim, Donya-e-Eqtesad
  (den.ir) "or any other thing that cant be reached through github". The owner: "the termux is the way
  to circumvent the iran geo blocking."
- **The daily recap is parked.** The owner: "the recap being sent daily is crap, just disable it for
  now. dont rewrite or delete, just put it out of cycle." `config.json` `email.send_daily_recap` is
  false, which stops both the Telegram and the email recap at the first scheduled run of the day. The
  code is unchanged; true brings it back.
- **Merging.** The owner: "i dont know why you keep asking for push sp-de to SP-D and main, do it.
  authorized." Approved work is merged with the safe tag first, then reported, without a second ask.
  This batch (the runner pin, the channel reader, the recap parked) went out after `v1.12safe`.
- **Next, owner's order:** tablokhani checked for more value; Direction's revamp (not yet done: its
  preview comes first, as agreed); the codebase audit and clean-up later ("everything now is so
  messy").

**35.7 tablokhani, checked for more** (the owner, 10-15: "there is the tablokhani thing as well, you
can check if there is anything valuable").

The site's front end (152 code chunks) calls many endpoints. Most need an account: "توکن نامعتبر یا
منقضی شده است", an invalid or expired token. Those include the trade history, the market signals and
the big movers; the subscription is paid, so they are not pursued (zero spending). Without an account
they answer:

| Endpoint | What it gives | Used now |
|---|---|---|
| `public/market-indices` | TEDPIX and the market's state | yes, the room's stock-index member |
| `public/smart-money-averages` | per symbol: the 10-day average per-capita buy and sell, buyer and seller counts, RSI14, MA20, the closes 1 and 29 days ago | Afran's close only; the gold funds' figures are fetched every run and dropped |
| `public/fund-categories`, `public/fund-categories/gold-symbols` | 350 funds with their category; 35 gold funds | no |
| `hot-money/{symbol}/daily` | a fund's daily money in, 14 days back (09-27 to 10-14), reachable by GitHub | no |
| `public/hot-money-outcome`, `public/volume-averages` | today's money out, and average volume, per symbol | no |

What follows from it:

1. **A defect in the money-flow member.** Its 19 "gold funds" include **سافرون (insCode
   51200575796028449), a saffron fund**: tablokhani does not list it as gold, and the research marked it
   `NOT_GOLD` in four scripts (`rd_analyst_model`, `rd_downtrend_2026`, `rd_volume_profile`,
   `chart_preview`). But `build_flow_seed.py`, the seed, the phone's list and `main._room_flow` all
   count it. Today it is 0.43% of the 19's trading value (69 of 15,919 B toman a day; 14-day volume
   times the last close), so the error is small now. It may not have been small in the early years,
   when there were fewer gold funds. Fixing it means rerunning section 33's evidence without it. That
   is for the audit.
2. **The member reads 80% of the gold funds' trading value.** Ten funds are missing, among them گنج
   (714 B toman a day), رز ترنج (657), ریتون (485), جام طلا (452), گلدا (413) and آتش (344): funds
   launched or grown after the research's list was drawn. Whether 35 funds read differently from 18 is
   an R&D question for the audit; the largest four (عیار, طلا, مثقال, کهربا) are in both.
3. **A second route for the money flow, from GitHub.** Two sources could keep the member's daily
   input alive when the phone is down, and both are reachable by the runner:
   - `hot-money/{fund}/daily`, once its definition is checked against TSETMC's client types (the
     phone's rows, readable after 11-01);
   - the gold funds' smart-money averages, which are already fetched every run.

   Not built.

**35.8 Direction's revamp agreed in structure; what it needs, measured; two outage fixes** (10-15
evening).

**The owner's review of the drafts.**
- *NEXT MONTH:* the range ("what kind of decision can be made from this") and the new-high chance
  ("does it say probability? again no feed for making a decision") are dropped. Buy-now-or-wait stays
  ("tends to be good").
- *WATCH:* it should discuss support and resistance, how far each is and what happened near them. The
  50-day lines keep the earlier draft's wording ("i like the EMA style of previous msg more"): "18K
  closes under its 50-day, 23.83M (−9%): followed by −2.9% over 20 days".
- *NEWS:* it must conclude, not list. Two conclusions:
  - whether people are rushing into gold or leaving, from the funds' money flow;
  - where the dollar and Tether are likely to go, from the event and what followed past ones ("whenever
    the cbi intervened the prices dropped").
- *Length:* Direction goes as text; Telegram allows 4,096 characters and `kpi_direction` caps it at
  1,500 (owner, 10-03); the drafts are about 1,150.
- *Routine:* the panel is computed at 06:00 and 13:00 and sent only on /Direction. Whether to push it
  is the owner's to decide.
- The approved structure:
  ```
  header (18K, uptrend since, driven by)
  TREND
  BUY NOW OR WAIT
  LEVELS
  WATCH
  GOLD DEMAND
  DOLLAR FROM NEWS
  ```
  Wiring waits for the two measured lines and the owner's view of the filled draft.

**Support and resistance, against the record.** `rd_chart_accuracy` (section 15) measured the
chart's lines on 18K, 2014-2026. Swing levels and trend lines held or broke no more often than a line
drawn at the same distance with no history. At the first touch, trend-line supports bounced less often
than that control (35% against 48%). So the message shows each line's distance and what lines at that
distance did. The levels with an edge are:
- the 50-day breaks;
- the value area of the funds' volume (section 11), which needs the phone's TSETMC volume and so waits
  for Neon.

**Gold demand** (`research/rd_gold_demand.py`, rules fixed in its docstring before the run). Inputs:
the 18 gold funds (saffron excluded) from TSETMC's client types, 2017-2026; ranks against earlier days
only; tgju's 18K over the next 20 trading days.

| Measure (10 days) | Band | 2019-2023 | 2024-2026 |
|---|---|---|---|
| all days | | move +2.00%, 5% drop 22% | move +7.45%, 5% drop 20% |
| buyer power (per-capita money in / out) | bottom 20% | **+0.15%** | **+2.31%** |
| | bottom 10% | +0.39% | **−0.41%**, drop 29% |
| | top 10% / 20% | +4.26%, drop 8% (39 days) | +6.11%, drop 41% (17 days) |
| net money in (share) | any band | no consistent effect | no consistent effect |
| **crowd: buyers against the previous 120 days** | **top 20%** | **5% drop 52%** (usually 22) | **5% drop 37%** (usually 20); move +2.70% |
| | top 10% | **−4.21%, drop 86%** (28 days) | — |

- Two readings hold in both eras.
  - **A rush of buyers precedes drops.** When the number of people buying the gold funds is in its
    top 20%, a 5% drop within a month came about twice as often.
  - **Sellers in control precede a weak month.** When buyer power is in its bottom 20%, 18K gained 2-5
    points less than usual.
- Net money in or out carries nothing.
- Today: buyer power 0.58-0.61, rank about 27-30, normal; crowd (to 10-03) rank 68, normal.
- Production can read both measures from GitHub through tablokhani's 10-day figures (35.7) once the
  seed carries daily buyers.

**Tether's history is on tgju.** `crypto-tether-irr` gives Tether in rial daily since 2020-11-12; it
closed at 264,993 toman on 10-14. That unblocks the Tether member's research, which waited for a
history (section 35).

**/Direction without the database.** `/Direction` rendered only the stored panel, so from 10-13 it
answered nothing. `main._send_direction_report` still reads the stored panel first. When none can be
read, `_direction_live` computes it now:
- `persistence/candle_cache.full_history` fetches tgju's whole history of 18K, the dollar and world
  gold, 1,000 rows a request, the same days the database holds;
- the platforms' prices give the live price.

It writes nothing. On the workstation it took 22 s with Neon refusing. `kpi_direction.test_25` keeps
the rules:
- writes nothing;
- the stored panel first;
- the live computation only as the fallback.

`test_25b` and `test_25c` cover the route and the paging. The message is today's layout until the
revamp is wired.

**The news run stops after three failed saves.** Each of up to 180 items spent about a second failing
against the suspended database, 2.5 minutes a run. After three failed saves in a row the run stores
nothing more and says how many it skipped (`ingest.MAX_CONSECUTIVE_FAILED`; test in
`tests/test_news_collector.py`). The test runner's list there names four tests twice, left for the
audit.

**Merged** after `v1.13safe` (main 2085974); suite 30/30, `kpi_direction` 37/37, CI green on
ubuntu-24.04.

**35.9 The dollar after the news: the year of channels, the keyword pass, the AI model's labels**
(10-15 night).

- **The history.** `research/backfill_telegram.py` ran on GitHub's runner, six jobs in parallel, and
  the files came back through a temporary branch because the log host does not answer the workstation.
  The result is **123,569 posts**:
  - five channels from 2025-10-15;
  - khabarfouri from 2026-01-08, where its 50-minute budget ran out.

  The files are `research/data/telegram/`, git-ignored.
- **Keywords cannot find the events** (`research/rd_news_events.py`, rules in its docstring). The
  "central-bank intervention" matches are mostly other things:
  - steel exporters' currency agreements with the central bank;
  - Japan's yen intervention;
  - an Iran-US memorandum.

  In a year with a war, "military" and "talks" match almost every day: 253 and 222 event days of
  357. Every type therefore reads like the base rate (the dollar's median 3-day move +0.53% on all
  days). The owner's hypothesis ("whenever the cbi intervened the prices dropped") is not tested by
  this, only shown to need the model.
- **The model reads each day** (`research/label_news_days.py`), running on GitHub on the temporary
  branch `probe-news-labels`:
  - each Tehran day gets one request to Groq, `openai/gpt-oss-120b` at low reasoning;
  - the request carries the day's headlines: the first line of each post from khabarfouri, betasahm1,
    bourse24ir and bidarbourse, deduplicated, filtered to the economy and politics, at most 70 a day
    (median 70, 5,440 characters);
  - the model returns `cbi_fx_intervention`, `talks`, `conflict`, `sanctions`, `oil_exports`,
    `dollar_pressure` and a one-line summary;
  - it is never shown a price after the day, and its training predates these events.

  It is paced under the free tier's 8,000 tokens a minute, about 3 hours for the year.
  `research/rd_news_labels.py` then measures the dollar and Tether 1 and 3 trading days after each
  label value, and the model's own `dollar_pressure` against what followed.
- **Tether's daily history** for it comes from tgju (`crypto-tether-irr`, from 2020-11-12).
- **The filled Direction draft** (all but its news line), live at 21:13 Tehran:

  ```
  GOLDPremium: DIRECTION · 23 Mehr, 21:13
  18K 26.25M · uptrend since 8 Azar 1402 · driven by the dollar

  TREND
  This leg +68% since 26 Khordad: dollar +70%, world gold −5%
  2.7% above the 20-day (was 2.2%), 9.9% above the 50-day (was 9.4%)
  20-day 7.0% above the 50-day: bullish since 27 Tir

  BUY NOW OR WAIT
  Waiting for a 3% dip: on days like today it came 27 in 100;
  buying now was 5.7% better on average, and cheaper in 12 of 13 years

  LEVELS (how lines this far away did)
  Resistance 26.84M (+2.2%): broken within 10 days 49 in 100
  Support 24.43M (−6.9%): held 10 days 93 in 100

  WATCH (each with a measured record)
  18K closes under its 50-day, 23.83M (−9%): followed by −2.9% over 20 days
  Dollar closes under its 50-day, 231,127 (−12%): followed by −3.2% over 20 days

  GOLD DEMAND (gold funds, last 10 days)
  Normal. Buyers 1.4x their usual number: from 2x, a rush, a 5% drop
  within a month came twice as often. Buyer power 0.60: under 0.55,
  sellers in control, the next month was 2-5 points weaker.

  DOLLAR FROM NEWS
  <from the model's labels>
  ```

**35.10 The owner's review of the filled draft; gold demand counted by episodes** (10-15 night).

- **21:00:** the evening chart reached the owner's Telegram ("yes i received the chart at 21 good"):
  the fallback of 35.2 worked on its first night.
- **WATCH is vague** (the owner: "idk what msg it want to deliver to the user"). It is to be rewritten
  to say when the uptrend would end and whether that is near.
- **GOLD DEMAND is vague and the wording misleads.** The owner read "buyers 1.4x their usual number" as
  buyer power against sellers. Plain words are needed, and the system's 7-day window ("we normally use
  the 7D MA through out the system"), not tablokhani's 10.
- **"How accurate is this?" Counted by episodes, the evidence is thin.** On 7 days the day-count
  results hold, but rush days come in clusters, and a 10-day rush counted ten times.
  - By separate episodes (`rd_gold_demand.py`, `GOLD_DEMAND_WINDOW=7`):
    - rushes of buyers (top 20%): 12 in 2019-2023, a 5% drop within a month after 4; 7 in 2024-2026,
      after 3. That is 7 of 19 against about 1 in 5 normally.
    - sellers in control (bottom 20% of buyer power): 32 episodes in 2019-2023, a drop after 12; 21
      in 2024-2026, after 4, the normal rate, with a median move of +6.8% against +7.45% on all days.
  - The 48 and 41 in 100 shown earlier were day counts and overstated it. 19 rushes are too few for a
    rate a reader should act on, so the line is to describe demand plainly and claim no forecast.
  - **Lesson:** count episodes, not days, whenever a signal persists. The 50-day break anchors (-2.9%,
    -3.2%) are to be checked the same way in the audit.
- **News through the phone** (the owner: "we need to bring back the websites, that are being geo
  blocked, using the termux. understood?"):
  - cbi.ir, Tasnim, Donya-e-Eqtesad and any site the runner cannot reach are read by `iran_node/node.py`
    and sent as `iran_node_readings` rows, as TSETMC is.
  - While Neon is down they wait in the phone's spool. A route that does not depend on Neon (the
    Cloudflare worker as a relay) is for the audit.

**35.11 Direction v7, wired** (10-15 night; the owner: "good, go ahead", after the corrected WATCH line).

- **Gold demand, the owner's caveat "does it spot the anomalies?": not as first drafted.**
  - The people and size readings missed the largest anomaly on record. In May 2026 individuals put a
    net 39,268 B toman into the gold funds in the middle of the fall, and the two readings said
    "normal" or "sellers in control".
  - Nominal net money cannot be ranked either: it grows with inflation and the funds, and since 2024,
    399 of 638 days ranked in its "top 10%".
  - The fix adds a third reading, **money**: net money in as a share of the buying and selling. All
    three are ranked against the trailing 250 trading days, with the top and bottom 10% unusual.
  - Since 2024 each reading flags 6-12% of days at each end, so none is degenerate. Money catches May
    2026 (6 days heavy buying) and December 2025 (9 days heavy selling).
  - At 10-03, the last day with full data: money rank 77 (normal), people 91 (a rush, 1.67 times the
    usual buyers), size 32 (normal).
  - The section describes and forecasts nothing.
- **WATCH, corrected.** The anchors (-2.9%, -3.2%) were measured against a normal month, not as falls.
  Counted by separate breaks (the first close under the 50-day after five closes above), 18K's next
  20 trading days against all days were:

  | Break | Breaks | Next 20 days | All days | Lower after |
  |---|---|---|---|---|
  | 18K under its 50-day, 2014-2023 | 28 | +0.1% | +1.8% | 50% |
  | 18K under its 50-day, 2024-2026 | 5 | +1.0% | +6.9% | 20% |
  | dollar under its 50-day, 2014-2023 | 35 | +0.6% | +1.8% | 46% |
  | dollar under its 50-day, 2024-2026 | 8 | +4.4% | +6.9% | 12% |

  The line reads: "After past breaks, 18K's next month was weaker than usual, by 1 to 6 points." The
  approved "18K fell about 3% more" was wrong.
- **The wiring.**
  - `analysis/gold_demand.py`: the calculator.
  - `src/seed/gold_fund_daily.json`: the 18 funds' daily individual totals, 1,711 days to 10-03, by
    `research/build_demand_seed.py`, saffron excluded.
  - `main._gold_demand`: the seed, then the phone's TSETMC days (14 of 18 funds a day). It is stored
    with the 06:00 and 13:00 panels as `panel.demand`.
  - `analysis/direction.py`:
    - `dist_prev`, the EMA distances at the close before;
    - `position.usd`, the dollar's close and 50-day;
    - each level's `held_10d_pct`, from `LINE_HELD_PCT` (section 15's table).
  - `alerts/telegram_direction.py`: rewritten to the layout of section 35.9 with the corrections
    above. DOLLAR FROM NEWS is left out until its measurement holds, and GOLD DEMAND is left out when
    its last day is more than 7 days old, so it shows from November 1.
  - One wording change from the draft: "cheaper in 12 of 13 years" became "waiting cost more in 12 of
    13 years", because the house vocabulary bans "cheap".
- **On live data with Neon refusing:** 913 characters without demand, and about 1,150 with it.
- **KPIs:** `kpi_direction` 43/43; tests 22 and 23 were updated for the dropped lines, and tests 29-34
  are new: the layout, the line rates, WATCH's state, demand's flags, staleness and the loader. Suite
  30/30.

**35.12 Health check 2026-10-16, 08:51 Tehran** (PROJECT_OPERATIONS.md section 15).

- **Runs.** Every hour from 06:00 to 21:00 Tehran on 10-15, and 06:00, 07:00 and 08:00 on 10-16:
  ANALYZE on `main`, all `success`, 1-3 minutes each (short, because every database call fails
  fast). /Direction at 00:11 ran on v7.
- **Neon.** It still refuses: "Your account or project has exceeded the quota", until the 11-01
  reset. Steps 2, 3, 5, 6, 7 and 8 (the database's rows) cannot run, and step 9 (transfer) means
  nothing until the new period.
- **Logs.** They are readable again, through the job-log API
  (`gh api --allow-escape-sequences repos/.../actions/jobs/<id>/logs`); the log host
  `results-receiver` still times out.
  - 21:00 on 10-15: "EVENING sent without the database: 1000 tgju candles to 2026-10-14, chart yes",
    the photo delivered (the owner confirmed it).
  - 00:11: "DIRECTION: computed live from tgju (OK)", sent.
  - 06:00 on 10-16: no message went out, so the recap is parked as decided.
  - The spool grows about 14-15 writes a run (30 held at 21:00, 50 at 06:00, 79 at 08:00). The
    room's inputs are held once a day. The news breaker skipped 156 items after three failed saves.
- **Platforms.** 10 of 11 valid at 08:00. Daric is refused by the runner (403), and its phone route
  needs Neon. **The stale-quote check is skipped every run** ("Platform history unavailable"):
  without Neon's history the repeat and jump rules cannot run, and they fail open. Frozen copies
  (Taline, HoorGold, section 31) can therefore reach UPDATE and the spool. The spool will write
  those readings back on 11-01 unchecked unless they are re-checked first. That is open, for the
  audit.
- **The push cannot fire.** At 08:00 the discount was 2.93% (basis), 2.74% without the cheapest
  platform, and the stored premium -3.12%; the push said `NO_DATA`. The last level computed before
  the suspension (20:00 on 10-13) was `fire_at` 3.1704614467926606 and `rearm_at`
  2.2590539162434133. No push has been missed: 2.93 is below 3.17. The market is 0.24 points from
  the level, though, and a deepening before 11-01 would go unannounced. Proposed to the owner: hold
  that level, dated 10-13, for the push until Neon returns.
- **The labels.** The AI model labelled 108 of 357 days (2025-10-15 to 2026-02-08) in the job's
  5h20m budget, about 3 minutes a day against 30 seconds expected. Groq's free tier evidently caps
  the day as well as the minute. The days span 2,471 tokens at the median; none failed to parse.
  The rest resumes in later runs (the labeller skips labelled days).
- **The Iran node** (step 8, read on the phone at 09:10 Tehran on 10-16): `wc -l ~/iran_node_spool.jsonl`
  gave 1,010. That fits continuous collection since the suspension: about 60 hours, 240 readings of 4
  platform rows, about 960, plus TSETMC's fund days at 19 a trading day. At about 400 rows a day the
  spool holds about 7,500 by 11-01, under its 30,000 limit.
- **Verdict.** Production does what it can without Neon: hourly runs green, the evening chart and
  /Direction working without it, the record held. **Open:**
  1. the push is blind while Neon is down;
  2. the held readings bypass the stale-quote rules;
  3. Daric is absent;
  4. 249 days remain unlabelled.

## 36. The audit: what the system knows, what it only says, and what it costs (2026-10-16)

**The owner's brief.**

> "we need to rethink, review critically, with no pride or prejudice or attachment to what have been
> built. the project has evolved. ... the core goal of the project is to give information, and act as
> Decision Support System and provide Expert System Judgements based on data, information and fact.
> ... pay close attention to the project core principles of development written in the skills folder."

The owner also listed specific items:

- the saffron fund and the member's evidence;
- 18 of 35 gold funds;
- every "followed by" figure re-checked by episodes;
- `rss.py` and the duplicated tests;
- `high_impact_count`;
- `SignalState`'s clock and `utcnow()`;
- stale and repeated docs.

**Parked first.** The owner: "lets park the discount now, it may mislead the user". The deep-discount
push stays blind until Neon returns. The 10-13 level (`fire_at` 3.17) is recorded in 35.12, not used.

**The test applied to every part.**

- Which decision does it support?
- Is what it tells the reader measured, and by independent cases rather than overlapping days?
- What does it cost (run time, Neon transfer, code to maintain)?

Built-ness, test counts and past effort count for nothing here.

### 36.1 What has measured value

| Part | The decision | The evidence | Caveat |
|---|---|---|---|
| **The room, 7 members** (without money flow) | gold or fixed income | Beat holding by +4.0% to +5.7% median over two-year windows (18 Afran windows, Daric's cost), ahead in 83-100% of them, worst -3.3%; at Goldika's cost +1.3% to +3.1%. `rd_room_simpler.py`, below. | 18 overlapping windows are about three independent periods. |
| **Buy now, don't wait for a dip** (Direction) | when to buy | Waiting for a 3% dip cost more in 12 of 13 years (section 1; the panel's `convert`). | The one robust timing fact on record. |
| **The live platform prices** (UPDATE) | where to buy | Today's spread is 1.9% between the cheapest and the most expensive platform (10-15). That is money a buyer saves for certain. | The price sides are mixed: see 36.3. |
| **The 50-day breaks** (Direction WATCH) | when the trend turns | Counted by separate breaks, a weaker month by 1 to 6 points (section 35.11). | 5 to 35 breaks a cell. |
| **Gold demand** (Direction) | context | Descriptive. It catches May 2026's heavy buying and December 2025's heavy selling (35.11). | No forecast, by design. |
| **The deep-discount zone** (the push) | when, within days | After the first deep reading of each episode, the platforms rose +1.16% in 24 hours against +0.53% for all readings (11 episodes, 08-04 to 10-04, `research/data/hourly.json`). Bought the same day, the deep zone saved only +0.05% (median). | Suggestive, not established. Re-measure on the full record after 11-01. |

**The room's members, tested** (`research/rd_room_simpler.py`, section 33's paired test, production as
the base; the production weights: brake 2.0, fair gap 1.5, real dollar 1.5, market state 1.5, dollar
20d 1.0, chartist 1.0, world gold 60d 0.5, money flow 0.5):

| Room | Gain over holding, median (Afran, 0.30%) | Paired against production |
|---|---|---|
| production, 8 | +5.0% to +9.0% | — |
| 7, no money flow | +4.0% to +5.7% | -0.83 pp (index windows -1.42) |
| 5, no money flow, chartist or dollar 20d | +0.3% to +1.4% | -3.57 pp |

- The chartist and the dollar's 20 days carry the room. Section 22's leave-one-out ("they add
  nothing") was measured on an earlier committee that acted daily, and it does not hold for the room
  as it runs.

### 36.2 What has no measured value

1. **The decision engine, the sole BUY/SELL authority.**
   - Its scorecard: a 55.2% hit rate against a 55.2% always-WAIT baseline, an edge of 0.0
     (`SP_C_HANDOFF.md` section 15, its open finding 2).
   - Four BUYs ever, all of which the confirmation check would now hold.
   - `analysis/decision_scorecard.py` is not reached from `main`: production records outcomes and never
     scores them. ANALYZE prints only their count.
2. **The money-flow member** (`research/rd_flow_saffron.py`). Its 19 funds include saffron. Rebuilt on
   the 18 gold funds, it votes differently on 42 of 1,306 days (3.2%), and its gain falls from +0.67
   to +1.42 points to +0.00, +0.00, +0.31 and +0.22, with fewer than half the windows improved. The
   measured edge came from a handful of saffron-tilted days. Section 33's figures reproduce exactly on
   19 funds, so the harness is right.
3. **The Analysis Wing's chain.**
   - What it covers: the snapshot builder, regime, structure, the evidence package, market
     intelligence, features, the read model, C.14A candles and the C.14B forecast engine, about 5,000
     lines.
   - Who reads it: nothing a reader sees and nothing the decision uses.
   - What it costs:
     - In a normal run (10-12 12:00) it took 4m46s of `main.py`'s 5m50s (82%): the outcome backfill,
       then "Forecast 1h/6h/24h: OK / UP", then the snapshot.
     - Its snapshot JSON spent Neon's transfer and suspended production (section 34).
   - A further 23 modules (2,204 lines, 1,663 of them in `intelligence/`) are reached from nowhere.
4. **The news, so far** (`research/rd_news_labels.py`, 108 of 357 days labelled by the model,
   2025-10-15 to 2026-02-08, the rest running):
   - the model's own call on the dollar shows no skill: its "down" days were followed by larger 3-day
     rises than its "up" days;
   - **the central-bank hypothesis is contradicted so far.** On the 9 intervention days the dollar
     rose +1.81% over 3 days against +0.65%, and fell after 2 of 9: interventions met pressure, they
     did not reverse it;
   - **escalation separates**: +1.20% the next day against +0.25%, falling after 18% (22 days).
5. **Forecast ranges.** The owner dropped Direction's range on 10-15 ("what kind of decision can be
   made from this"). The room's 21:00 report still prints one: "Next 20 trading days: most likely X to
   Y" (`alerts/telegram_paper.py:135`).
6. **ANALYZE's "when the discount was at this level"** counts hourly readings ("increased N times,
   decreased M times in the 24 hours after"). Neighbouring readings share most of the same 24 hours, so
   the counts overstate the evidence: the day-count inflation of 35.10. `SP_C_HANDOFF.md` section 31
   found it needs about 171 independent days against 42 available, and the 09-21 lean reversed within two
   days (its 33.6). Its deep-zone durations, by contrast, are episodes with censoring handled.

### 36.3 Defects

| Where | What |
|---|---|
| Price sides | Only Daric, Goldika and Ayyareh record both the buy and the sell price. The other 8 report one price whose side is not recorded (WallGold asks `side=buy`, Milli gives `price18`, and so on). The discount and "the cheapest platform" therefore compare mixed sides; SP-C found it ("part of the persistent discount is dealer spread") and it is still open. |
| The spool, 11-01 | Readings held during the outage skipped the repeat and jump rules ("Platform history unavailable"), so the write-back would store frozen copies unchecked. Time-bound. |
| `collector/news/rss.py:19` | A broken leftover copy of `collect_rss_feed` (`...` placeholders, "# rest unchanged", an undefined `headers`), overridden at line 228. |
| `tests/` and `src/tests/` | Five test files exist in both, diverged; `tests/test_news_collector.py` lists four tests twice. |
| `analysis/evidence_package.py:206` | `high_impact_count` reads `relevance` for values only `impact` holds: always 0 (`SP_C_HANDOFF.md` 33.3). |
| `caluclator/signal_state.py:56` | `SignalState.timestamp` defaults to `datetime.now`, the runner's clock. |
| `src/` | 92 `datetime.utcnow()` calls, deprecated by Python 3.12. |
| `.github/workflows/test-task-c.yml` | Runs two unit tests by hand; the KPI suite already covers them. |
| The money-flow member | Weighted 0.5 on evidence that does not survive the saffron fix (36.2). |
| Gold funds | Both the money-flow member and GOLD DEMAND read 18 of tablokhani's 35 gold funds, about 80% of their trading value (35.7). |

### 36.4 The docs

- **The authority docs describe September's project.**
  - `PROJECT_MEMORY.md` (2,368 lines, the highest authority) is the SP-A to SP-C history: indicator
    definitions, the C.14 research, the SP-C changelog. Its current state is 40 lines at the end.
  - `MASTER_PLAN_STATUS.md` is about C.14A/B/C and UPDATE v1.
  - `README.md` walks the PRE-SP-C phases.
  - Direction, PAPER and the room, the phone, the spool and the fallbacks are barely in any of them.
- **Five documents each define the authority order, and they differ:** `CLAUDE.md`,
  `skills/README.md`, `Prompt_Guide.md`, `PROJECT_ORCHESTRATION.md` (with a "KIMI handoff template" and
  the C.14 boundaries; last changed 09-13) and `DOCUMENTATION_INDEX.md` (titled "SP-B").
- **Not touched since August or September:** `C14_HANDOFF.md`, `C14C_HANDOFF.md`,
  `C14C_IMPLEMENTATION.md`, `UPDATE_V1_IMPLEMENTATION.md`, `Prompt_Guide.md` and
  `PROJECT_ORCHESTRATION.md`.
- **`skills/`** (last changed 09-12 and 09-29) is sound on principle and stale on fact:
  - `telegram-product.md` plans /Technical, /History, /News, /Radar and /Health, none built, and does
    not know /Direction, PAPER or the evening chart;
  - `market-analyst.md` does not know the room;
  - `data-and-neon.md` does not know the transfer cap, the spool or the node.
  - The principles hold, and this audit applies them: no fabrication, "expose sample size", "do not
    manufacture confidence from a small sample", "INSUFFICIENT DATA is valid", "remove dead code made
    obsolete".

### 36.5 Infrastructure

- **Neon** is the single point. The spool, the evening fallback and live Direction now carry an
  outage, but the phone's data (Daric, TSETMC) reaches the system only through Neon.
- **Groq's free tier** caps the day as well as the minute: about 108 labelled days per 5-hour run.
- **GitHub's log host** does not answer the workstation; the job-log API does (35.12).

### 36.6 Options, for the owner's decision

The reader's decisions, and what the record supports today:

| Question | What the system can say with evidence |
|---|---|
| **where** to buy | the live platform prices, once both sides are recorded |
| **when** | buy now rather than wait for a dip; the deep zone as a hint not yet proven |
| **how much** | gold or fixed income: the 7-member room |
| **what risk** | the trend and its 50-day breaks, gold demand, and escalation news |

Everything else either says what it cannot show, or costs without being read.

**A. Fix and tidy, keep the shape** (about 1-2 days).
- What it does:
  - the defects of 36.3;
  - the money-flow member to weight 0;
  - the room report's range line out;
  - the docs consolidated (36.4).
- What it keeps:
  - the Analysis Wing, with 82% of each run's time and the transfer risk;
  - the decision engine and ANALYZE as they are.
- Least change, least gain.

**B. Refocus on what is measured** (recommended; about 4-6 days in stages, each previewed and merged
on its own).
1. **Now, before 11-01:**
   - the spool's re-check against the stale-quote rules before it writes;
   - money flow out of the room, back to the 7 members that are the honest baseline;
   - the room report's range line out;
   - the small defects: `rss.py`, the duplicated tests, `SignalState`'s clock, `test-task-c.yml`.
2. **Retire the unconsumed Analysis Wing.**
   - What goes: the snapshot builder's chain, the forecast engine, the evidence, interpretation,
     features and read model, the 23 unreachable modules, and their KPIs.
   - What stays: the raw observations, market states and news events.
   - Effect: runs fall from about 6 minutes to about 1, and Neon's transfer moves far from its cap.
3. **The decision engine.**
   - Wire the scorecard (it exists, unrun) into ANALYZE as the system's own record.
   - Hold the BUY push until that record shows an edge over always-WAIT; the engine keeps computing
     and storing as now.
   - This changes the alert rule in `CLAUDE.md`, so it is the owner's decision. The alternative is to
     retire BUY/SELL alerts and keep the deep-discount push.
4. **Price sides.** Record both prices for every platform that publishes them, show "where to buy" by
   the buy price, and re-measure the discount on one side.
5. **ANALYZE.** Rebuild its level section on episodes, or retire the message and move its one
   decision-useful item (the deep-discount level and how long the zone lasts) next to UPDATE's
   discount. UPDATE is a locked layout, so that is a preview first.
6. **The docs.**
   - `PROJECT_MEMORY.md` rewritten as the system that runs (about 400 lines), its history moved to an
     archive file.
   - One authority order, in `CLAUDE.md`. `Prompt_Guide.md`, `PROJECT_ORCHESTRATION.md`, the C.14 and
     UPDATE v1 files archived, `DOCUMENTATION_INDEX.md` brought up to date.
   - `skills/` updated to SP-D.
7. **News.** Finish the labels within Groq's daily cap, measure them all, and add DOLLAR FROM NEWS
   only for labels that separate (escalation so far), with their counts.

**C. Rebuild as one advisor** (about 2 weeks).
- One daily brief answering where, when, how much and what risk, each line with its evidence; UPDATE
  on demand; alerts only where an edge is measured; PAPER and the research behind it.
- It uses the same parts as B and adds a redesign of the messages, so more previews. B leads into C
  without waste.

**Recommended: B, staged:**
1. B1 (part of it is time-bound);
2. B2 and B6 (the largest clean-up);
3. B4 (the data);
4. B3 and B5 when the owner has decided them;
5. B7 as the labels come in.

**36.7 B4 scoped** (10-16, probed from the workstation, Iranian sites direct): every platform but Milli
publishes, or can give, both sides.
- WallGold's API takes `side=sell` as well as `side=buy`.
- Goldika and Daric are already collected two-sided.
- Ayyareh gives `goldPrice` with `buyWageValue` and `sellWageValue`.
- The six HTML sites (Invi, MioGold, Parasteh, HoorGold, Taline, Eligold) show both "خرید" and "فروش"
  and need a parser each.
- Milli gives one `price18`.

About a day of collector work.

## 37. SP-De after the audit: the owner's decisions, and the first stage of B (2026-10-16)

**The owner's decisions on section 36.**

- **Options:** "lets say B, and then bringing in a total advisor as C."
- **Money flow:** "no, the money flow is precious, taking it is pricy, we should rethink the strategy
  to use that data". The owner points to the GOLD DEMAND wording of 35.10 (buyers 1.4 times the
  usual, within the normal range) and to its value "in the times of turbulence". The member stays at
  0.5. Its use is to be rethought around turbulence; section 36.2's finding stands as evidence, not as
  a removal.
- **The Analysis Wing:** "was built for the discount analysis. so retiring isnt good, but maybe
  revamping and rethinking would be a better call ... we spent loads of time for the analysis wing, if
  we arent gaining, mean we didnt design it well, i was low experienced back then, maybe rethinking is
  much better now." /Analyze answered "not enough history" while Neon was down. The owner asked: park
  it now like the recap, "or what do you say?"
- **The decision engine:** "agreed ... the problem is that the logic behind is messy and not standard.
  maybe restructuring now with loads of info could be better."
- **Price sides:** "collecting both sides is better unless if factually disagree."
- **The spool re-check:** agreed.
- **New, for the chart:**
  - patterns: the flag, the double top ("double ceiling") and others, with learning.emofid.com as a
    reference;
  - channels: "gold started a side channel, then hit the ema and rose up ... the system should be
    able to identify such moves technically";
  - "so even the room could be revised as well."
- **The go:** "GO FULL POWER."
- **The range line:** the owner asked what it is. It is the room report's "Next 20 trading days: most
  likely X to Y" (21:00 PAPER). It is shown to the owner before anything changes.

**37.1 The spool's re-check** (time-bound: the write-back runs on 11-01).

- **The problem.** Readings held during the outage skipped the repeat and jump rules, because those
  read the stored history (35.12).
- **The fix.** `main._recheck_held` runs in `_flush_spool` before anything is written.
  - It judges each held reading with `validation.data.defer_stale_quotes`, the production rule itself,
    in time order, against the stored history (one read: 60 days before the first held reading) and
    the held readings before it.
  - A deferred quote leaves the reading together with its price observations. The reading's premium
    (single cheapest) and its state's platform fields and structure (`caluclator.structure.evaluate_structure`)
    are recomputed from the quotes that remain.
  - A reading left with fewer than `MIN_WORKING_SOURCES` is dropped with its run's observations, as its
    run would have skipped it.
  - If the history cannot be read, nothing is written.
- **Tests:**
  - `kpi_coherence.test_41`: a frozen copy repeated from days earlier, 4% below the moved market, is
    deferred in both held readings; the premium and the state follow; its observations leave;
  - `test_42`: a reading left with too few platforms is dropped;
  - `test_40` pins the re-check before `spool.flush`.

**37.2 The Analysis Wing: parked in part, and /Analyze honest.** My call, as the owner asked for it:
park what nothing reads, keep what the redesign and the decision engine's scorecard need, and bring
parts back as they are redesigned rather than all on 11-01.

- **The switches.** `config.json` `analysis_wing` sets `interpretation`, `candles` and `forecasts` to
  false, with the reason recorded beside them, as with the recap.
  - `interpretation` covers the evidence package, intelligence, features and read model; `candles` is
    C.14A; `forecasts` is C.14B.
  - `snapshot_builder.build_analysis_snapshot` honours them; absent, everything runs as before.
- **What keeps running:** the snapshot's core (prices, premium, valuation, momentum, structure,
  regime) and the outcome evaluations with their backfill.
- **The effect** from 11-01: no JSON columns written or read back for the forecasts, and the run's
  longest stages gone except the outcome backfill.
- **/Analyze.** When the database does not answer, `main._send_analyze_report` sends
  `telegram_analyze.build_unavailable_message()`: "The record is in the database, which is out of
  reach right now. ANALYZE answers again when it is back. UPDATE and DIRECTION work meanwhile, from
  live prices." It no longer says "not enough history".
- **Tests:** `kpi_coherence.test_43` (the switches and their defaults; the outcome evaluations never
  parked) and `test_44` (the message).

**37.3 Defects fixed.**

- `collector/news/rss.py`: the broken leftover copy of `collect_rss_feed`, the stray `...` and the
  duplicated typing import are removed.
- `tests/test_news_collector.py`: its runner listed four tests twice (21 runs, now 17, all pass).
- **The machine clock.** `SignalState.timestamp` and `HistoricalQuery.query_time` defaulted to
  `datetime.now`, the runner's local time. They are now `datetime.utcnow`.
  - `kpi_coherence.test_19` looked only for the literal `datetime.now()` and missed both.
  - It now catches any read of the machine clock, except `datetime.now(timezone.utc)`.
  - The pattern was checked on samples after a shell heredoc had first turned its `\b` into a
    backspace and let it pass vacuously.
- **Found, left for the clean-up batch** (B6). The two unit-test folders run nowhere in CI and have
  rotted:
  - `src/tests/` passes only with `PYTHONPATH=src`;
  - `tests/test_event_classifier.py` has a SyntaxError;
  - `tests/test_signal_state.py` imports a function that no longer exists;
  - `src/tests/test_trends.py`, `test_event_classifier.py` (2 of 14) and `test_signal_state.py` (1 of
    26) fail, as does `tests/test_pre_sp_c3.py`.
- **The decision engine's BUY hold** (agreed) is built with its scorecard in B3. With Neon down the
  confirmation already holds every candidate (it fails closed).

`kpi_coherence` 39/39; suite 30/30.

**37.4 Chart patterns and channels: a reader that sees them, and their record on 18K** (the owner's request
of 37; research, a preview, nothing wired).

**Why the chartist missed the move.** `caluclator/chartist.py` confirms a swing at 3 x ATR(14), at
least 3% of the price; on 18K's ~2% ATR that is about 6%. It found no swing after the 15.65M low of
06-16, so through a +68% rally its box stayed June's 15.65-20.34M. The September range, its test of the
20-day and the breakout went unseen. On the record that sequence was:

- **Sideways:** 23.0-24.6M from 09-09 to 09-27 (18 Shahrivar to 5 Mehr), after the August rally.
- **The EMA test:** on 09-23 the low (23.46M) came within 1% of the 20-day (23.24M) and the close held
  above it.
- **The breakout:** a close at 24.40M on 09-28, then 26.84M.
- **The same shape again:** 25.57-26.84M from 10-07, with the 20-day tested on 10-13 (low 25.57M
  against 25.42M).

**The reader** (`research/rd_patterns.py`, rules fixed in its docstring before the measurement).

- **Swings:** a ZigZag at 3% on closes.
- **Ranges:** 8+ days within 6% after an 8% move; breakouts and breakdowns at 0.5% beyond the edge,
  with the range's height as the target.
- **EMA20 tests:** in an uptrend, a low within 1% of the 20-day and a close above it.
- **The flag:** a pole of 8% in 15 days, then a range of at most half the pole; the pole's height is
  the target.
- **On the swings:** double and triple tops and bottoms; head and shoulders and its inverse;
  symmetrical, ascending and descending triangles; rising and falling wedges. These are the classic
  patterns of learning.emofid.com, each confirmed on the close through its neckline or line, with
  Emofid's measured targets.

It finds the owner's sequence:

- the ranges of 09-03 to 09-28 (23.06-24.40M) and of 09-29 onwards (25.27-26.74M);
- EMA20 tests on 09-23 and 10-13;
- a flag breakout on 09-29 (level 24.40M, target 28.88M, invalidated under 23.06M).

**The record since 2014.** Each pattern is counted once (an episode). Its target is reached before its
stop within 40 trading days, against a control: the same two distances tried from every fifth day of
the same era (`research/rd_patterns_control.py`). 18K rose about 40-fold, so an upside target is often
reached from any day.

| Pattern | 2014-2020 | 2021-2026 |
|---|---|---|
| **flag** | **86% against 35% (7)** | **67% against 51% (12)** |
| range breakout | 78% against 66% (18) | 76% against 73% (21) |
| double bottom | 82% against 61% (11) | 77% against 76% (13) |
| EMA20 test, 20 days later (no target) | +1.85% against +1.43% on all days (95) | +4.66% against +3.62% (72) |
| double top (downside) | 50% against 34% (4) | **12% against 33% (8)** |
| rising wedge (downside) | 0% against 4% (16) | 8% against 10% (25) |
| range breakdown | 67% against 38% (6) | 50% against 46% (16) |
| head and shoulders, triangles | 1-13 cases each, mixed | |

Reading it:

- **The flag is the one pattern ahead of its control in both eras.** Breakouts and double bottoms
  "work" about as often as any day would in this uptrend.
- **The bearish patterns did not follow through on 18K.** Since 2021 it was higher 20 days after 7 of
  8 double tops.
- So the reader can find and draw every pattern on Emofid's list. What it says about each must be
  what the pattern did on 18K, not what the textbook promises.

**The preview.** `research/preview_patterns.py` draws on the 21:00 chart through the renderer's new
optional `patterns` overlay (`alerts/chart.py`: boxes, markers, dotted targets; inert unless passed):

- the last two ranges as boxes;
- the EMA20 tests and flag breakouts as markers;
- the live flag's target as a dotted line.

With the reading:

```
Sideways since 7 Mehr between 25.27M and 26.74M; tested the 20-day on 21 Mehr and held
Flag breakout of 7 Mehr: its measured target is 28.88M while 18K stays above 23.06M
A close above 26.74M breaks out of the range; under 25.27M breaks down.
```

Awaiting the owner. Once locked, the reader moves into `caluclator/` beside the chartist (calculators
calculate), and the evening and 21:00 charts and Direction carry it, each pattern with its 18K record.

**37.5 The patterns wired: both worlds on one chart; the buyers' line in the room report** (10-16).

**The owner.**
- On the chart: "the pattern chart is ok, but i like the last one better, especially, we spent loads of
  time and energy to give a life to resistance and support lines ... maybe having good of both worlds
  works much better."
- On the room report: "you can drop the line, but instead we can bring in the buyers power line we
  talked before."
- On the order of B: "agreed on 3, move on full horse power."

**The reader** (`caluclator/patterns.py`, beside the chartist). The rules are research/rd_patterns.py's,
unchanged, so their record applies:
- `zigzag` (3%), `ranges`, `range_breaks` (flag, breakout, breakdown), `ema_tests` and
  `swing_patterns`;
- `read(dates, high, low, close)` returns:
  - the last two ranges, the last one marked running while the price is still in it;
  - the last 60 days' events;
  - the live flag (target not reached, stop not broken);
  - the EMA20 tests inside the current range.
- `RECORD` holds each pattern's 18K figures from 37.4 and `POINTS` where the textbooks expect it to go.
- `name()` drops the direction words ("rising wedge", not "rising wedge (down)"): on the chart they
  read as a forecast the record does not support.

**The chart** (`main._chart_png`: the 21:00 PAPER chart and the evening fallback alike). It keeps
everything it drew: EMA20 and EMA50, the swing supports and resistances, the trend lines with their
projections, the Fibonacci levels, the trades and the live price. It adds `_pattern_overlay`:
- the two ranges as shaded boxes, labelled with their Persian dates;
- the events since the first of them as markers, named plainly;
- the live flag's target as a dotted line.

**The evening caption** (`telegram_paper.pattern_lines`) adds, after its EMA line:
- the current range and its EMA20 test;
- the live flag with its target, its stop and "14 of 19 flags since 2014 got there first";
- any pattern of the last 14 days with its record and the books' direction. On 10-16: "Rising wedge of
  21 Mehr, in the books a sign of a fall: on 18K 2 of 41 since 2014 reached their target first (about 8
  in 100 from any day)".

The caption is 559 characters, against Telegram's 1,024.

**The room report.** "Next 20 trading days: most likely X to Y" is dropped. In its place is
`telegram_paper.demand_line`, Direction's GOLD DEMAND in one line: "Gold funds, 7 days: 86,414 buyers a
day, 1.7 times the usual (a rush)", plus "money heavily in / out" when that reading is unusual. It is left
out when its last day is more than 7 days old; `main._gold_demand(session)` feeds it. The room still
computes `band20` and stores it with its view; nothing prints it.

**Tests** (`kpi_paper` 47/47, suite 30/30):
- `test_39`: a 20% pole, a range, and a breakout out of the 6% band read as a flag with the pole's
  height as target and the range's low as stop; an EMA20 test at a planted dip, and only there;
- `test_40`: plain names; every record has its direction;
- `test_41`: the chart receives the boxes, the flag's target and still the trend lines; the evening
  caption carries the flag with its record;
- `test_42`: the room report has the buyers' line, not the range, and leaves a stale reading out;
- `test_25` updated: no range line.

Learned from the fixtures and kept: a range grows while every close stays within 6% of the others, so a
breakout is recognized once the price leaves that band. That is how the September breakout read (24.40M
to 25.27M, 9.6% off the range's low).

**37.6 Money flow in turbulent times** (`research/rd_flow_turbulence.py`, its rules committed before the run).
The owner: the money flow is "precious", and the buying and selling power "sits very well in the times of
turbulence".

- **The design.**
  - 18 gold funds, saffron out; the readings of `gold_demand` over 7 days, ranked against the trailing year.
  - A turbulent day: 18K's 20-day volatility in the top 20% of its year, or 18K 10% or more under its
    year's high close. That covers 56-65% of days, which is too broad to be a sharp regime.
  - Outcomes are counted from the first day of each episode, against all turbulent days, in 2019-2022
    and 2023-2026.
- **What agrees in both eras.**

  | In turbulence | 2019-2022 | 2023-2026 |
  |---|---|---|
  | a rush of buyers (people HIGH) | another 5% fall within 20 days after 50% (6 episodes) | 43% (14); the turbulent base is 24% in both eras |
  | few buyers (people LOW) | another 5% fall after 0% (11) | 6% (32) |
  | big buyers (size HIGH) | +17.4% over 60 days (8) | +24.2% (11); the base is +5.3% and +7.4% |
  | heavy net money in (money HIGH) | +0.5% over 20 days (8) | -0.7% (7); the base is +1.6% and +2.7% |

  Heavy money out and sellers bigger are mixed.
- **The owner's case fits.** Heavy money came in on 05-13 to 05-20, 2026, while 18K fell, before turbulence
  was flagged. 18K fell another 7-15% over the next 20 days, then made its low on 06-16, when sellers
  were bigger.
- **The caveat.** Twelve combinations were tested per era, and four agree in both, partly by chance
  perhaps. They are leads to be confirmed forward, not edges.
- **Where they can go.**
  - Into GOLD DEMAND, as context with their counts when the market is turbulent. For example: "a rush
    of buyers in a turbulent market: another 5% fall followed within a month in 9 of 20 such rushes,
    about twice the usual".
  - Or into a money-flow member that votes only in turbulence. Designed on 2019-2022 and judged on
    2023-2026, so the room's test stays honest.

  The member stays at 0.5 meanwhile (the owner, 37).

## 38. Proposal: one advisor, built on measured evidence (2026-10-16, for the owner's decision)

The owner's decisions of 37 run together. One question decides all of them, so they are proposed together:
- the decision engine restructured ("the logic behind is messy and not standard");
- the Analysis Wing rethought ("built for the discount analysis ... we didn't design it well");
- the advisor (C).

The question: **what does a buyer of 18K need to decide, and what can the record answer?**

**38.1 The four questions, and the method that answers them.** A standard method fits this project better
than either of today's two:

- **Today's decision engine** is a fixed matrix of categorical states with hand-set transitions. It has no
  measured edge (55.2% against always-WAIT), and it cannot say why in numbers.
- **The C.14B forecaster** is a classifier whose output no one read, and whose skill was never shown.

The proposed method is the **decision table of an evidence-based expert system**:

- For each choice a reader actually faces, the record's outcome of each action on past days in the
  same state is shown, counted by episodes, with its sample size.
- A short rule base turns the table into a verdict. Every rule is written down with the evidence that
  admitted it, and every verdict prints the rules that fired.

This is what BUY NOW OR WAIT already does (waiting for a 3% dip came 27 in 100 and cost more in 12 of
13 years). The proposal makes it the whole engine.

| Question | Actions compared | Evidence it rests on (measured, or to measure) |
|---|---|---|
| **Where** to buy | each platform, at its buyer's price | the live prices, both sides (B4); the fees; the platform's own staleness record |
| **When** | now / wait for a dip / wait for the discount to deepen | waiting for a dip cost more in 12 of 13 years (robust); the deep-discount zone's head start (+0.6 pp in 24 hours, 11 episodes: to confirm on the full record); the platforms' lag behind a dollar move (to measure) |
| **How much** | all gold / part in fixed income | the room (+4.0% to +5.7% against holding over two-year windows; about three independent periods) |
| **What risk** | what would change the answer | the 50-day breaks (a weaker month by 1 to 6 points), the range edges and the flag's stop (37.4), turbulence with a rush of buyers (another 5% fall twice as often, 37.6), escalation news (+1.2% the next day, 37 and 36.2) |

**38.2 The decision engine, restructured.** The categorical chain (valuation, premium direction,
momentum, structure, conflict, candidate, confirmation, hysteresis) is replaced, as the alert authority,
by the WHEN rule base.

- **"Buy now"** is the default verdict, because the record says waiting costs.
- **"Wait a few hours"** applies only where a measured edge exists, for example the platforms lagging a
  dollar jump, if B confirms it.
- **"Heavily discounted now"** remains the push.
- **SELL** has no measured basis at all and is retired until one exists.

The confirmation checks keep their place: a verdict that rests on one platform, a stale dollar or a dead
world gold is held. The old chain keeps computing beside it until the new engine's scorecard (wired in B3)
has its first quarter. The two are then compared on the record, and the owner decides. This changes
`CLAUDE.md`'s alert rule (`final_decision` is the sole BUY/SELL authority), which is why it is the owner's
decision and not done here.

**38.3 The Analysis Wing, rebuilt as the discount laboratory.** Its purpose stays: the discount. Its
output becomes facts the advisor uses, stored small (no JSON columns):

1. **The lag:** after the dollar or world gold moves, how many hours the platforms take to follow, and
   how much of the move they make up. This is the "when" edge the discount was always about, measured
   by episode on the hourly record.
2. **The deep zone:** episodes, durations (as ANALYZE does now, with censoring) and what follows them.
   Head start or nothing, decided on the full record after 11-01.
3. **The spread:** each platform's buy-sell spread, once both sides are collected. A round trip's true
   cost, and whether "the cheapest" is cheapest to a buyer.
4. **Its own scorecard:** each WHEN verdict scored against the price 1, 3 and 20 days later.
   `decision_scorecard.py` exists but never runs; it would be wired in.

The parked parts (interpretation, C.14A candles, C.14B forecasts) stay parked. What the laboratory needs
it builds anew, on the outcome evaluations kept running.

**38.4 The advisor (C).** One message a morning and on demand, answering the four questions in that
order, each with its evidence in one line. It is Direction v7 grown into the brief that the owner and
§35's critique pointed to, with the patterns, gold demand and news in it. UPDATE stays the live price
check. The push stays for the deep zone, and becomes the WHEN alert once the lag edge is confirmed. The
room keeps its 21:00 report.

**38.5 The order, if the owner agrees.**
1. **B4, both price sides** (about a day): the "where" answer needs it, and so does the spread.
2. **38.3's measurements on the hourly record** (the lag, the head start). They can begin on the
   research copy now (`research/data/hourly.json`, August to October) and be confirmed on the full record
   after 11-01.
3. **38.2's engine, with its scorecard,** beside the old chain.
4. **C's message:** a preview first, as always.

**37.7 Both price sides (B4), and a correction to 36.7** (10-16).

**The correction.** 36.7 said every platform but Milli publishes both sides. That was wrong. On Invi,
MioGold, Parasteh, HoorGold and Eligold, "خرید" and "فروش" belong to the shop's navigation ("buy online",
"best sellers"), not to two prices. WallGold's API answers `side=buy` and `side=sell` with the same number
(26,053,000 on 10-16).

**What each platform's `price` means**, read from the collectors and the pages on 10-16:

| Platform | `price` | Both sides |
|---|---|---|
| Daric | what a buyer pays (`BestSellPrice`) | yes, `BestBuyPrice` the other |
| Goldika | what a buyer pays (`buy`) | yes |
| Ayyareh | its published price; a buyer pays it plus `buyWageValue`, a seller gets it less `sellWageValue` | yes, derived |
| Taline | the page's 18K figure, between its two sides (26,168,500 against buy 26,273,900 and sell 26,064,500, a 0.8% spread) | **yes, from 10-16** |
| Milli, Invi, WallGold | one price, its side not published | no |
| MioGold, Parasteh, HoorGold, Eligold | a jewellery gallery's daily gold price: the reference its jewellery is priced from, not a price raw gold can be bought at | no |

**So the discount and "the cheapest platform" compare four kinds of number:**
- two buyers' prices;
- two between-the-sides prices;
- three of unknown side;
- four gallery references.

This is the mixed-sides finding of SP-C, now itemized. **Changing what `price` means would break the
discount's history** (its ranks, the deep-discount level, the valuation leg), so it is left as it is. Both
sides are recorded beside it, for the advisor's "where" answer (38.1) and for a later one-sided discount,
measured before any change.

**Built.**
- `collector/taline.sides()` reads the calculator block ("قیمت خرید طلا: ۲۶,۲۹۴,۷۰۰ قیمت فروش طلا: ...",
  Persian digits, toman). It returns nothing unless both sides are found in order. Taline's `price` is
  unchanged.
- `main._save_price_observations` stores BUY and SELL rows for `TWO_SIDED_OBSERVED` (Goldika, Daric,
  Taline); until now only Goldika's sides were stored.
- Ayyareh stays one SINGLE row. The representative-price chain (Milli, Ayyareh, WallGold) reads each
  source's latest observation without a side, and two rows would move it from the published price to one
  side.
- Nothing a reader sees changes: no message reads `buy` or `sell`, and PAPER's venue chain (Daric,
  Goldika, Ayyareh) already used them.
- Tests: `kpi_coherence.test_45` (who is stored two-sided; no member of the representative chain is) and
  `test_46` (Taline's parser on Persian digits, a reversed pair, nothing). `kpi_coherence` 41/41, suite
  30/30.

**37.8 The unit tests: one folder, run in CI** (B6, first part; 10-16).

**One folder.**
- `src/tests/` is merged into `tests/`. Seven files moved, two (`test_event_classifier`,
  `test_signal_state`) replaced by their `src/tests` versions (the `tests/` copies had a SyntaxError and an
  import of a removed function), and three duplicates removed.
- `test_alert_routing` gained the path bootstrap the others have.

**Brought up to the code's documented behaviour.** The code did not change; these tests assert behaviour
that was changed on purpose:
- `test_event_classifier`:
  - a keyword's gold direction is `UNKNOWN` since 09-21;
  - the classifier returns the item with its labels, so the schema test's item carries a url and a source.
- `test_signal_state`: the cooldown is timed. A repeat BUY an hour after the last is held, after 25 hours
  it passes, and with the last alert's time unknown it fails open.
- `test_trends`: `ma7` is the 7-day average of the fair price, one value a day; the test built premiums on
  one day.
- `test_pre_sp_c3`: the relief case used the panic's own evidence. Relief is stress easing, so its evidence
  now eases.

**The tests' clock.**
- Five files stamped their rows with `datetime.now()` while the repository filters against `utcnow()`.
- `test_price_observations.test_hours_filtering` failed on this machine (UTC+3:30) and would pass on a UTC
  runner: the bug of SP-C.16, in the tests.
- All five use `utcnow()` now.

**Run in CI.**
- `tests/run_all.py`, the companion of `kpi/run_all.py`: each file in its own process, an in-memory
  database, UTF-8, pass on exit 0.
- `kpi-suite.yml` runs it after the KPI suite.
- `test-task-c.yml` is removed: its two files run in that step.

**`kpi_coherence.test_27` could not fail.**
- It matched `get_invi_price(` against `_code()`, whose tokens are joined by newlines, so no call ever
  matched.
- It is read from the syntax tree now: the calls, and the names rebound by assignment (each element of a
  tuple assignment too) or `patch()`.
- Two sample sources check it: an unsubstituted call must be caught, a substituted one must pass.
- On the real files it finds five calls in two files, all substituted. `kpi_sp_c5` rebinds `kitco.SOURCES` and
  `iran.COLLECTORS` by tuple assignment, which the old text patterns could not have recognised either.

Unit tests 18/18 files, `kpi_coherence` 41/41, suite 30/30, compile clean.

**37.9 The documents: one authority order, the system as it runs** (B6, second part; 10-16). The
audit's finding (36.4): the authority documents described September's project, and five of them each
stated an authority order, all different.

**`PROJECT_MEMORY.md` rewritten** (404 lines, from 2,368) as the system that runs:
- purpose and the four questions;
- the surfaces and their state;
- the scheduled run, step by step;
- what the data means (the price sides, the quantities, time, the daily series, news);
- the decisions and their record;
- Neon and the outage;
- what the research established;
- the defects index, re-checked item by item;
- how work is done;
- where things stand.

The old file is `archive/PROJECT_MEMORY_HISTORY.md`, moved with `git mv` and unchanged.

**The defects index, checked against code rather than carried over:**
- **Closed since the SP-C list:**
  - `MAX_WORLD_GOLD` ($20,000 since section 30);
  - `kpi_coherence.test_27` and the stale unit tests (37.8).
- **Restated:** the snapshot's support and resistance are still labelled by extremum type. That is the
  Analysis Wing's own `technical_state`, which no reader sees; readers get Direction's levels, labelled
  by position.
- **Still open:** Afran's late date and Taline's in-band frozen copies.

**One authority order.**
- The order is stated in `PROJECT_MEMORY.md` section 1 and in `CLAUDE.md`. `skills/README.md` and
  `DOCUMENTATION_INDEX.md` point to it.
- The order: `.project_state.json`, then `PROJECT_MEMORY.md`, this handoff, `PROJECT_OPERATIONS.md`,
  `LESSONS_LEARNED.md`, `skills/`, and the code. Executable evidence outranks prose.

**Archived** to `archive/`, unchanged, so every citation in the handoffs still resolves:
- `Prompt_Guide.md`: its rules were already in `skills/core-engineering.md`; the two that were not went
  to `validation-and-release.md`;
- `PROJECT_ORCHESTRATION.md`, last changed 09-13: the production-liveness rule, the KPI engineering
  standard and regression discipline went to `validation-and-release.md` and `PROJECT_MEMORY.md`
  section 10;
- `C14_HANDOFF.md`, `C14C_HANDOFF.md`, `C14C_IMPLEMENTATION.md`: contracts of the parked parts, to be
  read before one is brought back;
- `UPDATE_V1_IMPLEMENTATION.md`;
- `MASTER_PLAN_STATUS.md`. This one was not in the audit's list. Its milestone status ends at C.14C and
  UPDATE v1, and keeping it beside `.project_state.json` and this file's sub-sprint table would be the
  duplicate sprint-status document the governance rules forbid. Restoring it is one `git mv`.

**Rewritten:**
- `DOCUMENTATION_INDEX.md`: who owns what, the archive and what supersedes each file;
- `README.md`: a short orientation (what it sends, how it runs, run and test, the repository map).

**Updated:**
- `CLAUDE.md`: the reading order, the parked part of the Analysis Wing, the tests in the loop;
- `PROJECT_OPERATIONS.md`: its opening, and its C.14 sections marked as parked;
- `LESSONS_LEARNED.md`: lesson 10's "a check that cannot fail" gains test_27, test_19's vacuous
  pattern and the unit tests that ran nowhere.

**`skills/` brought to SP-D.** The principles are unchanged; stale facts and pointers to archived
files are replaced:
- **reading orders:** README, onboarding, bootstrap;
- **the owner's working rules:** core-engineering;
- **the branch model, the safe tag and the standing authorization**, stated as covering the push, not
  the approval: sprint-execution, branch-management;
- **validation-and-release:** the runners, production liveness, a check seen to fail, how a KPI is
  written;
- **data-and-neon:** the tables, the transfer cap, the spool, the phone's role, the price sides;
- **market-analyst:** the engine's zero edge, Direction and the room, "the default is gold", the
  method;
- **telegram-product:** the commands that exist, the five SP-C planned that do not, locked layouts, the
  owner's wording, Telegram's limits;
- **llm-news-intelligence:** Groq's caps, where news comes from, what has been measured.

No code changed. Suite 30/30 (840 assertions across 29 files), unit tests 18/18.

**37.10 A rule broken, and the owner's question: the phone as the database** (10-16).

**The safe tag.** A one-line fix to `CLAUDE.md` (5c60d04, its stale "latest safe tag" line) was pushed
to `main` without a safe tag first. `v1.20safe` was then put on `main` as it stood before the push
(6daa566), so the rollback point exists, but it was made after the merge, not before. The rule has no
exemption for documents. Small fixes now wait on SP-D for the next batch.

**The question.** The owner: "while the neon is down, can we use my phone as db via the termux thing
we have. how much space do we need, check the possibility."

**Space is not the constraint.**
- Neon's free plan caps a project's storage at 0.5 GB, so the database is under that by construction.
  The exact size cannot be read while the project is suspended: Neon's API does not answer this
  workstation's tools.
- PostgreSQL is a Termux package. An S10 has 128 GB or more.

**Reaching the phone is the constraint.**
- GitHub's runner would have to connect into a phone on a home connection in Iran, normally behind
  the ISP's NAT. That needs a tunnel or a forwarded port.
- A free tunnel from Iran is unproven, under the filtering and the sanctions both.
- Every run would then depend on the phone being up, on Wi-Fi and powered.

**It would start empty.**
- Neon's rows cannot be copied out while the project is suspended. Its compute does not start, so
  there is nothing to dump.
- A phone database would hold only the outage's own data, which the spool already keeps.
- So the parts the outage stops would stay stopped:
  - the valuation rank, the deep-discount level and the confirmation need the 30-day pool;
  - PAPER needs its accounts since 10-05.

**It would fork the record.** Two databases written in the same weeks, PAPER's accounts among them,
would have to be merged into Neon on 11-01. The spool already writes back with deduplication and the
stale-quote re-check.

**What would help instead** (for the owner's decision):
- **A mirror of what runs read**, on GitHub's side like the candle cache: the settled 30-day pool, the
  platforms' 14-day history, PAPER's latest account rows, filled from Neon whenever it answers.
  - It is small, under a megabyte.
  - It would let the next outage keep the confirmation, the deep-discount level and PAPER running.
  - It would also cut Neon's transfer, the cause of this outage.
  - Built and measured after 11-01, when there is something to fill it from.
- **The phone's TSETMC readings during an outage**, pushed through GitHub, which the phone reaches.
  - Only GOLD DEMAND would gain before 11-01, since PAPER is stopped.
  - It needs a write token on the phone.

The owner agreed (10-16: "agreed on your proposals, go ahead"). The mirror is 37.12.

**37.11 The news labels at 152 days, and where each news source can be read** (10-16).

**The labelling.**
- The second run on `probe-news-labels` (05:41-11:06 UTC) labelled 44 days, against 108 for the first.
- No request failed. The run waited out Groq's daily cap, which the first run had spent seven hours
  earlier.
- 152 of 357 days are labelled (2025-10-15 to 2026-03-24); 205 remain. A third run started at 11:13.
- At 44 to 108 days a run, the year completes in two to four more runs.
- The repository is public, so the runner's minutes cost nothing.

**Re-measured on 152 days** (`research/rd_news_labels.py`, its rules unchanged):

| Label | 108 days (36.2) | 152 days |
|---|---|---|
| all labelled days | — | dollar +0.15% next day, +0.55% over 3 days |
| central-bank intervention | +1.81% over 3 days (9 days) | +1.70% over 3 days (10 days); fell after 3 of 10 |
| escalation | **+1.20% next day against +0.25% (22 days)** | **+0.02% against +0.29% on days without (59 days)** |
| the model's own "dollar down" | larger rises than its "up" days | +1.20% over 3 days, against +0.44% after "up" |

- **Escalation no longer separates.** 37 of the 44 new days (02-09 to 03-24) are escalation days. By the
  model's own summaries they run from February's tension to the missile strikes of late March. The 108-day result was one window's number (lesson 22). B7's "DOLLAR FROM NEWS
  only for labels that separate" has, for now, no such label.
- **Interventions still meet pressure**; they do not reverse it.
- **The model's own dollar call** still runs the wrong way.
- Corrected in `PROJECT_MEMORY.md` section 8 and `skills/llm-news-intelligence.md`.

**Where each source can be read** (probed 10-16 from the workstation in Iran, direct, and from the
11:00 production run's log):

| Source | GitHub's runner | Iran |
|---|---|---|
| Donya-e-Eqtesad (`/rss`) | **already read**, 30 items a run | 30 items, fresh |
| Tejarat News (`/feed`) | **already read**, 100 items | 100 items |
| Tasnim (`/fa/rss/feed`) | refused (removed 09-21) | **no connection** from the workstation |
| cbi.ir | refused (removed 09-21) | the home page answers "Request Rejected"; `exratesrss.aspx` gives 47 items, the reference rates rather than news |
| Mehr, ISNA, IRNA | not tried | 30 items each, fresh |

- Of the owner's list (cbi.ir, Tasnim, Donya-e-Eqtesad), Donya-e-Eqtesad needs no phone.
- The other two fail from the workstation as well. Whether the phone's home connection reaches them is
  the first thing to test on the phone.

**A gap found.** News is not held while Neon is down. Each run fetches about 160 items and stores none
("3 saves failed in a row; 156 items of this run not stored"). The feeds keep only their latest items,
so the Iranian sites' news from 10-13 to 11-01 will be missing. The Telegram channels can be read back
later; the RSS feeds cannot.

**37.12 The record mirror: what runs read, kept for the next outage** (10-16; the owner: "agreed on your
proposals, go ahead").

**The problem.** With Neon out of reach the spool keeps what runs write, but what they read fails:
- the stale-quote rules run without history;
- the valuation leg abstains (UNKNOWN);
- the confirmation holds every BUY;
- UPDATE loses its rank, its deep-discount level, its bubble trend and its RUN/DAY/7D baselines.

All of those read only `market_snapshots` and their `platform_prices`, at most 60 days back.

**Built** (`src/persistence/mirror.py`):
- **The copy.** A SQLite file, `record_mirror.sqlite`, cached by the workflow beside `state.json`
  (`RECORD_MIRROR_FILE`). It holds the last 61 days of those two tables, in the same models, so every
  reader runs on it unchanged.
- **Filled.** Each scheduled run that reaches Neon calls `main._refresh_mirror` after its writes. It
  copies in full when the copy is missing or a week old, and otherwise only the readings added since.
  A row corrected in place, as section 45's were, reaches the copy within a week.
- **Read.** `main._read_session()` and `mirror.read_session()` give the copy only when Neon does not
  answer (probed once a run) and a copy made from Neon exists. Readers that use it:
  - the valuation rank, the platform history and the confirmation;
  - UPDATE's context, momentum and the input directions;
  - `update/baseline_resolver.resolve_update_baselines`.
- **Read-only.** A write on the copy raises. Every writer keeps `get_session()`, so a write fails as
  unreachable and goes to the spool as before.
- **Held readings.** A reading the spool holds is also added to the copy under a negative id, so the
  next run ranks against it. Only into a copy made from Neon: a copy of the outage alone would rank a
  reading against a few hours. When Neon answers again, the copy is rebuilt from it, where the spool
  has written the reading, and the negative ids go.
- **Not changed in an outage:**
  - the deep-discount push, which the owner parked ("it may mislead the user"; to be decided for the
    next outage);
  - PAPER, which needs its own writes held first;
  - ANALYZE, which is being redesigned (B5);
  - Direction, which already runs live from tgju.

**Its size, measured:**
- 0.88 MB for 61 days at 20 readings a day across 11 platforms (14,640 rows).
- A full copy reads about that from Neon once a week, about 4 MB a month. A run between copies reads
  its own new rows, plus one `SELECT 1` to probe.
- Against the 5 GB cap, that is under 0.1%.

**When it works.** It is first filled on 11-01, at the first scheduled run that reaches Neon. It does
nothing in this outage, because nothing can be copied from a suspended project.

**Tests** (`kpi_coherence`):
- `test_47`: the 61-day window, then only what is new, and the weekly copy that carries an in-place
  correction.
- `test_48`: the copy only when Neon is out of reach. On the copy, the valuation leg ranks a reading
  as on Neon, and the stale-quote rules see the same history. The copy refuses writes.
- `test_49`: a held reading is in the next run's history and goes at the rebuild; nothing is added
  without a copy from Neon.
- `test_50`: only the readers above use it; the push, PAPER, ANALYZE, Direction and the writers do
  not; the workflow caches it.

Each was seen to fail. Six breaks were made in the code, among them:
- the copy never served;
- the incremental copy taking everything;
- the held reading not added;
- no rebuild after an outage.

Each break failed its test. `kpi_coherence` 45/45, suite 30/30, unit tests 18/18.

**NEON MIGRATION REQUIRED = NO.**

**37.13 The owner's answers; the Iranian news sources read by GitHub, and news held in an outage** (10-16).

**The owner's answers to 37.10-37.12:**
- **The deep-discount push during an outage:** "Agreed" to the default. It stays parked, and does not
  run from the record mirror.
- **News during an outage:** "spool".
- **The phone test:**
  - Tasnim's address is `tasnimnews.ir`, not `.com`. The phone read it: curl's "(23) failure writing
    output" only means `head` closed the pipe after its 300 characters.
  - cbi.ir answered the phone with its home page.

**Where each source can be read** (probed 10-16 from the workstation, the phone and GitHub's runner, the
last through the temporary branch `probe-iran-news`, deleted):

| Feed | Runner | Items |
|---|---|---|
| Tasnim economy, `tasnimnews.ir/fa/rss/feeds/7/0/0/0` | 200 | 25, about 7 hours of news |
| Tasnim politics, `/feeds/1/0/0/0` | 200 | 17-18, about 9 hours |
| cbi.ir news, `NewsRss.aspx?ln=fa` | 200 | 10, four days of the bank's announcements |
| cbi.ir rates, `exratesrss.aspx` | 200 | 47, rates rather than news |
| Mehr, ISNA, IRNA | 200 | 30 each |
| `tasnimnews.com` | the name no longer resolves | — |

- **The runner reaches every one.** The two retired on 09-21 failed for other reasons than geoblocking:
  Tasnim's `.com` name is gone, and cbi.ir rejects some user agents. It refused the workstation's mobile
  one and accepts production's.
- **The phone is not needed for news.** No phone code is written.
- Tasnim's all-stories feed covers under an hour, which an hourly run would miss, so its two categories
  are read instead.

**Built:**
- **The sources** (`config.news.sources`): Tasnim economy, Tasnim politics and cbi.ir's news, the
  owner's list of 10-15. Donya-e-Eqtesad and Tejarat News were already read. Mehr, ISNA and IRNA are
  not added ("not to over pollute").
- **cbi.ir's feed parsed to nothing.** It is served as `text/xml` without a charset, so `requests`
  decoded its UTF-8 as ISO-8859-1. The byte-order mark and every Persian word came out as mojibake.
  - `rss.fetch_rss_feed` now decodes the bytes as UTF-8 when no charset is declared, which is XML's own
    default, and drops a byte-order mark.
  - Of the twelve feeds, only cbi.ir's decodes differently: the other three without a charset come out
    the same either way.
  - The first attempt stripped the byte-order mark from the decoded text. It changed nothing, and its
    test passed without it, so it was replaced. The test now serves the real case: text/xml without a
    charset, a byte-order mark, a Persian title.
- **Tasnim's two feeds share a host.** `rss.source_label` gives a numbered feed its number
  (`tasnimnews.ir/feeds/7`, `/feeds/1`), and no existing label changes.
- **News held in an outage** (`persistence/spool.py`, `repository.save_news_event`/`hold_news_event`,
  `collector/news/ingest.py`):
  - A save that finds the database out of reach holds the item and returns 0. The rest of the run is
    held without asking the database again, which replaces the 3-failure breaker for this case. The
    breaker stays for other failures.
  - Each run's dedup keys include the held items' keys, so an item fetched by every run is held once.
  - The write-back stores each item with its own time, in batches of 50, skipping a key already
    stored.
  - **Its share:** news is held only while the spool is under 16 MB (`NEWS_MAX_BYTES`), of its 20 MB. At
    about 1.1 KB an item and roughly 600 new items a day, that is about 0.7 MB a day, against the
    record's 0.1 MB. A 19-day outage then fits, and the record keeps 4 MB, about 40 days.
- **`kpi_sp_c5.test_37`** retired "cbi.ir" by host. Its reason, "connection reset, and it is rate data
  not news", was about the rate feed, so it now retires `cbi.ir/exratesrss.aspx`.

**Tests.**
- `kpi_coherence.test_51`: held, held once, written back once with its own time; an already-stored
  item skipped; news stops at its ceiling while the record still fits.
- `tests/test_news_collector.py`: the charset case, the labels, and the ingestion holding the rest of
  the run without asking the database.
- Seven breaks were made in the code; each failed its test. Suite 30/30, `kpi_coherence` 46/46, unit
  tests 18/18 files (the news file 20/20).

**From the next scheduled run until 11-01**, the news is kept. 10-13 to 10-16 is lost for the RSS
feeds.

**NEON MIGRATION REQUIRED = NO.**

**37.14 A defect of mine: the state cache's file list changed, and two runs started empty** (10-16).

**Found** in the 17:00 run's log: "SPOOL: 15 held writes wait". Three days of outage should have meant
hundreds.

**The cause.**
- `actions/cache` ties each entry to its exact list of paths.
- 37.12 added `record_mirror.sqlite` to the state's list.
- The run of 12:30 UTC therefore found no entry it could read ("Cache not found for input keys") and
  started from an empty `state.json` and spool.
- The entries list shows it: 6,297 bytes at 11:31, then 1,583 at 12:30.
- **The same happened on 10-15 at 08:34**, when the spool's file was added. The entry fell from 3,155
  to 586 bytes and `state.json` restarted, before anything was held.

**What was out of reach:**
- the spool from 10-15 08:34 UTC, when it began (35.4), to 10-16 11:31: 205 held writes, about 27 runs.
  Readings from the outage's start, 10-13 21:00 Tehran, to 10-15 were never held, because the spool did
  not yet exist;
- `state.json`: its history, the quote holds, the cooldown's last alert and the push's state.

It was not lost: the entry of 11:31 still exists under the old list. (The commit messages of 242d40e and
2b21ed2 say "three days"; it was one.)

**Fixed** (242d40e, `v1.23safe` before it, merged at 13:41 UTC ahead of the 14:30 run):
- The state's list is back to its three files, so the next run restores the entry of 11:31.
- The mirror has its own cache step (`gold-monitor-mirror-`).
- A one-off step reads the latest entry under the four-file list, sets its spool aside, and adds it
  once to the restored spool. This is what the 12:30 and 13:30 runs held, the 207 news items among it.
  `state.json` records it as done (`recovered_2026_10_16`). The step is removed after 11-01.
- `kpi_coherence.test_52` fixes the list at its three files. It fails on the four-file list.
- The lesson goes in `LESSONS_LEARNED.md`.

**Verified** on the run of 14:30 UTC (2b21ed2):
- it restored the entry of 11:31 (6,297 bytes);
- it found the four-file entry and added its 236 held writes: two runs' readings and observations, and
  207 news items;
- the spool then held 441 writes ("SPOOL: 441 held writes wait"), with 24 more news items held by that
  run.

**37.15 The SERVICE notice: a push when a service stops or comes back, and Status tells the truth**
(10-16; the owner: "go ahead with the outage notice", on the drafts of 39.7).

**Built:**
- **What is watched** (`analysis/service.py`, pure): four services, seen by every scheduled run right
  after it collects:
  - the database (Neon answers);
  - world gold (a live quote, not the fallback);
  - the dollar (bonbast answered);
  - the platforms (at least three answered, as UPDATE's discount needs).
- **When it is announced:** a change goes out once, after two runs in a row agree. Every service
  starts as working, so an outage already under way is announced by the second run that sees it.
  - **The date** is the first failing run, or the spool's oldest held reading if that is earlier.
  - **The outage under way** began before the spool existed. Its oldest reading is from 23 Mehr, so it
    is dated from the record instead: `main.NEON_SUSPENDED_AT`, 21 Mehr 21:00 (section 34).
  - That date applies only while no run has seen Neon answer (`last_ok`), and only until 11-01.
  - The first version took the spool's date alone. The run of 14:30 would have announced "since 23 Mehr,
    12:04". It was corrected, with its test, before the second run sent anything.
- **The message** (`alerts/telegram_service.py`), in the drafts' words:
  - **database out of reach:** since when; "(its free monthly limit)" when Neon says so; what works;
    what is paused (BUY signals only while there is no record mirror to read); that prices and news are
    kept; and, for the monthly limit, the day it resets;
  - **database back:** after how long, and what was kept and written, or how much is still being
    written;
  - **world gold, dollar, platforms:** down and back, one line each. These five were not among the
    three drafts and are written in the same style, for the owner's review.
- **Status** (`src/worker/telegram-trigger.js`):
  - each scheduled run leaves "::notice title=service::Service: ..." as an annotation of its job;
  - the worker's Status reads it from the latest ANALYZE run and adds it below the run's line, for
    example "Service: the database out of reach since 21 Mehr, 21:00. (the 17:00 run)";
  - **the worker runs on Cloudflare, so the file must be pasted into its dashboard by the owner**;
  - until then, Status is as before and the push already works.
- **Found on the way:** a missing dollar raised in `calculate_fair_price(world, None)` and ended the run
  before anything was stored.
  - It now ends the run cleanly, as a missing world gold does.
  - A user run is told the dollar is unavailable; a scheduled run leaves it to the SERVICE notice.

**Tests:**
- `kpi_coherence.test_53`: announced once after two runs, dated by the spool, the texts, and Status's
  line.
- `kpi_coherence.test_54`: the watch runs before validation and before the fair price; a missing dollar
  ends the run; three runs send one push and save the state; the annotation and the worker's reader are
  wired.
- Six breaks were made in the code, among them a single run announcing, no date from the spool, the
  watch moved or removed, and the dollar check removed. Each failed its test.
- The worker passes `node --check` as a module, a check that was first seen to reject a broken file.
- `kpi_coherence` 49/49, suite 30/30, unit tests 18/18.

**What the reader will see.** With the database still out of reach, the second scheduled run after the
merge sends:
"The database is out of reach since 21 Mehr, 21:00 (its free monthly limit). ... Expected back: 10 Aban."

**NEON MIGRATION REQUIRED = NO.**

**38.6 The first laboratory measurement: the platforms do not catch up a fair jump**
(`research/rd_platform_lag.py`, rules in its docstring; `hourly.json`, 2026-08-04 to 10-04).

- **The sample.** 15 jumps of 1% or more in fair value between consecutive readings (12 up, 3 down),
  counted once per 12 hours.

| After the jump | Share of fair's move the platforms made up | On all readings (the control) |
|---|---|---|
| 1 hour | 37% | 34% |
| 3 hours | 49% | 40% |
| 6 hours | 34% | 59% |
| 24 hours | 63% | 85% |

- **The discount stayed.** It was -2.37% at the jump and -2.46% a day later.
- **What it means.** After a fair jump, nearly all of them dollar moves here, the platforms followed
  *less* than usual, not more. There is no "wait a few hours for the platforms to catch up" edge for the
  WHEN rules (38.2), and nothing to exploit in the other direction either. The jump in fair value is
  partly not followed at all: the platforms may track a dollar other than Bonbast's.
- **To re-measure** on the full hourly record after 11-01, with the dollar's own sources (Tether from
  tgju; the node's TSETMC funds) beside Bonbast.
- **For the advisor:** WHEN starts from "buy now" (waiting for a dip cost more in 12 of 13 years). The
  deep zone stays a push, without a claim of what follows, until the full record speaks.

## 39. The decision engine: what the record says, before it is rebuilt (2026-10-16, for the owner's decision)

The owner: "before rebuilding the decision engine, let me know your plan in details. what the
documentation says, what the R&D says, and whats your opinion based on the data we have gathered and
analyzed so far. then we can come up with a viable solution."

**39.1 What the documentation says** (the rules in force):
- **The chain:** the valuation rank with its direction gate, then premium direction, momentum,
  structure, the conflict matrix, the candidate, the confirmation (which fails closed), the 24-hour
  timed cooldown, and `final_decision`.
- **The alert rule:** `final_decision` is the sole BUY/SELL alert authority, and a candidate never
  alerts (`CLAUDE.md`).
- **The matrix:** it is "explicit and testable", and it is not to be replaced by a weighted score
  without the owner's approval (`skills/market-analyst.md`).
- **SELL:** its gate (+3.0% premium) has never opened. The highest stored premium is +0.75%.
- **The scorecard** (`analysis/decision_scorecard.py`):
  - it scores the discount, not the price: BUY is right when the discount then shrank;
  - it is not reached from `main`.
- **The proposal of 38.2:** a WHEN rule base takes the alert authority; the old chain computes beside
  it; SELL is retired. It changes `CLAUDE.md`'s alert rule.

**39.2 A correction: "an edge of 0.0" never measured this engine.**
- The 55.2% against always-WAIT's 55.2% was taken while a latch held every decision at WAIT. SP-C
  said so itself: "the scorecard was scoring a constant against a constant ... untested in
  production, not failed" (`SP_C_HANDOFF.md` 16.1).
- The audit (36.2), the proposal (38.1) and the rewritten `PROJECT_MEMORY.md` repeated it as evidence.
  They are corrected by 39.3.

**39.3 The engine replayed** (`research/rd_engine_replay.py`; its rules committed before each run,
784d727 and 9519d94).
- **The data:** `research/data/hourly.json`, 607 readings, 2026-08-04 to 10-04.
- **The method:**
  - production's own functions judge each reading at its own time, from earlier readings only: the
    valuation rank, the confirmation, the matrix, and the cooldown on the replay's clock;
  - a buyer pays the mean of the three cheapest platforms;
  - each rule is counted by episodes, against every reading.

| Rule | Episodes | Basis change, next 24 h | next 72 h |
|---|---|---|---|
| every reading (the control) | 572 readings | +0.67% (median +0.49%) | +1.97% |
| the matrix's BUY candidate | 28 | +0.64% (median +0.28%) | +2.38% |
| the BUY that would have been sent | 11 | +0.39% (median +0.23%) | +2.27% |
| the deep-discount zone (the push's level) | 11 | +0.93% (median +1.16%) | +2.44% |

- **Verdicts, by the rule fixed before the run** (+0.5 pp over the control on 8 or more episodes):
  NO EDGE for all three, at -0.03, -0.29 and +0.25 pp.
  - The deep zone is the best of them. By medians it is +0.67 pp, which matches the head start of 36.1.
  - On 11 episodes that stays suggestive.
- **What the engine says.** WAIT on 555 of 607 readings, BUY on 12.
  - The confirmation held 41 of the 67 BUY candidates: 34 because only one platform showed the
    discount, 7 because the dollar was not yet today's.
- **The scorecard's own rule on the same readings:** the engine 53.8%, always-WAIT 51.9%, always-BUY
  48.1%.
  - That is +1.9 pp over the better baseline, on overlapping readings, about the discount and not the
    price.
- **The cost of following it.**
  - **40 days:** a reader whose day began with WAIT, and who waited for the engine's next BUY, paid
    +2.01% more on average (median +0.81%), 1.9 days later (median). Waiting was cheaper on 11 of the
    40.
  - **16 further days** had no later BUY in the record. They are left out, and they would only raise
    the cost.
- **Caveats:**
  - two months, all in one rising market (+0.67% a day);
  - the replay sent 12 BUYs where production sent 4. The copy is the corrected record (`SP_C_HANDOFF.md`
    45), and the confirmation's inputs differ in detail, so the replay measures the engine's logic,
    not production's exact sends;
  - to be re-run on the full record after 11-01.

**39.4 What the rest of the research says, by the reader's question:**

| Question | Measured | Where |
|---|---|---|
| when | waiting for a 3% dip cost more in 12 of 13 years, in every year of 18K's record | 1, 3 (R4) |
| when | the platforms do not catch up a fair jump: no "wait a few hours" edge | 38.6 |
| when | the deep zone: a head start of about half a point in a day, 11 episodes | 36.1, 39.3 |
| when | up or down in 20 days, and pullback odds: not predictable (AUC 0.49, 0.58) | 3 (R3) |
| how much | the room: +4.0% to +5.7% median over holding per two years, about three independent periods | 27, 36.1 |
| what risk | 18K or the dollar under its 50-day average: the next month weaker by 1 to 6 points | 35.11 |
| what risk | a new 52-week high: continuation (+3.2% over 20 days against normal) | 3 (R4) |
| what risk | in turbulence, a rush of buyers: another 5% fall about twice as often; leads | 37.6 |
| what risk | news: no label separates on 152 days; interventions meet pressure | 37.11 |
| where | the platforms' spread, about 1.9% on 10-15; the sides now recorded for three | 36.1, 37.7 |
| sell | nothing: the gate never opens, and no measure supports one | 39.1 |

**39.5 My reading.**
1. **The engine answers a question the reader does not face.** It asks whether today's discount is
   unusual and widening, hour by hour. The reader converts rial to gold, in a market where 18K is higher
   20 days later on two days in three. Its default answer, WAIT, is the expensive one: following it cost
   2% a time.
2. **Its parts that carry value are not its verdict.**
   - The confirmation's checks guard against data that is not what it seems (one stale platform, a stale
     dollar).
   - The valuation rank says honestly how discounted today is.
   - The deep-discount level is the one timing hint with a head start.
3. **The record supports four answers, none of them hour-level timing:**
   - buy now;
   - how much, from the room;
   - where, by the buyer's price;
   - what risk, from the 50-day breaks and the trend.
4. **SELL has no basis.**
5. **A weighted score fitted to two months would overfit, and the skill's rule forbids it.** An
   explicit table of rules, each with its evidence and its count, is the standard form of an expert
   system, and it keeps the project's audit trail.

**39.6 The proposed solution: the decision table, in stages.**
- **B3a, wire the scorecard** (about half a day; no message changes):
  - score every recorded decision on the buyer's price (the basis 24 and 72 hours later), beside the
    discount rule;
  - run it on production's record on 11-01;
  - keep the replay as the research check, re-run on the full record.
- **B3b, the WHEN table, built beside the old chain** (about two days; its output previewed first). Each
  rule has its verdict, evidence and status:

  | Rule | Verdict | Evidence | Status |
  |---|---|---|---|
  | default | buy now | 12 of 13 years; following the engine cost 2% | admitted |
  | deep zone | heavily discounted now: a good moment | +0.25 pp mean, +0.67 pp median, 11 episodes | context; re-measure after 11-01 |
  | the room out of gold | buy now the share the room holds (60%) | the room's replay | admitted (how much) |
  | 18K or the dollar under its 50-day | a risk line, not a wait | weaker month by 1-6 points | context (risk) |
  | turbulence and a rush of buyers | a risk line | twice as often; 4 of 12 agree | lead |
  | one platform shows it, stale dollar, world gold not live | the verdict names no platform | SP-C 37-38 | admitted (data quality) |
  | sell | none | none | retired |

  - Every verdict prints the rules that fired and their counts.
  - "Wait" enters only when a measure admits it: for example, buying after a 50-day break against buying
    at once, measured by episodes, which is to be run.
- **The gate.** The replay re-run on the full record after 11-01 (August to November, about three months)
  stands in place of a quarter's wait. If the table beats the old chain on the buyer's price there, the
  alert authority moves.
- **The alert rule** (the owner's decision, because it changes `CLAUDE.md`). When the table goes live,
  the matrix's BUY alert is retired. The pushes that stay are:
  - the room's trades;
  - the deep zone, once its record holds;
  - a risk push, only after its preview.

**The decisions for the owner:**
1. Proceed with the table (B3a then B3b)? Or retire the BUY/SELL alerts now and keep the chain only as a
   record? Or keep the chain as it is and wire only its scorecard?
2. Use the replay on the full record as the gate, instead of a quarter?
3. When the table goes live, retire the matrix's BUY alert (and change `CLAUDE.md`'s rule)?

**NEON MIGRATION REQUIRED = NO** for B3a and B3b: the table reads what is stored.

**39.7 Proposed: telling the reader about an outage** (the owner, 10-16: "the user should be informed of
any possible outage, it can either be retrieved through the status command as we have on tlgrm or a push
msg"). For preview, not built.

- **The gap.** Telegram's Status (`src/worker/telegram-trigger.js`) reports the latest GitHub run. Every
  run of this outage finished green, so Status read ✅ while the database was out of reach.
- **The proposal:**
  - **A push when a service changes state**, once each way, after two scheduled runs agree (so a
    single failed read does not alarm). The states: the database out of reach and back; platforms fewer
    than the minimum; world gold on its fallback; the dollar not updating.
  - **Status reads the same state**, kept in `state.json` by the scheduled run. The worker cannot read
    `state.json`, so this costs one short run. Alternatively, Status keeps its instant answer and the
    push carries the news.
- Draft texts, in the owner's wording rules, are shown in the chat for review.
- **Built** on the owner's "go ahead with the outage notice": the push, and Status reading the line
  each scheduled run leaves as an annotation, with no extra run (37.15).

## 40. R&D for the decision engine: scenarios and models (2026-10-16, for the owner's return)

The owner, leaving: "R&D models, build scenarios and come up with some suggestion for decision engine,
once back i will reply on 1 to 3 and also your new R&D."

The question each scenario answers is the reader's: rial to convert into 18K. Four studies were run,
each with its rules committed before it ran:
- `rd_engine_replay.py`: 784d727, 9519d94;
- `rd_when_scenarios.py` and `rd_where_and_hour.py`: 4edb48e, and 522d2d8 for the hour's follow-up;
- `rd_when_model.py`: 1415e68.

**40.1 WHEN: fixed rules on 18K's daily record, 2014-2026** (`research/rd_when_scenarios.py`).
- **The test:** convert within 20 trading days; on independent windows, every 20th day; the cost
  against buying at once.
- **The carry:** with it, the waiting rial earns the fixed-income fund's return, from 2015-03.

| Rule (with carry) | 2014-2019 mean | 2020-2026 mean | last 2 years | cheaper than at once | worst | verdict |
|---|---|---|---|---|---|---|
| wait for a 2% dip | +0.74% | +2.20% | +4.11% | 58% / 53% | +22.6% | COSTS |
| wait for a 3% dip | +0.82% | +2.01% | +3.77% | 56% / 49% | +22.6% | COSTS |
| wait for a 5% dip | +1.18% | +1.97% | +4.31% | 51% / 44% | +22.6% | COSTS |
| wait for a deep gap (rank <= 20%) | -0.16% | +0.67% | +2.42% | 38% / 39% | +20.2% | MIXED |
| wait out an 18K 50-day break | -0.08% | +0.14% | +0.10% | 13% / 9% | +8.7% | MIXED |
| wait out a dollar 50-day break | -0.74% | +0.21% | -0.22% | 25% / 12% | +7.7% | MIXED |
| split in four weeks | +0.57% | +0.91% | +2.37% | 49% / 43% | +17.7% | COSTS |
| skip less-discounted days | +0.06% | +0.11% | +0.96% | 10% / 17% | +13.7% | COSTS |
| skip a falling knife | +0.13% | +0.03% | -0.03% | 0% / 2% | +7.2% | COSTS |
| **the engine's shape (deep and widening)** | +0.01% | +0.68% | +2.45% | 43% / 44% | +20.2% | COSTS |

- **No rule beats buying at once.**
- **The dip rules show the trap:** their median is often below zero, because waiting usually saves a
  percent, but their worst case is about +20%, when the market jumps before the dip comes. That tail
  is the rial's.
- **The rules that wait out a break** rarely wait, and when they do the effect is a few tenths of a
  point, changing sign between eras.
- **The decision engine's own shape on daily data costs** +0.7% to +2.5% in the last six years.

**40.2 WHEN: a learned model, walk-forward 2018-2026** (`research/rd_when_model.py`).
- **The test:** each year is predicted from the years before, on 12 causal features (the gap and its
  rank, 18K against its averages, returns, volatility, distance from the high, the dollar's trend, world
  gold's). The reader waits 20 days when the model gives waiting better than 60%.

| Model | AUC by year | waited | mean cost | years below 0 | verdict |
|---|---|---|---|---|---|
| logistic regression | 0.41-0.68 | 27% | +0.67% | 2 of 9 | NO |
| gradient boosting | 0.23-0.72 | 36% | +1.17% | 3 of 9 | NO |

- Waiting pays on 27% to 57% of days, depending on the year, and no model finds which ones in advance.
- This agrees with R3 (section 3): whether 18K is higher in 20 days is not predictable.

**40.3 WHERE: the platform is worth more than the hour** (`research/rd_where_and_hour.py`; 607
readings, 62 days).
- **The median platform** sits 1.06% above the cheapest (median 0.88%). The basis of three sits 0.53%
  above it.
- **Platform by platform:**
  - Milli was the cheapest in 84% of readings, 0.05% above the cheapest on average;
  - Goldika, a buyer's price, was 2.15% above;
  - the gallery references were 0.9% to 1.3% above.
- **The caveat** (37.7): the prices are of mixed kinds, so this is the spread a reader sees, not a
  proven saving. Milli's side is not published.
- **The hour.** Readings at 06-09 Tehran sat 0.40% below the day's mean, on 68% of 44 days, which passes
  the rule. The follow-up split the days by direction:
  - on up days the morning was 0.80% below the day's mean (90% of 29 days);
  - on down days it was 0.37% above (15 days).
- **The verdict:** the drift, not the hour. In a down trend the morning would be the more expensive time. "Buy in the
  morning" is "buy now" again.

**40.4 What the scenarios say together.**
1. **WHEN:** no measured rule, and no model, beats buying at once:
   - the record of 39.3 (two months, hourly);
   - the daily record of 40.1 (twelve years, both eras);
   - the walk-forward of 40.2.

   The one hint left is the deep zone on hourly data: +0.25 pp mean, +0.67 pp median, 11 episodes, to
   be re-measured after 11-01.
2. **WHERE** is worth about a percent, every time, which is more than any timing rule offers. It needs
   each platform's buyer's price (fees included) to be claimed rather than suggested.
3. **HOW MUCH** is the room's question, and it has the only measured gain over holding: +4% to +6% per
   two years, from leaving gold rarely and on broad agreement.
4. **RISK** stays context: the 50-day breaks, the trend, turbulence. None of them earns a "wait".

**40.5 Suggestions for the decision engine** (for the owner's decision with 39.6's three questions):

| Scenario | What the engine says | Alerts | For | Against |
|---|---|---|---|---|
| **A. The advisor table** (recommended) | buy now, where (the cheapest buyer's price), how much (the room's posture), the risks; "heavily discounted now" when in the deep zone; no WAIT, no SELL | the room's trades; the deep zone, once it holds; SERVICE | every line has a measured basis; the default is the record's | retires the matrix's BUY alert, which changes `CLAUDE.md`'s rule |
| B. The matrix, reframed as information | as now, but BUY reads as "heavily discounted and still widening", with no instruction | as now | no rule change | keeps a verdict that costs when followed (39.3, 40.1) |
| C. The matrix as a record only | the matrix computes and stores; nothing is sent from it | the room's trades; SERVICE | the least to build | the reader loses the one timing hint (the deep zone) unless the push returns |
| D. A learned WHEN model | — | — | — | rejected by 40.2 |

- **Each of A to C keeps the confirmation checks** as data-quality gates on anything naming a platform.
- **A would be built in the stages of 39.6:** the scorecard first, then the table beside the old chain,
  with the replay on the full record after 11-01 as its gate.
- **The work A needs that B and C do not:** each platform's buyer's price, for WHERE.
  - Fees and sides are recorded for Goldika, Daric, Taline and Ayyareh.
  - The other seven need their buy price found or marked unknown.

**NEON MIGRATION REQUIRED = NO**; research only.

## 41. The owner's challenge: falls, parking in fixed income, and the central bank (2026-10-16)

The owner, on 40: "honestly, i cant decide, my gut feeling says you are wrong. you are seeing the whole
pattern in an inflated economy, in the past 2-3 years, dollar and gold have rised. now the gold is in a
side way channel, and the whole iran gold going up is on dollar. but when the CBI intervens, like past
week, the dollar loosen and gold prices drop. the whole benefit of the system should be in a way to
collect data, analyze and predict such falls. or even when the whole market is on wait move to fixed
income. so it should be able to see if the rally is coming to an end, how long park, what are the
signals to watch. how can the gold etf money flow help."

**41.1 Where the challenge is right.**
- 40.1 asked a buyer's question: convert within a month. It did not ask a holder's: when to step out of
  gold into fixed income, and for how long. That is the room's question.
- 37.11 measured the central bank's interventions at 1 and 3 days. The owner's claim is about the week
  or two after.
- Both are measured below. Each study's rules were committed before it ran (5bbf23d).

**41.2 The last four weeks** (tgju, and the channels' headlines):

| Days | The dollar | 18K | |
|---|---|---|---|
| 09-27 to 10-03 | 235,000 to 267,900 (+14.0%) | 23.90M to 26.23M toman | a surge |
| 09-30 | | | the bank announces $2 billion of banknotes |
| 10-01 to 10-06 | +1.5%, +3.7%, then flat to 268,820 | to 26.74M | |
| 10-07 to 10-13 | to 257,710 (-4.1%) | to 25.74M (-3.7%) | the fall the owner saw |
| 10-14, 10-15 | +2.4%, +1.5% | +1.2%, +0.8% | |

The fall came a week after the announcement, from the surge's peak. Ten trading days on, the dollar was
still 1.6% above the day before the announcement.

**41.3 The interventions at 1 to 20 trading days** (`research/rd_cbi_horizons.py`):

| Definition | Episodes | Dollar +5d | +10d | +20d | Dollar's control (+5d, +10d, +20d) |
|---|---|---|---|---|---|
| A, the AI model's labels (to 03-24) | 6 | +2.43% | +2.52% | +5.67% | +1.56%, +2.98%, +5.94% |
| B, channel headlines (to 10-15) | 19 | +2.88% | +5.53% | +9.92% | +1.68%, +3.30%, +6.69% |

- **The verdict:** a fall after an intervention is not shown at any horizon. The dollar rose more after
  announcements than on other days.
- **The reading:** an intervention marks a surge under way; the bank acts when the dollar is running. A
  pullback, when it comes, starts from the surge's peak, which is the case of 41.2.
- **The caveats:**
  - B is noisy: of its 19 episodes, about 6 to 8 are interventions, and the rest are exporters'
    currency, fund notices and commentary;
  - A has 6 episodes.
  - Re-measured when the labelling reaches October (it stands at 152 of 357 days).

**41.4 Falls and parking, 2013-2026** (`research/rd_falls.py`).
- **The falls:** 73 falls of 5% or more within 20 days. On any day the chance is 12% in 2014-2019 and
  23% in 2020-2026.
- **Parking:** the rial in the fixed-income fund for 20 trading days from a signal's first day, against
  holding 18K.

| Signal | 5% fall after: 2014-19 / 2020-26 (any day: 12% / 23%) | 20-day return after | parking in fixed income: 2014-19 / 2020-26 | verdict |
|---|---|---|---|---|
| 18K under its 50-day | 12% / 28% | -0.6% / +1.6% | **+2.35% / +0.80%** | parking pays |
| EMA20 under EMA50 | 27% / 30% | -0.0% / -0.3% | **+2.21% / +2.24%** | parking pays |
| the dollar under its 50-day | 14% / 38% | +1.9% / +0.5% | **+0.10% / +1.83%** | parking pays |
| a dollar spike (+8% in 10 days) | **31% / 44%** | +7.9% / +2.4% | -4.74% / +0.62% | warns; parking does not pay |
| turbulence | **29% / 37%** | +0.8% / +3.9% | +0.50% / -1.02% | warns; parking does not pay |
| a rush of buyers in the funds (2018-) | — / **41%** (of 21%) | — / +4.9% | — / -2.52% | warns (one era) |
| a rush in turbulence (2018-) | — / **55%** (of 21%) | — / +5.5% | — / -3.08% | warns (one era) |
| 18K stretched 15%+ | 14% / 32% | +12.4% / +8.3% | -8.36% / -4.98% | neither |
| sideways | 7% / 29% | +0.7% / +1.6% | +1.50% / +0.59% | neither (paid in 59% / 45%) |
| heavy money out of the funds | — / 31% | — / +3.0% | — / -0.56% | neither |

- 10 to 39 episodes a cell.

**41.5 What it says.**
1. **"When the market is on wait, move to fixed income" holds**, on the trend's own breaks:
   - 18K under its 50-day;
   - the 20-day EMA under the 50-day;
   - the dollar under its 50-day.

   After each, the next month of 18K was weak, and 20 days in the fund beat holding, by +0.8% to +2.4% on
   average in both eras.
2. **The signals that warn of a fall are not exit signals.** A dollar spike, turbulence and a rush of
   buyers in the funds roughly double the chance of a 5% fall. They also come before further rises (a
   dollar spike was followed by +7.9% in 20 days in 2014-2019), so leaving on them lost.
   - They say risk is high, not that the rally ended.
   - This is where the funds' money flow helps: a rush of buyers in turbulence is the strongest warning
     on record, 55% against 21%. It is a reason to watch, not to sell.
3. **A stretched rally keeps running** more often than not. Leaving at 15% above the 50-day lost 5% to 8%.
4. **The central bank's interventions** come during surges, and the dollar keeps rising after them.
5. **40.1 stands for its own question.** A reader with rial to convert does better buying at once. The
   new finding is for the holder.

**41.6 What it means for the decision engine.**
- The holder's question is the room's.
  - The trend breaks above are not explicit members: the chartist and the market-state member cover them
    only in part.
  - The warnings (spike, turbulence, a rush in turbulence) are candidates for a "risk" line, not a vote
    to leave.
- **"How long to park"** is not yet measured: only 20 days was tested. To test:
  - out until the break ends (18K back over its 50-day), against 10, 20 and 40 days;
  - the break combined with a warning;
  - the room with a trend-break member against the room without, by 33's paired test, designed on
    2014-2019 and judged on 2020-2026.
- **The labels' remaining 205 days** re-measure the interventions with the owner's own week of 10-07.

**NEON MIGRATION REQUIRED = NO**; research only.

## 42. The holder's question, full power: how long to park, what to watch (2026-10-16 night)

The owner: "Go ahead ... take a deep breath, stretch your fingers (and models) and GO FULL POWER." Six
studies were run, each committed before it ran:
- `rd_parking.py`: fa15bbf;
- `rd_room_breaks.py`: 80bfeba;
- `rd_room_stays.py`: 84264ec;
- `rd_tether_lead.py`: 4d45495, with a lookup fix (rules unchanged) before its first complete run;
- `rd_fund_premium.py`: ddd44dd;
- a descriptive check of the platforms on Fridays.

**42.1 How long to park after a trend break** (`research/rd_parking.py`, 2015-2026).
- **Per episode, many exits pay**, as 41.4 found: the gain is positive in both eras and paid in at least
  55% of episodes.
  - Best: 18K and the dollar both under their 50-day, parked 10, 20 or 40 days (+2.1% / +1.2% at 20).
  - EMA20 under EMA50, parked 20 or 40 days (+2.2% / +2.2% at 20).
- **On a reader's record, no rule is worth following.** The reader starts in gold, parks the whole
  holding or 40% on every break, and comes back on the exit, at Daric's 0.30% or Goldika's 2.37%,
  measured over two-year windows against holding.
  - The 50-day breaks of 18K and the dollar are era-bound. Windows starting 2015-2019 gained (+16% to
    +24% at Daric's cost); those starting 2020-2024 lost (-1% to -9%).
  - The nearest is EMA20 under EMA50, out 40 days with 40% of the holding.
    - At Daric's cost: +2.8% and +2.8% median, ahead in 65% of windows, worst -6.0% (the bar is -5%).
    - At Goldika's: +1.1% and +1.1%, ahead in 56% (the bar is 60%).
  - The worst windows of the others ran -15% to -46%: the jumps missed while out.
- **Lesson 28 again:** leaving gold on one signal is the expensive mistake. Whipsaws and costs take back
  what each episode earned.

**42.2 Trend breaks as members of the room** (`research/rd_room_breaks.py`, section 33's paired test).

| Added at weight 1.0 | Paired median vs the room as built (4 tests) | Windows improved | Accepted |
|---|---|---|---|
| EMA cross | -4.0 to -4.8 pp | 9-14% | 0 of 4 |
| EMA cross, only to leave | -0.9 to -2.6 pp | 12-25% | 0 of 4 |
| 18K 50-day | -2.6 to -4.2 pp | 5-23% | 0 of 4 |
| dollar 50-day | -2.1 to -4.1 pp | 12-24% | 0 of 4 |
| both 50-day | -2.5 to -3.4 pp | 8-20% | 0 of 4 |

- **Every break makes the room worse.** The break's edge sits in its first days. As a standing vote it
  keeps the room out while gold, on average, still beats the fund. From 2021, on the days the breaks
  lean out, gold over fixed income in the next 20 days was still +0.2% to +1.0%.
- **The room as built:** +5.0% to +9.0% over holding at Daric's cost (Afran windows), ahead in 83-100%.

**42.3 How long the room parks** (`research/rd_room_stays.py`, 2018-01 to 2026-10-01).
- **The stays:** 16 completed, 40% of the grams each; out of gold on 17% of days. Median 18 trading
  days, from 9 to 70.
- **Their gains:** 11 of 16 gained, by +1.19% on the whole holding on average (median +1.64%; best
  +7.55%, worst -7.59%).
- **The losses** were 2018-2019's sanction-shock jumps, out while 18K rose 16% and 24%.
- **Since 2020,** 8 of 9 stays gained or broke even, among them:
  - 2023-05-20 to 08-15, 70 days, 18K -10.0%: +6.96%;
  - 2025-03-17 to 04-07, 18K -9.2%: +4.79%.
- **On 10-01** the room was all in gold, back since 08-06.
- So the answer to "how long to park" is the room's: until its committee turns back, typically three to
  four weeks.

**42.4 Tether over the Iranian weekend** (`research/rd_tether_lead.py`, 2020-11 to 2026-10, 187 weekends).

| | 2020-11 to 2023-06 | 2023-07 to now |
|---|---|---|
| Tether's weekend move against Saturday's dollar / 18K | r = +0.53 / +0.53 | r = +0.61 / +0.46 |
| weekends of a 1%+ move: Saturday's dollar / 18K the same way | 66% / 75% (53) | 78% / 78% (23) |
| Tether down 1%+: Saturday's 18K | -1.79% (38) | -1.81% (13) |
| Tether up 1%+: Saturday's 18K | +1.98% (15) | +1.99% (10) |
| every Saturday's 18K | -0.08% | +0.11% |

- **The verdict:** A SIGNAL TO WATCH, in both halves.
- **It is the weekend's catch-up, not a general lead.** On trading days, Tether today against the dollar
  tomorrow is r = 0.00.
- **For a platform buyer:** the platforms trade on Fridays. In the hourly copy (9 weekends, one with a
  1%+ Tether move) their Friday moves did not follow Tether. Whether they already price it, or lag it,
  is to be measured on the full record after 11-01.

**42.5 The gold fund's price against its NAV** (`research/rd_fund_premium.py`, Ayyar, 2019-2026).
- **The verdicts:** a high premium (rank 90%+, 44 episodes) does not warn. A deep discount (rank 10% or
  less, 40 episodes) does not precede rises.
- **Seen, not registered:** after a deep discount 18K was weaker (+0.4% against +3.5% in 20 days,
  2019-2022; +3.8% against +5.4%, 2023-2026), and fell 5% more often (37% against 23%; 33% against 22%).
  - A discount behaves like sellers in control, not like a bargain.
  - It was not the hypothesis committed, so it is a lead to pre-register on new data, not a result.
- **On 10-03** the premium read +9.5% (relative), rank 97% of its year: buyers paying up.

**42.6 The signals on the latest close (10-15)**, for the record:

| Signal | Reading | State |
|---|---|---|
| 18K against its 50-day | +10.2% | no break |
| EMA20 against EMA50 | +7.0% | no break |
| the dollar against its 50-day | +15.1% | no break |
| the dollar's 10 days | -0.1% | no spike |
| 18K's volatility, rank in its year | 8% | calm, no turbulence |
| 18K under its year's high | -1.8% | — |
| Ayyar's premium to NAV (10-03) | +9.5%, rank 97% | buyers paying up |
| the room (10-01) | all in gold | — |
| the pattern reader (`caluclator/patterns.read`, tgju's last 300 days) | a sideways range since 09-29 (7 Mehr), 25.27M-26.74M toman, after the range of 09-03 to 09-28 broke up | the owner's "side way channel"; on 18K's record a breakout up from a range reached its target first in 30 of 39, a breakdown in 12 of 22 (37.4) |

**42.7 What the evidence supports for the decision engine** (with 39.6 and 40.5, for the owner's
decision). Three readers, three questions:

| Reader | Question | What the record supports |
|---|---|---|
| has rial | when to convert, where | buy now (40.1, 40.2; 12 years, both eras); the cheapest buyer's price (40.3); two short hints: after a weekend in which Tether fell 1%+, Saturday's 18K was about 1.8% lower on average (42.4), and the deep-discount zone (39.3) |
| holds gold | gold or fixed income, how long | the room: 40% out on broad agreement, back when it turns, stays of three to four weeks, 11 of 16 gained (42.3); not a single break (42.1, 42.2) |
| either | what to watch | measured warnings, each with its rate: a dollar spike, 31-44% against 12-23%; turbulence, 29-37%; a rush of buyers in the funds during turbulence, 55% against 21% (41.4); Tether's weekend move (42.4). They warn; they are not exits |

- **The central bank's interventions** mark a surge under way (41.3), so they read as a warning, not as
  a fall to come.
- **The old matrix** has no measured role among these (39.3, 40.1).
- **The proposed design** is A of 40.5 with the room as its holder's answer and a WATCH section built
  from 41.4 and 42.4.
  - Every line carries its measured rate.
  - A preview comes first.
  - The alert authority changes only on the owner's decision.

**Next, measurable on the full record after 11-01:**
- the platforms on Fridays against Tether;
- the deep zone;
- the replay of 39.3 on three months.

**NEON MIGRATION REQUIRED = NO**; research only.

**42.8 Addendum, 10-17 05:43: the labels at 198 days.**
- **The labelling:** the fourth run labelled 28 days, to 2026-05-09; 198 of 357 are done. The fifth
  started at 02:15 UTC.
- **Re-measured**, with the verdict rules unchanged (`rd_news_labels.py`, `rd_cbi_horizons.py`):
  - **Interventions:** no new intervention days were labelled after 03-24. Definition A still has 6
    episodes, and B's verdict is still not shown at any horizon. 41.3 stands.
  - **Escalation,** now 100 days: the dollar +0.14% the next day and +0.01% over 3 days, against +0.29%
    and +1.00% on days without. It does not separate as a rise, which agrees with 37.11.
  - **"Sanctions eased"** reaches 8 days for the first time: the dollar -2.38% the next day (fell on
    62%), -1.05% over 3 days, against +0.15% and +0.53% on all days. A lead that fits the owner's view
    that relief loosens the dollar. Eight days are too few to claim.
  - **The model's own "dollar down"** call (40 days) was still followed by +1.20% over 3 days, against
    +0.53% after its "up". It still has no skill.

## 43. Health check 2026-10-17, 09:50 Tehran (PROJECT_OPERATIONS.md section 15)

Neon is suspended to 11-01, so steps 2, 3 and 5 to 9 cannot query the database. They are read from the
run logs instead.

- **Runs.** 24 since 10-16 09:00, all `success` on `main`.
  - Every hourly ANALYZE from 09:00 to 21:00 on 10-16 and from 06:00 to 09:00 on 10-17 is there.
  - The owner's UPDATE (10:00, 14:35, 18:42), DIRECTION (11:42, 14:38, 09:04) and REPORT (10:10)
    dispatches sit between them.
  - Runs take about 1.5 to 2 minutes while the database is out of reach.
- **The SERVICE notice:**
  - announced once, 10-16 19:01 ("out of reach since 21 Mehr, 21:00");
  - every run since leaves the same service line.
- **The spool:** 571 held writes at 21:00, 627 at 06:00, 757 at 09:00, news included. The state cache
  entry is 151 KB compressed, against a 20 MB ceiling.
- **The recovery step** reports "nothing to recover" on every run: its marker holds.
- **News:** 35 to 63 new items held per run, from all twelve feeds.
- **The 21:00 chart** was sent without the database (1,000 tgju candles to 10-15).
- **/Direction** (09:04) was computed live from tgju and sent.
- **Platforms**, read from the logs' CALCULATE sections, 10-16 19:00 to 10-17 09:00:
  - Daric answered 403 on every run; the node's copy is unreachable while Neon is down.
  - HoorGold timed out once (06:00).
  - Flat while the others moved: HoorGold 263.50M for 14 hours, MioGold 261.75M all night, Parasteh
    262.95M, and Ayyareh and Eligold 262.16M from 06:00 to 09:00.
    - The first three are gallery reference prices, set once a day by nature (37.7).
    - Ayyareh and Eligold flat before about 11:00 is the known morning pattern.
    - None of them is among the three cheapest (Milli, WallGold, Invi), so the discount is unaffected.
- **Decisions:** valuation UNKNOWN (no pool without the database), so every reading is WAIT. The premium
  is -2.5% to -2.6%. PAPER cannot run without the database.
- **The labelling:** the fifth run is under way, from 05:45 Tehran.
- **Verdict:** healthy within the outage.
  - Open: Neon until 11-01; Daric refusing the runner.
  - The owner: paste the worker (37.15) into Cloudflare, and check the phone's spool (`wc -l
    ~/iran_node_spool.jsonl`, 1,010 on 10-16 morning).
- **10-17, later:** the owner pasted the worker into Cloudflare, so Status now carries the service line.
  The phone's spool is to be checked in the afternoon.

## 44. Sideways channels, the owner's doubt measured (2026-10-17)

The owner: "I agree with you, but with caution. i have doubt on you for this one. the backtest has
repeatedly confirmed the hold, but the problem as i have raised several times, is the times the gold enter a
sideway channel. and now the only way you are relying upon is the EMA method, not bad but not much relible.
how we can fix this. and im suprised why with all the information you have you cant come up with a
solution."

**44.1 What was already known** (section 16, 2026-10-04, `research/rd_sideways.py`):
- the room's sideways rule (the 60-day efficiency ratio under a random walk's) flagged 74% of the days of
  the 1405 channel;
- inside sideways, 18K earned about what fixed income earns (+1.70% against +1.61% over 20 days);
- breakouts did not say which way the next leg goes: up-breaks were followed by an ordinary month, and
  down-breaks were mostly false in toman;
- "sideways: 50% out" lost -4% to -23% against holding.

The room does not rest on the EMA: it is eight members, the market-state (sideways) member among them, and
it leaves only on broad agreement (section 27).

**44.2 The box, tested today** (`research/rd_sideways_box.py`, rules committed in 1b0ee51 before the run).
- **A defect of mine on the way:** the study was first written over section 16's `rd_sideways.py`. That file
  was restored unchanged (f4bd4b9), and the new study is `rd_sideways_box.py`.
- **The time spent in each state, and what followed** (18K's next month while on, against the fund's):

| Detector | Days on | 18K's next month while on | The fund's | 18K while off |
|---|---|---|---|---|
| the pattern reader's box | 16% | **+6.18%** | +1.85% | +3.84% |
| the room's sideways rule | 28% | +1.64% | +1.88% | +5.23% |
| 18K and the dollar both in a box | 7% | **+7.11%** | +1.95% | +3.99% |

- **A box in 18K is a pause inside an uptrend.** The month after it was stronger than usual: the flags and
  breakouts of 37.4, again.
- **The room's sideways rule** finds the flat stretches, where gold and the fund earn about the same.

**The reader's record** (two-year windows, both costs; median for 2015-2019 | 2020-2024 starts):

| Policy | 40% of the holding, Daric | 40%, Goldika |
|---|---|---|
| park the box | -9.1% / -4.0%, ahead 8% | -17.4% / -14.6% |
| park on the room's sideways rule | **+8.6% / -0.6%**, ahead 58%, worst -6.2% | -1.7% / -10.9% |
| park when both are in a box | -6.6% / -3.4% | -13.1% / -7.7% |
| trade the box (out in its upper third, back in its lower third or on an up-break) | -11.8% / -7.1%, ahead 2% | -20.7% / -15.9% |

The 100% versions lose more.

- **The verdict:** NOT WORTH FOLLOWING, all of them. The closest, parking 40% on the room's sideways rule,
  is ahead in 2015-2019 only.
- **Trading the box** sells into the pause before the next leg and buys back above where it sold.

**44.3 How the room handled the 1405 channel** (`rd_room_stays.py`, 42.3):
- out 40% from 2026-03-18 to 05-25: 56 days, 18K +2.6%, the fund +5.7%, a gain of +1.19% on the whole
  holding;
- out from 07-21 to 08-06: +0.26%;
- all in gold from 08-06, before the jump of mid-August (+20% in 20 days, section 16).

**44.4 What it means.**
- The fix for sideways is not a sideways rule. In toman a box is usually a pause, and leaving it costs the
  jump.
- The flat stretches that do exist pay gold and the fund about the same, so the gain from parking in them
  is small and sits in their first weeks.
- That is what the room does: the sideways reading is one vote among eight, it moves 40%, and it comes back
  when the votes turn. It parked twice in the 1405 channel and was in gold for the jump.
- What the advisor can add for a reader is the sight of it:
  - "the room is out: sideways, no new high";
  - "a box since 7 Mehr between 25.27M and 26.74M; on 18K, breaks up from a box reached their target first
    30 of 39 times".

  It is not another exit.

**NEON MIGRATION REQUIRED = NO**; research only.
