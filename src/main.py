import json
import os
from datetime import datetime, timedelta
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

from alerts.resend_mail import send_daily_recap as send_email_recap, send_alert as send_email_alert, send_signal_email
from alerts.telegram_signal import build_buy_signal_message, send_buy_signal
from analysis.confirmation import SignalConfirmation, resolve_signal_confirmation
from caluclator.signals import DEFAULT_COOLDOWN_HOURS
from alerts.telegram import (
    send_alert as send_telegram_alert,
    send_manual_update as send_telegram_manual,
    send_data_unavailable as send_telegram_unavailable,
    send_processing as send_telegram_processing,
    send_daily_recap as send_telegram_recap,
)
from alerts.telegram_update_v1 import send_update_v1
from validation.data import validate_world_gold, validate_usd_rate, validate_market_prices, validate_fair_price, STALE_LOOKBACK_DAYS
from database.connection import get_session
from database.repository import save_market_snapshot, save_market_state, save_price_observation, get_input_directions, get_recent_platform_prices, get_latest_node_reading
from intelligence.freshness import evaluate_freshness
from update.baseline_resolver import resolve_update_baselines
from analysis.bubble_position import (
    resolve_bubble_position,
    resolve_decision_valuation,
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
    return f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"


def _resolve_decision_valuation(premium, thresholds):
    """The valuation leg, or an abstention.

    Non-blocking in the same way `_build_valuation_context` is: a database failure
    must degrade the decision to UNKNOWN, never prevent the run. UNKNOWN reaches the
    conflict matrix as an abstention, which is the fail-safe law -- on missing data,
    abstain rather than extrapolate.
    """
    from analysis.bubble_position import DecisionValuation
    try:
        session = get_session()
        if session is None:
            return DecisionValuation(premium=premium)
        return resolve_decision_valuation(session, premium, thresholds)
    except Exception as e:
        print(f"Decision valuation failed, abstaining: {e}")
        return DecisionValuation(premium=premium)


# Rows re-read when a new trading day is due and history is stored: covers Fridays,
# holidays and a few missed days.
TGJU_WINDOW_ROWS = 10

# History is filled a page per run, oldest first, from where the stored history ends:
# 3,964 dollar days take four runs. The whole history in one request failed from the
# runner at 14:00 on 2026-09-30 (SP_C_HANDOFF.md section 43).
TGJU_BACKFILL_PAGE_ROWS = 1000

# An instrument whose newest stored candle is older than this pages forward rather than
# re-reading the newest days, so a long outage is filled from where it began.
TGJU_BACKFILL_AFTER_DAYS = 30


def _tgju_requests(coverage, today):
    """{tgju key: (start, rows, order)} from {name: (stored count, latest date)}.

    An instrument with no stored candle, or a latest one more than
    TGJU_BACKFILL_AFTER_DAYS old, asks for the next page of its history, oldest first,
    starting at its stored count. tgju's oldest-first offsets do not move, because new
    days only append; a skipped row can only make pages overlap, never leave a gap.
    Otherwise it asks for the newest days, enough to reach back past its latest candle.
    """
    from collector.tgju import INSTRUMENTS

    needed = {}
    for key, name in INSTRUMENTS.items():
        count, latest = coverage.get(name, (0, None))
        if latest is None or (today - latest).days > TGJU_BACKFILL_AFTER_DAYS:
            needed[key] = (count, TGJU_BACKFILL_PAGE_ROWS, "asc")
        else:
            needed[key] = (0, max(TGJU_WINDOW_ROWS, (today - latest).days + 5), "desc")
    return needed


def _tgju_last_trading_day(today, key="geram18"):
    """The newest candle tgju can have for `key` before `today`: the last earlier day its
    market trades (Iran: not Friday; world gold: not Saturday or Sunday). Public holidays
    are not known here; after one, runs simply keep asking until a newer candle appears."""
    from collector.tgju import CLOSED_WEEKDAYS
    closed = CLOSED_WEEKDAYS.get(key, (4,))
    day = today - timedelta(days=1)
    while day.weekday() in closed:
        day -= timedelta(days=1)
    return day


def _collect_tgju_candles(now=None):
    """Collect tgju's daily candles and store the completed days not stored yet.

    SP-D technical-analysis track (SP_C_HANDOFF.md sections 41.6, 43). Scheduled runs
    only. While an instrument's history is missing, each run stores one more page of
    it. After that tgju is asked only while the newest stored candle is older than the
    last trading day, so about once a day, and then for a short window. Today's candle is never stored, because
    it is not complete. A stored day that tgju has since changed is reported, not
    overwritten. Never raises, and the collector is bounded by its own deadline, so it
    cannot hold or fail a run.
    """
    session = None
    try:
        from datetime import date
        from collector.tgju import INSTRUMENTS, SOURCE, UNITS, collect_daily_candles
        from database.repository import get_daily_candle_coverage, save_daily_candles
        from timeutil import local_now
        from validation.data import classify_daily_candle

        session = get_session()
        if session is None:
            print("TGJU: database unavailable, nothing collected")
            return
        now = now or datetime.utcnow()
        today = local_now(now).date()
        coverage = get_daily_candle_coverage(session, SOURCE)
        latest = {name: last for name, (_, last) in coverage.items()}
        if all(latest.get(name) is not None and latest[name] >= _tgju_last_trading_day(today, key)
               for key, name in INSTRUMENTS.items()):
            print(f"TGJU: up to date, latest {max(latest.values())}")
            return
        plan = _tgju_requests(coverage, today)
        for key, result in collect_daily_candles(rows=plan).items():
            if result["status"] != "OK":
                print(f"TGJU {key}: {result['status']}")
                continue
            candles, invalid = [], 0
            for c in result["candles"]:
                trade_date = date.fromisoformat(c["date"])
                if trade_date >= today:
                    continue
                quality = classify_daily_candle(c)
                if quality == "INVALID":
                    invalid += 1
                    continue
                candles.append({**c, "trade_date": trade_date, "quality": quality})
            try:
                inserted, revised = save_daily_candles(
                    session, SOURCE, INSTRUMENTS[key], UNITS[key], candles, now)
            except Exception as e:
                session.rollback()
                print(f"TGJU {key}: store failed: {e}")
                continue
            line = f"TGJU {key}: {inserted} new"
            if plan[key][2] == "asc":
                line += f" (history page from row {plan[key][0]})"
            if candles:
                newest = max(candles, key=lambda c: c["trade_date"])
                line += f", latest {newest['date']} close {newest['close']:,.0f}"
            if revised:
                line += (f", {len(revised)} changed by tgju since stored, kept as first seen "
                         f"({', '.join(str(d) for d in revised[:3])})")
            if invalid:
                line += f", {invalid} without a valid price skipped"
            print(line)
    except Exception as e:
        print(f"TGJU collection failed: {e}")
    finally:
        if session is not None:
            session.close()


ROOM_INPUTS = {  # stored name -> (source, unit): the room's daily readings (SP_D_HANDOFF.md section 27)
    "TSE_TEDPIX": ("tablokhani", "POINTS"), "AFRAN_LAST": ("tablokhani", "IRR"),
    "ETFBAZ_USDT_IRR": ("etfbaz", "IRR"), "ETFBAZ_USD_IRR": ("etfbaz", "IRR"), "ETFBAZ_MELTED_GOLD": ("etfbaz", "IRR"),
    "ETFBAZ_GOLD_18K": ("etfbaz", "IRR"), "ETFBAZ_XAU_USD": ("etfbaz", "USD"), "ETFBAZ_TEDPIX": ("etfbaz", "POINTS"),
}


def _collect_room_inputs(now=None):
    """The room's daily readings from the sources GitHub's runner reaches: from tablokhani, Afran's
    last close, and the stock index once the Tehran exchange has closed; from etfbaz, from 21:00,
    the day's Tether, dollar, melted-gold quote, 18K and world gold. One row a day per instrument in
    market_daily_candles, the first seen kept; TSETMC and fipiran wait for the Iran-side collector.
    Never raises."""
    from collector import etfbaz, tablokhani
    from database.repository import save_daily_candles
    from timeutil import local_date, local_now, to_jalali

    session = get_session()
    if session is None:
        return
    try:
        now = now or datetime.utcnow()
        day, hour = local_date(now), local_now(now).hour
        jy, jm, jd = to_jalali(day)
        readings = {}
        t = tablokhani.collect()
        if t["afran_close"]:
            readings["AFRAN_LAST"] = t["afran_close"]
        if t["tedpix"] and t["tse_state"] == "closed" and hour >= 13:
            readings["TSE_TEDPIX"] = t["tedpix"]
        errors = list(t["errors"])
        if hour >= 21:
            e = etfbaz.collect()
            errors += e.pop("errors")
            readings.update(e)
        stored = []
        for name, value in readings.items():
            source, unit = ROOM_INPUTS[name]
            inserted, _ = save_daily_candles(session, source, name, unit, [{
                "trade_date": day, "jdate": f"{jy:04d}/{jm:02d}/{jd:02d}", "open": value, "high": value, "low": value,
                "close": value, "quality": "LAST_KNOWN"}], now)
            if inserted:
                stored.append(f"{name} {value:,.0f}")
        print("ROOM inputs: " + (", ".join(stored) if stored else "nothing new today")
              + (f"; unavailable: {', '.join(errors)}" if errors else ""))
    except Exception as e:
        session.rollback()
        print(f"ROOM inputs failed: {e}")
    finally:
        session.close()


def _recent_platform_history(now):
    """Stored platform prices for the stale-quote check, or an empty list.

    Fails open: without history no quote is deferred, because dropping a price on a
    guess is worse than keeping it -- and the confirmation check below still fails
    closed, so a stale quote that slips through cannot carry a signal on its own.
    """
    session = get_session()
    if session is None:
        return []
    try:
        return get_recent_platform_prices(session, now - timedelta(days=STALE_LOOKBACK_DAYS))
    except Exception as e:
        print(f"Platform history unavailable, stale-quote check skipped: {e}")
        return []
    finally:
        session.close()


NODE_MAX_AGE_MINUTES = 30   # the node reads every 15 minutes: two missed readings and Daric stays out


def _daric_from_node(raw_markets, now):
    """Daric's quote from the Iran-side node when the runner is refused (SP_D_HANDOFF.md
    section 30). Daric answers 403 to GitHub's addresses; the owner's phone in Iran reads
    it every 15 minutes into iran_node_readings. The reading enters validation like any
    platform's, its read time as the quote's time, so the stale-quote rules apply to it.

    Fails open: without the database or a recent reading, Daric stays as its collector
    left it, and is discarded as before.
    """
    if raw_markets.get("Daric", {}).get("status") == "OK":
        return
    session = get_session()
    if session is None:
        return
    try:
        row = get_latest_node_reading(session, "daric", "DARIC_18K",
                                      now - timedelta(minutes=NODE_MAX_AGE_MINUTES))
        if row is None:
            print(f" Daric: no node reading in the last {NODE_MAX_AGE_MINUTES} minutes")
            return
        ask, bid = float(row.ask), float(row.bid)
        raw_markets["Daric"] = {"price": ask, "buy": ask, "sell": bid, "status": "OK",
                                "quoted_at": row.observed_at}
        print(f" Daric: from the Iran node ({row.node}, read {(now - row.observed_at).total_seconds() / 60:.0f} min ago)")
    except Exception as e:
        print(f" Daric: node reading unavailable: {e}")
    finally:
        session.close()


def _resolve_signal_confirmation(markets, fair, usd, world_from_fallback, thresholds):
    """The checks a BUY/SELL candidate must pass, or a failed set.

    Fails closed, unlike the valuation leg's abstention and the push's fail-open: a
    check that cannot run holds the signal, because a recommendation that cannot show
    its evidence must not be sent (SP_C_HANDOFF.md section 38).
    """
    session = get_session()
    if session is None:
        return SignalConfirmation(world_live=not world_from_fallback, status="NO_SESSION")
    try:
        return resolve_signal_confirmation(session, markets, fair, usd,
                                           world_from_fallback, thresholds)
    except Exception as e:
        print(f"Signal confirmation failed, holding any signal: {e}")
        return SignalConfirmation(world_live=not world_from_fallback, status="ERROR")
    finally:
        session.close()


def _send_buy_signal(markets, fair, premium, signal_state, confirmation, baselines,
                     thresholds):
    """Resolve UPDATE's presentation values for this reading and send the BUY message.

    Telegram and email are isolated from each other, as every other alert path is.
    """
    run_premium = baselines.run.premium_percent if baselines and baselines.run else None
    run_elapsed_hours = None
    if baselines and baselines.run and baselines.run.timestamp:
        run_elapsed_hours = (datetime.utcnow() - baselines.run.timestamp).total_seconds() / 3600.0
    _, _, _, valuation = _resolve_presentation_context(
        premium, run_premium, markets=markets, fair=fair,
        run_basis_gap=_basis_change(markets, fair, baselines),
        run_elapsed_hours=run_elapsed_hours,
    )
    text = build_buy_signal_message(
        fair=fair, markets=markets, signal_state=signal_state, confirmation=confirmation,
        valuation=valuation, baselines=baselines,
        cooldown_hours=thresholds.get("cooldown_hours", DEFAULT_COOLDOWN_HOURS),
    )
    try:
        send_signal_email("GOLDPremium: BUY SIGNAL", text)
    except Exception as e:
        print(f"ERROR: Email BUY signal failed: {e}")
    try:
        send_buy_signal(text)
    except Exception as e:
        print(f"ERROR: Telegram BUY signal failed: {e}")


def _build_valuation_context(premium, markets=None, fair=None, thresholds=None):
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
        position = resolve_bubble_position(session, current_bubble=premium,
                                           thresholds=thresholds)
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


def _send_analyze_report():
    """Answer the Telegram Analyze command from persisted state.

    Reads only. Non-blocking in the same sense as the rest of the presentation layer:
    a failure here degrades to a message saying so rather than a silent absence.
    """
    from analysis.analyze_report import build_analyze_report
    from alerts.telegram_analyze import send_analyze

    session = get_session()
    if session is None:
        print("REPORT: no database session")
        return
    try:
        report = build_analyze_report(session)
        send_analyze(report)
        print(f"REPORT sent. status={report.status} "
              f"readings={report.health.readings} cases={report.level.cases}")
    except Exception as e:
        print(f"REPORT failed: {e}")
    finally:
        session.close()


DIRECTION_SLOTS = (6, 13)       # Tehran hours: the first scheduled run from each computes the panel


def _direction_slot(now):
    """"06:00" or "13:00", the latest slot this Tehran hour has reached, or None before 06:00."""
    from timeutil import local_now

    hour = local_now(now).hour
    reached = [h for h in DIRECTION_SLOTS if hour >= h]
    return f"{reached[-1]:02d}:00" if reached else None


def _direction_precompute(markets, signal_state, now):
    """Compute and store the DIRECTION panel once per slot, after resolving the forecasts
    whose horizon has passed (SP-D, SP_D_HANDOFF.md section 4). Never raises: Direction is evidence,
    and a failure here must not cost the run its push or recap."""
    slot = _direction_slot(now)
    if slot is None:
        return
    from analysis.direction import resolve_direction
    from analysis.direction_ledger import apply_gate, assess, resolve_pending
    from database.repository import (direction_snapshot_exists, resolved_direction_snapshots,
                                     save_direction_snapshot)
    from timeutil import local_date

    session = get_session()
    if session is None:
        return
    try:
        day = local_date(now)
        if direction_snapshot_exists(session, day, slot):
            return
        resolved = resolve_pending(session, now)
        system = {"final_decision": signal_state.final_decision, "valuation": signal_state.valuation,
                  "candidate": signal_state.candidate_decision} if signal_state else {}
        panel = resolve_direction(session, markets=markets, system=system, now=now)
        if panel.status != "OK":
            print(f"DIRECTION: {panel.status}; the next run retries")
            return
        for alarm in apply_gate(panel, assess(resolved_direction_snapshots(session))):
            print(f"DIRECTION ALARM: {alarm}")
        snapshot_id = save_direction_snapshot(session, panel, day, slot)
        print(f"DIRECTION: {slot} panel {snapshot_id} stored ({panel.stance.get('label')}, "
              f"{', '.join(panel.position.get('tags', [])) or 'no tags'}); {resolved} forecasts resolved")
    except Exception as e:
        session.rollback()
        print(f"DIRECTION failed: {e}")
    finally:
        session.close()


def _paper_run(markets, signal_state, now):
    """The PAPER portfolio's run (SP-D, SP_D_HANDOFF.md sections 9-10): evaluate the four
    accounts, trade where the contract allows, push the brave analyst's trades, and from
    21:00 write the day's report. Never raises: a hypothetical account must not cost the
    run its push, recap or history."""
    from analysis import paper
    from analysis.direction import GOLD, load_series
    from alerts.telegram_paper import build_trade_message, send_paper
    from database.repository import (ensure_paper_accounts, latest_direction_snapshot, paper_latest,
                                     paper_rows_on, save_paper_activity)
    from timeutil import local_date, local_now

    session = get_session()
    if session is None:
        return
    try:
        accounts = ensure_paper_accounts(session, paper.ACCOUNTS, paper.START_CASH_IRR, paper.VENUE_LABEL, now)
        day = local_date(now)
        quote = paper.venue_quote(markets)
        close = load_series(session, GOLD)[3]
        sig = paper.signals(close) if len(close) >= 260 else None
        final = getattr(signal_state, "final_decision", None)
        panel_row = latest_direction_snapshot(session)
        stance_score = ((panel_row.panel or {}).get("stance") or {}).get("score") if panel_row else None
        quote_json = {"venue": quote.venue, "buy": quote.buy, "sell": quote.sell} if quote else None
        engine = _quant_view(session, accounts, close, day)
        f_star = engine.get("f_star") if engine else None
        view = _room_view(session, accounts[paper.ROOM], engine, now) if paper.ROOM in accounts else None
        fund_day, fund_price = _room_series(session)[2] if paper.ROOM in accounts else (None, None)
        fund_estimated = bool(fund_day and (day - fund_day).days > paper.FUND_STALE_DAYS)

        for name, account in accounts.items():
            last = paper_latest(session, account.id)
            units = float(((last.inputs or {}).get("fund") or {}).get("units") or 0) if last else 0.0
            book = (paper.Book(float(last.cash), last.holding, units) if last
                    else paper.Book(float(account.start_cash), 0))
            traded = len(paper_rows_on(session, account.id, day, "TRADE"))
            prev = paper_latest(session, account.id, kinds=("EVAL", "TRADE"))
            state = (prev.inputs or {}) if prev is not None else {}
            found, out, swing, after = [], None, None, None
            if name == paper.ROOM:
                from analysis.room import ALL_GOLD
                posture = view["posture"] if view else ALL_GOLD
                decision, after = paper.room_trade(book, quote, posture, fund_price, traded)
                why = decision.reason
                if view and view.get("reasons"):
                    why = f"{'; '.join(view['reasons'])} ({decision.reason})"
                elif not view:
                    why = f"no room view: the default, all in gold ({decision.reason})"
            elif name == paper.ANALYST:
                decision = paper.brave(book, quote, state.get("swing"), day, traded, cap=f_star)
                why, swing = decision.reason, decision.swing
                found = paper.conflicts(stance_score, final, swing)
            else:
                share = book.share(quote.sell) if quote else 0.0
                band = paper.BAND
                if name == paper.QUANT:
                    from analysis.quant import cost_band
                    target = share if f_star is None else f_star
                    why = ("no quant view: hold" if f_star is None
                           else f"growth-optimal share {f_star:.0%} (drift {engine['mu'] * 300 * 100:+.0f}%/yr, "
                                f"volatility {(engine['variance'] * 300) ** 0.5 * 100:.0f}%/yr)")
                    band = cost_band(target, (quote.buy - quote.sell) / quote.buy * 100) if quote else 0.0
                elif name == paper.CAUTIOUS:
                    was_out = bool(state.get("out"))
                    target, out, why = (paper.analyst_target(sig, was_out) if sig is not None
                                        else (share, was_out, "not enough tgju history"))
                elif name == paper.HOLD:
                    target, why = 1.0, "buy and hold"
                else:
                    target, why = paper.system_target(final, share)
                decision = paper.decide(book, target, quote, traded, band=band)
            after = after if after is not None else paper.apply(book, decision)
            inputs = {"policy": account.policy, "quote": quote_json, "signals": sig, "final_decision": final,
                      "valuation": getattr(signal_state, "valuation", None), "stance_score": stance_score,
                      "conflicts": found, "out": out, "swing": swing, "plan": decision.plan,
                      "quant": engine}
            if name == paper.ROOM:
                inputs["room"] = view
                inputs["fund"] = {"name": paper.FUND, "units": after.units, "price": fund_price,
                                  "as_of": str(fund_day) if fund_day else None, "estimated": fund_estimated}
            value = after.value(quote.sell, fund_price) if quote else None
            if decision.action in ("BUY", "SELL"):
                save_paper_activity(session, account_id=account.id, at=now, local_date=day, kind="TRADE",
                                    action=decision.action, grams=decision.grams, price=decision.price,
                                    cash=after.cash, holding=after.grams, value=value, reason=why, inputs=inputs,
                                    trade_no=traded + 1)
                print(f"PAPER {name}: {decision.action} {decision.grams} g at {decision.price:,.0f} on {quote.venue} ({why})")
                if account.pushes and name == paper.ROOM:
                    from alerts.telegram_paper import build_room_trade_message
                    base = _quarter_base(session, account, day)
                    send_paper(build_room_trade_message(decision.action, decision.grams, decision.price, quote.venue,
                                                        now, view, after, fund_price, fund_estimated, quote.sell,
                                                        base, book.units))
                elif account.pushes:
                    send_paper(build_trade_message(decision.action, decision.grams, decision.price, quote.venue,
                                                   now, why, after.grams, after.cash, quote.sell, decision.plan))
            elif name in (paper.ROOM, paper.ANALYST, paper.QUANT, paper.CAUTIOUS):
                action = "UNDECIDED" if found else "HOLD"
                reason = why if name in (paper.ROOM, paper.ANALYST) else f"{why}; {decision.reason}"
                save_paper_activity(session, account_id=account.id, at=now, local_date=day, kind="EVAL",
                                    action=action, cash=book.cash, holding=book.grams, value=value,
                                    reason=reason, inputs=inputs)
                print(f"PAPER {name}: {action} ({reason})" + (f" -- {found}" if found else ""))

        if local_now(now).hour >= paper.REPORT_HOUR:
            _paper_report(session, accounts, day, quote, sig, now, view=view, fund=(fund_day, fund_price, fund_estimated))
    except Exception as e:
        session.rollback()
        print(f"PAPER failed: {e}")
    finally:
        session.close()


def _quant_view(session, accounts, close, day):
    """The quant engine's view this run: its regime model fitted once per Persian quarter
    (the contract changes rules only at a quarter boundary) and filtered on the completed
    candles. The fitted parameters live in the quant account's last row. None on failure."""
    from analysis import paper, quant
    from database.repository import paper_latest
    from timeutil import persian_quarter

    try:
        quarter = persian_quarter(day)[2]
        prev = paper_latest(session, accounts[paper.QUANT].id, kinds=("EVAL", "TRADE"))
        stored = ((prev.inputs or {}).get("quant") or {}) if prev is not None else {}
        fitted = stored.get("fitted") if stored.get("quarter") == quarter else None
        view = quant.assess(close, fitted)
        if view is None:
            return None
        view["quarter"] = quarter
        return view
    except Exception as e:
        print(f"PAPER quant view unavailable: {e}")
        return None


SEED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed")


def _stored_daily(session, source, instrument):
    from database.models import MarketDailyCandle
    rows = (session.query(MarketDailyCandle.trade_date, MarketDailyCandle.close)
            .filter(MarketDailyCandle.source == source, MarketDailyCandle.instrument == instrument)
            .order_by(MarketDailyCandle.trade_date.asc()).all())
    return [(r[0], float(r[1])) for r in rows]


def _room_series(session):
    """(TEDPIX, the cost of money, Afran's last close and its date): src/seed's history, then the
    daily readings production stored (tablokhani; etfbaz's index as a fallback)."""
    from datetime import date as _date
    ted = json.load(open(os.path.join(SEED_DIR, "tedpix.json"), encoding="utf-8"))
    ted = {_date.fromisoformat(k): v for k, v in ted.items()}
    for source, name in (("etfbaz", "ETFBAZ_TEDPIX"), ("tablokhani", "TSE_TEDPIX")):
        for d_, v in _stored_daily(session, source, name):
            if d_ > max(ted):
                ted[d_] = v
            elif source == "tablokhani":
                ted.setdefault(d_, v)
    fi_seed = json.load(open(os.path.join(SEED_DIR, "fixed_income.json"), encoding="utf-8"))
    fi = {_date.fromisoformat(k): v for k, v in fi_seed["level"].items()}
    scale, seed_end = fi_seed["afran_scale"], max(fi)
    afran = _stored_daily(session, "tablokhani", "AFRAN_LAST")
    for d_, v in afran:
        if d_ > seed_end:
            fi[d_] = v * scale
    last_afran = afran[-1] if afran else (seed_end, fi[seed_end] / scale)
    return ted, fi, last_afran


def _room_flow(session):
    """The gold funds' buyer power by day, for the room's money-flow member (SP_D_HANDOFF.md section
    33): src/seed's history, then the days the Iran node sent after it. A fund's latest copy of a day
    is used, and a day counts when room.FLOW_MIN_FUNDS of the seed's funds have it."""
    from datetime import date as _date, datetime as _dt
    from analysis import room
    from database.repository import get_node_rows
    seed = json.load(open(os.path.join(SEED_DIR, "gold_fund_flows.json"), encoding="utf-8"))
    power = {_date.fromisoformat(k): v for k, v in seed["power"].items()}
    seed_end, funds = max(power), set(seed["funds"])
    by_day = {}
    for row in get_node_rows(session, "tsetmc", _dt.combine(seed_end, _dt.min.time())):
        record, day = row.payload or {}, row.detail or ""
        code = str(record.get("insCode") or row.instrument.replace("CLIENTTYPE_", ""))
        if len(day) != 8 or code not in funds:
            continue
        day = _date(int(day[:4]), int(day[4:6]), int(day[6:]))
        if day > seed_end:
            by_day.setdefault(day, {})[code] = record
    for day, records in by_day.items():
        if len(records) < room.FLOW_MIN_FUNDS:
            continue
        bv, bc, sv, sc = (sum(float(r.get(k) or 0) for r in records.values())
                          for k in ("buy_I_Value", "buy_I_Count", "sell_I_Value", "sell_I_Count"))
        if bc and sc and sv:
            power[day] = (bv / bc) / (sv / sc)
    days = sorted(power)
    return days, [power[k] for k in days]


def _room_state(session, account, engine):
    """Everything the room reads, on the completed tgju candles, with its posture replayed from the
    account's first day (analysis/room.py); None without enough history."""
    import numpy as np
    from analysis import room
    from analysis.direction import GOLD, USD, XAU, load_series
    from analysis.quant import growth_path
    from caluclator.chartist import Chartist
    from database.models import MarketDailyCandle
    from timeutil import local_date

    rows = (session.query(MarketDailyCandle).filter(MarketDailyCandle.source == "tgju",
                                                    MarketDailyCandle.instrument == GOLD)
            .order_by(MarketDailyCandle.trade_date.asc()).all())
    if len(rows) < 600:
        return None
    dates = [r.trade_date for r in rows]
    o, h, l, c = (np.array([float(getattr(r, k)) for r in rows]) for k in ("open", "high", "low", "close"))
    flat = (o == h) & (h == l) & (l == c)
    usable = np.array([r.source_quality == "COMPLETE" for r in rows]) & ~flat
    ud, _, _, uc = load_series(session, USD)
    xd, _, _, xc = load_series(session, XAU)
    ted, fi, afran = _room_series(session)
    td, fd = sorted(ted), sorted(fi)
    fitted = (engine or {}).get("fitted")
    f_star, mu = growth_path(c, fitted) if fitted else (np.full(len(c), np.nan), np.zeros(len(c)))
    start_day = local_date(account.started_at)
    start = min(next((i for i, x in enumerate(dates) if x >= start_day), len(dates) - 1), len(dates) - 1)
    chart = Chartist(h, l, c, usable=usable)
    try:
        flow = room.money_flow(dates, *_room_flow(session))
    except Exception as e:
        print(f"PAPER money flow unavailable, the member has no view: {e}")
        flow = None
    leans, stocks = room.member_leans(h, l, c, room.aligned(dates, ud, uc), room.aligned(dates, xd, xc),
                                      room.aligned(dates, fd, [fi[k] for k in fd], max_gap_days=10),
                                      room.aligned(dates, td, [ted[k] for k in td], max_gap_days=10),
                                      f_star, flat, chartist=chart, from_index=max(0, start - 1), flow=flow)
    return {"dates": dates, "close": c, "mu": mu, "chart": chart, "leans": leans, "stocks": stocks,
            "start": start, "start_day": start_day, "path": room.replay(leans, stocks, start, len(c) - 1),
            "fi": fi, "afran": afran}


def _room_view_at(state, i):
    """The room's view on day i of `state`: its posture, the evidence and the words for the messages."""
    from analysis import room
    from analysis.direction import trading_date
    from caluclator.chartist import PHASE_WORDS, describe
    from timeutil import persian_day

    dates, chart, leans = state["dates"], state["chart"], state["leans"]
    today = state["path"][i - state["start"]]
    share, opinion = room.share_for_fixed_income(leans, i)
    days_in = (i - state["start"]) % room.REVIEW_EVERY
    next_review = trading_date(dates[i], room.REVIEW_EVERY - days_in)
    read = chart.read(i)
    label = lambda j: persian_day(dates[j])
    known = chart.known(i)
    phase_line = None
    if read.get("phase") and known:
        pivot = known[-1]
        phase_line = (f"{PHASE_WORDS[read['phase']]}, {'up' if pivot[3] == 'L' else 'down'} from "
                      f"{pivot[2] / 1e7:.2f}M on {label(pivot[1])}")
    band = room.forecast_band(state["close"][:i + 1], state["mu"][:i + 1])
    afran_day, afran_close = state["afran"]
    return {
        "posture": today["posture"], "review": today["review"], "early": today["early"], "inner": today["inner"],
        "share": round(float(share), 3), "members": {m: int(leans[m][i]) for m in room.WEIGHTS},
        "stocks": int(state["stocks"][i]), "for_fixed_income": [m for m, v in opinion.items() if v == -1],
        "for_gold": [m for m, v in opinion.items() if v == 1],
        "reasons": (["the stock index turned up: back to gold early"] if today["early"]
                    else room.reasons(opinion, today["posture"])),
        "next_review": str(next_review), "candle_date": str(dates[i]), "start_day": str(state["start_day"]),
        "phase": read.get("phase"), "phase_line": phase_line, "chart": describe(chart, i, label),
        "band20": [round(x) for x in band] if band else None,
        "fund": {"name": "Afran", "price": afran_close, "as_of": str(afran_day)},
    }


def _room_view(session, account, engine, now):
    """The room's posture and its evidence this run, or None without enough history."""
    try:
        state = _room_state(session, account, engine)
        return _room_view_at(state, len(state["dates"]) - 1) if state else None
    except Exception as e:
        print(f"PAPER room view unavailable: {e}")
        return None


def _quarter_base(session, account, day):
    """(the account's value at the quarter's start, that day): the start cash in its first quarter."""
    from database.repository import paper_value_before
    from timeutil import local_date, persian_quarter
    base_day = max(persian_quarter(day)[0], local_date(account.started_at))
    return paper_value_before(session, account.id, base_day) or float(account.start_cash), base_day


def _paper_report(session, accounts, day, quote, sig, now, view=None, fund=(None, None, False)):
    """The day's REPORT rows and the front office's 21:00 message, once per Tehran day. The value
    is at the venue's sell price (without a fresh quote at this run, the day's last one), and the
    room's fixed income at Afran's last close."""
    from analysis import paper
    from alerts.telegram_paper import build_report_message, build_room_report_message, send_paper_report
    from database.repository import paper_latest, paper_rows_on, save_paper_activity
    from timeutil import to_tehran

    front_name = paper.ROOM if paper.ROOM in accounts else paper.ANALYST
    front = accounts[front_name]
    if paper_rows_on(session, front.id, day, "REPORT"):
        return
    venue, sell, note = (quote.venue, quote.sell, "") if quote else (None, None, "")
    if sell is None:
        rows = sorted(paper_rows_on(session, front.id, day, "EVAL") + paper_rows_on(session, front.id, day, "TRADE"),
                      key=lambda r: r.id)
        for row in reversed(rows):
            q = (row.inputs or {}).get("quote")
            if q:
                venue, sell, note = q["venue"], q["sell"], f", last price at {to_tehran(row.at):%H:%M}"
                break
    if sell is None:
        print("PAPER report: no venue price today; skipped")
        return
    fund_day, fund_price, fund_estimated = fund
    lines = {}
    for name, account in accounts.items():
        last = paper_latest(session, account.id)
        holding, cash = (last.holding, float(last.cash)) if last else (0, float(account.start_cash))
        units = float(((last.inputs or {}).get("fund") or {}).get("units") or 0) if last else 0.0
        base, base_day = _quarter_base(session, account, day)
        value = cash + holding * sell + (units * fund_price if units and fund_price else 0.0)
        save_paper_activity(session, account_id=account.id, at=now, local_date=day, kind="REPORT",
                            action=None, price=sell, cash=cash, holding=holding, value=value, reason=None,
                            inputs={"base": base, "base_day": str(base_day), "sell_note": note,
                                    "fund": {"units": units, "price": fund_price, "as_of": str(fund_day) if fund_day else None,
                                             "estimated": fund_estimated} if units else None})
        lines[name] = (holding, cash, base, base_day, units, value)
    trades = [(t.action, t.grams, float(t.price), ((t.inputs or {}).get("quote") or {}).get("venue"),
               f"{to_tehran(t.at):%H:%M}") for t in paper_rows_on(session, front.id, day, "TRADE")]
    holding, cash, base, base_day, units, value = lines[front_name]
    hold = lines.get(paper.HOLD)
    if front_name == paper.ROOM:
        text = build_room_report_message(day, venue, sell, note, holding, units, fund_price, fund_estimated, value,
                                         base, base_day, (hold[5], hold[2]) if hold else None, trades, view)
    else:
        prev = paper_latest(session, front.id, kinds=("EVAL", "TRADE"))
        plan = (prev.inputs or {}).get("plan") if prev is not None else None
        engine = lines.get(paper.QUANT)
        text = build_report_message(day, venue, sell, note, (holding, cash, base), hold[:3] if hold else None,
                                    base_day, trades, plan, quant=engine[:3] if engine else None)
    png = _paper_chart(session, front, sell)
    send_paper_report(text, png)
    print(f"PAPER report sent: {holding} g + {units:,.0f} {paper.FUND} units + {cash:,.0f} cash at {sell:,.0f} ({venue}), "
          f"chart {'yes' if png else 'no'}")


def _paper_chart(session, analyst, live_sell):
    """The analyst's chart for the 21:00 report: tgju's last 120 daily candles, EMA20 and
    EMA50, the swing supports and resistances, the analyst's trades and the live price.
    None on failure: the report then goes out as text."""
    try:
        import numpy as np
        import talib
        from alerts.chart import render
        from analysis.direction import GOLD
        from caluclator.technical import fibonacci, rally_legs, split_levels, swing_levels, trendlines
        from database.models import MarketDailyCandle, PaperActivity
        from timeutil import to_tehran

        rows = (session.query(MarketDailyCandle).filter(MarketDailyCandle.source == "tgju",
                                                        MarketDailyCandle.instrument == GOLD)
                .order_by(MarketDailyCandle.trade_date.asc()).all())
        if len(rows) < 260:
            return None
        dates = [r.trade_date for r in rows]
        o, h, l, c = (np.array([float(getattr(r, k)) for r in rows]) for k in ("open", "high", "low", "close"))
        usable = [r.source_quality == "COMPLETE" and not (o[j] == h[j] == l[j] == c[j]) for j, r in enumerate(rows)]
        supports, resistances = split_levels(swing_levels(h, l, upto=len(c) - 1, usable=usable), live_sell)
        trades = [(to_tehran(t.at).date(), t.action, float(t.price)) for t in
                  session.query(PaperActivity).filter(PaperActivity.account_id == analyst.id,
                                                      PaperActivity.kind == "TRADE").all()]
        trend = trendlines(h, l, c, upto=len(c) - 1, usable=usable)
        direction, start = rally_legs(c)
        fib = fibonacci(c[start[-1]], c[start[-1]:].max()) if direction[-1] == "up" else []
        return render(dates, o, h, l, c, ema20=talib.EMA(c, 20), ema50=talib.EMA(c, 50),
                      supports=[x["price"] for x in supports[:3]], resistances=[x["price"] for x in resistances[:2]],
                      trades=trades, live=live_sell, title=f"18K daily · PAPER {analyst.name}", trend=trend, fib=fib)
    except Exception as e:
        print(f"PAPER chart unavailable: {e}")
        return None


def _send_direction_report():
    """Answer the Telegram Direction command from the stored panel. Reads only."""
    from alerts.telegram_direction import send_direction
    from analysis.direction import DirectionPanel
    from database.repository import latest_direction_snapshot

    session = get_session()
    if session is None:
        print("DIRECTION: no database session")
        return
    try:
        row = latest_direction_snapshot(session)
        send_direction(DirectionPanel.from_json(row.panel) if row else None)
        print(f"DIRECTION sent. panel={row.id if row else None}")
    except Exception as e:
        print(f"DIRECTION report failed: {e}")
    finally:
        session.close()


def _evaluate_deep_discount_push(markets, fair, state):
    """Fire the deep-discount push if the level is reached and the trigger is armed.

    Scheduled runs only. The push exists because the deep zone typically closes
    inside five hours, which is shorter than the interval between a reader
    remembering to look.
    """
    from analysis.analyze_report import resolve_deep_zone
    from analysis.push_trigger import (
        resolve_push_thresholds, evaluate_push, gap_without_cheapest, corroborate)
    from alerts.telegram_analyze import send_push
    from caluclator.gold import find_lowest_market_price

    session = get_session()
    if session is None:
        return
    try:
        prices = [
            float(info["price"]) for info in (markets or {}).values()
            if info.get("status") == "OK" and info.get("price") is not None
        ]
        gap = signed_gap(cheap_basis_price(prices), fair)
        thresholds = resolve_push_thresholds(session)
        # None, not False: an absent key means the state was never written or the
        # cache was lost, and the gate treats unknown as armed.
        armed = state.get("deep_discount_armed") if state else None
        without = gap_without_cheapest(prices, fair)
        # One platform cannot carry the push (SP_C_HANDOFF.md section 44).
        decision = corroborate(evaluate_push(gap, thresholds, armed), without, thresholds, armed)
        print(f"PUSH: gap={gap if gap is None else round(gap, 2)} "
              f"without_cheapest={without if without is None else round(without, 2)} "
              f"fire_at={thresholds.fire_at} rearm_at={thresholds.rearm_at} "
              f"armed={armed} -> {decision.reason}")

        if state is not None:
            state["deep_discount_armed"] = decision.armed_after

        if not decision.should_fire:
            return

        lowest = find_lowest_market_price(markets)
        low_name = None
        if lowest is not None:
            for name, info in (markets or {}).items():
                if info.get("status") == "OK" and info.get("price") == lowest:
                    low_name = name
                    break
        send_push(
            decision,
            resolve_deep_zone(session, current_gap=gap),
            lowest=lowest,
            low_name=low_name,
            basis_count=min(3, len(prices)),
            platform_count=len(prices),
        )
        print("PUSH sent: deep discount")
    except Exception as e:
        print(f"PUSH evaluation failed: {e}")
    finally:
        session.close()


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
                                  run_basis_gap=None, run_elapsed_hours=None):
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
        # The move size is ranked against intervals of comparable length, so the
        # resolver has to know how much time this change actually covers. The RUN
        # baseline is the last scheduled reading, which on a user request is
        # anywhere from a few minutes to an hour old.
        valuation = resolve_relative_valuation(
            session, markets=markets, fair_price=fair, change_pp=run_basis_gap,
            change_hours=run_elapsed_hours,
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
    report_only = os.environ.get("REPORT_ONLY", "false").lower() == "true"
    direction_only = os.environ.get("DIRECTION_ONLY", "false").lower() == "true"
    print(f"MODE: {'DIRECTION' if direction_only else 'REPORT' if report_only else ('ANALYZE' if is_scheduled else 'UPDATE')}")

    if direction_only:
        # Read-only like the report: the panel was computed by a scheduled run.
        _send_direction_report()
        return
    if report_only:
        # The Live Wing boundary in its strictest form. A reader asking what the
        # record shows must not collect prices, create a snapshot or produce an
        # outcome, so this returns before any collection happens at all.
        _send_analyze_report()
        return
    collection_run_id = _generate_collection_run_id()
    now = datetime.utcnow()
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
    _daric_from_node(raw_markets, now)
    for name, info in raw_markets.items():
        status = info.get("status", "UNKNOWN")
        print(f" {name:<15} {status.replace('ERROR: ', '') if status.startswith('ERROR: ') else status}")
    try:
        markets = validate_market_prices(raw_markets, history=_recent_platform_history(now), now=now,
                                         holds=state.setdefault("quote_holds", {}))
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

    # The valuation leg is ranked against the reading's own settled window rather
    # than compared with a fixed line. Resolved here because it needs a session, and
    # a calculator must not open one. A failure returns UNKNOWN, which makes the
    # conflict matrix abstain -- never a guess, and never the old constant.
    decision_valuation = _resolve_decision_valuation(premium, thresholds)

    # Checked before a BUY/SELL candidate may become final: a second platform confirms
    # a discount, the dollar is today's, and world gold is live. Resolved here for the
    # same reason as the valuation leg -- it needs a session.
    confirmation = _resolve_signal_confirmation(markets, fair, usd, world_from_fallback, thresholds)

    signal_state = build_signal_state(premium=premium, fair_price=fair, lowest_price=lowest, markets=markets, previous_premium=previous_premium, thresholds=thresholds, last_alert=last_alert, snapshot_id=0, last_alert_at=_last_alert_time(state), valuation=decision_valuation.state, confirmation=confirmation)
    print(f"Valuation: {decision_valuation.state} "
          f"(rank {decision_valuation.percentile}, n={decision_valuation.sample_size}, "
          f"status={decision_valuation.status})")
    print(f"Confirmation: second={confirmation.second_platform} "
          f"rank={confirmation.second_percentile} confirms={confirmation.second_confirms} "
          f"dollar_live={confirmation.dollar_live} world_live={confirmation.world_live} "
          f"status={confirmation.status}")
    if signal_state.held_reason:
        print(f"HELD: {signal_state.candidate_decision} -- {signal_state.held_reason}")
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
    # A scheduled BUY needs the RUN baseline too, for its message's move line. Resolved
    # here, before this reading is saved, so the baseline is the previous scheduled
    # reading rather than this one.
    if not is_scheduled or signal_state.final_decision == "BUY":
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
                premium, markets=markets, fair=fair, thresholds=thresholds))
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
        _collect_tgju_candles()
        _collect_room_inputs(now)
        _direction_precompute(markets, signal_state, now)
        _paper_run(markets, signal_state, now)
        if snapshot_id is not None:
            try:
                analysis_snapshot_id = build_analysis_snapshot(config=config)
                if analysis_snapshot_id:
                    print(f"DB: Analysis snapshot {analysis_snapshot_id} created")
            except Exception as e:
                print(f"DB ERROR (analysis snapshot): {e}")
        _evaluate_deep_discount_push(markets, fair, state)
        # state is saved above, before the analysis snapshot is built, so the armed
        # flag the push just set would be discarded without this. Left unsaved it
        # would read as unknown on every run, the gate would fail open every time,
        # and the push would fire on every reading above the level -- which is the
        # flicker the re-arm band exists to prevent.
        save_state(state)

    should_send_alert = bool(signal and signal["signal"] in ("BUY", "SELL") and email_cfg.get("send_alerts", True))
    if should_send_alert and signal["signal"] == "BUY":
        _send_buy_signal(markets, fair, premium, signal_state, confirmation, baselines, thresholds)
    elif should_send_alert:
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
            run_elapsed_hours = None
            if baselines and baselines.run and baselines.run.timestamp:
                run_elapsed_hours = (
                    datetime.utcnow() - baselines.run.timestamp
                ).total_seconds() / 3600.0
            position, trend, magnitude, valuation = _resolve_presentation_context(
                premium, run_premium, markets=markets, fair=fair,
                run_basis_gap=run_basis_gap, run_elapsed_hours=run_elapsed_hours,
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
