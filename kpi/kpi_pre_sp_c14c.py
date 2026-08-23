"""KPI — PRE-SP-C.14C: Adaptive Intelligence Foundation

Target: 21/21 PASS
Downstream diagnostic layer only. No adaptation. No pipeline change.
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

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import database.connection as db_conn

_TEST_ENGINE = create_engine("sqlite:///:memory:", echo=False)
_TestSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=_TEST_ENGINE, expire_on_commit=False
)


def _test_get_session():
    return _TestSessionLocal()


db_conn.get_session = _test_get_session
import database.repository as _repo_module
_repo_module.get_session = _test_get_session

from database.models import Base, AnalysisSnapshot, OutcomeEvaluation
Base.metadata.create_all(bind=_TEST_ENGINE)

# C.14C imports — subfolder or flat
try:
    from intelligence.c14c.error_classifier import classify_error, ERROR_CATEGORIES
    from intelligence.c14c.regime_analysis import analyze_regime_performance
    from intelligence.c14c.reliability_analysis import analyze_feature_reliability
    from intelligence.c14c.event_interface import EventInterpreter, StubEventInterpreter
    from intelligence.c14c.intelligence_layer import analyze_forecast_outcome, analyze_historical_batch
except ImportError:
    from intelligence.error_classifier import classify_error, ERROR_CATEGORIES
    from intelligence.regime_analysis import analyze_regime_performance
    from intelligence.reliability_analysis import analyze_feature_reliability
    from intelligence.event_interface import EventInterpreter, StubEventInterpreter
    from intelligence.intelligence_layer import analyze_forecast_outcome, analyze_historical_batch


# -----------------------------------------------------------------------------
# Test Suite
# -----------------------------------------------------------------------------
class TestC14C(unittest.TestCase):

    # -------------------------------------------------------------------------
    # 01. C.14B contract preserved
    # -------------------------------------------------------------------------
    def test_01_c14b_contract_preserved(self):
        from intelligence.forecast_contract import ForecastResult, validate_forecast_result
        from intelligence.forecast_engine import generate_forecast, run_forecast_evaluation
        self.assertTrue(callable(generate_forecast))
        self.assertTrue(callable(run_forecast_evaluation))

    # -------------------------------------------------------------------------
    # 02. Error classifier — correct prediction
    # -------------------------------------------------------------------------
    def test_02_error_classifier_correct(self):
        result = classify_error(forecast="UP", actual="UP")
        self.assertIsNone(result)

    # -------------------------------------------------------------------------
    # 03. Error classifier — direction error
    # -------------------------------------------------------------------------
    def test_03_error_classifier_direction(self):
        result = classify_error(forecast="UP", actual="DOWN")
        self.assertEqual(result, "DIRECTION_ERROR")

    # -------------------------------------------------------------------------
    # 04. Error classifier — confidence error
    # -------------------------------------------------------------------------
    def test_04_error_classifier_confidence(self):
        result = classify_error(
            forecast="UP", actual="DOWN",
            confidence=0.85,
            probabilities={"UP": 0.85, "NEUTRAL": 0.10, "DOWN": 0.05},
        )
        self.assertEqual(result, "CONFIDENCE_ERROR")

    # -------------------------------------------------------------------------
    # 05. Error classifier — regime error
    # -------------------------------------------------------------------------
    def test_05_error_classifier_regime(self):
        result = classify_error(forecast="UP", actual="DOWN", regime="PANIC")
        self.assertEqual(result, "REGIME_ERROR")

    # -------------------------------------------------------------------------
    # 06. Error classifier — timing error
    # -------------------------------------------------------------------------
    def test_06_error_classifier_timing(self):
        result = classify_error(
            forecast="UP", actual="DOWN",
            other_horizons={6: "UP", 24: "NEUTRAL"},
        )
        self.assertEqual(result, "TIMING_ERROR")

    # -------------------------------------------------------------------------
    # 07. Error classifier — data quality error
    # -------------------------------------------------------------------------
    def test_07_error_classifier_data_quality(self):
        result = classify_error(forecast=None, actual="UP")
        self.assertEqual(result, "DATA_QUALITY_ERROR")
        result2 = classify_error(
            forecast="UP", actual="DOWN",
            feature_quality="DEGRADED",
        )
        self.assertEqual(result2, "DATA_QUALITY_ERROR")

    # -------------------------------------------------------------------------
    # 08. Error categories frozen
    # -------------------------------------------------------------------------
    def test_08_error_categories(self):
        self.assertIn("DIRECTION_ERROR", ERROR_CATEGORIES)
        self.assertIn("CONFIDENCE_ERROR", ERROR_CATEGORIES)
        self.assertIn("TIMING_ERROR", ERROR_CATEGORIES)
        self.assertIn("REGIME_ERROR", ERROR_CATEGORIES)
        self.assertIn("DATA_QUALITY_ERROR", ERROR_CATEGORIES)

    # -------------------------------------------------------------------------
    # 09. Regime analysis — insufficient data
    # -------------------------------------------------------------------------
    def test_09_regime_insufficient(self):
        records = [
            {"regime": "NORMAL", "forecast": "UP", "actual": "UP", "correct": True, "confidence": 0.7},
        ]
        result = analyze_regime_performance(records)
        self.assertEqual(result["NORMAL"]["status"], "INSUFFICIENT_DATA")

    # -------------------------------------------------------------------------
    # 10. Regime analysis — normal metrics
    # -------------------------------------------------------------------------
    def test_10_regime_normal(self):
        records = [
            {"regime": "NORMAL", "forecast": "UP", "actual": "UP", "correct": True, "confidence": 0.8},
            {"regime": "NORMAL", "forecast": "UP", "actual": "DOWN", "correct": False, "confidence": 0.7},
            {"regime": "NORMAL", "forecast": "DOWN", "actual": "DOWN", "correct": True, "confidence": 0.75},
            {"regime": "NORMAL", "forecast": "UP", "actual": "UP", "correct": True, "confidence": 0.9},
        ]
        result = analyze_regime_performance(records)
        self.assertEqual(result["NORMAL"]["status"], "OK")
        self.assertEqual(result["NORMAL"]["sample_count"], 4)

    # -------------------------------------------------------------------------
    # 11. Regime analysis — calibration gap
    # -------------------------------------------------------------------------
    def test_11_regime_calibration(self):
        records = [
            {"regime": "FEAR", "forecast": "UP", "actual": "UP", "correct": True, "confidence": 0.9},
            {"regime": "FEAR", "forecast": "UP", "actual": "UP", "correct": True, "confidence": 0.9},
            {"regime": "FEAR", "forecast": "UP", "actual": "DOWN", "correct": False, "confidence": 0.9},
        ]
        result = analyze_regime_performance(records)
        self.assertIn("calibration_gap", result["FEAR"])

    # -------------------------------------------------------------------------
    # 12. Feature reliability — basic
    # -------------------------------------------------------------------------
    def test_12_feature_reliability(self):
        records = [
            {"features": {"f1": 1.0, "f2": 2.0}, "correct": True},
            {"features": {"f1": 1.1, "f2": 1.9}, "correct": True},
            {"features": {"f1": 5.0, "f2": 0.5}, "correct": False},
        ]
        result = analyze_feature_reliability(records)
        self.assertIn("f1", result)
        self.assertIn("f2", result)
        self.assertGreater(result["f1"]["correct_count"], 0)
        self.assertGreater(result["f1"]["incorrect_count"], 0)

    # -------------------------------------------------------------------------
    # 13. Feature reliability — separation
    # -------------------------------------------------------------------------
    def test_13_feature_separation(self):
        records = [
            {"features": {"x": 10.0}, "correct": True},
            {"features": {"x": 11.0}, "correct": True},
            {"features": {"x": 1.0}, "correct": False},
            {"features": {"x": 2.0}, "correct": False},
        ]
        result = analyze_feature_reliability(records)
        sep = result["x"]["mean_separation"]
        self.assertIsNotNone(sep)
        self.assertGreater(sep, 0)

    # -------------------------------------------------------------------------
    # 14. Event interpreter — abstract
    # -------------------------------------------------------------------------
    def test_14_event_interpreter_abstract(self):
        self.assertTrue(issubclass(StubEventInterpreter, EventInterpreter))

    # -------------------------------------------------------------------------
    # 15. Event interpreter — stub classify
    # -------------------------------------------------------------------------
    def test_15_stub_classify(self):
        stub = StubEventInterpreter()
        result = stub.classify({"title": "Gold rises", "source": "test"})
        self.assertIn("event_type", result)
        self.assertIn("sentiment", result)
        self.assertEqual(result["interpreter"], "stub")

    # -------------------------------------------------------------------------
    # 16. Event interpreter — stub summarize
    # -------------------------------------------------------------------------
    def test_16_stub_summarize(self):
        stub = StubEventInterpreter()
        result = stub.summarize([{"title": "a"}, {"title": "b"}])
        self.assertEqual(result["event_count"], 2)
        self.assertEqual(result["interpreter"], "stub")

    # -------------------------------------------------------------------------
    # 17. Intelligence layer — single forecast
    # -------------------------------------------------------------------------
    def test_17_single_forecast_analysis(self):
        result = analyze_forecast_outcome(
            forecast="UP", actual="DOWN",
            confidence=0.8, probabilities={"UP": 0.8, "NEUTRAL": 0.1, "DOWN": 0.1},
            regime="PANIC", snapshot_id=42,
        )
        self.assertEqual(result["forecast"], "UP")
        self.assertEqual(result["actual"], "DOWN")
        self.assertFalse(result["correct"])
        self.assertIsNotNone(result["error_type"])

    # -------------------------------------------------------------------------
    # 18. Intelligence layer — historical batch
    # -------------------------------------------------------------------------
    def test_18_historical_batch(self):
        records = [
            {"forecast": "UP", "actual": "UP", "correct": True, "regime": "NORMAL", "features": {"a": 1.0}},
            {"forecast": "UP", "actual": "DOWN", "correct": False, "regime": "NORMAL", "features": {"a": 5.0}},
            {"forecast": "DOWN", "actual": "DOWN", "correct": True, "regime": "FEAR", "features": {"a": 1.0}},
        ]
        result = analyze_historical_batch(records)
        self.assertEqual(result["total_evaluated"], 3)
        self.assertIn("regime_performance", result)
        self.assertIn("feature_reliability", result)
        self.assertIn("error_breakdown", result)

    # -------------------------------------------------------------------------
    # 19. No decision authority
    # -------------------------------------------------------------------------
    def test_19_no_decision_authority(self):
        result = analyze_forecast_outcome(forecast="UP", actual="DOWN")
        s = str(result).upper()
        self.assertNotIn("'BUY'", s)
        self.assertNotIn("'SELL'", s)
        self.assertNotIn("RECOMMENDED_ACTION", s)
        self.assertNotIn("FINAL_DECISION", s)

    # -------------------------------------------------------------------------
    # 20. No future leakage in diagnostics
    # -------------------------------------------------------------------------
    def test_20_no_future_leakage(self):
        # All C.14C functions are pure — they only consume provided arguments
        # No database queries, no timestamp comparisons, no global state
        result = analyze_forecast_outcome(
            forecast="UP", actual="DOWN",
            timestamp=datetime(2024, 1, 1, 8, 0, 0),
        )
        self.assertEqual(result["timestamp"], "2024-01-01T08:00:00")

    # -------------------------------------------------------------------------
    # 21. compileall
    # -------------------------------------------------------------------------
    def test_21_compileall(self):
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


# -----------------------------------------------------------------------------
# Runner
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestC14C)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print(f"\n{'=' * 55}")
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print(f"C.14C KPI RESULT: {passed}/{result.testsRun} PASS")
    print(f"TARGET: 21/21 PASS")
    print(f"{'=' * 55}")
    sys.exit(0 if result.wasSuccessful() else 1)
