"""Forecast Engine — PRE-SP-C.14B

Empirical evaluation of predictive signal.
Expanding-window walk-forward. Baseline-first. No decision authority.
"""

import copy
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    precision_recall_fscore_support,
    confusion_matrix,
)

from database.connection import get_session
from database.models import AnalysisSnapshot, OutcomeEvaluation
from intelligence.forecast_contract import ForecastResult, validate_forecast_result
from intelligence.forecast_features import build_forecast_feature_vector

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
VALID_LABELS = ["UP", "NEUTRAL", "DOWN"]
C5_TO_C14B = {"UP": "UP", "DOWN": "DOWN", "FLAT": "NEUTRAL", "INSUFFICIENT_DATA": None}


# -----------------------------------------------------------------------------
# Label extraction
# -----------------------------------------------------------------------------
def _extract_label(ev: OutcomeEvaluation) -> Optional[str]:
    """Map C.5/C.12 rep_gold_direction to C.14B canonical label."""
    direction = getattr(ev, "rep_gold_direction", None)
    if direction is None:
        return None
    return C5_TO_C14B.get(direction)


# -----------------------------------------------------------------------------
# Data readiness
# -----------------------------------------------------------------------------
def measure_data_readiness(
    horizon_hours: int = 1,
    hours_lookback: int = 2160,
    min_per_class: int = 3,
    min_train_samples: int = 30,
) -> Dict[str, Any]:
    """Measure dataset readiness before any model fitting.

    Returns:
        readiness dict with counts, distributions, and a go/no-go flag.
    """
    session = get_session()
    if session is None:
        return {"status": "DB_UNAVAILABLE", "sufficient": False}

    try:
        since = datetime.now() - timedelta(hours=hours_lookback)
        snaps = (
            session.query(AnalysisSnapshot)
            .filter(AnalysisSnapshot.analysis_timestamp >= since)
            .filter(AnalysisSnapshot.features_json.isnot(None))
            .order_by(AnalysisSnapshot.analysis_timestamp.asc())
            .all()
        )

        records = []
        class_counts = {"UP": 0, "DOWN": 0, "NEUTRAL": 0}
        regime_counts = {}

        for snap in snaps:
            ev = (
                session.query(OutcomeEvaluation)
                .filter(
                    OutcomeEvaluation.analysis_snapshot_id == snap.id,
                    OutcomeEvaluation.horizon_hours == horizon_hours,
                    OutcomeEvaluation.outcome_status == "COMPLETE",
                )
                .first()
            )
            if ev is None:
                continue

            label = _extract_label(ev)
            if label is None:
                continue

            # Feature vector must be buildable
            fv = build_forecast_feature_vector(snap, config={"include_c8": True})
            if fv is None or not fv.get("feature_names"):
                continue

            records.append({
                "snapshot_id": snap.id,
                "timestamp": snap.analysis_timestamp,
                "regime": snap.regime_state or "UNKNOWN",
                "label": label,
            })
            class_counts[label] = class_counts.get(label, 0) + 1
            regime_counts[snap.regime_state or "UNKNOWN"] = regime_counts.get(snap.regime_state or "UNKNOWN", 0) + 1

        n = len(records)
        min_class = min(class_counts.values()) if class_counts else 0
        sufficient = (
            n >= min_train_samples + 1  # at least one fold
            and min_class >= min_per_class
            and len(set(r["timestamp"].date() for r in records)) >= 2
        )

        return {
            "status": "OK" if sufficient else "INSUFFICIENT_DATA",
            "sufficient": sufficient,
            "total_records": n,
            "class_distribution": class_counts,
            "regime_coverage": regime_counts,
            "temporal_coverage": {
                "start": records[0]["timestamp"].isoformat() if records else None,
                "end": records[-1]["timestamp"].isoformat() if records else None,
                "distinct_days": len(set(r["timestamp"].date() for r in records)),
            },
            "min_train_samples": min_train_samples,
            "horizon_hours": horizon_hours,
        }
    except Exception as e:
        return {"status": f"ERROR: {e}", "sufficient": False}
    finally:
        session.close()


# -----------------------------------------------------------------------------
# Baseline predictors
# -----------------------------------------------------------------------------
def _majority_predict(train_records: List[dict]) -> Optional[str]:
    if not train_records:
        return None
    labels = [r["label"] for r in train_records]
    return max(set(labels), key=labels.count)


def _persistence_predict(prev_label: Optional[str]) -> Optional[str]:
    return prev_label


def _c8_deterministic_predict(features_json: Optional[dict]) -> Optional[str]:
    """Deterministic baseline using ONLY existing C.8 semantics.

    No invented thresholds. Point-in-time safe.
    """
    if not isinstance(features_json, dict):
        return None
    momentum = features_json.get("momentum", {})
    direction = momentum.get("premium_latest_direction", "UNKNOWN")
    if direction == "UP":
        return "UP"
    elif direction == "DOWN":
        return "DOWN"
    elif direction == "FLAT":
        return "NEUTRAL"
    return "NEUTRAL"


# -----------------------------------------------------------------------------
# Model factories
# -----------------------------------------------------------------------------
def _logistic_regression_factory():
    return LogisticRegression(
        multi_class="multinomial",
        solver="lbfgs",
        max_iter=1000,
        random_state=42,
    )


def _decision_tree_factory():
    return DecisionTreeClassifier(
        max_depth=5,
        min_samples_leaf=5,
        random_state=42,
    )


# -----------------------------------------------------------------------------
# Metrics
# -----------------------------------------------------------------------------
def _multiclass_brier_score(y_true: List[str], y_prob: List[List[float]], classes: List[str]) -> float:
    """Multiclass Brier score. Lower is better."""
    n = len(y_true)
    if n == 0:
        return float("nan")
    class_idx = {c: i for i, c in enumerate(classes)}
    score = 0.0
    for yt, yp in zip(y_true, y_prob):
        for i, cls in enumerate(classes):
            o = 1.0 if yt == cls else 0.0
            score += (yp[i] - o) ** 2
    return score / n


def _compute_metrics(predictions: List[dict], classes: List[str]) -> Dict[str, Any]:
    """Compute evaluation metrics for a set of predictions."""
    ok_preds = [p for p in predictions if p["status"] == "OK"]
    total = len(predictions)

    if not ok_preds:
        return {
            "status": "INSUFFICIENT_DATA",
            "reason": "no non-abstained predictions",
            "sample_count": 0,
            "coverage": 0.0,
            "abstention_rate": 1.0 if total > 0 else 0.0,
        }

    y_true = [p["actual"] for p in ok_preds]
    y_pred = [p["predicted"] for p in ok_preds]

    acc = accuracy_score(y_true, y_pred)
    bal_acc = balanced_accuracy_score(y_true, y_pred)
    prec, rec, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=classes, zero_division=0
    )
    cm = confusion_matrix(y_true, y_pred, labels=classes)

    # Probability matrix for Brier
    y_prob = []
    for p in ok_preds:
        prob_vec = [p["probabilities"].get(c, 0.0) for c in classes]
        y_prob.append(prob_vec)

    brier = _multiclass_brier_score(y_true, y_prob, classes)

    abstained = len([p for p in predictions if p["status"] == "ABSTAIN"])

    return {
        "status": "OK",
        "accuracy": round(float(acc), 4),
        "balanced_accuracy": round(float(bal_acc), 4),
        "precision": {c: round(float(p), 4) for c, p in zip(classes, prec)},
        "recall": {c: round(float(r), 4) for c, r in zip(classes, rec)},
        "macro_f1": round(float(sum(f1) / len(f1)), 4) if len(f1) > 0 else None,
        "confusion_matrix": cm.tolist(),
        "brier_score": round(float(brier), 6),
        "coverage": round(len(ok_preds) / total, 4) if total > 0 else 0.0,
        "abstention_rate": round(abstained / total, 4) if total > 0 else 0.0,
        "sample_count": len(ok_preds),
    }


def _regime_breakdown(predictions: List[dict], classes: List[str]) -> Dict[str, Any]:
    """Per-regime metrics. Minimum 5 samples per regime."""
    regimes: Dict[str, List[dict]] = {}
    for p in predictions:
        reg = p.get("regime", "UNKNOWN")
        regimes.setdefault(reg, []).append(p)

    result = {}
    for reg, preds in regimes.items():
        if len(preds) < 5:
            result[reg] = {"status": "INSUFFICIENT_DATA", "sample_count": len(preds)}
        else:
            result[reg] = _compute_metrics(preds, classes)
    return result


# -----------------------------------------------------------------------------
# Expanding-window walk-forward
# -----------------------------------------------------------------------------
def _load_records(
    horizon_hours: int,
    feature_config: Optional[dict],
    hours_lookback: int,
) -> List[dict]:
    """Load chronological records with features and labels."""
    session = get_session()
    if session is None:
        return []

    try:
        since = datetime.now() - timedelta(hours=hours_lookback)
        snaps = (
            session.query(AnalysisSnapshot)
            .filter(AnalysisSnapshot.analysis_timestamp >= since)
            .filter(AnalysisSnapshot.features_json.isnot(None))
            .order_by(AnalysisSnapshot.analysis_timestamp.asc())
            .all()
        )

        records = []
        for snap in snaps:
            ev = (
                session.query(OutcomeEvaluation)
                .filter(
                    OutcomeEvaluation.analysis_snapshot_id == snap.id,
                    OutcomeEvaluation.horizon_hours == horizon_hours,
                    OutcomeEvaluation.outcome_status == "COMPLETE",
                )
                .first()
            )
            if ev is None:
                continue

            label = _extract_label(ev)
            if label is None:
                continue

            fv = build_forecast_feature_vector(snap, config=feature_config or {"include_c8": True})
            if fv is None:
                continue

            records.append({
                "snapshot_id": snap.id,
                "timestamp": snap.analysis_timestamp,
                "regime": snap.regime_state or "UNKNOWN",
                "label": label,
                "features": np.array(fv["feature_values"], dtype=float),
                "feature_names": fv["feature_names"],
                "features_json": snap.features_json,
            })

        return records
    finally:
        session.close()


def _walk_forward(
    records: List[dict],
    min_train: int,
    step: int,
    abstention_threshold: float,
) -> Dict[str, List[dict]]:
    """Expanding-window walk-forward evaluation.

    Returns:
        dict mapping model_name -> list of prediction dicts.
    """
    n = len(records)
    if n < min_train + 1:
        return {}

    # Model specs
    specs = {
        "majority_baseline": {"type": "baseline"},
        "persistence_baseline": {"type": "baseline"},
        "c8_deterministic_baseline": {"type": "baseline"},
        "logistic_regression": {"type": "learned", "factory": _logistic_regression_factory, "scale": True},
        "decision_tree": {"type": "learned", "factory": _decision_tree_factory, "scale": False},
    }

    all_predictions: Dict[str, List[dict]] = {name: [] for name in specs}

    prev_label = None

    for i in range(min_train, n, step):
        train_recs = records[0:i]
        test_recs = records[i:min(i + step, n)]

        X_train = np.array([r["features"] for r in train_recs])
        y_train = [r["label"] for r in train_recs]

        # Imputation fitted on training data only
        imputer = SimpleImputer(strategy="median")
        X_train_imp = imputer.fit_transform(X_train)

        for model_name, spec in specs.items():
            for test_rec in test_recs:
                pred = None
                probs = {"UP": 0.0, "NEUTRAL": 0.0, "DOWN": 0.0}
                confidence = None
                status = "OK"

                if spec["type"] == "baseline":
                    if model_name == "majority_baseline":
                        pred = _majority_predict(train_recs)
                        if pred:
                            probs = {d: (1.0 if d == pred else 0.0) for d in VALID_LABELS}
                            confidence = 1.0
                    elif model_name == "persistence_baseline":
                        pred = _persistence_predict(prev_label)
                        if pred:
                            probs = {d: (1.0 if d == pred else 0.0) for d in VALID_LABELS}
                            confidence = 1.0
                        else:
                            status = "INSUFFICIENT_DATA"
                    elif model_name == "c8_deterministic_baseline":
                        pred = _c8_deterministic_predict(test_rec["features_json"])
                        if pred:
                            probs = {d: (1.0 if d == pred else 0.0) for d in VALID_LABELS}
                            confidence = 1.0
                        else:
                            status = "INSUFFICIENT_DATA"

                else:  # learned
                    model = spec["factory"]()
                    scaler = StandardScaler() if spec.get("scale") else None

                    X_train_final = X_train_imp
                    if scaler:
                        X_train_final = scaler.fit_transform(X_train_imp)

                    # Skip if not all classes present in training
                    train_classes = set(y_train)
                    if len(train_classes) < 2:
                        status = "INSUFFICIENT_DATA"
                    else:
                        try:
                            model.fit(X_train_final, y_train)
                            classes = list(model.classes_)

                            X_test = np.array([test_rec["features"]])
                            X_test_imp = imputer.transform(X_test)
                            X_test_final = X_test_imp
                            if scaler:
                                X_test_final = scaler.transform(X_test_imp)

                            raw_probs = model.predict_proba(X_test_final)[0]
                            probs = {cls: 0.0 for cls in VALID_LABELS}
                            for cls, p in zip(classes, raw_probs):
                                probs[cls] = float(p)

                            # Normalize to handle missing classes
                            total = sum(probs.values())
                            if total > 0:
                                probs = {k: v / total for k, v in probs.items()}

                            confidence = max(probs.values())
                            if confidence < abstention_threshold:
                                status = "ABSTAIN"
                            else:
                                pred = max(probs, key=probs.get)

                        except Exception as e:
                            status = "ERROR"
                            pred = None

                all_predictions[model_name].append({
                    "fold": i,
                    "snapshot_id": test_rec["snapshot_id"],
                    "timestamp": test_rec["timestamp"],
                    "regime": test_rec["regime"],
                    "actual": test_rec["label"],
                    "predicted": pred,
                    "status": status,
                    "probabilities": probs,
                    "confidence": confidence,
                })

        # Update persistence tracker
        for test_rec in test_recs:
            prev_label = test_rec["label"]

    return all_predictions


# -----------------------------------------------------------------------------
# Public API: Evaluation
# -----------------------------------------------------------------------------
def run_forecast_evaluation(
    horizon_hours: int = 1,
    feature_config: Optional[dict] = None,
    min_train_samples: int = 30,
    step: int = 1,
    abstention_threshold: float = 0.5,
    hours_lookback: int = 2160,
) -> Dict[str, Any]:
    """Run expanding-window walk-forward forecast evaluation.

    Args:
        horizon_hours: target horizon (1, 6, or 24)
        feature_config: feature vector configuration
        min_train_samples: minimum training records before first fold
        step: fold step size
        abstention_threshold: max probability threshold for abstention
        hours_lookback: data query window

    Returns:
        evaluation report dict.
    """
    # Data readiness
    readiness = measure_data_readiness(
        horizon_hours=horizon_hours,
        hours_lookback=hours_lookback,
        min_train_samples=min_train_samples,
    )

    if not readiness.get("sufficient"):
        return {
            "status": "INSUFFICIENT_DATA",
            "horizon_hours": horizon_hours,
            "data_readiness": readiness,
            "model_results": {},
            "comparison": {},
            "provenance": {
                "evaluated_at": datetime.now().isoformat(),
                "feature_schema_version": "1",
                "label_schema_version": "1",
            },
        }

    records = _load_records(horizon_hours, feature_config, hours_lookback)
    if len(records) < min_train_samples + 1:
        return {
            "status": "INSUFFICIENT_DATA",
            "horizon_hours": horizon_hours,
            "data_readiness": readiness,
            "model_results": {},
            "comparison": {},
            "provenance": {
                "evaluated_at": datetime.now().isoformat(),
                "feature_schema_version": "1",
                "label_schema_version": "1",
            },
        }

    predictions_by_model = _walk_forward(
        records, min_train_samples, step, abstention_threshold
    )

    model_results = {}
    for model_name, preds in predictions_by_model.items():
        model_results[model_name] = {
            "metrics": _compute_metrics(preds, VALID_LABELS),
            "regime_breakdown": _regime_breakdown(preds, VALID_LABELS),
        }

    # Comparison: does any learned model beat all baselines on balanced_accuracy?
    baseline_names = ["majority_baseline", "persistence_baseline", "c8_deterministic_baseline"]
    learned_names = ["logistic_regression", "decision_tree"]

    best_baseline = max(
        [(n, model_results[n]["metrics"].get("balanced_accuracy", 0.0)) for n in baseline_names],
        key=lambda x: x[1],
    )
    best_learned = None
    for n in learned_names:
        if n in model_results and model_results[n]["metrics"].get("status") == "OK":
            score = model_results[n]["metrics"].get("balanced_accuracy", 0.0)
            if best_learned is None or score > best_learned[1]:
                best_learned = (n, score)

    beats = False
    if best_learned and best_learned[1] > best_baseline[1]:
        beats = True

    return {
        "status": "OK",
        "horizon_hours": horizon_hours,
        "data_readiness": readiness,
        "fold_count": len(predictions_by_model.get("logistic_regression", [])),
        "model_results": model_results,
        "comparison": {
            "best_baseline": best_baseline[0],
            "best_baseline_score": round(best_baseline[1], 4),
            "best_learned": best_learned[0] if best_learned else None,
            "best_learned_score": round(best_learned[1], 4) if best_learned else None,
            "beats_baseline": beats,
        },
        "provenance": {
            "evaluated_at": datetime.now().isoformat(),
            "feature_schema_version": "1",
            "label_schema_version": "1",
            "feature_config": feature_config or {"include_c8": True},
            "min_train_samples": min_train_samples,
            "step": step,
            "abstention_threshold": abstention_threshold,
        },
    }


# -----------------------------------------------------------------------------
# Public API: Operational forecast generation
# -----------------------------------------------------------------------------
def generate_forecast(
    snapshot,
    horizon_hours: int = 1,
    feature_config: Optional[dict] = None,
    model_name: str = "logistic_regression",
    abstention_threshold: float = 0.5,
) -> ForecastResult:
    """Generate a single forecast for a snapshot using all historical training data.

    Point-in-time safe: only uses snapshots strictly before the target snapshot.

    Args:
        snapshot: AnalysisSnapshot ORM object or compatible dict.
        horizon_hours: forecast horizon.
        feature_config: feature vector configuration.
        model_name: 'logistic_regression' or 'decision_tree'.
        abstention_threshold: abstention threshold.

    Returns:
        ForecastResult dataclass.
    """
    # Build feature vector for target snapshot
    fv = build_forecast_feature_vector(snapshot, config=feature_config or {"include_c8": True})
    if fv is None:
        return ForecastResult(
            status="INSUFFICIENT_DATA",
            forecast=None,
            probabilities={"UP": 0.0, "NEUTRAL": 0.0, "DOWN": 0.0},
            confidence=None,
            horizon_hours=horizon_hours,
            model_version="none",
            feature_schema_version="1",
            label_schema_version="1",
            regime_state=getattr(snapshot, "regime_state", None),
            provenance={
                "snapshot_id": getattr(snapshot, "id", None),
                "reason": "feature_vector_unavailable",
            },
        )

    # Load all historical records before this snapshot
    analysis_ts = getattr(snapshot, "analysis_timestamp", None)
    if analysis_ts is None:
        return ForecastResult(
            status="INSUFFICIENT_DATA",
            forecast=None,
            probabilities={"UP": 0.0, "NEUTRAL": 0.0, "DOWN": 0.0},
            confidence=None,
            horizon_hours=horizon_hours,
            model_version="none",
            feature_schema_version="1",
            label_schema_version="1",
            regime_state=getattr(snapshot, "regime_state", None),
            provenance={"reason": "missing_timestamp"},
        )

    session = get_session()
    if session is None:
        return ForecastResult(
            status="INSUFFICIENT_DATA",
            forecast=None,
            probabilities={"UP": 0.0, "NEUTRAL": 0.0, "DOWN": 0.0},
            confidence=None,
            horizon_hours=horizon_hours,
            model_version="none",
            feature_schema_version="1",
            label_schema_version="1",
            regime_state=getattr(snapshot, "regime_state", None),
            provenance={"reason": "db_unavailable"},
        )

    try:
        historical = (
            session.query(AnalysisSnapshot)
            .join(
                OutcomeEvaluation,
                AnalysisSnapshot.id == OutcomeEvaluation.analysis_snapshot_id,
            )
            .filter(
                OutcomeEvaluation.horizon_hours == horizon_hours,
                OutcomeEvaluation.outcome_status == "COMPLETE",
                OutcomeEvaluation.rep_gold_direction.in_(["UP", "DOWN", "FLAT"]),
                AnalysisSnapshot.analysis_timestamp < analysis_ts,
                AnalysisSnapshot.features_json.isnot(None),
            )
            .order_by(AnalysisSnapshot.analysis_timestamp.asc())
            .all()
        )

        train_recs = []
        for snap in historical:
            label = _extract_label(
                session.query(OutcomeEvaluation)
                .filter(
                    OutcomeEvaluation.analysis_snapshot_id == snap.id,
                    OutcomeEvaluation.horizon_hours == horizon_hours,
                )
                .first()
            )
            if label is None:
                continue
            snap_fv = build_forecast_feature_vector(snap, config=feature_config or {"include_c8": True})
            if snap_fv is None:
                continue
            train_recs.append({
                "features": np.array(snap_fv["feature_values"], dtype=float),
                "label": label,
                "timestamp": snap.analysis_timestamp.isoformat() if snap.analysis_timestamp else None,
            })

        if len(train_recs) < 10:
            return ForecastResult(
                status="INSUFFICIENT_DATA",
                forecast=None,
                probabilities={"UP": 0.0, "NEUTRAL": 0.0, "DOWN": 0.0},
                confidence=None,
                horizon_hours=horizon_hours,
                model_version=model_name,
                feature_schema_version="1",
                label_schema_version="1",
                regime_state=getattr(snapshot, "regime_state", None),
                provenance={
                    "snapshot_id": getattr(snapshot, "id", None),
                    "training_samples": len(train_recs),
                    "reason": "insufficient_training_data",
                },
            )

        X_train = np.array([r["features"] for r in train_recs])
        y_train = [r["label"] for r in train_recs]

        imputer = SimpleImputer(strategy="median")
        X_train_imp = imputer.fit_transform(X_train)

        if model_name == "logistic_regression":
            model = _logistic_regression_factory()
            scaler = StandardScaler()
            X_train_final = scaler.fit_transform(X_train_imp)
        elif model_name == "decision_tree":
            model = _decision_tree_factory()
            scaler = None
            X_train_final = X_train_imp
        else:
            return ForecastResult(
                status="INSUFFICIENT_DATA",
                forecast=None,
                probabilities={"UP": 0.0, "NEUTRAL": 0.0, "DOWN": 0.0},
                confidence=None,
                horizon_hours=horizon_hours,
                model_version="unknown",
                feature_schema_version="1",
                label_schema_version="1",
                regime_state=getattr(snapshot, "regime_state", None),
                provenance={"reason": "unknown_model"},
            )

        model.fit(X_train_final, y_train)
        classes = list(model.classes_)

        X_target = np.array([fv["feature_values"]], dtype=float)
        X_target_imp = imputer.transform(X_target)
        X_target_final = X_target_imp
        if scaler:
            X_target_final = scaler.transform(X_target_imp)

        raw_probs = model.predict_proba(X_target_final)[0]
        probs = {cls: 0.0 for cls in VALID_LABELS}
        for cls, p in zip(classes, raw_probs):
            probs[cls] = float(p)

        total = sum(probs.values())
        if total > 0:
            probs = {k: v / total for k, v in probs.items()}

        confidence = max(probs.values())
        if confidence < abstention_threshold:
            return ForecastResult(
                status="ABSTAIN",
                forecast=None,
                probabilities=probs,
                confidence=round(confidence, 6),
                horizon_hours=horizon_hours,
                model_version=model_name,
                feature_schema_version="1",
                label_schema_version="1",
                regime_state=getattr(snapshot, "regime_state", None),
                provenance={
                    "snapshot_id": getattr(snapshot, "id", None),
                    "training_samples": len(train_recs),
                    "abstention_threshold": abstention_threshold,
                },
            )

        forecast = max(probs, key=probs.get)

        return ForecastResult(
            status="OK",
            forecast=forecast,
            probabilities={k: round(v, 6) for k, v in probs.items()},
            confidence=round(confidence, 6),
            horizon_hours=horizon_hours,
            model_version=model_name,
            feature_schema_version="1",
            label_schema_version="1",
            regime_state=getattr(snapshot, "regime_state", None),
            provenance={
                "snapshot_id": getattr(snapshot, "id", None),
                "training_samples": len(train_recs),
                "training_start": train_recs[0].get("timestamp"),
                "training_end": train_recs[-1].get("timestamp"),
            },
        )

    except Exception as e:
        return ForecastResult(
            status="INSUFFICIENT_DATA",
            forecast=None,
            probabilities={"UP": 0.0, "NEUTRAL": 0.0, "DOWN": 0.0},
            confidence=None,
            horizon_hours=horizon_hours,
            model_version=model_name,
            feature_schema_version="1",
            label_schema_version="1",
            regime_state=getattr(snapshot, "regime_state", None),
            provenance={"reason": f"error: {e}"},
        )
    finally:
        session.close()
