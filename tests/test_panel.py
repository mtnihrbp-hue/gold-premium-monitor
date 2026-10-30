"""The research table never uses a later day (SP_D_HANDOFF.md section 72; KPI Eb-2).

A row built from the data up to a day must equal the same row built from all the data: adding later days
changes nothing before them (the brief of 2026-10-21, 6.3). World gold enters from the day before; a day's money
flow is never carried to another day; the seed's flow gap stays empty.
"""

import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "research"))

import build_panel as bp  # noqa: E402


def _inputs(last):
    """A synthetic history to `last`: each series' value names its own day, so a leak shows."""
    start = date(2021, 9, 1)
    days = [start + timedelta(days=k) for k in range((last - start).days + 1)]
    trading = [d for d in days if d.weekday() != 4]                  # no Friday for 18K
    tgju = {"geram18": [(d, 1000.0 + d.toordinal() % 1000) for d in trading],
            "price_dollar_rl": [(d, 50.0 + d.toordinal() % 7) for d in trading],
            "ons": [(d, 2000.0 + d.toordinal() % 500) for d in days if d.weekday() not in (5, 6)],
            "sekee": [(d, 11000.0 + d.toordinal() % 900) for d in trading],
            "crypto-tether-irr": [(d, 51.0 + d.toordinal() % 5) for d in days]}
    fi = [(d, 1.0 + d.toordinal() % 100 / 1000) for d in trading]
    ted = [(d, 100.0 + d.toordinal() % 50) for d in trading]
    flows = [(d, 0.5 + d.toordinal() % 9 / 10) for d in trading if d.weekday() != 3]   # no flow on Thursdays
    return tgju, fi, ted, flows, {}


class TestPanel(unittest.TestCase):

    def test_a_row_does_not_change_when_later_days_are_added(self):
        cut = date(2021, 10, 30)
        short = {r["date"]: r for r in bp.build(*_inputs(cut))}
        full = {r["date"]: r for r in bp.build(*_inputs(date(2021, 12, 31)))}
        self.assertTrue(short)
        for day, row in short.items():
            self.assertEqual(row, full[day], day)

    def test_world_gold_enters_from_the_day_before(self):
        tgju, fi, ted, flows, news = _inputs(date(2021, 11, 30))
        ons = dict(tgju["ons"])
        for row in bp.build(tgju, fi, ted, flows, news):
            day = date.fromisoformat(row["date"])
            earlier = [d for d in ons if d < day]
            if not earlier:
                self.assertIsNone(row["ons_prev"], "nothing known before the first day")
                continue
            self.assertEqual(row["ons_prev"], ons[max(earlier)], day)

    def test_a_days_flow_is_never_carried(self):
        tgju, fi, ted, flows, news = _inputs(date(2021, 11, 30))
        for row in bp.build(tgju, fi, ted, flows, news):
            if date.fromisoformat(row["date"]).weekday() == 3:
                self.assertIsNone(row["flow_power"], row["date"])

    def test_the_seeds_flow_gap_stays_empty(self):
        tgju, fi, ted, flows, news = _inputs(date(2021, 10, 20))
        rows = {r["date"]: r for r in bp.build(tgju, fi, ted, flows, news)}
        self.assertIsNone(rows["2021-10-17"]["flow_power"], "inside the 2019-10 to 2021-10 gap")
        self.assertIsNotNone(rows["2021-10-18"]["flow_power"], "the first day after it")


if __name__ == "__main__":
    unittest.main()
