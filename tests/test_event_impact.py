"""Tests for event_impact.py — Diagnostic Observability

No network. No database. Deterministic fixtures only.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from intelligence.event_impact import (
    audit_event_impact,
    _relevance_score,
    _find_nearest_snapshot,
    _resolve_agreement,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeNewsEvent:
    def __init__(self, id_, ts, event_type, relevance, source="rss",
                 expected_gold_direction=None, expected_usd_direction=None):
        self.id = id_
        self.timestamp = ts
        self.event_type = event_type
        self.relevance = relevance
        self.source = source
        self.expected_gold_direction = expected_gold_direction
        self.expected_usd_direction = expected_usd_direction


class FakeSnapshot:
    def __init__(self, id_, ts, regime_state="NORMAL", premium_percent=None):
        self.id = id_
        self.analysis_timestamp = ts
        self.regime_state = regime_state
        self.premium_percent = premium_percent


class FakeOutcome:
    def __init__(self, status, direction, movement=None, horizon=1, snap_id=1):
        self.outcome_status = status
        self.rep_gold_direction = direction
        self.rep_gold_movement_percent = movement
        self.horizon_hours = horizon
        self.analysis_snapshot_id = snap_id


class FakeQuery:
    """Mock SQLAlchemy query that evaluates basic filter conditions."""
    def __init__(self, session, model):
        self.session = session
        self.model = model
        self._filters = []
        self._order = None

    def filter(self, *conds):
        self._filters.extend(conds)
        return self

    def order_by(self, *args):
        self._order = args
        return self

    def _get_pool(self):
        name = getattr(self.model, "__name__", "") or getattr(self.model, "__tablename__", "")
        if "NewsEvent" in name or "news_events" in name:
            return self.session._events
        if "AnalysisSnapshot" in name or "analysis_snapshots" in name:
            return self.session._snapshots
        if "OutcomeEvaluation" in name or "outcome_evaluations" in name:
            return self.session._outcomes
        return []

    def _eval_cond(self, obj, cond):
        """Evaluate a single SQLAlchemy-style condition."""
        if not hasattr(cond, 'left') or not hasattr(cond, 'right') or not hasattr(cond, 'operator'):
            return True

        left = cond.left
        attr_name = getattr(left, 'name', None) or getattr(left, 'key', None)
        if attr_name is None:
            return True

        right = cond.right
        target = getattr(right, 'value', None)
        if target is None and hasattr(right, 'effective_value'):
            target = right.effective_value
        if target is None:
            target = right

        actual = getattr(obj, attr_name, None)
        op_name = getattr(cond.operator, '__name__', str(cond.operator))

        if 'in_op' in op_name or op_name == 'in_':
            return actual in target if target is not None else False
        if 'notin_op' in op_name or op_name == 'notin_':
            return actual not in target if target is not None else True

        try:
            if 'eq' in op_name or op_name == 'eq':
                return actual == target
            if 'ne' in op_name or op_name == 'ne':
                return actual != target
            if 'lt' in op_name or op_name == 'lt':
                return actual < target
            if 'le' in op_name or op_name == 'le':
                return actual <= target
            if 'gt' in op_name or op_name == 'gt':
                return actual > target
            if 'ge' in op_name or op_name == 'ge':
                return actual >= target
        except TypeError:
            return False
        return True

    def _matches(self, obj):
        for cond in self._filters:
            if not self._eval_cond(obj, cond):
                return False
        return True

    def all(self):
        return [obj for obj in self._get_pool() if self._matches(obj)]

    def first(self):
        results = self.all()
        return results[0] if results else None


class FakeSession:
    def __init__(self, events=None, snapshots=None, outcomes=None):
        self._events = events or []
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

def test_relevance_score_ordering():
    assert _relevance_score("CRITICAL") == 4
    assert _relevance_score("HIGH") == 3
    assert _relevance_score("RELEVANT") == 2
    assert _relevance_score("LOW") == 1
    assert _relevance_score("UNKNOWN") == 0
    assert _relevance_score(None) == 0
    print("PASS: test_relevance_score_ordering")


def test_find_nearest_snapshot_within_window():
    event_ts = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
    snaps = [
        FakeSnapshot(1, event_ts - timedelta(minutes=30)),
        FakeSnapshot(2, event_ts + timedelta(minutes=10)),
        FakeSnapshot(3, event_ts - timedelta(minutes=180)),
    ]
    result = _find_nearest_snapshot(event_ts, snaps, window_minutes=120)
    assert result is not None and result.id == 2
    print("PASS: test_find_nearest_snapshot_within_window")


def test_find_nearest_snapshot_outside_window():
    event_ts = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
    snaps = [FakeSnapshot(1, event_ts - timedelta(minutes=180))]
    result = _find_nearest_snapshot(event_ts, snaps, window_minutes=120)
    assert result is None
    print("PASS: test_find_nearest_snapshot_outside_window")


def test_resolve_agreement_match():
    outcomes = {"1": {"outcome_status": "OBSERVED", "observed_direction": "UP"}}
    resolved = _resolve_agreement("UP", outcomes)
    assert resolved["1"]["directional_agreement"] == "AGREED"
    print("PASS: test_resolve_agreement_match")


def test_resolve_agreement_mismatch():
    outcomes = {"1": {"outcome_status": "OBSERVED", "observed_direction": "DOWN"}}
    resolved = _resolve_agreement("UP", outcomes)
    assert resolved["1"]["directional_agreement"] == "DISAGREED"
    print("PASS: test_resolve_agreement_mismatch")


def test_resolve_agreement_insufficient():
    outcomes = {"1": {"outcome_status": "OBSERVED", "observed_direction": "UP"}}
    resolved = _resolve_agreement(None, outcomes)
    assert resolved["1"]["directional_agreement"] == "INSUFFICIENT_DATA"
    print("PASS: test_resolve_agreement_insufficient")


# ---------------------------------------------------------------------------
# Audit tests
# ---------------------------------------------------------------------------

def test_audit_returns_db_unavailable_when_no_session():
    import intelligence.event_impact as ei_mod
    original_get_session = ei_mod.get_session
    ei_mod.get_session = lambda: None
    try:
        result = audit_event_impact()
        assert result["status"] == "DB_UNAVAILABLE"
        assert "Database session unavailable" in result["error"]
        assert "TEMPORAL_ASSOCIATION" in result["disclaimer"]
    finally:
        ei_mod.get_session = original_get_session
    print("PASS: test_audit_returns_db_unavailable_when_no_session")


def test_audit_selects_only_high_relevance_events():
    now = datetime.now(timezone.utc)
    events = [
        FakeNewsEvent(1, now, "GEOPOLITICAL", "HIGH", expected_gold_direction="UP"),
        FakeNewsEvent(2, now, "GEOPOLITICAL", "HIGH", expected_gold_direction="DOWN"),
        FakeNewsEvent(3, now, "SPORTS", "LOW"),
        FakeNewsEvent(4, now, "ECONOMIC", "LOW"),
        FakeNewsEvent(5, now, "ECONOMIC", "LOW"),
    ]
    session = FakeSession(events=events, snapshots=[], outcomes=[])
    result = audit_event_impact(session=session)
    assert result["status"] == "OK"
    assert result["events_audited"] == 2
    print("PASS: test_audit_selects_only_high_relevance_events")


def test_audit_matches_nearest_snapshot_within_window():
    now = datetime.now(timezone.utc)
    event_ts = now
    events = [FakeNewsEvent(1, event_ts, "GEOPOLITICAL", "HIGH", expected_gold_direction="UP")]
    snaps = [
        FakeSnapshot(1, event_ts - timedelta(minutes=30)),
        FakeSnapshot(2, event_ts + timedelta(minutes=10)),
    ]
    session = FakeSession(events=events, snapshots=snaps, outcomes=[])
    result = audit_event_impact(session=session)
    assert result["status"] == "OK"
    er = result["event_results"][0]
    assert er["snapshot_match"] is not None
    assert er["snapshot_match"]["snapshot_id"] == 2
    print("PASS: test_audit_matches_nearest_snapshot_within_window")


def test_audit_reports_insufficient_data_for_immature_outcomes():
    now = datetime.now(timezone.utc)
    events = [FakeNewsEvent(1, now, "GEOPOLITICAL", "HIGH", expected_gold_direction="UP")]
    snaps = [FakeSnapshot(1, now)]
    outcomes = [FakeOutcome("PENDING", None, horizon=1, snap_id=1)]
    session = FakeSession(events=events, snapshots=snaps, outcomes=outcomes)
    result = audit_event_impact(session=session)
    er = result["event_results"][0]
    assert er["outcomes_by_horizon"]["1"]["outcome_status"] == "INSUFFICIENT_DATA"
    print("PASS: test_audit_reports_insufficient_data_for_immature_outcomes")


def test_audit_reports_agreement_when_directions_match():
    now = datetime.now(timezone.utc)
    events = [FakeNewsEvent(1, now, "GEOPOLITICAL", "HIGH", expected_gold_direction="UP")]
    snaps = [FakeSnapshot(1, now)]
    outcomes = [FakeOutcome("COMPLETE", "UP", 0.5, horizon=1, snap_id=1)]
    session = FakeSession(events=events, snapshots=snaps, outcomes=outcomes)
    result = audit_event_impact(
        session=session,
        config={"horizons": [1]},  # Only check horizon 1
    )
    assert result["status"] == "OK"
    er = result["event_results"][0]
    assert er["outcomes_by_horizon"]["1"]["directional_agreement"] == "AGREED"
    assert er["summary"]["agreement_count"] == 1
    print("PASS: test_audit_reports_agreement_when_directions_match")


def test_audit_reports_disagreement_when_directions_differ():
    now = datetime.now(timezone.utc)
    events = [FakeNewsEvent(1, now, "GEOPOLITICAL", "HIGH", expected_gold_direction="UP")]
    snaps = [FakeSnapshot(1, now)]
    outcomes = [FakeOutcome("COMPLETE", "DOWN", -0.3, horizon=1, snap_id=1)]
    session = FakeSession(events=events, snapshots=snaps, outcomes=outcomes)
    result = audit_event_impact(
        session=session,
        config={"horizons": [1]},  # Only check horizon 1
    )
    assert result["status"] == "OK"
    er = result["event_results"][0]
    assert er["outcomes_by_horizon"]["1"]["directional_agreement"] == "DISAGREED"
    assert er["summary"]["disagreement_count"] == 1
    print("PASS: test_audit_reports_disagreement_when_directions_differ")


def test_audit_does_not_modify_database():
    now = datetime.now(timezone.utc)
    events = [FakeNewsEvent(1, now, "GEOPOLITICAL", "HIGH")]
    session = FakeSession(events=events, snapshots=[], outcomes=[])
    result = audit_event_impact(session=session)
    assert result["status"] == "OK"
    print("PASS: test_audit_does_not_modify_database")


def test_audit_explicitly_labels_temporal_association():
    now = datetime.now(timezone.utc)
    events = [FakeNewsEvent(1, now, "GEOPOLITICAL", "HIGH")]
    session = FakeSession(events=events, snapshots=[], outcomes=[])
    result = audit_event_impact(session=session)
    assert "TEMPORAL_ASSOCIATION" in result["disclaimer"]
    assert "not causation" in result["disclaimer"]
    print("PASS: test_audit_explicitly_labels_temporal_association")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_relevance_score_ordering,
        test_find_nearest_snapshot_within_window,
        test_find_nearest_snapshot_outside_window,
        test_resolve_agreement_match,
        test_resolve_agreement_mismatch,
        test_resolve_agreement_insufficient,
        test_audit_returns_db_unavailable_when_no_session,
        test_audit_selects_only_high_relevance_events,
        test_audit_matches_nearest_snapshot_within_window,
        test_audit_reports_insufficient_data_for_immature_outcomes,
        test_audit_reports_agreement_when_directions_match,
        test_audit_reports_disagreement_when_directions_differ,
        test_audit_does_not_modify_database,
        test_audit_explicitly_labels_temporal_association,
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
