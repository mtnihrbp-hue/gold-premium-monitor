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

from update.baseline_resolver import (
    _get_latest_market_snapshot,
    _get_earliest_market_snapshot_today,
)
from analysis.bubble_position import (
    resolve_bubble_trend,
    resolve_bubble_speed,
    resolve_zone_episodes,
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


    # --- percentile and bands ---------------------------------------------

    def test_28_percentile_at_the_extremes(self):
        _seed([-5.0 + i * 0.05 for i in range(40)])
        session = _test_get_session()
        values = [-5.0 + i * 0.05 for i in range(40)]
        lowest = resolve_bubble_position(session, current_bubble=min(values), now=NOW)
        highest = resolve_bubble_position(session, current_bubble=max(values), now=NOW)
        self.assertLessEqual(lowest.percentile, 5)
        self.assertEqual(highest.percentile, 100)

    def test_29_cheap_boundary_below_expensive_boundary(self):
        _seed([-5.0 + i * 0.05 for i in range(40)])
        pos = resolve_bubble_position(_test_get_session(), now=NOW)
        self.assertLess(pos.cheap_below, pos.expensive_above)

    def test_30_band_cheap_below_the_boundary(self):
        _seed([-5.0 + i * 0.05 for i in range(40)])
        pos = resolve_bubble_position(_test_get_session(), now=NOW)
        cheap = resolve_bubble_position(
            _test_get_session(), current_bubble=pos.cheap_below - 0.5, now=NOW
        )
        self.assertEqual(cheap.band, "CHEAP")

    def test_31_band_expensive_above_the_boundary(self):
        _seed([-5.0 + i * 0.05 for i in range(40)])
        pos = resolve_bubble_position(_test_get_session(), now=NOW)
        pricey = resolve_bubble_position(
            _test_get_session(), current_bubble=pos.expensive_above + 0.5, now=NOW
        )
        self.assertEqual(pricey.band, "EXPENSIVE")

    def test_32_band_survives_a_skewed_distribution(self):
        # A long cheap tail inflates the spread, so the z-score reports NORMAL while
        # the reading actually sits in the top fifth. The band must follow rank.
        _seed([-9.0] * 10 + [-4.0] * 25 + [-3.0] * 5)
        pos = resolve_bubble_position(_test_get_session(), current_bubble=-3.0, now=NOW)
        self.assertEqual(pos.zone, "NORMAL")
        self.assertEqual(pos.band, "EXPENSIVE")

    # --- expectancy --------------------------------------------------------

    def test_33_expectancy_positive_when_cheaper_dominates(self):
        start = NOW - timedelta(days=30)
        pairs = []
        for _ in range(15):
            pairs.extend([-4.0, -5.0])
        _seed(pairs, start=start, step_hours=24)
        out = resolve_similar_outcomes(
            _test_get_session(), current_bubble=-4.0, spread=1.0, now=NOW
        )
        self.assertGreater(out.expectancy_pp, 0)
        self.assertGreater(out.saved_when_cheaper_pp, 0)

    def test_34_reward_to_risk_reported(self):
        start = NOW - timedelta(days=40)
        pairs = []
        for index in range(20):
            pairs.extend([-4.0, -5.0 if index % 2 == 0 else -3.5])
        _seed(pairs, start=start, step_hours=24)
        out = resolve_similar_outcomes(
            _test_get_session(), current_bubble=-4.0, spread=1.0, now=NOW
        )
        self.assertIsNotNone(out.reward_to_risk)
        self.assertGreater(out.reward_to_risk, 0)

    def test_35_best_and_worst_case_reported(self):
        start = NOW - timedelta(days=30)
        pairs = []
        for _ in range(15):
            pairs.extend([-4.0, -5.0])
        _seed(pairs, start=start, step_hours=24)
        out = resolve_similar_outcomes(
            _test_get_session(), current_bubble=-4.0, spread=1.0, now=NOW
        )
        self.assertIsNotNone(out.best_case_pp)
        self.assertIsNotNone(out.worst_case_pp)

    # --- speed -------------------------------------------------------------

    def test_36_typical_move_is_not_inflated_by_short_gaps(self):
        # Regression guard. Deriving a daily rate from readings minutes apart once
        # produced a typical move larger than the entire observed range.
        _seed([-4.0, -4.05] * 60, step_hours=1)
        speed = resolve_bubble_speed(_test_get_session(), cheap_below=-5.0, now=NOW)
        if speed.typical_per_day_pp is not None:
            self.assertLess(speed.typical_per_day_pp, 1.0)

    def test_37_speed_reports_direction_toward_cheap(self):
        _seed([-3.0 - i * 0.05 for i in range(40)], step_hours=2)
        speed = resolve_bubble_speed(_test_get_session(), cheap_below=-6.0, now=NOW)
        self.assertEqual(speed.direction, "TOWARD_CHEAP")

    def test_38_speed_reports_direction_away_from_cheap(self):
        _seed([-5.0 + i * 0.05 for i in range(40)], step_hours=2)
        speed = resolve_bubble_speed(_test_get_session(), cheap_below=-6.0, now=NOW)
        self.assertEqual(speed.direction, "AWAY_FROM_CHEAP")

    def test_39_speed_insufficient_without_history(self):
        speed = resolve_bubble_speed(_test_get_session(), cheap_below=-4.0, now=NOW)
        self.assertEqual(speed.status, "INSUFFICIENT_DATA")

    # --- cheap zone episodes ----------------------------------------------

    def test_40_episodes_counted(self):
        # Three separate spells below the threshold.
        pattern = ([-6.0] * 4 + [-3.0] * 4) * 3 + [-3.0] * 20
        _seed(pattern, step_hours=2)
        episodes = resolve_zone_episodes(_test_get_session(), cheap_below=-5.0, now=NOW)
        self.assertEqual(episodes.episodes, 3)

    def test_41_currently_inside_is_reported(self):
        _seed([-3.0] * 35 + [-6.0] * 5, step_hours=2)
        episodes = resolve_zone_episodes(_test_get_session(), cheap_below=-5.0, now=NOW)
        self.assertTrue(episodes.currently_inside)

    def test_42_sparse_sampling_is_marked_coarse(self):
        _seed([-6.0, -3.0] * 20, step_hours=6)
        episodes = resolve_zone_episodes(_test_get_session(), cheap_below=-5.0, now=NOW)
        self.assertEqual(episodes.measurement_quality, "COARSE")

    def test_43_episodes_need_a_threshold(self):
        _seed([-4.0] * 40)
        episodes = resolve_zone_episodes(_test_get_session(), cheap_below=None, now=NOW)
        self.assertEqual(episodes.status, "INSUFFICIENT_DATA")

    # --- bubble moving averages -------------------------------------------

    def test_44_trend_insufficient_without_history(self):
        trend = resolve_bubble_trend(_test_get_session(), now=NOW)
        self.assertEqual(trend.status, "INSUFFICIENT_DATA")

    def test_45_trend_missing_session_does_not_raise(self):
        trend = resolve_bubble_trend(None, now=NOW)
        self.assertEqual(trend.status, "INSUFFICIENT_DATA")

    def test_46_short_average_above_long_reads_as_shrinking(self):
        # Older days deeply discounted, recent days shallower.
        _seed([-6.0] * 8 * 24, start=NOW - timedelta(days=15), step_hours=1)
        _seed([-3.0] * 6 * 24, start=NOW - timedelta(days=6), step_hours=1)
        trend = resolve_bubble_trend(_test_get_session(), now=NOW)
        self.assertEqual(trend.cross, "ABOVE")
        self.assertEqual(trend.reading, "DISCOUNT_SHRINKING")

    def test_47_short_average_below_long_reads_as_deepening(self):
        _seed([-3.0] * 8 * 24, start=NOW - timedelta(days=15), step_hours=1)
        _seed([-6.0] * 6 * 24, start=NOW - timedelta(days=6), step_hours=1)
        trend = resolve_bubble_trend(_test_get_session(), now=NOW)
        self.assertEqual(trend.cross, "BELOW")
        self.assertEqual(trend.reading, "DISCOUNT_DEEPENING")

    def test_48_bubble_compared_against_the_short_average(self):
        _seed([-4.0] * 10 * 24, start=NOW - timedelta(days=11), step_hours=1)
        below = resolve_bubble_trend(_test_get_session(), current_bubble=-5.0, now=NOW)
        above = resolve_bubble_trend(_test_get_session(), current_bubble=-3.0, now=NOW)
        self.assertEqual(below.versus_short, "BELOW")
        self.assertEqual(above.versus_short, "ABOVE")

    def test_49_each_day_weighs_the_same(self):
        # One day sampled forty times must not outweigh days sampled once.
        _seed([-8.0] * 40, start=NOW - timedelta(days=3), step_hours=0)
        _seed([-2.0], start=NOW - timedelta(days=2), step_hours=1)
        _seed([-2.0], start=NOW - timedelta(days=1), step_hours=1)
        trend = resolve_bubble_trend(_test_get_session(), now=NOW)
        # Equal weighting gives (-8 + -2 + -2) / 3; sample weighting would sit near -8.
        self.assertGreater(trend.short_average, -6.0)

    def test_50_current_partial_day_is_excluded(self):
        _seed([-4.0] * 10 * 24, start=NOW - timedelta(days=11), step_hours=1)
        _seed([-9.0] * 5, start=NOW - timedelta(hours=4), step_hours=1)
        trend = resolve_bubble_trend(_test_get_session(), now=NOW)
        self.assertAlmostEqual(trend.short_average, -4.0, places=2)

    # --- baselines prefer scheduled readings ------------------------------

    def _seed_modes(self, rows):
        """rows: (hours_before_now, premium, collection_mode)."""
        session = _test_get_session()
        for hours, premium, mode in rows:
            session.add(MarketSnapshot(
                timestamp=NOW - timedelta(hours=hours),
                fair_price=100.0, premium_percent=premium,
                world_gold_usd=4000.0, usd_irr=200000.0,
                collection_mode=mode,
            ))
        session.commit()
        session.close()

    def test_52_run_baseline_ignores_user_triggered_readings(self):
        # A user request written minutes ago must not become the RUN baseline, or
        # RUN measures the gap between two clicks rather than market movement.
        self._seed_modes([(5, -4.0, "scheduled"), (0.1, -9.9, "user")])
        latest = _get_latest_market_snapshot(_test_get_session())
        self.assertAlmostEqual(float(latest.premium_percent), -4.0, places=2)

    def test_53_run_baseline_falls_back_when_no_scheduled_reading(self):
        self._seed_modes([(5, -4.0, "user"), (1, -5.0, "user")])
        latest = _get_latest_market_snapshot(_test_get_session())
        self.assertAlmostEqual(float(latest.premium_percent), -5.0, places=2)

    def test_54_day_baseline_prefers_first_scheduled_of_today(self):
        self._seed_modes([(6, -7.7, "user"), (5, -4.0, "scheduled"), (1, -3.0, "scheduled")])
        earliest = _get_earliest_market_snapshot_today(_test_get_session(), now=NOW)
        self.assertAlmostEqual(float(earliest.premium_percent), -4.0, places=2)

    def test_55_day_baseline_falls_back_to_any_reading_today(self):
        self._seed_modes([(6, -7.7, "user"), (1, -3.0, "user")])
        earliest = _get_earliest_market_snapshot_today(_test_get_session(), now=NOW)
        self.assertAlmostEqual(float(earliest.premium_percent), -7.7, places=2)

    def test_51_trend_never_emits_a_decision(self):
        _seed([-4.0] * 10 * 24, start=NOW - timedelta(days=11), step_hours=1)
        trend = resolve_bubble_trend(_test_get_session(), now=NOW)
        values = {str(v) for v in vars(trend).values()}
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
