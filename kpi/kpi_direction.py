"""KPI -- SP-D Direction: trend, support/resistance, and the measured odds.

The owner's question (2026-10-03): is 18K going up or down, with what probability, and
where are support and resistance -- to decide when to convert rial into gold. The
answer must be evidence, not opinion, so the load-bearing properties are about honesty:

- standard indicators are TA-Lib's, not hand-rolled;
- nothing uses the future: a swing counts only once confirmed, an outcome only once it
  happened, and adding later data never changes an earlier day's view;
- levels are named by position: support below the price, resistance above;
- every conditional figure carries its sample size and the all-days base rate;
- the entry-timing measure is the real choice: wait for a dip, else convert later;
- Direction is evidence: no BUY/SELL authority, no instruction, and the message section
  stays a draft until the owner approves its layout.
"""

import inspect
import math
import os
import re
import sys
import unittest
from datetime import date, timedelta

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, SRC_DIR)

import numpy as np

from caluclator import technical as t
from analysis import direction as d


def _series(values, start=date(2014, 1, 1)):
    """A daily series from closes; high and low 0.5% around the close."""
    dates = [start + timedelta(days=k) for k in range(len(values))]
    close = [float(v) for v in values]
    high = [v * 1.005 for v in close]
    low = [v * 0.995 for v in close]
    return dates, high, low, close


def _trend_up(n=400, rate=0.002, wiggle=0.01, period=17):
    return [100 * (1 + rate) ** k * (1 + wiggle * math.sin(k / period * 2 * math.pi)) for k in range(n)]


class KPIDirection(unittest.TestCase):

    # -- indicators ------------------------------------------------------------

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

    # -- support and resistance --------------------------------------------------

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
        self.assertTrue(all(lv["price"] < 100 for lv in supports))

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

    # -- the odds ------------------------------------------------------------------

    def test_07_later_data_never_changes_an_earlier_view(self):
        dates, high, low, close = _series(_trend_up(900))
        early = d.build_view(dates[:700], high[:700], low[:700], close[:700])
        full = d.build_view(dates, high, low, close, i=699)
        self.assertEqual(early.status, "OK")
        for h in d.HORIZONS:
            self.assertEqual((early.odds[h].cases, early.odds[h].higher_pct),
                             (full.odds[h].cases, full.odds[h].higher_pct),
                             f"the {h}-day odds of day 699 used data after it")
        self.assertEqual([lv.price for lv in early.supports], [lv.price for lv in full.supports])

    def test_08_an_outcome_counts_only_once_it_happened(self):
        dates, high, low, close = _series(_trend_up(700))
        view = d.build_view(dates, high, low, close)
        last = len(close) - 1
        for h in d.HORIZONS:
            # every counted case j must satisfy j + h <= last: at most last - h + 1 days
            self.assertLessEqual(view.baseline[h].cases, last - h + 1)

    def test_09_every_conditional_figure_has_its_base_rate_and_sample(self):
        dates, high, low, close = _series(_trend_up(900))
        view = d.build_view(dates, high, low, close)
        for h in d.HORIZONS:
            self.assertIn(h, view.baseline)
            self.assertGreater(view.odds[h].cases, 0)
            self.assertGreater(view.odds[h].episodes, 0)
        self.assertTrue(view.condition)

    def test_10_too_few_similar_cases_widen_the_condition(self):
        dates, high, low, close = _series(_trend_up(900))
        view = d.build_view(dates, high, low, close)
        original = d.MIN_CASES
        d.MIN_CASES = 10 ** 6
        try:
            wide = d.build_view(dates, high, low, close)
        finally:
            d.MIN_CASES = original
        self.assertEqual(wide.condition, "uptrend")
        self.assertGreaterEqual(wide.odds[20].cases, view.odds[20].cases)

    def test_11_insufficient_history_is_not_an_answer(self):
        dates, high, low, close = _series(_trend_up(200))
        self.assertEqual(d.build_view(dates, high, low, close).status, "INSUFFICIENT_DATA")

        class _Broken:
            def query(self, *a, **k):
                raise RuntimeError("no database")
        self.assertEqual(d.resolve_direction(_Broken()).status, "INSUFFICIENT_DATA")

    # -- entry timing ------------------------------------------------------------

    def test_12_waiting_for_a_dip_in_a_steady_rise_costs(self):
        """Never dips: the wait always ends converting 20 days later, at a higher price."""
        close = [100 * 1.004 ** k for k in range(60)]
        option = d.measure_entry(close, list(range(30)), 3.0)
        self.assertEqual(option.reached_pct, 0)
        self.assertLess(option.mean_saving_pct, 0)

    def test_13_waiting_for_a_dip_that_comes_saves_the_dip(self):
        close = [100.0] * 60
        for k in range(5, 60, 10):
            close[k] = 96.0                           # a 4% dip every 10 days
        cases = [j for j in range(30) if close[j] == 100.0]   # starting on a dip is another case
        option = d.measure_entry(close, cases, 3.0)
        self.assertEqual(option.reached_pct, 100)
        self.assertAlmostEqual(option.mean_saving_pct, 3.0)

    # -- evidence, not decision ----------------------------------------------------

    def test_14_direction_has_no_decision_authority(self):
        for module in (d, t):
            source = inspect.getsource(module)
            for name in ("final_decision", "build_signal_state", "send_", "candidate_decision"):
                self.assertNotIn(name, source, f"{module.__name__} reaches into decisions")
        self.assertNotIn("database", inspect.getsource(t), "a calculator must not open a session")

    def test_15_the_section_counts_and_does_not_instruct(self):
        from alerts.telegram_direction import build_direction_section
        dates, high, low, close = _series(_trend_up(900))
        text = re.sub(r"</?[bi]>", "", build_direction_section(d.build_view(dates, high, low, close)))
        self.assertIn("historical record, not a forecast", text)
        self.assertIn("all days:", text, "a conditional figure without its base rate")
        self.assertRegex(text, r"In \d+ similar days")
        for word in ("cheap", "buy ", "sell ", "should", "recommend", "now is"):
            self.assertNotIn(word, text.lower())

    def test_16_the_section_is_a_draft_until_approved(self):
        import alerts.telegram_analyze as analyze
        self.assertNotIn("build_direction_section", inspect.getsource(analyze))
        import main
        self.assertNotIn("telegram_direction", inspect.getsource(main))

    def test_17_ta_lib_is_pinned(self):
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
