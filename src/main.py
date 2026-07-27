import json
from datetime import datetime

from collector.kitco import get_world_gold_price
from collector.bonbast import get_usd_sell_rate
from collector.iran import get_market_prices

from caluclator.gold import (
    calculate_fair_price,
    find_lowest_market_price,
    premium_percent,
)

from caluclator.signals import evaluate_signal

from persistence.state import (
    load_state,
    save_state,
)

from alerts.resend_mail import (
    send_daily_recap,
    send_alert,
)


def load_config():

    with open(
        "config/config.json",
        "r",
        encoding="utf-8",
    ) as f:

        return json.load(f)


def main():

    config = load_config()

    thresholds = config["thresholds"]

    email_cfg = config["email"]

    ####################################################
    # Restore memory
    ####################################################

    state = load_state()

    history = state["history"]

    last_alert = state["last_alert"]

    ####################################################
    # Collect
    ####################################################

    world = get_world_gold_price()

    usd = get_usd_sell_rate()

    markets = get_market_prices()

    ####################################################
    # Calculate
    ####################################################

    fair = calculate_fair_price(world, usd) * 10

    lowest = find_lowest_market_price(markets)

    premium = premium_percent(
        fair,
        lowest,
    )

    ####################################################
    # Previous values
    ####################################################

    if history:

        previous_premium = history[-1]["premium"]

    else:

        previous_premium = premium

    ####################################################
    # Signal
    ####################################################

    signal = evaluate_signal(
        current_premium=premium,
        previous_premium=previous_premium,
        last_alert_type=last_alert,
        thresholds=thresholds,
    )

    ####################################################
    # Console
    ####################################################

    print("=" * 60)

    print(f"World Gold : {world:.2f}")

    print(f"USD Sell   : {usd:,}")

    print("-" * 60)

    for name, info in markets.items():

        if info["status"] == "OK":

            print(
                f"{name:<15}"
                f"{info['price']:>15,.0f}"
            )

        else:

            print(
                f"{name:<15}ERROR"
            )

    print("-" * 60)

    print(f"Fair Price : {fair:,.0f}")

    print(f"Lowest     : {lowest:,.0f}")

    print(f"Premium    : {premium:.2f}%")

    print(f"Last Alert : {last_alert}")

    if signal:

        print(signal)

    ####################################################
    # History
    ####################################################

    history.append(
        {
            "timestamp": datetime.now().isoformat(),
            "world_gold": world,
            "usd": usd,
            "fair_price": fair,
            "lowest_market": lowest,
            "premium": premium,
            "markets": {
                k: v["price"]
                for k, v in markets.items()
                if v["status"] == "OK"
            },
        }
    )

    limit = thresholds.get(
        "history_limit",
        30,
    )

    history = history[-limit:]

    state["history"] = history

    ####################################################
    # Alert history
    ####################################################

    if signal:

        state["last_alert"] = signal["new_alert_type"]

        state["alert_history"].append(
            {
                "timestamp": datetime.now().isoformat(),
                "signal": signal["signal"],
                "premium": premium,
                "reason": signal["reason"],
            }
        )

    ####################################################
    # Save
    ####################################################

    save_state(state)

    ####################################################
    # Alert Email
    ####################################################

    if (
        signal
        and signal["signal"] in ("BUY", "SELL")
        and email_cfg.get(
            "send_alerts",
            True,
        )
    ):

        send_alert(
            signal,
            world,
            usd,
            fair,
            lowest,
            premium,
            markets,
        )

    ####################################################
    # Daily Report
    ####################################################

    if email_cfg.get(
        "send_daily_recap",
        True,
    ):

        send_daily_recap(
            world,
            usd,
            fair,
            lowest,
            premium,
            markets,
        )


if __name__ == "__main__":
    main()
