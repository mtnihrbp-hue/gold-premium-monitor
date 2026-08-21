#!/usr/bin/env python3
"""PRE-SP-C.10 KPI — Analytical Read Model Integration & Audit Layer.

Run from repository root:
    python kpi/kpi_pre_sp_c10.py
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
    save_outcome_evaluation,
)
from intelligence.read_model_integration import (
    get_analysis_read_model,
    reconstruct_historical_state,
    classify_completeness,
    validate_retrieved_state,
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


class KPIPreSPC10(unittest.TestCase):
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

        # Snapshot with full C.6-C.9 layers
        self.snapshot_id = save_analysis_snapshot(
            analysis_timestamp=now,
            source_run_id="c10_test_001",
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
            evidence_package_json={
                "schema_version": "1",
                "valuation": {"status": "AVAILABLE", "valuation_state": "CHEAP", "premium_percent": -1.2},
                "momentum": {"status": "AVAILABLE", "momentum_state": "IMPROVING"},
                "technical_structure": {"status": "AVAILABLE"},
                "regime": {"status": "AVAILABLE", "regime_state": "NORMAL"},
                "xau_usd": {"status": "AVAILABLE", "price": 2400.50},
                "usd_irr": {"status": "AVAILABLE", "price": 50000.0},
                "representative_gold": {"status": "AVAILABLE", "price": 190000000.0, "source": "milli"},
                "platform_structure": {"status": "AVAILABLE"},
                "news_context": {"status": "AVAILABLE", "recent_event_count": 0},
                "historical_context": {"status": "INSUFFICIENT_DATA"},
                "outcome_context": {"status": "INSUFFICIENT_DATA"},
                "data_quality": {"overall": "AVAILABLE", "missing": [], "stale": []},
                "provenance": {"source_run_id": "c10_test_001", "analysis_timestamp": now.isoformat()},
            },
            intelligence_result_json={
                "schema_version": "1",
                "intelligence_schema_version": "1",
                "generated_at": now.isoformat(),
                "model_provider": "test",
                "market_context": {"summary": "Test summary", "key_drivers": [], "risks": [], "conflicts": []},
                "valuation_interpretation": {"fact": "CHEAP", "interpretation": "Below fair", "uncertainty": "None"},
                "momentum_interpretation": {"fact": "IMPROVING", "interpretation": "Getting better", "uncertainty": "None"},
                "technical_interpretation": {"fact": "OK", "interpretation": "Stable", "uncertainty": "None"},
                "regime_interpretation": {"fact": "NORMAL", "interpretation": "Normal regime", "uncertainty": "None"},
                "news_interpretation": {"fact": "None", "interpretation": "No news", "uncertainty": "None"},
                "historical_context": {"fact": "None", "interpretation": "No history", "uncertainty": "None"},
                "outcome_context": {"fact": "None", "interpretation": "No outcomes", "uncertainty": "None"},
                "aligned_evidence": [],
                "conflicting_evidence": [],
                "missing_evidence": [],
                "uncertainties": [],
                "provenance": {"evidence_schema_version": "1", "source_run_id": "c10_test_001"},
            },
            features_json={
                "schema_version": "1",
                "price_trend": {"rep_gold_ma7": 190000000.0},
                "momentum": {"premium_velocity": 0.05},
                "volatility": {"rep_gold_volatility_7": 0.5},
                "regime": {"current_regime": "NORMAL"},
                "market_relation": {"xau_usd_direction": "UP"},
                "structure": {"platform_spread": 10000.0},
                "data_quality": {"sufficient_history": True},
            },
            analysis_read_model_json={
                "schema_version": "1",
                "provenance": {"source_run_id": "c10_test_001", "analysis_timestamp": now.isoformat()},
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
            },
        )

        # Outcome evaluation for this snapshot
        save_outcome_evaluation(
            analysis_snapshot_id=self.snapshot_id,
            horizon_hours=1,
            reference_time=now,
            target_time=now + timedelta(hours=1),
            outcome_status="COMPLETE",
            actual_xau_usd=2410.0,
            xau_usd_direction="UP",
        )

    # --- KPI-1: retrieve existing snapshot ---
    def test_01_retrieve_snapshot(self):
        rm = get_analysis_read_model(self.snapshot_id)
        self.assertIsNotNone(rm)
        self.assertEqual(rm["schema_version"], "1")

    # --- KPI-2: read-model structure valid ---
    def test_02_structure_valid(self):
        rm = get_analysis_read_model(self.snapshot_id)
        self.assertIn("facts", rm)
        self.assertIn("evidence_summary", rm)
        self.assertIn("interpretation_summary", rm)
        self.assertIn("features_summary", rm)
        self.assertIn("uncertainty", rm)
        self.assertIn("outcome_history", rm)
        self.assertIn("decision", rm)
        self.assertIn("provenance", rm)

    # --- KPI-3: completeness classification ---
    def test_03_completeness(self):
        rm = get_analysis_read_model(self.snapshot_id)
        self.assertIn("retrieval_metadata", rm)
        self.assertIn("completeness_status", rm["retrieval_metadata"])

    # --- KPI-4: complete snapshot ---
    def test_04_complete(self):
        rm = get_analysis_read_model(self.snapshot_id)
        self.assertEqual(rm["retrieval_metadata"]["completeness_status"], COMPLETENESS_COMPLETE)

    # --- KPI-5: degraded snapshot ---
    def test_05_degraded(self):
        # Modify evidence to create degraded state
        snap = self.session.query(AnalysisSnapshot).filter_by(id=self.snapshot_id).first()
        rm_data = dict(snap.analysis_read_model_json)
        rm_data["evidence_summary"]["historical_status"] = "INSUFFICIENT_DATA"
        rm_data["evidence_summary"]["outcome_status"] = "INSUFFICIENT_DATA"
        snap.analysis_read_model_json = rm_data
        self.session.commit()
        rm = get_analysis_read_model(self.snapshot_id)
        self.assertEqual(rm["retrieval_metadata"]["completeness_status"], COMPLETENESS_DEGRADED)

    # --- KPI-6: insufficient-data snapshot ---
    def test_06_insufficient_data(self):
        snap = self.session.query(AnalysisSnapshot).filter_by(id=self.snapshot_id).first()
        rm_data = dict(snap.analysis_read_model_json)
        rm_data["interpretation_summary"]["market_context_summary"] = "UNKNOWN"
        rm_data["decision"]["final_decision"] = "UNKNOWN"
        rm_data["facts"]["valuation_state"] = "UNKNOWN"
        rm_data["facts"]["momentum_state"] = "UNKNOWN"
        rm_data["facts"]["structure_state"] = "UNKNOWN"
        snap.analysis_read_model_json = rm_data
        self.session.commit()
        rm = get_analysis_read_model(self.snapshot_id)
        self.assertEqual(rm["retrieval_metadata"]["completeness_status"], COMPLETENESS_INSUFFICIENT_DATA)

    # --- KPI-7: invalid snapshot ---
    def test_07_invalid(self):
        snap = self.session.query(AnalysisSnapshot).filter_by(id=self.snapshot_id).first()
        snap.analysis_read_model_json = {"invalid": True}
        self.session.commit()
        rm = get_analysis_read_model(self.snapshot_id)
        self.assertEqual(rm["retrieval_metadata"]["completeness_status"], COMPLETENESS_INVALID)

    # --- KPI-8: historical reconstruction ---
    def test_08_historical_reconstruction(self):
        hist = reconstruct_historical_state(self.snapshot_id)
        self.assertIsNotNone(hist)
        self.assertEqual(hist["snapshot_id"], self.snapshot_id)
        self.assertIn("historical_state", hist)
        self.assertIn("outcome_evaluations", hist)

    # --- KPI-9: no current-data leakage ---
    def test_09_no_leakage(self):
        hist = reconstruct_historical_state(self.snapshot_id)
        self.assertTrue(hist["audit_invariants"]["no_current_data_queried"])
        self.assertTrue(hist["audit_invariants"]["no_future_observations"])

    # --- KPI-10: provenance preservation ---
    def test_10_provenance(self):
        rm = get_analysis_read_model(self.snapshot_id)
        self.assertEqual(rm["provenance"]["source_run_id"], "c10_test_001")

    # --- KPI-11: evidence preservation ---
    def test_11_evidence_preserved(self):
        rm = get_analysis_read_model(self.snapshot_id)
        self.assertEqual(rm["evidence_summary"]["valuation_status"], "AVAILABLE")

    # --- KPI-12: interpretation preservation ---
    def test_12_interpretation_preserved(self):
        rm = get_analysis_read_model(self.snapshot_id)
        self.assertEqual(rm["interpretation_summary"]["market_context_summary"], "Test summary")

    # --- KPI-13: feature preservation ---
    def test_13_features_preserved(self):
        rm = get_analysis_read_model(self.snapshot_id)
        self.assertEqual(rm["features_summary"]["sufficient_history"], True)

    # --- KPI-14: outcome preservation ---
    def test_14_outcome_preserved(self):
        hist = reconstruct_historical_state(self.snapshot_id)
        self.assertEqual(len(hist["outcome_evaluations"]), 1)
        self.assertEqual(hist["outcome_evaluations"][0]["horizon_hours"], 1)

    # --- KPI-15: decision preservation ---
    def test_15_decision_preserved(self):
        rm = get_analysis_read_model(self.snapshot_id)
        self.assertEqual(rm["decision"]["final_decision"], "WAIT")
        self.assertEqual(rm["decision"]["candidate_decision"], "BUY")

    # --- KPI-16: no decision generation ---
    def test_16_no_decision_generation(self):
        rm = get_analysis_read_model(self.snapshot_id)
        self.assertEqual(rm["decision"]["source"], "existing_decision_engine")

    # --- KPI-17: deterministic retrieval ---
    def test_17_deterministic(self):
        r1 = get_analysis_read_model(self.snapshot_id)
        r2 = get_analysis_read_model(self.snapshot_id)
        self.assertEqual(r1["facts"]["valuation_state"], r2["facts"]["valuation_state"])

    # --- KPI-18: database round-trip ---
    def test_18_roundtrip(self):
        rm = get_analysis_read_model(self.snapshot_id)
        self.assertIsNotNone(rm["retrieval_metadata"]["snapshot_id"])

    # --- KPI-19: C.7 compatibility ---
    def test_19_c7_compatible(self):
        rm = get_analysis_read_model(self.snapshot_id)
        self.assertTrue(rm["retrieval_metadata"]["interpretation_persisted"])

    # --- KPI-20: C.8 compatibility ---
    def test_20_c8_compatible(self):
        rm = get_analysis_read_model(self.snapshot_id)
        self.assertTrue(rm["retrieval_metadata"]["features_persisted"])

    # --- KPI-21: C.9 compatibility ---
    def test_21_c9_compatible(self):
        rm = get_analysis_read_model(self.snapshot_id)
        self.assertTrue(rm["retrieval_metadata"]["read_model_persisted"])

    # --- KPI-22: regression ---
    def test_22_regression(self):
        from database.models import AnalysisSnapshot
        self.assertTrue(hasattr(AnalysisSnapshot, 'evidence_package_json'))
        self.assertTrue(hasattr(AnalysisSnapshot, 'intelligence_result_json'))
        self.assertTrue(hasattr(AnalysisSnapshot, 'features_json'))
        self.assertTrue(hasattr(AnalysisSnapshot, 'analysis_read_model_json'))


def run_kpi():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(KPIPreSPC10)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    passed = result.testsRun - len(result.failures) - len(result.errors)
    total = result.testsRun

    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print(f"Result: {passed}/{total} passed, 0 failed")
        print("\n🟢 PRE-SP-C.10 COMPLETE")
        return 0
    else:
        failed = len(result.failures) + len(result.errors)
        print(f"Result: {passed}/{total} passed, {failed} failed")
        print("\n🔴 PRE-SP-C.10 FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_kpi())
