Gold Premium Monitor
Objective

Continuously monitor the Iranian 18K gold market by comparing the theoretical fair value of gold with live executable prices from Iranian trading platforms.

The monitor must identify market premiums/discounts and notify when opportunities appear.

Current Status
Infrastructure
✅ GitHub repository is public.
✅ GitHub Actions running every 30 minutes.
✅ Python 3.12.
✅ Repository connected to ChatGPT GitHub integration (read-only assistance).
✅ README updated.
✅ Resend email integration working.
✅ Daily HTML report successfully delivered.
Current Folder Structure
config/

src/

    alerts/
        resend_mail.py

    caluclator/
        gold.py

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

Purpose

World Gold Price (USD/oz)

Status

✅ Stable

Bonbast

Purpose

USD Sell Rate

Implementation

bonbast python package

Status

✅ Stable

Iranian Platforms
Milli

Endpoint

https://milli.gold/api/v1/public/milli-price/external

Uses

data.price18

Normalization

price × 1000

Status

✅ Working

Goldika

Endpoint

https://api.goldika.ir/api/public/price

Uses

data.price.buy

Status

✅ Working

WallGold

Endpoint

https://api.wallgold.ir/api/v1/price?side=buy&symbol=GLD_18C_750TMN

Uses

result.price

Normalization

price × 10

Status

✅ Working

Taline

Status

HTML parser exists

Currently unstable

Returns ERROR when unavailable

Daric

Endpoint responds inconsistently.

Frequent timeout.

Currently ignored.

Calculation Logic

Fair price is calculated from

World Gold
USD Sell

Current implementation multiplies calculated fair value by 10 to match Iranian market units.

Outputs

Fair Price
Lowest Market Price
Premium %
Persistence
src/persistence/state.py

Current implementation

load_state()

save_state()

State stored as

state.json

Current issue

GitHub Actions creates a fresh runner every execution.

Therefore

state.json

does not persist between workflow runs.

Persistence must be redesigned using GitHub Artifacts or GitHub Cache.

Email

Provider

Resend

Status

✅ Working

Current sender

onboarding@resend.dev

Recipient

Repository Secret

EMAIL_TO

API Key

Repository Secret

RESEND_API_KEY

HTML email contains

Fair Price
Every platform
Lowest Market
Premium
World Gold
USD Sell
Workflow

Runs every

30 minutes

Workflow

.github/workflows/gold-monitor.yml
Design Rules

Collectors only collect.

Collectors never calculate.

Collectors never send email.

Calculators never access APIs.

Alerts never calculate.

Persistence never performs calculations.

Each module owns exactly one responsibility.

Current Technical Debt

Persist state across GitHub Actions runs.

Priority: HIGH

Finish Taline collector.

Priority: HIGH

Replace Daric if timeout persists.

Priority: MEDIUM

Move from single HTML email to reusable email template.

Priority: LOW

Rename

caluclator

to

calculator

after project stabilizes.

Priority: LOW

Immediate Next Milestone

Implement persistent state using GitHub Artifacts.

Goal

Run N
↓

Load previous state

↓

Compare current premium vs previous premium

↓

Send alerts only when meaningful change occurs

↓

Save updated state for next execution
