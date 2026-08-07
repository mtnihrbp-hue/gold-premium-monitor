"""Tests for database repository layer (Sprint 1 + Task C)."""


import unittest
from datetime import datetime, timedelta

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from src.database.connection import init_db, get_session
from src.database.repository import (
    save_market_snapshot,
    get_latest_market_snapshot,
    get_snapshots,
    get_daily_premium_stats,
    get_premium_momentum_context,
    save_hypothesis,
    resolve_hypothesis,
    get_hypothesis_accuracy,
)


class TestDatabaseOperations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.session = get_session()

    def tearDown(self):
        self.session.close()

    def test_save_and_read_snapshot(self):
        sid = save_market_snapshot(
            timestamp=datetime.now(),
            fair_price=100000000,
            premium_percent=-2.5,
            world_gold_usd=2400.0,
            usd_irr=50000,
            signal="BUY",
        )
        self.assertIsInstance(sid, int)
        latest = get_latest_market_snapshot()
        self.assertIsNotNone(latest)
        self.assertEqual(float(latest.premium_percent), -2.5)

    def test_get_snapshots_time_range(self):
        now = datetime.now()
        save_market_snapshot(
            timestamp=now - timedelta(days=1),
            fair_price=100000000,
            premium_percent=-1.0,
        )
        save_market_snapshot(
            timestamp=now - timedelta(days=40),
            fair_price=100000000,
            premium_percent=-3.0,
        )
        recent = get_snapshots(days=30)
        self.assertEqual(len(recent), 1)

    def test_daily_premium_stats(self):
        today = datetime.now().date()
        base = datetime.combine(today, datetime.min.time())
        for i, premium in enumerate([-3.0, -4.0, -3.5]):
            save_market_snapshot(
                timestamp=base + timedelta(hours=i * 4),
                fair_price=100000000,
                premium_percent=premium,
            )
        stats = get_daily_premium_stats(today, self.session)
        self.assertIsNotNone(stats)
        self.assertEqual(stats["count"], 3)
        self.assertAlmostEqual(stats["avg"], -3.5, places=2)
        self.assertEqual(stats["min"], -4.0)
        self.assertEqual(stats["max"], -3.0)
        self.assertEqual(stats["open"], -3.0)
        self.assertEqual(stats["close"], -3.5)

    def test_daily_premium_stats_no_data(self):
        future_date = datetime.now().date() + timedelta(days=10)
        stats = get_daily_premium_stats(future_date, self.session)
        self.assertIsNone(stats)

    def test_premium_momentum_context(self):
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        base_today = datetime.combine(today, datetime.min.time())
        base_yesterday = datetime.combine(yesterday, datetime.min.time())

        save_market_snapshot(
            timestamp=base_yesterday + timedelta(hours=12),
            fair_price=100000000,
            premium_percent=-3.0,
        )
        for i, premium in enumerate([-4.0, -4.2, -3.8]):
            save_market_snapshot(
                timestamp=base_today + timedelta(hours=i * 4),
                fair_price=100000000,
                premium_percent=premium,
            )

        context = get_premium_momentum_context(-4.10, self.session)
        self.assertIsNotNone(context["premium_vs_today"])
        self.assertIsNotNone(context["premium_vs_yesterday"])
        self.assertIsNotNone(context["candlestick"])
        self.assertAlmostEqual(context["premium_vs_today"]["diff"], -0.1, places=2)
        self.assertEqual(context["premium_vs_today"]["label"], "Discount Deepening")
        self.assertAlmostEqual(context["premium_vs_yesterday"]["diff"], -1.1, places=2)
        self.assertEqual(context["verbal_direction"], "Toward Buy")

    def test_premium_momentum_no_history(self):
        context = get_premium_momentum_context(-2.0, self.session)
        self.assertIsNone(context["premium_vs_today"])
        self.assertIsNone(context["premium_vs_yesterday"])
        self.assertEqual(context["verbal_direction"], "Neutral")

    def test_save_hypothesis(self):
        hid = save_hypothesis(
            self.session,
            hypothesis_type="mean_reversion",
            description="Premium will revert to mean",
            expected_outcome="+2%",
            horizon_hours=48,
            basis_json={"percentile": 98},
            model_version="v0.1",
            source="prediction_engine",
        )
        self.assertIsInstance(hid, int)

    def test_resolve_hypothesis(self):
        hid = save_hypothesis(
            self.session,
            hypothesis_type="mean_reversion",
            description="Premium will revert",
            expected_outcome="+2%",
        )
        success = resolve_hypothesis(
            self.session,
            hid,
            actual_outcome="+0.5%",
            result="Partially Correct",
            failure_reason="Geopolitical event",
        )
        self.assertTrue(success)

    def test_resolve_hypothesis_not_found(self):
        success = resolve_hypothesis(
            self.session,
            99999,
            actual_outcome="0%",
            result="Wrong",
        )
        self.assertFalse(success)

    def test_hypothesis_accuracy(self):
        for result in ["Correct", "Correct", "Wrong", "Partially Correct"]:
            hid = save_hypothesis(
                self.session,
                hypothesis_type="directional",
                description="Test",
                expected_outcome="+1%",
            )
            resolve_hypothesis(self.session, hid, "+1%", result)

        stats = get_hypothesis_accuracy(self.session, days=30)
        self.assertIsNotNone(stats)
        self.assertEqual(stats["total"], 4)
        self.assertEqual(stats["correct"], 2)
        self.assertEqual(stats["partially_correct"], 1)
        self.assertEqual(stats["wrong"], 1)
        self.assertAlmostEqual(stats["accuracy_rate"], 0.625, places=3)

    def test_hypothesis_accuracy_empty(self):
        stats = get_hypothesis_accuracy(self.session, days=30)
        self.assertIsNone(stats)


if __name__ == "__main__":
    unittest.main()
