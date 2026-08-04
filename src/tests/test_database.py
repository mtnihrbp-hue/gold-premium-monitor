"""Automated tests for the database persistence layer.

Uses SQLite in-memory so tests run without a real Neon connection.
"""

import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, "src")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, MarketSnapshot, PlatformPrice, SystemEvent
from database import repository
from database import connection


class TestDatabase(unittest.TestCase):
    """Test suite for Sprint 1 database requirements."""

    @classmethod
    def setUpClass(cls):
        """Create an in-memory SQLite engine and patch get_session."""
        cls.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

        # Monkey-patch so repository functions use our test engine
        cls._orig_get_session = connection.get_session
        connection.get_session = lambda: cls.Session()

    @classmethod
    def tearDownClass(cls):
        """Restore original get_session and dispose engine."""
        connection.get_session = cls._orig_get_session
        cls.engine.dispose()

    def test_01_connection(self):
        """Database connection successful."""
        session = self.Session()
        self.assertIsNotNone(session)
        session.close()

    def test_02_tables_created(self):
        """Create tables successfully."""
        session = self.Session()
        tables = session.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {t[0] for t in tables}
        self.assertIn("market_snapshots", names)
        self.assertIn("platform_prices", names)
        self.assertIn("system_events", names)
        session.close()

    def test_03_insert_snapshot(self):
        """Insert fake market snapshot — record exists."""
        now = datetime.now()
        sid = repository.save_market_snapshot(
            timestamp=now,
            fair_price=187448499,
            premium_percent=-2.76,
            world_gold_usd=4080.70,
            usd_irr=190500,
            signal="BUY",
            confidence=None,
            platform_prices=[
                {
                    "platform_name": "Taline",
                    "price_irr": 182270000,
                    "change_irr": -970000,
                },
                {
                    "platform_name": "Milli",
                    "price_irr": 182270000,
                    "change_irr": None,
                },
            ],
        )
        self.assertIsNotNone(sid)
        self.assertIsInstance(sid, int)

        session = self.Session()
        snapshot = session.query(MarketSnapshot).filter_by(id=sid).first()
        self.assertIsNotNone(snapshot)
        self.assertEqual(float(snapshot.fair_price), 187448499.0)
        self.assertEqual(float(snapshot.premium_percent), -2.76)
        self.assertEqual(snapshot.signal, "BUY")

        platforms = (
            session.query(PlatformPrice)
            .filter_by(snapshot_id=sid)
            .order_by(PlatformPrice.id)
            .all()
        )
        self.assertEqual(len(platforms), 2)
        self.assertEqual(platforms[0].platform_name, "Taline")
        self.assertEqual(float(platforms[0].change_irr), -970000.0)
        session.close()

    def test_04_retrieve_latest(self):
        """Retrieve latest snapshot — correct data returned."""
        latest = repository.get_latest_market_snapshot()
        self.assertIsNotNone(latest)
        self.assertEqual(float(latest.premium_percent), -2.76)

    def test_05_failure_handling(self):
        """Database unavailable simulation — application continues."""
        orig = connection.get_session
        connection.get_session = lambda: None
        try:
            result = repository.get_latest_market_snapshot()
            self.assertIsNone(result)

            snapshots = repository.get_snapshots(days=7)
            self.assertEqual(snapshots, [])
        finally:
            connection.get_session = orig


if __name__ == "__main__":
    unittest.main()
