````markdown
# Gold Premium Monitor

## Objective

Continuously monitor the Iranian 18K gold market by comparing the theoretical fair value of gold with live executable prices from Iranian trading platforms.

The monitor identifies market premiums/discounts and sends BUY/SELL alerts when meaningful opportunities appear.

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

---

# Project Structure

```text
config/
  config.json

src/
  alerts/
    resend_mail.py
    gmail.py
    telegram.py

  caluclator/
    gold.py
    signals.py

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
    wallgold.py

  persistence/
    state.py

  main.py

.github/
  workflows/
    gold-monitor.yml
````

> Note: The project intentionally uses `caluclator` instead of `calculator`.

---

# Collectors

## External Price Feeds

| Platform | Type              | Method                                     | Status   |
| -------- | ----------------- | ------------------------------------------ | -------- |
| Kitco    | Global gold price | HTML scrape (`requests` + `BeautifulSoup`) | ✅ Stable |
| Bonbast  | USD exchange rate | Python package (`bonbast==1.0.2`)          | ✅ Stable |

---

## Iranian Market Collectors

| Platform   | Type        | Status                                        |
| ---------- | ----------- | --------------------------------------------- |
| Milli      | API         | ✅ Working                                     |
| Goldika    | API         | ✅ Working                                     |
| WallGold   | API         | ✅ Working                                     |
| Taline     | HTML scrape | ⚠️ Code ready, production verification needed |
| HoorGold   | HTML scrape | ⚠️ Code ready, production verification needed |
| Parasteh   | HTML scrape | ⚠️ Code ready, production verification needed |
| Miogold    | HTML scrape | ⚠️ Code ready, production verification needed |
| Ayyareh    | HTML scrape | ⚠️ Code ready, production verification needed |
| Eligallery | HTML scrape | ⚠️ Code ready, production verification needed |
| Daric      | HTML scrape | ❌ Ignored due to frequent timeouts            |

---

# Calculation Logic

Fair price formula:

```text
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

* Fair Price
* Lowest Market Price
* Premium %

---

# Signal Logic

Location:

```text
src/caluclator/signals.py
```

| Signal | Condition                                         |
| ------ | ------------------------------------------------- |
| BUY    | `premium <= buy_premium_percent` (default -1.5%)  |
| SELL   | `premium >= sell_premium_percent` (default +3.0%) |
| HOLD   | Between reset bands                               |

## Hysteresis Rules

* Same-zone drift below `min_change_for_alert` (0.5%) → no alert
* Entering neutral zone → resets previous alert silently
* First BUY/SELL entry → immediate alert
* Re-entry after reset → immediate alert

---

# Persistence

Location:

```text
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

```text
GitHub Actions Cache (actions/cache@v4)
```

Process:

1. Restore `state.json`
2. Execute monitoring
3. Update state
4. Save cache

---

# Notification Channels

## Email

Provider:

```text
Resend
```

Configuration:

```text
Sender:
onboarding@resend.dev

Secrets:
RESEND_API_KEY
EMAIL_TO
```

Notifications:

* Daily recap
* BUY/SELL alerts

---

## Telegram Bot

Created through:

```text
@BotFather
```

Secrets:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

Notifications:

* Daily recap
* BUY/SELL alerts

Features:

* HTML formatting (`parse_mode="HTML"`)
* Console error logging
* Graceful skip when secrets are unavailable

---

## Notification Data

Both channels include:

* Timestamp
* Fair price
* Lowest market price
* Premium %
* World gold price
* USD exchange rate

---

# Trigger Architecture

## Primary Trigger

Service:

```text
cron-job.org
```

Flow:

```text
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

* Schedule: Daily 18:00 Tehran
* Precision: ~10–30 seconds
* Token: GitHub PAT (`repo` scope)

---

## Telegram On-Demand Trigger

Architecture:

```text
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

```text
Update
```

Security:

* Validates `TELEGRAM_CHAT_ID`
* Cloudflare observability disabled to prevent retry loops

---

## Backup Trigger

GitHub Actions schedule:

```cron
30 14 * * *
```

Equivalent:

```text
14:30 UTC ≈ 18:00 Tehran
```

Note:

GitHub free-tier schedules may experience delays.

---

# Workflow

File:

```text
.github/workflows/gold-monitor.yml
```

Secrets passed:

```text
RESEND_API_KEY
EMAIL_TO
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

Execution:

1. Restore state cache
2. Install Python 3.12 dependencies
3. Run:

```bash
python src/main.py
```

4. Save updated state cache

---

# Design Rules

* Collectors only collect.
* Collectors never calculate.
* Collectors never send notifications.
* Calculators never access APIs.
* Alerts never calculate.
* Persistence never performs calculations.
* Each module owns exactly one responsibility.

---

# Technical Debt & Next Priorities

| Priority | Item                                      |
| -------- | ----------------------------------------- |
| P1       | Verify HTML collectors in production runs |
| P1       | Verify Telegram HTML rendering            |
| P2       | Add trend analysis module                 |
| P2       | Add 3-day trend arrows                    |
| P2       | Add 7-day moving average                  |
| P2       | Add sparkline charts                      |
| P2       | Rename `caluclator` → `calculator`        |

---

# Completed Milestones

* ✅ Persistent state using GitHub Actions Cache
* ✅ BUY/SELL signal evaluation with hysteresis
* ✅ Separate daily recap and alert notifications
* ✅ Defensive guards for empty markets and zero fair price
* ✅ Removed unused `playwright` dependency
* ✅ Added `state.json` to `.gitignore`
* ✅ Added timestamps to alert emails
* ✅ Added Telegram notifications
* ✅ Added Telegram error logging
* ✅ Added cron-job.org precise trigger
* ✅ Added Cloudflare Worker Telegram trigger
* ✅ Added HoorGold collector
* ✅ Added Parasteh collector
* ✅ Added Ayyareh collector
* ✅ Added Miogold collector
* ✅ Added Eligallery collector

---

# Secrets Reference

| Secret               | Used In                            | Source             |
| -------------------- | ---------------------------------- | ------------------ |
| `RESEND_API_KEY`     | GitHub Actions → Email sender      | Resend             |
| `EMAIL_TO`           | GitHub Actions → Email recipient   | User email         |
| `TELEGRAM_BOT_TOKEN` | GitHub Actions + Cloudflare Worker | Telegram BotFather |
| `TELEGRAM_CHAT_ID`   | GitHub Actions + Cloudflare Worker | Telegram API       |
| `GITHUB_TOKEN`       | Cloudflare Worker → GitHub API     | GitHub PAT         |

---

# New Chat Onboarding

When continuing development:

1. Share this `PROJECT_MEMORY.md`
2. Share repository:

```text
https://github.com/mtnihrbp-hue/gold-premium-monitor
```

3. State the current priority.

Examples:

```text
Add trend analysis
```

```text
Fix Taline collector
```

```text
Review signal accuracy
```

The assistant should read the repository before making architectural changes.

```
```
