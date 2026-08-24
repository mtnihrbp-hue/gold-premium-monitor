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


class FakeQuery:
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

    def all(self):
        # Robust matching: check class name or table name
        name = getattr(self.model, "__name__", "")
        tablename = getattr(self.model, "__tablename__", "")
        if name == "NewsEvent" or tablename == "news_events":
            return self.session._events
        if name == "AnalysisSnapshot" or tablename == "analysis_snapshots":
            return self.session._snapshots
        if name == "OutcomeEvaluation" or tablename == "outcome_evaluations":
            return self.session._outcomes
        return []

    def first(self):
        results = self.all()
        return results[0] if results else None


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------

def test_relevance_score_ordering():
    """Relevance scores must follow CRITICAL > HIGH > RELEVANT > LOW > UNKNOWN."""
    assert _relevance_score("CRITICAL") == 4
    assert _relevance_score("HIGH") == 3
    assert _relevance_score("RELEVANT") == 2
    assert _relevance_score("LOW") == 1
    assert _relevance_score("UNKNOWN") == 0
    assert _relevance_score(None) == 0
    print("PASS: test_relevance_score_ordering")


def test_find_nearest_snapshot_within_window():
    """Find closest snapshot within temporal window."""
    event_ts = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
    snaps = [
        FakeSnapshot(1, event_ts - timedelta(minutes=30)),
        FakeSnapshot(2, event_ts + timedelta(minutes=10)),
        FakeSnapshot(3, event_ts - timedelta(minutes=180)),  # outside window
    ]
    result = _find_nearest_snapshot(event_ts, snaps, window_minutes=120)
    assert result is not None, "Expected a snapshot match"
    assert result.id == 2, f"Expected id=2 (closest), got id={result.id}"
    print("PASS: test_find_nearest_snapshot_within_window")


def test_find_nearest_snapshot_outside_window():
    """No snapshot within window returns None."""
    event_ts = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
    snaps = [FakeSnapshot(1, event_ts - timedelta(minutes=180))]
    result = _find_nearest_snapshot(event_ts, snaps, window_minutes=120)
    assert result is None, f"Expected None, got {result}"
    print("PASS: test_find_nearest_snapshot_outside_window")


def test_resolve_agreement_match():
    """classified=UP, observed=UP → AGREED."""
    outcomes = {"1": {"outcome_status": "OBSERVED", "observed_direction": "UP"}}
    resolved = _resolve_agreement("UP", outcomes)
    assert resolved["1"]["directional_agreement"] == "AGREED", f"Got {resolved['1']['directional_agreement']}"
    print("PASS: test_resolve_agreement_match")


def test_resolve_agreement_mismatch():
    """classified=UP, observed=DOWN → DISAGREED."""
    outcomes = {"1": {"outcome_status": "OBSERVED", "observed_direction": "DOWN"}}
    resolved = _resolve_agreement("UP", outcomes)
    assert resolved["1"]["directional_agreement"] == "DISAGREED", f"Got {resolved['1']['directional_agreement']}"
    print("PASS: test_resolve_agreement_mismatch")


def test_resolve_agreement_insufficient():
    """Missing classified direction → INSUFFICIENT_DATA."""
    outcomes = {"1": {"outcome_status": "OBSERVED", "observed_direction": "UP"}}
    resolved = _resolve_agreement(None, outcomes)
    assert resolved["1"]["directional_agreement"] == "INSUFFICIENT_DATA", f"Got {resolved['1']['directional_agreement']}"
    print("PASS: test_resolve_agreement_insufficient")


# ---------------------------------------------------------------------------
# Audit tests
# ---------------------------------------------------------------------------

def test_audit_returns_db_unavailable_when_no_session():
    """When session is None and get_session returns None, audit returns DB_UNAVAILABLE."""
    import intelligence.event_impact as ei_mod
    original_get_session = ei_mod.get_session

    def mock_get_session():
        return None

    try:
        ei_mod.get_session = mock_get_session
        result = audit_event_impact()
        assert result["status"] == "DB_UNAVAILABLE", f"Got {result['status']}"
        assert "Database session unavailable" in result["error"]
        assert "TEMPORAL_ASSOCIATION" in result["disclaimer"]
    finally:
        ei_mod.get_session = original_get_session
    print("PASS: test_audit_returns_db_unavailable_when_no_session")


def test_audit_selects_only_high_relevance_events():
    """5 events: 2 HIGH, 3 LOW, min_relevance=HIGH → audits 2."""
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
    assert result["status"] == "OK", f"Got {result['status']}"
    assert result["events_audited"] == 2, f"Audited={result['events_audited']}"
    print("PASS: test_audit_selects_only_high_relevance_events")


def test_audit_matches_nearest_snapshot_within_window():
    """Event at T, snapshots at T-30min and T+10min, window=60min → matches T+10min."""
    now = datetime.now(timezone.utc)
    event_ts = now
    events = [FakeNewsEvent(1, event_ts, "GEOPOLITICAL", "HIGH", expected_gold_direction="UP")]
    snaps = [
        FakeSnapshot(1, event_ts - timedelta(minutes=30)),
        FakeSnapshot(2, event_ts + timedelta(minutes=10)),
    ]
    session = FakeSession(events=events, snapshots=snaps, outcomes=[])
    result = audit_event_impact(session=session)
    assert result["status"] == "OK", f"Got {result['status']}"
    er = result["event_results"][0]
    assert er["snapshot_match"] is not None, "Expected snapshot match"
    assert er["snapshot_match"]["snapshot_id"] == 2, f"Matched id={er['snapshot_match']['snapshot_id']}"
    print("PASS: test_audit_matches_nearest_snapshot_within_window")


def test_audit_reports_insufficient_data_for_immature_outcomes():
    """Snapshot exists but outcome_status=PENDING → INSUFFICIENT_DATA."""
    now = datetime.now(timezone.utc)
    events = [FakeNewsEvent(1, now, "GEOPOLITICAL", "HIGH", expected_gold_direction="UP")]
    snaps = [FakeSnapshot(1, now)]
    outcomes = [FakeOutcome("PENDING", None, horizon=1, snap_id=1)]
    session = FakeSession(events=events, snapshots=snaps, outcomes=outcomes)
    result = audit_event_impact(session=session)
    er = result["event_results"][0]
    assert er["outcomes_by_horizon"]["1"]["outcome_status"] == "INSUFFICIENT_DATA",         f"Got {er['outcomes_by_horizon']['1']['outcome_status']}"
    print("PASS: test_audit_reports_insufficient_data_for_immature_outcomes")


def test_audit_reports_agreement_when_directions_match():
    """classified=UP, observed=UP → AGREED."""
    now = datetime.now(timezone.utc)
    events = [FakeNewsEvent(1, now, "GEOPOLITICAL", "HIGH", expected_gold_direction="UP")]
    snaps = [FakeSnapshot(1, now)]
    outcomes = [FakeOutcome("COMPLETE", "UP", 0.5, horizon=1, snap_id=1)]
    session = FakeSession(events=events, snapshots=snaps, outcomes=outcomes)
    result = audit_event_impact(session=session)
    assert result["status"] == "OK", f"Got {result['status']}"
    er = result["event_results"][0]
    actual = er["outcomes_by_horizon"]["1"]["directional_agreement"]
    assert actual == "AGREED", f"Expected AGREED, got {actual}"
    assert er["summary"]["agreement_count"] == 1, f"Agreements={er['summary']['agreement_count']}"
    print("PASS: test_audit_reports_agreement_when_directions_match")


def test_audit_reports_disagreement_when_directions_differ():
    """classified=UP, observed=DOWN → DISAGREED."""
    now = datetime.now(timezone.utc)
    events = [FakeNewsEvent(1, now, "GEOPOLITICAL", "HIGH", expected_gold_direction="UP")]
    snaps = [FakeSnapshot(1, now)]
    outcomes = [FakeOutcome("COMPLETE", "DOWN", -0.3, horizon=1, snap_id=1)]
    session = FakeSession(events=events, snapshots=snaps, outcomes=outcomes)
    result = audit_event_impact(session=session)
    assert result["status"] == "OK", f"Got {result['status']}"
    er = result["event_results"][0]
    actual = er["outcomes_by_horizon"]["1"]["directional_agreement"]
    assert actual == "DISAGREED", f"Expected DISAGREED, got {actual}"
    assert er["summary"]["disagreement_count"] == 1, f"Disagreements={er['summary']['disagreement_count']}"
    print("PASS: test_audit_reports_disagreement_when_directions_differ")


def test_audit_does_not_modify_database():
    """Audit is read-only. No INSERT/UPDATE/DELETE."""
    now = datetime.now(timezone.utc)
    events = [FakeNewsEvent(1, now, "GEOPOLITICAL", "HIGH")]
    session = FakeSession(events=events, snapshots=[], outcomes=[])
    result = audit_event_impact(session=session)
    assert result["status"] == "OK", f"Got {result['status']}"
    print("PASS: test_audit_does_not_modify_database")


def test_audit_explicitly_labels_temporal_association():
    """Result contains disclaimer that this is temporal association, not causation."""
    now = datetime.now(timezone.utc)
    events = [FakeNewsEvent(1, now, "GEOPOLITICAL", "HIGH")]
    session = FakeSession(events=events, snapshots=[], outcomes=[])
    result = audit_event_impact(session=session)
    assert "TEMPORAL_ASSOCIATION" in result["disclaimer"], f"Disclaimer missing: {result.get('disclaimer')}"
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
