"""KPI — SP-C.1: Bubble position against its own recent distribution.

Verifies the relative valuation primitive that replaces the fixed thresholds. The
fixed buy_premium_percent was never crossed in 278 production readings, so
valuation carried no information; this measures the bubble against a rolling
reference instead.

Scope boundary: this primitive reports position and observed history only. It must
never emit a BUY/WAIT/SELL decision.
"""

import os
import sys
import unittest
from datetime import datetime, timedelta

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, SRC_DIR)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import database.connection as db_conn

_TEST_ENGINE = create_engine("sqlite:///:memory:", echo=False)
_TestSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=_TEST_ENGINE, expire_on_commit=False
)


def _test_get_session():
    return _TestSessionLocal()


db_conn.get_session = _test_get_session
import database.repository as _repo_module
_repo_module.get_session = _test_get_session

from database.models import Base, MarketSnapshot
Base.metadata.create_all(bind=_TEST_ENGINE)

from analysis.bubble_position import (
    resolve_bubble_position,
    resolve_similar_outcomes,
    MIN_OBSERVATIONS,
    UNUSUAL_Z,
    NOTABLE_Z,
)

NOW = datetime(2026, 9, 13, 12, 0, 0)


def _reset():
    session = _test_get_session()
    session.query(MarketSnapshot).delete()
    session.commit()
    session.close()


def _seed(premiums, start=None, step_hours=1):
    """Insert readings backwards from NOW so the newest is last."""
    session = _test_get_session()
    base = start or (NOW - timedelta(hours=step_hours * len(premiums)))
    for index, premium in enumerate(premiums):
        session.add(MarketSnapshot(
            timestamp=base + timedelta(hours=step_hours * index),
            fair_price=100.0,
            premium_percent=premium,
            world_gold_usd=4000.0,
            usd_irr=200000.0,
        ))
    session.commit()
    session.close()


class KPISPC1(unittest.TestCase):

    def setUp(self):
        _reset()

    # --- position ---------------------------------------------------------

    def test_01_insufficient_data_below_minimum(self):
        _seed([-4.0] * (MIN_OBSERVATIONS - 1))
        pos = resolve_bubble_position(_test_get_session(), now=NOW)
        self.assertEqual(pos.zone, "INSUFFICIENT_DATA")
        self.assertEqual(pos.confidence, "INSUFFICIENT_DATA")

    def test_02_no_data_is_insufficient_not_zero(self):
        pos = resolve_bubble_position(_test_get_session(), now=NOW)
        self.assertEqual(pos.zone, "INSUFFICIENT_DATA")
        self.assertIsNone(pos.z_score)
        self.assertIsNone(pos.average)

    def test_03_missing_session_does_not_raise(self):
        pos = resolve_bubble_position(None, now=NOW)
        self.assertEqual(pos.zone, "INSUFFICIENT_DATA")

    def test_04_average_and_spread_reported(self):
        _seed([-4.0] * 40)
        pos = resolve_bubble_position(_test_get_session(), now=NOW)
        self.assertAlmostEqual(pos.average, -4.0, places=3)
        self.assertAlmostEqual(pos.spread, 0.0, places=3)

    def test_05_normal_range_is_average_plus_minus_spread(self):
        _seed([-5.0, -3.0] * 20)
        pos = resolve_bubble_position(_test_get_session(), now=NOW)
        self.assertAlmostEqual(pos.normal_low, pos.average - pos.spread, places=3)
        self.assertAlmostEqual(pos.normal_high, pos.average + pos.spread, places=3)

    def test_06_zero_spread_yields_no_z_score(self):
        _seed([-4.0] * 40)
        pos = resolve_bubble_position(_test_get_session(), now=NOW)
        self.assertIsNone(pos.z_score)

    def test_07_deeper_discount_is_negative_z(self):
        _seed([-5.0, -3.0] * 20)
        pos = resolve_bubble_position(_test_get_session(), current_bubble=-6.0, now=NOW)
        self.assertLess(pos.z_score, 0)

    def test_08_shallower_discount_is_positive_z(self):
        _seed([-5.0, -3.0] * 20)
        pos = resolve_bubble_position(_test_get_session(), current_bubble=-2.0, now=NOW)
        self.assertGreater(pos.z_score, 0)

    def test_09_very_cheap_zone(self):
        _seed([-5.0, -3.0] * 20)
        pos = resolve_bubble_position(_test_get_session(), now=NOW)
        far = pos.average - (UNUSUAL_Z + 0.5) * pos.spread
        cheap = resolve_bubble_position(_test_get_session(), current_bubble=far, now=NOW)
        self.assertEqual(cheap.zone, "VERY_CHEAP")

    def test_10_very_expensive_zone(self):
        _seed([-5.0, -3.0] * 20)
        pos = resolve_bubble_position(_test_get_session(), now=NOW)
        far = pos.average + (UNUSUAL_Z + 0.5) * pos.spread
        pricey = resolve_bubble_position(_test_get_session(), current_bubble=far, now=NOW)
        self.assertEqual(pricey.zone, "VERY_EXPENSIVE")

    def test_11_normal_zone_near_average(self):
        _seed([-5.0, -3.0] * 20)
        pos = resolve_bubble_position(_test_get_session(), now=NOW)
        near = resolve_bubble_position(
            _test_get_session(), current_bubble=pos.average, now=NOW
        )
        self.assertEqual(near.zone, "NORMAL")

    def test_12_cheap_zone_between_thresholds(self):
        _seed([-5.0, -3.0] * 20)
        pos = resolve_bubble_position(_test_get_session(), now=NOW)
        mid = pos.average - ((NOTABLE_Z + UNUSUAL_Z) / 2) * pos.spread
        cheap = resolve_bubble_position(_test_get_session(), current_bubble=mid, now=NOW)
        self.assertEqual(cheap.zone, "CHEAP")

    def test_13_confidence_low_on_short_coverage(self):
        _seed([-5.0, -3.0] * 20)
        pos = resolve_bubble_position(_test_get_session(), now=NOW)
        self.assertEqual(pos.confidence, "LOW")

    def test_14_current_bubble_override_is_used(self):
        _seed([-5.0, -3.0] * 20)
        pos = resolve_bubble_position(_test_get_session(), current_bubble=-7.5, now=NOW)
        self.assertEqual(pos.bubble, -7.5)

    def test_15_drift_stable_when_mean_holds(self):
        _seed([-5.0, -3.0] * 20)
        pos = resolve_bubble_position(_test_get_session(), now=NOW)
        self.assertEqual(pos.drift, "STABLE")

    def test_16_drift_detects_moving_reference(self):
        _seed([-6.0] * 20 + [-2.0] * 20)
        pos = resolve_bubble_position(_test_get_session(), now=NOW)
        self.assertEqual(pos.drift, "TOWARD_LESS_DISCOUNT")

    def test_17_window_excludes_older_readings(self):
        old = NOW - timedelta(days=200)
        _seed([-9.0] * 40, start=old, step_hours=1)
        _seed([-4.0] * 40, start=NOW - timedelta(hours=40), step_hours=1)
        pos = resolve_bubble_position(_test_get_session(), window_days=30, now=NOW)
        self.assertAlmostEqual(pos.average, -4.0, places=3)

    def test_18_position_never_emits_a_decision(self):
        _seed([-5.0, -3.0] * 20)
        pos = resolve_bubble_position(_test_get_session(), now=NOW)
        values = {str(v) for v in vars(pos).values()}
        for forbidden in ("BUY", "SELL", "WAIT"):
            self.assertNotIn(forbidden, values)

    # --- similar outcomes -------------------------------------------------

    def test_19_outcomes_insufficient_without_history(self):
        out = resolve_similar_outcomes(
            _test_get_session(), current_bubble=-4.0, spread=1.0, now=NOW
        )
        self.assertEqual(out.status, "INSUFFICIENT_DATA")

    def test_20_outcomes_require_a_spread(self):
        _seed([-4.0] * 40)
        out = resolve_similar_outcomes(
            _test_get_session(), current_bubble=-4.0, spread=None, now=NOW
        )
        self.assertEqual(out.status, "INSUFFICIENT_DATA")

    def test_21_discount_growing_counts_as_cheaper(self):
        # Each reading is followed 24h later by a deeper discount.
        start = NOW - timedelta(days=20)
        premiums = []
        for _ in range(20):
            premiums.extend([-4.0, -5.0])
        _seed(premiums, start=start, step_hours=24)
        out = resolve_similar_outcomes(
            _test_get_session(), current_bubble=-4.0, spread=1.0,
            horizon_hours=24, now=NOW,
        )
        self.assertGreater(out.became_cheaper, 0)
        self.assertLess(out.average_move_pp, 0)

    def test_22_discount_shrinking_counts_as_pricier(self):
        start = NOW - timedelta(days=20)
        premiums = []
        for _ in range(20):
            premiums.extend([-5.0, -4.0])
        _seed(premiums, start=start, step_hours=24)
        out = resolve_similar_outcomes(
            _test_get_session(), current_bubble=-5.0, spread=1.0,
            horizon_hours=24, now=NOW,
        )
        self.assertGreater(out.became_pricier, 0)
        self.assertGreater(out.average_move_pp, 0)

    def test_23_tiny_moves_count_as_unchanged(self):
        start = NOW - timedelta(days=20)
        premiums = []
        for _ in range(20):
            premiums.extend([-4.00, -4.01])
        _seed(premiums, start=start, step_hours=24)
        out = resolve_similar_outcomes(
            _test_get_session(), current_bubble=-4.0, spread=1.0,
            horizon_hours=24, now=NOW,
        )
        self.assertEqual(out.became_cheaper, 0)
        self.assertEqual(out.became_pricier, 0)
        self.assertGreater(out.unchanged, 0)

    def test_24_readings_outside_the_band_are_excluded(self):
        start = NOW - timedelta(days=20)
        _seed([-9.0] * 40, start=start, step_hours=12)
        out = resolve_similar_outcomes(
            _test_get_session(), current_bubble=-3.0, spread=0.2,
            horizon_hours=24, now=NOW,
        )
        self.assertEqual(out.status, "INSUFFICIENT_DATA")

    def test_25_counts_sum_to_cases(self):
        start = NOW - timedelta(days=25)
        premiums = []
        for index in range(25):
            premiums.extend([-4.0, -4.0 - (index % 3) * 0.4])
        _seed(premiums, start=start, step_hours=24)
        out = resolve_similar_outcomes(
            _test_get_session(), current_bubble=-4.0, spread=1.0,
            horizon_hours=24, now=NOW,
        )
        self.assertEqual(
            out.cases, out.became_cheaper + out.became_pricier + out.unchanged
        )

    def test_26_no_future_leakage_into_the_past(self):
        # A horizon longer than the whole series can never resolve an outcome.
        start = NOW - timedelta(days=5)
        _seed([-4.0] * 40, start=start, step_hours=3)
        out = resolve_similar_outcomes(
            _test_get_session(), current_bubble=-4.0, spread=1.0,
            horizon_hours=24 * 365, now=NOW,
        )
        self.assertEqual(out.status, "INSUFFICIENT_DATA")

    def test_27_outcomes_never_emit_a_decision(self):
        start = NOW - timedelta(days=20)
        _seed([-4.0, -5.0] * 20, start=start, step_hours=24)
        out = resolve_similar_outcomes(
            _test_get_session(), current_bubble=-4.0, spread=1.0, now=NOW
        )
        values = {str(v) for v in vars(out).values()}
        for forbidden in ("BUY", "SELL", "WAIT"):
            self.assertNotIn(forbidden, values)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(KPISPC1)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print("\n" + "=" * 55)
    print(f"SP-C.1 KPI RESULT: {passed}/{result.testsRun} PASS")
    print("=" * 55)
    sys.exit(0 if result.wasSuccessful() else 1)
