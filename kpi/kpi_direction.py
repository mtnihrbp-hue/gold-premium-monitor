"""KPI -- SP-D Direction: the panel, its ledger, and the /Direction message.

The owner's question (2026-10-03): where does 18K's uptrend stand -- convert rial into gold
now, or wait? The answer must be evidence, not opinion, so the load-bearing properties
are about honesty:

- standard indicators are TA-Lib's, not hand-rolled;
- nothing uses the future: a swing counts once confirmed, a leg once the reversal
  happened, an outcome once it happened, and today's live price never enters a
  historical count;
- the stall clock and the rally end are the tested definitions (SP_D_HANDOFF.md section 4);
- every forecast shown is stored before its outcome, resolved against tgju's candles
  only, and demoted when its live record stops beating the plain base rate;
- Direction is evidence: no BUY/SELL authority; /Direction reads a stored panel and
  writes nothing; the message keeps UPDATE's vocabulary and fits one Telegram message.
"""

import inspect
import math
import os
import re
import sys
import unittest
from datetime import date, datetime, timedelta

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, SRC_DIR)

import numpy as np

from caluclator import technical as t
from analysis import direction as d
from analysis import direction_ledger as ledger

BANNED = ("widening", "widened", "narrowing", "grew", "smaller", "falling", "dearer", "dearest",
          "deepening", "cheap")


def _series(values, start=date(2014, 1, 1)):
    """A daily series from closes; high and low 0.5% around the close."""
    dates = [start + timedelta(days=k) for k in range(len(values))]
    close = [float(v) for v in values]
    high = [v * 1.005 for v in close]
    low = [v * 0.995 for v in close]
    return dates, high, low, close


def _trend_up(n=400, rate=0.002, wiggle=0.01, period=17):
    return [100 * (1 + rate) ** k * (1 + wiggle * math.sin(k / period * 2 * math.pi)) for k in range(n)]


def _cycles(n=1200):
    """Rallies of 80 days (+0.4%/day) and corrections of 30 (-0.35%/day): 8% legs both ways."""
    v, out = 100.0, []
    for k in range(n):
        v *= 1.004 if k % 110 < 80 else 0.9965
        out.append(v * (1 + 0.004 * math.sin(k / 3)))
    return out


def _usd(n=1200):
    return _series([1000 * 1.001 ** k for k in range(n)])


def _panel(n=1200, live=None, now=None, upto=None):
    gold = _series(_cycles(n))
    if upto is not None:
        gold = tuple(x[:upto] for x in gold)
    usd = _usd(n)
    now = now or datetime.combine(gold[0][-1] + timedelta(days=1), datetime.min.time()) + timedelta(hours=9)
    return d.build_panel(gold, usd, live_price=live, live_at=now, now=now,
                         system={"final_decision": "WAIT", "valuation": "FAIR"})


class _Row:
    """A stored panel, as direction_ledger reads one."""
    def __init__(self, day, forecasts, outcomes, hour=9):
        self.local_date = day
        self.computed_at = datetime.combine(day, datetime.min.time()) + timedelta(hours=hour)
        self.forecasts = forecasts
        self.outcomes = outcomes


class KPIDirection(unittest.TestCase):

    # -- indicators and levels -----------------------------------------------------

    def test_01_moving_averages_are_ta_libs_and_correct(self):
        closes = [float(k) for k in range(1, 301)]
        averages = t.moving_averages(closes)
        self.assertEqual(set(averages), {20, 50, 200})
        self.assertAlmostEqual(averages[20][-1], sum(closes[-20:]) / 20)
        self.assertTrue(np.isnan(averages[200][198]), "no average before a full window")
        self.assertIn("talib.SMA", inspect.getsource(t.moving_averages))

    def test_02_rsi_is_bounded_and_ta_libs(self):
        values = t.rsi(_trend_up(300))
        finite = values[~np.isnan(values)]
        self.assertTrue(((finite >= 0) & (finite <= 100)).all())
        self.assertIn("talib.RSI", inspect.getsource(t.rsi))

    def test_03_trend_states(self):
        for series, expect in ((_trend_up(400), "UPTREND"),
                               ([100 * 0.998 ** k for k in range(400)], "DOWNTREND")):
            close = [float(v) for v in series]
            self.assertEqual(t.trend_state(close, t.moving_averages(close), len(close) - 1), expect)
        flat = [100 + 2 * math.sin(k / 9) for k in range(400)]
        self.assertEqual(t.trend_state(flat, t.moving_averages(flat), 399), "MIXED")
        short = [100.0] * 150
        self.assertIsNone(t.trend_state(short, t.moving_averages(short), 149))

    def test_04_a_swing_counts_only_once_confirmed(self):
        values = [100.0] * 300
        values[296] = 130.0                       # a peak 3 days before the end
        dates, high, low, close = _series(values)
        levels = t.swing_levels(high, low, upto=299)
        self.assertFalse(any(abs(lv["price"] - 130 * 1.005) < 1 for lv in levels),
                         "a swing 3 days old was used before its 5 confirming days")
        levels = t.swing_levels(high + [100.5] * 5, low + [99.5] * 5, upto=304)
        self.assertTrue(any(abs(lv["price"] - 130 * 1.005) < 1 for lv in levels))

    def test_05_levels_are_named_by_position_and_clustered(self):
        levels = [{"price": 90.0, "touches": 2, "last": 10}, {"price": 95.0, "touches": 1, "last": 20},
                  {"price": 110.0, "touches": 3, "last": 30}]
        supports, resistances = t.split_levels(levels, 100.0)
        self.assertEqual([lv["price"] for lv in supports], [95.0, 90.0], "nearest support first")
        self.assertEqual([lv["price"] for lv in resistances], [110.0])
        values = [100.0] * 60
        values[20], values[40] = 120.0, 121.0     # two highs 0.8% apart: one level, two touches
        dates, high, low, close = _series(values)
        merged = [lv for lv in t.swing_levels(high, low, upto=59) if lv["price"] > 110]
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["touches"], 2)

    def test_06_flat_or_flagged_candles_make_no_swing(self):
        values = [100.0] * 60
        values[30] = 130.0
        dates, high, low, close = _series(values)
        usable = [True] * 60
        usable[30] = False
        self.assertFalse(any(lv["price"] > 120 for lv in t.swing_levels(high, low, upto=59, usable=usable)))

    # -- legs and clocks -----------------------------------------------------------

    def test_07_rally_legs_never_use_later_days(self):
        close = _cycles(700)
        direction, start = t.rally_legs(close)
        for i in range(0, 700, 37):
            dir_i, start_i = t.rally_legs(close[:i + 1])
            self.assertEqual((dir_i[-1], start_i[-1]), (direction[i], start[i]), f"day {i}")
        since = t.days_since_high(close)
        for i in range(0, 700, 41):
            self.assertEqual(t.days_since_high(close[:i + 1])[-1], since[i])

    def test_08_a_rally_ends_8pct_below_its_peak(self):
        close = [100 * 1.01 ** k for k in range(30)]
        peak = close[-1]
        close += [peak * 0.95, peak * 0.93, peak * 0.919]
        direction, start = t.rally_legs(close)
        self.assertEqual(direction[-2], "up", "7% off the peak is still the rally")
        self.assertEqual(direction[-1], "down", "8% off the peak ends it")
        self.assertEqual(start[-1], 29, "the correction starts at the peak")
        self.assertEqual(t.RALLY_REVERSAL, 0.08)

    def test_09_the_stall_clock_is_the_tested_definition(self):
        source = inspect.getsource(d.build_panel)
        self.assertIn("s50[j] > s200[j]", source, "the stall clock counts major-uptrend days (SP_D_HANDOFF.md section 4)")
        self.assertIn("record_at[j] * (1 - RALLY_REVERSAL)", source, "ended = 8% below the 52-week high")
        p = _panel()
        for band in p.rally["ladder"]:
            self.assertLessEqual(band["resumed"] + band["ended"], 100.0001)
            self.assertGreater(band["cases"], 0)
        bands = [tuple(b) for b in d.STALL_BANDS]
        self.assertEqual([b[0] for b in bands[1:]], [b[1] + 1 for b in bands[:-1]], "bands must not overlap")

    # -- the panel -------------------------------------------------------------------

    def test_10_the_live_price_never_enters_a_historical_count(self):
        base = _panel()
        live = _panel(live=base.price * 1.03)
        self.assertEqual(live.price_source, "live")
        self.assertAlmostEqual(live.price, base.price * 1.03)
        self.assertEqual(base.rally["ladder"], live.rally["ladder"])
        self.assertEqual(base.position["gaps"].keys(), live.position["gaps"].keys())
        self.assertEqual(base.stance["record"]["all_higher_pct"], live.stance["record"]["all_higher_pct"])
        self.assertEqual(base.convert["years_costlier"], live.convert["years_costlier"])
        self.assertEqual(base.position["adx"], live.position["adx"], "ADX from completed candles only")
        self.assertEqual(base.position["atr_pct"], live.position["atr_pct"])

    def test_11_a_live_price_counts_only_on_a_later_day(self):
        gold = _series(_cycles(1200))
        same_day = datetime.combine(gold[0][-1], datetime.min.time()) + timedelta(hours=9)
        p = d.build_panel(gold, _usd(), live_price=999.0, live_at=same_day, now=same_day)
        self.assertEqual(p.price_source, "close", "the day's own candle exists; no provisional close")
        self.assertAlmostEqual(p.price, gold[3][-1])

    def test_12_the_live_price_is_the_platform_median_at_tgju_level(self):
        markets = {"A": {"price": 100.0, "status": "OK"}, "B": {"price": 102.0, "status": "OK"},
                   "C": {"price": 104.0, "status": "OK"}, "D": {"price": 50.0, "status": "STALE"}}
        self.assertAlmostEqual(d.live_gold_price(markets), 102.0 * (1 + d.TGJU_OFFSET_PCT / 100))
        self.assertIsNone(d.live_gold_price({}))

    def test_13_insufficient_history_is_not_an_answer(self):
        self.assertEqual(_panel(n=300).status, "INSUFFICIENT_DATA")

        class _Broken:
            def query(self, *a, **k):
                raise RuntimeError("no database")
        self.assertEqual(d.resolve_direction(_Broken()).status, "INSUFFICIENT_DATA")

    def test_14_tags_have_fixed_definitions(self):
        p = _panel()
        allowed = {"RECORD", "STRONG TREND", "STRETCHED", "STALLING", "CORRECTION", "DOLLAR-DRIVEN"}
        self.assertTrue(set(p.position["tags"]) <= allowed)
        self.assertEqual("STRETCHED" in p.position["tags"], p.position["dist"]["SMA20"] >= d.STRETCH_PCT)
        self.assertEqual("RECORD" in p.position["tags"], p.rally["days_since_high"] == 0)
        self.assertEqual("CORRECTION" in p.position["tags"], not p.rally["in_rally"])

    def test_15_waiting_for_a_dip(self):
        rise = np.array([100 * 1.004 ** k for k in range(60)])
        self.assertGreater(d._waited(rise, 0), 0, "no dip: the wait converts 20 days later, higher")
        dips = np.array([100.0] * 60)
        dips[5] = 96.0
        self.assertEqual(d._waited(dips, 0), -3.0, "the dip came: the wait saved the dip")

    def test_16_the_stance_rulebook_and_its_triggers(self):
        self.assertEqual([d.stance_label(s) for s in (4, 3, 2, 1, 0, -1, -2, -3)],
                         ["STRONG BULLISH", "STRONG BULLISH", "BULLISH", "NEUTRAL", "NEUTRAL",
                          "BEARISH", "BEARISH", "STRONG BEARISH"])
        p = _panel()
        st = p.stance
        self.assertEqual(st["label"], d.stance_label(st["score"]))
        for trig in st["triggers"]:
            self.assertIn(trig["to"], d.STANCES)
        self.assertGreater(st["record"]["cases"], 0, "a stance is shown with what followed it")

    def test_17_direction_has_no_decision_authority(self):
        for module in (d, t, ledger):
            source = inspect.getsource(module)
            for name in ("build_signal_state", "send_", "candidate_decision", "save_market_state"):
                self.assertNotIn(name, source, f"{module.__name__} reaches into decisions")
        self.assertNotIn("database", inspect.getsource(t), "a calculator must not open a session")

    # -- the ledger -------------------------------------------------------------------

    def test_18_a_forecast_resolves_only_after_its_horizon(self):
        dates = [date(2026, 1, 1) + timedelta(days=k) for k in range(30)]
        close = [100.0 + k for k in range(30)]
        f = {"key": "new_high_20d", "prob": 90.0, "base": 50.0, "record": 105.0, "from_date": "2026-01-05",
             "horizon": 20}
        self.assertIsNone(ledger.resolve_forecast(f, dates[:24], close[:24]), "19 candles after: not yet")
        self.assertTrue(ledger.resolve_forecast(f, dates, close)["hit"])
        r = {"key": "range_20d", "from_price": 104.0, "price": [100.0, 110.0, 130.0], "from_date": "2026-01-05",
             "horizon": 20}
        out = ledger.resolve_forecast(r, dates, close)
        self.assertEqual(out["close"], close[24])
        self.assertTrue(out["inside"])
        s = {"key": "stance_20d", "label": "BULLISH", "from_price": 104.0, "from_date": "2026-01-05",
             "horizon": 20}
        self.assertTrue(ledger.resolve_forecast(s, dates, close)["higher"])

    def test_19_the_gate_learns_then_judges(self):
        def rows(n, prob, hit):
            return [_Row(date(2026, 1, 1) + timedelta(days=k),
                         [{"key": "new_high_20d", "prob": prob, "base": 50.0}],
                         {"new_high_20d": {"hit": hit}}) for k in range(n)]
        self.assertEqual(ledger.assess(rows(10, 90.0, True))["new_high"]["state"], "LEARNING")
        self.assertEqual(ledger.assess(rows(40, 90.0, True))["new_high"]["state"], "OK")
        self.assertEqual(ledger.assess(rows(40, 90.0, False))["new_high"]["state"], "DEMOTED",
                         "90% that never happens must lose to a 50% base rate")

    def test_20_one_forecast_per_day_enters_the_record(self):
        day = date(2026, 1, 1)
        morning = _Row(day, [{"key": "new_high_20d", "prob": 90.0, "base": 50.0}], {"new_high_20d": {"hit": False}}, 3)
        noon = _Row(day, [{"key": "new_high_20d", "prob": 90.0, "base": 50.0}], {"new_high_20d": {"hit": True}}, 10)
        record = ledger.assess([morning, noon])
        self.assertEqual(record["new_high"]["n"], 1)
        self.assertEqual(record["new_high"]["hit_pct"], 100.0, "the later slot of the day is the one kept")

    def test_21_the_ledger_grades_against_tgju_not_our_platforms(self):
        source = inspect.getsource(ledger.resolve_pending)
        self.assertIn("load_series(session, GOLD)", source)
        for name in ("platform", "market_snapshots", "PriceObservation"):
            self.assertNotIn(name, source)

    def test_22_a_demoted_figure_leaves_the_message(self):
        from alerts.telegram_direction import build_direction_message
        p = _panel()
        p.outlook["new_high"]["prob"] = 93.0
        demoted = [_Row(date(2026, 1, 1) + timedelta(days=k), [{"key": "new_high_20d", "prob": 93.0, "base": 46.0}],
                        {"new_high_20d": {"hit": False}}) for k in range(40)]
        alarms = ledger.apply_gate(p, ledger.assess(demoted))
        self.assertTrue(alarms)
        text = re.sub(r"<[^>]+>", "", build_direction_message(p))
        self.assertNotIn("93 in 100", text)
        self.assertIn("base rate", text)
        self.assertIn("⚠", text)

    # -- the message and the wiring ------------------------------------------------------

    def test_23_the_message_keeps_the_vocabulary_and_fits_telegram(self):
        from alerts.telegram_direction import build_direction_message, VALUATION_WORDS
        p = _panel(live=None)
        p.convert.update({"cheapest": "Milli", "cheapest_price": 100.0, "most_expensive_price": 101.0,
                          "spread_pct": 1.0})
        html = build_direction_message(p)
        text = re.sub(r"</?[bi]>", "", html)
        for word in BANNED:
            self.assertNotIn(word, text.lower())
        self.assertLess(len(text), 1500, "read on a phone: a short message (owner, 2026-10-03)")
        self.assertIn("System", text)
        self.assertIn("Analyst", text)
        self.assertIn("heavily discounted", VALUATION_WORDS["CHEAP"])
        self.assertNotIn("CHEAP", text, "the internal valuation state is never shown raw")

    def test_23b_the_message_is_telegram_safe_html(self):
        # A raw "<" broke the v5 draft: Telegram rejects an unknown tag, and the line
        # after it vanished. Only <b> and <i> are used; "<", ">" and "&" never appear bare.
        from alerts.telegram_direction import build_direction_message
        html = build_direction_message(_panel())
        bare = re.sub(r"</?[bi]>", "", html)
        for char in "<>&":
            self.assertNotIn(char, bare)

    def test_23c_the_ema_cross_is_reported_with_its_measured_risk(self):
        import talib
        p = _panel()
        ema = p.position["ema"]
        close = np.array(_cycles(1200))
        self.assertEqual(ema["above"], bool(talib.EMA(close, 20)[-1] > talib.EMA(close, 50)[-1]))
        self.assertIsNotNone(ema["since_date"])
        self.assertGreater(ema["death_cross_cases"], 0)
        self.assertIsNotNone(ema["base_drop_pct"], "a conditional figure carries its base rate")

    def test_23d_trading_days_skip_friday(self):
        saturday = date(2026, 10, 3)
        self.assertEqual(d.trading_date(saturday, 5), date(2026, 10, 8), "Sun..Thu")
        self.assertEqual(d.trading_date(saturday, 6), date(2026, 10, 10), "Friday skipped")
        self.assertEqual(d.trading_date(saturday, 20), date(2026, 10, 26))

    def test_24_no_panel_yet_says_so(self):
        from alerts.telegram_direction import build_direction_message
        self.assertIn("No panel computed yet", build_direction_message(None))

    def test_25_direction_mode_is_read_only(self):
        import main
        source = inspect.getsource(main.main)
        direction_index = source.find("if direction_only:")
        self.assertGreater(direction_index, 0)
        self.assertGreater(source.find("get_market_prices()"), direction_index,
                           "the direction wing must return before prices are collected")
        report = inspect.getsource(main._send_direction_report)
        for name in ("save_", "resolve_direction", "build_panel", "commit"):
            self.assertNotIn(name, report, "/Direction renders the stored panel and writes nothing")

    def test_26_the_workflow_and_the_worker_declare_the_direction_wing(self):
        root = os.path.join(os.path.dirname(__file__), "..")
        wf = open(os.path.join(root, ".github", "workflows", "gold-monitor.yml"), encoding="utf-8").read()
        self.assertIn("- direction", wf)
        self.assertIn("DIRECTION_ONLY: ${{ github.event.inputs.mode == 'direction'", wf)
        worker = open(os.path.join(root, "src", "worker", "telegram-trigger.js"), encoding="utf-8").read()
        self.assertIn('triggerGitHub(env, "direction")', worker)

    def test_27_the_panel_is_computed_twice_a_day_once_per_slot(self):
        import main
        self.assertEqual(main.DIRECTION_SLOTS, (6, 13))
        utc = lambda h, m=0: datetime(2026, 10, 3, h, m)          # Tehran = UTC + 3:30
        self.assertIsNone(main._direction_slot(utc(2, 0)))         # 05:30 Tehran
        self.assertEqual(main._direction_slot(utc(2, 30)), "06:00")
        self.assertEqual(main._direction_slot(utc(9, 29)), "06:00")  # 12:59
        self.assertEqual(main._direction_slot(utc(9, 30)), "13:00")
        self.assertEqual(main._direction_slot(utc(17, 30)), "13:00")  # 21:00

    def test_28_a_stored_panel_round_trips_and_a_slot_is_stored_once(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from database.connection import Base
        from database import repository as repo
        from alerts.telegram_direction import build_direction_message
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine, expire_on_commit=False)()
        p = _panel()
        day = date(2026, 10, 3)
        self.assertIsNotNone(repo.save_direction_snapshot(session, p, day, "13:00"))
        self.assertIsNone(repo.save_direction_snapshot(session, p, day, "13:00"), "one panel per slot")
        row = repo.latest_direction_snapshot(session)
        back = d.DirectionPanel.from_json(row.panel)
        strip = lambda s: re.sub(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", "", s)
        self.assertEqual(strip(build_direction_message(back)), strip(build_direction_message(p)))
        self.assertEqual(row.stance, p.stance["label"])
        self.assertEqual(len(row.forecasts), 4)
        self.assertEqual(len(repo.pending_direction_snapshots(session)), 1)
        session.close()

    def test_29_the_migration_matches_the_model(self):
        from database.models import DirectionSnapshot
        root = os.path.join(os.path.dirname(__file__), "..", "sql")
        sql = open(os.path.join(root, "neon_migration_direction.sql"), encoding="utf-8").read()
        schema = open(os.path.join(root, "neon_schema.sql"), encoding="utf-8").read()
        for column in DirectionSnapshot.__table__.columns:
            self.assertRegex(sql, rf"(?m)^\s+{column.name} ", f"{column.name} missing from the migration")
        self.assertIn("UNIQUE (local_date, slot)", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS direction_snapshots", schema)
        executable = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
        self.assertNotRegex(executable, r"(?i)\b(ALTER|DROP|DELETE|UPDATE|INSERT)\b",
                            "additive only: no existing table or row is touched")

    def test_30_ta_lib_is_pinned(self):
        reqs = open(os.path.join(os.path.dirname(__file__), "..", "requirements.txt"), encoding="utf-8").read()
        self.assertRegex(reqs, r"(?m)^TA-Lib==\d+\.\d+\.\d+$")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(KPIDirection)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    total = result.testsRun
    passed = total - len(result.failures) - len(result.errors)
    print()
    print("=" * 55)
    print(f"DIRECTION KPI RESULT: {passed}/{total} PASS")
    print("=" * 55)
    sys.exit(0 if result.wasSuccessful() else 1)
