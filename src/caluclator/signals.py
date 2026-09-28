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

# How long the same decision is suppressed after it has been alerted.
#
# This is a starting value, not a measured one. Collection runs hourly from 06:00 to
# 21:00 local, and DAY baselines are anchored to the first scheduled reading of the
# day, so one day is the natural unit: at most one alert of a given kind per trading
# day. It should be re-derived from measured zone-episode durations once enough
# history exists to measure them, which resolve_zone_episodes will provide.
DEFAULT_COOLDOWN_HOURS = 24


def apply_hysteresis(
    candidate: str,
    last_alert: Optional[str],
    thresholds: dict,
    last_alert_at: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> str:
    """Suppress a repeat of the same decision until its cooldown has elapsed.

    This gate used to compare the candidate against the last alert and suppress a
    match unconditionally, with `cooldown_hours` noted as reserved for future use.
    The time dimension was never built, so what was designed as "do not repeat the
    same alert within N hours" behaved as "never repeat the same alert". Because
    state.json persists across runs through the Actions cache, and because the latch
    only clears when a *different* alert fires — a SELL, which requires an EXPENSIVE
    valuation that has never once occurred in this market — the suppression was
    permanent. 100 of 100 BUY candidates were held, and final_decision read WAIT on
    every one of 264 stored decisions.

    The consequence reached further than the missing alerts: the decision scorecard
    was scoring a constant against a constant and correctly returning an edge of
    zero. The engine had not been disproven, it had never run.

    Failure here is deliberately open rather than closed. If the last alert's time is
    unknown the cooldown is treated as elapsed, because the alternative reinstates
    exactly the latch above: one missing timestamp would disable alerting forever. A
    duplicate alert is noise; silence is the failure that already cost this project
    a hundred signals.

    Args:
        candidate: BUY | WAIT | SELL | UNKNOWN from conflict matrix
        last_alert: last alert that was actually sent (BUY | SELL | None)
        thresholds: config dict; `cooldown_hours` overrides the default
        last_alert_at: when that alert was sent; None means unknown
        now: injectable clock, so the boundary can be tested without waiting

    Returns:
        final decision after the hysteresis gate
    """
    if candidate not in ("BUY", "SELL"):
        return candidate if candidate else "WAIT"

    if last_alert != candidate:
        return candidate

    if last_alert_at is None:
        return candidate

    cooldown_hours = thresholds.get("cooldown_hours", DEFAULT_COOLDOWN_HOURS)
    elapsed = (now or datetime.utcnow()) - last_alert_at
    if elapsed >= timedelta(hours=cooldown_hours):
        return candidate

    return "WAIT"


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
