#!/usr/bin/env python3
"""PRE-SP-C.11 KPI — Analytical Consumer Interface / Read-Model API.

Run from repository root:
    python kpi/kpi_pre_sp_c11.py
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
)
from intelligence.consumer import (
    get_analysis,
    get_latest_analysis,
    get_analysis_summary,
    validate_consumer_envelope,
    CONSUMER_SCHEMA_VERSION,
)
from intelligence.read_model_integration import (
    COMPLETENESS_COMPLETE,
    COMPLETENESS_DEGRADED,
    COMPLETENESS_INSUFFICIENT_DATA,
    COMPLETENESS_INVALID,
)


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


class KPIPreSPC11(unittest.TestCase):
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
        self.now = now

        self.snapshot_id = save_analysis_snapshot(
            analysis_timestamp=now,
            source_run_id="c11_test_001",
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
            analysis_read_model_json={
                "schema_version": "1",
                "provenance": {"source_run_id": "c11_test_001", "analysis_timestamp": now.isoformat()},
                "facts": {
                    "xau_usd": 2400.50, "usd_irr": 50000.0, "rep_gold_price": 190000000.0,
                    "premium_percent": -1.2, "valuation_state": "CHEAP",
                    "momentum_state": "IMPROVING", "structure_state": "DISCOUNT_DOMINANT",
                    "regime_state": "NORMAL",
                },
                "evidence_summary": {
                    "valuation_status": "AVAILABLE", "momentum_status": "AVAILABLE",
                    "technical_status": "AVAILABLE", "regime_status": "AVAILABLE",
                    "xau_usd_status": "AVAILABLE", "usd_irr_status": "AVAILABLE",
                    "representative_gold_status": "AVAILABLE", "platform_structure_status": "AVAILABLE",
                    "news_status": "AVAILABLE", "historical_status": "INSUFFICIENT_DATA",
                    "outcome_status": "INSUFFICIENT_DATA", "data_quality_overall": "AVAILABLE",
                },
                "interpretation_summary": {
                    "market_context_summary": "Test summary", "key_drivers": [], "risks": [], "conflicts": [],
                    "valuation_fact": "CHEAP", "valuation_interpretation": "Below fair",
                },
                "features_summary": {
                    "price_trend_status": "AVAILABLE", "momentum_features_status": "AVAILABLE",
                    "volatility_status": "AVAILABLE", "regime_features_status": "AVAILABLE",
                    "market_relation_status": "AVAILABLE", "structure_features_status": "AVAILABLE",
                    "sufficient_history": True,
                },
                "uncertainty": {"conflicts": [], "missing_evidence": [], "missing_features": [], "data_gaps": [], "uncertainties": []},
                "outcome_history": {"status": "INSUFFICIENT_DATA", "recent_evaluated_snapshots": 0, "latest_outcomes": []},
                "decision": {"candidate_decision": "BUY", "final_decision": "WAIT", "source": "existing_decision_engine", "note": "Read-only"},
                "retrieval_metadata": {
                    "completeness_status": COMPLETENESS_COMPLETE,
                    "completeness_reasons": [],
                    "evidence_persisted": True,
                    "interpretation_persisted": True,
                    "features_persisted": True,
                    "read_model_persisted": True,
                },
            },
        )

    # --- KPI-1: consumer retrieves existing snapshot ---
    def test_01_retrieve(self):
        env = get_analysis(self.snapshot_id)
        self.assertEqual(env["status"], "OK")
        self.assertEqual(env["snapshot_id"], self.snapshot_id)

    # --- KPI-2: consumer returns C.10 structure ---
    def test_02_c10_structure(self):
        env = get_analysis(self.snapshot_id)
        self.assertIn("data", env)
        self.assertIn("facts", env["data"])
        self.assertIn("evidence_summary", env["data"])

    # --- KPI-3: completeness preserved ---
    def test_03_completeness(self):
        env = get_analysis(self.snapshot_id)
        self.assertIn("completeness", env)

    # --- KPI-4: COMPLETE preserved ---
    def test_04_complete(self):
        env = get_analysis(self.snapshot_id)
        self.assertEqual(env["completeness"], COMPLETENESS_COMPLETE)

    # --- KPI-5: DEGRADED preserved ---
    def test_05_degraded(self):
        snap = self.session.query(AnalysisSnapshot).filter_by(id=self.snapshot_id).first()
        rm = dict(snap.analysis_read_model_json)
        rm["retrieval_metadata"]["completeness_status"] = COMPLETENESS_DEGRADED
        rm["retrieval_metadata"]["completeness_reasons"] = ["Test degraded"]
        snap.analysis_read_model_json = rm
        self.session.commit()
        env = get_analysis(self.snapshot_id)
        self.assertEqual(env["completeness"], COMPLETENESS_DEGRADED)

    # --- KPI-6: INSUFFICIENT_DATA preserved ---
    def test_06_insufficient(self):
        snap = self.session.query(AnalysisSnapshot).filter_by(id=self.snapshot_id).first()
        rm = dict(snap.analysis_read_model_json)
        rm["retrieval_metadata"]["completeness_status"] = COMPLETENESS_INSUFFICIENT_DATA
        rm["retrieval_metadata"]["completeness_reasons"] = ["Test insufficient"]
        snap.analysis_read_model_json = rm
        self.session.commit()
        env = get_analysis(self.snapshot_id)
        self.assertEqual(env["completeness"], COMPLETENESS_INSUFFICIENT_DATA)

    # --- KPI-7: INVALID preserved ---
    def test_07_invalid(self):
        snap = self.session.query(AnalysisSnapshot).filter_by(id=self.snapshot_id).first()
        rm = dict(snap.analysis_read_model_json)
        rm["retrieval_metadata"]["completeness_status"] = COMPLETENESS_INVALID
        rm["retrieval_metadata"]["completeness_reasons"] = ["Test invalid"]
        snap.analysis_read_model_json = rm
        self.session.commit()
        env = get_analysis(self.snapshot_id)
        self.assertEqual(env["completeness"], COMPLETENESS_INVALID)

    # --- KPI-8: historical snapshot retrieval ---
    def test_08_historical(self):
        env = get_analysis(self.snapshot_id)
        self.assertEqual(env["data"]["provenance"]["source_run_id"], "c11_test_001")

    # --- KPI-9: no current-data leakage ---
    def test_09_no_current_leakage(self):
        env = get_analysis(self.snapshot_id)
        facts = env["data"]["facts"]
        self.assertEqual(facts["xau_usd"], 2400.50)

    # --- KPI-10: no future-data leakage ---
    def test_10_no_future_leakage(self):
        env = get_analysis(self.snapshot_id)
        self.assertNotIn("future", str(env).lower())

    # --- KPI-11: evidence preservation ---
    def test_11_evidence(self):
        env = get_analysis(self.snapshot_id)
        self.assertEqual(env["data"]["evidence_summary"]["valuation_status"], "AVAILABLE")

    # --- KPI-12: interpretation preservation ---
    def test_12_interpretation(self):
        env = get_analysis(self.snapshot_id)
        self.assertEqual(env["data"]["interpretation_summary"]["market_context_summary"], "Test summary")

    # --- KPI-13: feature preservation ---
    def test_13_features(self):
        env = get_analysis(self.snapshot_id)
        self.assertEqual(env["data"]["features_summary"]["sufficient_history"], True)

    # --- KPI-14: outcome preservation ---
    def test_14_outcome(self):
        env = get_analysis(self.snapshot_id)
        self.assertEqual(env["data"]["outcome_history"]["status"], "INSUFFICIENT_DATA")

    # --- KPI-15: decision preservation ---
    def test_15_decision(self):
        env = get_analysis(self.snapshot_id)
        self.assertEqual(env["data"]["decision"]["final_decision"], "WAIT")

    # --- KPI-16: no decision generation ---
    def test_16_no_generation(self):
        env = get_analysis(self.snapshot_id)
        self.assertEqual(env["data"]["decision"]["source"], "existing_decision_engine")

    # --- KPI-17: deterministic output ---
    def test_17_deterministic(self):
        e1 = get_analysis(self.snapshot_id)
        e2 = get_analysis(self.snapshot_id)
        self.assertEqual(e1["completeness"], e2["completeness"])

    # --- KPI-18: C.9 compatibility ---
    def test_18_c9_compat(self):
        env = get_analysis(self.snapshot_id)
        self.assertIn("provenance", env["data"])

    # --- KPI-19: C.10 compatibility ---
    def test_19_c10_compat(self):
        env = get_analysis(self.snapshot_id)
        self.assertIn("retrieval_metadata", env["data"])

    # --- KPI-20: consumer contract stability ---
    def test_20_contract_stable(self):
        env = get_analysis(self.snapshot_id)
        self.assertEqual(env["consumer_contract"], "analysis_state")
        self.assertEqual(env["schema_version"], CONSUMER_SCHEMA_VERSION)

    # --- KPI-21: no UI formatting contamination ---
    def test_21_no_ui(self):
        env = get_analysis(self.snapshot_id)
        valid, errors = validate_consumer_envelope(env)
        self.assertTrue(valid, f"Errors: {errors}")

    # --- KPI-22: database round-trip ---
    def test_22_roundtrip(self):
        env = get_analysis(self.snapshot_id)
        self.assertEqual(env["snapshot_id"], self.snapshot_id)

    # --- KPI-23: regression ---
    def test_23_regression(self):
        from database.models import AnalysisSnapshot
        self.assertTrue(hasattr(AnalysisSnapshot, 'analysis_read_model_json'))

    # --- KPI-24: NOT_FOUND for missing snapshot ---
    def test_24_not_found(self):
        env = get_analysis(99999)
        self.assertEqual(env["status"], "NOT_FOUND")

    # --- KPI-25: summary contract ---
    def test_25_summary(self):
        summary = get_analysis_summary(self.snapshot_id)
        self.assertEqual(summary["consumer_contract"], "analysis_summary")
        self.assertEqual(summary["summary"]["final_decision"], "WAIT")


def run_kpi():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(KPIPreSPC11)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    passed = result.testsRun - len(result.failures) - len(result.errors)
    total = result.testsRun

    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print(f"Result: {passed}/{total} passed, 0 failed")
        print("\n🟢 PRE-SP-C.11 COMPLETE")
        return 0
    else:
        failed = len(result.failures) + len(result.errors)
        print(f"Result: {passed}/{total} passed, {failed} failed")
        print("\n🔴 PRE-SP-C.11 FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_kpi())
