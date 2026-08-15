"""Unit tests for SP-B.1 Historical Intelligence Foundation.

No database. No network. No ML.
Mocked MarketState-like objects only.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from intelligence.historical import (
    calculate_similarity,
    rank_similar_states,
    build_historical_comparison,
    SimilarStateResult,
    HistoricalComparison,
)


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

class MockSnapshot:
    def __init__(self, premium_percent):
        self.premium_percent = premium_percent


class MockState:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        if not hasattr(self, "snapshot"):
            self.snapshot = None


# ---------------------------------------------------------------------------
# 1. calculate_similarity — exact categorical match
# ---------------------------------------------------------------------------

def test_similarity_exact_match():
    """Same valuation, momentum, structure + premium within tolerance → match."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
        premium_direction="DISCOUNT_WIDENING", conflict_state="SUPPORTIVE",
        candidate_decision="BUY", final_decision="BUY",
        timestamp=datetime.now() - timedelta(days=5),
        platforms_below_fair=2, platforms_above_fair=1, platform_spread=5000,
        snapshot=MockSnapshot(premium_percent=-3.2),
    )
    result = calculate_similarity(ref, candidate, premium_tolerance=1.0)
    assert result is not None, "Expected match"
    assert result.premium_distance == 0.2
    assert result.valuation == "CHEAP"
    assert result.final_decision == "BUY"
    print("PASS: test_similarity_exact_match")


def test_similarity_valuation_mismatch():
    """Different valuation → no match."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="FAIR", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
        snapshot=MockSnapshot(premium_percent=-3.0),
    )
    result = calculate_similarity(ref, candidate)
    assert result is None, "Expected no match due to valuation mismatch"
    print("PASS: test_similarity_valuation_mismatch")


def test_similarity_momentum_mismatch():
    """Different momentum → no match."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="CHEAP", momentum_state="WEAKENING", structure_state="DISCOUNT_DOMINANT",
        snapshot=MockSnapshot(premium_percent=-3.0),
    )
    result = calculate_similarity(ref, candidate)
    assert result is None, "Expected no match due to momentum mismatch"
    print("PASS: test_similarity_momentum_mismatch")


def test_similarity_structure_mismatch():
    """Different structure → no match."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="MIXED",
        snapshot=MockSnapshot(premium_percent=-3.0),
    )
    result = calculate_similarity(ref, candidate)
    assert result is None, "Expected no match due to structure mismatch"
    print("PASS: test_similarity_structure_mismatch")


def test_similarity_premium_out_of_tolerance():
    """Premium difference exceeds tolerance → no match."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
        snapshot=MockSnapshot(premium_percent=-5.5),
    )
    result = calculate_similarity(ref, candidate, premium_tolerance=1.0)
    assert result is None, "Expected no match due to premium out of tolerance (2.5% > 1.0%)"
    print("PASS: test_similarity_premium_out_of_tolerance")


def test_similarity_premium_at_boundary():
    """Premium exactly at tolerance boundary → match."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
        snapshot=MockSnapshot(premium_percent=-4.0),
    )
    result = calculate_similarity(ref, candidate, premium_tolerance=1.0)
    assert result is not None, "Expected match at exact boundary"
    assert result.premium_distance == 1.0
    print("PASS: test_similarity_premium_at_boundary")


# ---------------------------------------------------------------------------
# 2. rank_similar_states
# ---------------------------------------------------------------------------

def test_rank_by_premium_distance():
    """Closer premium first."""
    s1 = SimilarStateResult(
        state_id=1, snapshot_id=1, timestamp=datetime.now(),
        premium_percent=-3.0, valuation="CHEAP", momentum="IMPROVING",
        premium_direction="DISCOUNT_WIDENING", structure="DISCOUNT_DOMINANT",
        conflict="SUPPORTIVE", candidate_decision="BUY", final_decision="BUY",
        premium_distance=0.5, days_ago=10,
    )
    s2 = SimilarStateResult(
        state_id=2, snapshot_id=2, timestamp=datetime.now(),
        premium_percent=-3.5, valuation="CHEAP", momentum="IMPROVING",
        premium_direction="DISCOUNT_WIDENING", structure="DISCOUNT_DOMINANT",
        conflict="SUPPORTIVE", candidate_decision="BUY", final_decision="BUY",
        premium_distance=0.2, days_ago=20,
    )
    ranked = rank_similar_states([s1, s2])
    assert ranked[0].state_id == 2, "Closer premium should be first"
    assert ranked[1].state_id == 1
    print("PASS: test_rank_by_premium_distance")


def test_rank_tiebreaker_recency():
    """Same premium distance → more recent first."""
    s1 = SimilarStateResult(
        state_id=1, snapshot_id=1, timestamp=datetime.now() - timedelta(days=5),
        premium_percent=-3.0, valuation="CHEAP", momentum="IMPROVING",
        premium_direction="DISCOUNT_WIDENING", structure="DISCOUNT_DOMINANT",
        conflict="SUPPORTIVE", candidate_decision="BUY", final_decision="BUY",
        premium_distance=0.5, days_ago=5,
    )
    s2 = SimilarStateResult(
        state_id=2, snapshot_id=2, timestamp=datetime.now() - timedelta(days=2),
        premium_percent=-3.0, valuation="CHEAP", momentum="IMPROVING",
        premium_direction="DISCOUNT_WIDENING", structure="DISCOUNT_DOMINANT",
        conflict="SUPPORTIVE", candidate_decision="BUY", final_decision="BUY",
        premium_distance=0.5, days_ago=2,
    )
    ranked = rank_similar_states([s1, s2])
    assert ranked[0].state_id == 2, "More recent should win tiebreaker"
    print("PASS: test_rank_tiebreaker_recency")


# ---------------------------------------------------------------------------
# 3. build_historical_comparison
# ---------------------------------------------------------------------------

def test_comparison_finds_matches():
    """Multiple candidates, some match."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    candidates = [
        MockState(
            id=1, snapshot_id=10,
            valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
            snapshot=MockSnapshot(premium_percent=-3.1),
            timestamp=datetime.now() - timedelta(days=5),
        ),
        MockState(
            id=2, snapshot_id=11,
            valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
            snapshot=MockSnapshot(premium_percent=-3.5),
            timestamp=datetime.now() - timedelta(days=3),
        ),
        MockState(
            id=3, snapshot_id=12,
            valuation_state="FAIR", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
            snapshot=MockSnapshot(premium_percent=-3.0),
            timestamp=datetime.now() - timedelta(days=1),
        ),
    ]
    comparison = build_historical_comparison(ref, candidates, config={"premium_tolerance": 1.0, "max_results": 20})
    assert comparison.match_count == 2, f"Expected 2 matches, got {comparison.match_count}"
    assert comparison.similar_states[0].premium_distance <= comparison.similar_states[1].premium_distance
    print("PASS: test_comparison_finds_matches")


def test_comparison_no_matches():
    """No candidates match → empty result."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    candidates = [
        MockState(
            id=1, snapshot_id=10,
            valuation_state="FAIR", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
            snapshot=MockSnapshot(premium_percent=-3.0),
        ),
    ]
    comparison = build_historical_comparison(ref, candidates)
    assert comparison.match_count == 0
    assert not comparison.has_sufficient_data
    print("PASS: test_comparison_no_matches")


def test_comparison_respects_max_results():
    """max_results limits output."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    candidates = []
    for i in range(10):
        candidates.append(MockState(
            id=i, snapshot_id=i,
            valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
            snapshot=MockSnapshot(premium_percent=-3.0 - i * 0.05),
            timestamp=datetime.now() - timedelta(days=i),
        ))
    comparison = build_historical_comparison(ref, candidates, config={"premium_tolerance": 2.0, "max_results": 5})
    assert comparison.match_count == 5, f"Expected 5, got {comparison.match_count}"
    print("PASS: test_comparison_respects_max_results")


def test_comparison_sufficient_data_threshold():
    """3+ matches = sufficient data."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    candidates = [
        MockState(
            id=i, snapshot_id=i,
            valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
            snapshot=MockSnapshot(premium_percent=-3.0 - i * 0.1),
            timestamp=datetime.now() - timedelta(days=i),
        )
        for i in range(3)
    ]
    comparison = build_historical_comparison(ref, candidates)
    assert comparison.has_sufficient_data
    print("PASS: test_comparison_sufficient_data_threshold")


def test_comparison_insufficient_data():
    """<3 matches = insufficient data."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    candidates = [
        MockState(
            id=1, snapshot_id=1,
            valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
            snapshot=MockSnapshot(premium_percent=-3.1),
            timestamp=datetime.now() - timedelta(days=1),
        ),
    ]
    comparison = build_historical_comparison(ref, candidates)
    assert not comparison.has_sufficient_data
    print("PASS: test_comparison_insufficient_data")


# ---------------------------------------------------------------------------
# 4. HistoricalComparison.to_text
# ---------------------------------------------------------------------------

def test_text_output_contains_reference():
    """Text output must reference the input state."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    candidates = [
        MockState(
            id=1, snapshot_id=1,
            valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
            snapshot=MockSnapshot(premium_percent=-3.1),
            timestamp=datetime.now() - timedelta(days=5),
            platforms_below_fair=2, platforms_above_fair=1, platform_spread=5000,
        ),
    ]
    comparison = build_historical_comparison(ref, candidates)
    text = comparison.to_text()
    assert "CHEAP" in text
    assert "IMPROVING" in text
    assert "DISCOUNT_DOMINANT" in text
    assert "-3.00%" in text or "-3.0%" in text
    print("PASS: test_text_output_contains_reference")


def test_text_output_no_matches():
    """No matches → clear message."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    comparison = build_historical_comparison(ref, [])
    text = comparison.to_text()
    assert "No comparable" in text
    print("PASS: test_text_output_no_matches")


def test_text_output_insufficient_warning():
    """<3 matches → caution note."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    candidates = [
        MockState(
            id=1, snapshot_id=1,
            valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
            snapshot=MockSnapshot(premium_percent=-3.1),
            timestamp=datetime.now() - timedelta(days=5),
        ),
    ]
    comparison = build_historical_comparison(ref, candidates)
    text = comparison.to_text()
    assert "Limited sample" in text or "caution" in text.lower()
    print("PASS: test_text_output_insufficient_warning")


def test_text_output_no_prediction():
    """Text must never contain prediction language."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    candidates = [
        MockState(
            id=1, snapshot_id=1,
            valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
            snapshot=MockSnapshot(premium_percent=-3.1),
            timestamp=datetime.now() - timedelta(days=5),
        ),
    ]
    comparison = build_historical_comparison(ref, candidates)
    text = comparison.to_text().lower()
    forbidden = ["predict", "forecast", "will rise", "will fall", "expect", "outcome"]
    for word in forbidden:
        assert word not in text, f"Forbidden word '{word}' found in output"
    print("PASS: test_text_output_no_prediction")


# ---------------------------------------------------------------------------
# 5. Edge cases
# ---------------------------------------------------------------------------

def test_similarity_missing_premium():
    """Candidate with no premium data → no match."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
        snapshot=None,
    )
    result = calculate_similarity(ref, candidate)
    assert result is None, "Expected no match when premium unavailable"
    print("PASS: test_similarity_missing_premium")


def test_similarity_none_reference_premium():
    """Reference with None premium → no match."""
    ref = {"premium": None, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
        snapshot=MockSnapshot(premium_percent=-3.0),
    )
    result = calculate_similarity(ref, candidate)
    assert result is None, "Expected no match when reference premium is None"
    print("PASS: test_similarity_none_reference_premium")


def test_rank_empty_list():
    """Ranking empty list → empty list."""
    ranked = rank_similar_states([])
    assert ranked == []
    print("PASS: test_rank_empty_list")


def test_comparison_empty_candidates():
    """Empty candidates → empty comparison with correct reference."""
    ref = {"premium": -2.5, "valuation": "FAIR", "momentum": "NEUTRAL", "structure": "MIXED"}
    comparison = build_historical_comparison(ref, [])
    assert comparison.reference_valuation == "FAIR"
    assert comparison.reference_momentum == "NEUTRAL"
    assert comparison.reference_structure == "MIXED"
    assert comparison.match_count == 0
    print("PASS: test_comparison_empty_candidates")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_similarity_exact_match,
        test_similarity_valuation_mismatch,
        test_similarity_momentum_mismatch,
        test_similarity_structure_mismatch,
        test_similarity_premium_out_of_tolerance,
        test_similarity_premium_at_boundary,
        test_rank_by_premium_distance,
        test_rank_tiebreaker_recency,
        test_comparison_finds_matches,
        test_comparison_no_matches,
        test_comparison_respects_max_results,
        test_comparison_sufficient_data_threshold,
        test_comparison_insufficient_data,
        test_text_output_contains_reference,
        test_text_output_no_matches,
        test_text_output_insufficient_warning,
        test_text_output_no_prediction,
        test_similarity_missing_premium,
        test_similarity_none_reference_premium,
        test_rank_empty_list,
        test_comparison_empty_candidates,
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
