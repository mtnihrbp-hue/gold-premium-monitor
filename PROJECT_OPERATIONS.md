# Gold Premium Monitor — Operational Control Plane

This document records the runtime control plane around the application. It is distinct from `PROJECT_MEMORY.md` (architecture/state), `PROJECT_ORCHESTRATION.md` (continuity), `C14_HANDOFF.md` (C.14 implementation contract), and `RESEARCH_ADOPTION.md` (research adoption/defer decisions).

## 1. Two frontend wings

### Live Wing

```text
Telegram /Update
   ↓
Cloudflare interconnection
   ↓
GitHub execution path
   ↓
collect → validate → calculate
   ↓
current deterministic state
   ↓
Telegram response
```

The Live Wing is user-triggered and current. It does not require cron scheduling.

### Analysis Wing

```text
cron-job.org
   ↓
external protected trigger
   ↓
GitHub Actions
   ↓
Analysis execution
   ↓
canonical observations
   ↓
analysis_snapshots
   ↓
outcome_evaluations
   ↓
evidence / interpretation / features
   ↓
read model / consumer
   ↓
historical dataset
   ↓
C.14A candles
   ↓
C.14B forecast
   ↓
C.14C forecast resolution / human review / closed-loop audit
```

The Analysis Wing is scheduled and independent of the number of Telegram users.

Human forecast review is collected inside the Analysis Wing Telegram experience. It is not a third frontend wing.

## 2. External scheduler policy

The intended scheduler is `cron-job.org`, not GitHub's internal `schedule` event.

```text
https://console.cron-job.org/jobs/8179679
Job ID: 8179679
```

The external scheduler exists so schedule control is outside GitHub Actions and can be inspected/manually operated independently.

GitHub Actions should retain a manual trigger for testing. The production Analysis Wing schedule should stop depending on GitHub's internal schedule only after the external trigger is verified end-to-end.

Current legacy internal GitHub schedule:

```text
30 14 * * * UTC
```

This is not the final production scheduling policy.

## 3. Intended Analysis cadence

```text
Timezone: Asia/Tehran
Start: 08:00
End: 21:00 exclusive
Interval: 30 minutes
```

Expected windows:

```text
08:00
08:30
09:00
...
20:30
```

The application scheduler remains authoritative for whether an analysis window is valid.

## 4. Analysis guardrails

```text
scheduled run
→ deterministic source_run_id
→ idempotent execution
→ duplicate trigger protection
→ analysis snapshot
```

Manual `/Update` remains independent from scheduled Analysis runs.

### World-gold / XAUUSD calendar guardrail

The historical discussion included the remembered wording:

```text
skip world-gold call on Saturday and Monday
```

This remains UNVERIFIED and must not be encoded as a production rule until the actual source calendar is confirmed.

Safe generic rule:

```text
source unavailable / market closed
    ↓
do not fabricate XAUUSD
    ↓
persist data-quality state
    ↓
allow independent valid sources to continue
```

## 5. Cloudflare role

Cloudflare is an interconnection/control layer, not an analytical engine.

```text
Telegram request
    ↓
Cloudflare Worker / secure gateway
    ↓
validated command or trigger
    ↓
GitHub execution endpoint
```

Potential scheduled path:

```text
cron-job.org
    ↓
Cloudflare Worker
    ↓
GitHub Actions
    ↓
Analysis Wing
```

Cloudflare must not calculate gold price, premium, regime, features, or forecast.

Current status:

```text
Cloudflare architecture = documented
Cloudflare live control = NOT YET CONNECTED IN THIS CHAT
```

## 6. Telegram analytical surface

C.13 established these analytical commands:

```text
/Analysis
/Technical
/History
/News
/Health
```

The broader two-wing user workflow is:

```text
/Update
→ live market state

/Analyze
→ evidence / interpretation / market structure / technical context

/Forecast
→ probabilistic directional forecast when enabled
```

`/Forecast` remains gated until forecast-readiness criteria are satisfied.

## 7. Forecast review and human feedback

The user should not fill a questionnaire.

After a forecast matures, a later `/Forecast` request may surface a compact review of the previous forecast.

Conceptual lifecycle:

```text
GENERATED
→ PENDING
→ ELIGIBLE_FOR_REVIEW
→ OBJECTIVELY_EVALUATED
→ USER_REVIEWED (optional)
```

The system first computes objective outcome quality from actual observations.

Human review is separate meta-data measuring perceived usefulness/timing/direction quality.

Human feedback must not directly update model weights or replace objective labels.

## 8. Fail-safe data policy

Global rule:

```text
MISSING
 ↓
safe deterministic fallback?
 ├─ YES → fallback + degraded provenance
 └─ NO  → INSUFFICIENT_DATA / ABSTAIN
```

Never silently extrapolate absent market facts.

This applies to prices, candles, features, outcomes, and forecast inputs.

## 9. C.14 operational scope

C.14 is split:

```text
PRE-SP-C.14A
Candle & Market-Structure Data Infrastructure

PRE-SP-C.14B
Forecast Features, Baselines, Evaluation & Forecast Engine

PRE-SP-C.14C
Forecast Resolution, Human Review & Closed-Loop Audit
```

C.14A is now VERIFIED COMPLETE.

C.14B must not begin until the C.14A gate is closed and documented.

## 10. C.14A verified state

C.14A establishes persistent deterministic 30-minute candles from canonical point observations.

Verified:

```text
KPI: 26/26 PASS
compileall: PASS locally
live smoke: PASS
Neon schema: APPLIED_AND_VERIFIED_IN_PRODUCTION
```

The latest live smoke created:

```text
Analysis snapshot 5
9 platform candles saved
Telegram delivery PASS
```

The live smoke discarded two unavailable sources:

```text
Invi — timeout
Daric — timeout
```

Nine valid Iranian gold sources remained, so the run completed normally.

The GitHub Actions compileall stage was cancelled after the source compilation output had completed; this is recorded as `CANCELLED`, not a source compile failure.

## 11. Candle semantics

Initial canonical timeframe:

```text
30m
```

For derived candles from point observations:

```text
OPEN  = first valid observation
HIGH  = maximum valid observation
LOW   = minimum valid observation
CLOSE = last valid observation
```

No interpolation, no forward-fill, no future observations.

For sources with explicit BUY/SELL quotes, preserve separate sides.

Goldika exposes explicit buy/sell quotes.

Ayyareh exposes `goldPrice` plus platform margin/wage fields. The existing collector contract is authoritative for how side estimates are derived; raw values and derived side values remain separate.

C.14A backfills existing `price_observations` where coverage exists, then continues forward. Historical reconstruction uses explicit historical bounds; normal runtime candle construction remains bounded to the recent observation window.

Unless a platform explicitly supplies official OHLC, the provenance identifies candles as derived from point observations.

## 12. Forecast readiness gate

Forecast target:

```text
UP
NEUTRAL
DOWN
```

C.5 mapping:

```text
UP → UP
FLAT → NEUTRAL
DOWN → DOWN
INSUFFICIENT_DATA → INSUFFICIENT_DATA
```

Also allow:

```text
ABSTAIN
```

Minimum production-readiness evidence:

```text
sustained analysis snapshots
+
sustained outcome evaluations
+
walk-forward evaluation
+
leakage audit
+
baseline comparison
+
probability calibration
+
abstention / insufficient-data behavior
+
no direct BUY/SELL authority
```

Current forecast status:

```text
NOT READY FOR DEPLOYMENT
```

## 13. C.13 completion state

```text
PRE-SP-C.13
KPI: 26/26 PASS
compileall: PASS
live smoke: PASS
analysis snapshot creation: PASS
Telegram delivery: PASS
Neon C.13 reconciliation: COMPLETE
```

## 14. Operational truth rule

For a new conversation:

```text
cron-job.org current configuration
↓
Cloudflare connection / Worker state
↓
GitHub Actions workflow trigger state
↓
SP-B source code
↓
Neon production row counts/schema
↓
Telegram command behavior
```

Document every resulting operational state change.


---

## Branch ref control plane

Three things decide which version of the system runs, and they are configured in
three different places. They must be changed together.

| trigger | where configured | carries | current |
|---|---|---|---|
| Telegram `/Update`, `/Analyze` | Cloudflare worker, hard-coded at `src/worker/telegram-trigger.js:135` (twice) | `{"ref": "..."}`, plus `inputs.mode` for `/Analyze` | `main` (since 2026-09-28) |
| hourly Analyze | cron-job.org job 8179679 request body | `{"ref": "...", "inputs": {"mode": "analyze"}}` | `main` (since 2026-09-28) |
| legacy daily schedule | `gold-monitor.yml` `on.schedule` | **default branch only** | **removed 2026-09-20**, see below |

`workflow_dispatch` runs the workflow file **and the application code** from `ref`.
A mismatch does not fail — it silently answers with a different version of the system.
That is exactly what happened between 2026-09-15 and 2026-09-20: cron-job.org pointed
at `SP-C` and the worker at `main`, so scheduled runs produced the current message
format while `/Update` produced the previous one, from the same bot.

The repository copy of the worker is `src/worker/telegram-trigger.js`. It is not
executed from here. Edit it there first and paste into Cloudflare, so the two do not
drift — they had drifted a full generation before 2026-09-20.

### Wings across one workflow file

The worker sends no inputs. `gold-monitor.yml` declares `mode` with a default of
`update`, so a user command runs with `SCHEDULED_RUN=false` on the Live Wing. Only
cron-job.org sends `inputs.mode = "analyze"`, which sets `SCHEDULED_RUN=true` and runs
the Analysis Wing. This is the mechanism that keeps the two wings separate.

### Legacy GitHub native schedule — REMOVED 2026-09-20

`on.schedule: cron "30 14 * * *"` was removed from `main` in `c1799fe` and mirrored
on `SP-C` so the merge cannot reintroduce it. A comment stands in its place in the
workflow file explaining why.

GitHub only runs `schedule` events on the **default branch**, so it fired `main`'s
workflow with `main`'s code against production Neon once a day, regardless of where
development was happening. `main` carries none of this sprint's fixes, so the
2026-09-19 run was cancelled by the job timeout after the unbounded collector
subprocess stalled — writing partial data before it died. It also collided with the
cron-job.org run at the same minute.

`workflow_dispatch` is the only trigger now. The Telegram worker and cron-job.org
both use it and were unaffected.

The `SCHEDULED_RUN` and `run-name` expressions still test
`github.event_name == 'schedule'`. That arm is now unreachable and is kept as a
defensive condition rather than deleted, so re-adding a schedule would still route to
the Analyze wing rather than silently running UPDATE.

### Cache scope

`state.json` is persisted through `actions/cache@v4`. GitHub scopes caches per
branch, with the default branch readable as a fallback. While `/Update` ran on `main`
and the schedule on `SP-C`, the two kept **separate** `last_alert` histories, which is
the state the hysteresis cooldown reads. Pointing both at the same ref unifies them.

Since the repoint of 2026-09-28 both triggers use `main`. `main` had no state cache
left, because caches unused for 7 days are evicted, so its first runs started from a
fresh `state.json`. The expected visible effect is one extra daily recap on the first
scheduled run on `main`, at 15:00 Tehran on 2026-09-28. SP-C's caches remain, but `main` cannot read another branch's caches,
by GitHub's design.

### Job timeouts and log access (2026-09-27)

`gold-monitor.yml` kills a run at 20 minutes. A normal scheduled Execute step takes
268-440 s. Three runs have hit the limit since the last code change (2026-09-24
13:51Z, 2026-09-25 08:30Z and 15:30Z). All three stopped before the first database
write, so there were no partial rows to clean up. Diagnosed on 2026-09-27: when
gold-api.com fails, the Kitco fallback reads an event stream that never ends, and the
run hangs until it is killed. The fix is queued (`SP_C_HANDOFF.md` section 33.2).

When a run is cancelled:

1. `gh run view <id> --json jobs` shows which step died (`gh` lives in
   `C:\Program Files\GitHub CLI`, not on the Bash PATH).
2. Check the window for partial rows in `price_observations`, `market_snapshots`,
   `market_states` and `analysis_snapshots`.
3. The job log (`gh run view <id> --log`) is **not reachable from the workstation**
   directly. Log storage times out at the TLS handshake, so fetch it through the
   Psiphon local proxy. Its ports change on every restart, so find them rather than
   looking for a saved value:

   ```powershell
   Get-NetTCPConnection -State Listen | Where-Object { $_.LocalAddress -eq '127.0.0.1' } |
     ForEach-Object { '{0} {1}' -f $_.LocalPort, (Get-Process -Id $_.OwningProcess).ProcessName } |
     Select-String psiphon
   ```

   `psiphon-tunnel-core` listens on a pair. On 2026-09-27 the higher one was the HTTP
   proxy (52692) and the lower one answered with EOF. Then run
   `HTTPS_PROXY=http://127.0.0.1:<port> gh run view <id> -R mtnihrbp-hue/gold-premium-monitor --log`
   (`-R` is needed when not inside the repo). The last `World Gold` or platform line
   printed names the call that was still running.

## 15. The routine health check (2026-10-05)

Run it at the start of a working session, and after any merge. Report every time in
Tehran time. Read-only throughout: no query below writes.

1. **Runs.** `gh run list -R mtnihrbp-hue/gold-premium-monitor --limit 60` since the last
   check: one ANALYZE per hour 06:00-21:00 Tehran, each `success`, normally 5-10 minutes;
   the owner's UPDATE / DIRECTION / REPORT dispatches in between. A missing hour is
   cron-job.org; a failure or a 20-minute kill follows "When a run is cancelled" above.
   Every run's branch is `main`: that verifies cron-job.org (ANALYZE) and the worker
   (UPDATE / DIRECTION) without their consoles.
2. **Freshness** (Neon, production): rows and latest time in the last 24 hours for
   `market_snapshots`, `analysis_snapshots`, `market_states`, `outcome_evaluations`,
   `price_observations`, `platform_prices`, `news_events`, `direction_snapshots`,
   `market_daily_candles`. Expected: one market snapshot, one market state and one
   analysis snapshot per scheduled run (plus one snapshot and state per UPDATE), about 3
   outcomes per run, two Direction panels a day (06:00 and 13:00 slots).
3. **Platforms.** `platform_prices` per `platform_name`, last 24 and 72 hours. Eleven
   platforms; fewer readings than runs means a failure or a discard. Then the **stored**
   prices side by side, reading by reading: a platform that holds one price for three
   hours or more while the others move is a frozen copy that passed every rule (Taline,
   2026-10-06 09:01-14:01, `SP_D_HANDOFF.md` section 29).
4. **Why a platform is missing.** The run log through the Psiphon HTTP proxy (above):
   `Discarded <platform>: <reason>` per run. Reasons on record: Daric `403` (its side,
   refusing GitHub's runner), `stale, priced ... ago` (the source's own time), `stale copy
   suspected, -x% from the other platforms' median` (Taline's 1% band), the repeat and
   jump rules. A price that repeats over readings while the others move is a frozen copy
   from the runner's side (CLAUDE.md, stale platform quotes).
5. **Decisions.** `market_states` of the last 24 hours: valuation, momentum, premium
   direction, structure, candidate and final decision, reason. Every BUY or SELL
   candidate: did the confirmation hold it, and was the hold right? Then the degenerate
   check: `SELECT final_decision, COUNT(*) FROM market_states GROUP BY 1` and the same for
   any categorical column reported; `structure_state` is a registered constant.
6. **Daily candles.** `market_daily_candles` per `instrument`: 18K and the dollar to
   yesterday's Tehran day, world gold to its last weekday.
7. **PAPER** (once merged): one REPORT row a day at 21:00, at most two TRADE rows a day
   per account, an EVAL row per run for each evaluated account.
8. **The Iran node** (from 2026-10-07): `iran_node_readings` per `node` and `status`, last
   24 hours. The phone reads every 15 minutes, so about 96 rows a day; a gap is the phone
   (asleep, off Wi-Fi, Termux stopped). In the run log, `Daric: from the Iran node (...)`
   when the runner was refused and the node supplied the quote.
9. **Verdict** in one line, the open defects named, then the record in the sprint's
   handoff.

**Reaching production from the workstation** (2026-10-07). The claude.ai Neon connector
does not survive a new session. The standing route is Neon's CLI, signed in once in the
owner's browser:

```bash
NODE_USE_ENV_PROXY=1 npx neonctl auth                     # Neon's sign-in refuses Iranian addresses
NODE_USE_ENV_PROXY=1 npx neonctl connection-string production --project-id wispy-glade-92753836 --pooled
```

The connection string lives in `~/.gpm_neon_url`, outside the repository and never
printed; checks open it read-only (`psycopg2`, `set_session(readonly=True)`). The Postgres
endpoint itself answers the workstation directly; only the CLI's sign-in and API need the
proxy.

## 16. The Iran-side node (2026-10-06)

The owner's phone in Iran (Samsung S10, Termux, the home connection, no VPN) reads what
GitHub's runner is refused -- Daric first -- and inserts each reading into
`iran_node_readings` through Neon's HTTPS endpoint as the role `iran_node`, which may only
INSERT (`SP_D_HANDOFF.md` sections 30-31).

```text
code        iran_node/node.py (Python + requests), iran_node/setup.sh (one-time setup)
on phone    ~/gold-premium-monitor (git clone -b sp-d-iran-node), ~/.iran_node.env (NEON_URL, NODE)
schedule    cronie, every 15 minutes; Termux:Boot restarts it after a reboot
local       ~/iran_node.log; ~/iran_node_spool.jsonl holds what could not be sent
update      cd ~/gold-premium-monitor && git pull
production  main._daric_from_node: the newest OK reading of the last 30 minutes, when
            Daric's own collector fails; validated like any platform
```

The role is made by SQL, never through Neon's API or console: a role made there joins
`neon_superuser`, which reads and writes every table. Keep the phone on its charger and
Wi-Fi, Termux's battery setting on Unrestricted, and do not tap Exit on Termux's
notification (it stops the schedule).
