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
from caluclator.trends import get_trend_summary, get_market_spread
from caluclator.sparkline import premium_sparkline

from persistence.state import load_state, save_state

from alerts.resend_mail import (
    send_daily_recap as send_email_recap,
    send_alert as send_email_alert,
)

from alerts.telegram import (
    send_alert as send_telegram_alert,
    send_manual_update as send_telegram_manual,
    send_data_unavailable as send_telegram_unavailable,
    send_processing as send_telegram_processing,
)

from alerts.telegram import send_daily_recap as send_telegram_recap

from validation.data import (
    validate_world_gold,
    validate_usd_rate,
    validate_market_prices,
    validate_fair_price,
)


def load_config():
    with open("config/config.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _fallback_world_from_history(history):
    if not history:
        return None
    last = history[-1]
    ts_str = last.get("timestamp")
    if not ts_str:
        return None
    try:
        ts = datetime.fromisoformat(ts_str)
    except ValueError:
        return None
    now = datetime.now()
    if ts.date() != now.date():
        return None
    age_hours = (now - ts).total_seconds() / 3600
    if age_hours > 6:
        return None
    return last.get("world_gold")


def main():
    config = load_config()
    thresholds = config["thresholds"]
    email_cfg = config["email"]

    state = load_state()
    history = state["history"]
    last_alert = state["last_alert"]
    is_scheduled = os.environ.get("SCHEDULED_RUN", "false").lower() == "true"

    # Previous markets for change calculation
    previous_markets = {}
    if history:
        prev_markets = history[-1].get("markets", {})
        previous_markets = {k: float(v) for k, v in prev_markets.items() if v is not None}


    changes = {}
    if previous_markets:
        for name, info in markets.items():
            if info["status"] == "OK" and name in previous_markets:
                changes[name] = info["price"] - previous_markets[name]
    
    # Heartbeat for manual triggers
    if not is_scheduled:
        try:
            send_telegram_processing()
        except Exception as e:
            print(f"ERROR: Telegram processing heartbeat failed: {e}")

    # Collect
    print("\nCOLLECT")
    print("-" * 40)

    world = get_world_gold_price()
    if world is not None:
        try:
            validate_world_gold(world)
        except Exception as e:
            print(f"  World Gold   validation failed: {e}")
            world = None

    if world is None:
        world = _fallback_world_from_history(history)
        if world:
            print(f"  World Gold   fallback from history: ${world:,.2f} (<6h old)")
        else:
            print("  World Gold   NO DATA")

    try:
        usd = get_usd_sell_rate()
        validate_usd_rate(usd)
    except Exception as e:
        print(f"  USD Rate     FAILED: {e}")
        usd = None

    raw_markets = get_market_prices()

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
        print(f"\nERROR: Market data invalid: {e}. Skipping.")
        return

    # If world gold unavailable
    if world is None:
        print("\nERROR: World gold price unavailable and no recent fallback.")
        try:
            send_telegram_unavailable(
                usd=usd,
                markets=markets,
                reason="World gold price unavailable. All APIs failed and no recent cached data.",
            )
        except Exception as e:
            print(f"ERROR: Telegram unavailable msg failed: {e}")

        if usd is not None:
            history.append({
                "timestamp": datetime.now().isoformat(),
                "world_gold": None,
                "usd": usd,
                "fair_price": None,
                "lowest_market": find_lowest_market_price(markets),
                "premium": None,
                "markets": {k: v["price"] for k, v in markets.items() if v["status"] == "OK"},
            })
            limit = thresholds.get("history_limit", 30)
            state["history"] = history[-limit:]
            save_state(state)
        return

    # Calculate
    fair = calculate_fair_price(world, usd) * 10

    try:
        validate_fair_price(fair)
    except Exception as e:
        print(f"\nERROR: Fair price invalid: {e}. Skipping.")
        return

    lowest = find_lowest_market_price(markets)
    if lowest is None:
        print("\nERROR: No market data available. Skipping.")
        return

    premium = premium_percent(fair, lowest)

    # Trends
    trends = get_trend_summary(history)
    spark = premium_sparkline(history, width=20)

    # Market spread
    spread, high_name, low_name = get_market_spread(markets)

    # Previous premium
    if history:
        previous_premium = history[-1]["premium"]
        if previous_premium is None:
            previous_premium = premium
    else:
        previous_premium = premium

    # Signal
    signal = evaluate_signal(
        current_premium=premium,
        previous_premium=previous_premium,
        last_alert_type=last_alert,
        thresholds=thresholds,
    )

    # Console output
    print("\nCALCULATE")
    print("-" * 40)
    for name in sorted(markets.keys()):
        info = markets[name]
        print(f"  {name:<15} {info['price']:>15,.0f}")
    print(f"  {'-' * 32}")
    print(f"  Fair Price: {fair:,.0f}")
    print(f"  Lowest:     {lowest:,.0f}")
    print(f"  Premium:    {premium:.2f}%")
    if spread is not None:
        print(f"  Spread:     {spread:,.0f} ({high_name} vs {low_name})")

    print("\nTRENDS")
    print("-" * 40)
    if trends.get("arrow_pct") is not None:
        print(f"  Fair Price Trend: {trends['arrow']} ({trends['arrow_pct']:+.2f}%)")
    if trends.get("vs_yesterday_pct") is not None:
        print(f"  vs Yesterday:     {trends['vs_yesterday_pct']:+.2f}%")
    if trends.get("ma7") is not None:
        print(f"  7-Day Avg Fair:   {trends['ma7']:,.0f}")

    print(f"\nLast Alert: {last_alert}")

    if signal:
        print("\nSIGNAL")
        print("-" * 40)
        print(f"  {signal['signal']}")
        print(f"  {signal['reason']}")

    # History
    history.append({
        "timestamp": datetime.now().isoformat(),
        "world_gold": world,
        "usd": usd,
        "fair_price": fair,
        "lowest_market": lowest,
        "premium": premium,
        "markets": {k: v["price"] for k, v in markets.items() if v["status"] == "OK"},
    })

    limit = thresholds.get("history_limit", 30)
    history = history[-limit:]
    state["history"] = history

    # Alert history
    if signal:
        state["last_alert"] = signal["new_alert_type"]
        state["alert_history"].append({
            "timestamp": datetime.now().isoformat(),
            "signal": signal["signal"],
            "premium": premium,
            "reason": signal["reason"],
        })

    save_state(state)

    # Alerts
    should_send_alert = (
        signal
        and signal["signal"] in ("BUY", "SELL")
        and email_cfg.get("send_alerts", True)
    )

    if should_send_alert:
        try:
            send_email_alert(signal, world, usd, fair, lowest, premium, markets,
                             trends=trends, previous_markets=previous_markets)
        except Exception as e:
            print(f"ERROR: Email alert failed: {e}")
        try:
            send_telegram_alert(signal, world, usd, fair, lowest, premium, markets,
                                trends=trends, sparkline=spark, previous_markets=previous_markets)
        except Exception as e:
            print(f"ERROR: Telegram alert failed: {e}")

    # Daily Report
    if email_cfg.get("send_daily_recap", True) and is_scheduled:
        try:
            send_email_recap(world, usd, fair, lowest, premium, markets,
                             trends=trends, previous_markets=previous_markets)
        except Exception as e:
            print(f"ERROR: Email daily recap failed: {e}")
        try:
            send_telegram_recap(world, usd, fair, lowest, premium, markets,
                                trends=trends, sparkline=spark, previous_markets=previous_markets)
        except Exception as e:
            print(f"ERROR: Telegram daily recap failed: {e}")

    # Manual Update
    if not is_scheduled and not should_send_alert:
        try:
            send_telegram_manual(world, usd, fair, lowest, premium, markets,
                                 trends=trends, sparkline=spark, previous_markets=previous_markets)
        except Exception as e:
            print(f"ERROR: Telegram manual update failed: {e}")


if __name__ == "__main__":
    main()
