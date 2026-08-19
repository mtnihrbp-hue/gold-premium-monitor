"""Tests for PRE-SP-C.3: Price Structure + Regime.

Deterministic tests for:
- Representative price fallback
- Support/resistance local extrema + clustering
- Regime classification + hysteresis
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
from analysis.structure import (
    build_structure_state,
    _find_local_extrema,
    _cluster_extrema,
    _strength_from_touches,
)
from analysis.regime import RegimeClassifier, REGIME_STATES


class TestRepresentativePrice(unittest.TestCase):
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

    def _save_obs(self, source, price, freshness="FRESH", minutes_ago=0):
        ts = datetime.now() - timedelta(minutes=minutes_ago)
        save_price_observation("REP_IRAN_GOLD", source, ts, price, freshness)

    # --- 1. Milli available → Milli selected ---
    def test_milli_first(self):
        self._save_obs("milli", 194000000.0)
        result = get_representative_price()
        self.assertEqual(result.source, "milli")
        self.assertEqual(result.status, "AVAILABLE")
        self.assertAlmostEqual(result.price, 194000000.0, places=2)

    # --- 2. Milli unavailable, Ayyareh available → Ayyareh selected ---
    def test_fallback_to_ayyareh(self):
        self._save_obs("ayyareh", 194500000.0)
        result = get_representative_price()
        self.assertEqual(result.source, "ayyareh")
        self.assertAlmostEqual(result.price, 194500000.0, places=2)

    # --- 3. Milli + Ayyareh unavailable, WallGold available → WallGold selected ---
    def test_fallback_to_wallgold(self):
        self._save_obs("wallgold", 195000000.0)
        result = get_representative_price()
        self.assertEqual(result.source, "wallgold")
        self.assertAlmostEqual(result.price, 195000000.0, places=2)

    # --- 4. All unavailable → UNKNOWN ---
    def test_all_unavailable(self):
        result = get_representative_price()
        self.assertEqual(result.source, "UNKNOWN")
        self.assertEqual(result.status, "UNKNOWN")
        self.assertIsNone(result.price)
        self.assertIsNotNone(result.fallback_reason)

    # --- 5. Invalid prices do not win the fallback chain ---
    def test_invalid_price_skipped(self):
        self._save_obs("milli", -100.0)
        self._save_obs("ayyareh", 0.0)
        self._save_obs("wallgold", 195000000.0)
        result = get_representative_price()
        self.assertEqual(result.source, "wallgold")

    # --- 6. Stale Milli skipped when freshness=FRESH ---
    def test_stale_milli_skipped(self):
        self._save_obs("milli", 194000000.0, freshness="STALE")
        self._save_obs("ayyareh", 194500000.0, freshness="FRESH")
        result = get_representative_price(freshness_required="FRESH")
        self.assertEqual(result.source, "ayyareh")

    # --- 7. Fallback chain order is fixed ---
    def test_chain_order_fixed(self):
        self.assertEqual(FALLBACK_CHAIN, ["milli", "ayyareh", "wallgold"])


class TestSupportResistance(unittest.TestCase):
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

    def _seed_prices(self, prices):
        now = datetime.now()
        for i, p in enumerate(prices):
            ts = now - timedelta(hours=len(prices) - i)
            save_price_observation("REP_IRAN_GOLD", "milli", ts, float(p), "FRESH")

    # --- 8. Known local low → support candidate ---
    def test_local_low_support(self):
        prices = [190, 191, 192, 190, 193, 194, 195]
        self._seed_prices(prices)
        state = build_structure_state(min_history=5, neighborhood_size=1)
        self.assertEqual(state.status, "COMPLETE")
        support_prices = [l.price for l in state.support_levels]
        self.assertIn(190.0, support_prices)

    # --- 9. Known local high → resistance candidate ---
    def test_local_high_resistance(self):
        prices = [190, 192, 194, 195, 193, 191, 190]
        self._seed_prices(prices)
        state = build_structure_state(min_history=5, neighborhood_size=1)
        resistance_prices = [l.price for l in state.resistance_levels]
        self.assertIn(195.0, resistance_prices)

    # --- 10. Nearby extrema cluster into one level ---
    def test_clustering_merges_nearby(self):
        prices = [190, 192, 191, 193, 192.5, 194, 195]
        self._seed_prices(prices)
        state = build_structure_state(
            min_history=5, neighborhood_size=1, cluster_tolerance_percent=1.0
        )
        support_touches = sum(l.touches for l in state.support_levels)
        self.assertGreaterEqual(support_touches, 2)

    # --- 11. Separated extrema remain separate ---
    def test_separated_extrema_remain_separate(self):
        prices = [180, 190, 185, 200, 195, 210, 205]
        self._seed_prices(prices)
        state = build_structure_state(
            min_history=5, neighborhood_size=1, cluster_tolerance_percent=0.3
        )
        self.assertGreaterEqual(len(state.support_levels), 1)
        self.assertGreaterEqual(len(state.resistance_levels), 1)

    # --- 12. Strength increases with touches ---
    def test_strength_deterministic(self):
        self.assertEqual(_strength_from_touches(1), "WEAK")
        self.assertEqual(_strength_from_touches(2), "MODERATE")
        self.assertEqual(_strength_from_touches(3), "STRONG")
        self.assertEqual(_strength_from_touches(5), "STRONG")

    # --- 13. Insufficient history → INSUFFICIENT_DATA ---
    def test_insufficient_history(self):
        prices = [190, 191]
        self._seed_prices(prices)
        state = build_structure_state(min_history=10)
        self.assertEqual(state.status, "INSUFFICIENT_DATA")
        self.assertEqual(len(state.support_levels), 0)
        self.assertEqual(len(state.resistance_levels), 0)

    # --- 14. No look-ahead leakage ---
    def test_no_lookahead(self):
        prices = [190, 191, 192, 193, 194, 195, 196]
        self._seed_prices(prices)
        state = build_structure_state(min_history=5, neighborhood_size=1)
        self.assertEqual(len(state.support_levels), 0)
        self.assertEqual(len(state.resistance_levels), 0)


class TestRegimeClassifier(unittest.TestCase):
    def setUp(self):
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

    # --- 15. Low stress → NORMAL ---
    def test_low_stress_normal(self):
        evidence = {
            "premium_percent": 0.5,
            "premium_change": 0.2,
            "volatility": 0.5,
            "usd_change": 0.1,
            "platform_spread": 100000.0,
            "high_impact_news_count": 0,
        }
        result = self.classifier.classify(evidence)
        self.assertEqual(result.state, "NORMAL")

    # --- 16. Elevated stress → FEAR ---
    def test_elevated_stress_fear(self):
        evidence = {
            "premium_percent": 3.0,
            "premium_change": 0.2,
            "volatility": 0.5,
            "usd_change": 0.1,
            "platform_spread": 100000.0,
            "high_impact_news_count": 0,
        }
        result = self.classifier.classify(evidence)
        self.assertEqual(result.state, "FEAR")

    # --- 17. Multiple severe aligned stress families → PANIC ---
    def test_multiple_stress_panic(self):
        evidence = {
            "premium_percent": 3.0,
            "premium_change": 0.2,
            "volatility": 2.0,
            "usd_change": 0.1,
            "platform_spread": 100000.0,
            "high_impact_news_count": 0,
        }
        result = self.classifier.classify(evidence)
        self.assertEqual(result.state, "PANIC")

    # --- 18. Easing stress after stress → RELIEF ---
    def test_relief_after_panic(self):
        panic_evidence = {
            "premium_percent": 3.0,
            "volatility": 2.0,
            "premium_change": 0.2,
        }
        self.classifier._hysteresis_enabled = False
        result = self.classifier.classify(panic_evidence)
        self.assertEqual(result.state, "PANIC")

        self.classifier._hysteresis_enabled = True
        relief_evidence = {
            "premium_percent": 3.0,
            "volatility": 2.0,
            "premium_change": 0.2,
            "previous_regime": "PANIC",
        }
        result1 = self.classifier.classify(relief_evidence)
        result2 = self.classifier.classify(relief_evidence)
        self.assertEqual(result2.state, "RELIEF")

    # --- 19. Insufficient evidence → UNKNOWN ---
    def test_insufficient_unknown(self):
        evidence = {}
        result = self.classifier.classify(evidence)
        self.assertEqual(result.state, "NORMAL")

    # --- 20. CHEAP + PANIC remains valid ---
    def test_cheap_plus_panic_valid(self):
        evidence = {
            "premium_percent": -3.0,
            "volatility": 2.0,
            "premium_change": 0.2,
        }
        self.classifier.reset_hysteresis()
        self.classifier._hysteresis_enabled = False
        result = self.classifier.classify(evidence)
        self.assertEqual(result.state, "PANIC")

    # --- 21. Regime does not create BUY/SELL ---
    def test_regime_no_decision(self):
        evidence = {
            "premium_percent": -3.0,
            "volatility": 2.0,
        }
        result = self.classifier.classify(evidence)
        self.assertIn(result.state, REGIME_STATES)
        self.assertNotIn(result.state, ["BUY", "SELL", "WAIT"])

    # --- 22. Hysteresis prevents one-observation flips ---
    def test_hysteresis_prevents_rapid_flip(self):
        self.classifier.reset_hysteresis()
        self.classifier._hysteresis_enabled = False
        self.classifier.classify({"premium_percent": 0.0})

        self.classifier._hysteresis_enabled = True
        evidence = {"premium_percent": 3.0}
        result = self.classifier.classify(evidence)
        self.assertEqual(result.state, "NORMAL")
        self.assertTrue(result.hysteresis_active)

    # --- 23. Configurable thresholds alter classification ---
    def test_configurable_thresholds(self):
        high_config = {
            "stress_thresholds": {"premium_magnitude": 5.0},
            "confirmation_periods": 1,
            "hysteresis_enabled": False,
        }
        high_cls = RegimeClassifier(high_config)
        result = high_cls.classify({"premium_percent": 3.0})
        self.assertEqual(result.state, "NORMAL")

        low_config = {
            "stress_thresholds": {"premium_magnitude": 1.0},
            "confirmation_periods": 1,
            "hysteresis_enabled": False,
        }
        low_cls = RegimeClassifier(low_config)
        result = low_cls.classify({"premium_percent": 3.0})
        self.assertEqual(result.state, "FEAR")

    # --- 24. Four evidence families are evaluated ---
    def test_four_families_evaluated(self):
        evidence = {
            "premium_percent": 3.0,
            "volatility": 2.0,
            "usd_change": 0.8,
            "platform_spread": 600000.0,
            "high_impact_news_count": 5,
        }
        result = self.classifier.classify(evidence)
        family_names = [f.name for f in result.evidence]
        self.assertEqual(len(family_names), 4)
        self.assertIn("PREMIUM_STRESS", family_names)
        self.assertIn("VOLATILITY_STRESS", family_names)
        self.assertIn("STRUCTURE_STRESS", family_names)
        self.assertIn("EVENT_STRESS", family_names)

    # --- 25. Evidence exposes component details ---
    def test_evidence_exposed(self):
        evidence = {"premium_percent": 3.0}
        result = self.classifier.classify(evidence)
        premium_family = next(f for f in result.evidence if f.name == "PREMIUM_STRESS")
        self.assertTrue(premium_family.stressed)
        self.assertIn("premium_percent", premium_family.evidence)


if __name__ == "__main__":
    unittest.main()
