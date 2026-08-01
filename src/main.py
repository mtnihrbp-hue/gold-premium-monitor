import json
import os
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
from caluclator.trends import get_trend_summary
from caluclator.sparkline import premium_sparkline

from persistence.state import (
    load_state,
    save_state,
)

from alerts.resend_mail import (
    send_daily_recap as send_email_recap,
    send_alert as send_email_alert,
)

from alerts.telegram import (
    send_alert as send_telegram_alert,
)

from alerts.telegram import send_daily_recap as send_telegram_recap

from validation.data import (
    validate_world_gold,
    validate_usd_rate,
    validate_market_prices,
    validate_fair_price,
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

    try:
        world = get_world_gold_price()
        validate_world_gold(world)
    except Exception as e:
        print(f"ERROR: World gold price invalid: {e}. Skipping.")
        return

    try:
        usd = get_usd_sell_rate()
        validate_usd_rate(usd)
    except Exception as e:
        print(f"ERROR: USD rate invalid: {e}. Skipping.")
        return

    raw_markets = get_market_prices()

    print("\nCOLLECT")
    print("-" * 40)
    for name, info in raw_markets.items():
        status = info.get("status", "UNKNOWN")
        if status == "OK":
            print(f"  {name:<15} OK")
        else:
            err = status.replace("ERROR: ", "") if status.startswith("ERROR: ") else status
            print(f"  {name:<15} {err}")

    try:
        markets = validate_market_prices(raw_markets)
    except Exception as e:
        print(f"ERROR: Market data invalid: {e}. Skipping.")
        return

    ####################################################
    # Calculate
    ####################################################

    fair = calculate_fair_price(world, usd) * 10

    try:
        validate_fair_price(fair)
    except Exception as e:
        print(f"ERROR: Fair price invalid: {e}. Skipping.")
        return

    lowest = find_lowest_market_price(markets)
    if lowest is None:
        print("ERROR: No market data available. Skipping.")
        return

    premium = premium_percent(fair, lowest)

    ####################################################
    # Trends
    ####################################################

    trends = get_trend_summary(history)
    spark = premium_sparkline(history, width=20)
    trends["sparkline"] = spark

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
    # Console output
    ####################################################

    print("\nCALCULATE")
    print("-" * 40)
    for name, info in markets.items():
        print(f"  {name:<15} {info['price']:>15,.0f}")
    print(f"  {'-' * 32}")
    print(f"  Fair Price: {fair:,.0f}")
    print(f"  Lowest:     {lowest:,.0f}")
    print(f"  Premium:    {premium:.2f}%")

    print("\nTRENDS")
    print("-" * 40)
    print(f"  Recent Trend: {trends['arrow']} ({trends['arrow_diff']:.2f}%)")
    if trends["ma7"] is not None:
        print(f"  7-Day MA:     {trends['ma7']:.2f}%")

    print(f"\nLast Alert: {last_alert}")

    if signal:
        print("\nSIGNAL")
        print("-" * 40)
        print(f"  {signal['signal']}")
        print(f"  {signal['reason']}")

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

    limit = thresholds.get("history_limit", 30)
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
    # Alert Email + Telegram (isolated)
    ####################################################

    should_send_alert = (
        signal
        and signal["signal"] in ("BUY", "SELL")
        and email_cfg.get("send_alerts", True)
    )

    if should_send_alert:
        try:
            send_email_alert(
                signal, world, usd, fair, lowest, premium, markets, trends=trends,
            )
        except Exception as e:
            print(f"ERROR: Email alert failed: {e}")

        try:
            send_telegram_alert(
                signal, world, usd, fair, lowest, premium, markets, trends=trends,
            )
        except Exception as e:
            print(f"ERROR: Telegram alert failed: {e}")

    ####################################################
    # Daily Report (isolated, scheduled only)
    ####################################################

    is_scheduled = os.environ.get("SCHEDULED_RUN", "false").lower() == "true"

    if email_cfg.get("send_daily_recap", True) and is_scheduled:
        try:
            send_email_recap(world, usd, fair, lowest, premium, markets, trends=trends)
        except Exception as e:
            print(f"ERROR: Email daily recap failed: {e}")

        try:
            send_telegram_recap(world, usd, fair, lowest, premium, markets, trends=trends)
        except Exception as e:
            print(f"ERROR: Telegram daily recap failed: {e}")


if __name__ == "__main__":
    main()
