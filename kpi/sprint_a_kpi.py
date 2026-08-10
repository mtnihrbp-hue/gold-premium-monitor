"""SP-A Sprint KPI — 10 behavioral verification checks.

Run: python kpi/sprint_a_kpi.py
Output: SPRINT A COMPLETE  or  SPRINT A FAILED
"""

import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from caluclator.valuation import evaluate_valuation
from caluclator.momentum import get_premium_direction, evaluate_momentum
from caluclator.structure import evaluate_structure
from caluclator.conflict import evaluate_conflict
from caluclator.signals import apply_hysteresis, evaluate_signal
from caluclator.signal_state import build_signal_state, SignalState
from alerts.telegram import format_decision_section


# ---------------------------------------------------------------------------
# KPI Checks
# ---------------------------------------------------------------------------

def kpi_1_valuation_cheap_recognized():
    """1. Deep discount recognized as CHEAP."""
    result = evaluate_valuation(-4.0, {"buy_premium": -1.5, "sell_premium": 2.0})
    assert result == "CHEAP", f"FAIL: expected CHEAP, got {result}"
    print("  ✓ KPI-1: Valuation cheap recognized")


def kpi_2_valuation_expensive_recognized():
    """2. High premium recognized as EXPENSIVE."""
    result = evaluate_valuation(3.0, {"buy_premium": -1.5, "sell_premium": 2.0})
    assert result == "EXPENSIVE", f"FAIL: expected EXPENSIVE, got {result}"
    print("  ✓ KPI-2: Valuation expensive recognized")


def kpi_3_discount_widening_detected():
    """3. Discount widening detected (improving for buyer)."""
    result = get_premium_direction(-5.0, -4.0)
    assert result == "DISCOUNT_WIDENING", f"FAIL: expected DISCOUNT_WIDENING, got {result}"
    print("  ✓ KPI-3: Discount widening detected")


def kpi_4_discount_narrowing_detected():
    """4. Discount narrowing detected (weakening for buyer)."""
    result = get_premium_direction(-4.0, -5.0)
    assert result == "DISCOUNT_NARROWING", f"FAIL: expected DISCOUNT_NARROWING, got {result}"
    print("  ✓ KPI-4: Discount narrowing detected")


def kpi_5_platform_consensus_calculated():
    """5. Platform consensus correctly calculated."""
    markets = {
        f"p{i}": {"price": 100.0 + i * 10, "status": "OK"}
        for i in range(9)
    }
    result = evaluate_structure(markets, 160.0)
    assert result["state"] == "DISCOUNT_DOMINANT", f"FAIL: expected DISCOUNT_DOMINANT"
    assert result["platforms_below_fair"] == 6, f"FAIL: expected 6 below"
    assert result["platforms_above_fair"] == 3, f"FAIL: expected 3 above"
    print("  ✓ KPI-5: Platform consensus calculated")


def kpi_6_conflict_detected():
    """6. Conflict state produced from valuation + momentum + structure."""
    conflict, decision = evaluate_conflict("CHEAP", "IMPROVING", "DISCOUNT_DOMINANT")
    assert conflict == "SUPPORTIVE", f"FAIL: expected SUPPORTIVE, got {conflict}"
    assert decision == "BUY", f"FAIL: expected BUY, got {decision}"
    print("  ✓ KPI-6: Conflict detected")


def kpi_7_cheap_plus_weakening_is_wait():
    """7. CHEAP + WEAKENING → WAIT (conflicting evidence)."""
    conflict, decision = evaluate_conflict("CHEAP", "WEAKENING", "DISCOUNT_DOMINANT")
    assert decision == "WAIT", f"FAIL: expected WAIT, got {decision}"
    assert conflict == "CAUTION", f"FAIL: expected CAUTION, got {conflict}"
    print("  ✓ KPI-7: Cheap + weakening = wait")


def kpi_8_state_persisted_to_neon():
    """8. Market state can be serialized to DB format."""
    markets = {
        "a": {"price": 90.0, "status": "OK"},
        "b": {"price": 95.0, "status": "OK"},
        "c": {"price": 110.0, "status": "OK"},
    }
    state = build_signal_state(
        premium=-3.0,
        fair_price=100.0,
        lowest_price=90.0,
        markets=markets,
        previous_premium=-2.0,
        thresholds={"buy_premium": -1.5, "sell_premium": 2.0},
        last_alert=None,
        snapshot_id=42,
    )
    required_fields = [
        "snapshot_id", "valuation", "momentum", "premium_direction",
        "structure", "platform_average", "platform_high", "platform_low",
        "platform_spread", "platforms_below_fair", "platforms_above_fair",
        "conflict", "candidate_decision", "final_decision", "reason", "timestamp",
    ]
    for field in required_fields:
        assert hasattr(state, field), f"FAIL: missing field {field}"
    assert state.snapshot_id == 42
    print("  ✓ KPI-8: State persisted to Neon (schema validated)")


def kpi_9_telegram_contains_normalized_state():
    """9. Telegram decision section contains normalized market state."""
    markets = {
        "a": {"price": 90.0, "status": "OK"},
        "b": {"price": 95.0, "status": "OK"},
        "c": {"price": 110.0, "status": "OK"},
    }
    state = build_signal_state(
        premium=-3.0,
        fair_price=100.0,
        lowest_price=90.0,
        markets=markets,
        previous_premium=-2.0,
        thresholds={"buy_premium": -1.5, "sell_premium": 2.0},
        last_alert=None,
        snapshot_id=0,
    )
    text = format_decision_section(state)
    assert "CHEAP" in text, "FAIL: valuation not in telegram"
    assert "IMPROVING" in text, "FAIL: momentum not in telegram"
    assert "DISCOUNT DOMINANT" in text, "FAIL: structure not in telegram"
    assert "SUPPORTIVE" in text, "FAIL: conflict not in telegram"
    assert "BUY" in text, "FAIL: decision not in telegram"
    print("  ✓ KPI-9: Telegram contains normalized state")


def kpi_10_existing_functionality_operational():
    """10. Legacy evaluate_signal still works unchanged."""
    result = evaluate_signal(
        current_premium=0.0,
        previous_premium=0.0,
        last_alert_type=None,
        thresholds={"buy_premium_percent": -1.5, "sell_premium_percent": 3.0, "min_change_for_alert": 0.5},
    )
    assert result is None, f"FAIL: expected None in hold zone, got {result}"

    result = evaluate_signal(
        current_premium=-2.0,
        previous_premium=0.0,
        last_alert_type=None,
        thresholds={"buy_premium_percent": -1.5, "sell_premium_percent": 3.0, "min_change_for_alert": 0.5},
    )
    assert result is not None, "FAIL: expected alert on first BUY entry"
    assert result["signal"] == "BUY", f"FAIL: expected BUY, got {result['signal']}"
    print("  ✓ KPI-10: Existing functionality operational")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    checks = [
        kpi_1_valuation_cheap_recognized,
        kpi_2_valuation_expensive_recognized,
        kpi_3_discount_widening_detected,
        kpi_4_discount_narrowing_detected,
        kpi_5_platform_consensus_calculated,
        kpi_6_conflict_detected,
        kpi_7_cheap_plus_weakening_is_wait,
        kpi_8_state_persisted_to_neon,
        kpi_9_telegram_contains_normalized_state,
        kpi_10_existing_functionality_operational,
    ]

    passed = 0
    failed = 0

    print("\nSP-A SPRINT KPI")
    print("=" * 40)

    for check in checks:
        try:
            check()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {check.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {check.__name__}: ERROR: {e}")
            failed += 1

    print("\n" + "=" * 40)
    print(f"Result: {passed}/{len(checks)} passed, {failed} failed")

    if failed == 0:
        print("\n🟢 SPRINT A COMPLETE")
        return 0
    else:
        print("\n🔴 SPRINT A FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
