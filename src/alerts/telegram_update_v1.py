"""UPDATE v1 Telegram formatter.

Presentation-only module for the fast user-triggered UPDATE wing.
Consumes current values, resolved baselines, and existing analytical context.
Does not calculate market state or run the Analyze pipeline.
"""

from typing import Any, Dict, Optional

from alerts.telegram import _money, _number, _send
from alerts.helpers import (
    classify_candle,
    build_update_interpretation,
    bubble_state_short,
    format_pct,
    format_pp,
    format_arrow,
    format_market_structure,
    format_timestamp,
)
from update.baseline_resolver import UpdateBaselines


def _update_sep():
    return "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"


def _pct_change(current, baseline):
    if current is None or baseline in (None, 0):
        return None
    return (current - baseline) / baseline * 100


def _build_market(world, usd, fair, platform_avg, lowest, premium, baselines):
    run = baselines.run
    day = baselines.day
    lines = [_update_sep(), "<b>MARKET</b>", _update_sep(), ""]
    for label, value, run_value, day_value, suffix, is_pp in [
        ("XAU/USD", world, run.xau_usd if run else None, day.xau_usd if day else None, "", False),
        ("USD/IRR", usd, run.usd_irr if run else None, day.usd_irr if day else None, "", False),
        ("Fair Price", fair, run.fair_price if run else None, day.fair_price if day else None, " IRR", False),
        ("Platform Avg", platform_avg, run.platform_average if run else None, day.platform_average if day else None, " IRR", False),
        ("Bubble", premium, run.premium_percent if run else None, day.premium_percent if day else None, "%", True),
    ]:
        if is_pp:
            run_change = value - run_value if value is not None and run_value is not None else None
            day_change = value - day_value if value is not None and day_value is not None else None
            lines.append(f"<code>{label:<14} {_number(value)}{suffix}</code>")
            lines.append(f"<code>{'':14} {format_arrow(run_change)} {format_pp(run_change)} Run | {format_arrow(day_change)} {format_pp(day_change)} Day</code>")
        else:
            run_change = _pct_change(value, run_value)
            day_change = _pct_change(value, day_value)
            value_text = _money(value)
            if label == "XAU/USD":
                value_text = "$" + value_text
            lines.append(f"<code>{label:<14} {value_text}{suffix}</code>")
            lines.append(f"<code>{'':14} {format_arrow(run_change)} {format_pct(run_change)} Run | {format_arrow(day_change)} {format_pct(day_change)} Day</code>")
        lines.append("")
    lines.append(f"<code>{'Lowest':<14} {_money(lowest)} IRR</code>")
    return "\n".join(lines)


def _build_dynamics(premium, baselines, momentum):
    bubble_state = bubble_state_short(premium)
    interpretation = build_update_interpretation(
        baselines.price_direction, bubble_state, baselines.bubble_movement
    )
    return "\n".join([
        _update_sep(),
        "<b>PRICE &amp; BUBBLE DYNAMICS</b>",
        _update_sep(),
        "",
        f"<code>Price          {baselines.price_direction}</code>",
        "<code>Pace           N/A</code>",
        f"<code>Acceleration   {baselines.rep_gold_acceleration_label}</code>",
        "",
        f"<code>Bubble         {bubble_state}</code>",
        f"<code>               {_number(premium)}%</code>",
        f"<code>Movement       {baselines.bubble_movement}</code>",
        "<code>Bubble Pace    N/A</code>",
        "",
        f"<code>Candle         {classify_candle(momentum)}</code>",
        "",
        "<b>Interpretation</b>",
        interpretation,
    ])


def _build_structure(markets, fair, baselines):
    structure = format_market_structure(markets, fair)
    if not structure:
        return ""
    lines = [_update_sep(), "<b>MARKET STRUCTURE</b>", _update_sep(), ""]
    lines.append(f"<code>Platforms      {structure['platform_count']} active</code>")
    lines.append(f"<code>Spread         {structure['spread']:,.0f} IRR</code>")
    lines.append("")
    for title, name_key, price_key in (("Highest", "high_name", "high_price"), ("Lowest", "low_name", "low_price")):
        name = structure[name_key]
        price = structure[price_key]
        day_price = baselines.day.platform_prices.get(name) if baselines.day else None
        day_change = _pct_change(price, day_price)
        lines.append(f"<code>{title:<14} {name}</code>")
        lines.append(f"<code>{'':14} {_money(price)} IRR | {format_pct(day_change)} vs Day</code>")
        lines.append("")
    consensus = structure["consensus_label"]
    if "Discount Dominant" in consensus:
        consensus = consensus.replace("Discount Dominant", "NEGATIVE BUBBLE DOMINANT")
    elif "Premium Dominant" in consensus:
        consensus = consensus.replace("Premium Dominant", "POSITIVE BUBBLE DOMINANT")
    lines.append(f"<code>Consensus      {consensus}</code>")
    return "\n".join(lines)


def _build_platforms(markets, baselines):
    lines = [_update_sep(), "<b>PLATFORMS</b>", _update_sep(), ""]
    rows = [
        "Platform       Price          Run Δ       vs Day",
        "────────────────────────────────────────────────",
    ]
    for name in sorted(markets.keys()):
        info = markets[name]
        if info.get("status") != "OK" or info.get("price") is None:
            continue
        price = float(info["price"])
        run_price = baselines.run.platform_prices.get(name) if baselines.run else None
        day_price = baselines.day.platform_prices.get(name) if baselines.day else None
        run_delta = f"{price - run_price:+,.0f}" if run_price is not None else "—"
        day_pct = _pct_change(price, day_price)
        day_text = f"{day_pct:+.2f}%" if day_pct is not None else "—"
        rows.append(f"{name:<14} {price:>15,.0f} {run_delta:>12} {day_text:>10}")
    lines.append("<pre>" + "\n".join(rows) + "</pre>")
    return "\n".join(lines)


def _build_decision(signal_state):
    if signal_state is None:
        return ""
    final = signal_state.final_decision
    return "\n".join([
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
        f"<code>Final          <b>{final}</b></code>",
        "",
        f"<b>{format_timestamp()}</b>",
    ])


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
    if baselines is None:
        raise RuntimeError("UPDATE v1 requires resolved baselines")
    body = "\n\n".join([
        "<b>GOLDPremium: UPDATE</b>",
        _build_market(world, usd, fair, platform_avg, lowest, premium, baselines),
        _build_dynamics(premium, baselines, momentum),
        _build_structure(markets, fair, baselines),
        _build_platforms(markets, baselines),
        _build_decision(signal_state),
    ])
    _send(body)
