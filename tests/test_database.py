"""Tests for database repository layer (Sprint 1 + Task C + Refinements)."""

import sys

sys.path.insert(0, "src")

import os
import unittest
from datetime import datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from database.connection import init_db, get_session, Base
from database.repository import (
    save_market_snapshot,
    get_latest_market_snapshot,
    get_snapshots,
    get_daily_premium_stats,
    get_premium_momentum_context,
    get_input_directions,
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
        for table in reversed(Base.metadata.sorted_tables):
            self.session.execute(table.delete())
        self.session.commit()
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

    # --- Refinement R3: Verbal direction consistency ---

    def test_verbal_direction_uses_today_diff(self):
        """When today data exists, verbal direction must match today label."""
        today = datetime.now().date()
        base = datetime.combine(today, datetime.min.time())
        for i, premium in enumerate([-4.0, -4.2, -3.8]):
            save_market_snapshot(
                timestamp=base + timedelta(hours=i * 4),
                fair_price=100000000,
                premium_percent=premium,
            )

        # Current = -4.10, today avg = -4.0
        # diff = -0.10 → Discount Deepening, Toward Buy
        context = get_premium_momentum_context(-4.10, self.session)
        self.assertEqual(context["premium_vs_today"]["label"], "Discount Deepening")
        self.assertEqual(context["verbal_direction"], "Toward Buy")

        # Current = -3.90, today avg = -4.0
        # diff = +0.10 → Premium Expanding, Toward Sell
        context = get_premium_momentum_context(-3.90, self.session)
        self.assertEqual(context["premium_vs_today"]["label"], "Premium Expanding")
        self.assertEqual(context["verbal_direction"], "Toward Sell")

    def test_verbal_direction_uses_yesterday_when_today_missing(self):
        """When today data is missing, fall back to yesterday diff."""
        yesterday = datetime.now().date() - timedelta(days=1)
        base_yesterday = datetime.combine(yesterday, datetime.min.time())
        save_market_snapshot(
            timestamp=base_yesterday + timedelta(hours=12),
            fair_price=100000000,
            premium_percent=-3.0,
        )

        # Current = -4.0, yesterday avg = -3.0
        # diff = -1.0 → Discount Deepening, Toward Buy
        context = get_premium_momentum_context(-4.0, self.session)
        self.assertIsNone(context["premium_vs_today"])
        self.assertIsNotNone(context["premium_vs_yesterday"])
        self.assertEqual(context["verbal_direction"], "Toward Buy")

    # --- Refinement R1: Input directions ---

    def test_input_directions_world_and_usd(self):
        now = datetime.now()
        for i in range(3):
            save_market_snapshot(
                timestamp=now - timedelta(hours=i),
                fair_price=100000000,
                premium_percent=-2.0,
                world_gold_usd=2400.0,
                usd_irr=50000 + i * 100,
            )

        directions = get_input_directions(2400.0, 50300, self.session)
        self.assertEqual(directions["world"]["arrow"], "→")
        self.assertEqual(directions["world"]["pct"], 0.0)
        self.assertEqual(directions["world"]["stale_count"], 3)
        self.assertEqual(directions["usd"]["arrow"], "↑")
        self.assertGreater(directions["usd"]["pct"], 0)

    def test_input_directions_no_history(self):
        directions = get_input_directions(2400.0, 50000, self.session)
        self.assertEqual(directions["world"]["arrow"], "→")
        self.assertEqual(directions["world"]["stale_count"], 0)
        self.assertEqual(directions["usd"]["arrow"], "→")
        self.assertEqual(directions["usd"]["stale_count"], 0)

    def test_input_directions_none_inputs(self):
        directions = get_input_directions(None, 50000, self.session)
        self.assertEqual(directions["world"]["arrow"], "→")
        self.assertEqual(directions["usd"]["arrow"], "→")

    def test_input_directions_stale_detection(self):
        now = datetime.now()
        for i in range(5):
            save_market_snapshot(
                timestamp=now - timedelta(hours=i),
                fair_price=100000000,
                premium_percent=-2.0,
                world_gold_usd=2400.0,
                usd_irr=50000,
            )

        directions = get_input_directions(2400.0, 50000, self.session)
        self.assertEqual(directions["world"]["stale_count"], 5)
        self.assertEqual(directions["usd"]["stale_count"], 5)

    # --- Hypotheses (SP3 Foundation) ---

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
