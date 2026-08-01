"""Unit tests for the signal evaluation engine."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from caluclator.signals import evaluate_signal


def test_no_alert_when_hold_zone():
    """No alert when premium is in neutral zone and no prior alert."""
    result = evaluate_signal(
        current_premium=0.0,
        previous_premium=0.0,
        last_alert_type=None,
        thresholds={"buy_premium_percent": -1.5, "sell_premium_percent": 3.0, "min_change_for_alert": 0.5},
    )
    assert result is None


def test_buy_alert_on_first_entry():
    """First entry into BUY zone triggers alert."""
    result = evaluate_signal(
        current_premium=-2.0,
        previous_premium=0.0,
        last_alert_type=None,
        thresholds={"buy_premium_percent": -1.5, "sell_premium_percent": 3.0, "min_change_for_alert": 0.5},
    )
    assert result is not None
    assert result["signal"] == "BUY"
    assert result["new_alert_type"] == "BUY"


def test_sell_alert_on_first_entry():
    """First entry into SELL zone triggers alert."""
    result = evaluate_signal(
        current_premium=4.0,
        previous_premium=0.0,
        last_alert_type=None,
        thresholds={"buy_premium_percent": -1.5, "sell_premium_percent": 3.0, "min_change_for_alert": 0.5},
    )
    assert result is not None
    assert result["signal"] == "SELL"
    assert result["new_alert_type"] == "SELL"


def test_no_duplicate_alert_same_zone():
    """No duplicate alert when already in BUY zone with small drift."""
    result = evaluate_signal(
        current_premium=-2.0,
        previous_premium=-1.8,
        last_alert_type="BUY",
        thresholds={"buy_premium_percent": -1.5, "sell_premium_percent": 3.0, "min_change_for_alert": 0.5},
    )
    assert result is None


def test_alert_on_significant_drift_same_zone():
    """Alert again if drift within same zone exceeds min_change."""
    result = evaluate_signal(
        current_premium=-3.0,
        previous_premium=-1.8,
        last_alert_type="BUY",
        thresholds={"buy_premium_percent": -1.5, "sell_premium_percent": 3.0, "min_change_for_alert": 0.5},
    )
    assert result is not None
    assert result["signal"] == "BUY"


def test_hold_resets_buy_alert():
    """Entering neutral zone resets BUY alert silently."""
    result = evaluate_signal(
        current_premium=0.0,
        previous_premium=-2.0,
        last_alert_type="BUY",
        thresholds={"buy_premium_percent": -1.5, "sell_premium_percent": 3.0, "min_change_for_alert": 0.5},
    )
    assert result is not None
    assert result["signal"] == "HOLD"
    assert result["new_alert_type"] is None


def test_hold_resets_sell_alert():
    """Entering neutral zone resets SELL alert silently."""
    result = evaluate_signal(
        current_premium=1.0,
        previous_premium=4.0,
        last_alert_type="SELL",
        thresholds={"buy_premium_percent": -1.5, "sell_premium_percent": 3.0, "min_change_for_alert": 0.5},
    )
    assert result is not None
    assert result["signal"] == "HOLD"
    assert result["new_alert_type"] is None


def test_reentry_after_reset():
    """Re-entry into BUY zone after reset triggers new alert."""
    # First, reset
    evaluate_signal(
        current_premium=0.0,
        previous_premium=-2.0,
        last_alert_type="BUY",
        thresholds={"buy_premium_percent": -1.5, "sell_premium_percent": 3.0, "min_change_for_alert": 0.5},
    )
    # Then re-enter
    result = evaluate_signal(
        current_premium=-2.0,
        previous_premium=0.0,
        last_alert_type=None,
        thresholds={"buy_premium_percent": -1.5, "sell_premium_percent": 3.0, "min_change_for_alert": 0.5},
    )
    assert result is not None
    assert result["signal"] == "BUY"


def test_exactly_at_threshold():
    """Exactly at BUY threshold should trigger."""
    result = evaluate_signal(
        current_premium=-1.5,
        previous_premium=0.0,
        last_alert_type=None,
        thresholds={"buy_premium_percent": -1.5, "sell_premium_percent": 3.0, "min_change_for_alert": 0.5},
    )
    assert result is not None
    assert result["signal"] == "BUY"


def test_no_alert_when_no_prior_and_neutral():
    """No alert in neutral zone even with drift, when no prior alert."""
    result = evaluate_signal(
        current_premium=2.0,
        previous_premium=0.0,
        last_alert_type=None,
        thresholds={"buy_premium_percent": -1.5, "sell_premium_percent": 3.0, "min_change_for_alert": 0.5},
    )
    assert result is None


if __name__ == "__main__":
    test_no_alert_when_hold_zone()
    test_buy_alert_on_first_entry()
    test_sell_alert_on_first_entry()
    test_no_duplicate_alert_same_zone()
    test_alert_on_significant_drift_same_zone()
    test_hold_resets_buy_alert()
    test_hold_resets_sell_alert()
    test_reentry_after_reset()
    test_exactly_at_threshold()
    test_no_alert_when_no_prior_and_neutral()
    print("All signal tests passed.")
