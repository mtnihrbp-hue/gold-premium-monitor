# Gold Premium Monitor

## Objective
Monitor the premium of gold in Iran by comparing:
- World gold ounce price (USD/oz)
- USD/IRR free market sell rate (Bonbast)
- Calculate theoretical gold value
- Calculate premium
- Send email every 30 minutes

## Current Architecture

src/
    collector/
        kitco.py        # World gold price
        bonbast.py      # USD/IRR sell rate
    calculator.py
    notifier/
        email.py
    main.py

## Data Sources

World Gold:
- Kitco (or replacement if Kitco changes)

USD/IRR:
- Bonbast.com

## Constraints

- Open-source only
- No paid APIs
- Runs on GitHub Actions
- Email notification
- No local server

## Current Status

✔ GitHub Actions working
✔ Email configured
✔ Workflow scheduled
✔ Kitco collector implemented
❌ Bonbast collector not finalized

## Rules

- Keep collectors independent.
- Never mix world gold logic with Bonbast logic.
- Replace a collector only if its source becomes permanently unavailable.
- Kitco → World gold price.
Bonbast → USD/IRR sell rate.
Milli or Taline → Actual tradable 18K gold price (the price you can execute at).
Do not use Bonbast's gold price for trading decisions.



ok, lets go
so another thing we should do is to get IRAN 18Gold Price per gram from milli and taline and so on you rememebr, we locked the arch as below i guess, 

gold-premium-monitor
│
├── config
│   └── config.json
│
├── src
│   ├── main.py
│   ├── collectors
│   │      ├── kitco.py
│   │      ├── bonbast.py
│   │      ├── iran.py
│   │      └── common.py
│   │
│   ├── calculators
│   │      └── gold.py
│   │
│   ├── alerts
│   │      └── gmail.py
│   │
│   ├── persistence
│   │      └── state.py
│   │
│   └── utils
│          ├── logger.py
│          └── validator.py
│
├── tests
│
├── requirements.txt
└── .github
    └── workflows
        └── gold-monitor.yml

Milli_Gold Price == https://milli.gold/api/v1/public/milli-price/external
Goldika Gold Price == https://api.goldika.ir/api/public/price
Darik Gold Price == https://apisc.daric.gold/loan/api/v1/User/Collateral/GetGoldlPrice
Wall Gold Price == https://api.wallgold.ir/api/v1/price?side=buy&symbol=GLD_18C_750TMN










-----------------------

# Gold Premium Monitor

## Objective

Continuously monitor the Iranian 18K gold market by comparing the theoretical fair value (derived from the world gold price and USD/IRR exchange rate) with executable prices from Iranian online gold platforms.

The system sends:
- Daily market report
- Trading opportunity alerts

---

# Current Status

## Infrastructure

✅ GitHub repository operational

✅ GitHub Actions operational

✅ Scheduled workflow operational

---

## Data Collectors

### World Gold

Collector:
kitco.py

Status:
Working

Purpose:
Retrieve live world gold ounce price (USD/oz).

---

### USD / IRR

Collector:
bonbast.py

Status:
Working

Implementation:
SamadiPour/bonbast package

Purpose:
Retrieve Bonbast USD Sell rate.

---

### Iranian Gold Platforms

Status:
Research completed.

Confirmed sources:

- Milli
- Goldika
- Daric
- WallGold
- Taline

Known endpoints:

Milli
https://milli.gold/api/v1/public/milli-price/external

Goldika
https://api.goldika.ir/api/public/price

Daric
https://apisc.daric.gold/loan/api/v1/User/Collateral/GetGoldlPrice

WallGold
https://api.wallgold.ir/api/v1/price?side=buy&symbol=GLD_18C_750TMN

Taline
HTML parser available.

Implementation pending.

---

# Architecture

gold-premium-monitor

config/

src/

    collectors/

        kitco.py

        bonbast.py

        iran.py

    calculators/

        gold.py

    alerts/

        gmail.py

    persistence/

        state.py

    utils/

tests/

.github/

---

# Design Rules

Collectors only collect.

Collectors never perform calculations.

Collectors never send email.

Calculators never access websites.

Alerts never perform calculations.

Every module has exactly one responsibility.

---

# Iranian Market Logic

The monitor is NOT intended to report Bonbast gold prices.

Bonbast is ONLY the exchange-rate source.

Tradable prices MUST come from Iranian online trading platforms.

Priority sources:

1. Milli

2. Goldika

3. Daric

4. WallGold

5. Taline

---

# Trading Logic

Collect prices from every available platform.

Ignore unavailable platforms.

Select the lowest executable price.

Compare against calculated fair value.

Compute:

- Fair Value
- Lowest Tradable Price
- Premium %
- Spread between platforms

---

# Notifications

## Daily Report

Schedule:

18:00 Iran Time

Always send.

Contents:

- World Gold
- USD Sell
- Fair Value
- Every platform price
- Lowest platform
- Premium
- Platform spread

---

## Trading Alert

Schedule:

Every 3 hours

12:00

15:00

18:00

21:00

Trigger:

Premium exceeds configured threshold.

Condition must persist for configured consecutive runs.

---

# Constraints

Python 3.12

GitHub Actions

Open-source only

No paid APIs

No browser automation unless absolutely necessary.

Official APIs preferred.

JSON endpoints preferred.

HTML scraping is the final fallback.

---

# Next Milestone

Implement iran.py.

Responsibilities:

- Query every supported platform.

- Normalize returned prices.

- Return:

{
    "milli": ...,
    "goldika": ...,
    "daric": ...,
    "wallgold": ...,
    "taline": ...
}

No calculations.

No alerting.

No persistence.















