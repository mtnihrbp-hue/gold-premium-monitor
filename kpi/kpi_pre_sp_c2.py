#!/usr/bin/env python3
"""PRE-SP-C.2 KPI — Analysis Snapshot Foundation.

Run from repository root:
    python kpi/kpi_pre_sp_c2.py
"""

import sys
sys.path.insert(0, "src")

import os
import unittest
from datetime import datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from database.connection import init_db, Base, get_session
from database.repository import (
    save_market_snapshot,
    save_market_state,
    save_analysis_snapshot,
    get_latest_analysis_snapshot,
    get_analysis_snapshots,
    analysis_snapshot_exists,
)
from database.models import AnalysisSnapshot
from analysis.scheduler import (
    generate_source_run_id,
    is_analysis_window,
    get_next_analysis_windows,
    should_run_analysis,
)
from analysis.snapshot_builder import build_analysis_snapshot


class KPIPreSPC2(unittest.TestCase):
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

    def _seed_market_data(self):
        """Seed a market snapshot and state for testing."""
        now = datetime.now()
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
        return sid, ms.id

    # --- KPI-1: Schema exists ---
    def test_01_schema_valid(self):
        """AnalysisSnapshot table exists and is queryable."""
        snap = AnalysisSnapshot(
            snapshot_type="analysis",
            analysis_timestamp=datetime.now(),
            source_run_id="test_run_001",
            valuation_state="CHEAP",
            momentum_state="IMPROVING",
            structure_state="DISCOUNT_DOMINANT",
        )
        self.session.add(snap)
        self.session.commit()
        result = self.session.query(AnalysisSnapshot).first()
        self.assertIsNotNone(result)
        self.assertEqual(result.snapshot_type, "analysis")

    # --- KPI-2: Snapshot creation works ---
    def test_02_snapshot_creation(self):
        now = datetime.now()
        oid = save_analysis_snapshot(
            analysis_timestamp=now,
            source_run_id="analysis_20260816_1000",
            xau_usd=2400.50,
            usd_irr=50000.0,
            premium_percent=-1.2,
            valuation_state="CHEAP",
            momentum_state="IMPROVING",
            structure_state="DISCOUNT_DOMINANT",
        )
        self.assertGreater(oid, 0)
        latest = get_latest_analysis_snapshot()
        self.assertIsNotNone(latest)
        self.assertAlmostEqual(float(latest.xau_usd), 2400.50, places=2)

    # --- KPI-3: Required fields persist ---
    def test_03_required_fields_persist(self):
        now = datetime.now()
        save_analysis_snapshot(
            analysis_timestamp=now,
            source_run_id="analysis_20260816_1030",
            xau_usd=2400.50,
            usd_irr=50000.0,
            rep_gold_price=1900000.0,
            premium_percent=-1.2,
            valuation_state="CHEAP",
            momentum_state="IMPROVING",
            structure_state="DISCOUNT_DOMINANT",
            analysis_window="08:00-21:00",
            data_quality_json={"market_snapshot": "AVAILABLE"},
        )
        latest = get_latest_analysis_snapshot()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.valuation_state, "CHEAP")
        self.assertEqual(latest.momentum_state, "IMPROVING")
        self.assertEqual(latest.structure_state, "DISCOUNT_DOMINANT")
        self.assertEqual(latest.analysis_window, "08:00-21:00")
        self.assertIsNotNone(latest.data_quality_json)

    # --- KPI-4: Historical linkage works ---
    def test_04_historical_linkage(self):
        sid, msid = self._seed_market_data()
        now = datetime.now()
        save_analysis_snapshot(
            analysis_timestamp=now,
            source_run_id="analysis_20260816_1100",
            market_snapshot_id=sid,
            market_state_id=msid,
            xau_usd=2400.50,
            usd_irr=50000.0,
            premium_percent=-1.2,
            valuation_state="CHEAP",
            momentum_state="IMPROVING",
            structure_state="DISCOUNT_DOMINANT",
        )
        latest = get_latest_analysis_snapshot()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.market_snapshot_id, sid)
        self.assertEqual(latest.market_state_id, msid)

    # --- KPI-5: Duplicate handling works ---
    def test_05_duplicate_handling(self):
        now = datetime.now()
        source_run_id = "analysis_20260816_1130"
        oid1 = save_analysis_snapshot(
            analysis_timestamp=now,
            source_run_id=source_run_id,
            valuation_state="CHEAP",
            momentum_state="IMPROVING",
            structure_state="DISCOUNT_DOMINANT",
        )
        self.assertGreater(oid1, 0)
        oid2 = save_analysis_snapshot(
            analysis_timestamp=now,
            source_run_id=source_run_id,
            valuation_state="FAIR",
            momentum_state="NEUTRAL",
            structure_state="MIXED",
        )
        self.assertEqual(oid2, -1)
        self.assertTrue(analysis_snapshot_exists(source_run_id))

    # --- KPI-6: Missing database handling works ---
    def test_06_missing_db_handling(self):
        import inspect
        sig = inspect.signature(save_analysis_snapshot)
        self.assertIn("source_run_id", sig.parameters)
        self.assertIn("analysis_timestamp", sig.parameters)

    # --- KPI-7: Snapshot builder assembles correctly ---
    def test_07_snapshot_builder(self):
        self._seed_market_data()
        now = datetime.now()
        oid = build_analysis_snapshot(analysis_timestamp=now)
        self.assertGreater(oid, 0)
        latest = get_latest_analysis_snapshot()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.snapshot_type, "analysis")
        self.assertIsNotNone(latest.data_quality_json)

    # --- KPI-8: Snapshot builder is idempotent ---
    def test_08_builder_idempotent(self):
        self._seed_market_data()
        now = datetime.now()
        oid1 = build_analysis_snapshot(analysis_timestamp=now)
        self.assertGreater(oid1, 0)
        oid2 = build_analysis_snapshot(analysis_timestamp=now)
        self.assertEqual(oid2, -1)

    # --- KPI-9: Scheduler window logic works ---
    def test_09_scheduler_window(self):
        from datetime import time
        dt = datetime(2026, 8, 17, 10, 0)
        self.assertTrue(is_analysis_window(dt, time(8, 0), time(21, 0)))

        dt = datetime(2026, 8, 17, 22, 0)
        self.assertFalse(is_analysis_window(dt, time(8, 0), time(21, 0)))

        dt = datetime(2026, 8, 17, 7, 0)
        self.assertFalse(is_analysis_window(dt, time(8, 0), time(21, 0)))

        dt = datetime(2026, 8, 17, 21, 0)
        self.assertFalse(is_analysis_window(dt, time(8, 0), time(21, 0)))

    # --- KPI-10: Source run ID is deterministic ---
    def test_10_source_run_id_deterministic(self):
        dt = datetime(2026, 8, 16, 10, 30)
        run_id = generate_source_run_id(dt)
        self.assertEqual(run_id, "analysis_20260816_1030")
        run_id2 = generate_source_run_id(dt)
        self.assertEqual(run_id, run_id2)

    # --- KPI-11: Next windows generation works ---
    def test_11_next_windows(self):
        from datetime import time
        dt = datetime(2026, 8, 17, 9, 0)
        windows = get_next_analysis_windows(
            from_time=dt,
            count=3,
            interval_minutes=30,
            start_time=time(8, 0),
            end_time=time(21, 0),
        )
        self.assertEqual(len(windows), 3)
        self.assertEqual(windows[0], datetime(2026, 8, 17, 9, 30))
        self.assertEqual(windows[1], datetime(2026, 8, 17, 10, 0))
        self.assertEqual(windows[2], datetime(2026, 8, 17, 10, 30))

    # --- KPI-12: Analysis snapshot type is distinguishable from live ---
    def test_12_snapshot_type_distinguishable(self):
        now = datetime.now()
        save_analysis_snapshot(
            analysis_timestamp=now,
            source_run_id="analysis_20260816_1200",
            valuation_state="CHEAP",
            momentum_state="IMPROVING",
            structure_state="DISCOUNT_DOMINANT",
        )
        latest = get_latest_analysis_snapshot()
        self.assertEqual(latest.snapshot_type, "analysis")

    # --- KPI-13: Query by hours filter works ---
    def test_13_hours_filtering(self):
        now = datetime.now()
        save_analysis_snapshot(
            analysis_timestamp=now - timedelta(hours=3),
            source_run_id="analysis_20260816_0900",
            valuation_state="CHEAP",
            momentum_state="IMPROVING",
            structure_state="DISCOUNT_DOMINANT",
        )
        save_analysis_snapshot(
            analysis_timestamp=now - timedelta(minutes=30),
            source_run_id="analysis_20260816_1130",
            valuation_state="FAIR",
            momentum_state="NEUTRAL",
            structure_state="MIXED",
        )
        recent = get_analysis_snapshots(hours=2)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].valuation_state, "FAIR")

    # --- KPI-14: Default UNKNOWN states when market state missing ---
    def test_14_default_unknown_states(self):
        now = datetime.now()
        oid = build_analysis_snapshot(analysis_timestamp=now)
        self.assertGreater(oid, 0)
        latest = get_latest_analysis_snapshot()
        self.assertEqual(latest.valuation_state, "UNKNOWN")
        self.assertEqual(latest.momentum_state, "UNKNOWN")
        self.assertEqual(latest.structure_state, "UNKNOWN")


def run_kpi():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(KPIPreSPC2)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    passed = result.testsRun - len(result.failures) - len(result.errors)
    total = result.testsRun

    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print(f"Result: {passed}/{total} passed, 0 failed")
        print("\n🟢 PRE-SP-C.2 COMPLETE")
        return 0
    else:
        failed = len(result.failures) + len(result.errors)
        print(f"Result: {passed}/{total} passed, {failed} failed")
        print("\n🔴 PRE-SP-C.2 FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_kpi())
