"""Signal evaluation — threshold logic with hysteresis cooldown.

SP-A CHANGES:
- Preserves existing evaluate_signal() for backward compatibility.
- Adds apply_hysteresis() for the new SignalState pipeline.
- Adds evaluate_market_state() as new entry point.
"""

from datetime import datetime, timedelta
from typing import Optional


# ---------------------------------------------------------------------------
# EXISTING FUNCTION — PRESERVED (main.py + test_signals.py depend on this)
# ---------------------------------------------------------------------------

def evaluate_signal(
    current_premium: float,
    previous_premium: float,
    last_alert_type: Optional[str],
    thresholds: dict,
) -> Optional[dict]:
    """Legacy signal evaluator — preserved for existing callers.

    Args:
        current_premium: current premium percentage
        previous_premium: previous premium percentage
        last_alert_type: last alert that was sent ("BUY", "SELL", or None)
        thresholds: dict with buy_premium_percent, sell_premium_percent,
                    min_change_for_alert

    Returns:
        None if no alert should be sent,
        or {"signal": str, "new_alert_type": str|None, "reason": str}
    """
    buy_threshold = thresholds.get("buy_premium_percent", -1.5)
    sell_threshold = thresholds.get("sell_premium_percent", 3.0)
    min_change = thresholds.get("min_change_for_alert", 0.5)

    # Determine zone
    if current_premium <= buy_threshold:
        zone = "BUY"
    elif current_premium >= sell_threshold:
        zone = "SELL"
    else:
        zone = "HOLD"

    # Neutral zone — reset any active alert
    if zone == "HOLD":
        if last_alert_type in ("BUY", "SELL"):
            return {
                "signal": "HOLD",
                "new_alert_type": None,
                "reason": (
                    f"Premium returned to neutral zone ({current_premium:.2f}%). "
                    "Alert reset."
                ),
            }
        return None

    # zone is BUY or SELL
    if last_alert_type == zone:
        if previous_premium is not None:
            drift = abs(current_premium - previous_premium)
            if drift < min_change:
                return None  # Suppress — not enough change

    reason = f"Premium {current_premium:.2f}% — {zone} threshold triggered."
    return {
        "signal": zone,
        "new_alert_type": zone,
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# SP-A ADDITION: apply_hysteresis
# ---------------------------------------------------------------------------

def apply_hysteresis(
    candidate: str,
    last_alert: Optional[str],
    thresholds: dict,
) -> str:
    """Apply simple hysteresis gate to candidate decision.

    If candidate == last_alert, suppress to WAIT (cooldown).
    Otherwise pass through unchanged.

    Args:
        candidate: BUY | WAIT | SELL | UNKNOWN from conflict matrix
        last_alert: last alert that was actually sent (BUY | SELL | None)
        thresholds: config dict (cooldown_hours reserved for future use)

    Returns:
        final decision after hysteresis gate
    """
    if candidate not in ("BUY", "SELL"):
        return candidate if candidate else "WAIT"

    if last_alert == candidate:
        return "WAIT"

    return candidate


# ---------------------------------------------------------------------------
# SP-A ADDITION: evaluate_market_state
# ---------------------------------------------------------------------------

def evaluate_market_state(signal_state) -> str:
    """New entry point — returns final decision from a computed SignalState.

    Args:
        signal_state: fully populated SignalState from build_signal_state()

    Returns:
        final_decision string (BUY | WAIT | SELL | UNKNOWN)
    """
    return signal_state.final_decision
