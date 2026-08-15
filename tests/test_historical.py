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
    _soft_match,
    _is_known,
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
# 0. Soft-match primitives
# ---------------------------------------------------------------------------

def test_soft_match_both_known_equal():
    """Both known and equal → match."""
    assert _soft_match("RISING", "RISING")
    print("PASS: test_soft_match_both_known_equal")


def test_soft_match_both_known_different():
    """Both known and different → no match."""
    assert not _soft_match("RISING", "FALLING")
    print("PASS: test_soft_match_both_known_different")


def test_soft_match_one_unknown():
    """One unknown → no blocking."""
    assert _soft_match("RISING", "UNKNOWN")
    assert _soft_match("UNKNOWN", "RISING")
    assert _soft_match("RISING", None)
    assert _soft_match(None, "RISING")
    assert _soft_match("RISING", "")
    print("PASS: test_soft_match_one_unknown")


def test_soft_match_both_unknown():
    """Both unknown → no blocking."""
    assert _soft_match("UNKNOWN", "UNKNOWN")
    assert _soft_match(None, None)
    print("PASS: test_soft_match_both_unknown")


# ---------------------------------------------------------------------------
# 1. Primary hard requirements
# ---------------------------------------------------------------------------

def test_similarity_exact_match():
    """Same valuation, momentum + premium within tolerance → match."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING"}
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
    """Different valuation → no match (hard requirement)."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING"}
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="FAIR", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
        snapshot=MockSnapshot(premium_percent=-3.0),
    )
    result = calculate_similarity(ref, candidate)
    assert result is None, "Expected no match due to valuation mismatch"
    print("PASS: test_similarity_valuation_mismatch")


def test_similarity_momentum_mismatch():
    """Different momentum → no match (hard requirement)."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING"}
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="CHEAP", momentum_state="WEAKENING", structure_state="DISCOUNT_DOMINANT",
        snapshot=MockSnapshot(premium_percent=-3.0),
    )
    result = calculate_similarity(ref, candidate)
    assert result is None, "Expected no match due to momentum mismatch"
    print("PASS: test_similarity_momentum_mismatch")


def test_similarity_premium_out_of_tolerance():
    """Premium difference exceeds tolerance → no match (hard requirement)."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING"}
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
        snapshot=MockSnapshot(premium_percent=-5.5),
    )
    result = calculate_similarity(ref, candidate, premium_tolerance=1.0)
    assert result is None, "Expected no match due to premium out of tolerance"
    print("PASS: test_similarity_premium_out_of_tolerance")


def test_similarity_premium_at_boundary():
    """Premium exactly at tolerance boundary → match."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING"}
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
# 2. Secondary soft requirements — structure
# ---------------------------------------------------------------------------

def test_similarity_structure_both_known_mismatch():
    """Both structure known and different → no match (soft filter)."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="MIXED",
        snapshot=MockSnapshot(premium_percent=-3.0),
    )
    result = calculate_similarity(ref, candidate)
    assert result is None, "Expected no match when both structures known and different"
    print("PASS: test_similarity_structure_both_known_mismatch")


def test_similarity_structure_unknown_no_block():
    """Structure UNKNOWN on candidate → no blocking."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="CHEAP", momentum_state="IMPROVING",
        snapshot=MockSnapshot(premium_percent=-3.0),
        # no structure_state attribute → UNKNOWN
    )
    result = calculate_similarity(ref, candidate)
    assert result is not None, "Expected match when candidate structure is unknown"
    print("PASS: test_similarity_structure_unknown_no_block")


def test_similarity_structure_reference_unknown_no_block():
    """Structure UNKNOWN on reference → no blocking."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "UNKNOWN"}
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="MIXED",
        snapshot=MockSnapshot(premium_percent=-3.0),
    )
    result = calculate_similarity(ref, candidate)
    assert result is not None, "Expected match when reference structure is unknown"
    print("PASS: test_similarity_structure_reference_unknown_no_block")


def test_similarity_structure_both_known_match():
    """Both structure known and same → match."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
        snapshot=MockSnapshot(premium_percent=-3.0),
    )
    result = calculate_similarity(ref, candidate)
    assert result is not None, "Expected match when structures match"
    print("PASS: test_similarity_structure_both_known_match")


# ---------------------------------------------------------------------------
# 3. Secondary soft requirements — USD/IRR direction
# ---------------------------------------------------------------------------

def test_similarity_usd_match():
    """Matching USD direction when both known → match."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "usd_direction": "RISING"}
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
        usd_direction="RISING",
        snapshot=MockSnapshot(premium_percent=-3.0),
    )
    result = calculate_similarity(ref, candidate)
    assert result is not None, "Expected match with matching USD direction"
    assert result.usd_direction == "RISING"
    print("PASS: test_similarity_usd_match")


def test_similarity_usd_mismatch_rejects():
    """Different USD direction when both known → no match."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "usd_direction": "RISING"}
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
        usd_direction="FALLING",
        snapshot=MockSnapshot(premium_percent=-3.0),
    )
    result = calculate_similarity(ref, candidate)
    assert result is None, "Expected no match when USD directions differ"
    print("PASS: test_similarity_usd_mismatch_rejects")


def test_similarity_usd_unknown_no_block():
    """UNKNOWN USD direction → no fabricated blocking."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "usd_direction": "RISING"}
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
        # no usd_direction → UNKNOWN
        snapshot=MockSnapshot(premium_percent=-3.0),
    )
    result = calculate_similarity(ref, candidate)
    assert result is not None, "Expected match when candidate USD direction is unknown"
    print("PASS: test_similarity_usd_unknown_no_block")


def test_similarity_usd_reference_unknown_no_block():
    """Reference USD direction UNKNOWN → no blocking."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "usd_direction": "UNKNOWN"}
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
        usd_direction="FALLING",
        snapshot=MockSnapshot(premium_percent=-3.0),
    )
    result = calculate_similarity(ref, candidate)
    assert result is not None, "Expected match when reference USD direction is unknown"
    print("PASS: test_similarity_usd_reference_unknown_no_block")


# ---------------------------------------------------------------------------
# 4. Secondary soft requirements — XAU/USD direction
# ---------------------------------------------------------------------------

def test_similarity_xau_match():
    """Matching XAU direction when both known → match."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "xau_direction": "FALLING"}
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
        xau_direction="FALLING",
        snapshot=MockSnapshot(premium_percent=-3.0),
    )
    result = calculate_similarity(ref, candidate)
    assert result is not None, "Expected match with matching XAU direction"
    assert result.xau_direction == "FALLING"
    print("PASS: test_similarity_xau_match")


def test_similarity_xau_mismatch_rejects():
    """Different XAU direction when both known → no match."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "xau_direction": "FALLING"}
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
        xau_direction="RISING",
        snapshot=MockSnapshot(premium_percent=-3.0),
    )
    result = calculate_similarity(ref, candidate)
    assert result is None, "Expected no match when XAU directions differ"
    print("PASS: test_similarity_xau_mismatch_rejects")


def test_similarity_xau_unknown_no_block():
    """UNKNOWN XAU direction → no fabricated blocking."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "xau_direction": "FALLING"}
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
        # no xau_direction → UNKNOWN
        snapshot=MockSnapshot(premium_percent=-3.0),
    )
    result = calculate_similarity(ref, candidate)
    assert result is not None, "Expected match when candidate XAU direction is unknown"
    print("PASS: test_similarity_xau_unknown_no_block")


def test_similarity_xau_reference_unknown_no_block():
    """Reference XAU direction UNKNOWN → no blocking."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "xau_direction": "UNKNOWN"}
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
        xau_direction="RISING",
        snapshot=MockSnapshot(premium_percent=-3.0),
    )
    result = calculate_similarity(ref, candidate)
    assert result is not None, "Expected match when reference XAU direction is unknown"
    print("PASS: test_similarity_xau_reference_unknown_no_block")


# ---------------------------------------------------------------------------
# 5. Combined secondary filters
# ---------------------------------------------------------------------------

def test_similarity_multiple_soft_filters():
    """All soft filters match → success."""
    ref = {
        "premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING",
        "structure": "DISCOUNT_DOMINANT", "usd_direction": "RISING", "xau_direction": "FALLING",
    }
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
        usd_direction="RISING", xau_direction="FALLING",
        snapshot=MockSnapshot(premium_percent=-3.0),
    )
    result = calculate_similarity(ref, candidate)
    assert result is not None
    print("PASS: test_similarity_multiple_soft_filters")


def test_similarity_one_soft_filter_fails():
    """One soft filter fails (both known, different) → reject."""
    ref = {
        "premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING",
        "structure": "DISCOUNT_DOMINANT", "usd_direction": "RISING", "xau_direction": "FALLING",
    }
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
        usd_direction="RISING", xau_direction="RISING",  # mismatch
        snapshot=MockSnapshot(premium_percent=-3.0),
    )
    result = calculate_similarity(ref, candidate)
    assert result is None, "Expected no match when one soft filter mismatches"
    print("PASS: test_similarity_one_soft_filter_fails")


# ---------------------------------------------------------------------------
# 6. Ranking
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
# 7. build_historical_comparison
# ---------------------------------------------------------------------------

def test_comparison_finds_matches():
    """Multiple candidates, some match."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING"}
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
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING"}
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
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING"}
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
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING"}
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
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING"}
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
# 8. HistoricalComparison.to_text
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
# 9. Edge cases
# ---------------------------------------------------------------------------

def test_similarity_missing_premium():
    """Candidate with no premium data → no match."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING"}
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
    ref = {"premium": None, "valuation": "CHEAP", "momentum": "IMPROVING"}
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
        # Soft-match primitives
        test_soft_match_both_known_equal,
        test_soft_match_both_known_different,
        test_soft_match_one_unknown,
        test_soft_match_both_unknown,
        # Primary hard requirements
        test_similarity_exact_match,
        test_similarity_valuation_mismatch,
        test_similarity_momentum_mismatch,
        test_similarity_premium_out_of_tolerance,
        test_similarity_premium_at_boundary,
        # Secondary soft — structure
        test_similarity_structure_both_known_mismatch,
        test_similarity_structure_unknown_no_block,
        test_similarity_structure_reference_unknown_no_block,
        test_similarity_structure_both_known_match,
        # Secondary soft — USD
        test_similarity_usd_match,
        test_similarity_usd_mismatch_rejects,
        test_similarity_usd_unknown_no_block,
        test_similarity_usd_reference_unknown_no_block,
        # Secondary soft — XAU
        test_similarity_xau_match,
        test_similarity_xau_mismatch_rejects,
        test_similarity_xau_unknown_no_block,
        test_similarity_xau_reference_unknown_no_block,
        # Combined soft filters
        test_similarity_multiple_soft_filters,
        test_similarity_one_soft_filter_fails,
        # Ranking
        test_rank_by_premium_distance,
        test_rank_tiebreaker_recency,
        # Comparison
        test_comparison_finds_matches,
        test_comparison_no_matches,
        test_comparison_respects_max_results,
        test_comparison_sufficient_data_threshold,
        test_comparison_insufficient_data,
        # Text
        test_text_output_contains_reference,
        test_text_output_no_matches,
        test_text_output_insufficient_warning,
        test_text_output_no_prediction,
        # Edge cases
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
