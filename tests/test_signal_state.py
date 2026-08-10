"""Unit tests for SP-A signal intelligence layer.

20 deterministic tests covering:
- Valuation engine
- Premium direction terminology
- Momentum mapping
- Structure consensus
- Conflict matrix
- Hysteresis gate
- Platform statistics
- Integration pipeline
"""

import pytest
from datetime import datetime

from src.caluclator.valuation import evaluate_valuation
from src.caluclator.momentum import get_premium_direction, evaluate_momentum
from src.caluclator.structure import evaluate_structure
from src.caluclator.conflict import evaluate_conflict, build_reason
from src.caluclator.signal_state import SignalState, build_signal_state
from src.caluclator.signals import apply_hysteresis


# ---------------------------------------------------------------------------
# Valuation tests (3)
# ---------------------------------------------------------------------------

class TestValuation:
    def test_valuation_cheap(self):
        assert evaluate_valuation(-4.0, {"buy_premium": -1.5, "sell_premium": 2.0}) == "CHEAP"

    def test_valuation_expensive(self):
        assert evaluate_valuation(3.0, {"buy_premium": -1.5, "sell_premium": 2.0}) == "EXPENSIVE"

    def test_valuation_fair(self):
        assert evaluate_valuation(0.5, {"buy_premium": -1.5, "sell_premium": 2.0}) == "FAIR"

    def test_valuation_none_returns_unknown(self):
        assert evaluate_valuation(None, {"buy_premium": -1.5, "sell_premium": 2.0}) == "UNKNOWN"


# ---------------------------------------------------------------------------
# Premium direction tests (5)
# ---------------------------------------------------------------------------

class TestPremiumDirection:
    def test_discount_widening(self):
        assert get_premium_direction(-5.0, -4.0) == "DISCOUNT_WIDENING"

    def test_discount_narrowing(self):
        assert get_premium_direction(-4.0, -5.0) == "DISCOUNT_NARROWING"

    def test_discount_stable(self):
        assert get_premium_direction(-4.02, -4.0) == "DISCOUNT_STABLE"

    def test_premium_widening(self):
        assert get_premium_direction(3.0, 2.0) == "PREMIUM_WIDENING"

    def test_premium_narrowing(self):
        assert get_premium_direction(2.0, 3.0) == "PREMIUM_NARROWING"

    def test_premium_stable(self):
        assert get_premium_direction(2.02, 2.0) == "PREMIUM_STABLE"

    def test_no_previous_defaults_stable(self):
        assert get_premium_direction(-3.0, None) == "DISCOUNT_STABLE"
        assert get_premium_direction(3.0, None) == "PREMIUM_STABLE"


# ---------------------------------------------------------------------------
# Momentum tests (3)
# ---------------------------------------------------------------------------

class TestMomentum:
    def test_momentum_improving_discount_widening(self):
        assert evaluate_momentum("DISCOUNT_WIDENING") == "IMPROVING"

    def test_momentum_improving_premium_narrowing(self):
        assert evaluate_momentum("PREMIUM_NARROWING") == "IMPROVING"

    def test_momentum_weakening_discount_narrowing(self):
        assert evaluate_momentum("DISCOUNT_NARROWING") == "WEAKENING"

    def test_momentum_weakening_premium_widening(self):
        assert evaluate_momentum("PREMIUM_WIDENING") == "WEAKENING"

    def test_momentum_neutral_stable(self):
        assert evaluate_momentum("DISCOUNT_STABLE") == "NEUTRAL"
        assert evaluate_momentum("PREMIUM_STABLE") == "NEUTRAL"

    def test_momentum_unknown_unrecognized(self):
        assert evaluate_momentum("GIBBERISH") == "UNKNOWN"


# ---------------------------------------------------------------------------
# Structure tests (5)
# ---------------------------------------------------------------------------

class TestStructure:
    def test_structure_discount_dominant(self):
        markets = {f"p{i}": {"price": 90.0, "status": "OK"} for i in range(6)}
        markets.update({f"p{i}": {"price": 110.0, "status": "OK"} for i in range(6, 10)})
        result = evaluate_structure(markets, fair_price=100.0)
        assert result["state"] == "DISCOUNT_DOMINANT"
        assert result["platforms_below_fair"] == 6
        assert result["platforms_above_fair"] == 4

    def test_structure_premium_dominant(self):
        markets = {f"p{i}": {"price": 200.0, "status": "OK"} for i in range(6)}
        markets.update({f"p{i}": {"price": 100.0, "status": "OK"} for i in range(6, 10)})
        result = evaluate_structure(markets, fair_price=150.0)
        assert result["state"] == "PREMIUM_DOMINANT"
        assert result["platforms_below_fair"] == 4
        assert result["platforms_above_fair"] == 6

    def test_structure_mixed(self):
        markets = {f"p{i}": {"price": 100.0, "status": "OK"} for i in range(4)}
        markets.update({f"p{i}": {"price": 200.0, "status": "OK"} for i in range(4, 9)})
        result = evaluate_structure(markets, fair_price=150.0)
        assert result["state"] == "MIXED"

    def test_structure_insufficient_platforms(self):
        markets = {"p1": {"price": 100.0, "status": "OK"}}
        result = evaluate_structure(markets, fair_price=150.0)
        assert result["state"] == "UNKNOWN"
        assert result["platform_average"] == 0.0

    def test_platform_average(self):
        markets = {
            "p1": {"price": 100.0, "status": "OK"},
            "p2": {"price": 200.0, "status": "OK"},
            "p3": {"price": 300.0, "status": "OK"},
        }
        result = evaluate_structure(markets, fair_price=200.0)
        assert result["platform_average"] == 200.0
        assert result["platform_high"] == 300.0
        assert result["platform_low"] == 100.0
        assert result["platform_spread"] == 200.0

    def test_structure_ignores_non_ok(self):
        markets = {
            "ok1": {"price": 100.0, "status": "OK"},
            "ok2": {"price": 200.0, "status": "OK"},
            "bad": {"price": 150.0, "status": "ERROR"},
        }
        result = evaluate_structure(markets, fair_price=150.0)
        assert result["state"] == "MIXED"
        assert result["platforms_below_fair"] == 1
        assert result["platforms_above_fair"] == 1


# ---------------------------------------------------------------------------
# Conflict matrix tests (10 rules)
# ---------------------------------------------------------------------------

class TestConflict:
    def test_conflict_supportive_buy_cheap_improving_discount_dominant(self):
        conflict, decision = evaluate_conflict("CHEAP", "IMPROVING", "DISCOUNT_DOMINANT")
        assert conflict == "SUPPORTIVE"
        assert decision == "BUY"

    def test_conflict_supportive_buy_cheap_improving_mixed(self):
        conflict, decision = evaluate_conflict("CHEAP", "IMPROVING", "MIXED")
        assert conflict == "SUPPORTIVE"
        assert decision == "BUY"

    def test_conflict_caution_cheap_improving_premium_dominant(self):
        conflict, decision = evaluate_conflict("CHEAP", "IMPROVING", "PREMIUM_DOMINANT")
        assert conflict == "CAUTION"
        assert decision == "WAIT"

    def test_conflict_caution_cheap_weakening_any(self):
        for struct in ("DISCOUNT_DOMINANT", "MIXED", "PREMIUM_DOMINANT"):
            conflict, decision = evaluate_conflict("CHEAP", "WEAKENING", struct)
            assert conflict == "CAUTION"
            assert decision == "WAIT"

    def test_conflict_neutral_cheap_neutral_any(self):
        for struct in ("DISCOUNT_DOMINANT", "MIXED", "PREMIUM_DOMINANT"):
            conflict, decision = evaluate_conflict("CHEAP", "NEUTRAL", struct)
            assert conflict == "NEUTRAL"
            assert decision == "WAIT"

    def test_conflict_neutral_fair_any_any(self):
        for mom in ("IMPROVING", "NEUTRAL", "WEAKENING"):
            for struct in ("DISCOUNT_DOMINANT", "MIXED", "PREMIUM_DOMINANT"):
                conflict, decision = evaluate_conflict("FAIR", mom, struct)
                assert conflict == "NEUTRAL"
                assert decision == "WAIT"

    def test_conflict_supportive_sell_expensive_weakening_premium_dominant(self):
        conflict, decision = evaluate_conflict("EXPENSIVE", "WEAKENING", "PREMIUM_DOMINANT")
        assert conflict == "SUPPORTIVE_FOR_SELL"
        assert decision == "SELL"

    def test_conflict_supportive_sell_expensive_weakening_mixed(self):
        conflict, decision = evaluate_conflict("EXPENSIVE", "WEAKENING", "MIXED")
        assert conflict == "SUPPORTIVE_FOR_SELL"
        assert decision == "SELL"

    def test_conflict_caution_expensive_improving_any(self):
        for struct in ("DISCOUNT_DOMINANT", "MIXED", "PREMIUM_DOMINANT"):
            conflict, decision = evaluate_conflict("EXPENSIVE", "IMPROVING", struct)
            assert conflict == "CAUTION"
            assert decision == "WAIT"

    def test_conflict_neutral_expensive_neutral_any(self):
        for struct in ("DISCOUNT_DOMINANT", "MIXED", "PREMIUM_DOMINANT"):
            conflict, decision = evaluate_conflict("EXPENSIVE", "NEUTRAL", struct)
            assert conflict == "NEUTRAL"
            assert decision == "WAIT"

    def test_conflict_unknown_unknown_any_any(self):
        for mom in ("IMPROVING", "NEUTRAL", "WEAKENING"):
            for struct in ("DISCOUNT_DOMINANT", "MIXED", "PREMIUM_DOMINANT"):
                conflict, decision = evaluate_conflict("UNKNOWN", mom, struct)
                assert conflict == "UNKNOWN"
                assert decision == "UNKNOWN"


# ---------------------------------------------------------------------------
# Hysteresis tests (4)
# ---------------------------------------------------------------------------

class TestHysteresis:
    def test_hysteresis_passes_buy_when_no_last_alert(self):
        assert apply_hysteresis("BUY", None, {}) == "BUY"

    def test_hysteresis_passes_sell_when_no_last_alert(self):
        assert apply_hysteresis("SELL", None, {}) == "SELL"

    def test_hysteresis_suppresses_repeat_buy(self):
        assert apply_hysteresis("BUY", "BUY", {}) == "WAIT"

    def test_hysteresis_suppresses_repeat_sell(self):
        assert apply_hysteresis("SELL", "SELL", {}) == "WAIT"

    def test_hysteresis_allows_buy_after_sell(self):
        assert apply_hysteresis("BUY", "SELL", {}) == "BUY"

    def test_hysteresis_allows_sell_after_buy(self):
        assert apply_hysteresis("SELL", "BUY", {}) == "SELL"

    def test_hysteresis_wait_passthrough(self):
        assert apply_hysteresis("WAIT", "BUY", {}) == "WAIT"
        assert apply_hysteresis("WAIT", "SELL", {}) == "WAIT"


# ---------------------------------------------------------------------------
# Reason builder tests (3)
# ---------------------------------------------------------------------------

class TestReasonBuilder:
    def test_reason_contains_valuation(self):
        reason = build_reason(
            valuation="CHEAP",
            momentum="IMPROVING",
            premium_direction="DISCOUNT_WIDENING",
            structure="DISCOUNT_DOMINANT",
            conflict="SUPPORTIVE",
        )
        assert "deeply discounted" in reason

    def test_reason_contains_momentum(self):
        reason = build_reason(
            valuation="FAIR",
            momentum="IMPROVING",
            premium_direction="PREMIUM_NARROWING",
            structure="MIXED",
            conflict="NEUTRAL",
        )
        assert "Premium narrowing" in reason

    def test_reason_contains_conflict(self):
        reason = build_reason(
            valuation="CHEAP",
            momentum="WEAKENING",
            premium_direction="DISCOUNT_NARROWING",
            structure="DISCOUNT_DOMINANT",
            conflict="CAUTION",
        )
        assert "caution advised" in reason


# ---------------------------------------------------------------------------
# Integration: build_signal_state (3)
# ---------------------------------------------------------------------------

class TestSignalStateIntegration:
    def test_pipeline_produces_buy(self):
        markets = {f"p{i}": {"price": 90.0, "status": "OK"} for i in range(6)}
        markets.update({f"p{i}": {"price": 110.0, "status": "OK"} for i in range(6, 10)})

        state = build_signal_state(
            premium=-4.0,
            fair_price=100.0,
            lowest_price=85.0,
            markets=markets,
            previous_premium=-3.0,  # widening discount
            thresholds={"buy_premium": -1.5, "sell_premium": 2.0},
            last_alert=None,
            snapshot_id=1,
        )

        assert state.valuation == "CHEAP"
        assert state.premium_direction == "DISCOUNT_WIDENING"
        assert state.momentum == "IMPROVING"
        assert state.structure == "DISCOUNT_DOMINANT"
        assert state.conflict == "SUPPORTIVE"
        assert state.candidate_decision == "BUY"
        assert state.final_decision == "BUY"
        assert state.reason != ""
        assert state.snapshot_id == 1

    def test_pipeline_produces_wait_due_to_hysteresis(self):
        markets = {f"p{i}": {"price": 90.0, "status": "OK"} for i in range(6)}
        markets.update({f"p{i}": {"price": 110.0, "status": "OK"} for i in range(6, 10)})

        state = build_signal_state(
            premium=-4.0,
            fair_price=100.0,
            lowest_price=85.0,
            markets=markets,
            previous_premium=-3.0,
            thresholds={"buy_premium": -1.5, "sell_premium": 2.0},
            last_alert="BUY",  # hysteresis should suppress
            snapshot_id=2,
        )

        assert state.candidate_decision == "BUY"
        assert state.final_decision == "WAIT"

    def test_pipeline_produces_sell(self):
        markets = {f"p{i}": {"price": 110.0, "status": "OK"} for i in range(6)}
        markets.update({f"p{i}": {"price": 90.0, "status": "OK"} for i in range(6, 10)})

        state = build_signal_state(
            premium=3.0,
            fair_price=100.0,
            lowest_price=95.0,
            markets=markets,
            previous_premium=2.5,  # widening premium
            thresholds={"buy_premium": -1.5, "sell_premium": 2.0},
            last_alert=None,
            snapshot_id=3,
        )

        assert state.valuation == "EXPENSIVE"
        assert state.premium_direction == "PREMIUM_WIDENING"
        assert state.momentum == "WEAKENING"
        assert state.structure == "PREMIUM_DOMINANT"
        assert state.conflict == "SUPPORTIVE_FOR_SELL"
        assert state.candidate_decision == "SELL"
        assert state.final_decision == "SELL"
