"""Signal evaluation — threshold logic with hysteresis cooldown.

SP-A CHANGES:
  - Preserves existing evaluate_signal() for backward compatibility.
  - Extracts apply_hysteresis() so the conflict engine can reuse it.
  - Adds evaluate_market_state() as new entry point for SignalState.
"""

from datetime import datetime, timedelta
from typing import Optional


# ---------------------------------------------------------------------------
# SP-A ADDITION: apply_hysteresis()
# ---------------------------------------------------------------------------

def apply_hysteresis(
    candidate: str,
    last_alert: Optional[str],
    thresholds: dict,
    last_alert_time: Optional[datetime] = None,
) -> str:
    """Apply hysteresis gate to candidate decision.

    Preserves existing evaluate_signal() cooldown behavior:
      - If candidate == BUY and last_alert == BUY within cooldown → WAIT
      - If candidate == SELL and last_alert == SELL within cooldown → WAIT
      - Otherwise pass candidate through unchanged

    Args:
        candidate: candidate decision from conflict matrix (BUY | WAIT | SELL | UNKNOWN)
        last_alert: last alert that was actually sent (BUY | SELL | WAIT | None)
        thresholds: config dict with cooldown_hours (default 24)
        last_alert_time: timestamp of last_alert for cooldown check

    Returns:
        final decision after hysteresis gate
    """
    if candidate not in ("BUY", "SELL"):
        return candidate if candidate else "WAIT"

    if last_alert == candidate and last_alert_time is not None:
        cooldown_hours = thresholds.get("cooldown_hours", 24)
        elapsed = datetime.utcnow() - last_alert_time
        if elapsed < timedelta(hours=cooldown_hours):
            return "WAIT"

    return candidate


# ---------------------------------------------------------------------------
# EXISTING FUNCTION — PRESERVED (SP-A does not change behavior)
# ---------------------------------------------------------------------------

def evaluate_signal(
    premium: float,
    thresholds: dict,
    last_alert: Optional[str] = None,
    last_alert_time: Optional[datetime] = None,
) -> str:
    """Legacy signal evaluator — preserved for existing callers.

    New code should use build_signal_state() from signal_state.py,
    which delegates hysteresis to apply_hysteresis().

    Args:
        premium: current premium percentage
        thresholds: dict with buy_premium, sell_premium, cooldown_hours
        last_alert: last alert decision for cooldown check
        last_alert_time: timestamp of last alert

    Returns:
        BUY | SELL | WAIT
    """
    buy_threshold = thresholds.get("buy_premium", -1.5)
    sell_threshold = thresholds.get("sell_premium", 2.0)

    # Raw threshold candidate
    if premium <= buy_threshold:
        candidate = "BUY"
    elif premium >= sell_threshold:
        candidate = "SELL"
    else:
        return "WAIT"

    # Hysteresis gate
    return apply_hysteresis(candidate, last_alert, thresholds, last_alert_time)


# ---------------------------------------------------------------------------
# SP-A ADDITION: evaluate_market_state()
# ---------------------------------------------------------------------------

def evaluate_market_state(signal_state: "SignalState") -> str:
    """New entry point — returns final decision from a computed SignalState.

    Args:
        signal_state: fully populated SignalState from build_signal_state()

    Returns:
        final_decision string (BUY | WAIT | SELL | UNKNOWN)
    """
    return signal_state.final_decision
