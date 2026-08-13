"""Unit tests for the SP-A signal state pipeline.

26 existing + 7 new regression tests — no database, no network, no ML.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from caluclator.valuation import evaluate_valuation
from caluclator.momentum import get_premium_direction, evaluate_momentum
from caluclator.structure import evaluate_structure
from caluclator.conflict import evaluate_conflict
from caluclator.signals import apply_hysteresis
from caluclator.signal_state import build_signal_state, SignalState
from alerts.telegram import (
    send_alert,
    send_manual_update,
    send_data_unavailable,
    send_processing,
    send_daily_recap,
    format_decision_section,
)
from alerts.helpers import format_momentum_block


# ---------------------------------------------------------------------------
# 1. Valuation Engine (4 tests)
# ---------------------------------------------------------------------------

def test_valuation_cheap():
    """premium = -4.0, threshold = -1.5 → CHEAP"""
    result = evaluate_valuation(-4.0, {"buy_premium": -1.5, "sell_premium": 2.0})
    assert result == "CHEAP", f"Expected CHEAP, got {result}"


def test_valuation_expensive():
    """premium = 3.0, threshold = 2.0 → EXPENSIVE"""
    result = evaluate_valuation(3.0, {"buy_premium": -1.5, "sell_premium": 2.0})
    assert result == "EXPENSIVE", f"Expected EXPENSIVE, got {result}"


def test_valuation_fair():
    """premium = 0.5 → FAIR"""
    result = evaluate_valuation(0.5, {"buy_premium": -1.5, "sell_premium": 2.0})
    assert result == "FAIR", f"Expected FAIR, got {result}"


def test_valuation_unknown():
    """premium = None → UNKNOWN"""
    result = evaluate_valuation(None, {"buy_premium": -1.5, "sell_premium": 2.0})
    assert result == "UNKNOWN", f"Expected UNKNOWN, got {result}"


# ---------------------------------------------------------------------------
# 2. Premium Direction (6 tests)
# ---------------------------------------------------------------------------

def test_premium_direction_discount_widening():
    """-4.0 → -5.0 (more negative) → DISCOUNT_WIDENING"""
    result = get_premium_direction(-5.0, -4.0)
    assert result == "DISCOUNT_WIDENING", f"Expected DISCOUNT_WIDENING, got {result}"


def test_premium_direction_discount_narrowing():
    """-5.0 → -4.0 (less negative) → DISCOUNT_NARROWING"""
    result = get_premium_direction(-4.0, -5.0)
    assert result == "DISCOUNT_NARROWING", f"Expected DISCOUNT_NARROWING, got {result}"


def test_premium_direction_premium_widening():
    """+2.0 → +3.0 (more positive) → PREMIUM_WIDENING"""
    result = get_premium_direction(3.0, 2.0)
    assert result == "PREMIUM_WIDENING", f"Expected PREMIUM_WIDENING, got {result}"


def test_premium_direction_premium_narrowing():
    """+3.0 → +2.0 (less positive) → PREMIUM_NARROWING"""
    result = get_premium_direction(2.0, 3.0)
    assert result == "PREMIUM_NARROWING", f"Expected PREMIUM_NARROWING, got {result}"


def test_premium_direction_stable():
    """diff < 0.05% → STABLE"""
    result = get_premium_direction(2.01, 2.0)
    assert result == "PREMIUM_STABLE", f"Expected PREMIUM_STABLE, got {result}"


def test_premium_direction_no_previous():
    """previous_premium = None → defaults to STABLE based on sign"""
    result = get_premium_direction(-3.0, None)
    assert result == "DISCOUNT_STABLE", f"Expected DISCOUNT_STABLE, got {result}"


# ---------------------------------------------------------------------------
# 3. Momentum Engine (3 tests)
# ---------------------------------------------------------------------------

def test_momentum_improving():
    """DISCOUNT_WIDENING → IMPROVING"""
    result = evaluate_momentum("DISCOUNT_WIDENING")
    assert result == "IMPROVING", f"Expected IMPROVING, got {result}"


def test_momentum_weakening():
    """DISCOUNT_NARROWING → WEAKENING"""
    result = evaluate_momentum("DISCOUNT_NARROWING")
    assert result == "WEAKENING", f"Expected WEAKENING, got {result}"


def test_momentum_neutral():
    """DISCOUNT_STABLE → NEUTRAL"""
    result = evaluate_momentum("DISCOUNT_STABLE")
    assert result == "NEUTRAL", f"Expected NEUTRAL, got {result}"


# ---------------------------------------------------------------------------
# 4. Structure Engine (4 tests)
# ---------------------------------------------------------------------------

def test_structure_discount_dominant():
    """6/9 below fair → DISCOUNT_DOMINANT"""
    markets = {
        f"p{i}": {"price": 100.0 + i * 10, "status": "OK"}
        for i in range(9)
    }
    result = evaluate_structure(markets, 160.0)
    assert result["state"] == "DISCOUNT_DOMINANT", f"Expected DISCOUNT_DOMINANT, got {result['state']}"


def test_structure_premium_dominant():
    """6/9 above fair → PREMIUM_DOMINANT"""
    markets = {
        f"p{i}": {"price": 100.0 + i * 10, "status": "OK"}
        for i in range(9)
    }
    result = evaluate_structure(markets, 130.0)
    assert result["state"] == "PREMIUM_DOMINANT", f"Expected PREMIUM_DOMINANT, got {result['state']}"


def test_structure_mixed():
    """4/9 below, 5/9 above → MIXED"""
    markets = {
        f"p{i}": {"price": 100.0 + i * 10, "status": "OK"}
        for i in range(9)
    }
    result = evaluate_structure(markets, 135.0)
    assert result["state"] == "MIXED", f"Expected MIXED, got {result['state']}"


def test_structure_insufficient_platforms():
    """1 platform → UNKNOWN"""
    markets = {"only": {"price": 100.0, "status": "OK"}}
    result = evaluate_structure(markets, 100.0)
    assert result["state"] == "UNKNOWN", f"Expected UNKNOWN, got {result['state']}"


# ---------------------------------------------------------------------------
# 5. Conflict Engine (4 tests)
# ---------------------------------------------------------------------------

def test_conflict_supportive_buy():
    """CHEAP + IMPROVING + DISCOUNT_DOMINANT → SUPPORTIVE, BUY"""
    conflict, decision = evaluate_conflict("CHEAP", "IMPROVING", "DISCOUNT_DOMINANT")
    assert conflict == "SUPPORTIVE", f"Expected SUPPORTIVE, got {conflict}"
    assert decision == "BUY", f"Expected BUY, got {decision}"


def test_conflict_caution_wait():
    """CHEAP + WEAKENING + ANY → CAUTION, WAIT"""
    conflict, decision = evaluate_conflict("CHEAP", "WEAKENING", "DISCOUNT_DOMINANT")
    assert conflict == "CAUTION", f"Expected CAUTION, got {conflict}"
    assert decision == "WAIT", f"Expected WAIT, got {decision}"


def test_conflict_supportive_sell():
    """EXPENSIVE + WEAKENING + PREMIUM_DOMINANT → SUPPORTIVE_FOR_SELL, SELL"""
    conflict, decision = evaluate_conflict("EXPENSIVE", "WEAKENING", "PREMIUM_DOMINANT")
    assert conflict == "SUPPORTIVE_FOR_SELL", f"Expected SUPPORTIVE_FOR_SELL, got {conflict}"
    assert decision == "SELL", f"Expected SELL, got {decision}"


def test_conflict_unknown():
    """UNKNOWN + ANY + ANY → UNKNOWN, UNKNOWN"""
    conflict, decision = evaluate_conflict("UNKNOWN", "IMPROVING", "DISCOUNT_DOMINANT")
    assert conflict == "UNKNOWN", f"Expected UNKNOWN, got {conflict}"
    assert decision == "UNKNOWN", f"Expected UNKNOWN, got {decision}"


# ---------------------------------------------------------------------------
# 6. Hysteresis (2 tests)
# ---------------------------------------------------------------------------

def test_hysteresis_cooldown_same_alert():
    """Candidate=BUY, last_alert=BUY → WAIT (cooldown)"""
    result = apply_hysteresis("BUY", "BUY", {})
    assert result == "WAIT", f"Expected WAIT, got {result}"


def test_hysteresis_passes_new_alert():
    """Candidate=BUY, last_alert=None → BUY"""
    result = apply_hysteresis("BUY", None, {})
    assert result == "BUY", f"Expected BUY, got {result}"


# ---------------------------------------------------------------------------
# 7. Platform Metrics (2 tests)
# ---------------------------------------------------------------------------

def test_platform_average():
    """3 platforms [100, 200, 300] → avg = 200"""
    markets = {
        "a": {"price": 100.0, "status": "OK"},
        "b": {"price": 200.0, "status": "OK"},
        "c": {"price": 300.0, "status": "OK"},
    }
    result = evaluate_structure(markets, 200.0)
    assert result["platform_average"] == 200.0, f"Expected 200.0, got {result['platform_average']}"


def test_platform_spread():
    """3 platforms [100, 200, 300] → spread = 200"""
    markets = {
        "a": {"price": 100.0, "status": "OK"},
        "b": {"price": 200.0, "status": "OK"},
        "c": {"price": 300.0, "status": "OK"},
    }
    result = evaluate_structure(markets, 200.0)
    assert result["platform_spread"] == 200.0, f"Expected 200.0, got {result['platform_spread']}"


# ---------------------------------------------------------------------------
# 8. Integration (1 test)
# ---------------------------------------------------------------------------

def test_build_signal_state_integration():
    """Full pipeline: cheap + improving + discount dominant → BUY"""
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
    assert state.valuation == "CHEAP"
    assert state.momentum == "IMPROVING"
    assert state.premium_direction == "DISCOUNT_WIDENING"
    assert state.structure == "DISCOUNT_DOMINANT"
    assert state.conflict == "SUPPORTIVE"
    assert state.candidate_decision == "BUY"
    assert state.final_decision == "BUY"
    assert state.platforms_below_fair == 2
    assert state.platforms_above_fair == 1


# ---------------------------------------------------------------------------
# 9. SP-A STABILIZATION — Regression Tests (7 tests)
# ---------------------------------------------------------------------------

def test_telegram_api_available():
    """All 5 public Telegram functions must be importable and callable."""
    assert callable(send_alert)
    assert callable(send_manual_update)
    assert callable(send_data_unavailable)
    assert callable(send_processing)
    assert callable(send_daily_recap)
    assert callable(format_decision_section)


def test_no_duplicate_header():
    """GOLDPremium: must appear exactly once in a formatted message."""
    import alerts.telegram as tg

    captured = []
    original = tg._send
    tg._send = captured.append

    try:
        tg.send_manual_update(
            world=2400,
            usd=85000,
            fair=194853736,
            lowest=186580000,
            premium=-4.25,
            markets={"test": {"price": 186580000, "status": "OK"}},
        )
        assert len(captured) == 1
        message = captured[0]
        count = message.count("GOLDPremium:")
        assert count == 1, f"Expected 1 GOLDPremium:, found {count}"
    finally:
        tg._send = original


def test_canonical_terminology():
    """Legacy momentum phrases must not appear; canonical terms must."""
    momentum = {
        "premium_vs_today": {"diff": -0.5, "count": 5},
        "verbal_direction": "Toward Buy",
    }
    block = format_momentum_block(momentum)
    text = "\n".join(block)
    assert "Discount Deepening" not in text, f"Legacy phrase found: {text}"
    assert "Premium Expanding" not in text, f"Legacy phrase found: {text}"
    assert "Discount Widening" in text or "Premium Widening" in text or "STABLE" in text


def test_candidate_preserved():
    """Candidate decision must be visible in Telegram output."""
    state = SignalState(
        premium=-3.0,
        fair_price=100.0,
        lowest_price=90.0,
        valuation="CHEAP",
        momentum="IMPROVING",
        premium_direction="DISCOUNT_WIDENING",
        structure="DISCOUNT_DOMINANT",
        conflict="SUPPORTIVE",
        candidate_decision="BUY",
        final_decision="BUY",
        reason="Test",
    )
    text = format_decision_section(state)
    assert "Candidate:" in text
    assert "BUY" in text


def test_final_preserved():
    """Final decision must be visible in Telegram output."""
    state = SignalState(
        premium=-3.0,
        fair_price=100.0,
        lowest_price=90.0,
        valuation="CHEAP",
        momentum="IMPROVING",
        premium_direction="DISCOUNT_WIDENING",
        structure="DISCOUNT_DOMINANT",
        conflict="SUPPORTIVE",
        candidate_decision="BUY",
        final_decision="BUY",
        reason="Test",
    )
    text = format_decision_section(state)
    assert "Final:" in text


def test_candidate_final_can_differ():
    """Hysteresis must cause candidate and final to legitimately differ."""
    markets = {
        "a": {"price": 90.0, "status": "OK"},
        "b": {"price": 95.0, "status": "OK"},
        "c": {"price": 110.0, "status": "OK"},
    }
    # First alert: candidate=BUY, final=BUY (no last_alert)
    state1 = build_signal_state(
        premium=-3.0,
        fair_price=100.0,
        lowest_price=90.0,
        markets=markets,
        previous_premium=-2.0,
        thresholds={"buy_premium": -1.5, "sell_premium": 2.0},
        last_alert=None,
    )
    assert state1.candidate_decision == "BUY"
    assert state1.final_decision == "BUY"

    # Second alert with same last_alert: candidate=BUY, final=WAIT (hysteresis)
    state2 = build_signal_state(
        premium=-3.5,
        fair_price=100.0,
        lowest_price=90.0,
        markets=markets,
        previous_premium=-3.0,
        thresholds={"buy_premium": -1.5, "sell_premium": 2.0},
        last_alert="BUY",
    )
    assert state2.candidate_decision == "BUY"
    assert state2.final_decision == "WAIT"
    assert "hysteresis" in state2.reason.lower() or "transition" in state2.reason.lower()


def test_hysteresis_intact():
    """Existing hysteresis behavior must remain unchanged."""
    # BUY → same last_alert = WAIT
    assert apply_hysteresis("BUY", "BUY", {}) == "WAIT"
    # SELL → same last_alert = WAIT
    assert apply_hysteresis("SELL", "SELL", {}) == "WAIT"
    # BUY → no last_alert = BUY
    assert apply_hysteresis("BUY", None, {}) == "BUY"
    # WAIT → any last_alert = WAIT
    assert apply_hysteresis("WAIT", "BUY", {}) == "WAIT"
    assert apply_hysteresis("WAIT", "SELL", {}) == "WAIT"
    assert apply_hysteresis("WAIT", None, {}) == "WAIT"


if __name__ == "__main__":
    tests = [
        test_valuation_cheap,
        test_valuation_expensive,
        test_valuation_fair,
        test_valuation_unknown,
        test_premium_direction_discount_widening,
        test_premium_direction_discount_narrowing,
        test_premium_direction_premium_widening,
        test_premium_direction_premium_narrowing,
        test_premium_direction_stable,
        test_premium_direction_no_previous,
        test_momentum_improving,
        test_momentum_weakening,
        test_momentum_neutral,
        test_structure_discount_dominant,
        test_structure_premium_dominant,
        test_structure_mixed,
        test_structure_insufficient_platforms,
        test_conflict_supportive_buy,
        test_conflict_caution_wait,
        test_conflict_supportive_sell,
        test_conflict_unknown,
        test_hysteresis_cooldown_same_alert,
        test_hysteresis_passes_new_alert,
        test_platform_average,
        test_platform_spread,
        test_build_signal_state_integration,
        # Regression tests
        test_telegram_api_available,
        test_no_duplicate_header,
        test_canonical_terminology,
        test_candidate_preserved,
        test_final_preserved,
        test_candidate_final_can_differ,
        test_hysteresis_intact,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
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
