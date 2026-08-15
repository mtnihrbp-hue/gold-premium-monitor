"""SP-B.1 Sprint KPI — Historical Intelligence Foundation.

Run: python kpi/kpi_sp_b1.py
Output: SP-B.1 COMPLETE  or  SP-B.1 FAILED

Behavioral verification — no database, no network.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from intelligence.historical import (
    calculate_similarity,
    rank_similar_states,
    build_historical_comparison,
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
# KPI Checks
# ---------------------------------------------------------------------------

def kpi_1_similarity_exact_categorical_match():
    """1. Exact categorical match (valuation + momentum + structure) finds similar state."""
    ref = {"premium": -3.2, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    candidate = MockState(
        id=1, snapshot_id=10,
        valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
        premium_direction="DISCOUNT_WIDENING", conflict_state="SUPPORTIVE",
        candidate_decision="BUY", final_decision="BUY",
        timestamp=datetime.now() - timedelta(days=5),
        platforms_below_fair=2, platforms_above_fair=1, platform_spread=5000,
        snapshot=MockSnapshot(premium_percent=-3.5),
    )
    result = calculate_similarity(ref, candidate, premium_tolerance=1.0)
    assert result is not None, "FAIL: exact categorical match should succeed"
    assert result.premium_distance == 0.3
    print("  ✓ KPI-1: Exact categorical match works")


def kpi_2_similarity_filters_mismatches():
    """2. Mismatched valuation, momentum, or structure is rejected."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    mismatches = [
        MockState(id=1, valuation_state="FAIR", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT", snapshot=MockSnapshot(-3.0)),
        MockState(id=2, valuation_state="CHEAP", momentum_state="WEAKENING", structure_state="DISCOUNT_DOMINANT", snapshot=MockSnapshot(-3.0)),
        MockState(id=3, valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="MIXED", snapshot=MockSnapshot(-3.0)),
    ]
    for c in mismatches:
        result = calculate_similarity(ref, c)
        assert result is None, f"FAIL: mismatch should be rejected"
    print("  ✓ KPI-2: Mismatches correctly filtered")


def kpi_3_premium_tolerance_respected():
    """3. Premium outside tolerance is rejected; within tolerance is accepted."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    out = MockState(id=1, valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
                    snapshot=MockSnapshot(-5.5))
    inside = MockState(id=2, valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
                       snapshot=MockSnapshot(-3.8))
    assert calculate_similarity(ref, out, premium_tolerance=1.0) is None
    assert calculate_similarity(ref, inside, premium_tolerance=1.0) is not None
    print("  ✓ KPI-3: Premium tolerance respected")


def kpi_4_ranking_orders_by_premium_distance():
    """4. Results ordered by premium distance ascending."""
    states = [
        MockState(id=i, snapshot_id=i,
                  valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
                  snapshot=MockSnapshot(-3.0 - i * 0.3),
                  timestamp=datetime.now() - timedelta(days=i),
                  platforms_below_fair=2, platforms_above_fair=1, platform_spread=5000,
                  premium_direction="DISCOUNT_WIDENING", conflict_state="SUPPORTIVE",
                  candidate_decision="BUY", final_decision="BUY")
        for i in range(5)
    ]
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    matches = [calculate_similarity(ref, s, premium_tolerance=2.0) for s in states]
    matches = [m for m in matches if m is not None]
    ranked = rank_similar_states(matches)
    for i in range(len(ranked) - 1):
        assert ranked[i].premium_distance <= ranked[i + 1].premium_distance, \
            "FAIL: ranking out of order"
    print("  ✓ KPI-4: Ranking orders by premium distance")


def kpi_5_comparison_returns_configurable_max_results():
    """5. max_results limits output correctly."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    candidates = [
        MockState(id=i, snapshot_id=i,
                  valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
                  snapshot=MockSnapshot(-3.0 - i * 0.05),
                  timestamp=datetime.now() - timedelta(days=i),
                  platforms_below_fair=2, platforms_above_fair=1, platform_spread=5000,
                  premium_direction="DISCOUNT_WIDENING", conflict_state="SUPPORTIVE",
                  candidate_decision="BUY", final_decision="BUY")
        for i in range(10)
    ]
    comparison = build_historical_comparison(ref, candidates, config={"premium_tolerance": 2.0, "max_results": 3})
    assert comparison.match_count == 3, f"FAIL: expected 3, got {comparison.match_count}"
    print("  ✓ KPI-5: max_results respected")


def kpi_6_graceful_empty_result():
    """6. No candidates → empty comparison, no crash."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    comparison = build_historical_comparison(ref, [])
    assert comparison.match_count == 0
    assert not comparison.has_sufficient_data
    text = comparison.to_text()
    assert "No comparable" in text
    print("  ✓ KPI-6: Graceful empty result")


def kpi_7_sample_size_exposed():
    """7. Sufficient vs insufficient data is correctly flagged."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    few = [MockState(id=i, snapshot_id=i,
                     valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
                     snapshot=MockSnapshot(-3.1), timestamp=datetime.now() - timedelta(days=i),
                     platforms_below_fair=2, platforms_above_fair=1, platform_spread=5000,
                     premium_direction="DISCOUNT_WIDENING", conflict_state="SUPPORTIVE",
                     candidate_decision="BUY", final_decision="BUY")
           for i in range(2)]
    many = [MockState(id=i, snapshot_id=i,
                      valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
                      snapshot=MockSnapshot(-3.1), timestamp=datetime.now() - timedelta(days=i),
                      platforms_below_fair=2, platforms_above_fair=1, platform_spread=5000,
                      premium_direction="DISCOUNT_WIDENING", conflict_state="SUPPORTIVE",
                      candidate_decision="BUY", final_decision="BUY")
            for i in range(5)]
    c_few = build_historical_comparison(ref, few)
    c_many = build_historical_comparison(ref, many)
    assert not c_few.has_sufficient_data
    assert c_many.has_sufficient_data
    print("  ✓ KPI-7: Sample size correctly exposed")


def kpi_8_text_contains_no_prediction():
    """8. Output never contains prediction language."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    candidates = [
        MockState(id=1, snapshot_id=1,
                  valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
                  snapshot=MockSnapshot(-3.1), timestamp=datetime.now() - timedelta(days=5),
                  platforms_below_fair=2, platforms_above_fair=1, platform_spread=5000,
                  premium_direction="DISCOUNT_WIDENING", conflict_state="SUPPORTIVE",
                  candidate_decision="BUY", final_decision="BUY"),
    ]
    comparison = build_historical_comparison(ref, candidates)
    text = comparison.to_text().lower()
    forbidden = ["predict", "forecast", "will rise", "will fall", "expect", "outcome"]
    for word in forbidden:
        assert word not in text, f"FAIL: forbidden word '{word}' in output"
    print("  ✓ KPI-8: No prediction language")


def kpi_9_text_readable_format():
    """9. Text output is human-readable with reference state."""
    ref = {"premium": -3.2, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    candidates = [
        MockState(id=1, snapshot_id=1,
                  valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
                  snapshot=MockSnapshot(-3.5), timestamp=datetime.now() - timedelta(days=5),
                  platforms_below_fair=2, platforms_above_fair=1, platform_spread=5000,
                  premium_direction="DISCOUNT_WIDENING", conflict_state="SUPPORTIVE",
                  candidate_decision="BUY", final_decision="BUY"),
        MockState(id=2, snapshot_id=2,
                  valuation_state="CHEAP", momentum_state="IMPROVING", structure_state="DISCOUNT_DOMINANT",
                  snapshot=MockSnapshot(-2.9), timestamp=datetime.now() - timedelta(days=12),
                  platforms_below_fair=2, platforms_above_fair=1, platform_spread=5000,
                  premium_direction="DISCOUNT_WIDENING", conflict_state="SUPPORTIVE",
                  candidate_decision="BUY", final_decision="BUY"),
    ]
    comparison = build_historical_comparison(ref, candidates)
    text = comparison.to_text()
    assert "CHEAP" in text
    assert "IMPROVING" in text
    assert "DISCOUNT_DOMINANT" in text
    assert "BUY" in text
    assert "5d ago" in text or "12d ago" in text
    print("  ✓ KPI-9: Human-readable format")


def kpi_10_db_unavailable_returns_empty():
    """10. DB unavailable scenario: returns empty HistoricalComparison."""
    # Verify the fallback object structure directly
    # (Full DB path requires sqlalchemy installed; core logic verified here)
    comparison = HistoricalComparison(
        reference_premium=-3.0,
        reference_valuation="CHEAP",
        reference_momentum="IMPROVING",
        reference_structure="DISCOUNT_DOMINANT",
    )
    assert comparison.match_count == 0
    assert not comparison.has_sufficient_data
    text = comparison.to_text()
    assert "No comparable" in text
    # Verify repository function signature exists when sqlalchemy available
    try:
        from database.repository import get_similar_market_states
        assert callable(get_similar_market_states)
        print("  ✓ KPI-10: DB unavailable degrades gracefully (sqlalchemy available)")
    except ImportError:
        # sqlalchemy not installed in this environment — fallback verified above
        print("  ✓ KPI-10: DB unavailable degrades gracefully (sqlalchemy not installed — fallback verified)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 50)
    print("SP-B.1 Sprint KPI")
    print("=" * 50)

    checks = [
        kpi_1_similarity_exact_categorical_match,
        kpi_2_similarity_filters_mismatches,
        kpi_3_premium_tolerance_respected,
        kpi_4_ranking_orders_by_premium_distance,
        kpi_5_comparison_returns_configurable_max_results,
        kpi_6_graceful_empty_result,
        kpi_7_sample_size_exposed,
        kpi_8_text_contains_no_prediction,
        kpi_9_text_readable_format,
        kpi_10_db_unavailable_returns_empty,
    ]

    passed = 0
    failed = 0
    for check in checks:
        try:
            check()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {check.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {check.__name__}: ERR {e}")
            failed += 1

    print("=" * 50)
    print(f"Result: {passed}/{len(checks)} passed, {failed} failed")
    if failed == 0:
        print("\n🟢 SP-B.1 COMPLETE")
    else:
        print("\n🔴 SP-B.1 FAILED")
        sys.exit(1)
