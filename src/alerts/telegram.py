"""Telegram alert formatter and sender for SP-A."""

import os
import sys

import requests

from alerts.helpers import (
    format_platform_table,
    format_trend_lines,
    format_momentum_block,
    format_market_structure,
    format_market_structure_block,
    format_timestamp,
    SEPARATOR,
)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
APP_HEADER = "GOLDPremium:"


def _send(text: str):
    if not TELEGRAM_BOT_TOKEN:
        print("TELEGRAM SKIP: TELEGRAM_BOT_TOKEN not set", file=sys.stderr)
        return
    if not TELEGRAM_CHAT_ID:
        print("TELEGRAM SKIP: TELEGRAM_CHAT_ID not set", file=sys.stderr)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}

    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        print(f"TELEGRAM OK: message sent to chat {TELEGRAM_CHAT_ID}")
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "UNKNOWN"
        body = e.response.text if e.response is not None else str(e)
        print(f"TELEGRAM ERROR HTTP {status}: {body}", file=sys.stderr)
    except Exception as e:
        print(f"TELEGRAM ERROR: {e}", file=sys.stderr)


def _money(value):
    if value is None:
        return "N/A"
    try:
        return f"{float(value):,.0f}"
    except Exception:
        return str(value)


def _number(value, decimals=2):
    if value is None:
        return "N/A"
    try:
        return f"{float(value):,.{decimals}f}"
    except Exception:
        return str(value)


def _format_platforms(markets, previous_markets=None):
    table_lines = format_platform_table(markets, previous_markets)
    if not table_lines:
        return "No platforms available."
    return "\n".join(["```", f"{'Platform':<12} {'Price':>15} {'Change':>12}", "-" * 42, *table_lines, "```"])


def format_decision_section(signal_state):
    if signal_state is None:
        return ""
    lines = [
        SEPARATOR, "<b>DECISION</b>", SEPARATOR, "", "<b>Market State:</b>",
        f"  Valuation:  <code>{signal_state.valuation}</code>",
        f"  Momentum:   <code>{signal_state.momentum}</code> ({signal_state.premium_direction.replace('_', ' ')})",
        f"  Structure:  <code>{signal_state.structure.replace('_', ' ')}</code>",
        f"  Conflict:   <code>{signal_state.conflict.replace('_', ' ')}</code>", "",
        f"Candidate:   <code>{signal_state.candidate_decision}</code>",
    ]
    final = signal_state.final_decision
    lines.append(f"Final:       <b>{final}</b>" if final in {"BUY", "SELL", "WAIT"} else f"Final:       <code>{final}</code>")
    if signal_state.reason:
        lines.extend(["", "<b>Reason:</b>", f"  {signal_state.reason}"])
    return "\n".join(lines)


def _format_market_section(world, usd, fair, lowest, premium, input_directions=None):
    lines = [
        SEPARATOR, "<b>MARKET</b>", SEPARATOR, "",
        f"XAU/USD:    ${_money(world)}  |  USD/IRR: {_money(usd)}",
        f"Fair Value: {_money(fair)} IRR",
        f"Lowest:     {_money(lowest)} IRR",
        f"Premium:    {_number(premium)}%",
    ]
    if input_directions:
        wd = input_directions.get("world")
        ud = input_directions.get("usd")
        if wd:
            stale = f" stale={wd['stale_count']}" if wd.get("stale_count") else ""
            lines.append(f"XAU/USD:    {wd['arrow']} ({wd['pct']:+.2f}%){stale}")
        if ud:
            stale = f" stale={ud['stale_count']}" if ud.get("stale_count") else ""
            lines.append(f"USD/IRR:    {ud['arrow']} ({ud['pct']:+.2f}%){stale}")
    return "\n".join(lines)


def _format_trends_section(trends):
    if not trends:
        return ""
    lines = [SEPARATOR, "<b>TRENDS</b>", SEPARATOR, ""]
    lines.extend(format_trend_lines(trends) or ["No trend data available."])
    premium_direction = trends.get("premium_direction")
    if premium_direction:
        lines.extend(["", premium_direction])
    return "\n".join(lines)


def _format_momentum_section(momentum, current_premium):
    if not momentum:
        return ""
    lines = [SEPARATOR, "<b>MOMENTUM</b>", SEPARATOR, ""]
    lines.extend(format_momentum_block(momentum, current_premium=current_premium) or ["No momentum data available."])
    return "\n".join(lines)


def _format_structure_section(markets, fair_price):
    structure = format_market_structure(markets, fair_price)
    if not structure:
        return ""
    lines = [SEPARATOR, "<b>MARKET STRUCTURE</b>", SEPARATOR, ""]
    lines.extend(format_market_structure_block(structure))
    return "\n".join(lines)


def _format_platforms_section(markets, previous_markets=None):
    return "\n".join([
        SEPARATOR, "<b>PLATFORMS</b>", SEPARATOR, "",
        _format_platforms(markets, previous_markets), "",
    ])


def _build_common_body(world, usd, fair, lowest, premium, markets, trends=None, momentum=None, previous_markets=None, input_directions=None, signal_state=None):
    sections = [
        _format_market_section(world, usd, fair, lowest, premium, input_directions),
        format_decision_section(signal_state),
        _format_trends_section(trends),
        _format_momentum_section(momentum, premium),
        _format_structure_section(markets, fair),
        _format_platforms_section(markets, previous_markets),
        f"<b>{format_timestamp()}</b>",
    ]
    return "\n\n".join(section for section in sections if section)


def _build_message(message_type_header, reason, body):
    parts = [APP_HEADER, "", message_type_header]
    if reason:
        parts.extend(["", reason])
    parts.extend(["", body])
    return "\n".join(parts)


def send_alert(signal, world, usd, fair, lowest, premium, markets, trends=None, momentum=None, previous_markets=None, input_directions=None, signal_state=None):
    if signal_state is not None:
        alert_type = signal_state.final_decision
        if alert_type not in {"BUY", "SELL"}:
            return
        reason = signal_state.reason or ""
    else:
        alert_type = signal.get("signal", "ALERT") if signal else "ALERT"
        if alert_type not in {"BUY", "SELL"}:
            return
        reason = signal.get("reason", "") if signal else ""

    header = f"<b>{alert_type} SIGNAL</b>"
    body = _build_common_body(world, usd, fair, lowest, premium, markets, trends, momentum, previous_markets, input_directions, signal_state)
    _send(_build_message(header, reason, body))


def send_manual_update(world, usd, fair, lowest, premium, markets, trends=None, momentum=None, previous_markets=None, input_directions=None, signal_state=None):
    body = _build_common_body(world, usd, fair, lowest, premium, markets, trends, momentum, previous_markets, input_directions, signal_state)
    _send(_build_message("<b>MANUAL UPDATE</b>", "", body))


def send_data_unavailable(usd=None, markets=None, reason=None):
    lines = [APP_HEADER, "", "<b>DATA UNAVAILABLE</b>", "", reason or "Unable to fetch required market data."]
    if usd is not None:
        lines.append(f"USD Rate: {_money(usd)} IRR")
    if markets:
        valid = [name for name, info in markets.items() if info.get("status") == "OK"]
        lines.append(f"Available platforms: {len(valid)}")
    _send("\n".join(lines))


def send_processing():
    _send(f"{APP_HEADER}\n\n<b>Processing...</b> Gathering market data.")


def send_daily_recap(world, usd, fair, lowest, premium, markets, trends=None, momentum=None, previous_markets=None, input_directions=None, signal_state=None):
    body = _build_common_body(world, usd, fair, lowest, premium, markets, trends, momentum, previous_markets, input_directions, signal_state)
    _send(_build_message("<b>DAILY RECAP</b>", "", body))

# ============================================================
# PRE-SP-C.13 — Analytical Command Formatters
# Consume C.11 consumer contract and C.8 features.
# Do not calculate. Do not decide.
# ============================================================


def send_analysis_update(consumer_envelope: dict):
    """/Analysis — expose latest persisted analytical read state."""
    data = consumer_envelope.get("data", {})
    facts = data.get("facts", {})
    evidence = data.get("evidence_summary", {})
    interpretation = data.get("interpretation_summary", {})
    uncertainty = data.get("uncertainty", {})
    decision = data.get("decision", {})
    completeness = consumer_envelope.get("completeness", "UNKNOWN")

    lines = [
        APP_HEADER,
        "",
        f"<b>ANALYSIS</b>  |  Completeness: <code>{completeness}</code>",
        "",
        "<b>FACTS</b>",
        f"Valuation:  <code>{facts.get('valuation_state', 'UNKNOWN')}</code>",
        f"Momentum:   <code>{facts.get('momentum_state', 'UNKNOWN')}</code>",
        f"Structure:  <code>{facts.get('structure_state', 'UNKNOWN')}</code>",
        f"Regime:     <code>{facts.get('regime_state', 'UNKNOWN')}</code>",
        f"Premium:    {_number(facts.get('premium_percent'))}%",
        "",
        "<b>INTERPRETATION</b>",
        interpretation.get("market_context_summary", "No interpretation available."),
        "",
        "<b>UNCERTAINTY</b>",
    ]
    conflicts = uncertainty.get("conflicts", [])
    missing = uncertainty.get("missing_evidence", [])
    if conflicts:
        lines.append(f"Conflicts: {len(conflicts)}")
    if missing:
        lines.append(f"Missing evidence: {len(missing)}")
    if not conflicts and not missing:
        lines.append("No major uncertainties.")

    lines.extend([
        "",
        "<b>DECISION</b>  <i>(read-only)</i>",
        f"Candidate: <code>{decision.get('candidate_decision', 'UNKNOWN')}</code>",
        f"Final:     <code>{decision.get('final_decision', 'UNKNOWN')}</code>",
    ])

    _send("\n".join(lines))


def send_technical_update(features: dict):
    """/Technical — expose persisted C.8 feature information."""
    price_trend = features.get("price_trend", {}) or {}
    momentum = features.get("momentum", {}) or {}
    volatility = features.get("volatility", {}) or {}
    regime = features.get("regime", {}) or {}

    lines = [
        APP_HEADER,
        "",
        "<b>TECHNICAL</b>",
        "",
        "<b>PRICE TREND</b>",
    ]
    for key in ["rep_gold_ma7", "rep_gold_ma15", "rep_gold_ma30"]:
        val = price_trend.get(key)
        if val is not None:
            lines.append(f"  {key}: {_money(val)}")

    lines.extend([
        "",
        "<b>MOMENTUM</b>",
        f"  Premium Velocity: {_number(momentum.get('premium_velocity'))}",
        f"  Acceleration:     {_number(momentum.get('premium_acceleration'))}",
        f"  Direction:        {momentum.get('premium_latest_direction', 'UNKNOWN')}",
        "",
        "<b>VOLATILITY</b>",
        f"  7-Day CV:  {_number(volatility.get('rep_gold_volatility_7'))}%",
        "",
        "<b>REGIME</b>",
        f"  Current:  <code>{regime.get('current_regime', 'UNKNOWN')}</code>",
        f"  Previous: <code>{regime.get('previous_regime', 'UNKNOWN')}</code>",
    ])

    _send("\n".join(lines))


def send_history_update(snapshots: list):
    """/History — expose recent analytical snapshot summaries."""
    lines = [APP_HEADER, "", "<b>HISTORY</b>", ""]

    if not snapshots:
        lines.append("No historical snapshots available.")
    else:
        lines.append(f"{'Valuation':<10} {'Momentum':<12} {'Regime':<10} {'Premium':>10}")
        lines.append("-" * 48)
        for snap in snapshots[:10]:
            facts = snap.get("facts", {}) or {}
            lines.append(
                f"{facts.get('valuation_state', '?'):<10} "
                f"{facts.get('momentum_state', '?'):<12} "
                f"{facts.get('regime_state', '?'):<10} "
                f"{_number(facts.get('premium_percent')):>10}%"
            )

    _send("\n".join(lines))


def send_news_update(news_events: list):
    """/News — expose structured news context."""
    lines = [APP_HEADER, "", "<b>NEWS</b>", ""]

    if not news_events:
        lines.append("No recent news events.")
    else:
        for ev in news_events[:5]:
            rel = ev.get("relevance", "?")
            evt = ev.get("event_type", "?")
            topic = ev.get("topic", "No topic")
            lines.append(f"• [{rel}] {evt}: {topic}")

    _send("\n".join(lines))


def send_health_update(health: dict):
    """/Health — expose operational health metrics."""
    lines = [
        APP_HEADER,
        "",
        "<b>HEALTH</b>",
        "",
        f"Latest Analysis:    {health.get('latest_analysis_time') or 'N/A'}",
        f"Latest Market Snap: {health.get('latest_snapshot_time') or 'N/A'}",
        f"Analysis Snapshots: {health.get('analysis_snapshot_count', 0)}",
        f"Outcome Evals:      {health.get('outcome_count', 0)}",
        f"Sources:            {health.get('sources_available', 0)}/{health.get('sources_total', 0)}",
        f"Database:           <code>{health.get('database_status', 'UNKNOWN')}</code>",
    ]

    _send("\n".join(lines))







# ============================================================
# UPDATE v1 formatter
# ============================================================

from update.baseline_resolver import UpdateBaselines
from alerts.helpers import (
    classify_candle,
    build_update_interpretation,
    bubble_state_label,
    bubble_state_short,
    format_pct,
    format_pp,
    format_arrow,
)


def _update_sep():
    return "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"


def _build_update_market_section(
    world: Optional[float],
    usd: Optional[float],
    fair: Optional[float],
    platform_avg: Optional[float],
    lowest: Optional[float],
    premium: float,
    baselines: UpdateBaselines,
) -> str:
    """Build MARKET section for UPDATE v1."""
    lines = [
        _update_sep(),
        "<b>MARKET</b>",
        _update_sep(),
        "",
    ]

    # XAU/USD
    run_world = baselines.run.xau_usd if baselines.run else None
    day_world = baselines.day.xau_usd if baselines.day else None
    world_run_pct = ((world - run_world) / run_world * 100) if world and run_world and run_world != 0 else None
    world_day_pct = ((world - day_world) / day_world * 100) if world and day_world and day_world != 0 else None
    lines.append(f"<code>XAU/USD        {_money(world)}</code>")
    lines.append(f"<code>               {format_arrow(world_run_pct)} {format_pct(world_run_pct)} Run | {format_arrow(world_day_pct)} {format_pct(world_day_pct)} Day</code>")
    lines.append("")

    # USD/IRR
    run_usd = baselines.run.usd_irr if baselines.run else None
    day_usd = baselines.day.usd_irr if baselines.day else None
    usd_run_pct = ((usd - run_usd) / run_usd * 100) if usd and run_usd and run_usd != 0 else None
    usd_day_pct = ((usd - day_usd) / day_usd * 100) if usd and day_usd and day_usd != 0 else None
    lines.append(f"<code>USD/IRR        {_money(usd)}</code>")
    lines.append(f"<code>               {format_arrow(usd_run_pct)} {format_pct(usd_run_pct)} Run | {format_arrow(usd_day_pct)} {format_pct(usd_day_pct)} Day</code>")
    lines.append("")

    # Fair Price
    run_fair = baselines.run.fair_price if baselines.run else None
    day_fair = baselines.day.fair_price if baselines.day else None
    fair_run_pct = ((fair - run_fair) / run_fair * 100) if fair and run_fair and run_fair != 0 else None
    fair_day_pct = ((fair - day_fair) / day_fair * 100) if fair and day_fair and day_fair != 0 else None
    lines.append(f"<code>Fair Price     {_money(fair)} IRR</code>")
    lines.append(f"<code>               {format_arrow(fair_run_pct)} {format_pct(fair_run_pct)} Run | {format_arrow(fair_day_pct)} {format_pct(fair_day_pct)} Day</code>")
    lines.append("")

    # Platform Average
    run_avg = baselines.run.platform_average if baselines.run else None
    day_avg = baselines.day.platform_average if baselines.day else None
    avg_run_pct = ((platform_avg - run_avg) / run_avg * 100) if platform_avg and run_avg and run_avg != 0 else None
    avg_day_pct = ((platform_avg - day_avg) / day_avg * 100) if platform_avg and day_avg and day_avg != 0 else None
    lines.append(f"<code>Platform Avg   {_money(platform_avg)} IRR</code>")
    lines.append(f"<code>               {format_arrow(avg_run_pct)} {format_pct(avg_run_pct)} Run | {format_arrow(avg_day_pct)} {format_pct(avg_day_pct)} Day</code>")
    lines.append("")

    # Bubble
    run_premium = baselines.run.premium_percent if baselines.run else None
    day_premium = baselines.day.premium_percent if baselines.day else None
    premium_run_pp = (premium - run_premium) if run_premium is not None else None
    premium_day_pp = (premium - day_premium) if day_premium is not None else None
    lines.append(f"<code>Bubble         {_number(premium)}%  {bubble_state_short(premium)}</code>")
    lines.append(f"<code>               {format_arrow(premium_run_pp)} {format_pp(premium_run_pp)} Run | {format_arrow(premium_day_pp)} {format_pp(premium_day_pp)} Day</code>")
    lines.append("")

    # Lowest / Highest / Spread
    lines.append(f"<code>Lowest         {_money(lowest)} IRR</code>")
    # Highest is computed from current markets, shown in structure section
    # Spread is also in structure section

    return "\n".join(lines)


def _build_update_dynamics_section(
    price_direction: str,
    price_pace: str,
    acceleration_label: str,
    premium: float,
    bubble_movement: str,
    bubble_pace: str,
    candle_label: str,
    interpretation: str,
) -> str:
    """Build PRICE & BUBBLE DYNAMICS section."""
    lines = [
        _update_sep(),
        "<b>PRICE & BUBBLE DYNAMICS</b>",
        _update_sep(),
        "",
        f"<code>Price          {price_direction}</code>",
        f"<code>Pace           {price_pace}</code>",
        f"<code>Acceleration   {acceleration_label}</code>",
        "",
        f"<code>Bubble         {bubble_state_short(premium)}</code>",
        f"<code>               {_number(premium)}%</code>",
        "",
        f"<code>Bubble         {bubble_movement}</code>",
        f"<code>Bubble Pace    {bubble_pace}</code>",
        "",
        f"<code>Candle         {candle_label}</code>",
        "",
        "<b>Interpretation</b>",
        interpretation,
    ]
    return "\n".join(lines)


def _build_update_structure_section(
    markets: Dict[str, Any],
    fair: Optional[float],
    baselines: UpdateBaselines,
) -> str:
    """Build MARKET STRUCTURE section."""
    structure = format_market_structure(markets, fair)
    if not structure:
        return ""

    lines = [
        _update_sep(),
        "<b>MARKET STRUCTURE</b>",
        _update_sep(),
        "",
        f"<code>Platforms      {structure['platform_count']} active</code>",
        f"<code>Spread         {structure['spread']:,.0f} IRR</code>",
        "",
    ]

    # Highest with DAY relative position
    high_name = structure["high_name"]
    high_price = structure["high_price"]
    day_high_price = baselines.day.platform_prices.get(high_name) if baselines.day else None
    high_day_pct = ((high_price - day_high_price) / day_high_price * 100) if high_price and day_high_price and day_high_price != 0 else None
    lines.append(f"<code>Highest        {high_name}</code>")
    lines.append(f"<code>               {_money(high_price)}</code>")
    if high_day_pct is not None:
        lines.append(f"<code>               {format_pct(high_day_pct)} vs Day</code>")
    lines.append("")

    # Lowest with DAY relative position
    low_name = structure["low_name"]
    low_price = structure["low_price"]
    day_low_price = baselines.day.platform_prices.get(low_name) if baselines.day else None
    low_day_pct = ((low_price - day_low_price) / day_low_price * 100) if low_price and day_low_price and day_low_price != 0 else None
    lines.append(f"<code>Lowest         {low_name}</code>")
    lines.append(f"<code>               {_money(low_price)}</code>")
    if low_day_pct is not None:
        lines.append(f"<code>               {format_pct(low_day_pct)} vs Day</code>")
    lines.append("")

    # Consensus
    consensus = structure["consensus_label"]
    # Translate to bubble terminology
    if "Discount Dominant" in consensus:
        consensus_telegram = "NEGATIVE BUBBLE DOMINANT"
    elif "Premium Dominant" in consensus:
        consensus_telegram = "POSITIVE BUBBLE DOMINANT"
    else:
        consensus_telegram = consensus
    lines.append(f"<code>Consensus      {consensus_telegram}</code>")

    return "\n".join(lines)


def _build_update_platforms_section(
    markets: Dict[str, Any],
    baselines: UpdateBaselines,
) -> str:
    """Build PLATFORMS table section."""
    lines = [
        _update_sep(),
        "<b>PLATFORMS</b>",
        _update_sep(),
        "",
    ]

    # Build table header and rows
    table_lines = [
        "Platform       Price          Run Δ       vs Day",
        "────────────────────────────────────────────────",
    ]

    for name in sorted(markets.keys()):
        info = markets[name]
        if info.get("status") != "OK":
            continue
        price = info["price"]

        # RUN Δ (absolute IRR change from latest snapshot)
        run_price = baselines.run.platform_prices.get(name) if baselines.run else None
        if run_price is not None:
            run_diff = price - run_price
            run_delta = "—" if abs(run_diff) < 0.01 else f"{run_diff:+,.0f}"
        else:
            run_delta = "—"

        # vs DAY (percentage change from first today snapshot)
        day_price = baselines.day.platform_prices.get(name) if baselines.day else None
        if day_price is not None and day_price != 0:
            day_pct = ((price - day_price) / day_price) * 100
            day_str = f"{day_pct:+.2f}%"
        else:
            day_str = "—"

        table_lines.append(f"{name:<14} {price:>15,.0f} {run_delta:>12} {day_str:>10}")

    lines.append("<pre>" + "\n".join(table_lines) + "</pre>")

    return "\n".join(lines)


def _build_update_decision_section(signal_state) -> str:
    """Build CURRENT DECISION section."""
    if signal_state is None:
        return ""

    lines = [
        _update_sep(),
        "<b>CURRENT DECISION</b>",
        _update_sep(),
        "",
        f"<code>Valuation      {signal_state.valuation}</code>",
        f"<code>Momentum       {signal_state.momentum}</code>",
        f"<code>Structure      {signal_state.structure.replace('_', ' ')}</code>",
        f"<code>Conflict       {signal_state.conflict.replace('_', ' ')}</code>",
        "",
        f"<code>Candidate      {signal_state.candidate_decision}</code>",
    ]
    final = signal_state.final_decision
    if final in {"BUY", "SELL", "WAIT"}:
        lines.append(f"<code>Final          <b>{final}</b></code>")
    else:
        lines.append(f"<code>Final          {final}</code>")
    lines.append("")
    lines.append(f"<b>{format_timestamp()}</b>")

    return "\n".join(lines)


def send_update_v1(
    world: Optional[float],
    usd: Optional[float],
    fair: Optional[float],
    platform_avg: Optional[float],
    lowest: Optional[float],
    premium: float,
    markets: Dict[str, Any],
    signal_state,
    baselines: UpdateBaselines,
    momentum: Optional[Dict] = None,
):
    """Send UPDATE v1 Telegram message.

    Replaces send_manual_update with the approved information architecture.
    Does not calculate — consumes already-resolved baselines and current state.
    """
    # Classifications
    price_direction = baselines.price_direction
    price_pace = "N/A"  # Deferred pending empirical calibration
    acceleration_label = baselines.rep_gold_acceleration_label
    bubble_state = bubble_state_short(premium)
    bubble_movement = baselines.bubble_movement
    bubble_pace = "N/A"  # Deferred pending empirical calibration
    candle_label = classify_candle(momentum)
    interpretation = build_update_interpretation(
        price_direction=price_direction,
        bubble_state=bubble_state,
        bubble_movement=bubble_movement,
    )

    # Build sections
    header = "<b>GOLDPremium: UPDATE</b>"
    market_section = _build_update_market_section(
        world, usd, fair, platform_avg, lowest, premium, baselines
    )
    dynamics_section = _build_update_dynamics_section(
        price_direction, price_pace, acceleration_label,
        premium, bubble_movement, bubble_pace, candle_label, interpretation
    )
    structure_section = _build_update_structure_section(markets, fair, baselines)
    platforms_section = _build_update_platforms_section(markets, baselines)
    decision_section = _build_update_decision_section(signal_state)

    body = "\n\n".join([
        header,
        market_section,
        dynamics_section,
        structure_section,
        platforms_section,
        decision_section,
    ])

    _send(body)
