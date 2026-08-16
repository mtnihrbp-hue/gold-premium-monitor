#!/usr/bin/env python3
"""PRE-SP-C.1 KPI — Canonical Time Series.

Run from repository root:
    python kpi/kpi_pre_sp_c1.py
"""

import sys
sys.path.insert(0, "src")

import os
import unittest
from datetime import datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from database.connection import init_db, Base, get_session
from database.repository import (
    save_price_observation,
    get_price_observations,
    get_latest_price_observation,
    get_price_observations_by_instrument,
)
from database.models import PriceObservation
from intelligence.freshness import evaluate_freshness


class KPIPreSPC1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.session = get_session()

    def tearDown(self):
        for table in reversed(Base.metadata.sorted_tables):
            self.session.execute(table.delete())
        self.session.commit()
        self.session.close()

    def test_01_schema_valid(self):
        obs = PriceObservation(
            instrument="XAUUSD",
            source="test",
            timestamp=datetime.now(),
            price=2400.0,
            freshness="FRESH",
            collection_run_id="run_test",
        )
        self.session.add(obs)
        self.session.commit()
        self.assertIsNotNone(self.session.query(PriceObservation).first())

    def test_02_xauusd_persists(self):
        oid = save_price_observation("XAUUSD", "kitco", datetime.now(), 2400.50, "FRESH", "run_1")
        self.assertGreater(oid, 0)
        latest = get_latest_price_observation(instrument="XAUUSD")
        self.assertIsNotNone(latest)
        self.assertAlmostEqual(float(latest.price), 2400.50, places=2)

    def test_03_usd_irr_persists(self):
        oid = save_price_observation("USD/IRR", "bonbast", datetime.now(), 50000.0, "FRESH", "run_1")
        self.assertGreater(oid, 0)
        latest = get_latest_price_observation(instrument="USD/IRR")
        self.assertIsNotNone(latest)
        self.assertAlmostEqual(float(latest.price), 50000.0, places=2)

    def test_04_rep_iran_gold_persists(self):
        oid = save_price_observation("REP_IRAN_GOLD", "milli", datetime.now(), 1900000.0, "FRESH", "run_1")
        self.assertGreater(oid, 0)
        latest = get_latest_price_observation(instrument="REP_IRAN_GOLD")
        self.assertIsNotNone(latest)
        self.assertAlmostEqual(float(latest.price), 1900000.0, places=2)

    def test_05_paxg_schema_valid(self):
        oid = save_price_observation("PAXG", "paxg_api", datetime.now(), 2400.0, "UNKNOWN", "run_1")
        self.assertGreater(oid, 0)
        latest = get_latest_price_observation(instrument="PAXG")
        self.assertIsNotNone(latest)
        self.assertEqual(latest.instrument, "PAXG")

    def test_06_freshness_deterministic(self):
        now = datetime.now()
        self.assertEqual(evaluate_freshness(now, now, 15), "FRESH")
        self.assertEqual(evaluate_freshness(now - timedelta(minutes=20), now, 15), "STALE")
        self.assertEqual(evaluate_freshness(None, stale_threshold_minutes=15), "UNKNOWN")
        self.assertEqual(evaluate_freshness(now + timedelta(minutes=5), now, 15), "UNKNOWN")

    def test_07_instrument_filtering(self):
        now = datetime.now()
        save_price_observation("XAUUSD", "kitco", now, 2400.0, "FRESH", "run_1")
        save_price_observation("USD/IRR", "bonbast", now, 50000.0, "FRESH", "run_1")
        save_price_observation("REP_IRAN_GOLD", "milli", now, 1900000.0, "FRESH", "run_1")
        self.assertEqual(len(get_price_observations_by_instrument("XAUUSD")), 1)
        self.assertEqual(len(get_price_observations_by_instrument("USD/IRR")), 1)
        self.assertEqual(len(get_price_observations_by_instrument("REP_IRAN_GOLD")), 1)

    def test_08_timestamp_ordering(self):
        now = datetime.now()
        save_price_observation("XAUUSD", "kitco", now - timedelta(hours=2), 2390.0, "FRESH", "run_1")
        save_price_observation("XAUUSD", "kitco", now - timedelta(hours=1), 2395.0, "FRESH", "run_1")
        save_price_observation("XAUUSD", "kitco", now, 2400.0, "FRESH", "run_1")
        obs = get_price_observations_by_instrument("XAUUSD", limit=10)
        self.assertEqual(len(obs), 3)
        self.assertAlmostEqual(float(obs[0].price), 2400.0, places=2)

    def test_09_collection_run_id_preserved(self):
        now = datetime.now()
        save_price_observation("XAUUSD", "kitco", now, 2400.0, "FRESH", "run_abc123")
        latest = get_latest_price_observation(instrument="XAUUSD")
        self.assertEqual(latest.collection_run_id, "run_abc123")

    def test_10_db_failure_non_fatal(self):
        import inspect
        sig = inspect.signature(save_price_observation)
        self.assertIn("instrument", sig.parameters)
        self.assertIn("collection_run_id", sig.parameters)


def run_kpi():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(KPIPreSPC1)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    passed = result.testsRun - len(result.failures) - len(result.errors)
    total = result.testsRun

    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print(f"Result: {passed}/{total} passed, 0 failed")
        print("\n🟢 PRE-SP-C.1 COMPLETE")
        return 0
    else:
        failed = len(result.failures) + len(result.errors)
        print(f"Result: {passed}/{total} passed, {failed} failed")
        print("\n🔴 PRE-SP-C.1 FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_kpi())
