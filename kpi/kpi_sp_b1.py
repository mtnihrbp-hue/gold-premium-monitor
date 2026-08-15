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
    _soft_match,
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
    """1. Exact categorical match (valuation + momentum) finds similar state."""
    ref = {"premium": -3.2, "valuation": "CHEAP", "momentum": "IMPROVING"}
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


def kpi_2_similarity_filters_hard_mismatches():
    """2. Mismatched valuation or momentum is rejected (hard requirements)."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING"}
    mismatches = [
        MockState(id=1, valuation_state="FAIR", momentum_state="IMPROVING", snapshot=MockSnapshot(-3.0)),
        MockState(id=2, valuation_state="CHEAP", momentum_state="WEAKENING", snapshot=MockSnapshot(-3.0)),
    ]
    for c in mismatches:
        result = calculate_similarity(ref, c)
        assert result is None, "FAIL: hard mismatch should be rejected"
    print("  ✓ KPI-2: Hard mismatches correctly filtered")


def kpi_3_premium_tolerance_respected():
    """3. Premium outside tolerance is rejected; within tolerance is accepted."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING"}
    out = MockState(id=1, valuation_state="CHEAP", momentum_state="IMPROVING",
                    snapshot=MockSnapshot(-5.5))
    inside = MockState(id=2, valuation_state="CHEAP", momentum_state="IMPROVING",
                       snapshot=MockSnapshot(-3.8))
    assert calculate_similarity(ref, out, premium_tolerance=1.0) is None
    assert calculate_similarity(ref, inside, premium_tolerance=1.0) is not None
    print("  ✓ KPI-3: Premium tolerance respected")


def kpi_4_structure_soft_match():
    """4. Structure: both known and different → reject; either unknown → no block."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "structure": "DISCOUNT_DOMINANT"}
    # Both known, different → reject
    c1 = MockState(id=1, valuation_state="CHEAP", momentum_state="IMPROVING",
                   structure_state="MIXED", snapshot=MockSnapshot(-3.0))
    # Candidate unknown → allow
    c2 = MockState(id=2, valuation_state="CHEAP", momentum_state="IMPROVING",
                   snapshot=MockSnapshot(-3.0))
    # Both known, same → allow
    c3 = MockState(id=3, valuation_state="CHEAP", momentum_state="IMPROVING",
                   structure_state="DISCOUNT_DOMINANT", snapshot=MockSnapshot(-3.0))
    assert calculate_similarity(ref, c1) is None
    assert calculate_similarity(ref, c2) is not None
    assert calculate_similarity(ref, c3) is not None
    print("  ✓ KPI-4: Structure soft match works")


def kpi_5_usd_direction_soft_match():
    """5. USD/IRR direction: match when both known; no block when unknown."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "usd_direction": "RISING"}
    # Both known, match → allow
    c1 = MockState(id=1, valuation_state="CHEAP", momentum_state="IMPROVING",
                   usd_direction="RISING", snapshot=MockSnapshot(-3.0))
    # Both known, mismatch → reject
    c2 = MockState(id=2, valuation_state="CHEAP", momentum_state="IMPROVING",
                   usd_direction="FALLING", snapshot=MockSnapshot(-3.0))
    # Candidate unknown → allow
    c3 = MockState(id=3, valuation_state="CHEAP", momentum_state="IMPROVING",
                   snapshot=MockSnapshot(-3.0))
    assert calculate_similarity(ref, c1) is not None
    assert calculate_similarity(ref, c2) is None
    assert calculate_similarity(ref, c3) is not None
    print("  ✓ KPI-5: USD direction soft match works")


def kpi_6_xau_direction_soft_match():
    """6. XAU/USD direction: match when both known; no block when unknown."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING", "xau_direction": "FALLING"}
    # Both known, match → allow
    c1 = MockState(id=1, valuation_state="CHEAP", momentum_state="IMPROVING",
                   xau_direction="FALLING", snapshot=MockSnapshot(-3.0))
    # Both known, mismatch → reject
    c2 = MockState(id=2, valuation_state="CHEAP", momentum_state="IMPROVING",
                   xau_direction="RISING", snapshot=MockSnapshot(-3.0))
    # Candidate unknown → allow
    c3 = MockState(id=3, valuation_state="CHEAP", momentum_state="IMPROVING",
                   snapshot=MockSnapshot(-3.0))
    assert calculate_similarity(ref, c1) is not None
    assert calculate_similarity(ref, c2) is None
    assert calculate_similarity(ref, c3) is not None
    print("  ✓ KPI-6: XAU direction soft match works")


def kpi_7_unknown_never_fabricates():
    """7. UNKNOWN USD/XAU/structure never causes fabricated matching."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING",
           "usd_direction": "UNKNOWN", "xau_direction": "UNKNOWN", "structure": "UNKNOWN"}
    candidate = MockState(
        id=1, valuation_state="CHEAP", momentum_state="IMPROVING",
        usd_direction="RISING", xau_direction="FALLING", structure_state="MIXED",
        snapshot=MockSnapshot(premium_percent=-3.0),
    )
    result = calculate_similarity(ref, candidate)
    assert result is not None, "FAIL: UNKNOWN reference fields should not block"
    print("  ✓ KPI-7: UNKNOWN never fabricates blocking")


def kpi_8_ranking_orders_by_premium_distance():
    """8. Results ordered by premium distance ascending."""
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
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING"}
    matches = [calculate_similarity(ref, s, premium_tolerance=2.0) for s in states]
    matches = [m for m in matches if m is not None]
    ranked = rank_similar_states(matches)
    for i in range(len(ranked) - 1):
        assert ranked[i].premium_distance <= ranked[i + 1].premium_distance, \
            "FAIL: ranking out of order"
    print("  ✓ KPI-8: Ranking orders by premium distance")


def kpi_9_comparison_returns_configurable_max_results():
    """9. max_results limits output correctly."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING"}
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
    print("  ✓ KPI-9: max_results respected")


def kpi_10_graceful_empty_and_no_prediction():
    """10. Empty result graceful + no prediction language."""
    ref = {"premium": -3.0, "valuation": "CHEAP", "momentum": "IMPROVING"}
    comparison = build_historical_comparison(ref, [])
    assert comparison.match_count == 0
    assert not comparison.has_sufficient_data
    text = comparison.to_text()
    assert "No comparable" in text
    forbidden = ["predict", "forecast", "will rise", "will fall", "expect", "outcome"]
    for word in forbidden:
        assert word not in text.lower(), f"FAIL: forbidden word '{word}' in output"
    print("  ✓ KPI-10: Graceful empty + no prediction")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 50)
    print("SP-B.1 Sprint KPI")
    print("=" * 50)

    checks = [
        kpi_1_similarity_exact_categorical_match,
        kpi_2_similarity_filters_hard_mismatches,
        kpi_3_premium_tolerance_respected,
        kpi_4_structure_soft_match,
        kpi_5_usd_direction_soft_match,
        kpi_6_xau_direction_soft_match,
        kpi_7_unknown_never_fabricates,
        kpi_8_ranking_orders_by_premium_distance,
        kpi_9_comparison_returns_configurable_max_results,
        kpi_10_graceful_empty_and_no_prediction,
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
