#!/usr/bin/env python3
"""PRE-SP-C.6 KPI — Evidence Package + Market Intelligence Foundation.

Run from repository root:
    python kpi/kpi_pre_sp_c6.py
"""

import sys
sys.path.insert(0, "src")

import os
import unittest
from datetime import datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from database.connection import init_db, Base, get_session
from database.models import AnalysisSnapshot, MarketState, NewsEvent
from database.repository import (
    save_market_snapshot,
    save_market_state,
    save_analysis_snapshot,
    save_price_observation,
    save_news_event,
    save_outcome_evaluation,
)
from analysis.evidence_package import (
    build_evidence_package,
    validate_evidence_package,
    EVIDENCE_SCHEMA_VERSION,
)
from analysis.regime import RegimeClassifier, RegimeResult


class MockRepPrice:
    def __init__(self, price=None, source="UNKNOWN", status="INSUFFICIENT_DATA"):
        self.price = price
        self.source = source
        self.status = status


class MockStructureState:
    def __init__(self, status="INSUFFICIENT_DATA"):
        self.status = status
        self.support_levels = []
        self.resistance_levels = []


class KPIPreSPC6(unittest.TestCase):
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

        # Market snapshot
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

        # Market state
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
        self.market_state_id = ms.id
        self.market_snapshot = self.session.query(
            __import__('database.models', fromlist=['MarketSnapshot']).MarketSnapshot
        ).filter_by(id=sid).first()
        self.market_state = ms

        # Analysis snapshot
        self.snapshot_time = now
        self.snapshot_id = save_analysis_snapshot(
            analysis_timestamp=now,
            source_run_id="test_evidence_001",
            market_snapshot_id=sid,
            market_state_id=ms.id,
            xau_usd=2400.50,
            usd_irr=50000.0,
            rep_gold_price=190000000.0,
            premium_percent=-1.2,
            valuation_state="CHEAP",
            momentum_state="IMPROVING",
            structure_state="DISCOUNT_DOMINANT",
            regime_state="NORMAL",
            technical_state_json={
                "representative_price": {"price": 190000000.0, "source": "milli"},
                "support_levels": [{"price": 189000000.0, "touches": 3}],
                "resistance_levels": [{"price": 191000000.0, "touches": 2}],
                "structure_status": "AVAILABLE",
            },
            previous_regime="NORMAL",
            regime_candidate_state=None,
            regime_confirmation_count=0,
        )

        # Seed news
        save_news_event({
            "published_at": now - timedelta(hours=2),
            "source": "test",
            "title": "Gold prices stable",
            "event_type": "MARKET",
            "relevance": "MEDIUM",
            "classification_method": "KEYWORD",
        })

        # Seed outcome for previous snapshot context
        save_outcome_evaluation(
            analysis_snapshot_id=self.snapshot_id,
            horizon_hours=1,
            reference_time=now,
            target_time=now + timedelta(hours=1),
            outcome_status="COMPLETE",
            actual_xau_usd=2410.0,
            xau_usd_direction="UP",
        )

    def _build_package(self, **overrides):
        defaults = {
            "analysis_timestamp": self.snapshot_time,
            "source_run_id": "test_evidence_001",
            "market_snapshot": self.market_snapshot,
            "market_state": self.market_state,
            "rep_price": MockRepPrice(price=190000000.0, source="milli", status="AVAILABLE"),
            "structure_state": MockStructureState(status="AVAILABLE"),
            "regime_result": RegimeResult(state="NORMAL", previous_state="NORMAL"),
            "classifier": RegimeClassifier(),
            "data_quality": {
                "overall": "AVAILABLE",
                "xau_usd": "AVAILABLE",
                "usd_irr": "AVAILABLE",
                "representative_price": "AVAILABLE",
            },
            "technical_state_json": {
                "representative_price": {"price": 190000000.0, "source": "milli"},
                "support_levels": [{"price": 189000000.0, "touches": 3}],
                "resistance_levels": [{"price": 191000000.0, "touches": 2}],
                "structure_status": "AVAILABLE",
            },
            "config": {},
        }
        defaults.update(overrides)
        return build_evidence_package(**defaults)

    # --- KPI-1: evidence package assembles ---
    def test_01_package_assembles(self):
        pkg = self._build_package()
        self.assertIsInstance(pkg, dict)
        self.assertIn("schema_version", pkg)

    # --- KPI-2: valuation evidence present ---
    def test_02_valuation_present(self):
        pkg = self._build_package()
        self.assertIn("valuation", pkg)
        self.assertEqual(pkg["valuation"]["valuation_state"], "CHEAP")
        self.assertIsNotNone(pkg["valuation"]["premium_percent"])

    # --- KPI-3: momentum evidence present ---
    def test_03_momentum_present(self):
        pkg = self._build_package()
        self.assertIn("momentum", pkg)
        self.assertEqual(pkg["momentum"]["momentum_state"], "IMPROVING")

    # --- KPI-4: technical evidence present ---
    def test_04_technical_present(self):
        pkg = self._build_package()
        self.assertIn("technical_structure", pkg)
        self.assertIsNotNone(pkg["technical_structure"]["representative_price"])

    # --- KPI-5: regime evidence present ---
    def test_05_regime_present(self):
        pkg = self._build_package()
        self.assertIn("regime", pkg)
        self.assertEqual(pkg["regime"]["regime_state"], "NORMAL")

    # --- KPI-6: XAU/USD evidence present ---
    def test_06_xau_present(self):
        pkg = self._build_package()
        self.assertIn("xau_usd", pkg)
        self.assertAlmostEqual(pkg["xau_usd"]["price"], 2400.50, places=2)

    # --- KPI-7: USD/IRR evidence present ---
    def test_07_usd_present(self):
        pkg = self._build_package()
        self.assertIn("usd_irr", pkg)
        self.assertAlmostEqual(pkg["usd_irr"]["price"], 50000.0, places=2)

    # --- KPI-8: representative gold evidence present ---
    def test_08_rep_gold_present(self):
        pkg = self._build_package()
        self.assertIn("representative_gold", pkg)
        self.assertEqual(pkg["representative_gold"]["source"], "milli")
        self.assertEqual(pkg["representative_gold"]["fallback_status"], "PRIMARY")

    # --- KPI-9: platform structure evidence present ---
    def test_09_platform_present(self):
        pkg = self._build_package()
        self.assertIn("platform_structure", pkg)
        self.assertIsNotNone(pkg["platform_structure"]["platform_spread"])

    # --- KPI-10: news evidence handled ---
    def test_10_news_present(self):
        pkg = self._build_package()
        self.assertIn("news_context", pkg)
        self.assertGreaterEqual(pkg["news_context"]["recent_event_count"], 1)

    # --- KPI-11: historical evidence handled ---
    def test_11_historical_present(self):
        pkg = self._build_package()
        self.assertIn("historical_context", pkg)
        # With seeded market state, similar states may or may not exist
        self.assertIn("status", pkg["historical_context"])

    # --- KPI-12: outcome context handled ---
    def test_12_outcome_present(self):
        pkg = self._build_package()
        self.assertIn("outcome_context", pkg)
        self.assertIn("latest_outcomes", pkg["outcome_context"])

    # --- KPI-13: data quality section present ---
    def test_13_data_quality_present(self):
        pkg = self._build_package()
        self.assertIn("data_quality", pkg)
        self.assertIn("components", pkg["data_quality"])

    # --- KPI-14: provenance preserved ---
    def test_14_provenance_present(self):
        pkg = self._build_package()
        self.assertIn("provenance", pkg
