#!/usr/bin/env python3
"""PRE-SP-C.5 KPI — Outcome Evaluation Foundation.

Run from repository root:
    python kpi/kpi_pre_sp_c5.py
"""

import sys
sys.path.insert(0, "src")

import os
import unittest
from datetime import datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from database.connection import init_db, Base, get_session
from database.models import AnalysisSnapshot, PriceObservation, OutcomeEvaluation
from database.repository import (
    save_market_snapshot,
    save_market_state,
    save_analysis_snapshot,
    save_price_observation,
    save_outcome_evaluation,
    get_outcome_evaluation,
    get_outcome_evaluations_by_snapshot,
)
from analysis.outcome_evaluator import (
    evaluate_snapshot,
    backfill_outcome_evaluations,
    _get_nearest_observation,
    _calculate_movement,
    DEFAULT_TOLERANCE_MINUTES,
    DEFAULT_FLAT_TOLERANCE,
)


class MockSignalState:
    def __init__(self):
        self.snapshot_id = 1
        self.valuation = "CHEAP"
        self.momentum = "IMPROVING"
        self.premium_direction = "DISCOUNT WIDENING"
        self.structure = "DISCOUNT_DOMINANT"
        self.platform_average = 1900000.0
        self.platform_high = 1905000.0
        self.platform_low = 1895000.0
        self.platform_spread = 10000.0
        self.platforms_below_fair = 3
        self.platforms_above_fair = 0
        self.conflict = "NONE"
        self.candidate_decision = "BUY"
        self.final_decision = "WAIT"
        self.reason = "Test"
        self.timestamp = datetime.now()


class KPIPreSPC5(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.session = get_session()
        self._clean_tables()
        self._seed_data()

    def tearDown(self):
        self._clean_tables()
        self.session.close()

    def _clean_tables(self):
        for table in reversed(Base.metadata.sorted_tables):
            self.session.execute(table.delete())
        self.session.commit()

    def _seed_data(self):
        now = datetime.now()

        # Market snapshot
        sid = save_market_snapshot(
            timestamp=now,
            fair_price=1900000.0,
            premium_percent=-1.2,
            world_gold_usd=2400.50,
            usd_irr=50000.0,
            signal="WAIT",
            confidence=0.75,
            platform_prices=[],
        )

        # Market state
        from database.models import MarketState
        ms = MarketState(
            snapshot_id=sid,
            valuation_state="CHEAP",
            momentum_state="IMPROVING",
            premium_direction="DISCOUNT WIDENING",
            structure_state="DISCOUNT_DOMINANT",
            platform_average=1900000.0,
            platform_high=1905000.0,
            platform_low=1895000.0,
            platform_spread=10000.0,
            platforms_below_fair=3,
            platforms_above_fair=0,
            conflict_state="NONE",
            candidate_decision="BUY",
            final_decision="WAIT",
            reason="Test state",
            timestamp=now,
        )
        self.session.add(ms)
        self.session.commit()
        self.market_state_id = ms.id

        # Analysis snapshot at T=now
        self.snapshot_time = now
        self.snapshot_id = save_analysis_snapshot(
            analysis_timestamp=now,
            source_run_id="test_run_001",
            market_snapshot_id=sid,
            market_state_id=ms.id,
            xau_usd=2400.50,
            usd_irr=50000.0,
            rep_gold_price=190000000.0,
            premium_percent=-1.2,
            valuation_state="CHEAP",
            momentum_state="IMPROVING",
            structure_state="DISCOUNT_DOMINANT",
            regime_state="NORMAL",
            technical_state_json={"representative_price": {"price": 190000000.0, "source": "milli"}},
            previous_regime="NORMAL",
            regime_candidate_state=None,
            regime_confirmation_count=0,
        )

        # Seed future price observations for +1h, +6h, +24h
        save_price_observation("XAUUSD", "kitco", now + timedelta(hours=1), 2410.0, "FRESH")
        save_price_observation("XAUUSD", "kitco", now + timedelta(hours=6), 2420.0, "FRESH")
        save_price_observation("XAUUSD", "kitco", now + timedelta(hours=24), 2430.0, "FRESH")

        save_price_observation("USD/IRR", "bonbast", now + timedelta(hours=1), 50100.0, "FRESH")
        save_price_observation("USD/IRR", "bonbast", now + timedelta(hours=6), 50200.0, "FRESH")
        save_price_observation("USD/IRR", "bonbast", now + timedelta(hours=24), 50300.0, "FRESH")

        save_price_observation("REP_IRAN_GOLD", "milli", now + timedelta(hours=1), 190500000.0, "FRESH")
        save_price_observation("REP_IRAN_GOLD", "milli", now + timedelta(hours=6), 191000000.0, "FRESH")
        save_price_observation("REP_IRAN_GOLD", "milli", now + timedelta(hours=24), 192000000.0, "FRESH")

    # --- KPI-1: Schema exists ---
    def test_01_schema_exists(self):
        ev = OutcomeEvaluation(
            analysis_snapshot_id=self.snapshot_id,
            horizon_hours=1,
            reference_time=self.snapshot_time,
            target_time=self.snapshot_time + timedelta(hours=1),
            outcome_status="PENDING",
        )
        self.session.add(ev)
        self.session.commit()
        self.assertIsNotNone(ev.id)

    # --- KPI-2: +1h evaluation ---
    def test_02_one_hour_evaluation(self):
        result = evaluate_snapshot(self.snapshot_id, horizons=[1])
        self.assertEqual(len(result), 1)
        self.assertGreater(result[0], 0)
        ev = get_outcome_evaluation(self.snapshot_id, 1)
        self.assertIsNotNone(ev)
        self.assertEqual(ev.outcome_status, "COMPLETE")

    # --- KPI-3: +6h evaluation ---
    def test_03_six_hour_evaluation(self):
        result = evaluate_snapshot(self.snapshot_id, horizons=[6])
        self.assertEqual(len(result), 1)
        ev = get_outcome_evaluation(self.snapshot_id, 6)
        self.assertIsNotNone(ev)
        self.assertEqual(ev.outcome_status, "COMPLETE")

    # --- KPI-4: +24h evaluation ---
    def test_04_twenty_four_hour_evaluation(self):
        result = evaluate_snapshot(self.snapshot_id, horizons=[24])
        self.assertEqual(len(result), 1)
        ev = get_outcome_evaluation(self.snapshot_id, 24)
        self.assertIsNotNone(ev)
        self.assertEqual(ev.outcome_status, "COMPLETE")

    # --- KPI-5: Wall-clock target time ---
    def test_05_wall_clock_target(self):
        evaluate_snapshot(self.snapshot_id, horizons=[1])
        ev = get_outcome_evaluation(self.snapshot_id, 1)
        expected_target = self.snapshot_time + timedelta(hours=1)
        self.assertEqual(ev.target_time.replace(microsecond=0), expected_target.replace(microsecond=0))

    # --- KPI-6: Nearest observation selection ---
    def test_06_nearest_observation(self):
        now = self.snapshot_time
        self.session.query(PriceObservation).filter(
            PriceObservation.instrument == "XAUUSD",
            PriceObservation.timestamp == now + timedelta(hours=1),
        ).delete()
        self.session.commit()
        save_price_observation("XAUUSD", "kitco", now + timedelta(minutes=55), 2415.0, "FRESH")
        save_price_observation("XAUUSD", "kitco", now + timedelta(hours=1, minutes=10), 2405.0, "FRESH")
        evaluate_snapshot(self.snapshot_id, horizons=[1])
        ev = get_outcome_evaluation(self.snapshot_id, 1)
        self.assertAlmostEqual(float(ev.actual_xau_usd), 2415.0, places=2)

    # --- KPI-7: Tolerance boundary (inside) ---
    def test_07_tolerance_inside(self):
        now = self.snapshot_time
        self.session.query(PriceObservation).filter(
            PriceObservation.instrument == "XAUUSD",
            PriceObservation.timestamp == now + timedelta(hours=1),
        ).delete()
        self.session.commit()
        save_price_observation("XAUUSD", "kitco", now + timedelta(hours=1, minutes=15), 2500.0, "FRESH")
        evaluate_snapshot(self.snapshot_id, horizons=[1])
        ev = get_outcome_evaluation(self.snapshot_id, 1)
        self.assertEqual(ev.outcome_status, "COMPLETE")
        self.assertAlmostEqual(float(ev.actual_xau_usd), 2500.0, places=2)

    # --- KPI-8: Outside tolerance rejected ---
    def test_08_outside_tolerance(self):
        now = self.snapshot_time
        self.session.query(PriceObservation).filter(
            PriceObservation.instrument == "XAUUSD",
            PriceObservation.timestamp > now,
        ).delete()
        self.session.commit()
        save_price_observation("XAUUSD", "kitco", now + timedelta(hours=1, minutes=16), 2500.0, "FRESH")
        evaluate_snapshot(self.snapshot_id, horizons=[1])
        ev = get_outcome_evaluation(self.snapshot_id, 1)
        self.assertEqual(ev.outcome_status, "COMPLETE")
        self.assertIsNone(ev.actual_xau_usd)

    # --- KPI-9: No interpolation ---
    def test_09_no_interpolation(self):
        now = self.snapshot_time
        self.session.query(PriceObservation).filter(
            PriceObservation.instrument == "XAUUSD",
            PriceObservation.timestamp > now,
        ).delete()
        self.session.commit()
        evaluate_snapshot(self.snapshot_id, horizons=[1])
        ev = get_outcome_evaluation(self.snapshot_id, 1)
        self.assertIsNone(ev.actual_xau_usd)
        self.assertIsNone(ev.xau_usd_movement_percent)

    # --- KPI-10: Movement calculation correct ---
    def test_10_movement_calculation(self):
        evaluate_snapshot(self.snapshot_id, horizons=[1])
        ev = get_outcome_evaluation(self.snapshot_id, 1)
        expected = ((2410.0 - 2400.50) / 2400.50) * 100
        self.assertAlmostEqual(float(ev.xau_usd_movement_percent), round(expected, 4), places=3)

    # --- KPI-11: Direction UP ---
    def test_11_direction_up(self):
        evaluate_snapshot(self.snapshot_id, horizons=[1])
        ev = get_outcome_evaluation(self.snapshot_id, 1)
        self.assertEqual(ev.xau_usd_direction, "UP")
        self.assertEqual(ev.usd_irr_direction, "UP")
        self.assertEqual(ev.rep_gold_direction, "UP")

    # --- KPI-12: FLAT behavior ---
    def test_12_flat_behavior(self):
        now = self.snapshot_time
        self.session.query(PriceObservation).filter(
            PriceObservation.instrument == "XAUUSD",
            PriceObservation.timestamp == now + timedelta(hours=1),
        ).delete()
        self.session.commit()
        save_price_observation("XAUUSD", "kitco", now + timedelta(hours=1), 2400.62, "FRESH")
        evaluate_snapshot(self.snapshot_id, horizons=[1], flat_tolerance=0.01)
        ev = get_outcome_evaluation(self.snapshot_id, 1)
        self.assertEqual(ev.xau_usd_direction, "FLAT")

    # --- KPI-13: Missing target -> INSUFFICIENT_DATA ---
    def test_13_missing_target(self):
        now = self.snapshot_time
        self.session.query(PriceObservation).filter(
            PriceObservation.timestamp > now,
        ).delete()
        self.session.commit()
        evaluate_snapshot(self.snapshot_id, horizons=[1])
        ev = get_outcome_evaluation(self.snapshot_id, 1)
        self.assertEqual(ev.outcome_status, "INSUFFICIENT_DATA")

    # --- KPI-14: Partial series failure ---
    def test_14_partial_series_failure(self):
        now = self.snapshot_time
        self.session.query(PriceObservation).filter(
            PriceObservation.instrument == "XAUUSD",
            PriceObservation.timestamp > now,
        ).delete()
        self.session.commit()
        evaluate_snapshot(self.snapshot_id, horizons=[1])
        ev = get_outcome_evaluation(self.snapshot_id, 1)
        self.assertEqual(ev.outcome_status, "COMPLETE")
        self.assertIsNone(ev.actual_xau_usd)
        self.assertIsNotNone(ev.actual_usd_irr)
        self.assertIsNotNone(ev.actual_rep_gold_price)

    # --- KPI-15: Idempotency ---
    def test_15_idempotency(self):
        result1 = evaluate_snapshot(self.snapshot_id, horizons=[1])
        result2 = evaluate_snapshot(self.snapshot_id, horizons=[1])
        self.assertEqual(result1, result2)
        count = self.session.query(OutcomeEvaluation).filter(
            OutcomeEvaluation.analysis_snapshot_id == self.snapshot_id,
            OutcomeEvaluation.horizon_hours == 1,
        ).count()
        self.assertEqual(count, 1)

    # --- KPI-16: Historical backfill ---
    def test_16_historical_backfill(self):
        count = backfill_outcome_evaluations(hours=1)
        self.assertGreaterEqual(count, 1)

    # --- KPI-17: No look-ahead leakage ---
    def test_17_no_lookahead(self):
        now = self.snapshot_time
        save_price_observation("XAUUSD", "kitco", now, 9999.0, "FRESH")
        evaluate_snapshot(self.snapshot_id, horizons=[1])
        ev = get_outcome_evaluation(self.snapshot_id, 1)
        self.assertIsNotNone(ev.actual_xau_usd)
        self.assertNotAlmostEqual(float(ev.actual_xau_usd), 9999.0, places=2)

    # --- KPI-18: Representative price semantics ---
    def test_18_representative_semantics(self):
        now = self.snapshot_time
        self.session.query(PriceObservation).filter(
            PriceObservation.instrument == "REP_IRAN_GOLD",
            PriceObservation.source == "milli",
            PriceObservation.timestamp > now,
        ).delete()
        self.session.commit()
        save_price_observation("REP_IRAN_GOLD", "ayyareh", now + timedelta(hours=1), 195000000.0, "FRESH")
        evaluate_snapshot(self.snapshot_id, horizons=[1])
        ev = get_outcome_evaluation(self.snapshot_id, 1)
        self.assertAlmostEqual(float(ev.actual_rep_gold_price), 195000000.0, places=2)

    # --- KPI-19: XAU/USD independence ---
    def test_19_xau_usd_independence(self):
        now = self.snapshot_time
        self.session.query(PriceObservation).filter(
            PriceObservation.instrument != "XAUUSD",
            PriceObservation.timestamp > now,
        ).delete()
        self.session.commit()
        evaluate_snapshot(self.snapshot_id, horizons=[1])
        ev = get_outcome_evaluation(self.snapshot_id, 1)
        self.assertIsNotNone(ev.actual_xau_usd)
        self.assertIsNone(ev.actual_usd_irr)
        self.assertIsNone(ev.actual_rep_gold_price)

    # --- KPI-20: USD/IRR independence ---
    def test_20_usd_irr_independence(self):
        now = self.snapshot_time
        self.session.query(PriceObservation).filter(
            PriceObservation.instrument != "USD/IRR",
            PriceObservation.timestamp > now,
        ).delete()
        self.session.commit()
        evaluate_snapshot(self.snapshot_id, horizons=[1])
        ev = get_outcome_evaluation(self.snapshot_id, 1)
        self.assertIsNotNone(ev.actual_usd_irr)
        self.assertIsNone(ev.actual_xau_usd)
        self.assertIsNone(ev.actual_rep_gold_price)

    # --- KPI-21: Premium INSUFFICIENT_DATA ---
    def test_21_premium_insufficient(self):
        evaluate_snapshot(self.snapshot_id, horizons=[1])
        ev = get_outcome_evaluation(self.snapshot_id, 1)
        self.assertIsNone(ev.actual_premium_percent)
        self.assertEqual(ev.premium_direction, "INSUFFICIENT_DATA")

    # --- KPI-22: Direction DOWN ---
    def test_22_direction_down(self):
        now = self.snapshot_time
        self.session.query(PriceObservation).filter(
            PriceObservation.instrument == "XAUUSD",
            PriceObservation.timestamp == now + timedelta(hours=1),
        ).delete()
        self.session.commit()
        save_price_observation("XAUUSD", "kitco", now + timedelta(hours=1), 2390.0, "FRESH")
        self.session.query(PriceObservation).filter(
            PriceObservation.instrument == "USD/IRR",
            PriceObservation.timestamp == now + timedelta(hours=1),
        ).delete()
        self.session.commit()
        save_price_observation("USD/IRR", "bonbast", now + timedelta(hours=1), 49900.0, "FRESH")
        self.session.query(PriceObservation).filter(
            PriceObservation.instrument == "REP_IRAN_GOLD",
            PriceObservation.timestamp == now + timedelta(hours=1),
        ).delete()
        self.session.commit()
        save_price_observation("REP_IRAN_GOLD", "milli", now + timedelta(hours=1), 189000000.0, "FRESH")
        evaluate_snapshot(self.snapshot_id, horizons=[1])
        ev = get_outcome_evaluation(self.snapshot_id, 1)
        self.assertEqual(ev.xau_usd_direction, "DOWN")
        self.assertEqual(ev.usd_irr_direction, "DOWN")
        self.assertEqual(ev.rep_gold_direction, "DOWN")

    # --- KPI-23: Reference values preserved ---
    def test_23_reference_preserved(self):
        evaluate_snapshot(self.snapshot_id, horizons=[1])
        ev = get_outcome_evaluation(self.snapshot_id, 1)
        self.assertAlmostEqual(float(ev.reference_xau_usd), 2400.50, places=2)
        self.assertAlmostEqual(float(ev.reference_usd_irr), 50000.0, places=2)
        self.assertAlmostEqual(float(ev.reference_rep_gold_price), 190000000.0, places=2)
        self.assertAlmostEqual(float(ev.reference_premium_percent), -1.2, places=2)

    # --- KPI-24: Target time math ---
    def test_24_target_time_math(self):
        evaluate_snapshot(self.snapshot_id, horizons=[6])
        ev = get_outcome_evaluation(self.snapshot_id, 6)
        expected = self.snapshot_time + timedelta(hours=6)
        self.assertEqual(ev.target_time.replace(microsecond=0), expected.replace(microsecond=0))

    # --- KPI-25: Backfill respects existing complete horizons ---
    def test_25_backfill_respects_complete(self):
        configured_horizons = [1, 6, 24]
        evaluate_snapshot(self.snapshot_id, horizons=configured_horizons)

        count = backfill_outcome_evaluations(
            hours=1,
            horizons=configured_horizons,
        )
        self.assertEqual(count, 0)

        evaluations = get_outcome_evaluations_by_snapshot(self.snapshot_id)
        complete_horizons = {
            evaluation.horizon_hours
            for evaluation in evaluations
            if evaluation.outcome_status == "COMPLETE"
        }
        self.assertEqual(complete_horizons, set(configured_horizons))


def run_kpi():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(KPIPreSPC5)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    passed = result.testsRun - len(result.failures) - len(result.errors)
    total = result.testsRun

    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print(f"Result: {passed}/{total} passed, 0 failed")
        print("\n🟢 PRE-SP-C.5 COMPLETE")
        return 0
    else:
        print(f"Result: {passed}/{total} passed, {len(result.failures) + len(result.errors)} failed")
        print("\n🔴 PRE-SP-C.5 FAILED")
        return 1


if __name__ == "__main__":
    raise SystemExit(run_kpi())
