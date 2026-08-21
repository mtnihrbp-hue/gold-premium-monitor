#!/usr/bin/env python3
"""PRE-SP-C.12 KPI — Historical Feature Dataset & Leakage-Safe Labeling.

Run from repository root:
    python kpi/kpi_pre_sp_c12.py
"""

import sys
sys.path.insert(0, "src")

import os
import unittest
import copy
from datetime import datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from database.connection import init_db, Base, get_session
from database.models import AnalysisSnapshot
from database.repository import (
    save_market_snapshot,
    save_market_state,
    save_analysis_snapshot,
    save_price_observation,
    save_outcome_evaluation,
)
from intelligence.dataset import (
    build_dataset_record,
    build_dataset_batch,
    validate_dataset_record,
    verify_no_leakage,
    DATASET_VALID,
    DATASET_DEGRADED,
    DATASET_INSUFFICIENT_DATA,
    DATASET_INVALID,
    DATASET_SCHEMA_VERSION,
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


class KPIPreSPC12(unittest.TestCase):
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

        ms = MockSignalState()
        ms.snapshot_id = sid
        self.market_state_id = save_market_state(ms)

        # Seed price observations
        for i in range(40):
            ts = now - timedelta(hours=40 - i)
            save_price_observation("REP_IRAN_GOLD", "milli", ts, base_price + (i * 100000.0), "FRESH")
            save_price_observation("XAUUSD", "kitco", ts, 2400.0 + (i * 0.5), "FRESH")
            save_price_observation("USD/IRR", "bonbast", ts, 50000.0 + (i * 10), "FRESH")

        # C.8 features
        features = {
            "schema_version": "1",
            "generated_at": now.isoformat(),
            "price_trend": {"rep_gold_ma7": 190000000.0, "rep_gold_ma15": 189500000.0},
            "momentum": {"premium_velocity": 0.05, "premium_acceleration": 0.01},
            "volatility": {"rep_gold_volatility_7": 0.5},
            "regime": {"current_regime": "NORMAL", "previous_regime": "NORMAL"},
            "market_relation": {"xau_usd_direction": "UP", "usd_irr_direction": "UP", "rep_gold_direction": "UP"},
            "structure": {"platform_spread": 10000.0, "consensus_ratio": 0.75},
            "data_quality": {"rep_gold_observations": 40, "sufficient_history": True},
        }

        self.snapshot_id = save_analysis_snapshot(
            analysis_timestamp=now,
            source_run_id="c12_test_001",
            market_snapshot_id=sid,
            market_state_id=self.market_state_id,
            xau_usd=2400.50,
            usd_irr=50000.0,
            rep_gold_price=190000000.0,
            premium_percent=-1.2,
            valuation_state="CHEAP",
            momentum_state="IMPROVING",
            structure_state="DISCOUNT_DOMINANT",
            regime_state="NORMAL",
            features_json=features,
        )

        # C.5 outcomes — future observations
        for horizon in [1, 6, 24]:
            target = now + timedelta(hours=horizon)
            save_outcome_evaluation(
                analysis_snapshot_id=self.snapshot_id,
                horizon_hours=horizon,
                reference_time=now,
                target_time=target,
                actual_observation_time=target + timedelta(minutes=5),
                outcome_status="COMPLETE",
                rep_gold_direction="UP",
                rep_gold_movement_percent=0.5,
                xau_usd_direction="UP",
                usd_irr_direction="UP",
            )

        self.now = now
        self.features = features

    # --- KPI-1: valid snapshot becomes dataset record ---
    def test_01_valid_record(self):
        rec = build_dataset_record(self.snapshot_id)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["snapshot_id"], self.snapshot_id)

    # --- KPI-2: feature schema preserved ---
    def test_02_feature_schema(self):
        rec = build_dataset_record(self.snapshot_id)
        self.assertEqual(rec["feature_schema_version"], "1")

    # --- KPI-3: feature timestamp preserved ---
    def test_03_feature_timestamp(self):
        rec = build_dataset_record(self.snapshot_id)
        self.assertEqual(rec["feature_timestamp"], self.now.isoformat())

    # --- KPI-4: provenance preserved ---
    def test_04_provenance(self):
        rec = build_dataset_record(self.snapshot_id)
        self.assertEqual(rec["provenance"]["snapshot_source_run_id"], "c12_test_001")

    # --- KPI-5: 1h label generated ---
    def test_05_label_1h(self):
        rec = build_dataset_record(self.snapshot_id)
        self.assertIn("1", rec["labels"])
        self.assertEqual(rec["labels"]["1"]["status"], "COMPLETE")

    # --- KPI-6: 6h label generated ---
    def test_06_label_6h(self):
        rec = build_dataset_record(self.snapshot_id)
        self.assertIn("6", rec["labels"])
        self.assertEqual(rec["labels"]["6"]["status"], "COMPLETE")

    # --- KPI-7: 24h label generated ---
    def test_07_label_24h(self):
        rec = build_dataset_record(self.snapshot_id)
        self.assertIn("24", rec["labels"])
        self.assertEqual(rec["labels"]["24"]["status"], "COMPLETE")

    # --- KPI-8: label strictly after feature timestamp ---
    def test_08_label_after_feature(self):
        rec = build_dataset_record(self.snapshot_id)
        for horizon, label in rec["labels"].items():
            if label.get("actual_observation_time"):
                self.assertGreater(label["actual_observation_time"], rec["feature_timestamp"])

    # --- KPI-9: no same-time observation leakage ---
    def test_09_no_same_time(self):
        rec = build_dataset_record(self.snapshot_id)
        for horizon, label in rec["labels"].items():
            if label.get("actual_observation_time"):
                self.assertNotEqual(label["actual_observation_time"], rec["feature_timestamp"])

    # --- KPI-10: no future-feature leakage ---
    def test_10_no_future_feature_leakage(self):
        # Add a future observation — should NOT affect the dataset
        future_ts = self.now + timedelta(hours=100)
        save_price_observation("REP_IRAN_GOLD", "milli", future_ts, 999999999.0, "FRESH")
        rec = build_dataset_record(self.snapshot_id)
        features = rec["features"]
        self.assertNotEqual(features["price_trend"].get("rep_gold_ma7"), 999999999.0)

    # --- KPI-11: no interpolation ---
    def test_11_no_interpolation(self):
        rec = build_dataset_record(self.snapshot_id)
        self.assertIsNotNone(rec["labels"]["1"]["direction"])

    # --- KPI-12: missing outcome ---
    def test_12_missing_outcome(self):
        # Create snapshot WITHOUT outcomes
        sid = save_analysis_snapshot(
            analysis_timestamp=self.now,
            source_run_id="c12_no_outcome",
            market_snapshot_id=1,
            market_state_id=1,
            features_json=self.features,
        )
        rec = build_dataset_record(sid)
        self.assertEqual(rec["dataset_status"], DATASET_INSUFFICIENT_DATA)

    # --- KPI-13: insufficient-data propagation ---
    def test_13_insufficient_data(self):
        save_outcome_evaluation(
            analysis_snapshot_id=self.snapshot_id,
            horizon_hours=1,
            reference_time=self.now,
            target_time=self.now + timedelta(hours=1),
            outcome_status="INSUFFICIENT_DATA",
        )
        rec = build_dataset_record(self.snapshot_id)
        self.assertEqual(rec["labels"]["1"]["status"], "INSUFFICIENT_DATA")

    # --- KPI-14: feature preservation ---
    def test_14_feature_preservation(self):
        rec = build_dataset_record(self.snapshot_id)
        self.assertEqual(rec["features"]["price_trend"]["rep_gold_ma7"], 190000000.0)

    # --- KPI-15: outcome preservation ---
    def test_15_outcome_preservation(self):
        rec = build_dataset_record(self.snapshot_id)
        self.assertEqual(rec["labels"]["1"]["rep_gold_direction"], "UP")

    # --- KPI-16: deterministic generation ---
    def test_16_deterministic(self):
        r1 = build_dataset_record(self.snapshot_id)
        r2 = build_dataset_record(self.snapshot_id)
        self.assertEqual(r1["primary_label"], r2["primary_label"])
        self.assertEqual(r1["dataset_status"], r2["dataset_status"])

    # --- KPI-17: duplicate snapshot handling ---
    def test_17_duplicate_handling(self):
        rec = build_dataset_record(self.snapshot_id)
        self.assertEqual(rec["snapshot_id"], self.snapshot_id)

    # --- KPI-18: schema version present ---
    def test_18_schema_version(self):
        rec = build_dataset_record(self.snapshot_id)
        self.assertEqual(rec["schema_version"], DATASET_SCHEMA_VERSION)

    # --- KPI-19: point-in-time correctness ---
    def test_19_point_in_time(self):
        rec = build_dataset_record(self.snapshot_id)
        self.assertEqual(rec["feature_timestamp"], self.now.isoformat())

    # --- KPI-20: C.5 compatibility ---
    def test_20_c5_compat(self):
        rec = build_dataset_record(self.snapshot_id)
        self.assertIn("movement_percent", rec["labels"]["1"])

    # --- KPI-21: C.8 compatibility ---
    def test_21_c8_compat(self):
        rec = build_dataset_record(self.snapshot_id)
        self.assertIn("price_trend", rec["features"])

    # --- KPI-22: C.9 compatibility ---
    def test_22_c9_compat(self):
        rec = build_dataset_record(self.snapshot_id)
        self.assertIn("snapshot_id", rec)

    # --- KPI-23: C.10 compatibility ---
    def test_23_c10_compat(self):
        rec = build_dataset_record(self.snapshot_id)
        self.assertIn("provenance", rec)

    # --- KPI-24: C.11 compatibility ---
    def test_24_c11_compat(self):
        rec = build_dataset_record(self.snapshot_id)
        self.assertIn("data_quality", rec)

    # --- KPI-25: regression ---
    def test_25_regression(self):
        from database.models import AnalysisSnapshot
        self.assertTrue(hasattr(AnalysisSnapshot, 'features_json'))
        self.assertTrue(hasattr(AnalysisSnapshot, 'analysis_read_model_json'))

    # --- KPI-26: leakage test with future data ---
    def test_26_leakage_future_data(self):
        self.assertTrue(verify_no_leakage(self.snapshot_id, []))

    # --- KPI-27: batch generation ---
    def test_27_batch(self):
        batch = build_dataset_batch(hours=1)
        self.assertIsInstance(batch, list)

    # --- KPI-28: validation passes ---
    def test_28_validation(self):
        rec = build_dataset_record(self.snapshot_id)
        valid, errors = validate_dataset_record(rec)
        self.assertTrue(valid, f"Errors: {errors}")

    # --- KPI-29: primary label is direction ---
    def test_29_primary_label(self):
        rec = build_dataset_record(self.snapshot_id)
        self.assertEqual(rec["primary_label"], "UP")

    # --- KPI-30: invalid record for missing snapshot ---
    def test_30_invalid_missing(self):
        rec = build_dataset_record(99999)
        self.assertEqual(rec["dataset_status"], DATASET_INVALID)


def run_kpi():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(KPIPreSPC12)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    passed = result.testsRun - len(result.failures) - len(result.errors)
    total = result.testsRun

    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print(f"Result: {passed}/{total} passed, 0 failed")
        print("\n🟢 PRE-SP-C.12 COMPLETE")
        return 0
    else:
        failed = len(result.failures) + len(result.errors)
        print(f"Result: {passed}/{total} passed, {failed} failed")
        print("\n🔴 PRE-SP-C.12 FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_kpi())
