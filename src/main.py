import json
import os
from datetime import datetime
from dataclasses import replace

from collector.kitco import get_world_gold_price
from collector.bonbast import get_usd_sell_rate
from collector.iran import get_market_prices
from analysis.snapshot_builder import build_analysis_snapshot
from collector.news.ingest import run_news_ingestion

from caluclator.gold import calculate_fair_price, find_lowest_market_price, premium_percent
from caluclator.signal_state import build_signal_state
from caluclator.trends import get_trend_summary, get_market_spread
from caluclator.momentum import build_momentum_context
from persistence.state import load_state, save_state

from alerts.resend_mail import send_daily_recap as send_email_recap, send_alert as send_email_alert
from alerts.telegram import (
    send_alert as send_telegram_alert,
    send_manual_update as send_telegram_manual,
    send_data_unavailable as send_telegram_unavailable,
    send_processing as send_telegram_processing,
    send_daily_recap as send_telegram_recap,
)
from alerts.telegram_update_v1 import send_update_v1
from validation.data import validate_world_gold, validate_usd_rate, validate_market_prices, validate_fair_price
from database.connection import get_session
from database.repository import save_market_snapshot, save_market_state, save_price_observation, get_input_directions
from intelligence.freshness import evaluate_freshness
from update.baseline_resolver import resolve_update_baselines


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
    if ts.date() != now.date() or (now - ts).total_seconds() / 3600 > 6:
        return None
    return last.get("world_gold")


def _fallback_world_from_db(max_age_hours=6):
    from database.models import PriceObservation
    from sqlalchemy import desc
    session = get_session()
    if session is None:
        return None
    try:
        obs = session.query(PriceObservation).filter(PriceObservation.instrument == "XAUUSD").order_by(desc(PriceObservation.timestamp)).first()
        if obs is None or obs.price is None:
            return None
        age_hours = (datetime.now() - obs.timestamp).total_seconds() / 3600
        if age_hours > max_age_hours:
            return None
        return float(obs.price)
    except Exception as e:
        print(f" World Gold DB fallback failed: {e}")
        return None
    finally:
        session.close()


def _generate_collection_run_id():
    return f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def _save_price_observations(markets, world, usd, now, stale_threshold, collection_run_id):
    for name, info in markets.items():
        if info.get("status") != "OK":
            continue
        try:
            freshness = evaluate_freshness(now, now, stale_threshold)
            source = name.lower()
            if name == "Goldika" and "buy" in info and "sell" in info:
                for side in ("buy", "sell"):
                    save_price_observation(instrument="REP_IRAN_GOLD", source=source, timestamp=now, price=info[side], freshness=freshness, collection_run_id=collection_run_id, quote_side=side.upper())
            elif info.get("price") is not None:
                save_price_observation(instrument="REP_IRAN_GOLD", source=source, timestamp=now, price=info["price"], freshness=freshness, collection_run_id=collection_run_id, quote_side="SINGLE")
        except Exception as e:
            print(f" Price observation {name} failed: {e}")

    for instrument, source, price in (("XAUUSD", "kitco_fallback", world), ("USD/IRR", "bonbast", usd)):
        if price is None:
            continue
        try:
            freshness = evaluate_freshness(now, now, stale_threshold)
            save_price_observation(instrument=instrument, source=source, timestamp=now, price=price, freshness=freshness, collection_run_id=collection_run_id, quote_side="SINGLE")
        except Exception as e:
            print(f" Price observation {instrument} failed: {e}")


def main():
    config = load_config()
    thresholds = config["thresholds"]
    email_cfg = config["email"]
    state = load_state()
    history = state["history"]
    last_alert = state["last_alert"]
    is_scheduled = os.environ.get("SCHEDULED_RUN", "false").lower() == "true"
    collection_run_id = _generate_collection_run_id()
    now = datetime.now()
    stale_threshold = config.get("freshness", {}).get("stale_threshold_minutes", 15)

    previous_markets = {}
    if history:
        previous_markets = {k: float(v) for k, v in history[-1].get("markets", {}).items() if v is not None}

    if not is_scheduled:
        try:
            send_telegram_processing()
        except Exception as e:
            print(f"ERROR: Telegram processing heartbeat failed: {e}")

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
        world = _fallback_world_from_history(history) or _fallback_world_from_db(max_age_hours=6)

    try:
        usd = get_usd_sell_rate()
        validate_usd_rate(usd)
    except Exception as e:
        print(f" USD Rate FAILED: {e}")
        usd = None

    raw_markets = get_market_prices()
    for name, info in raw_markets.items():
        status = info.get("status", "UNKNOWN")
        print(f" {name:<15} {status.replace('ERROR: ', '') if status.startswith('ERROR: ') else status}")
    try:
        markets = validate_market_prices(raw_markets)
    except Exception as e:
        print(f"\nERROR: Market data invalid: {e}. Skipping.")
        return

    _save_price_observations(markets, world, usd, now, stale_threshold, collection_run_id)

    if world is None:
        send_telegram_unavailable(usd=usd, markets=markets, reason="World gold price unavailable. All APIs failed and no recent cached data.")
        return

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
    trends = get_trend_summary(history)
    spread, high_name, low_name = get_market_spread(markets)
    previous_premium = history[-1].get("premium") if history else premium
    if previous_premium is None:
        previous_premium = premium

    signal_state = build_signal_state(premium=premium, fair_price=fair, lowest_price=lowest, markets=markets, previous_premium=previous_premium, thresholds=thresholds, last_alert=last_alert, snapshot_id=0)
    signal = None
    if signal_state.final_decision in ("BUY", "SELL"):
        signal = {"signal": signal_state.final_decision, "new_alert_type": signal_state.final_decision, "reason": signal_state.reason or f"Final decision: {signal_state.final_decision}."}

    momentum = None
    input_directions = None
    try:
        session = get_session()
        if session:
            momentum = build_momentum_context(premium, session)
            if is_scheduled:
                input_directions = get_input_directions(world, usd, session)
            session.close()
    except Exception as e:
        print(f"Momentum/Directions build failed: {e}")

    baselines = None
    if not is_scheduled:
        try:
            baselines = resolve_update_baselines(current_platform_avg=signal_state.platform_average, current_premium=premium)
            print(f"UPDATE baselines: RUN={'OK' if baselines.run else 'N/A'} DAY={'OK' if baselines.day else 'N/A'}")
        except Exception as e:
            print(f"UPDATE baseline resolution failed: {e}")

    print("\nCALCULATE")
    print("-" * 40)
    for name in sorted(markets.keys()):
        print(f" {name:<15} {markets[name]['price']:>15,.0f}")
    print(" " + "-" * 32)
    print(f" Fair Price: {fair:,.0f}")
    print(f" Lowest: {lowest:,.0f}")
    print(f" Premium: {premium:.2f}%")
    if spread is not None:
        print(f" Spread: {spread:,.0f} ({high_name} vs {low_name})")

    history.append({"timestamp": now.isoformat(), "world_gold": world, "usd": usd, "fair_price": fair, "lowest_market": lowest, "premium": premium, "markets": {k: v["price"] for k, v in markets.items() if v["status"] == "OK"}})
    state["history"] = history[-thresholds.get("history_limit", 30):]
    if signal:
        state["last_alert"] = signal["new_alert_type"]
        state["alert_history"].append({"timestamp": now.isoformat(), "signal": signal["signal"], "premium": premium, "reason": signal["reason"]})
    save_state(state)

    snapshot_id = None
    try:
        platform_prices = [{"platform_name": name, "price_irr": info["price"], "change_irr": None} for name, info in markets.items() if info.get("status") == "OK"]
        snapshot_id = save_market_snapshot(timestamp=now, fair_price=fair, premium_percent=premium, world_gold_usd=world, usd_irr=usd, signal=signal_state.final_decision, confidence=None, platform_prices=platform_prices)
        print("\nDB: Snapshot saved")
    except Exception as e:
        print(f"\nDB ERROR (snapshot): {e}")

    if snapshot_id is not None:
        try:
            signal_state = replace(signal_state, snapshot_id=snapshot_id)
            save_market_state(signal_state)
            print("DB: Market state saved")
        except Exception as e:
            print(f"DB ERROR (market state): {e}")

    if is_scheduled:
        try:
            news_result = run_news_ingestion(config)
            if news_result.get("status") == "OK":
                print(f"NEWS: {news_result.get('total_new', 0)} new events")
        except Exception as e:
            print(f"News ingestion failed: {e}")
        if snapshot_id is not None:
            try:
                analysis_snapshot_id = build_analysis_snapshot(config=config)
                if analysis_snapshot_id:
                    print(f"DB: Analysis snapshot {analysis_snapshot_id} created")
            except Exception as e:
                print(f"DB ERROR (analysis snapshot): {e}")

    should_send_alert = bool(signal and signal["signal"] in ("BUY", "SELL") and email_cfg.get("send_alerts", True))
    if should_send_alert:
        try:
            send_email_alert(signal, world, usd, fair, lowest, premium, markets, trends=trends, momentum=momentum, previous_markets=previous_markets, signal_state=signal_state)
        except Exception as e:
            print(f"ERROR: Email alert failed: {e}")
        try:
            send_telegram_alert(signal, world, usd, fair, lowest, premium, markets, trends=trends, momentum=momentum, previous_markets=previous_markets, signal_state=signal_state)
        except Exception as e:
            print(f"ERROR: Telegram alert failed: {e}")

    if is_scheduled:
        if email_cfg.get("send_daily_recap", True):
            try:
                send_email_recap(world, usd, fair, lowest, premium, markets, trends=trends, momentum=momentum, previous_markets=previous_markets)
            except Exception as e:
                print(f"ERROR: Email daily recap failed: {e}")
            try:
                send_telegram_recap(world, usd, fair, lowest, premium, markets, trends=trends, momentum=momentum, previous_markets=previous_markets, input_directions=input_directions, signal_state=signal_state)
            except Exception as e:
                print(f"ERROR: Telegram daily recap failed: {e}")
    else:
        try:
            # Resolve highest price for UPDATE v1 MARKET section
            highest_price = markets[high_name]["price"] if high_name in markets else None
            send_update_v1(
                world=world,
                usd=usd,
                fair=fair,
                platform_avg=signal_state.platform_average,
                lowest=lowest,
                highest=highest_price,
                spread=spread,
                premium=premium,
                markets=markets,
                signal_state=signal_state,
                baselines=baselines,
                momentum=momentum,
            )
            print("UPDATE v1 sent.")
        except Exception as e:
            print(f"UPDATE v1 failed: {e}")
            try:
                send_telegram_manual(world, usd, fair, lowest, premium, markets, trends=trends, momentum=momentum, previous_markets=previous_markets, input_directions=input_directions, signal_state=signal_state)
                print("Fallback manual update sent.")
            except Exception as e2:
                print(f"Fallback manual update failed: {e2}")


if __name__ == "__main__":
    main()
