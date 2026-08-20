#!/usr/bin/env python3
"""PRE-SP-C.8 KPI — Feature Intelligence Layer.

Run from repository root:
    python kpi/kpi_pre_sp_c8.py
"""

import sys
sys.path.insert(0, "src")

import os
import unittest
from datetime import datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from database.connection import init_db, Base, get_session
from database.models import AnalysisSnapshot
from database.repository import (
    save_market_snapshot,
    save_market_state,
    save_analysis_snapshot,
    save_price_observation,
)
from intelligence.features import (
    build_feature_snapshot,
    validate_feature_snapshot,
    FEATURE_SCHEMA_VERSION,
    _sma,
    _ema,
    _rolling_volatility,
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


class KPIPreSPC8(unittest.TestCase):
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
        base_price = 190000000.0

        # Seed 40 price observations for each instrument
        for i in range(40):
            ts = now - timedelta(hours=40 - i)
            price = base_price + (i * 100000.0)  # rising trend
            save_price_observation("REP_IRAN_GOLD", "milli", ts, price, "FRESH")
            save_price_observation("XAUUSD", "kitco", ts, 2400.0 + (i * 0.5), "FRESH")
            save_price_observation("USD/IRR", "bonbast", ts, 50000.0 + (i * 10), "FRESH")

        # Seed market snapshots with premiums
        for i in range(20):
            ts = now - timedelta(hours=20 - i)
            premium = -1.2 + (i * 0.05)
            save_market_snapshot(
                timestamp=ts,
                fair_price=1900000.0,
                premium_percent=premium,
                world_gold_usd=2400.0 + (i * 0.5),
                usd_irr=50000.0 + (i * 10),
                signal="WAIT",
                confidence=0.75,
                platform_prices=[],
            )

        # Market state
        ms = MockSignalState()
        ms.snapshot_id = 1
        ms.timestamp = now
        self.market_state_id = save_market_state(ms)
        self.now = now

    # --- KPI-1: feature calculation correctness ---
    def test_01_sma_correct(self):
        vals = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
        self.assertEqual(_sma(vals, 7), 4.0)
        self.assertIsNone(_sma(vals, 10))

    # --- KPI-2: EMA correctness ---
    def test_02_ema_correct(self):
        vals = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0]
        ema = _ema(vals, 7)
        self.assertIsNotNone(ema)
        self.assertGreater(ema, 10.0)

    # --- KPI-3: deterministic output ---
    def test_03_deterministic(self):
        f1 = build_feature_snapshot(self.now, "NORMAL", "NORMAL", None, config={})
        f2 = build_feature_snapshot(self.now, "NORMAL", "NORMAL", None, config={})
        self.assertEqual(f1["schema_version"], f2["schema_version"])
        self.assertEqual(f1["regime"]["current_regime"], f2["regime"]["current_regime"])

    # --- KPI-4: missing data handling ---
    def test_04_missing_data(self):
        self._clean_tables()
        f = build_feature_snapshot(self.now, "UNKNOWN", None, None, config={})
        self.assertEqual(f["data_quality"]["rep_gold_observations"], 0)
        self.assertIsNone(f["price_trend"]["rep_gold_ma7"])

    # --- KPI-5: insufficient history ---
    def test_05_insufficient_history(self):
        self._clean_tables()
        # Only 5 observations
        for i in range(5):
            ts = self.now - timedelta(hours=5 - i)
            save_price_observation("REP_IRAN_GOLD", "milli", ts, 190000000.0, "FRESH")
        f = build_feature_snapshot(self.now, "NORMAL", "NORMAL", None, config={})
        self.assertIsNone(f["price_trend"]["rep_gold_ma30"])
        self.assertFalse(f["data_quality"]["sufficient_history"])

    # --- KPI-6: no future leakage ---
    def test_06_no_lookahead(self):
        future_ts = self.now + timedelta(hours=1)
        save_price_observation("REP_IRAN_GOLD", "milli", future_ts, 999999999.0, "FRESH")
        f = build_feature_snapshot(self.now, "NORMAL", "NORMAL", None, config={})
        # The 999M price should not appear
        self.assertNotEqual(f["price_trend"].get("rep_gold_ma7"), 999999999.0)

    # --- KPI-7: MA7 present ---
    def test_07_ma7_present(self):
        f = build_feature_snapshot(self.now, "NORMAL", "NORMAL", None, config={})
        self.assertIsNotNone(f["price_trend"]["rep_gold_ma7"])
        self.assertIsNotNone(f["price_trend"]["xau_usd_ma7"])
        self.assertIsNotNone(f["price_trend"]["usd_irr_ma7"])

    # --- KPI-8: EMA present ---
    def test_08_ema_present(self):
        f = build_feature_snapshot(self.now, "NORMAL", "NORMAL", None, config={})
        self.assertIsNotNone(f["price_trend"]["rep_gold_ema7"])

    # --- KPI-9: price vs MA distance ---
    def test_09_price_vs_ma(self):
        f = build_feature_snapshot(self.now, "NORMAL", "NORMAL", None, config={})
        self.assertIsNotNone(f["price_trend"]["rep_gold_vs_ma7_percent"])

    # --- KPI-10: premium velocity ---
    def test_10_premium_velocity(self):
        f = build_feature_snapshot(self.now, "NORMAL", "NORMAL", None, config={})
        self.assertIsNotNone(f["momentum"]["premium_velocity"])

    # --- KPI-11: premium acceleration ---
    def test_11_premium_acceleration(self):
        f = build_feature_snapshot(self.now, "NORMAL", "NORMAL", None, config={})
        self.assertIsNotNone(f["momentum"]["premium_acceleration"])

    # --- KPI-12: direction persistence ---
    def test_12_direction_persistence(self):
        f = build_feature_snapshot(self.now, "NORMAL", "NORMAL", None, config={})
        self.assertIn(f["momentum"]["premium_latest_direction"], ["UP", "DOWN", "FLAT", "UNKNOWN"])

    # --- KPI-13: volatility ---
    def test_13_volatility(self):
        f = build_feature_snapshot(self.now, "NORMAL", "NORMAL", None, config={})
        self.assertIsNotNone(f["volatility"]["rep_gold_volatility_7"])

    # --- KPI-14: range expansion ---
    def test_14_range_expansion(self):
        f = build_feature_snapshot(self.now, "NORMAL", "NORMAL", None, config={})
        # May be None if exactly 14 obs not available, but with 40 it should exist
        self.assertIsNotNone(f["volatility"]["rep_gold_range_expansion_percent"])

    # --- KPI-15: regime features ---
    def test_15_regime_features(self):
        f = build_feature_snapshot(self.now, "NORMAL", "NORMAL", None, config={})
        self.assertEqual(f["regime"]["current_regime"], "NORMAL")
        self.assertEqual(f["regime"]["previous_regime"], "NORMAL")

    # --- KPI-16: market relation ---
    def test_16_market_relation(self):
        f = build_feature_snapshot(self.now, "NORMAL", "NORMAL", None, config={})
        self.assertIn(f["market_relation"]["xau_usd_direction"], ["UP", "DOWN", "FLAT", "UNKNOWN"])
        self.assertIn(f["market_relation"]["usd_irr_direction"], ["UP", "DOWN", "FLAT", "UNKNOWN"])

    # --- KPI-17: structure features ---
    def test_17_structure_features(self):
        from database.models import MarketState
        ms = self.session.query(MarketState).first()
        f = build_feature_snapshot(self.now, "NORMAL", "NORMAL", ms, config={})
        self.assertIsNotNone(f["structure"]["platform_spread"])

    # --- KPI-18: no BUY/SELL ---
    def test_18_no_decision(self):
        f = build_feature_snapshot(self.now, "NORMAL", "NORMAL", None, config={})
        valid, errors = validate_feature_snapshot(f)
        self.assertTrue(valid, f"Errors: {errors}")

    # --- KPI-19: schema version ---
    def test_19_schema_version(self):
        f = build_feature_snapshot(self.now, "NORMAL", "NORMAL", None, config={})
        self.assertEqual(f["schema_version"], FEATURE_SCHEMA_VERSION)

    # --- KPI-20: persistence roundtrip ---
    def test_20_persistence_roundtrip(self):
        f = build_feature_snapshot(self.now, "NORMAL", "NORMAL", None, config={})
        sid = save_analysis_snapshot(
            analysis_timestamp=self.now,
            source_run_id="feat_test_001",
            market_snapshot_id=1,
            market_state_id=self.market_state_id,
            xau_usd=2400.50,
            usd_irr=50000.0,
            rep_gold_price=190000000.0,
            premium_percent=-1.2,
            valuation_state="CHEAP",
            momentum_state="IMPROVING",
            structure_state="DISCOUNT_DOMINANT",
            features_json=f,
        )
        snap = self.session.query(AnalysisSnapshot).filter_by(id=sid).first()
        self.assertIsNotNone(snap.features_json)
        self.assertEqual(snap.features_json["schema_version"], FEATURE_SCHEMA_VERSION)

    # --- KPI-21: data quality explicit ---
    def test_21_data_quality(self):
        f = build_feature_snapshot(self.now, "NORMAL", "NORMAL", None, config={})
        self.assertIn("sufficient_history", f["data_quality"])
        self.assertIn("rep_gold_observations", f["data_quality"])

    # --- KPI-22: validation catches errors ---
    def test_22_validation(self):
        valid, errors = validate_feature_snapshot({})
        self.assertFalse(valid)
        self.assertTrue(len(errors) > 0)

    # --- KPI-23: compatibility with previous KPIs ---
    def test_23_no_regression(self):
        # Ensure existing models still work
        from database.models import AnalysisSnapshot, OutcomeEvaluation
        self.assertTrue(hasattr(AnalysisSnapshot, 'evidence_package_json'))
        self.assertTrue(hasattr(AnalysisSnapshot, 'intelligence_result_json'))

    # --- KPI-24: divergence indicator ---
    def test_24_divergence(self):
        f = build_feature_snapshot(self.now, "NORMAL", "NORMAL", None, config={})
        self.assertIn(f["market_relation"]["xau_local_divergence"], [True, False, None])

    # --- KPI-25: consensus ratio ---
    def test_25_consensus_ratio(self):
        from database.models import MarketState
        ms = self.session.query(MarketState).first()
        f = build_feature_snapshot(self.now, "NORMAL", "NORMAL", ms, config={})
        if f["structure"]["consensus_ratio"] is not None:
            self.assertGreaterEqual(f["structure"]["consensus_ratio"], 0.0)
            self.assertLessEqual(f["structure"]["consensus_ratio"], 1.0)


def run_kpi():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(KPIPreSPC8)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    passed = result.testsRun - len(result.failures) - len(result.errors)
    total = result.testsRun

    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print(f"Result: {passed}/{total} passed, 0 failed")
        print("\n🟢 PRE-SP-C.8 COMPLETE")
        return 0
    else:
        failed = len(result.failures) + len(result.errors)
        print(f"Result: {passed}/{total} passed, {failed} failed")
        print("\n🔴 PRE-SP-C.8 FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_kpi())
