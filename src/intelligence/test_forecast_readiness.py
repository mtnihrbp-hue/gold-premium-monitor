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
# Helpers
# ---------------------------------------------------------------------------

class FakeSnapshot:
    def __init__(self, ts, features_json=None):
        self.analysis_timestamp = ts
        self.features_json = features_json


class FakeOutcome:
    def __init__(self, status, direction, horizon):
        self.outcome_status = status
        self.rep_gold_direction = direction
        self.horizon_hours = horizon
        self.analysis_snapshot_id = 1


class FakeSession:
    """Minimal mock session for forecast readiness tests."""
    def __init__(self, snapshots=None, outcomes=None):
        self._snapshots = snapshots or []
        self._outcomes = outcomes or []
        self._closed = False

    def query(self, model):
        return FakeQuery(self, model)

    def close(self):
        self._closed = True


class FakeQuery:
    def __init__(self, session, model):
        self.session = session
        self.model = model
        self.filters = []
        self.joins = []

    def filter(self, *conds):
        self.filters.extend(conds)
        return self

    def join(self, *args):
        self.joins.extend(args)
        return self

    def order_by(self, *args):
        return self

    def all(self):
        if self.model.__name__ == "AnalysisSnapshot":
            return self.session._snapshots
        if self.model.__name__ == "OutcomeEvaluation":
            return self.session._outcomes
        return []

    def first(self):
        results = self.all()
        return results[0] if results else None


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------

def test_count_distinct_days():
    """Count unique calendar days from timestamps."""
    ts = [
        datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 20, 14, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 21, 9, 0, tzinfo=timezone.utc),
    ]
    assert _count_distinct_days(ts) == 2
    print("PASS: test_count_distinct_days")


def test_count_distinct_days_empty():
    """Empty list returns 0."""
    assert _count_distinct_days([]) == 0
    print("PASS: test_count_distinct_days_empty")


def test_estimated_days_zero_when_sufficient():
    """When current >= required, estimate is 0."""
    ts = [datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc)]
    result = _compute_estimated_days_to_readiness(15, 10, ts)
    assert result == 0.0
    print("PASS: test_estimated_days_zero_when_sufficient")


def test_estimated_days_none_when_insufficient_data():
    """When fewer than 2 timestamps, cannot estimate."""
    result = _compute_estimated_days_to_readiness(5, 10, [datetime.now(timezone.utc)])
    assert result is None
    print("PASS: test_estimated_days_none_when_insufficient_data")


def test_estimated_days_calculates_from_cadence():
    """Estimate derived from observed examples per hour."""
    ts = [
        datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 20, 14, 0, tzinfo=timezone.utc),
    ]  # 3 examples over 4 hours = 0.75 per hour
    # Need 10, have 3 → need 7 more → 7/0.75 = 9.33 hours → 0.39 days
    result = _compute_estimated_days_to_readiness(3, 10, ts)
    assert result is not None
    assert result > 0
    print("PASS: test_estimated_days_calculates_from_cadence")


# ---------------------------------------------------------------------------
# Audit tests
# ---------------------------------------------------------------------------

def test_audit_returns_db_unavailable_when_no_session():
    """When session is None and get_session returns None, audit returns DB_UNAVAILABLE."""
    import intelligence.forecast_readiness as fr_mod
    original_get_session = fr_mod.get_session

    def mock_get_session():
        return None

    try:
        fr_mod.get_session = mock_get_session
        result = audit_forecast_readiness()
        assert result["status"] == "DB_UNAVAILABLE"
        assert result["error"] == "Database session unavailable"
    finally:
        fr_mod.get_session = original_get_session
    print("PASS: test_audit_returns_db_unavailable_when_no_session")


def test_audit_counts_snapshots_correctly():
    """5 snapshots, 3 with features_json → counts must match."""
    snaps = [
        FakeSnapshot(datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc), {"f": 1}),
        FakeSnapshot(datetime(2026, 8, 20, 11, 0, tzinfo=timezone.utc), {"f": 2}),
        FakeSnapshot(datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc), {"f": 3}),
        FakeSnapshot(datetime(2026, 8, 20, 13, 0, tzinfo=timezone.utc), None),
        FakeSnapshot(datetime(2026, 8, 20, 14, 0, tzinfo=timezone.utc), None),
    ]
    session = FakeSession(snapshots=snaps, outcomes=[])
    result = audit_forecast_readiness(session=session)
    assert result["status"] == "OK"
    agg = result["aggregate"]
    assert agg["total_snapshots"] == 5
    assert agg["snapshots_with_features"] == 3
    assert agg["snapshots_without_features"] == 2
    print("PASS: test_audit_counts_snapshots_correctly")


def test_audit_reports_insufficient_training_examples():
    """3 usable examples, min_train_samples=10 → GATED with reason."""
    snaps = [
        FakeSnapshot(datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc), {"f": 1}),
    ]
    outcomes = [
        FakeOutcome("COMPLETE", "UP", 1),
        FakeOutcome("COMPLETE", "DOWN", 1),
        FakeOutcome("COMPLETE", "FLAT", 1),
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
    """5 usable examples: UP=5, DOWN=0, NEUTRAL=0 → GATED with class_imbalance reason."""
    snaps = [
        FakeSnapshot(datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc), {"f": 1}),
    ]
    outcomes = [
        FakeOutcome("COMPLETE", "UP", 1),
        FakeOutcome("COMPLETE", "UP", 1),
        FakeOutcome("COMPLETE", "UP", 1),
        FakeOutcome("COMPLETE", "UP", 1),
        FakeOutcome("COMPLETE", "UP", 1),
    ]
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
    """31 usable examples, balanced classes, 3 distinct days → OPEN."""
    snaps = [
        FakeSnapshot(datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc), {"f": 1}),
        FakeSnapshot(datetime(2026, 8, 19, 10, 0, tzinfo=timezone.utc), {"f": 2}),
        FakeSnapshot(datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc), {"f": 3}),
    ]
    outcomes = []
    for i in range(31):
        direction = ["UP", "DOWN", "FLAT"][i % 3]
        outcomes.append(FakeOutcome("COMPLETE", direction, 1))
    session = FakeSession(snapshots=snaps, outcomes=outcomes)
    result = audit_forecast_readiness(
        config={"min_train_samples": 10, "min_per_class": 3, "min_distinct_days": 2, "horizons_hours": [1]},
        session=session,
    )
    h1 = result["per_horizon"]["1"]
    assert h1["readiness_gate"] == "OPEN"
    assert len(h1["gate_reasons"]) == 0
    assert h1["usable_training_examples"] == 31
    print("PASS: test_audit_reports_open_gate_when_all_conditions_met")


def test_audit_does_not_modify_database():
    """Audit is read-only. No INSERT/UPDATE/DELETE."""
    snaps = [FakeSnapshot(datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc), {"f": 1})]
    session = FakeSession(snapshots=snaps, outcomes=[])
    # FakeSession has no add/commit/delete methods; if audit tried to write,
    # it would fail. The test passes because audit only queries.
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
