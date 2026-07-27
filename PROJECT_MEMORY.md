Gold Premium Monitor

Objective

Continuously monitor the Iranian 18K gold market by comparing the theoretical fair value of gold with live executable prices from Iranian trading platforms.

The monitor identifies market premiums/discounts and sends BUY/SELL alerts when meaningful opportunities appear.

Current Status

Infrastructure
✅ GitHub repository is public.
✅ GitHub Actions running daily at 14:30 UTC.
✅ Python 3.12.
✅ Repository connected to ChatGPT GitHub integration (read-only assistance).
✅ Resend email integration working.
✅ Daily HTML report successfully delivered.
✅ BUY/SELL alert system with hysteresis.
✅ Persistent state via GitHub Actions Cache (state.json survives across runs).

Current Folder Structure

config/
  config.json

src/
  alerts/
    resend_mail.py
    gmail.py

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

Email

Provider: Resend
Sender:   onboarding@resend.dev
Recipient: Repository Secret EMAIL_TO
API Key:   Repository Secret RESEND_API_KEY

Email types:
  1. Daily Recap — always sent (unless disabled in config)
  2. BUY/SELL Alert — sent only on signal trigger

Both emails include timestamp, fair price, lowest market, premium, world gold, and USD rate.

Workflow

Runs:     Daily at 14:30 UTC (cron: "30 14 * * *")
Trigger:  workflow_dispatch (manual) + schedule

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

Completed Milestones

✅ Implement persistent state using GitHub Actions Cache
✅ Add BUY/SELL signal evaluation with hysteresis
✅ Separate daily recap emails from alert emails
✅ Add defensive guards (empty markets, zero fair price)
✅ Remove unused dependency (playwright)
✅ Add state.json to .gitignore
✅ Add timestamps to alert emails
