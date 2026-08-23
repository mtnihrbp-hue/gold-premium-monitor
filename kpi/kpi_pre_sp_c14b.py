"""KPI — PRE-SP-C.14B: Forecast Features, Baselines, Evaluation & Forecast Engine

Target: 35/35 PASS
Contract-first. No imagined implementation.
"""

import copy
import os
import sys
import subprocess
import unittest
import warnings
import math
from datetime import datetime, timedelta
from dataclasses import asdict

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

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

from intelligence.forecast_contract import (
    ForecastResult,
    validate_forecast_result,
    VALID_STATUSES,
    VALID_DIRECTIONS,
)
from intelligence.forecast_features import FEATURE_SCHEMA_VERSION, build_forecast_feature_vector
from intelligence.forecast_engine import (
    run_forecast_evaluation,
    generate_forecast,
    measure_data_readiness,
    _extract_label,
    _majority_predict,
    _persistence_predict,
    _c8_deterministic_predict,
    VALID_LABELS,
)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _make_features(direction="UP"):
    velocity = 0.5 if direction == "UP" else (-0.5 if direction == "DOWN" else 0.0)
    return {
        "schema_version": "1",
        "price_trend": {
            "rep_gold_ma7": 1000000.0,
            "rep_gold_ema7": 1000000.0,
            "rep_gold_vs_ma7_percent": 0.5,
        },
        "momentum": {
            "premium_velocity": velocity,
            "premium_acceleration": 0.01,
            "premium_latest_direction": direction,
            "premium_direction_persistence": 2,
            "momentum_change_rate_percent": velocity / 10.0,
        },
        "volatility": {
            "rep_gold_volatility_7": 1.5,
            "rep_gold_range_expansion_percent": 0.0,
            "rep_gold_max_period_change_percent": 0.2,
        },
        "regime": {
            "current_regime": "NORMAL",
            "previous_regime": "NORMAL",
            "regime_duration_observations": 5,
            "regime_transition_frequency": 0,
        },
        "market_relation": {
            "xau_usd_direction": direction,
            "usd_irr_direction": direction,
            "rep_gold_direction": direction,
            "premium_vs_local_gold_alignment": "ALIGNED",
            "xau_local_divergence": False,
            "usd_irr_local_gold_pressure": "SAME",
        },
        "structure": {
            "platform_spread": 50000.0,
            "consensus_ratio": 0.6,
            "discount_dominance": True,
            "premium_concentration": 0.4,
        },
        "data_quality": {
            "rep_gold_observations": 50,
            "xau_usd_observations": 50,
            "usd_irr_observations": 50,
            "premium_observations": 30,
            "sufficient_history": True,
        },
    }


def _seed_snapshot(timestamp, label_direction, regime="NORMAL", features=None):
    session = _test_get_session()
    snap = AnalysisSnapshot(
        analysis_timestamp=timestamp,
        source_run_id=f"test_{timestamp.isoformat()}",
        snapshot_type="analysis",
        features_json=features or _make_features(label_direction),
        regime_state=regime,
    )
    session.add(snap)
    session.commit()
    session.refresh(snap)
    snap_id = snap.id

    ev = OutcomeEvaluation(
        analysis_snapshot_id=snap_id,
        horizon_hours=1,
        reference_time=timestamp,
        target_time=timestamp + timedelta(hours=1),
        outcome_status="COMPLETE",
        rep_gold_direction=label_direction,
    )
    session.add(ev)
    session.commit()
    session.close()
    return snap_id


def _clear_tables():
    session = _test_get_session()
    session.query(OutcomeEvaluation).delete()
    session.query(AnalysisSnapshot).delete()
    session.commit()
    session.close()


def _build_dataset(n=40, start_hours_ago=42):
    now = datetime.now()
    labels = ["UP", "DOWN", "FLAT"]  # FLAT is the valid C.5 direction, maps to NEUTRAL
    regimes = ["NORMAL", "FEAR", "PANIC"]
    for i in range(n):
        ts = now - timedelta(hours=start_hours_ago - i)
        label = labels[i % 3]
        regime = regimes[i % 3]
        _seed_snapshot(ts, label, regime)


def _get_latest_snapshot():
    session = _test_get_session()
    snap = session.query(AnalysisSnapshot).order_by(
        AnalysisSnapshot.analysis_timestamp.desc()
    ).first()
    session.close()
    return snap


# -----------------------------------------------------------------------------
# Test Suite
# -----------------------------------------------------------------------------
class TestC14B(unittest.TestCase):
    def setUp(self):
        _clear_tables()

    # -------------------------------------------------------------------------
    # 01. dataset readiness
    # -------------------------------------------------------------------------
    def test_01_dataset_readiness_insufficient(self):
        ready = measure_data_readiness(horizon_hours=1, hours_lookback=24, min_train_samples=10)
        self.assertFalse(ready["sufficient"])
        self.assertEqual(ready["status"], "INSUFFICIENT_DATA")

    def test_01b_dataset_readiness_sufficient(self):
        _build_dataset(n=40)
        ready = measure_data_readiness(horizon_hours=1, hours_lookback=168, min_train_samples=30)
        self.assertTrue(ready["sufficient"])
        self.assertEqual(ready["status"], "OK")
        for lbl in VALID_LABELS:
            self.assertGreaterEqual(ready["class_distribution"].get(lbl, 0), 3)

    # -------------------------------------------------------------------------
    # 02. label mapping
    # -------------------------------------------------------------------------
    def test_02_label_mapping(self):
        self.assertEqual(_extract_label(type("E", (), {"rep_gold_direction": "UP"})()), "UP")
        self.assertEqual(_extract_label(type("E", (), {"rep_gold_direction": "DOWN"})()), "DOWN")
        self.assertEqual(_extract_label(type("E", (), {"rep_gold_direction": "FLAT"})()), "NEUTRAL")
        self.assertIsNone(_extract_label(type("E", (), {"rep_gold_direction": "INSUFFICIENT_DATA"})()))
        self.assertIsNone(_extract_label(type("E", (), {"rep_gold_direction": None})()))

    # -------------------------------------------------------------------------
    # 03. baseline generation
    # -------------------------------------------------------------------------
    def test_03_baseline_generation(self):
        _build_dataset(n=10)
        session = _test_get_session()
        snaps = session.query(AnalysisSnapshot).order_by(AnalysisSnapshot.analysis_timestamp.asc()).all()
        session.close()
        recs = [{"label": "UP"}, {"label": "DOWN"}, {"label": "UP"}]
        self.assertIn(_majority_predict(recs), VALID_LABELS)
        self.assertEqual(_persistence_predict("UP"), "UP")
        self.assertIn(_c8_deterministic_predict(_make_features("UP")), VALID_LABELS)

    # -------------------------------------------------------------------------
    # 04. baseline determinism
    # -------------------------------------------------------------------------
    def test_04_baseline_determinism(self):
        recs = [{"label": "UP"}, {"label": "UP"}, {"label": "DOWN"}]
        self.assertEqual(_majority_predict(recs), _majority_predict(recs))
        features = _make_features("UP")
        self.assertEqual(
            _c8_deterministic_predict(features),
            _c8_deterministic_predict(features),
        )

    # -------------------------------------------------------------------------
    # 05. model generation
    # -------------------------------------------------------------------------
    def test_05_model_generation(self):
        _build_dataset(n=40)
        report = run_forecast_evaluation(
            horizon_hours=1,
            feature_config={"include_c8": True},
            min_train_samples=30,
            step=1,
            hours_lookback=168,
        )
        self.assertIn("logistic_regression", report["model_results"])
        self.assertIn("decision_tree", report["model_results"])

    # -------------------------------------------------------------------------
    # 06. model determinism
    # -------------------------------------------------------------------------
    def test_06_model_determinism(self):
        _build_dataset(n=40)
        r1 = run_forecast_evaluation(
            horizon_hours=1,
            feature_config={"include_c8": True},
            min_train_samples=30,
            step=1,
            hours_lookback=168,
        )
        r2 = run_forecast_evaluation(
            horizon_hours=1,
            feature_config={"include_c8": True},
            min_train_samples=30,
            step=1,
            hours_lookback=168,
        )
        m1 = r1["model_results"]["logistic_regression"]["metrics"]
        m2 = r2["model_results"]["logistic_regression"]["metrics"]
        if m1.get("status") == "OK" and m2.get("status") == "OK":
            self.assertEqual(m1["accuracy"], m2["accuracy"])

    # -------------------------------------------------------------------------
    # 07. probability validity
    # -------------------------------------------------------------------------
    def test_07_probability_validity(self):
        _build_dataset(n=40)
        target = _get_latest_snapshot()
        forecast = generate_forecast(target, horizon_hours=1, abstention_threshold=0.0)
        for d in VALID_LABELS:
            p = forecast.probabilities.get(d, 0.0)
            self.assertGreaterEqual(p, 0.0)
            self.assertLessEqual(p, 1.0)

    # -------------------------------------------------------------------------
    # 08. probability sum
    # -------------------------------------------------------------------------
    def test_08_probability_sum(self):
        _build_dataset(n=40)
        target = _get_latest_snapshot()
        forecast = generate_forecast(target, horizon_hours=1, abstention_threshold=0.0)
        if forecast.status == "OK":
            total = sum(forecast.probabilities.get(d, 0.0) for d in VALID_LABELS)
            self.assertAlmostEqual(total, 1.0, delta=1e-6)

    # -------------------------------------------------------------------------
    # 09. UP handling
    # -------------------------------------------------------------------------
    def test_09_up_handling(self):
        _build_dataset(n=40)
        report = run_forecast_evaluation(horizon_hours=1, min_train_samples=30, hours_lookback=168)
        m = report["model_results"]["majority_baseline"]["metrics"]
        self.assertIn("UP", m["precision"])

    # -------------------------------------------------------------------------
    # 10. NEUTRAL handling
    # -------------------------------------------------------------------------
    def test_10_neutral_handling(self):
        _build_dataset(n=40)
        report = run_forecast_evaluation(horizon_hours=1, min_train_samples=30, hours_lookback=168)
        m = report["model_results"]["majority_baseline"]["metrics"]
        self.assertIn("NEUTRAL", m["precision"])

    # -------------------------------------------------------------------------
    # 11. DOWN handling
    # -------------------------------------------------------------------------
    def test_11_down_handling(self):
        _build_dataset(n=40)
        report = run_forecast_evaluation(horizon_hours=1, min_train_samples=30, hours_lookback=168)
        m = report["model_results"]["majority_baseline"]["metrics"]
        self.assertIn("DOWN", m["precision"])

    # -------------------------------------------------------------------------
    # 12. insufficient-data handling
    # -------------------------------------------------------------------------
    def test_12_insufficient_data_handling(self):
        report = run_forecast_evaluation(horizon_hours=1, min_train_samples=100, hours_lookback=24)
        self.assertEqual(report["status"], "INSUFFICIENT_DATA")

    # -------------------------------------------------------------------------
    # 13. abstention
    # -------------------------------------------------------------------------
    def test_13_abstention(self):
        _build_dataset(n=40)
        report = run_forecast_evaluation(
            horizon_hours=1,
            min_train_samples=30,
            hours_lookback=168,
            abstention_threshold=1.0,
        )
        lr = report["model_results"]["logistic_regression"]["metrics"]
        self.assertGreater(lr["abstention_rate"], 0.0)

    # -------------------------------------------------------------------------
    # 14. provenance
    # -------------------------------------------------------------------------
    def test_14_provenance(self):
        _build_dataset(n=40)
        target = _get_latest_snapshot()
        forecast = generate_forecast(target, horizon_hours=1, abstention_threshold=0.0)
        self.assertIn("snapshot_id", forecast.provenance)

    # -------------------------------------------------------------------------
    # 15. model version
    # -------------------------------------------------------------------------
    def test_15_model_version(self):
        _build_dataset(n=40)
        target = _get_latest_snapshot()
        forecast = generate_forecast(target, horizon_hours=1, model_name="logistic_regression")
        self.assertIsInstance(forecast.model_version, str)
        self.assertGreater(len(forecast.model_version), 0)

    # -------------------------------------------------------------------------
    # 16. feature schema version
    # -------------------------------------------------------------------------
    def test_16_feature_schema_version(self):
        _build_dataset(n=40)
        target = _get_latest_snapshot()
        forecast = generate_forecast(target, horizon_hours=1)
        self.assertEqual(forecast.feature_schema_version, "1")

    # -------------------------------------------------------------------------
    # 17. label schema version
    # -------------------------------------------------------------------------
    def test_17_label_schema_version(self):
        _build_dataset(n=40)
        target = _get_latest_snapshot()
        forecast = generate_forecast(target, horizon_hours=1)
        self.assertEqual(forecast.label_schema_version, "1")

    # -------------------------------------------------------------------------
    # 18. horizon preservation
    # -------------------------------------------------------------------------
    def test_18_horizon_preservation(self):
        _build_dataset(n=40)
        target = _get_latest_snapshot()
        for h in [1, 6, 24]:
            forecast = generate_forecast(target, horizon_hours=h)
            self.assertEqual(forecast.horizon_hours, h)

    # -------------------------------------------------------------------------
    # 19. chronological split
    # -------------------------------------------------------------------------
    def test_19_chronological_split(self):
        _build_dataset(n=40)
        report = run_forecast_evaluation(horizon_hours=1, min_train_samples=30, hours_lookback=168)
        preds = report["model_results"]["logistic_regression"].get("metrics", {})
        if preds.get("status") == "OK":
            self.assertGreater(report.get("fold_count", 0), 0)

    # -------------------------------------------------------------------------
    # 20. walk-forward evaluation
    # -------------------------------------------------------------------------
    def test_20_walk_forward_evaluation(self):
        _build_dataset(n=40)
        report = run_forecast_evaluation(horizon_hours=1, min_train_samples=30, hours_lookback=168)
        self.assertEqual(report["status"], "OK")
        self.assertGreater(report["fold_count"], 0)

    # -------------------------------------------------------------------------
    # 21. no leakage
    # -------------------------------------------------------------------------
    def test_21_no_leakage(self):
        now = datetime.now()
        # 30 training snapshots
        for i in range(30):
            ts = now - timedelta(hours=35 - i)
            _seed_snapshot(ts, "UP")
        # Target snapshot
        target_ts = now - timedelta(hours=2)
        target_id = _seed_snapshot(target_ts, "UP")
        session = _test_get_session()
        target = session.query(AnalysisSnapshot).filter(AnalysisSnapshot.id == target_id).first()
        f1 = generate_forecast(target, horizon_hours=1, abstention_threshold=0.0)
        train_count_1 = f1.provenance.get("training_samples", 0)
        # Future snapshot (should NOT affect training)
        future_ts = now - timedelta(hours=1)
        _seed_snapshot(future_ts, "DOWN", features=_make_features("DOWN"))
        session.refresh(target)
        f2 = generate_forecast(target, horizon_hours=1, abstention_threshold=0.0)
        train_count_2 = f2.provenance.get("training_samples", 0)
        session.close()
        self.assertEqual(train_count_1, train_count_2)

    # -------------------------------------------------------------------------
    # 22. calibration metric
    # -------------------------------------------------------------------------
    def test_22_calibration_metric(self):
        _build_dataset(n=40)
        report = run_forecast_evaluation(horizon_hours=1, min_train_samples=30, hours_lookback=168)
        m = report["model_results"]["logistic_regression"]["metrics"]
        self.assertIn("brier_score", m)

    # -------------------------------------------------------------------------
    # 23. confusion matrix
    # -------------------------------------------------------------------------
    def test_23_confusion_matrix(self):
        _build_dataset(n=40)
        report = run_forecast_evaluation(horizon_hours=1, min_train_samples=30, hours_lookback=168)
        m = report["model_results"]["logistic_regression"]["metrics"]
        self.assertIn("confusion_matrix", m)

    # -------------------------------------------------------------------------
    # 24. baseline comparison
    # -------------------------------------------------------------------------
    def test_24_baseline_comparison(self):
        _build_dataset(n=40)
        report = run_forecast_evaluation(horizon_hours=1, min_train_samples=30, hours_lookback=168)
        comp = report.get("comparison", {})
        self.assertIn("best_baseline", comp)
        self.assertIn("best_learned", comp)

    # -------------------------------------------------------------------------
    # 25. regime context
    # -------------------------------------------------------------------------
    def test_25_regime_context(self):
        _build_dataset(n=40)
        target = _get_latest_snapshot()
        forecast = generate_forecast(target, horizon_hours=1)
        self.assertIsNotNone(forecast.regime_state)

    # -------------------------------------------------------------------------
    # 26. regime-conditioned evaluation
    # -------------------------------------------------------------------------
    def test_26_regime_conditioned_evaluation(self):
        _build_dataset(n=40)
        report = run_forecast_evaluation(horizon_hours=1, min_train_samples=30, hours_lookback=168)
        rb = report["model_results"]["logistic_regression"].get("regime_breakdown", {})
        self.assertGreater(len(rb), 0)

    # -------------------------------------------------------------------------
    # 27. C.8 compatibility
    # -------------------------------------------------------------------------
    def test_27_c8_compatibility(self):
        from intelligence.features import FEATURE_SCHEMA_VERSION as C8_VER
        self.assertEqual(C8_VER, "1")

    # -------------------------------------------------------------------------
    # 28. C.12 compatibility
    # -------------------------------------------------------------------------
    def test_28_c12_compatibility(self):
        from intelligence.dataset import DATASET_SCHEMA_VERSION as C12_VER
        self.assertEqual(C12_VER, "1")

    # -------------------------------------------------------------------------
    # 29. C.13 compatibility
    # -------------------------------------------------------------------------
    def test_29_c13_compatibility(self):
        from analysis.snapshot_builder import build_analysis_snapshot
        self.assertTrue(callable(build_analysis_snapshot))

    # -------------------------------------------------------------------------
    # 30. C.14A compatibility
    # -------------------------------------------------------------------------
    def test_30_c14a_compatibility(self):
        from intelligence.candles import DEFAULT_TIMEFRAME
        self.assertEqual(DEFAULT_TIMEFRAME, "30m")

    # -------------------------------------------------------------------------
    # 31. no decision generation
    # -------------------------------------------------------------------------
    def test_31_no_decision_generation(self):
        _build_dataset(n=40)
        target = _get_latest_snapshot()
        forecast = generate_forecast(target, horizon_hours=1)
        s = str(asdict(forecast)).upper()
        self.assertNotIn("'BUY'", s)
        self.assertNotIn("'SELL'", s)
        self.assertNotIn("RECOMMENDED_ACTION", s)

    # -------------------------------------------------------------------------
    # 32. historical safety
    # -------------------------------------------------------------------------
    def test_32_historical_safety(self):
        now = datetime.now()
        labels = ["UP", "DOWN", "FLAT"]
        for i in range(30):
            ts = now - timedelta(hours=35 - i)
            _seed_snapshot(ts, labels[i % 3])
        target_ts = now - timedelta(hours=2)
        target_id = _seed_snapshot(target_ts, "UP")
        session = _test_get_session()
        target = session.query(AnalysisSnapshot).filter(AnalysisSnapshot.id == target_id).first()
        forecast = generate_forecast(target, horizon_hours=1)
        train_end = forecast.provenance.get("training_end")
        session.close()
        self.assertIsNotNone(train_end)
        if train_end:
            self.assertLess(datetime.fromisoformat(train_end), target_ts)

    # -------------------------------------------------------------------------
    # 33. deterministic contract validation
    # -------------------------------------------------------------------------
    def test_33_contract_validation(self):
        valid = {
            "status": "OK",
            "forecast": "UP",
            "probabilities": {"UP": 0.7, "NEUTRAL": 0.2, "DOWN": 0.1},
            "confidence": 0.7,
            "horizon_hours": 1,
            "model_version": "lr_v1",
            "feature_schema_version": "1",
            "label_schema_version": "1",
            "regime_state": "NORMAL",
            "provenance": {"snapshot_id": 1},
        }
        ok, errs = validate_forecast_result(valid)
        self.assertTrue(ok, errs)

        invalid = copy.deepcopy(valid)
        invalid["probabilities"] = {"UP": 0.5, "NEUTRAL": 0.5, "DOWN": 0.5}
        ok2, errs2 = validate_forecast_result(invalid)
        self.assertFalse(ok2)

    # -------------------------------------------------------------------------
    # 34. regression
    # -------------------------------------------------------------------------
    def test_34_regression(self):
        import analysis.outcome_evaluator
        import analysis.evidence_package
        import intelligence.market_intelligence
        import intelligence.read_model
        import intelligence.read_model_integration
        import intelligence.candles
        import intelligence.forecast_contract
        import intelligence.forecast_features
        import intelligence.forecast_engine

    # -------------------------------------------------------------------------
    # 35. compileall
    # -------------------------------------------------------------------------
    def test_35_compileall(self):
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
    suite = loader.loadTestsFromTestCase(TestC14B)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print(f"\n{'=' * 55}")
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print(f"C.14B KPI RESULT: {passed}/{result.testsRun} PASS")
    print(f"TARGET: 35/35 PASS")
    print(f"{'=' * 55}")
    sys.exit(0 if result.wasSuccessful() else 1)
