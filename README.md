# Gold Premium Monitor

```markdown
# Gold Premium Monitor

A Python-based monitoring system for the Iranian 18K gold market.

Gold Premium Monitor compares the theoretical fair value of gold against live executable prices from Iranian gold trading platforms to identify market deviations and generate BUY/SELL alerts.

The system is designed for continuous monitoring, not automated trading.

---

## Overview

The monitor calculates the theoretical value of 18K gold using:

```

World Gold Price (USD/oz)
×
USD Sell Exchange Rate (IRR)
÷
31.1034768
×
0.750

```

The calculated fair value is compared with live market prices from Iranian platforms.

The output:

- Fair price
- Lowest available market price
- Market deviation percentage
- BUY / SELL / HOLD signal

---

## Features

### Market Monitoring

Supported price sources:

| Source | Purpose | Status |
|---|---|---|
| Kitco | Global gold price | Stable |
| Bonbast | USD sell exchange rate | Stable |
| Milli | Iranian 18K gold price | Stable |
| Goldika | Iranian gold price | Stable |
| WallGold | Iranian gold price | Stable |
| Taline | Iranian gold price | Experimental |
| Daric | Iranian gold price | Unstable |

---

## Signal Engine

The monitor uses a hysteresis-based alert system to prevent repeated notifications during normal market movement.

Default thresholds:

```

BUY:
premium <= -1.5%

SELL:
premium >= +3.0%

```

Signal behavior:

- First entry into BUY/SELL zone → alert sent
- Movement inside the same zone → no duplicate alert
- Return to neutral zone → alert state reset
- Re-entry into BUY/SELL zone → new alert allowed

Example:

```

Premium: -2.1%

Signal:
BUY

```

---

## Alert Channels

The system supports two notification channels.

### Email

Provider:

- Resend API

Notifications:

- Daily recap
- BUY/SELL alerts

Required secrets:

```

RESEND_API_KEY
EMAIL_TO

```

---

### Telegram

Notifications:

- Daily recap
- BUY/SELL alerts

Features:

- HTML formatted messages
- Timestamp information
- Error logging
- Graceful fallback when not configured

Required secrets:

```

TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID

```

---

## Architecture

The project follows strict separation of responsibilities.

```

src/

├── collector/
│   ├── Fetch market data only
│
├── caluclator/
│   ├── Calculate fair value
│   └── Evaluate signals
│
├── alerts/
│   ├── Email notifications
│   └── Telegram notifications
│
├── persistence/
│   └── Store monitoring state
│
└── main.py

```

Design rules:

- Collectors only collect data
- Calculators only calculate
- Alerts only notify
- Persistence only stores state

---

## Workflow

The monitoring pipeline:

```

External Trigger
|
|
GitHub Actions
|
|
Restore State
|
|
Collect Market Data
|
|
Calculate Fair Value
|
|
Evaluate Signal
|
|
Send Notifications
|
|
Save State

```

---

## Trigger System

The system supports multiple triggers.

### Primary Trigger

Service:

```

cron-job.org

```

Purpose:

Precise scheduled execution.

Flow:

```

cron-job.org
|
|
GitHub workflow_dispatch
|
|
GitHub Actions

```

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
GitHub Actions

````

Allows manual updates from Telegram.

---

### Backup Trigger

GitHub Actions native schedule.

Note:

GitHub scheduled workflows may experience execution delays.

---

## Persistence

The monitor maintains state between executions.

Stored information:

```json
{
  "schema_version": 1,
  "history": [],
  "last_alert": null,
  "alert_history": [],
  "created_at": "",
  "updated_at": ""
}
````

Current storage:

```
GitHub Actions Cache
```

State includes:

* Previous alerts
* Historical values
* Signal state
* Execution timestamps

---

## Repository Structure

```
gold-premium-monitor/

├── config/
│   └── config.json
│
├── src/
│   ├── alerts/
│   ├── caluclator/
│   ├── collector/
│   ├── persistence/
│   └── main.py
│
├── .github/
│   └── workflows/
│       └── gold-monitor.yml
│
└── project_memory.md
```

---

## Configuration

Configuration is stored in:

```
config/config.json
```

Secrets are stored as GitHub Actions repository secrets.

Required secrets:

```
RESEND_API_KEY
EMAIL_TO

TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

---

## Running Locally

Requirements:

```
Python 3.12+
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run:

```bash
python src/main.py
```

---

## Development Status

Current completed milestones:

* Persistent state management
* BUY/SELL signal engine
* Alert hysteresis
* Email notifications
* Telegram notifications
* External precise triggering
* Telegram manual updates
* Defensive calculation guards
* Removal of unused dependencies

---

## Known Technical Debt

### High Priority

* Complete Taline collector
* Improve external data validation

### Medium Priority

* Replace unreliable data sources
* Add historical trend analysis

### Low Priority

* Rename:

```
caluclator
```

to:

```
calculator
```

* Add chart visualizations

---

## Limitations

This project:

* Does not execute trades
* Does not provide financial advice
* Depends on third-party market data availability
* Calculates theoretical value, not guaranteed market value

Market prices may differ due to:

* Liquidity
* Spreads
* Platform pricing
* Market conditions

---

## License

Not specified.

```
```
