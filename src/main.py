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
from analysis.bubble_position import (
    resolve_bubble_position,
    resolve_bubble_trend,
    resolve_change_magnitude,
    resolve_relative_valuation,
    cheap_basis_price,
    signed_gap,
)


def load_config():
    with open("config/config.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _fallback_world_from_history(history):
    """Cached world gold price and the time it was actually observed.

    The observation time is returned, not discarded, so the caller can record the
    value's real age. Without it the row is persisted as though it were collected
    now, and nothing downstream can tell a cached quote from a live one.
    """
    if not history:
        return None, None
    last = history[-1]
    ts_str = last.get("timestamp")
    if not ts_str:
        return None, None
    try:
        ts = datetime.fromisoformat(ts_str)
    except ValueError:
        return None, None
    now = datetime.utcnow()
    if (now - ts).total_seconds() / 3600 > 6:
        return None, None
    return last.get("world_gold"), ts


def _fallback_world_from_db(max_age_hours=6):
    """As above, from the persisted observation stream. Returns (price, observed_at)."""
    from database.models import PriceObservation
    from sqlalchemy import desc
    session = get_session()
    if session is None:
        return None, None
    try:
        obs = session.query(PriceObservation).filter(PriceObservation.instrument == "XAUUSD").order_by(desc(PriceObservation.timestamp)).first()
        if obs is None or obs.price is None:
            return None, None
        age_hours = (datetime.utcnow() - obs.timestamp).total_seconds() / 3600
        if age_hours > max_age_hours:
            return None, None
        return float(obs.price), obs.timestamp
    except Exception as e:
        print(f" World Gold DB fallback failed: {e}")
        return None, None
    finally:
        session.close()


def _generate_collection_run_id():
    return f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def _build_valuation_context(premium, markets=None, fair=None):
    """Capture the relative valuation that accompanied this decision.

    Stored alongside the decision so the scorecard can later attribute an outcome
    to what the system knew at the time, rather than to whatever the logic would
    compute when the scoring runs.

    Non-blocking: returns None on any failure, since a missing context must never
    prevent a decision from being persisted.
    """
    session = get_session()
    if session is None:
        return None
    try:
        position = resolve_bubble_position(session, current_bubble=premium)
        # Which sample the reader's valuation was drawn from. The message does not
        # say, because the line it qualifies claims only "the last 30 days" and that
        # is true on either path, but an audit needs to know whether a reading was
        # ranked against verified scheduled history or a mixed-provenance window.
        valuation = resolve_relative_valuation(session, markets=markets, fair_price=fair)
        sampling = {
            "basis": "cheap_3",
            "basis_gap": valuation.gap,
            "basis_price": valuation.basis_price,
            "bigger_than": valuation.bigger_than,
            "deep_at": valuation.deep_at,
            "sampling": valuation.sampling,
            "sample_size": valuation.sample_size,
            "coverage_days": valuation.coverage_days,
            "status": valuation.status,
        }
        if position.band == "INSUFFICIENT_DATA":
            return {"band": "INSUFFICIENT_DATA", "sample_size": position.sample_size,
                    "valuation": sampling}
        return {
            "valuation": sampling,
            "bubble": position.bubble,
            "percentile": position.percentile,
            "band": position.band,
            "cheap_below": position.cheap_below,
            "expensive_above": position.expensive_above,
            "window_days": position.window_days,
            "sample_size": position.sample_size,
            "coverage_days": position.coverage_days,
            "confidence": position.confidence,
            "drift": position.drift,
        }
    except Exception as e:
        print(f" Valuation context unavailable: {e}")
        return None
    finally:
        session.close()


def _last_alert_time(state):
    """When the last alert was actually sent, from the persisted alert history.

    The hysteresis gate needs this to tell a live cooldown from an expired one.
    Returns None when nothing has been alerted or the record cannot be parsed, which
    the gate treats as an expired cooldown rather than an indefinite suppression.
    """
    history = (state or {}).get("alert_history") or []
    for entry in reversed(history):
        stamp = entry.get("timestamp")
        if not stamp:
            continue
        try:
            return datetime.fromisoformat(stamp)
        except (TypeError, ValueError):
            continue
    return None


def _basis_change(markets, fair, baselines):
    """Change in the trimmed gap against the last scheduled reading, in points.

    Both sides are rebuilt from platform prices. The baseline's stored premium is
    minimum-based, so subtracting it from a trimmed reading would report a change
    that is partly a change of definition.
    """
    run = baselines.run if baselines else None
    if run is None or not run.platform_prices or not run.fair_price or not fair:
        return None
    prices = [
        float(info["price"]) for info in (markets or {}).values()
        if info.get("status") == "OK" and info.get("price") is not None
    ]
    now_gap = signed_gap(cheap_basis_price(prices), fair)
    run_gap = signed_gap(cheap_basis_price(run.platform_prices.values()), run.fair_price)
    if now_gap is None or run_gap is None:
        return None
    return abs(now_gap) - abs(run_gap)


def _resolve_presentation_context(premium, run_premium=None, markets=None, fair=None,
                                  run_basis_gap=None):
    """Relative valuation, bubble trend and move size for the UPDATE message.

    These are reads against persisted observations, not an Analyze pipeline run, so
    they stay inside the Live Wing boundary. Non-blocking: a failure here degrades
    the message rather than preventing it.
    """
    session = get_session()
    if session is None:
        return None, None, None, None
    try:
        # Percentage points of gap movement, which is what the magnitude resolver
        # ranks. A percent change of the premium would invert the sign, since the
        # premium is itself a percentage and negative throughout this market.
        change = (
            abs(premium) - abs(run_premium)
            if premium is not None and run_premium is not None
            else None
        )
        # The valuation is measured on the trimmed basis, so its own change has to
        # be measured on that basis too rather than on the minimum-based premium.
        valuation = resolve_relative_valuation(
            session, markets=markets, fair_price=fair, change_pp=run_basis_gap,
        )
        return (
            resolve_bubble_position(session, current_bubble=premium),
            resolve_bubble_trend(session, current_bubble=premium),
            resolve_change_magnitude(session, change_pp=change),
            valuation,
        )
    except Exception as e:
        print(f" Presentation context unavailable: {e}")
        return None, None, None, None
    finally:
        session.close()


def _save_price_observations(markets, world, usd, now, stale_threshold, collection_run_id,
                             collection_mode="unknown", world_observed_at=None,
                             world_from_fallback=False):
    for name, info in markets.items():
        if info.get("status") != "OK":
            continue
        try:
            freshness = evaluate_freshness(now, now, stale_threshold)
            source = name.lower()
            if name == "Goldika" and "buy" in info and "sell" in info:
                for side in ("buy", "sell"):
                    save_price_observation(instrument="REP_IRAN_GOLD", source=source, timestamp=now, price=info[side], freshness=freshness, collection_run_id=collection_run_id, quote_side=side.upper(), collection_mode=collection_mode)
            elif info.get("price") is not None:
                save_price_observation(instrument="REP_IRAN_GOLD", source=source, timestamp=now, price=info["price"], freshness=freshness, collection_run_id=collection_run_id, quote_side="SINGLE", collection_mode=collection_mode)
        except Exception as e:
            print(f" Price observation {name} failed: {e}")

    # World gold is the one input that can be served from cache, and both of its
    # provenance channels used to be inert: `source` was the literal "kitco_fallback"
    # whether the value was live or cached, and freshness was
    # evaluate_freshness(now, now, ...), which is FRESH by construction -- 3,316 of
    # 3,316 stored rows read FRESH. The reader got a warning in the message; nothing
    # downstream could tell the difference, and no stored row could be audited after
    # the fact. That is the fail-safe law satisfied for a human and not for the system.
    #
    # Platform observations keep (now, now) deliberately. They are fetched live at
    # `now`, and a platform does not disclose the age of its own quote, so anything
    # other than FRESH there would be invented precision.
    world_source = "kitco_cached" if world_from_fallback else "kitco"
    world_freshness = evaluate_freshness(world_observed_at or now, now, stale_threshold)
    for instrument, source, price, fresh in (
        ("XAUUSD", world_source, world, world_freshness),
        ("USD/IRR", "bonbast", usd, evaluate_freshness(now, now, stale_threshold)),
    ):
        if price is None:
            continue
        try:
            save_price_observation(instrument=instrument, source=source, timestamp=now, price=price, freshness=fresh, collection_run_id=collection_run_id, quote_side="SINGLE", collection_mode=collection_mode)
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
    print(f"MODE: {'ANALYZE' if is_scheduled else 'UPDATE'}")
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
    world_from_fallback = False
    world_observed_at = now
    if world is None:
        # Not `a or b`: both fallbacks return a (price, observed_at) pair, and a
        # (None, None) tuple is truthy.
        world, world_observed_at = _fallback_world_from_history(history)
        if world is None:
            world, world_observed_at = _fallback_world_from_db(max_age_hours=6)
        world_from_fallback = world is not None
        if world_from_fallback:
            age = (now - world_observed_at).total_seconds() / 3600 if world_observed_at else None
            suffix = f", {age:.1f}h old" if age is not None else ""
            print(f" World Gold: using cached fallback value (degraded provenance){suffix}")

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

    collection_mode = "scheduled" if is_scheduled else "user"
    _save_price_observations(markets, world, usd, now, stale_threshold, collection_run_id, collection_mode,
                             world_observed_at=world_observed_at, world_from_fallback=world_from_fallback)

    if world is None:
        send_telegram_unavailable(usd=usd, markets=markets, reason="World gold price unavailable. All APIs failed and no recent cached data.")
        return

    # calculate_fair_price inherits its unit from usd_irr, which bonbast reports in
    # Tomans. The x10 converts to Rials, the unit every persisted price uses. This
    # conversion belongs in the collector per CLAUDE.md, not here; it is left in place
    # because relocating it changes where a stored-value semantic is applied.
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

    signal_state = build_signal_state(premium=premium, fair_price=fair, lowest_price=lowest, markets=markets, previous_premium=previous_premium, thresholds=thresholds, last_alert=last_alert, snapshot_id=0, last_alert_at=_last_alert_time(state))
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
        snapshot_id = save_market_snapshot(timestamp=now, fair_price=fair, premium_percent=premium, world_gold_usd=world, usd_irr=usd, signal=signal_state.final_decision, confidence=None, platform_prices=platform_prices, collection_mode=collection_mode)
        print("\nDB: Snapshot saved")
    except Exception as e:
        print(f"\nDB ERROR (snapshot): {e}")

    if snapshot_id is not None:
        try:
            signal_state = replace(signal_state, snapshot_id=snapshot_id)
            save_market_state(signal_state, valuation_context=_build_valuation_context(
                premium, markets=markets, fair=fair))
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
        # The recap is a daily summary, not a per-run notification. Once the Analyze
        # wing runs on a real cadence there are dozens of scheduled runs a day, and
        # sending it from each one would bury the user in duplicates.
        today_key = now.date().isoformat()
        recap_already_sent = state.get("last_recap_date") == today_key
        if email_cfg.get("send_daily_recap", True) and not recap_already_sent:
            recap_delivered = False
            try:
                send_email_recap(world, usd, fair, lowest, premium, markets, trends=trends, momentum=momentum, previous_markets=previous_markets)
                recap_delivered = True
            except Exception as e:
                print(f"ERROR: Email daily recap failed: {e}")
            try:
                send_telegram_recap(world, usd, fair, lowest, premium, markets, trends=trends, momentum=momentum, previous_markets=previous_markets, input_directions=input_directions, signal_state=signal_state)
                recap_delivered = True
            except Exception as e:
                print(f"ERROR: Telegram daily recap failed: {e}")
            # Only mark the day done once something actually reached the user. If every
            # channel failed the next run retries, which costs nothing and self-heals,
            # whereas marking it sent would silently drop that day's recap.
            if recap_delivered:
                state["last_recap_date"] = today_key
                save_state(state)
        elif recap_already_sent:
            print("Daily recap already sent today — skipping.")
    else:
        try:
            # Resolve highest price for UPDATE v1 MARKET section
            highest_price = markets[high_name]["price"] if high_name in markets else None
            run_premium = baselines.run.premium_percent if baselines and baselines.run else None
            run_basis_gap = _basis_change(markets, fair, baselines)
            position, trend, magnitude, valuation = _resolve_presentation_context(
                premium, run_premium, markets=markets, fair=fair,
                run_basis_gap=run_basis_gap,
            )
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
                world_from_fallback=world_from_fallback,
                position=position,
                trend=trend,
                magnitude=magnitude,
                valuation=valuation,
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
