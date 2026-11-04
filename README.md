# The forward test's ledger

This branch holds the forward test of the E-8 candidate, frozen on 2026-10-30 (`SP_D_HANDOFF.md` sections 77.7-77.8,
79, 82, 83 and 89-90 on `main`). It shares no history with `main` and is never merged.

- `data/shadow_ledger_v2.jsonl`: **version 2, from 2026-11-04** (`SP_D_HANDOFF.md` 94): version 1 with the real
  dollar's CPI carried forward up to three months while the IMF has not published the month two before. One line
  per closed Tehran day, the rule's state and its forecasts, written before the day's outcome exists. A line
  marked `"late"` was written after its day, from the data up to that day only.
- `data/shadow_ledger.jsonl`: version 1's five lines, 2026-10-29 to 2026-11-03, closed. Kept as written.
- Each new line is one commit, made by `.github/workflows/forward-test.yml` on `main` after the 06:00 Tehran run.
  The commit's time is the public record that the line came before its outcome. No ledger line is edited by hand.
- The other files are the engine's inputs as of the last line:
  - refreshed by each run: `tgju_more.json` (tgju), `gvz.csv` and `vix.csv` (CBOE), `macro.json` (the IMF's CPI);
  - frozen as of 2026-10-30, copied from the owner's workstation: `calm_forecasts_b.json` (the calm forecasts
    before the test), `flows_daily.json` (the funds' flows, read from inside Iran) and `news_days.jsonl` (the
    news labels).
- The first line, for 2026-10-29, was written on the workstation on 2026-10-30. From 2026-11-01 the lines are
  written on GitHub's runner.
- Version 2's first verdict is on 2027-06-21 (31 Khordad 1406). Nothing in the rule changes before then; a change
  opens a new version with its own ledger file and date.
