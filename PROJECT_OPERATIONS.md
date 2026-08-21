# Gold Premium Monitor — Operational Control Plane

This document records the runtime control plane that sits around the application code.

It is distinct from `PROJECT_MEMORY.md` (architecture/state) and `PROJECT_ORCHESTRATION.md` (project continuity).

## 1. Two wings

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
future dataset / forecast
```

The Analysis Wing is scheduled and must be independent of the number of Telegram users.

## 2. External scheduler policy

The intended scheduler is `cron-job.org`, not GitHub's internal `schedule` event.

User-provided cron-job.org job reference:

```text
https://console.cron-job.org/jobs/8179679
Job ID: 8179679
```

The external scheduler exists so schedule control is outside GitHub Actions and can be inspected and manually operated independently.

GitHub Actions should retain a manual trigger for testing, but the production Analysis Wing schedule should not depend on GitHub's own `schedule` trigger once the external scheduler is operational.

GitHub currently still contains an internal daily schedule in `.github/workflows/gold-monitor.yml`:

```text
30 14 * * * UTC
```

This is NOT the final Analysis Wing scheduling policy. It is legacy/current infrastructure that must be removed or disabled after the external trigger has been verified.

## 3. Intended analysis cadence

Current project scheduler contract:

```text
Timezone: Asia/Tehran
Start: 08:00
End: 21:00 exclusive
Interval: 30 minutes
Active days: configurable
```

Therefore the intended operational cadence is:

```text
08:00
08:30
09:00
...
20:30
```

The external cron may use a simpler wall-clock cadence, but the application scheduler remains authoritative for deciding whether an analysis window is valid.

Do not silently change the cadence to 60 minutes without updating the project contract.

## 4. Analysis run guardrails

The scheduler/execution layer must enforce:

```text
analysis run is scheduled
analysis run is idempotent
source_run_id is deterministic
duplicate trigger does not create duplicate analysis state
manual /Update does not create a scheduled analysis run
```

C.13 verified these properties through the KPI and live smoke path.

The live Analysis Wing smoke on SP-B successfully created an analysis snapshot and delivered Telegram output.

The C.13 KPI result was:

```text
26/26 PASS
```

### World-gold / XAUUSD calendar guardrail

The historical project discussion included a source-calendar guardrail for days when the world-gold source/market is closed.

The remembered historical wording was:

```text
skip world-gold call on Saturday and Monday
```

This remains **UNVERIFIED** because standard global gold market calendars do not support treating Monday as a normal weekly closure. No code should implement the Saturday/Monday rule until the actual source calendar and intended exception are verified.

What is safe to implement generically:

```text
source unavailable / market closed
    ↓
do not fabricate XAUUSD
    ↓
persist source/data-quality state
    ↓
allow other independent analyses to continue when valid
```

Any source-specific closure calendar must be documented next to the collector/guardrail that owns it.

## 5. Cloudflare role

Cloudflare is an interconnection/control layer, not the analytical engine.

Intended responsibilities:

```text
Telegram request
    ↓
Cloudflare Worker / secure gateway
    ↓
validated command or trigger
    ↓
GitHub execution endpoint
```

and, for scheduled analysis if retained as the protected intermediary:

```text
cron-job.org
    ↓
Cloudflare Worker
    ↓
GitHub Actions workflow dispatch
    ↓
Analysis Wing
```

Cloudflare must not calculate gold price, premium, regime, features, or forecast.

## 6. GitHub Actions trigger contract

The GitHub workflow must expose an external/manual trigger path that can receive an explicit execution mode.

Preferred conceptual modes:

```text
analysis_scheduled
live_update
telegram_command
```

The external trigger must select a ref explicitly (`SP-B` while SP-B is active) and must not rely on an implicit default branch.

## 7. cron-job.org security boundary

The cron-job.org job must never contain a long-lived repository credential in a public URL.

A protected intermediary (Cloudflare Worker or equivalent secure endpoint) should hold the GitHub credential and make the GitHub API request.

Credentials must never be copied into repository files.

## 8. Current Cloudflare connection status

Cloudflare engineering skills are available in the project workspace, but the Cloudflare application connection is not currently installed/connected in this ChatGPT session.

Therefore:

```text
Cloudflare architecture = documented
Cloudflare live control = NOT YET CONNECTED
```

Do not claim Cloudflare deployment or secret access until the actual Cloudflare connection is available.

## 9. Telegram command roadmap

C.13 established the analytical command contract:

```text
/Update
/Analysis
/Technical
/History
/News
/Health
```

The live smoke verified Telegram delivery from the integrated execution path.

Potential future:

```text
/Radar
/Forecast
```

`/Forecast` must remain disabled until the empirical forecast-readiness gate is satisfied.

## 10. Forecast readiness gate

A forecast engine may target:

```text
UP
NEUTRAL
DOWN
```

but it must not be deployed merely because feature infrastructure exists.

Minimum evidence gate:

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

C.13 has now started the production Analysis Wing history required for that gate. The forecast engine remains **NOT READY FOR DEPLOYMENT**.

## 11. C.13 Neon reconciliation

C.13 live smoke exposed two production-schema mismatches. They were reconciled through an incremental migration validated on a temporary Neon branch before production application.

Production now includes:

```text
news_events
idx_news_events_dedup_key
expanded outcome direction fields sufficient for INSUFFICIENT_DATA
```

No destructive replacement migration was used.

The migration is recorded in:

```text
sql/neon_migration_c13.sql
```

## 12. Current operational completion state

```text
PRE-SP-C.13
KPI: 26/26 PASS
compileall: PASS
live smoke: PASS
analysis snapshot creation: PASS
Telegram delivery: PASS
Neon C.13 reconciliation: COMPLETE
```

A non-blocking Daric timeout was observed during live smoke. Ten other gold sources remained valid, so the collection/validation path continued normally.

## 13. Operational truth rule

For a new conversation, reconcile these in order:

```text
cron-job.org current configuration
↓
Cloudflare connection / Worker state
↓
GitHub Actions workflow trigger state
↓
SP-B source code
↓
Neon production row counts
↓
Telegram command behavior
```

The repository must document the resulting state after every operational change.
