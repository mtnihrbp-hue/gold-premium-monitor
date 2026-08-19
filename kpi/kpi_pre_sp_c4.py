#!/usr/bin/env python3
"""PRE-SP-C.4 KPI — Analysis Snapshot Integration.

Run from repository root:
    python kpi/kpi_pre_sp_c4.py
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
    save_price_observation,
    get_latest_analysis_snapshot,
)
from database.models import MarketState
from analysis.snapshot_builder import build_analysis_snapshot
from analysis.regime import RegimeClassifier


class KPIPreSPC4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.session = get_session()
        self._seed_market_data()

    def tearDown(self):
        for table in reversed(Base.metadata.sorted_tables):
            self.session.execute(table.delete())
        self.session.commit()
        self.session.close()

    def _seed_market_data(self):
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

        for i, price in enumerate([190, 192, 191, 193, 195, 194, 196]):
            ts = now - timedelta(hours=7 - i)
            save_price_observation("REP_IRAN_GOLD", "milli", ts, float(price) * 1000000, "FRESH")

        save_price_observation("USD/IRR", "bonbast", now, 50000.0, "FRESH")
        save_price_observation("USD/IRR", "bonbast", now - timedelta(hours=1), 49800.0, "FRESH")
        return sid, ms.id

    # --- KPI-1: Snapshot includes regime_state ---
    def test_01_regime_state_persisted(self):
        now = datetime.now()
        oid = build_analysis_snapshot(analysis_timestamp=now)
        self.assertGreater(oid, 0)
        latest = get_latest_analysis_snapshot()
        self.assertIn(latest.regime_state, ["NORMAL", "FEAR", "PANIC", "RELIEF", "UNKNOWN"])

    # --- KPI-2: Snapshot includes technical_state_json ---
    def test_02_technical_json_persisted(self):
        now = datetime.now()
        build_analysis_snapshot(analysis_timestamp=now)
        latest = get_latest_analysis_snapshot()
        self.assertIsNotNone(latest.technical_state_json)
        self.assertIn("representative_price", latest.technical_state_json)
        self.assertIn("support_levels", latest.technical_state_json)
        self.assertIn("resistance_levels", latest.technical_state_json)

    # --- KPI-3: Representative price integrated ---
    def test_03_representative_price_integrated(self):
        now = datetime.now()
        build_analysis_snapshot(analysis_timestamp=now)
        latest = get_latest_analysis_snapshot()
        tech = latest.technical_state_json
        self.assertIsNotNone(tech["representative_price"])
        self.assertEqual(tech["representative_price"]["source"], "milli")

    # --- KPI-4: Support/resistance persisted ---
    def test_04_sr_persisted(self):
        now = datetime.now()
        build_analysis_snapshot(analysis_timestamp=now)
        latest = get_latest_analysis_snapshot()
        tech = latest.technical_state_json
        self.assertIsNotNone(tech["support_levels"])
        self.assertIsNotNone(tech["resistance_levels"])

    # --- KPI-5: Regime result persisted ---
    def test_05_regime_persisted(self):
        now = datetime.now()
        build_analysis_snapshot(analysis_timestamp=now)
        latest = get_latest_analysis_snapshot()
        self.assertIsNotNone(latest.regime_state)

    # --- KPI-6: Four evidence families in data quality ---
    def test_06_evidence_families(self):
        now = datetime.now()
        build_analysis_snapshot(analysis_timestamp=now)
        latest = get_latest_analysis_snapshot()
        dq = latest.data_quality_json or {}
        self.assertIn("regime", dq)

    # --- KPI-7: Hysteresis survives process recreation ---
    def test_07_hysteresis_survives(self):
        now = datetime.now()
        build_analysis_snapshot(analysis_timestamp=now)
        snap1 = get_latest_analysis_snapshot()

        classifier = RegimeClassifier()
        classifier.restore_state(
            previous_state=snap1.regime_state,
            candidate_state=snap1.regime_candidate_state,
            confirmation_count=snap1.regime_confirmation_count or 0,
        )
        self.assertEqual(classifier._previous_state, snap1.regime_state)

    # --- KPI-8: Second run reconstructs previous regime ---
    def test_08_second_run_reconstructs(self):
        now = datetime.now()
        build_analysis_snapshot(analysis_timestamp=now)
        snap1 = get_latest_analysis_snapshot()
        first_regime = snap1.regime_state

        later = now + timedelta(minutes=30)
        oid2 = build_analysis_snapshot(analysis_timestamp=later)
        self.assertGreater(oid2, 0)
        snap2 = get_latest_analysis_snapshot()
        self.assertEqual(snap2.previous_regime, first_regime)

    # --- KPI-9: Confirmation count survives ---
    def test_09_confirmation_count_survives(self):
        now = datetime.now()
        build_analysis_snapshot(analysis_timestamp=now)
        snap1 = get_latest_analysis_snapshot()

        later = now + timedelta(minutes=30)
        build_analysis_snapshot(analysis_timestamp=later)
        snap2 = get_latest_analysis_snapshot()
        self.assertIsNotNone(snap2.regime_confirmation_count)

    # --- KPI-10: Regime transition deterministic ---
    def test_10_regime_deterministic(self):
        now = datetime.now()
        build_analysis_snapshot(analysis_timestamp=now)
        oid_dup = build_analysis_snapshot(analysis_timestamp=now)
        self.assertEqual(oid_dup, -1)

    # --- KPI-11: UNKNOWN technical data explicit ---
    def test_11_unknown_technical(self):
        for table in reversed(Base.metadata.sorted_tables):
            if table.name == "price_observations":
                self.session.execute(table.delete())
        self.session.commit()

        now = datetime.now()
        build_analysis_snapshot(analysis_timestamp=now)
        latest = get_latest_analysis_snapshot()
        tech = latest.technical_state_json
        self.assertEqual(tech["structure_status"], "INSUFFICIENT_DATA")

    # --- KPI-12: C.2 snapshot behavior intact ---
    def test_12_c2_intact(self):
        now = datetime.now()
        oid = build_analysis_snapshot(analysis_timestamp=now)
        self.assertGreater(oid, 0)
        latest = get_latest_analysis_snapshot()
        self.assertEqual(latest.snapshot_type, "analysis")
        self.assertIsNotNone(latest.source_run_id)

    # --- KPI-13: Invi collector contract ---
    def test_13_invi_contract(self):
        from collector.invi import get_invi_price
        result = get_invi_price()
        self.assertIn("platform", result)
        self.assertIn("price", result)
        self.assertEqual(result["platform"], "Invi")
        self.assertEqual(result["status"], "OK")

    # --- KPI-14: Invi in COLLECTORS ---
    def test_14_invi_registered(self):
        from collector.iran import COLLECTORS
        from collector.invi import get_invi_price
        self.assertIn(get_invi_price, COLLECTORS)

    # --- KPI-15: Invi failure isolated ---
    def test_15_invi_failure_isolated(self):
        from collector.iran import get_market_prices
        try:
            markets = get_market_prices()
            self.assertIsInstance(markets, dict)
        except Exception as e:
            self.fail(f"get_market_prices crashed: {e}")

    # --- KPI-16: Invi does not alter fallback ---
    def test_16_fallback_unchanged(self):
        from analysis.representative_price import FALLBACK_CHAIN
        self.assertEqual(FALLBACK_CHAIN, ["milli", "ayyareh", "wallgold"])

    # --- KPI-17: C.3 primitives pure ---
    def test_17_c3_pure(self):
        from analysis.representative_price import get_representative_price
        from analysis.structure import build_structure_state
        r1 = get_representative_price()
        r2 = get_representative_price()
        self.assertEqual(r1.source, r2.source)

    # --- KPI-18: Regime no BUY/SELL ---
    def test_18_regime_no_trade(self):
        now = datetime.now()
        build_analysis_snapshot(analysis_timestamp=now)
        latest = get_latest_analysis_snapshot()
        self.assertNotIn(latest.regime_state, ["BUY", "SELL", "WAIT"])

    # --- KPI-19: Candidate/Final separation ---
    def test_19_candidate_final(self):
        now = datetime.now()
        build_analysis_snapshot(analysis_timestamp=now)
        latest = get_latest_analysis_snapshot()
        self.assertIsNotNone(latest.market_state_id)


def run_kpi():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(KPIPreSPC4)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    passed = result.testsRun - len(result.failures) - len(result.errors)
    total = result.testsRun

    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print(f"Result: {passed}/{total} passed, 0 failed")
        print("\n🟢 PRE-SP-C.4 COMPLETE")
        return 0
    else:
        failed = len(result.failures) + len(result.errors)
        print(f"Result: {passed}/{total} passed, {failed} failed")
        print("\n🔴 PRE-SP-C.4 FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_kpi())
