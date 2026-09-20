# Lessons Learned

A record of the failure patterns this project has actually met, written so a future
session recognises the shape of a defect before spending a week on its symptoms.

Every item here was found in production, not in review. All of them passed their
tests. None of them raised an error. That is the point: the defects this system
produces do not crash, they return a plausible number forever.

Kept in failure-pattern order rather than chronological, because the patterns repeat
and the dates do not matter.

---

## 1. The constant that looks like a reading

**The pattern.** A classifier is written with a fixed threshold. The market never
crosses it. The classifier emits the same value on every reading for months. Nothing
fails, nothing logs, and every downstream layer treats the constant as information.

**Where it has happened, four times:**

```text
valuation_state = CHEAP      on every reading ever stored
regime_state    = PANIC      96 of 96 analysis snapshots
final_decision  = WAIT       264 of 264 stored decisions
news relevance  = UNKNOWN    1,638 of 2,345 events (70%)
```

**Why it keeps happening here.** Thresholds get chosen from intuition about a market
where the premium hovers near zero. This market does not: the discount has sat
between 1.82% and 8.19% for its entire recorded history. A threshold of 2.0 in that
market is not a threshold, it is the floor. Likewise `platform_spread > 500000` Rials
when a normal spread is 3,300,000.

**The measurement that exposes it.** Group by the output and count:

```sql
SELECT regime_state, COUNT(*) FROM analysis_snapshots GROUP BY 1;
```

One row means the classifier is a constant. This takes ten seconds and should be run
against every categorical column the system produces, on a schedule.

**The fix that works.** Replace the constant with a percentile of the market's own
recent distribution, recalculated every run. `bubble_position.CHEAP_PERCENTILE` and
`regime.STRESS_PERCENTILE` both do this. A reference that moves with the market
cannot be permanently on the wrong side of it.

**The trap inside the fix.** A percentile still needs a sample, and a sample needs
both a count and a calendar span. 30 readings at hourly cadence is under two days. A
line saying "of the last 30 days" that measures against Tuesday is a new constant
wearing the old one's clothes. See `bubble_position.MIN_SCHEDULED_COVERAGE_DAYS`.

---

## 2. The latch that was meant to be a timer

**The pattern.** A suppression rule is written to be temporary. The time dimension is
deferred. What ships is permanent.

**Where it has happened, twice:**

`caluclator/signals.apply_hysteresis` compared the candidate decision against the last
alert and suppressed a match. `cooldown_hours` sat in the signature, documented as
"reserved for future use". It was never implemented. Because `state.json` persists
across runs through the Actions cache, and because the latch clears only when a
*different* alert fires — a SELL, requiring an EXPENSIVE valuation that has never once
occurred — the first BUY ever sent disabled every BUY thereafter. 100 of 100 BUY
candidates were held.

`regime._apply_hysteresis` has the same shape: `if previous in ("FEAR", "PANIC")`
keeps a stressed regime stressed. Combined with a permanently-firing threshold
(pattern 1), PANIC became unreachable from any other state.

**The tell.** A docstring that says "cooldown", "temporary", "for now" or "reserved
for future use" beside code with no clock in it.

**The fix.** Either implement the time dimension or do not ship the suppression.
And when the timestamp needed to evaluate it is missing, **fail open**. Failing closed
reinstates the latch: one absent record disables the feature forever. A duplicate
alert is noise; silence is what cost this project a hundred signals.

---

## 3. Measuring a constant and calling it evidence

**What happened.** The decision scorecard reported a 55.2% hit rate against a 55.2%
always-WAIT baseline, edge 0.0. That was read — by me, in writing, to the product
owner — as evidence that the decision strategy does not work.

It was not. The scorecard scored `final_decision`. `final_decision` was a constant
(pattern 2). It was comparing always-WAIT against always-WAIT and correctly returning
zero. **The engine had not been disproven. It had never run.**

**The lesson.** Before interpreting any performance metric, check that the thing being
measured varies. A baseline comparison between two identical series always returns no
edge, and that result is indistinguishable from a real negative finding unless you
look.

**The check.** `SELECT DISTINCT <measured_column>` before drawing any conclusion from
a metric computed over it. If the answer is one row, the metric is meaningless and no
amount of statistical care downstream will rescue it.

---

## 4. Built but not wired

Tested capability the runtime never reaches. Eight instances so far:

```text
C14C news collector             built, never invoked
Analyze trigger                 built, never routed
analysis window enforcement     built, never applied
RUN baseline                    built, compared against the wrong row
outcome evaluation              built, only ever called on unmatured horizons
resolve_similar_outcomes        built, never called
resolve_zone_episodes           built, never called
regime threshold calibration    built, computed, logged, then discarded
```

The eighth was committed in the same change that documented this pattern. Regime
calibration ran correctly in production and printed its result to the log every hour,
and `config/config.json` pinned the same three keys, which the merge lets win. The
unit tests constructed the classifier directly and never loaded the shipped config, so
the suite was green while the feature was inert. It was caught a day later only
because someone asked whether the system was healthy.

**Why tests do not catch it.** A unit test calls the function directly. Nothing
asserts that production does.

**The configuration corollary.** A feature whose behaviour depends on configuration
needs an assertion against the *shipped configuration file*, not only against values a
test passes in. `kpi_sp_c5.test_18b` reads `config/config.json` directly for exactly
this reason.

**The fix.** Assert reachability, not just correctness. `kpi_sp_c3.py` was written
specifically for this: it checks that the runtime path invokes the capability, not
that the capability works. Any new module needs one such assertion.

**The cheapest detector.** Count production rows, and check that the output varies.
A feature that has run for a week and produced zero rows has not run — and one whose
output never changes has not run either, whatever the logs say.

---

## 5. Unbounded external calls

`collector/bonbast.get_usd_sell_rate` invoked a third-party CLI through
`subprocess.run` with no `timeout=`. The CLI makes its own network calls and sets no
timeout either. When the runner's network degraded, the subprocess blocked until the
GitHub job timeout killed the entire run twenty minutes later.

Eight scheduled runs between 2026-09-14 and 2026-09-18 died this way — roughly one to
two missed readings a day against a four-minute healthy run. The log signature is
distinctive: a DNS failure on the preceding collector, then twenty minutes of silence,
then `##[error]The operation was canceled`.

**The lesson.** Every call that leaves the process needs a bound — `requests`,
`subprocess`, database, all of it. The eleven HTTP collectors all had timeouts. The
one subprocess did not, and it was the one that took the system down.

**The audit.** Grep for `requests.get(`, `requests.post(`, `subprocess.run(` and
`subprocess.Popen(` and confirm a timeout on each. Watch for arguments on
continuation lines — a naive grep reports false positives.

---

## 6. A unit that is right in storage and wrong in display

**Timezone.** Everything stored is UTC, because the runner and the database are UTC.
Every reader is in Iran, UTC+3:30. The two were never reconciled, so the message
footer printed a time 3.5 hours behind the reader's watch, and anything grouping "by
day" cut each day at 03:30 local.

The day-grouping half was silent for weeks: the cron window (06:00–21:00 local) falls
inside a single UTC date, so it only misbehaved for a user pressing Update between
midnight and 03:30. It surfaced only when a footnote started naming clock times.

Fixed by `src/timeutil.py` — one definition, one offset, applied at every display and
grouping boundary. Iran abolished DST in 2022, so a fixed offset is correct and avoids
depending on a tz database that is not present on every runner.

**Percentage points versus percent.** The premium is itself a percentage and always
negative, so a percent-change of it inverts the sign: a discount shrinking from -5.0
to -4.0 computed as `((-4.0 - -5.0) / -5.0) * 100` yields -20 and records a move
toward zero as a move away from it. Every premium delta is percentage points.

**Rials versus Tomans.** 1 Toman = 10 Rials. Storage is Rials, display is millions of
Tomans. A threshold written in the wrong one is off by a factor of ten and still looks
plausible.

---

## 7. The order statistic that is not a market level

The discount was computed from the single cheapest platform, on the reasonable ground
that a buyer transacts at the lowest price. Measured across 332 snapshots, that
platform sits more than 3 median absolute deviations below the median of the rest in
**62%** of readings. It is a tail point, not a level.

The cost was noise: 60% more hour-to-hour variance than a trimmed basis and eight
times as many jumps above 1 pp between consecutive readings. A 1 pp move in an hour is
a quote artefact.

And quotes freeze. Parasteh does not move 67% of the time, MioGold 52%, with freezes
up to 89 hours. On 2026-09-15 a stale MioGold quote moved the reported discount 2.07
pp and produced "unusually large, cheaper than 94% of the last 30 days" on a day the
market did not move. It refreshed the next morning and the number fell back.

**The lesson.** A minimum, a maximum or any single extreme is an order statistic, not
an estimate. Use it for what it literally is — the price you can execute at — and use
a trimmed statistic for anything that needs to represent the market.

**The corollary.** Separate the number you act on from the number you measure with,
and say which is which in the output.

---

## 8. Changing a definition is a change to every comparison

Any change to how a stored quantity is computed silently invalidates every historical
comparison against it. Switching the discount basis from the minimum to the platform
average would have moved today's reading 0.79 pp with no market movement, and its rank
inside a window built on the old basis from the 38th percentile to the 12th.

**The rule.** When a basis changes, the window must be rebuilt on the same basis in
the same commit, or the two must be kept explicitly separate and documented. The
current split — display on the trimmed basis, `premium_percent` still on the minimum —
is deliberate and recorded in `CLAUDE.md` and `SP_C_HANDOFF.md` §15.1. It is not a bug
to be tidied up by a future session without the phase and approval that change needs.

---

## 9. Environment drift

A loose dependency range (`scikit-learn>=1.3.0,<2.0.0`) let CI resolve 1.9.1 while
development ran 1.6.1. `multi_class` was removed in 1.7 and 14 of 36 assertions failed
on CI while passing locally on the identical commit. The failure had been latent in
production for weeks, masked by data starvation in the same path.

Pins are exact now. The lesson is broader: a test that passes locally and fails in CI
on the same commit is an environment difference, and the environment is the bug.

Related: KPI scripts print status emoji, which raise `UnicodeEncodeError` under the
Windows console codepage **after** assertions pass — a passing suite reporting as
failed. `kpi/run_all.py` forces UTF-8 for child output. Always use the runner.

---

## 10. Process notes that earned their place

**Do not change an agreed design without asking.** Asked to fix mobile width and trim
a section, I also dropped a column, renamed metrics and moved lines. The product
owner's response — *"the msg gets worse each time you change it"* — was correct. Fix
what was asked. Propose the rest.

**Check the calendar before calling a flat series a defect.** 36 of 39 consecutive
XAU/USD readings were identical, which I reported as probable fallback abuse. They
were identical because the world gold market closes at the weekend, and I had sampled
"the last 40 readings" on a Saturday. Measured properly: XAU/USD repeats on 100% of
Saturday and Sunday readings and 0-3% of weekdays; USD/IRR repeats on 61-69% of
Thursday and Friday readings, the Iranian weekend. Neither is a defect.

The general form: **this system's inputs have trading calendars, and a frozen series
is the expected output of a closed market.** Before treating one as evidence of
anything, group by weekday. It costs one query.

**Do not generalise from one sample without saying so.** I recommended dropping a line
because two figures matched at 08:30, without noting that at 08:30 the last scheduled
run *is* the day's open and they must match. At 20:00 they diverge completely. If a
conclusion rests on one observation, say so in the same sentence.

**Verify before asserting, especially your own scratch work.** A preview built the
percentile window from positive magnitudes while reusing a formula written for the
signed premium, and reported 71% where the truth was 29% — inverted. The production
code was correct. The error was in the throwaway script used to review it, which is
exactly where nobody looks. Compute a cross-check by a second method and print both.

**A phase with zero production cases is IMPLEMENTED, not COMPLETE.** Recorded in
`PROJECT_ORCHESTRATION.md`. Green tests establish that code can work, not that it does.
