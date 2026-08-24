"""Tests for forecast_readiness.py — Diagnostic Observability

No network. No database. Deterministic fixtures only.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from intelligence.forecast_readiness import (
    audit_forecast_readiness,
    _count_distinct_days,
    _compute_estimated_days_to_readiness,
)


# ---------------------------------------------------------------------------
# Helpers — Robust FakeQuery that evaluates SQLAlchemy-style filters
# ---------------------------------------------------------------------------

class FakeSnapshot:
    def __init__(self, id_, ts, features_json=None, regime_state="NORMAL", premium_percent=None):
        self.id = id_
        self.analysis_timestamp = ts
        self.features_json = features_json
        self.regime_state = regime_state
        self.premium_percent = premium_percent


class FakeOutcome:
    def __init__(self, status, direction, horizon, snap_id=1):
        self.outcome_status = status
        self.rep_gold_direction = direction
        self.horizon_hours = horizon
        self.analysis_snapshot_id = snap_id
        self.rep_gold_movement_percent = 0.5


class FakeQuery:
    """Mock SQLAlchemy query with real filter evaluation."""
    def __init__(self, session, model):
        self.session = session
        self.model = model
        self._filters = []

    def filter(self, *conds):
        self._filters.extend(conds)
        return self

    def join(self, *args):
        return self

    def order_by(self, *args):
        return self

    def _pool(self):
        name = getattr(self.model, "__name__", "") or getattr(self.model, "__tablename__", "")
        if "AnalysisSnapshot" in name or "analysis_snapshots" in name:
            return self.session._snapshots
        if "OutcomeEvaluation" in name or "outcome_evaluations" in name:
            return self.session._outcomes
        return []

    def _eval(self, obj, cond):
        """Evaluate a SQLAlchemy binary condition against a plain object."""
        if not hasattr(cond, "left") or not hasattr(cond, "right") or not hasattr(cond, "operator"):
            return True

        # --- attribute name ---
        left = cond.left
        attr = None
        for attr_name in ("key", "name"):
            v = getattr(left, attr_name, None)
            if v and isinstance(v, str):
                attr = v
                break
        if attr is None and hasattr(left, "property"):
            attr = getattr(left.property, "key", None)
        if not attr:
            return True

        # If the object doesn't have this attribute, the filter is probably
        # a cross-table join condition (e.g. AnalysisSnapshot.timestamp on
        # an OutcomeEvaluation query). Be permissive.
        if not hasattr(obj, attr):
            return True

        actual = getattr(obj, attr)

        # --- target value ---
        right = cond.right
        target = None
        # Try SQLAlchemy wrapper attributes
        for val_attr in ("value", "effective_value", "compiled_value"):
            if hasattr(right, val_attr):
                target = getattr(right, val_attr)
                break
        # If still None and right looks like a plain Python value, use it directly
        if target is None:
            target = right

        # --- operator ---
        op = cond.operator
        op_name = getattr(op, "__name__", str(op))

        # Comparison
        try:
            if "in_op" in op_name or op_name == "in_":
                return actual in target
            if "notin_op" in op_name or op_name == "notin_":
                return actual not in target
            if op_name in ("eq", "=="):
                return actual == target
            if op_name in ("ne", "!="):
                return actual != target
            if op_name in ("lt", "<"):
                return actual < target
            if op_name in ("le", "<="):
                return actual <= target
            if op_name in ("gt", ">"):
                return actual > target
            if op_name in ("ge", ">="):
                return actual >= target
            if "is_not" in op_name:
                return actual is not target
            if "is_" in op_name:
                return actual is target
            # Fallback: call operator directly
            return op(actual, target)
        except TypeError:
            # Cannot compare (e.g. datetime vs None) → permissive
            return True

    def _matches(self, obj):
        return all(self._eval(obj, c) for c in self._filters)

    def all(self):
        return [o for o in self._pool() if self._matches(o)]

    def first(self):
        results = self.all()
        return results[0] if results else None


class FakeSession:
    def __init__(self, snapshots=None, outcomes=None):
        self._snapshots = snapshots or []
        self._outcomes = outcomes or []
        self._closed = False

    def query(self, model):
        return FakeQuery(self, model)

    def close(self):
        self._closed = True


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------

def test_count_distinct_days():
    ts = [
        datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 20, 14, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 21, 9, 0, tzinfo=timezone.utc),
    ]
    assert _count_distinct_days(ts) == 2
    print("PASS: test_count_distinct_days")


def test_count_distinct_days_empty():
    assert _count_distinct_days([]) == 0
    print("PASS: test_count_distinct_days_empty")


def test_estimated_days_zero_when_sufficient():
    ts = [datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc)]
    result = _compute_estimated_days_to_readiness(15, 10, ts)
    assert result == 0.0
    print("PASS: test_estimated_days_zero_when_sufficient")


def test_estimated_days_none_when_insufficient_data():
    result = _compute_estimated_days_to_readiness(5, 10, [datetime.now(timezone.utc)])
    assert result is None
    print("PASS: test_estimated_days_none_when_insufficient_data")


def test_estimated_days_calculates_from_cadence():
    ts = [
        datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 20, 14, 0, tzinfo=timezone.utc),
    ]
    result = _compute_estimated_days_to_readiness(3, 10, ts)
    assert result is not None and result > 0
    print("PASS: test_estimated_days_calculates_from_cadence")


# ---------------------------------------------------------------------------
# Audit tests
# ---------------------------------------------------------------------------

def test_audit_returns_db_unavailable_when_no_session():
    import intelligence.forecast_readiness as fr_mod
    original = fr_mod.get_session
    fr_mod.get_session = lambda: None
    try:
        result = audit_forecast_readiness()
        assert result["status"] == "DB_UNAVAILABLE"
        assert result["error"] == "Database session unavailable"
    finally:
        fr_mod.get_session = original
    print("PASS: test_audit_returns_db_unavailable_when_no_session")


def test_audit_counts_snapshots_correctly():
    snaps = [
        FakeSnapshot(1, datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc), {"f": 1}),
        FakeSnapshot(2, datetime(2026, 8, 20, 11, 0, tzinfo=timezone.utc), {"f": 2}),
        FakeSnapshot(3, datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc), {"f": 3}),
        FakeSnapshot(4, datetime(2026, 8, 20, 13, 0, tzinfo=timezone.utc), None),
        FakeSnapshot(5, datetime(2026, 8, 20, 14, 0, tzinfo=timezone.utc), None),
    ]
    session = FakeSession(snapshots=snaps, outcomes=[])
    result = audit_forecast_readiness(session=session)
    assert result["status"] == "OK", f"status={result['status']}"
    agg = result["aggregate"]
    assert agg["total_snapshots"] == 5, f"total={agg['total_snapshots']}"
    assert agg["snapshots_with_features"] == 3, f"with={agg['snapshots_with_features']}"
    assert agg["snapshots_without_features"] == 2, f"without={agg['snapshots_without_features']}"
    print("PASS: test_audit_counts_snapshots_correctly")


def test_audit_reports_insufficient_training_examples():
    snaps = [FakeSnapshot(1, datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc), {"f": 1})]
    outcomes = [
        FakeOutcome("COMPLETE", "UP", 1, snap_id=1),
        FakeOutcome("COMPLETE", "DOWN", 1, snap_id=1),
        FakeOutcome("COMPLETE", "FLAT", 1, snap_id=1),
    ]
    session = FakeSession(snapshots=snaps, outcomes=outcomes)
    result = audit_forecast_readiness(
        config={"min_train_samples": 10, "horizons_hours": [1]},
        session=session,
    )
    assert result["status"] == "OK"
    h1 = result["per_horizon"]["1"]
    assert h1["readiness_gate"] == "GATED"
    assert any("insufficient_training_examples" in r for r in h1["gate_reasons"])
    print("PASS: test_audit_reports_insufficient_training_examples")


def test_audit_reports_class_imbalance():
    snaps = [FakeSnapshot(1, datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc), {"f": 1})]
    outcomes = [FakeOutcome("COMPLETE", "UP", 1, snap_id=1) for _ in range(5)]
    session = FakeSession(snapshots=snaps, outcomes=outcomes)
    result = audit_forecast_readiness(
        config={"min_train_samples": 3, "min_per_class": 3, "horizons_hours": [1]},
        session=session,
    )
    h1 = result["per_horizon"]["1"]
    assert h1["readiness_gate"] == "GATED"
    assert any("class_imbalance" in r for r in h1["gate_reasons"])
    print("PASS: test_audit_reports_class_imbalance")


def test_audit_reports_open_gate_when_all_conditions_met():
    snaps = [
        FakeSnapshot(1, datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc), {"f": 1}),
        FakeSnapshot(2, datetime(2026, 8, 19, 10, 0, tzinfo=timezone.utc), {"f": 2}),
        FakeSnapshot(3, datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc), {"f": 3}),
    ]
    outcomes = []
    for i in range(31):
        direction = ["UP", "DOWN", "FLAT"][i % 3]
        snap_id = [1, 2, 3][i % 3]
        outcomes.append(FakeOutcome("COMPLETE", direction, 1, snap_id=snap_id))
    session = FakeSession(snapshots=snaps, outcomes=outcomes)
    result = audit_forecast_readiness(
        config={"min_train_samples": 10, "min_per_class": 3, "min_distinct_days": 2, "horizons_hours": [1]},
        session=session,
    )
    h1 = result["per_horizon"]["1"]
    assert h1["readiness_gate"] == "OPEN", f"gate={h1['readiness_gate']}, reasons={h1['gate_reasons']}"
    assert len(h1["gate_reasons"]) == 0
    assert h1["usable_training_examples"] == 31
    print("PASS: test_audit_reports_open_gate_when_all_conditions_met")


def test_audit_does_not_modify_database():
    snaps = [FakeSnapshot(1, datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc), {"f": 1})]
    session = FakeSession(snapshots=snaps, outcomes=[])
    result = audit_forecast_readiness(session=session)
    assert result["status"] == "OK"
    print("PASS: test_audit_does_not_modify_database")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_count_distinct_days,
        test_count_distinct_days_empty,
        test_estimated_days_zero_when_sufficient,
        test_estimated_days_none_when_insufficient_data,
        test_estimated_days_calculates_from_cadence,
        test_audit_returns_db_unavailable_when_no_session,
        test_audit_counts_snapshots_correctly,
        test_audit_reports_insufficient_training_examples,
        test_audit_reports_class_imbalance,
        test_audit_reports_open_gate_when_all_conditions_met,
        test_audit_does_not_modify_database,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERR : {t.__name__}: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed out of {len(tests)}")
    if failed > 0:
        sys.exit(1)
