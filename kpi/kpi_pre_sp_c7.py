#!/usr/bin/env python3
"""PRE-SP-C.7 KPI — Bounded Market Intelligence.

Run from repository root:
    python kpi/kpi_pre_sp_c7.py
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
from intelligence.market_intelligence import (
    build_intelligence_result,
    validate_intelligence_result,
    _detect_conflicts,
    _build_fallback_intelligence,
    INTELLIGENCE_SCHEMA_VERSION,
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


class KPIPreSPC7(unittest.TestCase):
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
        self.snapshot_time = now

    def _make_evidence(self, **overrides):
        base = {
            "schema_version": "1",
            "generated_at": self.snapshot_time.isoformat(),
            "provenance": {
                "source_run_id": "test_001",
                "analysis_timestamp": self.snapshot_time.isoformat(),
                "market_snapshot_id": 1,
                "market_state_id": 1,
            },
            "valuation": {
                "premium_percent": -1.2,
                "valuation_state": "CHEAP",
                "fair_price": 1900000.0,
                "status": "AVAILABLE",
            },
            "momentum": {
                "momentum_state": "IMPROVING",
                "premium_direction": "DISCOUNT WIDENING",
                "status": "AVAILABLE",
            },
            "technical_structure": {
                "representative_price": {"price": 190000000.0, "source": "milli"},
                "support_levels": [{"price": 189000000.0, "touches": 3}],
                "resistance_levels": [{"price": 191000000.0, "touches": 2}],
                "status": "AVAILABLE",
            },
            "regime": {
                "regime_state": "NORMAL",
                "previous_regime": "NORMAL",
                "candidate_state": None,
                "confirmation_count": 0,
                "status": "AVAILABLE",
            },
            "xau_usd": {
                "price": 2400.50,
                "timestamp": self.snapshot_time.isoformat(),
                "freshness": "AVAILABLE",
                "status": "AVAILABLE",
            },
            "usd_irr": {
                "price": 50000.0,
                "timestamp": self.snapshot_time.isoformat(),
                "freshness": "AVAILABLE",
                "status": "AVAILABLE",
            },
            "representative_gold": {
                "price": 190000000.0,
                "source": "milli",
                "fallback_status": "PRIMARY",
                "status": "AVAILABLE",
            },
            "platform_structure": {
                "platform_high": 1905000.0,
                "platform_low": 1895000.0,
                "platform_spread": 10000.0,
                "platforms_below_fair": 3,
                "platforms_above_fair": 0,
                "status": "AVAILABLE",
            },
            "news_context": {
                "recent_event_count": 1,
                "high_impact_count": 0,
                "latest_events": [],
                "status": "AVAILABLE",
            },
            "historical_context": {
                "similar_state_count": 0,
                "recent_similar_states": [],
                "status": "INSUFFICIENT_DATA",
            },
            "outcome_context": {
                "recent_evaluated_snapshots": 0,
                "latest_outcomes": [],
                "status": "INSUFFICIENT_DATA",
            },
            "data_quality": {
                "overall": "AVAILABLE",
                "components": {},
                "missing": [],
                "stale": [],
                "warnings": [],
            },
        }
        base.update(overrides)
        return base

    # --- KPI-1: evidence package accepted ---
    def test_01_evidence_accepted(self):
        ev = self._make_evidence()
        result = build_intelligence_result(ev)
        self.assertIsInstance(result, dict)

    # --- KPI-2: structured intelligence returned ---
    def test_02_structured_result(self):
        ev = self._make_evidence()
        result = build_intelligence_result(ev)
        self.assertIn("market_context", result)
        self.assertIn("valuation_interpretation", result)

    # --- KPI-3: schema version present ---
    def test_03_schema_version(self):
        ev = self._make_evidence()
        result = build_intelligence_result(ev)
        self.assertEqual(result["schema_version"], INTELLIGENCE_SCHEMA_VERSION)
        self.assertEqual(result["intelligence_schema_version"], INTELLIGENCE_SCHEMA_VERSION)

    # --- KPI-4: source provenance preserved ---
    def test_04_provenance(self):
        ev = self._make_evidence()
        result = build_intelligence_result(ev)
        self.assertEqual(result["provenance"]["evidence_schema_version"], "1")
        self.assertEqual(result["provenance"]["source_run_id"], "test_001")

    # --- KPI-5: facts preserved ---
    def test_05_facts_preserved(self):
        ev = self._make_evidence()
        result = build_intelligence_result(ev)
        self.assertIn("CHEAP", result["valuation_interpretation"]["fact"])
        self.assertIn("IMPROVING", result["momentum_interpretation"]["fact"])

    # --- KPI-6: interpretation separated ---
    def test_06_interpretation_separated(self):
        ev = self._make_evidence()
        result = build_intelligence_result(ev)
        self.assertNotEqual(
            result["valuation_interpretation"]["fact"],
            result["valuation_interpretation"]["interpretation"]
        )

    # --- KPI-7: uncertainty explicit ---
    def test_07_uncertainty_explicit(self):
        ev = self._make_evidence()
        result = build_intelligence_result(ev)
        self.assertTrue(len(result["uncertainties"]) > 0 or
                        result["valuation_interpretation"]["uncertainty"] != "INSUFFICIENT_DATA")

    # --- KPI-8: valuation interpreted ---
    def test_08_valuation_interpreted(self):
        ev = self._make_evidence()
        result = build_intelligence_result(ev)
        self.assertIn("interpretation", result["valuation_interpretation"])
        self.assertNotEqual(result["valuation_interpretation"]["interpretation"], "INSUFFICIENT_DATA")

    # --- KPI-9: momentum interpreted ---
    def test_09_momentum_interpreted(self):
        ev = self._make_evidence()
        result = build_intelligence_result(ev)
        self.assertIn("interpretation", result["momentum_interpretation"])

    # --- KPI-10: technical interpretation present ---
    def test_10_technical_present(self):
        ev = self._make_evidence()
        result = build_intelligence_result(ev)
        self.assertIn("interpretation", result["technical_interpretation"])

    # --- KPI-11: regime interpretation present ---
    def test_11_regime_present(self):
        ev = self._make_evidence()
        result = build_intelligence_result(ev)
        self.assertIn("interpretation", result["regime_interpretation"])

    # --- KPI-12: news interpretation present ---
    def test_12_news_present(self):
        ev = self._make_evidence()
        result = build_intelligence_result(ev)
        self.assertIn("interpretation", result["news_interpretation"])

    # --- KPI-13: historical context present ---
    def test_13_historical_present(self):
        ev = self._make_evidence()
        result = build_intelligence_result(ev)
        self.assertIn("interpretation", result["historical_context"])

    # --- KPI-14: outcome context present ---
    def test_14_outcome_present(self):
        ev = self._make_evidence()
        result = build_intelligence_result(ev)
        self.assertIn("interpretation", result["outcome_context"])

    # --- KPI-15: conflicts preserved ---
    def test_15_conflicts_preserved(self):
        ev = self._make_evidence(valuation={"valuation_state": "CHEAP", "premium_percent": -1.2, "status": "AVAILABLE"},
                                  momentum={"momentum_state": "IMPROVING", "premium_direction": "DISCOUNT WIDENING", "status": "AVAILABLE"})
        result = build_intelligence_result(ev)
        self.assertTrue(len(result["conflicting_evidence"]) > 0)

    # --- KPI-16: missing evidence explicit ---
    def test_16_missing_explicit(self):
        ev = self._make_evidence(historical_context={"status": "INSUFFICIENT_DATA", "similar_state_count": None, "recent_similar_states": []})
        result = build_intelligence_result(ev)
        self.assertTrue(any("Historical" in m for m in result["missing_evidence"]))

    # --- KPI-17: deterministic facts unchanged ---
    def test_17_facts_unchanged(self):
        ev = self._make_evidence()
        r1 = build_intelligence_result(ev)
        r2 = build_intelligence_result(ev)
        self.assertEqual(r1["valuation_interpretation"]["fact"], r2["valuation_interpretation"]["fact"])

    # --- KPI-18: no BUY/SELL authority ---
    def test_18_no_decision(self):
        ev = self._make_evidence()
        result = build_intelligence_result(ev)
        valid, errors = validate_intelligence_result(result)
        self.assertTrue(valid, f"Errors: {errors}")

    # --- KPI-19: model/prompt provenance ---
    def test_19_model_provenance(self):
        ev = self._make_evidence()
        result = build_intelligence_result(ev, model_provider="test_provider", prompt_version="v2")
        self.assertEqual(result["model_provider"], "test_provider")
        self.assertEqual(result["prompt_version"], "v2")

    # --- KPI-20: deterministic fallback when LLM unavailable ---
    def test_20_fallback(self):
        result = _build_fallback_intelligence()
        self.assertEqual(result["market_context"]["summary"], "Insufficient evidence for market context.")
        valid, _ = validate_intelligence_result(result)
        self.assertTrue(valid)

    # --- KPI-21: persistence roundtrip ---
    def test_21_persistence_roundtrip(self):
        ev = self._make_evidence()
        intel = build_intelligence_result(ev)
        snap = self.session.query(AnalysisSnapshot).first()
        if snap is None:
            sid = save_analysis_snapshot(
                analysis_timestamp=self.snapshot_time,
                source_run_id="persist_test_001",
                market_snapshot_id=1,
                market_state_id=self.market_state_id,
                xau_usd=2400.50,
                usd_irr=50000.0,
                rep_gold_price=190000000.0,
                premium_percent=-1.2,
                valuation_state="CHEAP",
                momentum_state="IMPROVING",
                structure_state="DISCOUNT_DOMINANT",
                intelligence_result_json=intel,
            )
            snap = self.session.query(AnalysisSnapshot).filter_by(id=sid).first()
        else:
            snap.intelligence_result_json = intel
            self.session.commit()
            self.session.refresh(snap)
        self.assertIsNotNone(snap.intelligence_result_json)
        self.assertEqual(snap.intelligence_result_json["schema_version"], INTELLIGENCE_SCHEMA_VERSION)

    # --- KPI-22: repeated execution stable ---
    def test_22_stable_repeat(self):
        ev = self._make_evidence()
        r1 = build_intelligence_result(ev)
        r2 = build_intelligence_result(ev)
        self.assertEqual(r1["market_context"]["summary"], r2["market_context"]["summary"])
        self.assertEqual(r1["aligned_evidence"], r2["aligned_evidence"])

    # --- KPI-23: validation catches missing fields ---
    def test_23_validation_catches_missing(self):
        result = {"schema_version": "1"}
        valid, errors = validate_intelligence_result(result)
        self.assertFalse(valid)
        self.assertTrue(len(errors) > 0)

    # --- KPI-24: empty evidence safe ---
    def test_24_empty_evidence_safe(self):
        result = build_intelligence_result({})
        self.assertEqual(result["market_context"]["summary"], "Insufficient evidence for market context.")
        valid, _ = validate_intelligence_result(result)
        self.assertTrue(valid)

    # --- KPI-25: aligned evidence detected ---
    def test_25_aligned_evidence(self):
        ev = self._make_evidence(valuation={"valuation_state": "CHEAP", "premium_percent": -1.2, "status": "AVAILABLE"},
                                  momentum={"momentum_state": "IMPROVING", "premium_direction": "DISCOUNT NARROWING", "status": "AVAILABLE"})
        result = build_intelligence_result(ev)
        self.assertTrue(len(result["aligned_evidence"]) > 0)


def run_kpi():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(KPIPreSPC7)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    passed = result.testsRun - len(result.failures) - len(result.errors)
    total = result.testsRun

    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print(f"Result: {passed}/{total} passed, 0 failed")
        print("\n🟢 PRE-SP-C.7 COMPLETE")
        return 0
    else:
        failed = len(result.failures) + len(result.errors)
        print(f"Result: {passed}/{total} passed, {failed} failed")
        print("\n🔴 PRE-SP-C.7 FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_kpi())
