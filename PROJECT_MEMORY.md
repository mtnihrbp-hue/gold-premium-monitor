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
