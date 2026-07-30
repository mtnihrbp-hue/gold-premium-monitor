Gold Premium Monitor

Objective

Continuously monitor the Iranian 18K gold market by comparing the theoretical fair value of gold with live executable prices from Iranian trading platforms.

The monitor identifies market premiums/discounts and sends BUY/SELL alerts when meaningful opportunities appear.

Current Status

Infrastructure
✅ GitHub repository is public.
✅ Python 3.12.
✅ Repository connected to ChatGPT GitHub integration (read-only assistance).
✅ Persistent state via GitHub Actions Cache (state.json survives across runs).
✅ BUY/SELL alert system with hysteresis.
✅ Dual-channel notifications: Email (Resend) + Telegram Bot.
✅ On-demand triggering via Telegram bot + Cloudflare Worker.
✅ External precise trigger via cron-job.org (primary).
✅ GitHub Actions schedule kept as backup.

Current Folder Structure

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
    bonbast.py
    goldika.py
    iran.py
    kitco.py
    milli.py
    wallgold.py
    taline.py
    daric.py

  persistence/
    state.py

  main.py

.github/
  workflows/
    gold-monitor.yml

(Current project intentionally uses caluclator instead of calculator.)

Working Collectors

Kitco
  Purpose:    World Gold Price (USD/oz)
  Status:     ✅ Stable

Bonbast
  Purpose:    USD Sell Rate (IRR)
  Implementation: bonbast python package
  Status:     ✅ Stable

Milli
  Endpoint:  https://milli.gold/api/v1/public/milli-price/external
  Uses:      data.price18
  Normalization: price × 1000
  Status:     ✅ Working

Goldika
  Endpoint:  https://api.goldika.ir/api/public/price
  Uses:      data.price.buy
  Status:     ✅ Working

WallGold
  Endpoint:  https://api.wallgold.ir/api/v1/price?side=buy&symbol=GLD_18C_750TMN
  Uses:      result.price
  Normalization: price × 10
  Status:     ✅ Working

Taline
  Status:     HTML parser exists. Currently unstable. Returns ERROR when unavailable.

Daric
  Status:     Endpoint responds inconsistently. Frequent timeout. Currently ignored.

Calculation Logic

Fair price is calculated from:
  World Gold (USD/oz) × USD Sell (IRR) / 31.1034768 × 0.750

Current implementation multiplies calculated fair value by 10 to match Iranian market units.

Outputs:
  Fair Price
  Lowest Market Price
  Premium %

Signal Logic (src/caluclator/signals.py)

BUY:   premium &lt;= buy_threshold  (default -1.5%)
SELL:  premium &gt;= sell_threshold (default +3.0%)
HOLD:  premium between reset bands (clears last_alert to allow re-entry)

Hysteresis rules:
  - Same-zone drift &lt; 0.5% → no re-alert
  - Crossed into neutral zone → resets last_alert silently
  - First entry into BUY/SELL zone → immediate alert
  - Re-entry after reset → immediate alert

Persistence

src/persistence/state.py
  load_state()  → restores from state.json (with schema migration)
  save_state()  → writes to state.json

State schema:
  {
    "schema_version": 1,
    "history": [...],
    "last_alert": null | "BUY" | "SELL",
    "alert_history": [...],
    "created_at": "...",
    "updated_at": "..."
  }

Storage: GitHub Actions Cache (actions/cache@v4)
  - Restores previous state.json at start of run
  - Saves updated state.json at end of run
  - Survives across workflow executions

Notification Channels

1. Email (Resend)
   Provider:   Resend
   Sender:     onboarding@resend.dev
   Recipient:  Repository Secret EMAIL_TO
   API Key:    Repository Secret RESEND_API_KEY
   Types:
     - Daily Recap — always sent (unless disabled in config)
     - BUY/SELL Alert — sent only on signal trigger

2. Telegram Bot
   Bot:        Created via @BotFather
   Chat ID:    Repository Secret TELEGRAM_CHAT_ID
   Token:      Repository Secret TELEGRAM_BOT_TOKEN
   Types:
     - Daily Recap — sent on every run
     - BUY/SELL Alert — sent only on signal trigger
   Features:
     - HTML formatting with emojis
     - Error logging to console (visible in Actions logs)
     - Graceful skip if secrets not configured

Both channels include timestamp, fair price, lowest market, premium, world gold, and USD rate.

Trigger Architecture

Primary Trigger (Precise)
  Service:    cron-job.org
  Method:     POST to GitHub API
  Target:     workflow_dispatch
  Schedule:   Daily at 18:00 Tehran (configurable)
  Precision:  ~10–30 seconds
  Token:      GitHub Personal Access Token (Classic, repo scope)

Secondary Trigger (On-Demand)
  Service:    Cloudflare Worker
  Interface:  Telegram Bot
  Command:    "Update"
  Method:     POST to GitHub API
  Target:     workflow_dispatch
  Security:   Validates TELEGRAM_CHAT_ID before triggering

Backup Trigger (Best-effort)
  Service:    GitHub Actions native schedule
  Cron:       "30 14 * * *" (14:30 UTC ≈ 18:00 Tehran)
  Note:       Subject to 0–4 hour platform delay

Workflow

File: .github/workflows/gold-monitor.yml

Secrets passed to runner:
  RESEND_API_KEY
  EMAIL_TO
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID

Steps:
  1. Restore state.json from cache
  2. Install Python 3.12 + dependencies
  3. Run src/main.py
  4. Cache saves state.json automatically

Design Rules

Collectors only collect.
Collectors never calculate.
Collectors never send email.
Calculators never access APIs.
Alerts never calculate.
Persistence never performs calculations.
Each module owns exactly one responsibility.

Current Technical Debt

Finish Taline collector.
  Priority: HIGH

Replace Daric if timeout persists.
  Priority: MEDIUM

Rename caluclator → calculator after project stabilizes.
  Priority: LOW

Add trend analysis module (historical comparison, moving averages).
  Priority: MEDIUM

Add sparkline charts to reports.
  Priority: LOW

Completed Milestones

✅ Implement persistent state using GitHub Actions Cache
✅ Add BUY/SELL signal evaluation with hysteresis
✅ Separate daily recap emails from alert emails
✅ Add defensive guards (empty markets, zero fair price)
✅ Remove unused dependency (playwright)
✅ Add state.json to .gitignore
✅ Add timestamps to alert emails
✅ Add Telegram Bot integration (alerts + daily recap)
✅ Add error logging to Telegram module
✅ Add external precise trigger via cron-job.org
✅ Add on-demand Telegram trigger via Cloudflare Worker
