
# Gold Premium Monitor

## Objective

Continuously monitor the Iranian 18K gold market by comparing the theoretical fair value of gold with live executable prices from Iranian trading platforms.

The monitor identifies market premiums/discounts and sends BUY/SELL alerts when meaningful opportunities appear.

---

Premium %

Deviation of executable market price from calculated theoretical fair value.

(price - fair_value) / fair_value

---

# Data Quality Rules

A signal is valid only when:

- World gold price is available (or recent fallback <6h old from history)
- USD rate is available
- Minimum N market sources return valid prices
- No price is stale beyond threshold

---

# Current Status

## Infrastructure

- ✅ Public GitHub repository
- ✅ Python 3.12
- ✅ Repository connected to ChatGPT GitHub integration (read-only assistance)
- ✅ Persistent state via GitHub Actions Cache (`state.json` survives across runs)
- ✅ BUY/SELL alert system with hysteresis
- ✅ Dual-channel notifications:
  - Email (Resend)
  - Telegram Bot
- ✅ Telegram-triggered on-demand execution via Cloudflare Worker
- ✅ External precise scheduling via cron-job.org
- ✅ GitHub Actions schedule retained as backup
- ✅ Defensive data validation (`src/validation/data.py`)
- ✅ Notification transport isolation (one channel failure never blocks another)
- ✅ Unified notification interfaces (all channels accept identical signatures)
- ✅ Daily recap protection (only scheduled runs send recaps)
- ✅ Structured console output with diagnostics
- ✅ State corruption warning with graceful fallback
- ✅ Manual update via Telegram (on-demand snapshot)
- ✅ World gold price fallback from history (<6h old)

---

# Project Structure

```text
config/
    config.json

src/
    alerts/
        helpers.py          # Shared formatting helpers
        resend_mail.py
        gmail.py            # SMTP fallback (alternative to Resend)
        telegram.py

    caluclator/
        gold.py
        signals.py
        trends.py           # Fair price trend + 7-day MA + market spread
        sparkline.py        # ASCII sparkline charts

    collector/
        __init__.py
        ayyareh.py
        bonbast.py
        daric.py
        eligallery.py
        goldika.py
        hoorgold.py
        iran.py
        kitco.py
        miogold.py
        milli.py
        parasteh.py
        taline.py
        tlyn_backup.py      # API backup for Taline
        wallgold.py

    persistence/
        state.py

    validation/
        data.py             # Input validation guards

    main.py

tests/
    test_signals.py
    test_gold.py
    test_trends.py
    test_sparkline.py
    test_collectors.py
    test_state_migration.py

.github/
    workflows/
        gold-monitor.yml
```

> Note: The project intentionally uses `caluclator` instead of `calculator`.

---

## Collectors

### External Price Feeds

| Platform | Type | Method | Status |
| --- | --- | --- | --- |
| Kitco | Global gold price | API with 3-level fallback (gold-api.com → kitco SSE → goldprice.org) | ✅ Stable |
| Bonbast | USD exchange rate | Python package (`bonbast==1.0.2`) | ✅ Stable |

### Iranian Market Collectors

| Platform | Type | Status |
| --- | --- | --- |
| Milli | API | ✅ Working |
| Goldika | API | ✅ Working |
| WallGold | API | ✅ Working |
| Taline | HTML scrape | ⚠️ Code ready, production verification needed |
| HoorGold | HTML scrape | ⚠️ Code ready, production verification needed |
| Parasteh | HTML scrape | ⚠️ Code ready, production verification needed |
| Miogold | HTML scrape | ⚠️ Code ready, production verification needed |
| Ayyareh | HTML scrape | ⚠️ Code ready, production verification needed |
| Eligallery | HTML scrape | ⚠️ Code ready, production verification needed |
| Daric | API | ⚠️ Code ready, production verification needed |

---

## Calculation Logic

Fair price formula:

```
World Gold (USD/oz)
×
USD Sell Rate (IRR)
÷
31.1034768
×
0.750
```

Current implementation:

```python
fair = calculate_fair_price(world, usd) * 10
```

Outputs:

- Fair Price
- Lowest Market Price
- Premium %
- Market Spread (highest vs lowest valid platform)

### World Gold Fallback

If all live world gold APIs fail, `main.py` falls back to the most recent cached `world_gold` value from `state.json` if it is less than 6 hours old and from the same calendar day.

---

## Signal Logic

Location:

```
src/caluclator/signals.py
```

| Signal | Condition |
| --- | --- |
| BUY | `premium <= buy_premium_percent` (default -1.5%) |
| SELL | `premium >= sell_premium_percent` (default +3.0%) |
| HOLD | Between reset bands |

### Hysteresis Rules

- Same-zone drift below `min_change_for_alert` (0.5%) → no alert
- Entering neutral zone → resets previous alert silently
- First BUY/SELL entry → immediate alert
- Re-entry after reset → immediate alert

---

## Trends

Location:

```
src/caluclator/trends.py
```

| Metric | Description |
| --- | --- |
| Fair Price Trend | Direction of last 3 daily fair prices (↑ ↓ →) with 0.1% deadband |
| vs Yesterday | Percentage change of today's fair price vs yesterday's |
| 7-Day Avg Fair | Simple moving average of last 7 daily fair prices |
| Market Spread | Absolute spread between highest and lowest valid platform price (current run) |
| Premium Sparkline | ASCII block-character chart of recent premium history |

Trends are included in both Email and Telegram notifications when sufficient history exists.

> **Note:** The `get_trend_summary()` builder returns fair-price-based metrics. Premium-based trend functions (`get_recent_trend`, `get_7day_ma`) remain available for backward compatibility but are not used in the main flow.

---

## Persistence

Location:

```
src/persistence/state.py
```

Functions:

```python
load_state()
save_state()
```

State schema:

```json
{
  "schema_version": 1,
  "history": [],
  "last_alert": null,
  "alert_history": [],
  "created_at": "",
  "updated_at": ""
}
```

Storage:

```
GitHub Actions Cache (actions/cache@v4)
```

Process:

1. Restore `state.json`
2. Execute monitoring
3. Update state
4. Save cache

**Corruption handling:** If `state.json` is corrupted, a warning is printed and a fresh default state is used. The monitor continues running.

---

## Validation

Location:

```
src/validation/data.py
```

Validates:

- World gold price ($1,000–$5,000)
- USD sell rate (10,000–1,000,000 IRR)
- Market prices (1M–500M IRR per gram)
- Minimum 2 working market sources
- Fair price sanity checks

Discarded platforms are logged with diagnostic reasons (e.g., "price out of range", "timeout").

---

## Notification Channels

### Email

Primary Provider:

```
Resend
```

Configuration:

```
Sender:
onboarding@resend.dev

Secrets:
RESEND_API_KEY
EMAIL_TO
```

Fallback:

```
gmail.py — SMTP via smtplib (alternative transport, not actively used in CI)
```

Notifications:

- Daily recap (scheduled runs only)
- BUY/SELL alerts

Features:

- Unified interface: `send_alert(..., trends=None)` and `send_daily_recap(..., trends=None)`
- Transport isolation: Email failure never blocks Telegram
- Optional trend block in HTML

---

### Telegram Bot

Created through:

```
@BotFather
```

Secrets:

```
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

Notifications:

- Daily recap (scheduled runs only)
- BUY/SELL alerts
- Manual Update (on-demand trigger)
- Data Unavailable (when world gold fails)
- Processing heartbeat (manual triggers only)

Features:

- HTML formatting (`parse_mode="HTML"`)
- ASCII sparkline charts
- Console error logging
- Graceful skip when secrets are unavailable
- Transport isolation: Telegram failure never blocks Email

---

### Notification Data

Both channels include:

- Timestamp
- Fair price
- Lowest market price
- Premium %
- World gold price
- USD exchange rate
- Fair Price Trend arrow + percentage
- vs Yesterday percentage
- 7-Day Avg Fair (when available)
- Premium sparkline (Telegram only)
- Platform price change vs previous run

---

## Trigger Architecture

### Primary Trigger

Service:

```
cron-job.org
```

Flow:

```
cron-job.org
      |
      |
GitHub API
      |
      |
workflow_dispatch
      |
      |
GitHub Actions
```

Configuration:

- Schedule: Daily 18:00 Tehran
- Precision: ~10–30 seconds
- Token: GitHub PAT (`repo` scope)
- `SCHEDULED_RUN` env var: not set (daily recap sent)

---

### Telegram On-Demand Trigger

Architecture:

```
Telegram Bot
      |
      |
Cloudflare Worker
      |
      |
GitHub API
      |
      |
GitHub Actions
```

Command:

```
Update
```

Behavior:

- Sends a "📋 Manual Update" snapshot with current market data
- Does NOT send daily recap
- BUY/SELL alerts still fire if signal conditions are met
- Security: Validates `TELEGRAM_CHAT_ID`
- Cloudflare observability disabled to prevent retry loops

---

### Backup Trigger

GitHub Actions schedule:

```
30 14 * * *
```

Equivalent:

```
14:30 UTC ≈ 18:00 Tehran
```

Note:

GitHub free-tier schedules may experience delays.

---

## Workflow

File:

```
.github/workflows/gold-monitor.yml
```

Secrets passed:

```
RESEND_API_KEY
EMAIL_TO
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

Execution:

1. Restore state cache
2. Install Python 3.12 dependencies
3. **Smoke test** (`python -m compileall src` + import check)
4. Run:

```python
python src/main.py
```

5. Save updated state cache

---

## Design Rules

- Collectors only collect.
- Collectors never calculate.
- Collectors never send notifications.
- Calculators never access APIs.
- Alerts never calculate.
- Persistence never performs calculations.
- Each module owns exactly one responsibility.
- **Notification channels are isolated** — one failure never blocks another.

---

## Technical Debt & Next Priorities

| Priority | Item | Status |
| --- | --- | --- |
| P1 | Verify HTML collectors in production runs | ⚠️ Pending |
| P1 | Verify Telegram HTML rendering | ✅ Fixed |
| P2 | Add trend analysis module | ✅ Done |
| P2 | Add recent trend arrows | ✅ Done |
| P2 | Add 7-day moving average | ✅ Done |
| P2 | Add sparkline charts | ✅ Done |
| P2 | Rename `caluclator` → `calculator` | ⏸️ Deferred |
| P2 | Add collector response tests | ✅ Done |
| P2 | Add state migration tests | ✅ Done |
| P3 | Add historical trend analysis | 📋 Planned |
| P3 | Add price volatility tracking | 📋 Planned |
| P3 | Add multi-platform price comparison chart | 📋 Planned |

---

## Completed Milestones

- ✅ Persistent state using GitHub Actions Cache
- ✅ BUY/SELL signal evaluation with hysteresis
- ✅ Separate daily recap and alert notifications
- ✅ Defensive guards for empty markets and zero fair price
- ✅ Removed unused `playwright` dependency
- ✅ Added `state.json` to `.gitignore`
- ✅ Added timestamps to alert emails
- ✅ Added Telegram notifications
- ✅ Added Telegram error logging
- ✅ Added cron-job.org precise trigger
- ✅ Added Cloudflare Worker Telegram trigger
- ✅ Added HoorGold collector
- ✅ Added Parasteh collector
- ✅ Added Ayyareh collector
- ✅ Added Miogold collector
- ✅ Added Eligallery collector
- ✅ Added market spread tracking
- ✅ Added world gold price fallback from history
- ✅ **Sprint 1:** Data validation module + unit tests (signals + gold)
- ✅ **Sprint 2:** Trend analysis, recent trend arrows, 7-day MA, ASCII sparklines
- ✅ **Quality Sprint A:** Unified notification interfaces, transport isolation
- ✅ **Quality Sprint B:** Config cleanup, `SCHEDULED_RUN` guard, smoke test reorder
- ✅ **Quality Sprint C:** Collector diagnostics, structured logging, shared helpers, trend naming
- ✅ **Sprint 3:** Collector response tests, state migration tests
- ✅ **Fix:** Telegram manual update on non-scheduled runs

---

## Configuration

Example:

```json
{
  "timezone": "Asia/Tehran",
  "thresholds": {
    "buy_premium_percent": -1.5,
    "sell_premium_percent": 3.0,
    "min_change_for_alert": 0.5,
    "history_limit": 30
  },
  "email": {
    "send_daily_recap": true,
    "send_alerts": true
  }
}
```

---

## Testing Status

Current:

- Manual validation
- **Unit tests:**
  - Signal engine (10 cases)
  - Gold calculator (14 cases)
  - Trend module (11 cases)
  - Sparkline generator (10 cases)
  - Collector responses (9 cases)
  - State migration (7 cases)
- **Total: 61 test cases**

Planned:

- Kitco collector mock test
- Bonbast collector mock test
- End-to-end workflow test

---

## Secrets Reference

| Secret | Used In | Source |
| --- | --- | --- |
| `RESEND_API_KEY` | GitHub Actions → Email sender | Resend |
| `EMAIL_TO` | GitHub Actions → Email recipient | User email |
| `TELEGRAM_BOT_TOKEN` | GitHub Actions + Cloudflare Worker | Telegram BotFather |
| `TELEGRAM_CHAT_ID` | GitHub Actions + Cloudflare Worker | Telegram API |
| `GITHUB_TOKEN` | Cloudflare Worker → GitHub API | GitHub PAT |

---

## New Chat Onboarding

When continuing development:

1. Share this `PROJECT_MEMORY.md`
2. Share repository:

```
https://github.com/mtnihrbp-hue/gold-premium-monitor
```

3. State the current priority.

Examples:

```
Add volatility tracking
```

```
Fix Taline collector in production
```

```
Add Kitco collector unit test
```

The assistant should read the repository before making architectural changes.


-----------------------


## Sprint 1 Completed — 2026-08-04

### Added
- Neon PostgreSQL persistence layer via SQLAlchemy ORM
- Tables: `market_snapshots`, `platform_prices`, `system_events`
- Database module: `src/database/` (connection, models, repository, init)
- Automated tests: `tests/test_database.py` (5 tests, SQLite in-memory)
- KPI checker: `kpi/sprint_01_kpi.py` (validates against real Neon)
- `requirements.txt`: +sqlalchemy, +psycopg2-binary

### Modified
- `src/main.py`: Computes `platform_changes`, saves snapshot to DB after signal generation. DB failure is caught and logged — never crashes the app.
- `src/caluclator/trends.py`: Fixed `get_fair_price_trend()` bug. Now compares last 2 consecutive readings instead of 3-day aggregated window. Arrow direction is now correct for consecutive runs.
- `src/alerts/telegram.py`: Replaced ASCII sparkline with directional sentence: "Premium falling by 0.41% over last 5 checks" (or rising/stable).

### Architecture Decision
- JSON `state.json` retained for hysteresis/last_alert runtime state
- PostgreSQL handles historical snapshots and platform prices
- Dual-write strategy: JSON for state machine, Postgres for analytics

### Next Sprint Ready
- Historical data is now queryable via `get_snapshots(days=N)`
- Foundation ready for: sentiment radar, regime detector, prediction engine

----------------------


