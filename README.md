
# Gold Premium Monitor

A Python-based monitoring system for the Iranian 18K gold market. It calculates a theoretical fair value for 18K gold using world gold price (USD/oz) and USD/IRR sell rate, then compares it against live prices from Iranian platforms to generate BUY/SELL/HOLD signals with trend analysis.

---

## Features

- **Fair Price Calculation**: Computes theoretical 18K gold price using world gold price and USD exchange rate.
- **Multi-Platform Monitoring**: Tracks prices from Milli, Goldika, WallGold, Taline, HoorGold, Parasteh, Miogold, Ayyareh, and Eligallery.
- **Signal Engine**: BUY/SELL/HOLD alerts with hysteresis to prevent duplicate notifications.
- **Trend Analysis**: Recent trend arrows (↑↓→) and 7-day moving average of premium.
- **ASCII Sparklines**: Inline visual charts in Telegram notifications.
- **Dual Notifications**: Email (Resend) and Telegram alerts.
- **On-Demand Updates**: Trigger snapshots via Telegram bot command.
- **Daily Recaps**: Scheduled daily reports (only on scheduled runs, not manual triggers).
- **Defensive Validation**: Input guards prevent false signals from bad data.
- **Transport Isolation**: Email failure never blocks Telegram, and vice versa.
- **Persistent State**: History and alert state survive across runs via GitHub Actions Cache.
- **CI Smoke Test**: Syntax and import checks run before every execution.

---

## Architecture

### Data Flow

```
World Gold Price (Kitco)
        |
        v
USD Sell Rate (Bonbast)
        |
        v
Fair Price Calculator
        |
        v
Iranian Market Collectors
        |
        v
Premium Analysis
        |
        v
Signal Engine (BUY/SELL/HOLD)
        |
        +---> Email (Resend)
        +---> Telegram Bot
```

### Triggers

| Source | Type | Daily Recap | Alerts |
|---|---|---|---|
| cron-job.org | Primary schedule | ✅ Yes | ✅ Yes |
| GitHub Actions schedule | Backup | ✅ Yes | ✅ Yes |
| Telegram "Update" command | On-demand | ❌ No | ✅ Yes |
| GitHub workflow_dispatch | Manual | ❌ No | ✅ Yes |

---

## Repository Structure

```text
gold-premium-monitor/
├── config/
│   └── config.json
├── src/
│   ├── alerts/
│   │   ├── helpers.py          # Shared formatting helpers
│   │   ├── resend_mail.py
│   │   ├── telegram.py
│   │   └── gmail.py
│   ├── caluclator/
│   │   ├── gold.py
│   │   ├── signals.py
│   │   ├── trends.py           # Recent trend + 7-day MA
│   │   └── sparkline.py        # ASCII sparkline charts
│   ├── collector/
│   │   ├── kitco.py
│   │   ├── bonbast.py
│   │   ├── iran.py
│   │   ├── milli.py
│   │   ├── goldika.py
│   │   ├── wallgold.py
│   │   ├── taline.py
│   │   ├── hoorgold.py
│   │   ├── parasteh.py
│   │   ├── miogold.py
│   │   ├── ayyareh.py
│   │   ├── eligallery.py
│   │   └── daric.py
│   ├── persistence/
│   │   └── state.py
│   ├── validation/
│   │   └── data.py             # Input validation guards
│   └── main.py
├── tests/
│   ├── test_signals.py
│   ├── test_gold.py
│   ├── test_trends.py
│   ├── test_sparkline.py
│   ├── test_collectors.py
│   └── test_state_migration.py
├── requirements.txt
└── .github/workflows/
    └── gold-monitor.yml
```

> Note: The project intentionally uses `caluclator` instead of `calculator`.

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/mtnihrbp-hue/gold-premium-monitor.git
cd gold-premium-monitor
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file or export directly:

```bash
export RESEND_API_KEY="your_resend_api_key"
export EMAIL_TO="your_email@example.com"
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
```

### 4. Run locally

```bash
python src/main.py
```

### 5. Run tests

```bash
python tests/test_signals.py
python tests/test_gold.py
python tests/test_trends.py
python tests/test_sparkline.py
python tests/test_collectors.py
python tests/test_state_migration.py
```

---

## Configuration

Edit `config/config.json`:

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

| Setting | Description |
|---|---|
| `buy_premium_percent` | Threshold for BUY signal (default: -1.5%) |
| `sell_premium_percent` | Threshold for SELL signal (default: +3.0%) |
| `min_change_for_alert` | Minimum premium change for repeat alerts (default: 0.5%) |
| `history_limit` | Maximum history entries to retain (default: 30) |

---

## Signal Logic

| Signal | Condition |
|---|---|
| **BUY** | Premium ≤ -1.5% |
| **SELL** | Premium ≥ +3.0% |
| **HOLD** | Between reset bands |

### Hysteresis Rules

- Same-zone drift below 0.5% → no repeat alert
- Entering neutral zone → resets previous alert silently
- First entry or re-entry after reset → immediate alert

---

## Notifications

### Email (Resend)

- HTML-formatted daily reports and alerts
- Includes trend summary when available

### Telegram

- HTML-formatted messages with bold/italic rendering
- ASCII sparkline charts
- Manual "Update" command for on-demand snapshots
- Console error logging for debugging

---

## CI/CD

GitHub Actions workflow:

1. Restore `state.json` from cache
2. Install Python 3.12 dependencies
3. **Smoke test** (`python -m compileall src` + import check)
4. Execute monitor
5. Save updated state cache

---

## Development Status

### Completed

- ✅ Persistent state via GitHub Actions Cache
- ✅ BUY/SELL signal engine with hysteresis
- ✅ Dual-channel notifications (Email + Telegram)
- ✅ External precise scheduling (cron-job.org)
- ✅ Telegram on-demand trigger via Cloudflare Worker
- ✅ Defensive data validation
- ✅ Notification transport isolation
- ✅ Unified notification interfaces
- ✅ Daily recap protection (scheduled runs only)
- ✅ Structured console output with diagnostics
- ✅ State corruption warning with graceful fallback
- ✅ Trend analysis (recent trend + 7-day MA)
- ✅ ASCII sparkline charts
- ✅ Shared formatting helpers
- ✅ 61 unit tests covering signals, gold, trends, sparklines, collectors, state migration
- ✅ CI smoke test

### In Progress

- ⚠️ Production verification of HTML scraper collectors

### Planned

- 📋 Historical trend analysis
- 📋 Price volatility tracking
- 📋 Multi-platform price comparison chart

---

## Known Technical Debt

| Item | Priority | Status |
|---|---|---|
| Verify HTML collectors in production | P1 | ⚠️ Pending |
| Rename `caluclator` → `calculator` | P2 | ⏸️ Deferred |

---

## License

MIT

---

## Contributing

This project follows the principles documented in `Prompt_Guide.md`:

- Think before coding
- Simplicity first
- Surgical changes
- Goal-driven execution

When contributing, please read `PROJECT_MEMORY.md` for architectural context.
