import json
import os
from datetime import datetime
from dataclasses import replace

from collector.kitco import get_world_gold_price
from collector.bonbast import get_usd_sell_rate
from collector.iran import get_market_prices

from caluclator.gold import (
    calculate_fair_price,
    find_lowest_market_price,
    premium_percent,
)

from caluclator.signals import evaluate_signal
from caluclator.signal_state import build_signal_state, SignalState
from caluclator.trends import get_trend_summary, get_market_spread
from caluclator.momentum import build_momentum_context

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

from database.connection import get_session
from database.repository import (
    save_market_snapshot,
    save_market_state,
    save_price_observation,
)

from intelligence.freshness import evaluate_freshness

###### End of Imports

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


def _generate_collection_run_id():
    """Generate a deterministic collection run ID for traceability."""
    return f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


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
            print(f" World Gold validation failed: {e}")
            world = None

    if world is None:
        world = _fallback_world_from_history(history)
        if world:
            print(f" World Gold fallback from history: ${world:,.2f} (<6h old)")
        else:
            print(" World Gold NO DATA")

    try:
        usd = get_usd_sell_rate()
        validate_usd_rate(usd)
    except Exception as e:
        print(f" USD Rate FAILED: {e}")
        usd = None

    raw_markets = get_market_prices()

    for name, info in raw_markets.items():
        status = info.get("status", "UNKNOWN")
        if status == "OK":
            print(f" {name:<15} OK")
        else:
            err = status.replace("ERROR: ", "") if status.startswith("ERROR: ") else status
            print(f" {name:<15} {err}")

    try:
        markets = validate_market_prices(raw_markets)
    except Exception as e:
        print(f"\nERROR: Market data invalid: {e}. Skipping.")
        return

    # Compute per-platform changes for database and notifications
    platform_changes = {}
    if previous_markets:
        for name, info in markets.items():
            if info["status"] == "OK" and name in previous_markets:
                platform_changes[name] = info["price"] - previous_markets[name]

    # If world gold unavailable
    if world is None:
        print("\nERROR: World gold price unavailable and no recent cached data.")
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

    # Market spread
    spread, high_name, low_name = get_market_spread(markets)

    # Previous premium
    if history:
        previous_premium = history[-1]["premium"]
        if previous_premium is None:
            previous_premium = premium
    else:
        previous_premium = premium

    # Legacy signal (preserved for backward compatibility)
    signal = evaluate_signal(
        current_premium=premium,
        previous_premium=previous_premium,
        last_alert_type=last_alert,
        thresholds=thresholds,
    )

    # SP-A: Build signal state (snapshot_id placeholder — updated after DB save)
    signal_state = build_signal_state(
        premium=premium,
        fair_price=fair,
        lowest_price=lowest,
        markets=markets,
        previous_premium=previous_premium,
        thresholds=thresholds,
        last_alert=last_alert,
        snapshot_id=0,
    )

    # Momentum + Input Directions (DB-backed, non-blocking)
    momentum = None
    input_directions = None
    try:
        session = get_session()
        if session:
            momentum = build_momentum_context(premium, session)
            from database.repository import get_input_directions
            input_directions = get_input_directions(world, usd, session)
            session.close()
    except Exception as e:
        print(f"Momentum/Directions build failed: {e}")

    # Console output
    print("\nCALCULATE")
    print("-" * 40)
    for name in sorted(markets.keys()):
        info = markets[name]
        print(f" {name:<15} {info['price']:>15,.0f}")
    print(f" {'-' * 32}")
    print(f" Fair Price: {fair:,.0f}")
    print(f" Lowest: {lowest:,.0f}")
    print(f" Premium: {premium:.2f}%")
    if spread is not None:
        print(f" Spread: {spread:,.0f} ({high_name} vs {low_name})")

    print("\nTRENDS")
    print("-" * 40)
    if trends.get("arrow_pct") is not None:
        print(f" Fair Price Trend: {trends['arrow']} ({trends['arrow_pct']:+.2f}%)")
    if trends.get("vs_yesterday_pct") is not None:
        print(f" vs Yesterday: {trends['vs_yesterday_pct']:+.2f}%")
    if trends.get("ma7") is not None:
        print(f" 7-Day Avg Fair: {trends['ma7']:,.0f}")

    if momentum:
        print("\nMOMENTUM")
        print("-" * 40)
        vs_today = momentum.get("premium_vs_today")
        vs_yesterday = momentum.get("premium_vs_yesterday")
        if vs_today:
            print(f" Premium vs today: {vs_today['diff']:+.2f}% ({vs_today['label']})")
        if vs_yesterday:
            print(f" Premium vs yesterday: {vs_yesterday['diff']:+.2f}%")
        print(f" Direction: {momentum.get('verbal_direction', 'Neutral')}")

    if input_directions:
        print("\nINPUT DIRECTIONS")
        print("-" * 40)
        wd = input_directions.get("world")
        if wd:
            print(f" World Gold: {wd['arrow']} ({wd['pct']:+.2f}%) stale={wd['stale_count']}")
        ud = input_directions.get("usd")
        if ud:
            print(f" USD: {ud['arrow']} ({ud['pct']:+.2f}%) stale={ud['stale_count']}")

    # SP-A console output
    print("\nSP-A STATE")
    print("-" * 40)
    print(f" Valuation:   {signal_state.valuation}")
    print(f" Momentum:    {signal_state.momentum} ({signal_state.premium_direction})")
    print(f" Structure:   {signal_state.structure}")
    print(f" Conflict:    {signal_state.conflict}")
    print(f" Candidate:   {signal_state.candidate_decision}")
    print(f" Final:       {signal_state.final_decision}")

    print(f"\nLast Alert: {last_alert}")

    if signal:
        print("\nSIGNAL")
        print("-" * 40)
        print(f" {signal['signal']}")
        print(f" {signal['reason']}")

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

    # Save to database (non-blocking)
    snapshot_id = None
    try:
        platform_prices = []
        for name, info in markets.items():
            if info["status"] == "OK":
                platform_prices.append({
                    "platform_name": name,
                    "price_irr": info["price"],
                    "change_irr": platform_changes.get(name),
                })

        snapshot_id = save_market_snapshot(
            timestamp=datetime.now(),
            fair_price=fair,
            premium_percent=premium,
            world_gold_usd=world,
            usd_irr=usd,
            signal=signal_state.final_decision,
            confidence=None,
            platform_prices=platform_prices,
        )
        print("\nDB: Snapshot saved")
    except Exception as e:
        print(f"\nDB ERROR (snapshot): {e}")

    # SP-A: Save interpreted market state
    if snapshot_id is not None:
        try:
            signal_state = replace(signal_state, snapshot_id=snapshot_id)
            save_market_state(signal_state)
            print("DB: Market state saved")
        except Exception as e:
            print(f"DB ERROR (market state): {e}")

    # Alerts
    should_send_alert = (
        signal
        and signal["signal"] in ("BUY", "SELL")
        and email_cfg.get("send_alerts", True)
    )

    if should_send_alert:
        try:
            send_email_alert(
                signal, world, usd, fair, lowest, premium, markets,
                trends=trends, momentum=momentum, previous_markets=previous_markets
            )
        except Exception as e:
            print(f"ERROR: Email alert failed: {e}")
        try:
            send_telegram_alert(
                signal, world, usd, fair, lowest, premium, markets,
                trends=trends, momentum=momentum, previous_markets=previous_markets,
                input_directions=input_directions,
                signal_state=signal_state,
            )
        except Exception as e:
            print(f"ERROR: Telegram alert failed: {e}")

    # Daily Report
    if email_cfg.get("send_daily_recap", True) and is_scheduled:
        try:
            send_email_recap(
                world, usd, fair, lowest, premium, markets,
                trends=trends, momentum=momentum, previous_markets=previous_markets
            )
        except Exception as e:
            print(f"ERROR: Email daily recap failed: {e}")
        try:
            send_telegram_recap(
                world, usd, fair, lowest, premium, markets,
                trends=trends, momentum=momentum, previous_markets=previous_markets,
                input_directions=input_directions,
                signal_state=signal_state,
            )
        except Exception as e:
            print(f"ERROR: Telegram daily recap failed: {e}")

    # Manual Update
    if not is_scheduled and not should_send_alert:
        try:
            send_telegram_manual(
                world, usd, fair, lowest, premium, markets,
                trends=trends, momentum=momentum, previous_markets=previous_markets,
                input_directions=input_directions,
                signal_state=signal_state,
            )
        except Exception as e:
            print(f"ERROR: Telegram manual update failed: {e}")


if __name__ == "__main__":
    main()
