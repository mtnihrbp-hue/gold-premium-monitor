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

# CRITICAL: Patch database.connection BEFORE any project imports
import database.connection as db_conn

_TEST_ENGINE = create_engine("sqlite:///:memory:", echo=False)
_TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_TEST_ENGINE)


def _test_get_session():
    return _TestSessionLocal()


db_conn.get_session = _test_get_session

# Now safe to import project modules
from database.models import Base, PriceObservation, PlatformCandle

Base.metadata.create_all(bind=_TEST_ENGINE)

from database.repository import (
    save_price_observation,
    save_platform_candle,
    get_platform_candles,
    get_latest_platform_candle,
    platform_candle_exists,
)

# EXTRA: patch repository's local get_session reference in case it captured
# the unpatched function before db_conn.get_session was updated
import database.repository as _repo_module

_repo_module.get_session = _test_get_session

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
# All fixtures use recent timestamps so they fall within the 720-hour window
NOW = datetime.now()
BASE = NOW.replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)


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
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (BASE, 1000.0),
            (BASE + timedelta(minutes=10), 1010.0),
            (BASE + timedelta(minutes=20), 1005.0),
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
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (BASE, 1000.0),
            (BASE + timedelta(minutes=10), 1010.0),
            (BASE + timedelta(minutes=20), 1005.0),
        ])
        candles = build_candles_from_observations("milli", "REP_IRAN_GOLD")
        self.assertEqual(candles[0]["open"], 1000.0)

    # -------------------------------------------------------------------------
    # 03. max observation = high
    # -------------------------------------------------------------------------
    def test_03_max_observation_is_high(self):
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (BASE, 1000.0),
            (BASE + timedelta(minutes=10), 1010.0),
            (BASE + timedelta(minutes=20), 1005.0),
        ])
        candles = build_candles_from_observations("milli", "REP_IRAN_GOLD")
        self.assertEqual(candles[0]["high"], 1010.0)

    # -------------------------------------------------------------------------
    # 04. min observation = low
    # -------------------------------------------------------------------------
    def test_04_min_observation_is_low(self):
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (BASE, 1000.0),
            (BASE + timedelta(minutes=10), 1010.0),
            (BASE + timedelta(minutes=20), 1005.0),
        ])
        candles = build_candles_from_observations("milli", "REP_IRAN_GOLD")
        self.assertEqual(candles[0]["low"], 1000.0)

    # -------------------------------------------------------------------------
    # 05. last observation = close
    # -------------------------------------------------------------------------
    def test_05_last_observation_is_close(self):
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (BASE, 1000.0),
            (BASE + timedelta(minutes=10), 1010.0),
            (BASE + timedelta(minutes=20), 1005.0),
        ])
        candles = build_candles_from_observations("milli", "REP_IRAN_GOLD")
        self.assertEqual(candles[0]["close"], 1005.0)

    # -------------------------------------------------------------------------
    # 06. deterministic aggregation
    # -------------------------------------------------------------------------
    def test_06_deterministic_aggregation(self):
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (BASE, 1000.0),
            (BASE + timedelta(minutes=10), 1010.0),
            (BASE + timedelta(minutes=20), 1005.0),
        ])
        c1 = build_candles_from_observations("milli", "REP_IRAN_GOLD")
        c2 = build_candles_from_observations("milli", "REP_IRAN_GOLD")
        self.assertEqual(len(c1), len(c2))
        for a, b in zip(c1, c2):
            self.assertEqual(a["open"], b["open"])
            self.assertEqual(a["high"], b["high"])
            self.assertEqual(a["low"], b["low"])
            self.assertEqual(a["close"], b["close"])

    # -------------------------------------------------------------------------
    # 07. no interpolation
    # -------------------------------------------------------------------------
    def test_07_no_interpolation(self):
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (BASE, 1000.0),
            (BASE + timedelta(hours=1), 1020.0),
        ])
        candles = build_candles_from_observations("milli", "REP_IRAN_GOLD")
        self.assertEqual(len(candles), 2)
        # No fabricated middle bucket
        starts = [c["bucket_start"] for c in candles]
        self.assertNotIn(BASE + timedelta(minutes=30), starts)

    # -------------------------------------------------------------------------
    # 08. no future leakage
    # -------------------------------------------------------------------------
    def test_08_no_future_leakage(self):
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (BASE, 1000.0),
            (BASE + timedelta(minutes=10), 1010.0),
            (BASE + timedelta(minutes=40), 1020.0),
        ])
        end_boundary = BASE + timedelta(minutes=20)
        candles = build_candles_from_observations(
            "milli", "REP_IRAN_GOLD", end=end_boundary
        )
        prices = [c["close"] for c in candles]
        self.assertNotIn(1020.0, prices)

    # -------------------------------------------------------------------------
    # 09. incomplete bucket handling
    # -------------------------------------------------------------------------
    def test_09_incomplete_bucket_handling(self):
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (BASE, 1000.0),
        ])
        candles = build_candles_from_observations("milli", "REP_IRAN_GOLD")
        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0]["source_quality"], "INCOMPLETE")

    # -------------------------------------------------------------------------
    # 10. Goldika buy/sell preservation
    # -------------------------------------------------------------------------
    def test_10_goldika_buy_sell_preservation(self):
        _seed_obs("goldika", "REP_IRAN_GOLD", [
            (BASE, 1000000.0),
            (BASE + timedelta(minutes=10), 1005000.0),
        ], quote_side="BUY")
        _seed_obs("goldika", "REP_IRAN_GOLD", [
            (BASE, 995000.0),
            (BASE + timedelta(minutes=10), 998000.0),
        ], quote_side="SELL")
        buy_candles = build_candles_from_observations(
            "goldika", "REP_IRAN_GOLD", quote_side="BUY"
        )
        sell_candles = build_candles_from_observations(
            "goldika", "REP_IRAN_GOLD", quote_side="SELL"
        )
        self.assertEqual(len(buy_candles), 1)
        self.assertEqual(len(sell_candles), 1)
        self.assertNotEqual(buy_candles[0]["close"], sell_candles[0]["close"])

    # -------------------------------------------------------------------------
    # 11. Ayyareh semantics preservation
    # -------------------------------------------------------------------------
    def test_11_ayyareh_semantics_preservation(self):
        _seed_obs("ayyareh", "REP_IRAN_GOLD", [
            (BASE, 1000000.0),
            (BASE + timedelta(minutes=10), 1002000.0),
        ], quote_side="SINGLE")
        candles = build_candles_from_observations(
            "ayyareh", "REP_IRAN_GOLD", quote_side="SINGLE"
        )
        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0]["quote_side"], "SINGLE")

    # -------------------------------------------------------------------------
    # 12. single-price source handling
    # -------------------------------------------------------------------------
    def test_12_single_price_source_handling(self):
        for platform in ["milli", "wallgold"]:
            _seed_obs(platform, "REP_IRAN_GOLD", [
                (BASE, 1000000.0),
            ], quote_side="SINGLE")
            candles = build_candles_from_observations(
                platform, "REP_IRAN_GOLD", quote_side="SINGLE"
            )
            self.assertEqual(len(candles), 1)
            self.assertEqual(candles[0]["quote_side"], "SINGLE")

    # -------------------------------------------------------------------------
    # 13. backfill correctness
    # -------------------------------------------------------------------------
    def test_13_backfill_correctness(self):
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (BASE, 1000.0),
            (BASE + timedelta(minutes=30), 1010.0),
            (BASE + timedelta(minutes=60), 1020.0),
        ])
        result = backfill_platform_candles("milli", "REP_IRAN_GOLD", "30m", "SINGLE")
        self.assertEqual(result["candles_built"], 3)
        self.assertEqual(result["candles_saved"], 3)

    # -------------------------------------------------------------------------
    # 14. duplicate candle protection
    # -------------------------------------------------------------------------
    def test_14_duplicate_candle_protection(self):
        candle = {
            "platform": "milli",
            "instrument": "REP_IRAN_GOLD",
            "timeframe": "30m",
            "bucket_start": BASE,
            "bucket_end": BASE + timedelta(minutes=30),
            "open": 1000.0,
            "high": 1010.0,
            "low": 999.0,
            "close": 1005.0,
            "candle_type": "DERIVED_FROM_POINT_OBSERVATIONS",
            "quote_side": "SINGLE",
            "source_quality": "COMPLETE",
            "observation_count": 2,
            "collection_run_id": "test",
        }
        saved1, skipped1 = persist_candles([candle])
        saved2, skipped2 = persist_candles([candle])
        self.assertEqual(saved1, 1)
        # Second persist should skip the duplicate
        self.assertEqual(saved2, 0)
        self.assertEqual(skipped2, 1)
        # Verify only one row exists
        session = _test_get_session()
        count = session.query(PlatformCandle).count()
        session.close()
        self.assertEqual(count, 1)

    # -------------------------------------------------------------------------
    # 15. idempotent persistence
    # -------------------------------------------------------------------------
    def test_15_idempotent_persistence(self):
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (BASE, 1000.0),
            (BASE + timedelta(minutes=10), 1010.0),
        ])
        candles = build_candles_from_observations("milli", "REP_IRAN_GOLD")
        persist_candles(candles)
        persist_candles(candles)
        session = _test_get_session()
        count = session.query(PlatformCandle).count()
        session.close()
        self.assertEqual(count, 1)

    # -------------------------------------------------------------------------
    # 16. provenance
    # -------------------------------------------------------------------------
    def test_16_provenance(self):
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (BASE, 1000.0),
        ])
        candles = build_candles_from_observations(
            "milli", "REP_IRAN_GOLD",
            collection_run_id="run_20240101_080000",
            candle_type="BACKFILLED_FROM_POINT_OBSERVATIONS",
        )
        self.assertEqual(candles[0]["candle_type"], "BACKFILLED_FROM_POINT_OBSERVATIONS")
        self.assertEqual(candles[0]["collection_run_id"], "run_20240101_080000")

    # -------------------------------------------------------------------------
    # 17. timeframe preservation
    # -------------------------------------------------------------------------
    def test_17_timeframe_preservation(self):
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (BASE, 1000.0),
            (BASE + timedelta(minutes=29), 1010.0),
        ])
        candles = build_candles_from_observations("milli", "REP_IRAN_GOLD", timeframe="30m")
        self.assertEqual(len(candles), 1)
        delta = candles[0]["bucket_end"] - candles[0]["bucket_start"]
        self.assertEqual(delta, timedelta(minutes=30))

    # -------------------------------------------------------------------------
    # 18. source quality
    # -------------------------------------------------------------------------
    def test_18_source_quality(self):
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (BASE, 1000.0),
        ])
        _seed_obs("wallgold", "REP_IRAN_GOLD", [
            (BASE, 1000.0),
            (BASE + timedelta(minutes=10), 1010.0),
            (BASE + timedelta(minutes=20), 1020.0),
        ])
        inc = build_candles_from_observations("milli", "REP_IRAN_GOLD")
        comp = build_candles_from_observations("wallgold", "REP_IRAN_GOLD")
        self.assertEqual(inc[0]["source_quality"], "INCOMPLETE")
        self.assertEqual(comp[0]["source_quality"], "COMPLETE")

    # -------------------------------------------------------------------------
    # 19. Neon round-trip
    # -------------------------------------------------------------------------
    def test_19_neon_round_trip(self):
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (BASE, 1000.0),
            (BASE + timedelta(minutes=10), 1010.0),
        ])
        candles = build_candles_from_observations("milli", "REP_IRAN_GOLD")
        persist_candles(candles)
        retrieved = get_platform_candles(
            platform="milli", instrument="REP_IRAN_GOLD", timeframe="30m"
        )
        self.assertEqual(len(retrieved), 1)
        self.assertEqual(float(retrieved[0].open), 1000.0)
        self.assertEqual(float(retrieved[0].high), 1010.0)

    # -------------------------------------------------------------------------
    # 20. schema validation
    # -------------------------------------------------------------------------
    def test_20_schema_validation(self):
        inspector = inspect(_TEST_ENGINE)
        columns = {c["name"] for c in inspector.get_columns("platform_candles")}
        required = {
            "id", "platform", "instrument", "timeframe", "bucket_start",
            "bucket_end", "open", "high", "low", "close", "candle_type",
            "quote_side", "source_quality", "observation_count",
            "collection_run_id", "created_at",
        }
        self.assertTrue(required.issubset(columns))

    # -------------------------------------------------------------------------
    # 21. C.8 compatibility
    # -------------------------------------------------------------------------
    def test_21_c8_compatibility(self):
        from intelligence.features import build_feature_snapshot, FEATURE_SCHEMA_VERSION
        self.assertEqual(FEATURE_SCHEMA_VERSION, "1")

    # -------------------------------------------------------------------------
    # 22. C.12 compatibility
    # -------------------------------------------------------------------------
    def test_22_c12_compatibility(self):
        from intelligence.dataset import build_dataset_record, DATASET_SCHEMA_VERSION
        self.assertEqual(DATASET_SCHEMA_VERSION, "1")

    # -------------------------------------------------------------------------
    # 23. C.13 compatibility
    # -------------------------------------------------------------------------
    def test_23_c13_compatibility(self):
        from analysis.snapshot_builder import build_analysis_snapshot
        self.assertTrue(callable(build_analysis_snapshot))

    # -------------------------------------------------------------------------
    # 24. regression
    # -------------------------------------------------------------------------
    def test_24_regression(self):
        # Verify all prior phase modules still import cleanly
        import analysis.outcome_evaluator
        import analysis.evidence_package
        import intelligence.market_intelligence
        import intelligence.read_model
        import intelligence.read_model_integration

    # -------------------------------------------------------------------------
    # 25. compileall
    # -------------------------------------------------------------------------
    def test_25_compileall(self):
        repo_root = os.path.join(os.path.dirname(__file__), "..")
        result = subprocess.run(
            [sys.executable, "-m", "compileall", "src"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode, 0,
            f"compileall failed:\n{result.stdout}\n{result.stderr}"
        )

    # -------------------------------------------------------------------------
    # 26. contract validation
    # -------------------------------------------------------------------------
    def test_26_contract_validation(self):
        _seed_obs("milli", "REP_IRAN_GOLD", [
            (BASE, 1000.0),
        ])
        candles = build_candles_from_observations("milli", "REP_IRAN_GOLD")
        self.assertEqual(len(candles), 1)
        c = candles[0]
        required_keys = [
            "platform", "instrument", "timeframe", "bucket_start", "bucket_end",
            "open", "high", "low", "close", "candle_type", "quote_side",
            "source_quality", "observation_count", "collection_run_id",
        ]
        for key in required_keys:
            self.assertIn(key, c, f"Missing contract key: {key}")


# -----------------------------------------------------------------------------
# Runner
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestC14A)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print(f"\n{'=' * 55}")
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print(f"C.14A KPI RESULT: {passed}/{result.testsRun} PASS")
    print(f"TARGET: 26/26 PASS")
    print(f"{'=' * 55}")
    sys.exit(0 if result.wasSuccessful() else 1)
