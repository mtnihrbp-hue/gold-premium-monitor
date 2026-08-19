"""Tests for PRE-SP-C.4: Analysis Snapshot Integration."""

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
    get_analysis_snapshots,
)
from database.models import AnalysisSnapshot, MarketState
from analysis.snapshot_builder import build_analysis_snapshot
from analysis.regime import RegimeClassifier


class TestPreSPC4(unittest.TestCase):
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

    def test_snapshot_includes_regime_state(self):
        now = datetime.now()
        oid = build_analysis_snapshot(analysis_timestamp=now)
        self.assertGreater(oid, 0)
        latest = get_latest_analysis_snapshot()
        self.assertIn(latest.regime_state, ["NORMAL", "FEAR", "PANIC", "RELIEF", "UNKNOWN"])

    def test_snapshot_includes_technical_json(self):
        now = datetime.now()
        build_analysis_snapshot(analysis_timestamp=now)
        latest = get_latest_analysis_snapshot()
        self.assertIsNotNone(latest.technical_state_json)
        self.assertIn("representative_price", latest.technical_state_json)
        self.assertIn("support_levels", latest.technical_state_json)
        self.assertIn("resistance_levels", latest.technical_state_json)

    def test_representative_price_in_snapshot(self):
        now = datetime.now()
        build_analysis_snapshot(analysis_timestamp=now)
        latest = get_latest_analysis_snapshot()
        tech = latest.technical_state_json
        self.assertIsNotNone(tech["representative_price"])
        self.assertEqual(tech["representative_price"]["source"], "milli")
        self.assertEqual(tech["representative_price"]["status"], "AVAILABLE")

    def test_support_resistance_persisted(self):
        now = datetime.now()
        build_analysis_snapshot(analysis_timestamp=now)
        latest = get_latest_analysis_snapshot()
        tech = latest.technical_state_json
        self.assertIsNotNone(tech["support_levels"])
        self.assertIsNotNone(tech["resistance_levels"])

    def test_regime_persisted(self):
        now = datetime.now()
        build_analysis_snapshot(analysis_timestamp=now)
        latest = get_latest_analysis_snapshot()
        self.assertIsNotNone(latest.regime_state)
        self.assertIn(latest.regime_state, ["NORMAL", "FEAR", "PANIC", "RELIEF", "UNKNOWN"])

    def test_regime_evidence_persisted(self):
        now = datetime.now()
        build_analysis_snapshot(analysis_timestamp=now)
        latest = get_latest_analysis_snapshot()
        dq = latest.data_quality_json or {}
        self.assertIn("regime", dq)

    def test_hysteresis_survives_recreation(self):
        now = datetime.now()
        oid1 = build_analysis_snapshot(analysis_timestamp=now)
        self.assertGreater(oid1, 0)
        snap1 = get_latest_analysis_snapshot()
        classifier = RegimeClassifier()
        classifier.restore_state(
            previous_state=snap1.regime_state,
            candidate_state=snap1.regime_candidate_state,
            confirmation_count=snap1.regime_confirmation_count or 0,
        )
        self.assertEqual(classifier._previous_state, snap1.regime_state)
        self.assertEqual(classifier._candidate_state, snap1.regime_candidate_state)
        self.assertEqual(classifier._confirmation_count, snap1.regime_confirmation_count or 0)

    def test_second_run_reconstructs_regime(self):
        now = datetime.now()
        build_analysis_snapshot(analysis_timestamp=now)
        snap1 = get_latest_analysis_snapshot()
        first_regime = snap1.regime_state
        later = now + timedelta(minutes=30)
        oid2 = build_analysis_snapshot(analysis_timestamp=later)
        self.assertGreater(oid2, 0)
        snap2 = get_latest_analysis_snapshot()
        self.assertEqual(snap2.previous_regime, first_regime)

    def test_confirmation_count_survives(self):
        now = datetime.now()
        build_analysis_snapshot(analysis_timestamp=now)
        snap1 = get_latest_analysis_snapshot()
        later = now + timedelta(minutes=30)
        build_analysis_snapshot(analysis_timestamp=later)
        snap2 = get_latest_analysis_snapshot()
        self.assertIsNotNone(snap2.regime_confirmation_count)

    def test_regime_transition_deterministic(self):
        now = datetime.now()
        build_analysis_snapshot(analysis_timestamp=now)
        oid_dup = build_analysis_snapshot(analysis_timestamp=now)
        self.assertEqual(oid_dup, -1)

    def test_unknown_technical_explicit(self):
        for table in reversed(Base.metadata.sorted_tables):
            if table.name == "price_observations":
                self.session.execute(table.delete())
        self.session.commit()
        now = datetime.now()
        build_analysis_snapshot(analysis_timestamp=now)
        latest = get_latest_analysis_snapshot()
        tech = latest.technical_state_json
        self.assertEqual(tech["structure_status"], "INSUFFICIENT_DATA")

    def test_c2_snapshot_behavior_intact(self):
        now = datetime.now()
        oid = build_analysis_snapshot(analysis_timestamp=now)
        self.assertGreater(oid, 0)
        latest = get_latest_analysis_snapshot()
        self.assertEqual(latest.snapshot_type, "analysis")
        self.assertIsNotNone(latest.source_run_id)
        self.assertIsNotNone(latest.analysis_timestamp)

    def test_invi_collector_contract(self):
        from collector.invi import get_invi_price
        result = get_invi_price()
        self.assertIn("platform", result)
        self.assertIn("price", result)
        self.assertIn("status", result)
        self.assertEqual(result["platform"], "Invi")
        self.assertEqual(result["status"], "OK")
        self.assertIsInstance(result["price"], (int, float))

    def test_invi_in_platform_collection(self):
        from collector.iran import COLLECTORS
        from collector.invi import get_invi_price
        self.assertIn(get_invi_price, COLLECTORS)

    def test_invi_failure_isolated(self):
        from collector.iran import get_market_prices
        try:
            markets = get_market_prices()
            self.assertIsInstance(markets, dict)
        except Exception as e:
            self.fail(f"get_market_prices crashed: {e}")

    def test_invi_does_not_alter_fallback(self):
        from analysis.representative_price import FALLBACK_CHAIN
        self.assertEqual(FALLBACK_CHAIN, ["milli", "ayyareh", "wallgold"])

    def test_c3_primitives_pure(self):
        from analysis.representative_price import get_representative_price
        from analysis.structure import build_structure_state
        from analysis.regime import RegimeClassifier
        r1 = get_representative_price()
        r2 = get_representative_price()
        self.assertEqual(r1.source, r2.source)
        self.assertEqual(r1.price, r2.price)
        s1 = build_structure_state(min_history=5, neighborhood_size=1)
        s2 = build_structure_state(min_history=5, neighborhood_size=1)
        self.assertEqual(s1.status, s2.status)

    def test_regime_no_decision(self):
        now = datetime.now()
        build_analysis_snapshot(analysis_timestamp=now)
        latest = get_latest_analysis_snapshot()
        self.assertNotIn(latest.regime_state, ["BUY", "SELL", "WAIT"])

    def test_candidate_final_separation(self):
        now = datetime.now()
        build_analysis_snapshot(analysis_timestamp=now)
        latest = get_latest_analysis_snapshot()
        self.assertIsNotNone(latest.market_state_id)


if __name__ == "__main__":
    unittest.main()
