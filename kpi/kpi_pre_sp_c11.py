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
                "outcome_history": {"status": "INSUFF
