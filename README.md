Here's the complete, corrected `README.md`. Copy everything below and paste it directly into your GitHub file editor.

```markdown
# Gold Premium Monitor

A Python-based monitoring system for the Iranian 18K gold market. It calculates a theoretical fair value for 18K gold using world gold price (USD/oz) and USD/IRR sell rate, then compares it against live prices from Iranian platforms to generate BUY/SELL/HOLD signals with trend analysis.

---

## Features

- **Fair Price Calculation**: Computes theoretical 18K gold price using world gold price and USD exchange rate.
- **Multi-Platform Monitoring**: Tracks prices from Milli, Goldika, WallGold, Taline, HoorGold, Parasteh, Miogold, Ayyareh, and Eligallery.
- **Signal Engine**: BUY/SELL/HOLD alerts with hysteresis to prevent duplicate notifications.
- **Trend Analysis**: Recent trend arrows (↑↓→), 7-day moving average, and premium direction sentences.
- **Premium Direction Sentences**: Human-readable trend summaries (e.g., "Premium rising by 0.61% over last 5 checks").
- **Dual Notifications**: Email (Resend) and Telegram alerts.
- **On-Demand Updates**: Trigger snapshots via Telegram bot command.
- **Daily Recaps**: Scheduled daily reports (only on scheduled runs, not manual triggers).
- **Defensive Validation**: Input guards prevent false signals from bad data.
- **Transport Isolation**: Email failure never blocks Telegram, and vice versa.
- **Persistent State**: History and alert state survive across runs via GitHub Actions Cache.
- **Long-Term Memory**: Neon PostgreSQL stores every market snapshot for historical analytics.
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
        |
        v
Neon PostgreSQL (historical storage)
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
│   │   └── gmail.py            # SMTP fallback
│   ├── caluclator/
│   │   ├── gold.py
│   │   ├── signals.py
│   │   ├── trends.py           # Recent trend + 7-day MA + premium direction
│   │   └── sparkline.py        # Legacy ASCII sparkline (deprecated)
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
│   ├── database/               # Neon PostgreSQL persistence (Sprint 1)
│   │   ├── __init__.py
│   │   ├── connection.py
│   │   ├── models.py
│   │   ├── repository.py
│   │   └── init.py
│   ├── persistence/
│   │   └── state.py
│   ├── validation/
│   │   └── data.py             # Input validation guards
│   ├── worker/                 # Cloudflare Worker backup
│   │   ├── telegram-trigger.js
│   │   └── README.md
│   └── main.py
├── tests/
│   ├── test_signals.py
│   ├── test_gold.py
│   ├── test_trends.py
│   ├── test_sparkline.py
│   ├── test_collectors.py
│   ├── test_state_migration.py
│   └── test_database.py        # Database persistence tests (Sprint 1)
├── kpi/
│   ├── __init__.py
│   └── sprint_01_kpi.py        # Sprint 1 validation
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
export DATABASE_URL="postgresql://user:password@host.neon.tech/database?sslmode=require"
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
python tests/test_database.py
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
- Premium trend sentences with directional context
- Manual "Update" command for on-demand snapshots
- Console error logging for debugging

---

## Database Architecture

Sprint 1 introduces a Neon PostgreSQL persistence layer for long-term historical storage.

### Why Neon?

- **Free tier**: 3 GB storage, auto-suspend when idle (you pay nothing 22 hours/day)
- **Serverless connections**: Designed for ephemeral GitHub Actions runners
- **PostgreSQL**: Full SQL support for future analytics (window functions, time-series queries)
- **No concurrency conflicts**: Unlike SQLite-in-repo, multiple workflows can write safely

### Setup

1. **Create a Neon project** at [neon.tech](https://neon.tech) (free tier)
2. **Copy the connection string** from your Neon dashboard
3. **Add `DATABASE_URL` to your GitHub repository secrets**:
   - Go to Settings → Secrets and variables → Actions
   - Add `DATABASE_URL` with your connection string:
     ```
     postgresql://user:password@host.neon.tech/database?sslmode=require
     ```

### Local Development

```bash
# Set the environment variable
export DATABASE_URL="postgresql://user:password@host.neon.tech/database?sslmode=require"

# Install dependencies
pip install -r requirements.txt

# Create tables
python -m src.database.init
```

### Running the KPI Checker

The KPI checker validates Sprint 1 against your real Neon instance:

```bash
export DATABASE_URL="postgresql://user:password@host.neon.tech/database?sslmode=require"
python -m kpi.sprint_01_kpi
```

Expected output:
```
==================================================
Sprint 1 KPI Report
==================================================
Database connection: PASS
Tables created: PASS
Insert test: PASS
Read test: PASS
Failure handling: PASS
--------------------------------------------------
Overall: SPRINT 1 COMPLETE
==================================================
```

### Schema

**market_snapshots**
| Column | Type | Description |
|--------|------|-------------|
| id | integer PK | Auto-increment |
| timestamp | datetime | Observation time |
| fair_price | numeric(20,2) | Calculated fair price (IRR) |
| premium_percent | numeric(10,4) | Premium/discount percentage |
| world_gold_usd | numeric(10,2) | World gold price (USD/oz) |
| usd_irr | numeric(20,2) | USD sell rate (IRR) |
| signal | varchar(10) | BUY / SELL / HOLD / NULL |
| confidence | numeric(5,4) | Model confidence (SP1: NULL) |
| created_at | datetime | Record creation time (auto) |

**platform_prices**
| Column | Type | Description |
|--------|------|-------------|
| id | integer PK | Auto-increment |
| snapshot_id | integer FK | References market_snapshots |
| platform_name | varchar(50) | Platform name |
| price_irr | numeric(20,2) | Platform price (IRR) |
| change_irr | numeric(20,2) | Change from previous reading |
| timestamp | datetime | Observation time |

**system_events**
| Column | Type | Description |
|--------|------|-------------|
| id | integer PK | Auto-increment |
| timestamp | datetime | Event time |
| event_type | varchar(50) | Event category |
| source | varchar(100) | Event source |
| description | text | Human-readable description |
| metadata_json | json | Structured metadata |

> **Note**: `system_events` is created empty in Sprint 1. It will be populated by the news intelligence module in Sprint 2+.

### Error Handling

Database failures are **non-fatal**. If Neon is unavailable:
- The error is logged to console
- Market monitoring continues
- Telegram notifications still work
- JSON state persistence still works

The application degrades gracefully. No alerts are lost.

### GitHub Actions Integration

Add `DATABASE_URL` to your workflow environment:

```yaml
- name: Execute
  env:
    SCHEDULED_RUN: ${{ github.event_name == 'schedule' && 'true' || 'false' }}
    RESEND_API_KEY: ${{ secrets.RESEND_API_KEY }}
    EMAIL_TO: ${{ secrets.EMAIL_TO }}
    TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
    TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
    DATABASE_URL: ${{ secrets.DATABASE_URL }}
  run: |
    python src/main.py
```

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
- ✅ Premium direction sentences (replaced sparklines)
- ✅ Shared formatting helpers
- ✅ Neon PostgreSQL persistence layer (Sprint 1)
- ✅ 61+ unit tests covering signals, gold, trends, sparklines, collectors, state migration, database
- ✅ CI smoke test

### In Progress

- ⚠️ Production verification of HTML scraper collectors

### Planned

- 📋 Historical trend analysis
- 📋 Price volatility tracking
- 📋 Multi-platform price comparison chart
- 📋 News sentiment intelligence (Sprint 2)

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
```

---

**How to apply:** Go to your repo on GitHub → click `README.md` → click the pencil icon (Edit) → Select all → Delete → Paste the entire block above → Commit directly to `main`.

Once that's done, tell me and we'll move to **Task C** — your improvement items.
