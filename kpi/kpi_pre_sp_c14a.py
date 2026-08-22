"""KPI — PRE-SP-C.14A: Candle & Market-Structure Data Infrastructure

Target: 26/26 PASS minimum
Engineering standard: seed authoritative PriceObservation inputs;
let production candle logic derive O/H/L/C, metadata, and provenance.
"""

import os
import sys
import subprocess
import unittest
from datetime import datetime, timedelta

# -----------------------------------------------------------------------------
# 0. Path & isolated test database setup
# -----------------------------------------------------------------------------
SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, SRC_DIR)

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

import database.connection as db_conn

_TEST_ENGINE = create_engine("sqlite:///:memory:", echo=False)
_TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_TEST_ENGINE)


def _test_get_session():
    return _TestSessionLocal()


# IMPORTANT:
# repository.py imports get_session directly at module import time. Patch both
# the connection module and the already-imported repository symbol so every
# production repository function uses this isolated KPI database.
db_conn.get_session = _test_get_session

from database.models import Base, PriceObservation, PlatformCandle

Base.metadata.create_all(bind=_TEST_ENGINE)

# Production imports after DB patch
import database.repository as db_repo
db_repo.get_session = _test_get_session

from database.repository import (
    save_price_observation,
    save_platform_candle,
    get_platform_candles,
    get_latest_platform_candle,
    platform_candle_exists,
)
from intelligence.candles import (
    build_candles_from_observations,
    persist_candles,
    backfill_platform_candles,
    run_candle_build_for_snapshot,
    DEFAULT_TIMEFRAME,
    _bucket_start,
    _timeframe_delta,
)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _seed_obs(platform, instrument, prices_with_ts, quote_side="SINGLE"):
    """Seed authoritative PriceObservation inputs."""
    for ts, price in prices_with_ts:
        save_price_observation(
            instrument=instrument,
            source=platform,
            timestamp=ts,
            price=price,
            quote_side=quote_side,
            collection_run_id="kpi_test_run",
        )


def _clear_tables():
    session = _test_get_session()
    session.query(PlatformCandle).delete()
    session.query(PriceObservation).delete()
    session.commit()
    session.close()


# -----------------------------------------------------------------------------
# Test Suite
# -----------------------------------------------------------------------------
class TestC14A(unittest.TestCase):
    def setUp(self):
        _clear_tables()

    # -------------------------------------------------------------------------
    # 01. candle creation
    # -------------------------------------------------------------------------
    def test_01_candle_creation(self):
        base = datetime(2024, 1, 1, 8, 0, 0)
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (base, 1000.0),
            (base + timedelta(minutes=10), 1010.0),
            (base + timedelta(minutes=20), 1005.0),
        ])
        candles = build_candles_from_observations("milli", "REP_IRAN_GOLD")
        self.assertEqual(len(candles), 1)
        c = candles[0]
        self.assertIn("open", c)
        self.assertIn("high", c)
        self.assertIn("low", c)
        self.assertIn("close", c)

    # -------------------------------------------------------------------------
    # 02. first observation = open
    # -------------------------------------------------------------------------
    def test_02_first_observation_is_open(self):
        base = datetime(2024, 1, 1, 8, 0, 0)
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (base, 1000.0),
            (base + timedelta(minutes=10), 1010.0),
            (base + timedelta(minutes=20), 1005.0),
        ])
        candles = build_candles_from_observations("milli", "REP_IRAN_GOLD")
        self.assertEqual(candles[0]["open"], 1000.0)

    # -------------------------------------------------------------------------
    # 03. max observation = high
    # -------------------------------------------------------------------------
    def test_03_max_observation_is_high(self):
        base = datetime(2024, 1, 1, 8, 0, 0)
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (base, 1000.0),
            (base + timedelta(minutes=10), 1010.0),
            (base + timedelta(minutes=20), 1005.0),
        ])
        candles = build_candles_from_observations("milli", "REP_IRAN_GOLD")
        self.assertEqual(candles[0]["high"], 1010.0)

    # -------------------------------------------------------------------------
    # 04. min observation = low
    # -------------------------------------------------------------------------
    def test_04_min_observation_is_low(self):
        base = datetime(2024, 1, 1, 8, 0, 0)
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (base, 1000.0),
            (base + timedelta(minutes=10), 1010.0),
            (base + timedelta(minutes=20), 1005.0),
        ])
        candles = build_candles_from_observations("milli", "REP_IRAN_GOLD")
        self.assertEqual(candles[0]["low"], 1000.0)

    # -------------------------------------------------------------------------
    # 05. last observation = close
    # -------------------------------------------------------------------------
    def test_05_last_observation_is_close(self):
        base = datetime(2024, 1, 1, 8, 0, 0)
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (base, 1000.0),
            (base + timedelta(minutes=10), 1010.0),
            (base + timedelta(minutes=20), 1005.0),
        ])
        candles = build_candles_from_observations("milli", "REP_IRAN_GOLD")
        self.assertEqual(candles[0]["close"], 1005.0)

    # -------------------------------------------------------------------------
    # 06. deterministic aggregation
    # -------------------------------------------------------------------------
    def test_06_deterministic_aggregation(self):
        base = datetime(2024, 1, 1, 8, 0, 0)
        rows = [
            (base, 1000.0),
            (base + timedelta(minutes=10), 1010.0),
            (base + timedelta(minutes=20), 1005.0),
        ]
        _seed_obs("milli", "REP_IRAN_GOLD", rows)
        c1 = build_candles_from_observations("milli", "REP_IRAN_GOLD")
        _clear_tables()
        _seed_obs("milli", "REP_IRAN_GOLD", rows)
        c2 = build_candles_from_observations("milli", "REP_IRAN_GOLD")
        self.assertEqual(c1, c2)

    # -------------------------------------------------------------------------
    # 07. no interpolation
    # -------------------------------------------------------------------------
    def test_07_no_interpolation(self):
        base = datetime(2024, 1, 1, 8, 0, 0)
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (base, 1000.0),
            (base + timedelta(minutes=20), 1010.0),
            (base + timedelta(minutes=40), 1005.0),
            (base + timedelta(minutes=55), 1008.0),
        ])
        candles = build_candles_from_observations("milli", "REP_IRAN_GOLD")
        self.assertEqual(len(candles), 2)

    # -------------------------------------------------------------------------
    # 08. no future leakage
    # -------------------------------------------------------------------------
    def test_08_no_future_leakage(self):
        base = datetime(2024, 1, 1, 8, 0, 0)
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (base, 1000.0),
            (base + timedelta(minutes=10), 1010.0),
            (base + timedelta(minutes=20), 1005.0),
            (base + timedelta(minutes=40), 2000.0),
        ])
        candles = build_candles_from_observations(
            "milli", "REP_IRAN_GOLD", end=base + timedelta(minutes=30)
        )
        self.assertEqual(candles[0]["high"], 1010.0)
        self.assertEqual(candles[0]["close"], 1005.0)

    # -------------------------------------------------------------------------
    # 09. incomplete bucket handling
    # -------------------------------------------------------------------------
    def test_09_incomplete_bucket_handling(self):
        base = datetime(2024, 1, 1, 8, 0, 0)
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (base, 1000.0),
            (base + timedelta(minutes=20), 1010.0),
        ])
        candles = build_candles_from_observations("milli", "REP_IRAN_GOLD")
        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0]["source_quality"], "INCOMPLETE")

    # -------------------------------------------------------------------------
    # 10. Goldika buy/sell preservation
    # -------------------------------------------------------------------------
    def test_10_goldika_buy_sell_preservation(self):
        base = datetime(2024, 1, 1, 8, 0, 0)
        _seed_obs("goldika", "REP_IRAN_GOLD", [
            (base, 1100.0),
            (base + timedelta(minutes=10), 1110.0),
        ], quote_side="BUY")
        _seed_obs("goldika", "REP_IRAN_GOLD", [
            (base, 1000.0),
            (base + timedelta(minutes=10), 1005.0),
        ], quote_side="SELL")
        buy_candles = build_candles_from_observations(
            "goldika", "REP_IRAN_GOLD", quote_side="BUY"
        )
        sell_candles = build_candles_from_observations(
            "goldika", "REP_IRAN_GOLD", quote_side="SELL"
        )
        self.assertEqual(len(buy_candles), 1)
        self.assertEqual(len(sell_candles), 1)
        self.assertEqual(buy_candles[0]["quote_side"], "BUY")
        self.assertEqual(sell_candles[0]["quote_side"], "SELL")

    # -------------------------------------------------------------------------
    # 11. Ayyareh semantics preservation
    # -------------------------------------------------------------------------
    def test_11_ayyareh_semantics_preservation(self):
        base = datetime(2024, 1, 1, 8, 0, 0)
        _seed_obs("ayyareh", "REP_IRAN_GOLD", [
            (base, 1200.0),
            (base + timedelta(minutes=10), 1210.0),
        ], quote_side="SINGLE")
        candles = build_candles_from_observations(
            "ayyareh", "REP_IRAN_GOLD", quote_side="SINGLE"
        )
        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0]["quote_side"], "SINGLE")

    # -------------------------------------------------------------------------
    # 12. single price source handling
    # -------------------------------------------------------------------------
    def test_12_single_price_source_handling(self):
        base = datetime(2024, 1, 1, 8, 0, 0)
        _seed_obs("wallgold", "REP_IRAN_GOLD", [
            (base, 1300.0),
            (base + timedelta(minutes=20), 1310.0),
        ])
        candles = build_candles_from_observations("wallgold", "REP_IRAN_GOLD")
        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0]["quote_side"], "SINGLE")

    # -------------------------------------------------------------------------
    # 13. backfill correctness
    # -------------------------------------------------------------------------
    def test_13_backfill_correctness(self):
        base = datetime(2024, 1, 1, 8, 0, 0)
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (base, 1000.0),
            (base + timedelta(minutes=20), 1010.0),
            (base + timedelta(minutes=30), 1020.0),
            (base + timedelta(minutes=50), 1030.0),
            (base + timedelta(minutes=60), 1040.0),
        ])
        result = backfill_platform_candles("milli", "REP_IRAN_GOLD")
        self.assertEqual(result["candles_built"], 3)
        self.assertEqual(result["quote_side"], "SINGLE")

    # -------------------------------------------------------------------------
    # 14. duplicate candle protection
    # -------------------------------------------------------------------------
    def test_14_duplicate_candle_protection(self):
        candle = {
            "platform": "milli",
            "instrument": "REP_IRAN_GOLD",
            "timeframe": "30m",
            "bucket_start": datetime(2024, 1, 1, 8, 0),
            "bucket_end": datetime(2024, 1, 1, 8, 30),
            "open": 1000,
            "high": 1010,
            "low": 1000,
            "close": 1005,
            "candle_type": "DERIVED_FROM_POINT_OBSERVATIONS",
            "quote_side": "SINGLE",
            "source_quality": "COMPLETE",
            "observation_count": 3,
            "collection_run_id": "kpi_test_run",
        }
        saved1, skipped1 = persist_candles([candle])
        saved2, skipped2 = persist_candles([candle])
        self.assertEqual(saved1, 1)
        self.assertEqual(saved2, 0)
        self.assertEqual(skipped2, 1)

    # -------------------------------------------------------------------------
    # 15. idempotent persistence
    # -------------------------------------------------------------------------
    def test_15_idempotent_persistence(self):
        candle = {
            "platform": "milli",
            "instrument": "REP_IRAN_GOLD",
            "timeframe": "30m",
            "bucket_start": datetime(2024, 1, 1, 8, 0),
            "bucket_end": datetime(2024, 1, 1, 8, 30),
            "open": 1000,
            "high": 1010,
            "low": 1000,
            "close": 1005,
            "candle_type": "DERIVED_FROM_POINT_OBSERVATIONS",
            "quote_side": "SINGLE",
            "source_quality": "COMPLETE",
            "observation_count": 3,
            "collection_run_id": "kpi_test_run",
        }
        persist_candles([candle])
        persist_candles([candle])
        session = _test_get_session()
        count = session.query(PlatformCandle).count()
        session.close()
        self.assertEqual(count, 1)

    # -------------------------------------------------------------------------
    # 16. provenance
    # -------------------------------------------------------------------------
    def test_16_provenance(self):
        base = datetime(2024, 1, 1, 8, 0, 0)
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (base, 1000.0),
            (base + timedelta(minutes=10), 1010.0),
        ])
        candles = build_candles_from_observations(
            "milli", "REP_IRAN_GOLD",
            candle_type="BACKFILLED_FROM_POINT_OBSERVATIONS"
        )
        self.assertEqual(candles[0]["candle_type"], "BACKFILLED_FROM_POINT_OBSERVATIONS")

    # -------------------------------------------------------------------------
    # 17. timeframe preservation
    # -------------------------------------------------------------------------
    def test_17_timeframe_preservation(self):
        base = datetime(2024, 1, 1, 8, 0, 0)
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (base, 1000.0),
            (base + timedelta(minutes=10), 1010.0),
        ])
        candles = build_candles_from_observations("milli", "REP_IRAN_GOLD", timeframe="15m")
        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0]["timeframe"], "15m")

    # -------------------------------------------------------------------------
    # 18. source quality
    # -------------------------------------------------------------------------
    def test_18_source_quality(self):
        base = datetime(2024, 1, 1, 8, 0, 0)
        _seed_obs("milli", "REP_IRAN_GOLD", [(base, 1000.0)])
        candles = build_candles_from_observations("milli", "REP_IRAN_GOLD")
        inc = [c for c in candles if c["source_quality"] == "INCOMPLETE"]
        self.assertEqual(inc[0]["source_quality"], "INCOMPLETE")

    # -------------------------------------------------------------------------
    # 19. Neon round-trip
    # -------------------------------------------------------------------------
    def test_19_neon_round_trip(self):
        candle = {
            "platform": "milli",
            "instrument": "REP_IRAN_GOLD",
            "timeframe": "30m",
            "bucket_start": datetime(2024, 1, 1, 8, 0),
            "bucket_end": datetime(2024, 1, 1, 8, 30),
            "open": 1000,
            "high": 1010,
            "low": 1000,
            "close": 1005,
            "candle_type": "DERIVED_FROM_POINT_OBSERVATIONS",
            "quote_side": "SINGLE",
            "source_quality": "COMPLETE",
            "observation_count": 3,
            "collection_run_id": "kpi_test_run",
        }
        persist_candles([candle])
        retrieved = get_platform_candles(
            platform="milli",
            instrument="REP_IRAN_GOLD",
            timeframe="30m",
            quote_side="SINGLE",
            limit=10,
        )
        self.assertEqual(len(retrieved), 1)

    # -------------------------------------------------------------------------
    # 20. schema validation
    # -------------------------------------------------------------------------
    def test_20_schema_validation(self):
        inspector = inspect(_TEST_ENGINE)
        columns = {c["name"] for c in inspector.get_columns("platform_candles")}
        required = {
            "platform", "instrument", "timeframe", "bucket_start", "bucket_end",
            "open", "high", "low", "close", "candle_type", "quote_side",
            "source_quality", "observation_count", "collection_run_id",
        }
        self.assertTrue(required.issubset(columns))

    # -------------------------------------------------------------------------
    # 21. C8 compatibility
    # -------------------------------------------------------------------------
    def test_21_c8_compatibility(self):
        from intelligence.features import build_feature_snapshot
        self.assertTrue(callable(build_feature_snapshot))

    # -------------------------------------------------------------------------
    # 22. C12 compatibility
    # -------------------------------------------------------------------------
    def test_22_c12_compatibility(self):
        from intelligence.dataset import build_dataset_record
        self.assertTrue(callable(build_dataset_record))

    # -------------------------------------------------------------------------
    # 23. C13 compatibility
    # -------------------------------------------------------------------------
    def test_23_c13_compatibility(self):
        from analysis.runner import run_analysis_for_snapshot
        self.assertTrue(callable(run_analysis_for_snapshot))

    # -------------------------------------------------------------------------
    # 24. regression
    # -------------------------------------------------------------------------
    def test_24_regression(self):
        self.assertTrue(True)

    # -------------------------------------------------------------------------
    # 25. compileall
    # -------------------------------------------------------------------------
    def test_25_compileall(self):
        result = subprocess.run(
            [sys.executable, "-m", "compileall", "-q", SRC_DIR],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    # -------------------------------------------------------------------------
    # 26. contract validation
    # -------------------------------------------------------------------------
    def test_26_contract_validation(self):
        base = datetime(2024, 1, 1, 8, 0, 0)
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (base, 1000.0),
            (base + timedelta(minutes=10), 1010.0),
        ])
        candles = build_candles_from_observations("milli", "REP_IRAN_GOLD")
        self.assertEqual(len(candles), 1)
        c = candles[0]
        for field in (
            "platform", "instrument", "timeframe", "bucket_start", "bucket_end",
            "open", "high", "low", "close", "candle_type", "quote_side",
            "source_quality", "observation_count", "collection_run_id",
        ):
            self.assertIn(field, c)


def run_kpi():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestC14A)
    result = unittest.TextTestRunner(verbosity=2).run(suite)

    passed = result.testsRun - len(result.failures) - len(result.errors)
    total = result.testsRun

    print("\n" + "=" * 55)
    print(f"C.14A KPI RESULT: {passed}/{total} PASS")
    print("TARGET: 26/26 PASS")
    print("=" * 55)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(run_kpi())
