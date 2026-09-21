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

**A timeout that cannot interrupt is not a timeout.** `collector/iran` documented a
20-second global ceiling and had none. `wait()` was capped correctly, but
`future.cancel()` only cancels a future that has not *started*, and the
`ThreadPoolExecutor` context manager then called `shutdown(wait=True)` — so the capped
wait was followed immediately by an uncapped one. A hung collector took the entire run
with it.

Two things to check on any timeout in this codebase, not just its presence:

- **can the mechanism actually interrupt the work?** Cancelling a queued task is not
  cancelling a running one. Nothing in Python kills a running thread.
- **what happens after the timeout fires?** A bounded wait followed by an unbounded
  join is unbounded.

And a specific trap: `requests`' `timeout=` bounds connect and read, **not DNS
resolution**. A degraded network produces an unbounded thread despite a correct-looking
timeout argument. That is what made this one fire in production.

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

The same codepage then bit the runner itself. It forced UTF-8 on the child but printed
the captured failure report through the parent console, so the first failing suite
containing an emoji raised `UnicodeEncodeError` **after** the summary line: the run
named the file that failed and died before saying why. Finding out required stashing
the change and re-running. Diagnostics written on a failure path have to survive the
conditions of that failure; the report now goes to `sys.stdout.buffer` as bytes.

---

## 10. Process notes that earned their place

**A bare `except` will hide your own missing import.** `source_label` returned
`"unknown"` for every Google News feed. The cause was a missing `import re`; the
handler was `except Exception: return "unknown"`, so a `NameError` became a plausible
default and the function looked like it worked. It was found only because the output
was inspected by eye.

This is the silent-degradation pattern the same commit was written to remove, produced
while removing it. A fallback that cannot distinguish "this input has no identity" from
"this code is broken" is a constant with extra steps. **Log what you caught**, even in
a helper that is allowed to degrade.

**Collecting the wrong thing beats analysing it badly.** `EVENT_STRESS` had never
fired in the system's life, which was filed as a classifier problem needing an LLM. The
feed was a national general-news firehose: 1,987 items in seven days, zero relevant,
headlines about opium seizures and basketball. No classifier extracts market signal
from that.

**Check what a pipeline is being fed before improving how it thinks.** The fix was a
config change and cost nothing; the LLM work it displaced would have been weeks and
would have improved nothing.

**A preference applied before a filter becomes a veto.**
`_get_nearest_recorded_premium` preferred scheduled readings, applied that preference
to the whole candidate window, and only then picked the nearest row. A scheduled
reading an hour away shadowed an unscheduled one four minutes away, the documented
fallback never executed, and the function returned nothing although a usable row was
sitting right there.

The preference was correct. Its position in the pipeline was not.

**Order matters in a selection chain: filter for validity, rank for quality,
prefer as a tie-break.** A preference promoted to a filter silently discards data it
was never meant to reject -- and the symptom is absence, which nothing alerts on.

**The message has a fixed vocabulary; a synonym is a defect, not a style choice.**
Three times in one sprint I introduced a word the product owner had already replaced:
`widening` after we settled on increased/decreased, `dearer` after we settled on
expensive, `grew` after both. Each time the reasoning felt local and each time it
reintroduced the two-vocabulary problem the message had just been cleaned of.

Before writing any user-facing line, check the words already in use for that concept.
A near-synonym reads as a new concept to someone who did not write it.

**An episode cannot span a period nobody observed.** Deep-zone duration first
measured 15 hours. Collection runs 06:00 to 21:00 local, so the series carries a
nightly nine-hour hole: 66 of 264 intervals exceed three hours against a median
spacing of one. Two readings either side of a night were joining into a single
episode, and the reported duration was mostly time nobody looked at. Broken across
gaps, the same zone measures 2 hours.

**Before reporting any duration, frequency or streak, check the sampling interval of
the series it is measured on.** A gap is not a continuation, and the resulting number
is wrong in the direction that flatters it.

**A check that cannot fail is not a check.** `node --check` was run against the
Cloudflare worker repeatedly during SP-C.12 and reported success every time. It
cannot parse a file containing `export` as CommonJS, falls back, and returns 0
without validating. An unterminated string sat on line 94 through all of it, and the
worker would have been broken the moment it was pasted into production.

Verified by construction: `printf 'export default { a: 1 };
const x = "abc
def";
'`
passes `node --check` and fails `node --check` on the same content named `.mjs`.

**Before trusting a verification tool, make it fail on purpose.** A check that has
never been seen to reject anything is indistinguishable from no check, and it is
worse than none because it is quoted as evidence.

**Interesting is not actionable.** An investigation into market sessions produced a
genuinely novel finding -- Iran's trading calendar and the world gold calendar are
almost exactly out of phase, so the two inputs driving fair value take turns. I
immediately began designing a message line around it. The product owner asked the
question I had skipped: does this improve decision quality, or is it just wording?

It was just wording. No number changed. The correction it implied was smaller than the
noise it sat in, and the underlying data was already correct.

**The test to apply before proposing any addition: name the number that changes.** If
none does, the finding belongs in documentation, not in the product. That matters
particularly here, where a week had already been spent removing lines from the same
message.

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


---

## 11. One word, two definitions

SP-C.5 hunted the opposite problem: two words for one quantity (`widening`, `deepening`
and `growing` all meaning a discount increasing). It did not look for one word over two
quantities, and that is what shipped.

`Deep discount` meant the 40th percentile of the signed gap in UPDATE and the 85th of
the size in ANALYZE and the push. On 2026-09-21 that was 3.29% and 3.70%, printed in
two messages a reader is expected to read together. At 3.40% the system said deep, said
not deep, and sent nothing.

It survived review because each surface was checked against the market and against its
own module, and neither was checked against the other. Nothing in the test suite
compared two surfaces' vocabulary, and nothing does so by accident — you have to decide
to write that assertion.

**The rule.** The number a reader is shown is the number the system acts on. A second
surface that needs the same concept calls the same function; it does not declare a
constant of the same value. Three equal constants in three files is not one definition,
it is three definitions that currently agree — and `bubble_position`, `analyze_report`
and `push_trigger` held exactly that for one day.

Two corollaries found while fixing it:

- **A shared rank over unshared samples is still two numbers.** The ranking pool and
  the threshold pool differed by a gate due to open seven days later, at which point
  p85 would have read 3.70% and 3.64%. The pool is part of the definition.
- **A threshold compared against readings must not be rounded.** Gaps land on values
  like `8.999999999999996`; rounding the level to `9.0` lifted it above the very
  readings it was drawn from, and a zone containing eight of them measured zero
  episodes. Round at render, never before a comparison.

---

## 12. A magnitude is not a direction

`evaluate_push` compared `abs(current_gap)` against a threshold, so a premium of the
same size as a deep discount would have fired a message headed DEEP DISCOUNT on a
market trading above fair value. UPDATE carried the mirror image through a signed
threshold whose sign nothing enforced.

Latent, never fired: all 437 readings on record are discounts. Latent is the point.
The record contained no counterexample, so no test and no production run could expose
it, and the code read as correct because in this market it was.

**The rule.** Taking an absolute value discards a fact. When the label on the output
asserts a direction, assert the direction on the input too — and check whether the
sample simply never contained the other case.

---

## 13. Fixing the instance and recording the class

The pattern behind most of this file.

A defect is found in one place. It gets fixed there, a KPI is written for that place,
and the defect index records the *class* as closed. Nothing in the process ever asks
where else this shape exists -- and the document that would raise the question is the
document just written by the person who did not ask it.

Proven in this repo. `PROJECT_MEMORY.md` recorded `valuation_state read CHEAP on every
reading (fixed threshold)` as resolved on 2026-09-15. SP-C.2 had replaced the fixed
threshold **for the reader**. The column the decision engine reads was untouched and
went on writing CHEAP every hour -- 364 of 364 rows, including rows written six days
after the index said it was fixed. The percentile replacement was computed, persisted
to `valuation_context_json`, and read by nothing.

Two conditions kept it invisible:

- **Correctness was checked inside a boundary.** Each module against the market, each
  surface against its own tests. Never module against module. The contradiction lived
  between two individually correct things, and `valuation_state=CHEAP` beside
  `band=EXPENSIVE` sat in the same database row for weeks.
- **The record hides what the record has never contained.** `CHEAP` looks correct
  because the market really has been cheap. The `-1.5` threshold sits 0.02 pp outside
  the entire observed range of 438 readings, so it has never been crossed and never
  been tested by reality. A degenerate classifier and a correct one are
  indistinguishable until the world changes.

**The rules.**

1. `GROUP BY` in production before writing "fixed" anywhere. The repo already mandates
   this for classifiers; it was not applied to the defect index itself. The audit that
   falsified the row above took four minutes.
2. A defect index entry names the **class** and lists **every** instance, open ones
   included. "Fixed in SP-C.2" becomes "instance 1 fixed, instances 2 and 3 open".
3. Cross-module assertions are their own KPI file, not something remembered after
   someone else catches one. `kpi/kpi_coherence.py` exists for this, and its register
   of accepted divergences fails the suite when an entry is silently fixed -- a
   register that can go stale is a second copy of the problem it prevents.

What actually caught the last three of these: a human reading the real outputs side by
side. Not review, not the suite. That is where the signal is, and it is cheap to look.


---

## 14. The safe-looking fix that was the dangerous one

`valuation_state` had been CHEAP on 364 of 364 rows because its threshold sat outside
the observed range. The percentile band that should replace it already existed,
already varied, and was already being computed on every run. Swapping one for the
other looked like a two-line change.

It would have started issuing SELL on a market trading below fair value.

A percentile-EXPENSIVE reading means *less discounted than usual*. It does not mean
the market is above fair value. The conflict matrix turns `EXPENSIVE + WEAKENING` into
`SELL`, so the ranked band — correct as a description of position — becomes a false
claim about direction the moment it is read by something that acts on direction.

Nothing in the band was wrong. Nothing in the matrix was wrong. The defect would have
been created entirely by connecting them, and it would have been created by the change
that fixed a real, measured, well-documented bug.

**The rules.**

1. **A value means what its producer measured, not what its consumer assumes.** Before
   wiring an existing quantity into a new consumer, state in one sentence what it
   asserts, and check that against what the consumer will do with it. "Rank within the
   window" and "above fair value" are different sentences.
2. **Check the fix for the failure mode of the thing it replaces.** The old leg could
   never say EXPENSIVE, so SELL had never fired and no test, no KPI and no production
   row covered that path. The replacement made a dead branch live, and a dead branch
   going live is a new feature with no history behind it.
3. **Carry the direction with the label.** Same rule as section 12, applied one layer
   up: `CHEAP` and `EXPENSIVE` now each require the reading to be on the side of fair
   value the word claims. The gate never opens on the record — every reading is a
   discount — and that is the correct answer, not a dead bound to be tidied away.

The general shape: the most dangerous change is not the one that looks risky. It is
the obviously-correct one that removes a constraint nobody realised was load-bearing,
because the constraint was an accident.


---

## 15. A constant that cannot vary is not the same defect as a stale bound

Two classifiers in this system emitted one value for months. They look identical in a
`GROUP BY` and they need opposite fixes.

**`valuation_state`** was `CHEAP` on 364 of 364 rows because its threshold sat 0.02 pp
outside the observed range. The underlying quantity — the premium — varied from
−8.19% to −1.52%. The bound was stale; a rank over that quantity separated the record
cleanly. Fixed in SP-C.15.

**`structure_state`** is `DISCOUNT_DOMINANT` on 365 of 367 rows because it classifies
on the share of platforms trading below fair value, and every reading on record is a
discount. That share is exactly 1.00 on 345 of 367 rows. **A rank over it would be
just as constant**, because a percentile of a point mass is the point mass. No bound
and no threshold can fix this: the measure itself asks a question whose answer is
fixed by the shape of the market.

The distinguishing test takes one query. Do not look at the *output* of the
classifier, look at the **quantity it classifies**:

```sql
SELECT <the input quantity>, COUNT(*) FROM ... GROUP BY 1;
```

- Input varies, output does not → the bound is stale. Replace it with a rank.
- Input does not vary → the measure is wrong. Changing the bound achieves nothing,
  and replacing it with a rank achieves nothing while *looking* like a fix, which is
  worse.

The second case is the dangerous one, because the obvious remedy is the one that has
worked three times already and it will appear to work here too: a percentile is
always computable, always produces a number, and gives no sign that the number is
meaningless.

There is usually something informative nearby that is being ignored. In the same rows
that made `structure_state` constant, platform spread runs 0.73% to 6.86% of fair
price with a median of 2.02%. Whether it predicts anything is untested — the point is
only that it moves, and the thing being measured does not.

**And a third possibility, which is neither.** After SP-C.15 the `EXPENSIVE` branch of
the valuation leg can never fire, because the market has never traded above fair
value. That is not a defect at all: the classifier is answering correctly about a case
the world has not yet produced. Section 13 has the rule — a constant output is only a
defect when the record contained the other case and the classifier missed it. Check
the record before reaching for a fix, and check the input before choosing which fix.
