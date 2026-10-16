# Gold Premium Monitor — Project Memory

The system as it runs: what it is for, what it sends, how a run works, what its data means, what it
has measured, what is broken and the rules it is built by. The highest-authority document; the
machine-readable mirror is `.project_state.json`.

Rewritten on 2026-10-16 (`SP_D_HANDOFF.md` section 37.9; the audit's B6, section 36.4). The previous
file, the SP-A to SP-C history (indicator definitions, the PRE-SP-C phases, the C.14 research, the
SP-C changelog), is `archive/PROJECT_MEMORY_HISTORY.md`, unchanged. The sprint records stay where they
are: `SP_C_HANDOFF.md` (SP-C and the pre-SP-D hotfixes, closed) and `SP_D_HANDOFF.md` (SP-D, open).

---

## 1. Authority

**Reading order for a new session:**

```text
.project_state.json      machine-readable state: branch, tags, production, open items
→ PROJECT_MEMORY.md       this file
→ SP_D_HANDOFF.md         the current sprint: its sub-sprint table, then the latest sections
→ PROJECT_OPERATIONS.md   the runtime: scheduler, workflows, Cloudflare, the health check, the node
→ LESSONS_LEARNED.md      the defect patterns this project has met
→ skills/                 core-engineering → repository-onboarding → sprint-execution → the specialist
→ source, tests, KPI, sql
```

**When documents conflict:**
- this file wins over every other document;
- executable evidence (tests, KPIs, production database state) outranks any prose, this file included;
- a sprint handoff narrates and dates, and a later section supersedes an earlier one.

`DOCUMENTATION_INDEX.md` says which file owns what, and `CLAUDE.md` is the entry point for Claude Code.
The same order is stated there. Do not restate it in a fourth place.

## 2. Purpose and boundaries

A decision-support system for the Iranian 18K physical-gold market. The owner, 2026-10-16: "the core
goal of the project is to give information, and act as Decision Support System and provide Expert
System Judgements based on data, information and fact." **It is not a trading bot and executes
nothing.**

The reader's four questions, the frame for every surface (`SP_D_HANDOFF.md` 36.6, 38.1):

| Question | What the system can answer with evidence today |
|---|---|
| **where** to buy | the live platform prices and their spread |
| **when** | buy now rather than wait for a dip; the deep-discount zone as a lead |
| **how much** | gold or fixed income: the room's posture |
| **what risk** | the trend and its 50-day breaks, gold demand |

**Invariants**, enforced by code and KPIs:

```text
CHEAP ≠ BUY
VALUATION ≠ MOMENTUM
CANDIDATE DECISION ≠ FINAL DECISION
NEWS ≠ MARKET DATA
LLM ≠ MARKET CALCULATION
EVIDENCE PACKAGE ≠ DECISION
READ MODEL ≠ DECISION AUTHORITY
PREDICTION ≠ FACTS / EVIDENCE / INTERPRETATION / FEATURES
```

- **Ownership.** Collectors collect, calculators calculate, intelligence interprets, presentation
  formats, persistence stores. A message never computes a market fact.
- **Unknown over invented.** `UNKNOWN` and `INSUFFICIENT_DATA` are valid answers. On missing data: a
  safe deterministic fallback with degraded provenance if one exists, otherwise abstain; never
  extrapolate.
- **The LLM** may summarise, label and express uncertainty over validated inputs. It never computes
  a price, a premium or an indicator, never invents a level or a statistic, and never holds BUY/SELL
  authority.
- **Research informs design only.** No execution, no broker, no reinforcement learning, no model that
  rewrites its own weights from feedback.
- **Alerts.** `final_decision` is the sole BUY/SELL alert authority; a candidate never alerts. The
  deep-discount push and the room's trades are separate, documented pushes. This rule is under review
  (section 6).
- **Wording** (owner): "heavily discounted", never "cheap"; increased and decreased; every change says
  against what; one header per message.

## 3. What runs

Production is `main`, dispatched by cron-job.org and the Cloudflare worker with `ref: main`
(`PROJECT_OPERATIONS.md`). One workflow, `gold-monitor.yml`, has four modes:

| Mode | Trigger | What it does |
|---|---|---|
| UPDATE | `/Update` | collect, validate, the current discount and platforms; writes its reading as `user` |
| ANALYZE | cron-job.org, hourly 06:00-21:00 Tehran | the scheduled run (section 4); `SCHEDULED_RUN=true` |
| REPORT | `/Analyze` | reads the record, collects nothing; says the database is unreachable when it is |
| DIRECTION | `/Direction` | sends the stored panel, or computes it live from tgju when none can be read |

**What a reader receives:**

| Surface | When | Module | State on 2026-10-16 |
|---|---|---|---|
| UPDATE | on demand | `alerts/telegram_update_v1.py` | live; a locked layout |
| ANALYZE | on demand | `alerts/telegram_analyze.py` | live; honest when Neon is out of reach |
| Direction | panel computed at 06:00 and 13:00, sent on `/Direction` | `analysis/direction.py`, `alerts/telegram_direction.py` | v7 (SP-D 35.11) |
| BUY signal | when `final_decision` is BUY | `alerts/telegram_signal.py` | live; the confirmation holds every BUY while Neon is down |
| Deep-discount push | scheduled runs | `analysis/push_trigger.py` | **parked** by the owner until Neon returns ("it may mislead the user") |
| The room's trades | when the room trades | `alerts/telegram_paper.py` | live; the only PAPER account that pushes |
| The 21:00 report and chart | first run from 21:00 | `alerts/telegram_paper.py`, `alerts/chart.py` | live; support and resistance with the patterns (37.5); sent from tgju when Neon is out of reach (35.2) |
| Daily recap | — | `alerts/telegram_*`, `alerts/email_*` | **parked** 2026-10-15 (`config.email.send_daily_recap`) |

**Parked, not deleted** (owner, 2026-10-16: the Analysis Wing "is to be rethought, not retired"):
`config.analysis_wing` turns off the evidence package, interpretation, features and read model, the
C.14A candles and the C.14B forecasts. Nothing a reader sees reads them. The whole wing took 82% of a
run (4m46s of 5m50s on 10-12, SP-D 36.2). The snapshot's core and the outcome evaluations still run,
and the outcome backfill is now the longest stage (37.2). `true` brings a part back.

**Not in production:** the LLM member of the room, GDELT, broadcast to other readers (parked), the
Telegram-channel news reader (`collector/news/telegram_channels.py`, research only), the room alert at
3 of 8 (agreed, not built).

## 4. The scheduled run

`src/main.py`, in order:

1. **Flush the spool** (section 7) before the run takes its time.
2. **Collect**, each source isolated:
   - eleven platforms under one deadline;
   - world gold: gold-api.com, then Kitco's stream, then goldprice.org, under one 60-second deadline;
   - the dollar from bonbast.
3. **Validate** (`validation/data.py`). Sanity ranges, then the stale-quote rules: the source's own
   price time, a repeat, a jump, and Taline's 1% band. They act on that reading only; `CLAUDE.md` gives
   them in full.
4. **Store the observations** (`price_observations`): the representative price, and BUY and SELL rows
   for the two-sided platforms.
5. **Decide**:
   - fair value and the premium from the single cheapest platform;
   - the valuation leg, as a rank;
   - momentum, structure and the conflict matrix give the candidate;
   - the confirmation, then hysteresis, give `final_decision`.
6. **Persist** `market_snapshots`, `platform_prices` and `market_states`, or hold them in the spool.
7. **Then:**
   - news ingestion;
   - tgju's daily candles;
   - the room's inputs (tablokhani, etfbaz);
   - the Direction panel (06:00 and 13:00);
   - PAPER (trades, and at 21:00 the report);
   - the evening fallback;
   - the analysis snapshot's core and outcome evaluations;
   - the deep-discount push;
   - the record mirror's refresh (section 7).
8. **Send** the BUY or SELL alert if `final_decision` gives one.

A normal run took about 6 minutes before the wing was parked; the new time is measured once Neon is
back. The runner is pinned to `ubuntu-24.04`.

## 5. The data and what it means

**Platforms.** Eleven Iranian platforms, collected from GitHub's runner. Daric refuses the runner
(since 2026-10-03) and is read by the owner's phone. What each one's `price` means differs (SP-D
37.7):

| Platform | `price` | Both sides stored |
|---|---|---|
| Daric, Goldika | what a buyer pays | yes |
| Taline | between its two sides | yes, from 10-16 |
| Ayyareh | its published price; the fees give the sides | no: the representative chain reads it |
| Milli, Invi, WallGold | one price, side not published | no |
| MioGold, Parasteh, HoorGold, Eligold | a gallery's reference price, not a raw-gold price | no |

So "the discount" compares mixed kinds of number. That is known and kept, because changing what
`price` means would break every rank and level drawn from its history. A one-sided discount is to be
measured before any change.

**The quantities.**
- **Fair value:** world gold × the dollar × 0.75 / 31.1035.
- **The discount a reader sees:** the mean of the three cheapest platforms against fair value
  (`analysis/bubble_position.cheap_basis_price`).
- **The stored `premium_percent`:** from the single cheapest platform. The engine, outcomes and
  snapshots read this one, and the split is deliberate (`SP_C_HANDOFF.md` 15.1).
- **The deep-discount level:** one number for every surface, `deep_discount_threshold()` over the
  settled non-user pool. Never rounded before a comparison (`SP_C_HANDOFF.md` 24).
- **The representative price:** Milli, then Ayyareh, then WallGold, else UNKNOWN; first valid wins,
  with provenance kept.

**Time.** Stored in UTC, shown and grouped by day in Tehran time: `timeutil`, fixed UTC+3:30.
`datetime.now()` is banned in `src/`. Morning readings, before about 11:00 Tehran, can carry
yesterday's dollar (`SP_C_HANDOFF.md` 34.3).

**Daily series** (`market_daily_candles`, never mixed with platform prices):
- tgju: 18K from 2013, the dollar from 2011, world gold;
- tablokhani: TEDPIX, Afran's close;
- etfbaz, one reading a day: Tether, the dollar, melted gold, 18K, world gold, TEDPIX;
- the phone: TSETMC's gold-fund money flow, via `iran_node_readings`;
- `src/seed/`: the histories production cannot fetch, extended by these daily readings.

Read daily candles through `persistence/candle_cache.py`.

**News.** RSS feeds (`config.news.sources`), all read by GitHub's runner:
- international feeds and Google News queries;
- Donya-e-Eqtesad and Tejarat News;
- from 10-16, Tasnim's economy and politics feeds and cbi.ir's news (SP-D 37.13).

A keyword classifier records `relevance`, `impact` and an event type, never a gold direction (UNKNOWN
since 2026-09-21). While Neon is out of reach the items are held in the spool, each once. The labelling of a year of Telegram channels by an AI model
(Groq, free tier) is research: it is in `research/`, not production.

## 6. The decisions and their record

**The decision engine:**

```text
valuation rank → premium direction → momentum → structure → conflict matrix → candidate
→ confirmation → hysteresis (24 h, timed) → final_decision
```

- **Valuation** (`caluclator/valuation.classify_valuation`): a rank with a direction gate. CHEAP needs
  a low rank and a premium at or below the buy gate; EXPENSIVE a high rank and a premium at or above
  +3.0%, which no stored reading has reached (highest +0.75%). UNKNOWN below `MIN_OBSERVATIONS`.
- **Confirmation**: the second-cheapest platform heavily discounted on its own 30-day record, today's
  dollar and live world gold. It fails closed (`SP_C_HANDOFF.md` 37, 38).
- **Its record.** WAIT on 663 readings and BUY on 4 to 2026-10-13.
  - The "55.2% against always-WAIT, an edge of 0.0" once quoted was taken while a latch held every
    decision at WAIT. It scored a constant, not the engine (SP-C 16.1, SP-D 39.2).
- **Replayed on 08-04 to 10-04** (SP-D 39.3):
  - its BUY candidates did not pick better moments: the next 24 hours rose +0.64%, against +0.67% from
    any reading (28 episodes);
  - a reader who waited for its next BUY paid +2.0% on average.
- **Proposed:** a decision table built beside it, gated by the replay on the full record (SP-D 39.6).
  Moving the alert authority changes `CLAUDE.md`'s rule, so it waits for the owner's decision.

**Direction** (`analysis/direction.py`):
- the trend and its drivers;
- **buy now or wait**: waiting for a 3% dip cost more in 12 of 13 years, the one robust timing fact on
  record;
- support and resistance, each with how often lines that far away held for 10 days;
- WATCH: a break of the 50-day average, counted by separate breaks; the next month was weaker by 1 to 6
  points;
- GOLD DEMAND: the gold funds over 7 days against their usual (`analysis/gold_demand.py`).

Its 20-day forecasts resolve from early November.

**The room** (`analysis/room.py`): the PAPER front office's posture.
- **The posture:** ALL_GOLD, or SWING_OUT (40% of the grams into Afran fixed income).
- **Eight members and their weights:** brake 2.0, market state 1.5, fair gap 1.5, real dollar 1.5,
  dollar 20d 1.0, chartist 1.0, world gold 60d 0.5, money flow 0.5.
- **The vote:** it leaves at 60% of the weight with a view and comes back at 30%, reviewed every 10
  trading days, with the stock index as the sharp eye.
- **Replayed:** +5.0% to +9.0% median over holding per two years with money flow, +4.0% to +5.7%
  without, ahead in 83-100% of windows. 18 overlapping windows are about three independent periods.
- **PAPER** runs six accounts: the room and, beside it, the analyst, the quant, the cautious analyst,
  buy-and-hold, and one that follows `final_decision`.

**Chart patterns** (`caluclator/patterns.py`, SP-D 37.4-37.5):
- **What it reads:** a 3% ZigZag; sideways ranges and their breaks (flag, breakout, breakdown); tests
  of the 20-day EMA; double and triple tops and bottoms, head and shoulders, triangles, wedges.
- **What it prints:** each pattern with its record on 18K since 2014 (`RECORD`) against the chance from
  any day.
- **What the record shows:**
  - flags reached their target first in 14 of 19, against 45 in 100 from any day;
  - double bottoms 19 of 24, against 69;
  - the bearish patterns fail on 18K: double tops 3 of 12, against 33.

## 7. Database and Neon

Neon Postgres on the free plan:

```text
market_snapshots  platform_prices  market_states  price_observations  news_events
analysis_snapshots  outcome_evaluations  platform_candles  market_daily_candles
direction_snapshots  paper_accounts  paper_activity  iran_node_readings
system_events  market_hypotheses
```

- **The transfer cap.** The free plan allows **5 GB of outbound transfer a month**. Exceeding it
  suspended production from 2026-10-13 21:00 Tehran to 2026-11-01 (SP-D 34). A reader loads only the
  columns it uses (`get_analysis_snapshots(columns=...)`, enforced by `kpi_coherence.test_36`), and
  the health check watches the month-to-date figure (`PROJECT_OPERATIONS.md` 15).
- **The spool.** While Neon is out of reach, what a run cannot write waits in `record_spool.jsonl` in
  the Actions cache (`persistence/spool.py`, SP-D 35.4). Each scheduled run flushes it first. Held
  readings are re-checked against the stale-quote rules before they are written (37.1). News is held
  too, up to 16 MB of the spool's 20 (37.13).
- **The record mirror.** The last 61 days of `market_snapshots` and `platform_prices`, copied by each
  scheduled run that reaches Neon into `record_mirror.sqlite` (`persistence/mirror.py`, SP-D 37.12;
  0.88 MB). While Neon is out of reach the outage-sensitive readers use it, read-only:
  - the stale-quote history, the valuation rank and the confirmation;
  - UPDATE's context and baselines.

  A held reading is added to it, so the next run sees it. First filled on 11-01.
- **The outage, until Neon returns:**
  - the 21:00 chart comes from tgju;
  - `/Direction` is computed live;
  - ANALYZE says the database is unreachable;
  - the push is parked;
  - the phone keeps its own spool.
- **The phone** writes `iran_node_readings` as the role `iran_node`, which may only INSERT. Such a role
  is made with SQL, never through Neon's API or console, whose roles join `neon_superuser`
  (`PROJECT_OPERATIONS.md` 16).
- **Migrations.** `sql/neon_schema.sql` is the target schema; `sql/neon_migration_*.sql` change the
  live database. Any change goes: inspect production → incremental migration → a temporary Neon branch
  → the owner's authorization → production → verify → docs. Never apply the target schema to
  production. A phase that needs none records `NEON MIGRATION REQUIRED = NO`.

## 8. What the research has established

**Method** (the audit's test, SP-D 36):
- count independent episodes, not overlapping days;
- compare with a control drawn from every day;
- commit the rules before the run;
- show the sample size;
- judge on one era and test on another.

Built-ness and past effort count for nothing.

**Measured:**

| Finding | Evidence | Where |
|---|---|---|
| Buying now beats waiting for a 3% dip | 12 of 13 years | SP-D 1, 36.1 |
| The decision engine's BUYs do not pick better moments, and waiting for them cost +2.0% | 28 candidate episodes, +0.64% against +0.67% in 24 h; 40 days of waiting | 39.3 |
| The room's gain rests on its chartist and dollar 20d | with five members it falls to +0.3% to +1.4% | 36.1 |
| The money-flow member's edge came from the saffron fund | without it: 0 to +0.31 pp, from +0.67 to +1.42 | 36.2 |
| In turbulence, a rush of buyers precedes a further 5% fall about twice as often; big buyers precede a rise | four combinations of twelve agree in both eras: leads, not edges | 37.6 |
| The platforms do not catch up a jump in fair value | 63% of fair's move after 24 h, against 85% for all readings | 38.6 |
| The deep-discount zone gives a head start | +1.16% in 24 h against +0.53% (11 episodes) | 36.1, suggestive |
| The central bank's interventions met pressure, they did not reverse it | the dollar +1.70% over 3 days on 10 days against +0.55% | 37.11, 152 of 357 days labelled |
| Escalation news does not separate | +1.20% the next day on 22 of 108 days did not hold: +0.02% against +0.29% on 59 of 152 | 36.2, 37.11 |
| The AI model's own call on the dollar has no skill | its "down" days were followed by +1.20% over 3 days, its "up" days by +0.44% | 37.11 |
| Flags and double bottoms work on 18K; bearish patterns do not | section 6 | 37.4 |

**Proposed, for the owner's decision** (SP-D 38):
- **one advisor (C):** a daily brief that answers the four questions, each line with its evidence;
- **the Analysis Wing** rebuilt as the discount laboratory;
- **the decision engine** restructured.

The agreed order for B: money flow, then the Analysis Wing, the decision engine, the price sides and
the docs and tests, then C.

## 9. Defects index

Check here before reading a failure narrative in a handoff as live: the narratives read as current
until the sentence that says otherwise.

**Open:**

| Defect | Status | Reference |
|---|---|---|
| Neon suspended for transfer to 2026-11-01; the spool's write-back, the transfer per run and the phone's spool are to be checked that day | time-bound | SP-D 34, 35.4, 37.1 |
| The decision engine's BUYs do not pick better moments | owner's decision on 39.6 | SP-D 39.3 |
| Morning readings priced on yesterday's dollar; dollar freshness stored as always fresh | research first | `SP_C_HANDOFF.md` 34.3 |
| Daric refuses GitHub's runner | their side; the phone reads it | SP-D 29-31 |
| Taline's frozen copy is stored when it sits within its band and its usual position | open | SP-D 20, 29 |
| News dedup looks back 24 h while feeds keep items for days; Google News's " - Publisher" suffix defeats the title hash | open | `SP_C_HANDOFF.md` 33.3, 34.5 |
| `high_impact_count` reads `relevance` for values only `impact` holds (always 0) | open; parked with the evidence package | `SP_C_HANDOFF.md` 33.3 |
| The outcome backfill retries horizons that cannot complete for 7 days | open | health check 2026-10-03 |
| `AFRAN_LAST` dated one to two sessions late (tablokhani's `closing_1d_ago`) | small; with the next change to the room | SP-D 29 |
| `structure_state` DISCOUNT_DOMINANT on almost every row | measured, left alone; a rare-event detector | `SP_C_HANDOFF.md` 28, 34.6 |
| The analysis snapshot's support and resistance are labelled by extremum type | unshown; readers get Direction's levels | `SP_C_HANDOFF.md` 41.1 |
| Ayyareh and Eligold quote the same price in about 60% of readings | watch (owner: keep both) | `SP_C_HANDOFF.md` 44 |
| The news LLM classification path has never run in production | open | `SP_C_HANDOFF.md` 27.5 |
| 92 `datetime.utcnow()` calls, deprecated in Python 3.12 | open; the clean-up | SP-D 36.3 |

**Closed, latest first** (the full SP-A to SP-C list is in the archived history):

| Defect | Fixed | Reference |
|---|---|---|
| `kpi_coherence.test_27` could not fail; the unit tests ran nowhere and five had rotted | 2026-10-16 | SP-D 37.8 |
| Held readings would skip the stale-quote rules on write-back | 2026-10-16 | SP-D 37.1 |
| `SignalState` and `HistoricalQuery` defaulted to the machine clock; `rss.py`'s broken copy | 2026-10-16 | SP-D 37.3 |
| Only Goldika's two sides were stored | 2026-10-16 | SP-D 37.7 |
| Every run read whole snapshot documents: about 450 MB a day of transfer | 2026-10-14 | SP-D 34 |
| `MAX_WORLD_GOLD` $5,000 with gold near $4,150 | 2026-10-06 ($20,000) | SP-D 30 |
| PAPER's venue label too long for its column; statsmodels broken by new scipy and pandas | 2026-10-05 | SP-D 28 |
| Stale CDN copies (Goldika's from 09-13) contaminated readings, pushes and regimes | 2026-10-02 and 10-03 | `SP_C_HANDOFF.md` 44, 45 |
| The first live BUY rested on one stale quote | 2026-09-29 | `SP_C_HANDOFF.md` 37, 38 |
| The Kitco stream hung runs to the job timeout | 2026-09-30 | `SP_C_HANDOFF.md` 42 |
| `valuation_state` CHEAP and `regime_state` PANIC on every row; `final_decision` latched to WAIT | 2026-09-18 to 09-21 | `SP_C_HANDOFF.md` 16, 26 |
| `Deep discount` meant two numbers on two surfaces | 2026-09-21 | `SP_C_HANDOFF.md` 24 |

## 10. How work is done

**The loop:**

```text
inspect → define the change surface → implement minimally → targeted test → regression
(python tests/run_all.py, python kpi/run_all.py, compileall) → Neon verification when it applies
→ diff review → docs and .project_state.json → commit
```

- **Talk, preview, lock, wire, document.** R&D and a full preview come before code that changes what a
  reader sees. An agreed layout or framework is never changed without the owner's permission.
- **Production liveness.** A component that has processed no real production case is IMPLEMENTED, not
  COMPLETE: a KPI passes on fixtures and cannot see a path the runtime never reaches (lesson 4).
- **A check must be seen to fail.** A test that has never rejected anything is quoted as evidence and
  is none. Feed it a known offender (lesson 10).
- **Measure the input as well as the output** before trusting a categorical column: `GROUP BY` both
  (lessons 1-3, 15, 16).
- **Cross-module assertions** belong in `kpi_coherence`. Its `ACCEPTED` register lists the deliberate
  divergences, and an entry whose divergence is fixed fails the suite.
- **Branches.**
  - `main` is production.
  - The sprint is SP-D, run in sub-sprints with one branch each (now `sp-de`).
  - A batch reaches SP-D and `main` by fast-forward, with a safe tag on `main` first (`v1.22safe` is
    the latest).
  - The owner authorized on 2026-10-15 that approved work is tagged and pushed without asking again.
  - A production defect is fixed on a short branch cut from `main`.
- **Documents.**
  - Update the file that owns the fact (`DOCUMENTATION_INDEX.md`). A sprint's record goes in its
    handoff.
  - This file changes when what runs changes.
  - No new top-level status or architecture document.
  - What is superseded goes to `archive/`, unchanged.
- **Zero spending.** Free tiers only: Neon, GitHub Actions, Groq, Cloudflare, cron-job.org.

## 11. Where things stand

`.project_state.json` holds the live position, and `SP_D_HANDOFF.md`'s sub-sprint table lists each
batch with its tag.

On 2026-10-16:
- **Branches:** `main` and SP-D at SP-De's B6 batch and the record mirror (v1.21safe before it).
- **Neon:** suspended to 11-01.
- **Tests:** unit tests 18 of 18 files, KPI suite 30 of 30, both run in CI.
- **Next, in the agreed order of B:**
  - the decision engine (B3) and ANALYZE (B5), after the owner's decisions;
  - the news labels (B7);
  - the money flow in turbulence;
  - then the advisor (C).
- **On 11-01:** the spool's write-back, Neon's transfer per run, and the phone's spool.
