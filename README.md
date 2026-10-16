# Gold Premium Monitor

Decision support for the Iranian 18K physical-gold market. It collects eleven Iranian platforms' prices,
world gold and the dollar. From them it computes fair value and the discount, reads the trend and the
chart, and tells one reader on Telegram where, when and how much, with the evidence for each. It is not
a trading bot and executes nothing.

## What it sends

| Message | When |
|---|---|
| UPDATE | `/Update`: the current discount, its rank, the deep-discount level, the platforms |
| ANALYZE | `/Analyze`: what the record shows at this level |
| DIRECTION | `/Direction`: the trend, buy now or wait, support and resistance, what to watch, gold demand |
| The room's report and chart | 21:00 Tehran: the PAPER portfolio's posture, gold or fixed income, and the day's chart with its levels and patterns |
| The room's trades | when the room moves between gold and fixed income |
| BUY | when the decision engine's final decision is BUY, after its confirmation |

The deep-discount push and the daily recap are parked. `PROJECT_MEMORY.md` section 3 has the state of
each surface.

## How it runs

- **Workflow.** GitHub Actions, `gold-monitor.yml`, in four modes (UPDATE, ANALYZE, REPORT, DIRECTION).
  Every run is production: it uses the repository's secrets, writes to Neon and sends Telegram
  messages, whatever branch it runs from.
- **Scheduling.** cron-job.org runs ANALYZE hourly, 06:00-21:00 Tehran. A Cloudflare worker turns
  Telegram commands into runs.
- **Storage.** Neon Postgres, on the free plan.
- **The phone.** It reads what GitHub's runner cannot reach (Daric, TSETMC's money flow) and writes
  it to Neon.
- **More.** `PROJECT_OPERATIONS.md`.

## Run and test

```text
pip install -r requirements.txt
python src/main.py              a manual UPDATE-style run (needs the variables below)
python tests/run_all.py         the unit tests, 18 files
python kpi/run_all.py           the KPI suite, 30 files; the regression check before any merge
python -m compileall src
```

Both runners use an in-memory database and cannot reach production. CI (`kpi-suite.yml`) runs them on
`main`, SP-D and pull requests.

Variables:
- `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `RESEND_API_KEY`, `EMAIL_TO`;
- `SCHEDULED_RUN=true` for the scheduled path.

## Repository

```text
src/collector/     the platforms, world gold, the dollar, tgju, tablokhani, etfbaz, news
src/validation/    the gates before a value is used, the stale-quote rules among them
src/caluclator/    fair value, premium, valuation, momentum, decisions, the chartist, the patterns (sic)
src/analysis/      the scheduled analysis, Direction, PAPER and the room, gold demand, the push
src/alerts/        the Telegram and email messages, the chart
src/database/      Neon's models and repository
src/persistence/   state.json, the spool, the candle cache
src/seed/          histories production cannot fetch
iran_node/         the Iran-side reader on the owner's phone
kpi/  tests/       the acceptance specifications and the unit tests
sql/               the target schema and the migrations
research/          the studies behind each decision; their data is git-ignored
archive/           superseded documents, unchanged
```

## Documentation

Start with `PROJECT_MEMORY.md`: the system as it runs, and the reading order for everything else.
`DOCUMENTATION_INDEX.md` says which file owns what.
