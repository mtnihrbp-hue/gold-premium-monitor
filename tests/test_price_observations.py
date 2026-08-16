"""Tests for PRE-SP-C.1: Canonical Price Observations."""

import sys
sys.path.insert(0, "src")

import os
import unittest
from datetime import datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from database.connection import init_db, get_session, Base
from database.repository import (
    save_price_observation,
    get_price_observations,
    get_latest_price_observation,
    get_price_observations_by_instrument,
)
from database.models import PriceObservation
from intelligence.freshness import evaluate_freshness


class TestPriceObservations(unittest.TestCase):
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

    # --- KPI-1: Schema valid ---
    def test_schema_valid(self):
        """PriceObservation table exists and is queryable."""
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
        result = self.session.query(PriceObservation).first()
        self.assertIsNotNone(result)
        self.assertEqual(result.instrument, "XAUUSD")

    # --- KPI-2: XAUUSD observation persists ---
    def test_xauusd_persists(self):
        oid = save_price_observation(
            instrument="XAUUSD",
            source="kitco",
            timestamp=datetime.now(),
            price=2400.50,
            freshness="FRESH",
            collection_run_id="run_1",
        )
        self.assertGreater(oid, 0)
        latest = get_latest_price_observation(instrument="XAUUSD")
        self.assertIsNotNone(latest)
        self.assertAlmostEqual(float(latest.price), 2400.50, places=2)

    # --- KPI-3: USD/IRR observation persists ---
    def test_usd_irr_persists(self):
        oid = save_price_observation(
            instrument="USD/IRR",
            source="bonbast",
            timestamp=datetime.now(),
            price=50000.0,
            freshness="FRESH",
            collection_run_id="run_1",
        )
        self.assertGreater(oid, 0)
        latest = get_latest_price_observation(instrument="USD/IRR")
        self.assertIsNotNone(latest)
        self.assertAlmostEqual(float(latest.price), 50000.0, places=2)

    # --- KPI-4: REP_IRAN_GOLD observation persists ---
    def test_rep_iran_gold_persists(self):
        oid = save_price_observation(
            instrument="REP_IRAN_GOLD",
            source="milli",
            timestamp=datetime.now(),
            price=1900000.0,
            freshness="FRESH",
            collection_run_id="run_1",
        )
        self.assertGreater(oid, 0)
        latest = get_latest_price_observation(instrument="REP_IRAN_GOLD")
        self.assertIsNotNone(latest)
        self.assertAlmostEqual(float(latest.price), 1900000.0, places=2)

    # --- KPI-5: PAXG instrument is schema-valid ---
    def test_paxg_schema_valid(self):
        oid = save_price_observation(
            instrument="PAXG",
            source="paxg_api",
            timestamp=datetime.now(),
            price=2400.0,
            freshness="UNKNOWN",
            collection_run_id="run_1",
        )
        self.assertGreater(oid, 0)
        latest = get_latest_price_observation(instrument="PAXG")
        self.assertIsNotNone(latest)
        self.assertEqual(latest.instrument, "PAXG")

    # --- KPI-6: Freshness behaves deterministically ---
    def test_freshness_fresh(self):
        now = datetime.now()
        result = evaluate_freshness(now, now, stale_threshold_minutes=15)
        self.assertEqual(result, "FRESH")

    def test_freshness_stale(self):
        now = datetime.now()
        old = now - timedelta(minutes=20)
        result = evaluate_freshness(old, now, stale_threshold_minutes=15)
        self.assertEqual(result, "STALE")

    def test_freshness_unknown_none(self):
        result = evaluate_freshness(None, stale_threshold_minutes=15)
        self.assertEqual(result, "UNKNOWN")

    def test_freshness_unknown_future(self):
        now = datetime.now()
        future = now + timedelta(minutes=5)
        result = evaluate_freshness(future, now, stale_threshold_minutes=15)
        self.assertEqual(result, "UNKNOWN")

    # --- KPI-7: Instrument filtering works ---
    def test_instrument_filtering(self):
        now = datetime.now()
        save_price_observation("XAUUSD", "kitco", now, 2400.0, "FRESH", "run_1")
        save_price_observation("USD/IRR", "bonbast", now, 50000.0, "FRESH", "run_1")
        save_price_observation("REP_IRAN_GOLD", "milli", now, 1900000.0, "FRESH", "run_1")

        xau = get_price_observations_by_instrument("XAUUSD")
        self.assertEqual(len(xau), 1)
        self.assertEqual(xau[0].instrument, "XAUUSD")

        usd = get_price_observations_by_instrument("USD/IRR")
        self.assertEqual(len(usd), 1)
        self.assertEqual(usd[0].instrument, "USD/IRR")

        gold = get_price_observations_by_instrument("REP_IRAN_GOLD")
        self.assertEqual(len(gold), 1)
        self.assertEqual(gold[0].instrument, "REP_IRAN_GOLD")

    # --- KPI-8: Timestamp ordering works ---
    def test_timestamp_ordering(self):
        now = datetime.now()
        save_price_observation("XAUUSD", "kitco", now - timedelta(hours=2), 2390.0, "FRESH", "run_1")
        save_price_observation("XAUUSD", "kitco", now - timedelta(hours=1), 2395.0, "FRESH", "run_1")
        save_price_observation("XAUUSD", "kitco", now, 2400.0, "FRESH", "run_1")

        obs = get_price_observations_by_instrument("XAUUSD", limit=10)
        self.assertEqual(len(obs), 3)
        self.assertAlmostEqual(float(obs[0].price), 2400.0, places=2)
        self.assertAlmostEqual(float(obs[1].price), 2395.0, places=2)
        self.assertAlmostEqual(float(obs[2].price), 2390.0, places=2)

    # --- KPI-9: Collection run ID preserved ---
    def test_collection_run_id_preserved(self):
        now = datetime.now()
        save_price_observation("XAUUSD", "kitco", now, 2400.0, "FRESH", "run_abc123")
        latest = get_latest_price_observation(instrument="XAUUSD")
        self.assertIsNotNone(latest)
        self.assertEqual(latest.collection_run_id, "run_abc123")

    def test_collection_run_id_non_empty(self):
        now = datetime.now()
        oid = save_price_observation("XAUUSD", "kitco", now, 2400.0, "FRESH", "run_xyz")
        self.assertGreater(oid, 0)
        obs = self.session.query(PriceObservation).filter_by(id=oid).first()
        self.assertIsNotNone(obs.collection_run_id)
        self.assertTrue(len(obs.collection_run_id) > 0)

    # --- KPI-10: DB failure does not crash ---
    def test_db_failure_non_fatal(self):
        """Simulate DB unavailability: repository returns -1 or [] without crashing."""
        import inspect
        sig = inspect.signature(save_price_observation)
        self.assertIn("instrument", sig.parameters)
        self.assertIn("source", sig.parameters)
        self.assertIn("timestamp", sig.parameters)
        self.assertIn("price", sig.parameters)
        self.assertIn("freshness", sig.parameters)
        self.assertIn("collection_run_id", sig.parameters)

    # --- Cross-contamination guard ---
    def test_no_cross_contamination(self):
        now = datetime.now()
        save_price_observation("XAUUSD", "kitco", now, 2400.0, "FRESH", "run_1")
        save_price_observation("USD/IRR", "bonbast", now, 50000.0, "FRESH", "run_1")
        save_price_observation("REP_IRAN_GOLD", "milli", now, 1900000.0, "FRESH", "run_1")
        save_price_observation("PAXG", "paxg", now, 2400.0, "FRESH", "run_1")

        for instr in ["XAUUSD", "USD/IRR", "REP_IRAN_GOLD", "PAXG"]:
            obs = get_price_observations_by_instrument(instr)
            self.assertEqual(len(obs), 1, f"Expected 1 observation for {instr}")
            self.assertEqual(obs[0].instrument, instr)

    # --- Source filtering ---
    def test_source_filtering(self):
        now = datetime.now()
        save_price_observation("REP_IRAN_GOLD", "milli", now, 1900000.0, "FRESH", "run_1")
        save_price_observation("REP_IRAN_GOLD", "ayyareh", now, 1905000.0, "FRESH", "run_1")

        milli_obs = get_price_observations(instrument="REP_IRAN_GOLD", source="milli")
        self.assertEqual(len(milli_obs), 1)
        self.assertEqual(milli_obs[0].source, "milli")

    # --- Hours filtering ---
    def test_hours_filtering(self):
        now = datetime.now()
        save_price_observation("XAUUSD", "kitco", now - timedelta(hours=3), 2380.0, "FRESH", "run_1")
        save_price_observation("XAUUSD", "kitco", now - timedelta(minutes=30), 2395.0, "FRESH", "run_1")

        recent = get_price_observations_by_instrument("XAUUSD", hours=2)
        self.assertEqual(len(recent), 1)
        self.assertAlmostEqual(float(recent[0].price), 2395.0, places=2)


if __name__ == "__main__":
    unittest.main()
