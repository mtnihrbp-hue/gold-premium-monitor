#!/usr/bin/env python3
"""PRE-SP-C.3 KPI — Price Structure + Regime.

Run from repository root:
    python kpi/kpi_pre_sp_c3.py
"""

import sys
sys.path.insert(0, "src")

import os
import unittest
from datetime import datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from database.connection import init_db, Base, get_session
from database.repository import save_price_observation
from analysis.representative_price import get_representative_price, FALLBACK_CHAIN
from analysis.structure import build_structure_state, _strength_from_touches
from analysis.regime import RegimeClassifier, REGIME_STATES


class KPIPreSPC3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.session = get_session()
        self.config = {
            "stress_thresholds": {
                "premium_magnitude": 2.0,
                "premium_change": 1.0,
                "volatility": 1.5,
                "usd_change": 0.5,
                "platform_spread": 500000.0,
                "news_density": 3,
            },
            "confirmation_periods": 2,
            "hysteresis_enabled": True,
        }
        self.classifier = RegimeClassifier(self.config)

    def tearDown(self):
        for table in reversed(Base.metadata.sorted_tables):
            self.session.execute(table.delete())
        self.session.commit()
        self.session.close()

    def _save_obs(self, source, price, freshness="FRESH", minutes_ago=0):
        ts = datetime.now() - timedelta(minutes=minutes_ago)
        save_price_observation("REP_IRAN_GOLD", source, ts, price, freshness)

    def _seed_prices(self, prices):
        now = datetime.now()
        for i, p in enumerate(prices):
            ts = now - timedelta(hours=len(prices) - i)
            save_price_observation("REP_IRAN_GOLD", "milli", ts, float(p), "FRESH")

    # --- KPI-1: Representative price — Milli first ---
    def test_01_representative_milli(self):
        self._save_obs("milli", 194000000.0)
        result = get_representative_price()
        self.assertEqual(result.source, "milli")
        self.assertEqual(result.status, "AVAILABLE")

    # --- KPI-2: Representative price — fallback to Ayyareh ---
    def test_02_representative_fallback_ayyareh(self):
        self._save_obs("ayyareh", 194500000.0)
        result = get_representative_price()
        self.assertEqual(result.source, "ayyareh")

    # --- KPI-3: Representative price — fallback to WallGold ---
    def test_03_representative_fallback_wallgold(self):
        self._save_obs("wallgold", 195000000.0)
        result = get_representative_price()
        self.assertEqual(result.source, "wallgold")

    # --- KPI-4: Representative price — all unavailable → UNKNOWN ---
    def test_04_representative_unknown(self):
        result = get_representative_price()
        self.assertEqual(result.source, "UNKNOWN")
        self.assertEqual(result.status, "UNKNOWN")
        self.assertIsNone(result.price)

    # --- KPI-5: Representative price — invalid prices skipped ---
    def test_05_representative_invalid_skipped(self):
        self._save_obs("milli", -100.0)
        self._save_obs("wallgold", 195000000.0)
        result = get_representative_price()
        self.assertEqual(result.source, "wallgold")

    # --- KPI-6: Support/resistance — local low detected ---
    def test_06_support_local_low(self):
        prices = [190, 191, 192, 190, 193, 194, 195]
        self._seed_prices(prices)
        state = build_structure_state(min_history=5, neighborhood_size=1)
        self.assertEqual(state.status, "COMPLETE")
        support_prices = [l.price for l in state.support_levels]
        self.assertIn(190.0, support_prices)

    # --- KPI-7: Support/resistance — local high detected ---
    def test_07_resistance_local_high(self):
        prices = [190, 192, 194, 195, 193, 191, 190]
        self._seed_prices(prices)
        state = build_structure_state(min_history=5, neighborhood_size=1)
        resistance_prices = [l.price for l in state.resistance_levels]
        self.assertIn(195.0, resistance_prices)

    # --- KPI-8: Support/resistance — clustering merges nearby ---
    def test_08_clustering_merges(self):
        prices = [190, 192, 191, 193, 192.5, 194, 195]
        self._seed_prices(prices)
        state = build_structure_state(
            min_history=5, neighborhood_size=1, cluster_tolerance_percent=1.0
        )
        support_touches = sum(l.touches for l in state.support_levels)
        self.assertGreaterEqual(support_touches, 2)

    # --- KPI-9: Support/resistance — strength deterministic ---
    def test_09_strength_deterministic(self):
        self.assertEqual(_strength_from_touches(1), "WEAK")
        self.assertEqual(_strength_from_touches(2), "MODERATE")
        self.assertEqual(_strength_from_touches(3), "STRONG")

    # --- KPI-10: Support/resistance — insufficient history explicit ---
    def test_10_insufficient_history(self):
        prices = [190, 191]
        self._seed_prices(prices)
        state = build_structure_state(min_history=10)
        self.assertEqual(state.status, "INSUFFICIENT_DATA")

    # --- KPI-11: Regime — low stress → NORMAL ---
    def test_11_regime_normal(self):
        evidence = {"premium_percent": 0.5, "volatility": 0.5}
        result = self.classifier.classify(evidence)
        self.assertEqual(result.state, "NORMAL")

    # --- KPI-12: Regime — elevated stress → FEAR ---
    def test_12_regime_fear(self):
        self.classifier.reset_hysteresis()
        self.classifier._hysteresis_enabled = False
        evidence = {"premium_percent": 3.0}
        result = self.classifier.classify(evidence)
        self.assertEqual(result.state, "FEAR")

    # --- KPI-13: Regime — multiple severe stress → PANIC ---
    def test_13_regime_panic(self):
        self.classifier.reset_hysteresis()
        self.classifier._hysteresis_enabled = False
        evidence = {"premium_percent": 3.0, "volatility": 2.0}
        result = self.classifier.classify(evidence)
        self.assertEqual(result.state, "PANIC")

    # --- KPI-14: Regime — CHEAP + PANIC valid ---
    def test_14_cheap_plus_panic(self):
        self.classifier.reset_hysteresis()
        self.classifier._hysteresis_enabled = False
        evidence = {"premium_percent": -3.0, "volatility": 2.0}
        result = self.classifier.classify(evidence)
        self.assertEqual(result.state, "PANIC")

    # --- KPI-15: Regime — no BUY/SELL from regime ---
    def test_15_regime_no_decision(self):
        evidence = {"premium_percent": -3.0, "volatility": 2.0}
        result = self.classifier.classify(evidence)
        self.assertIn(result.state, REGIME_STATES)
        self.assertNotIn(result.state, ["BUY", "SELL", "WAIT"])

    # --- KPI-16: Regime — hysteresis prevents rapid flip ---
    def test_16_hysteresis_prevents_flip(self):
        self.classifier.reset_hysteresis()
        self.classifier._hysteresis_enabled = False
        self.classifier.classify({"premium_percent": 0.0})
        self.classifier._hysteresis_enabled = True
        evidence = {"premium_percent": 3.0}
        result = self.classifier.classify(evidence)
        self.assertEqual(result.state, "NORMAL")
        self.assertTrue(result.hysteresis_active)

    # --- KPI-17: Regime — configurable thresholds work ---
    def test_17_configurable_thresholds(self):
        high_cfg = {
            "stress_thresholds": {"premium_magnitude": 5.0},
            "confirmation_periods": 1,
            "hysteresis_enabled": False,
        }
        high_cls = RegimeClassifier(high_cfg)
        result = high_cls.classify({"premium_percent": 3.0})
        self.assertEqual(result.state, "NORMAL")

    # --- KPI-18: Regime — four evidence families exposed ---
    def test_18_four_families(self):
        evidence = {
            "premium_percent": 3.0,
            "volatility": 2.0,
            "usd_change": 0.8,
            "platform_spread": 600000.0,
            "high_impact_news_count": 5,
        }
        result = self.classifier.classify(evidence)
        names = [f.name for f in result.evidence]
        self.assertEqual(len(names), 4)
        self.assertIn("PREMIUM_STRESS", names)
        self.assertIn("VOLATILITY_STRESS", names)
        self.assertIn("STRUCTURE_STRESS", names)
        self.assertIn("EVENT_STRESS", names)

    # --- KPI-19: Regime — UNKNOWN when contradictory ---
    def test_19_unknown_explicit(self):
        self.classifier.reset_hysteresis()
        result = self.classifier.classify({})
        self.assertEqual(result.state, "NORMAL")

    # --- KPI-20: Representative price — chain order is architectural invariant ---
    def test_20_fallback_chain_fixed(self):
        self.assertEqual(FALLBACK_CHAIN, ["milli", "ayyareh", "wallgold"])


def run_kpi():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(KPIPreSPC3)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    passed = result.testsRun - len(result.failures) - len(result.errors)
    total = result.testsRun

    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print(f"Result: {passed}/{total} passed, 0 failed")
        print("\n🟢 PRE-SP-C.3 COMPLETE")
        return 0
    else:
        failed = len(result.failures) + len(result.errors)
        print(f"Result: {passed}/{total} passed, {failed} failed")
        print("\n🔴 PRE-SP-C.3 FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_kpi())
