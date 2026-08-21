#!/usr/bin/env python3
"""PRE-SP-C.9 KPI — Analytical Read Model.

Run from repository root:
    python kpi/kpi_pre_sp_c9.py
"""

import sys
sys.path.insert(0, "src")

import os
import unittest
from datetime import datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from database.connection import init_db, Base, get_session
from database.models import AnalysisSnapshot
from database.repository import (
    save_market_snapshot,
    save_market_state,
    save_analysis_snapshot,
    save_price_observation,
)
from intelligence.read_model import (
    build_read_model,
    validate_read_model,
    READ_MODEL_SCHEMA_VERSION,
)
from analysis.evidence_package import build_evidence_package, validate_evidence_package
from intelligence.market_intelligence import build_intelligence_result, validate_intelligence_result
from intelligence.features import build_feature_snapshot, validate_feature_snapshot
from analysis.regime import RegimeClassifier, RegimeResult, EvidenceFamily


class MockSignalState:
    def __init__(self):
        self.snapshot_id = 1
        self.valuation = "CHEAP"
        self.momentum = "IMPROVING"
        self.premium_direction = "DISCOUNT WIDENING"
        self.structure = "DISCOUNT_DOMINANT"
        self.platform_average = 1900000.0
        self.platform_high = 1905000.0
        self.platform_low = 1895000.0
        self.platform_spread = 10000.0
        self.platforms_below_fair = 3
        self.platforms_above_fair = 0
        self.conflict = "NONE"
        self.candidate_decision = "BUY"
        self.final_decision = "WAIT"
        self.reason = "Test"
        self.timestamp = datetime.now()


class KPIPreSPC9(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.session = get_session()
        self._clean_tables()
        self._seed_data()

    def tearDown(self):
        self._clean_tables()
        self.session.close()

    def _clean_tables(self):
        for table in reversed(Base.metadata.sorted_tables):
            self.session.execute(table.delete())
        self.session.commit()

    def _seed_data(self):
        now = datetime.now()
        base_price = 190000000.0

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

        ms = MockSignalState()
        ms.snapshot_id = sid
        self.market_state_id = save_market_state(ms)

        for i in range(40):
            ts = now - timedelta(hours=40 - i)
            save_price_observation("REP_IRAN_GOLD", "milli", ts, base_price + (i * 100000.0), "FRESH")
            save_price_observation("XAUUSD", "kitco", ts, 2400.0 + (i * 0.5), "FRESH")
            save_price_observation("USD/IRR", "bonbast", ts, 50000.0 + (i * 10), "FRESH")

        for i in range(20):
            ts = now - timedelta(hours=20 - i)
            save_market_snapshot(
                timestamp=ts,
                fair_price=1900000.0,
                premium_percent=-1.2 + (i * 0.05),
                world_gold_usd=2400.0 + (i * 0.5),
                usd_irr=50000.0 + (i * 10),
                signal="WAIT",
                confidence=0.75,
                platform_prices=[],
            )

        self.now = now
        self.snapshot_id = save_analysis_snapshot(
            analysis_timestamp=now,
            source_run_id="read_model_test_001",
            market_snapshot_id=sid,
            market_state_id=self.market_state_id,
            xau_usd=2400.50,
            usd_irr=50000.0,
            rep_gold_price=190000000.0,
            premium_percent=-1.2,
            valuation_state="CHEAP",
            momentum_state="IMPROVING",
            structure_state="DISCOUNT_DOMINANT",
            regime_state="NORMAL",
        )

    def _build_full_stack(self):
        """Build C.6, C.7, C.8, then C.9."""
        snap = self.session.query(AnalysisSnapshot).filter_by(id=self.snapshot_id).first()
        ms = self.session.query(__import__('database.models', fromlist=['MarketState']).MarketState).filter_by(id=self.market_state_id).first()
        MarketSnapshot = __import__('database.models', fromlist=['MarketSnapshot']).MarketSnapshot
        mkt_snap = self.session.query(MarketSnapshot).first()

        # C.6 evidence
        evidence = build_evidence_package(
            analysis_timestamp=self.now,
            source_run_id="read_model_test_001",
            market_snapshot=mkt_snap,
            market_state=ms,
            rep_price=None,
            structure_state=None,
            regime_result=RegimeResult(state="NORMAL", previous_state="NORMAL", evidence=[], confirmation_count=0, hysteresis_active=False),
            classifier=RegimeClassifier(),
            data_quality={"overall": "AVAILABLE", "xau_usd": "AVAILABLE"},
            technical_state_json=None,
            config={},
        )

        # C.7 intelligence
        intelligence = build_intelligence_result(
            evidence_package=evidence,
            model_provider="test",
            prompt_version="1",
        )

        # C.8 features
        features = build_feature_snapshot(
            analysis_timestamp=self.now,
            current_regime="NORMAL",
            previous_regime="NORMAL",
            market_state=ms,
            config={},
        )

        snapshot_facts = {
            "xau_usd": 2400.50,
            "usd_irr": 50000.0,
            "rep_gold_price": 190000000.0,
            "premium_percent": -1.2,
            "valuation_state": "CHEAP",
            "momentum_state": "IMPROVING",
            "structure_state": "DISCOUNT_DOMINANT",
            "regime_state": "NORMAL",
            "candidate_decision": "BUY",
            "final_decision": "WAIT",
        }

        return evidence, intelligence, features, snapshot_facts

    # --- KPI-1: read model builds from valid evidence ---
    def test_01_from_evidence(self):
        ev, intel, feat, facts = self._build_full_stack()
        rm = build_read_model(self.now, "test_001", 1, 1, ev, intel, feat, facts)
        self.assertIsInstance(rm, dict)
        self.assertEqual(rm["schema_version"], READ_MODEL_SCHEMA_VERSION)

    # --- KPI-2: read model builds from valid C.7 interpretation ---
    def test_02_from_intelligence(self):
        ev, intel, feat, facts = self._build_full_stack()
        rm = build_read_model(self.now, "test_001", 1, 1, ev, intel, feat, facts)
        self.assertIn("interpretation_summary", rm)
        self.assertNotEqual(rm["interpretation_summary"]["market_context_summary"], "UNKNOWN")

    # --- KPI-3: read model consumes C.8 features ---
    def test_03_from_features(self):
        ev, intel, feat, facts = self._build_full_stack()
        rm = build_read_model(self.now, "test_001", 1, 1, ev, intel, feat, facts)
        self.assertIn("features_summary", rm)
        self.assertIn("price_trend_status", rm["features_summary"])

    # --- KPI-4: deterministic output ---
    def test_04_deterministic(self):
        ev, intel, feat, facts = self._build_full_stack()
        r1 = build_read_model(self.now, "test_001", 1, 1, ev, intel, feat, facts)
        r2 = build_read_model(self.now, "test_001", 1, 1, ev, intel, feat, facts)
        self.assertEqual(r1["facts"]["valuation_state"], r2["facts"]["valuation_state"])

    # --- KPI-5: missing evidence preserved ---
    def test_05_missing_evidence(self):
        ev, intel, feat, facts = self._build_full_stack()
        ev["valuation"]["status"] = "INSUFFICIENT_DATA"
        rm = build_read_model(self.now, "test_001", 1, 1, ev, intel, feat, facts)
        self.assertEqual(rm["evidence_summary"]["valuation_status"], "INSUFFICIENT_DATA")

    # --- KPI-6: missing interpretation preserved ---
    def test_06_missing_interpretation(self):
        ev, intel, feat, facts = self._build_full_stack()
        intel["valuation_interpretation"]["interpretation"] = "INSUFFICIENT_DATA"
        rm = build_read_model(self.now, "test_001", 1, 1, ev, intel, feat, facts)
        self.assertEqual(rm["interpretation_summary"]["valuation_interpretation"], "INSUFFICIENT_DATA")

    # --- KPI-7: missing features preserved ---
    def test_07_missing_features(self):
        ev, intel, feat, facts = self._build_full_stack()
        rm = build_read_model(self.now, "test_001", 1, 1, ev, intel, None, facts)
        self.assertEqual(rm["features_summary"]["price_trend_status"], "INSUFFICIENT_DATA")
        self.assertIn("all_features", rm["uncertainty"]["missing_features"])

    # --- KPI-8: UNKNOWN propagation ---
    def test_08_unknown_propagation(self):
        ev, intel, feat, facts = self._build_full_stack()
        facts["valuation_state"] = "UNKNOWN"
        rm = build_read_model(self.now, "test_001", 1, 1, ev, intel, feat, facts)
        self.assertEqual(rm["facts"]["valuation_state"], "UNKNOWN")

    # --- KPI-9: INSUFFICIENT_DATA propagation ---
    def test_09_insufficient_data(self):
        ev, intel, feat, facts = self._build_full_stack()
        ev["momentum"]["status"] = "INSUFFICIENT_DATA"
        rm = build_read_model(self.now, "test_001", 1, 1, ev, intel, feat, facts)
        self.assertEqual(rm["evidence_summary"]["momentum_status"], "INSUFFICIENT_DATA")

    # --- KPI-10: provenance retained ---
    def test_10_provenance(self):
        ev, intel, feat, facts = self._build_full_stack()
        rm = build_read_model(self.now, "test_001", 1, 1, ev, intel, feat, facts)
        self.assertEqual(rm["provenance"]["source_run_id"], "test_001")
        self.assertEqual(rm["provenance"]["read_model_schema_version"], READ_MODEL_SCHEMA_VERSION)

    # --- KPI-11: schema version present ---
    def test_11_schema_version(self):
        ev, intel, feat, facts = self._build_full_stack()
        rm = build_read_model(self.now, "test_001", 1, 1, ev, intel, feat, facts)
        self.assertEqual(rm["schema_version"], READ_MODEL_SCHEMA_VERSION)

    # --- KPI-12: no BUY/SELL generation ---
    def test_12_no_decision(self):
        ev, intel, feat, facts = self._build_full_stack()
        rm = build_read_model(self.now, "test_001", 1, 1, ev, intel, feat, facts)
        valid, errors = validate_read_model(rm)
        self.assertTrue(valid, f"Errors: {errors}")

    # --- KPI-13: existing final_decision preserved ---
    def test_13_final_decision_preserved(self):
        ev, intel, feat, facts = self._build_full_stack()
        rm = build_read_model(self.now, "test_001", 1, 1, ev, intel, feat, facts)
        self.assertEqual(rm["decision"]["final_decision"], "WAIT")
        self.assertEqual(rm["decision"]["source"], "existing_decision_engine")

    # --- KPI-14: evidence package unchanged ---
    def test_14_evidence_unchanged(self):
        ev, intel, feat, facts = self._build_full_stack()
        ev_before = str(ev)
        rm = build_read_model(self.now, "test_001", 1, 1, ev, intel, feat, facts)
        self.assertEqual(str(ev), ev_before)

    # --- KPI-15: facts unchanged ---
    def test_15_facts_unchanged(self):
        ev, intel, feat, facts = self._build_full_stack()
        facts_before = dict(facts)
        rm = build_read_model(self.now, "test_001", 1, 1, ev, intel, feat, facts)
        self.assertEqual(facts, facts_before)

    # --- KPI-16: C.7 compatibility ---
    def test_16_c7_compatible(self):
        ev, intel, feat, facts = self._build_full_stack()
        rm = build_read_model(self.now, "test_001", 1, 1, ev, intel, feat, facts)
        self.assertIn("valuation_fact", rm["interpretation_summary"])
        self.assertIn("valuation_interpretation", rm["interpretation_summary"])

    # --- KPI-17: C.8 compatibility ---
    def test_17_c8_compatible(self):
        ev, intel, feat, facts = self._build_full_stack()
        rm = build_read_model(self.now, "test_001", 1, 1, ev, intel, feat, facts)
        self.assertIn("sufficient_history", rm["features_summary"])

    # --- KPI-18: persistence round-trip ---
    def test_18_persistence_roundtrip(self):
        ev, intel, feat, facts = self._build_full_stack()
        rm = build_read_model(self.now, "test_001", 1, 1, ev, intel, feat, facts)
        sid = save_analysis_snapshot(
            analysis_timestamp=self.now,
            source_run_id="rm_persist_001",
            market_snapshot_id=1,
            market_state_id=self.market_state_id,
            xau_usd=2400.50,
            usd_irr=50000.0,
            rep_gold_price=190000000.0,
            premium_percent=-1.2,
            valuation_state="CHEAP",
            momentum_state="IMPROVING",
            structure_state="DISCOUNT_DOMINANT",
            analysis_read_model_json=rm,
        )
        snap = self.session.query(AnalysisSnapshot).filter_by(id=sid).first()
        self.assertIsNotNone(snap.analysis_read_model_json)
        self.assertEqual(snap.analysis_read_model_json["schema_version"], READ_MODEL_SCHEMA_VERSION)

    # --- KPI-19: no look-ahead ---
    def test_19_no_lookahead(self):
        ev, intel, feat, facts = self._build_full_stack()
        rm = build_read_model(self.now, "test_001", 1, 1, ev, intel, feat, facts)
        gen = datetime.fromisoformat(rm["provenance"]["generated_at"])
        self.assertLessEqual(gen, self.now + timedelta(seconds=5))

    # --- KPI-20: no regression ---
    def test_20_no_regression(self):
        from database.models import AnalysisSnapshot
        self.assertTrue(hasattr(AnalysisSnapshot, 'evidence_package_json'))
        self.assertTrue(hasattr(AnalysisSnapshot, 'intelligence_result_json'))
        self.assertTrue(hasattr(AnalysisSnapshot, 'features_json'))

    # --- KPI-21: empty inputs safe ---
    def test_21_empty_inputs(self):
        facts = {
            "xau_usd": None, "usd_irr": None, "rep_gold_price": None,
            "premium_percent": None, "valuation_state": "UNKNOWN",
            "momentum_state": "UNKNOWN", "structure_state": "UNKNOWN",
            "regime_state": "UNKNOWN", "candidate_decision": "UNKNOWN",
            "final_decision": "UNKNOWN",
        }
        rm = build_read_model(self.now, "test_001", None, None, None, None, None, facts)
        self.assertEqual(rm["facts"]["valuation_state"], "UNKNOWN")
        self.assertEqual(rm["evidence_summary"]["valuation_status"], "UNKNOWN")

    # --- KPI-22: uncertainty aggregation ---
    def test_22_uncertainty_aggregation(self):
        ev, intel, feat, facts = self._build_full_stack()
        rm = build_read_model(self.now, "test_001", 1, 1, ev, intel, feat, facts)
        self.assertIn("uncertainty", rm)
        self.assertIsInstance(rm["uncertainty"]["conflicts"], list)

    # --- KPI-23: outcome history present ---
    def test_23_outcome_history(self):
        ev, intel, feat, facts = self._build_full_stack()
        rm = build_read_model(self.now, "test_001", 1, 1, ev, intel, feat, facts)
        self.assertIn("outcome_history", rm)
        self.assertIn("status", rm["outcome_history"])


def run_kpi():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(KPIPreSPC9)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    passed = result.testsRun - len(result.failures) - len(result.errors)
    total = result.testsRun

    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print(f"Result: {passed}/{total} passed, 0 failed")
        print("\n🟢 PRE-SP-C.9 COMPLETE")
        return 0
    else:
        failed = len(result.failures) + len(result.errors)
        print(f"Result: {passed}/{total} passed, {failed} failed")
        print("\n🔴 PRE-SP-C.9 FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_kpi())
