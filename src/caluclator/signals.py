from typing import Optional


def evaluate_signal(
    current_premium: float,
    previous_premium: float,
    last_alert_type: Optional[str],
    thresholds: dict,
):
    """
    BUY / SELL / HOLD evaluator with hysteresis.

    Returns:

    None

    OR

    {
        signal,
        reason,
        new_alert_type
    }
    """

    buy_thr = thresholds.get("buy_premium_percent", -2.0)
    sell_thr = thresholds.get("sell_premium_percent", 5.0)
    min_change = thresholds.get("min_change_for_alert", 1.0)

    buy_reset = buy_thr + 0.5
    sell_reset = sell_thr - 0.5

    if current_premium <= buy_thr:

        if (
            last_alert_type != "BUY"
            or abs(current_premium - previous_premium) >= min_change
        ):
            return {
                "signal": "BUY",
                "reason": (
                    f"Premium {current_premium:.2f}% "
                    f"is below BUY threshold ({buy_thr:.2f}%)."
                ),
                "new_alert_type": "BUY",
            }

    elif current_premium >= sell_thr:

        if (
            last_alert_type != "SELL"
            or abs(current_premium - previous_premium) >= min_change
        ):
            return {
                "signal": "SELL",
                "reason": (
                    f"Premium {current_premium:.2f}% "
                    f"is above SELL threshold ({sell_thr:.2f}%)."
                ),
                "new_alert_type": "SELL",
            }

    elif buy_reset < current_premium < sell_reset:

        if last_alert_type is not None:
            return {
                "signal": "HOLD",
                "reason": (
                    f"Premium normalized ({current_premium:.2f}%)."
                ),
                "new_alert_type": None,
            }

    return None
