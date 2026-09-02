"""UPDATE v1 Telegram formatter — Chunk C (visual/mobile fixes).

Presentation-only module for the fast user-triggered UPDATE wing.
Consumes current values, resolved baselines, and existing analytical context.
Does not calculate market state or run the Analyze pipeline.

Visual design decisions:
- <code> tags removed from non-table sections (mobile readability)
- Vertical spacing compressed within sections
- All prices converted to Tomans (1 Toman = 10 Rials)
- Platform table uses abbreviated M-Tomans format for mobile width
- Arrows paired with absolute values (no double-negative)
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
    format_m_tomans,
    format_m_tomans_short,
)
from update.baseline_resolver import UpdateBaselines


def _update_sep():
    return "━━━━━━━━━━━━━━━━━━━━"


def _pct_change(current, baseline):
    if current is None or baseline in (None, 0):
        return None
    return (current - baseline) / baseline * 100


# ---------------------------------------------------------------------------
# MARKET section
# ---------------------------------------------------------------------------

def _build_market(world, usd, fair, platform_avg, lowest, highest, spread, premium, baselines):
    run = baselines.run
    day = baselines.day
    lines = [_update_sep(), "<b>MARKET</b>", _update_sep()]

    # XAU/USD
    run_change = _pct_change(world, run.xau_usd if run else None)
    day_change = _pct_change(world, day.xau_usd if day else None)
    lines.append(f"<b>XAU/USD</b>  ${_money(world)}")
    lines.append(f"               {format_arrow(run_change)} {format_pct(run_change, signed=False)} Run | {format_arrow(day_change)} {format_pct(day_change, signed=False)} Day")

    # USD/IRR
    run_change = _pct_change(usd, run.usd_irr if run else None)
    day_change = _pct_change(usd, day.usd_irr if day else None)
    lines.append(f"<b>USD/IRR</b>  {_money(usd)}")
    lines.append(f"               {format_arrow(run_change)} {format_pct(run_change, signed=False)} Run | {format_arrow(day_change)} {format_pct(day_change, signed=False)} Day")

    # Fair Price
    run_change = _pct_change(fair, run.fair_price if run else None)
    day_change = _pct_change(fair, day.fair_price if day else None)
    lines.append(f"<b>Fair Price</b>  {format_m_tomans(fair)}")
    lines.append(f"               {format_arrow(run_change)} {format_pct(run_change, signed=False)} Run | {format_arrow(day_change)} {format_pct(day_change, signed=False)} Day")

    # Platform Average
    run_change = _pct_change(platform_avg, run.platform_average if run else None)
    day_change = _pct_change(platform_avg, day.platform_average if day else None)
    lines.append(f"<b>Platform Avg</b>  {format_m_tomans(platform_avg)}")
    lines.append(f"               {format_arrow(run_change)} {format_pct(run_change, signed=False)} Run | {format_arrow(day_change)} {format_pct(day_change, signed=False)} Day")

    # Bubble
    run_pp = (premium - run.premium_percent) if run and run.premium_percent is not None else None
    day_pp = (premium - day.premium_percent) if day and day.premium_percent is not None else None
    lines.append(f"<b>Bubble</b>  {_number(premium)}%  {bubble_state_short(premium)}")
    lines.append(f"               {format_arrow(run_pp)} {format_pp(run_pp, signed=False)} Run | {format_arrow(day_pp)} {format_pp(day_pp, signed=False)} Day")

    # Lowest / Highest / Spread
    lines.append(f"<b>Lowest</b>  {format_m_tomans(lowest)}")
    lines.append(f"<b>Highest</b>  {format_m_tomans(highest)}")
    lines.append(f"<b>Spread</b>  {format_m_tomans(spread)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PRICE & BUBBLE DYNAMICS section
# ---------------------------------------------------------------------------

def _build_dynamics(premium, baselines, momentum):
    bubble_state = bubble_state_short(premium)
    interpretation = build_update_interpretation(
        baselines.price_direction, bubble_state, baselines.bubble_movement
    )
    return "\n".join([
        _update_sep(),
        "<b>PRICE & BUBBLE DYNAMICS</b>",
        _update_sep(),
        f"<b>Price</b>  {baselines.price_direction}",
        f"<b>Pace</b>  N/A",
        f"<b>Acceleration</b>  {baselines.rep_gold_acceleration_label}",
        "",
        f"<b>Bubble</b>  {bubble_state}",
        f"               {_number(premium)}%",
        "",
        f"<b>Bubble</b>  {baselines.bubble_movement}",
        f"<b>Bubble Pace</b>  N/A",
        "",
        f"<b>Candle</b>  {classify_candle(momentum)}",
        "",
        "<b>Interpretation</b>",
        interpretation,
    ])


# ---------------------------------------------------------------------------
# MARKET STRUCTURE section
# ---------------------------------------------------------------------------

def _build_structure(markets, fair, baselines):
    structure = format_market_structure(markets, fair)
    if not structure:
        return ""
    lines = [_update_sep(), "<b>MARKET STRUCTURE</b>", _update_sep()]
    lines.append(f"<b>Platforms</b>  {structure['platform_count']} active")
    lines.append(f"<b>Spread</b>  {format_m_tomans(structure['spread'])}")
    lines.append("")

    # Highest with DAY relative position
    high_name = structure["high_name"]
    high_price = structure["high_price"]
    day_high_price = baselines.day.platform_prices.get(high_name) if baselines.day else None
    high_day_pct = _pct_change(high_price, day_high_price)
    lines.append(f"<b>Highest</b>  {high_name}")
    lines.append(f"               {format_m_tomans(high_price)}")
    if high_day_pct is not None:
        lines.append(f"               {format_pct(high_day_pct, signed=True)} vs Day")
    lines.append("")

    # Lowest with DAY relative position
    low_name = structure["low_name"]
    low_price = structure["low_price"]
    day_low_price = baselines.day.platform_prices.get(low_name) if baselines.day else None
    low_day_pct = _pct_change(low_price, day_low_price)
    lines.append(f"<b>Lowest</b>  {low_name}")
    lines.append(f"               {format_m_tomans(low_price)}")
    if low_day_pct is not None:
        lines.append(f"               {format_pct(low_day_pct, signed=True)} vs Day")
    lines.append("")

    # Consensus
    consensus = structure["consensus_label"]
    below = structure.get("below_count")
    above = structure.get("above_count")
    total = structure.get("platform_count", 0)
    if below is not None and above is not None:
        if below > above:
            consensus_telegram = f"{below}/{total} below Fair Price\n               NEGATIVE BUBBLE DOMINANT"
        elif above > below:
            consensus_telegram = f"{above}/{total} above Fair Price\n               POSITIVE BUBBLE DOMINANT"
        else:
            consensus_telegram = f"{total}/{total} mixed\n               BALANCED"
    else:
        if "Discount Dominant" in consensus:
            consensus_telegram = "NEGATIVE BUBBLE DOMINANT"
        elif "Premium Dominant" in consensus:
            consensus_telegram = "POSITIVE BUBBLE DOMINANT"
        else:
            consensus_telegram = consensus
    lines.append(f"<b>Consensus</b>  {consensus_telegram}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PLATFORMS section — narrow table, M Tomans
# ---------------------------------------------------------------------------

def _build_platforms(markets, baselines):
    lines = [_update_sep(), "<b>PLATFORMS</b>", _update_sep(), ""]
    rows = [
        "Platform   Price    Run Δ   vs Day",
        "───────────────────────────────────",
    ]
    for name in sorted(markets.keys()):
        info = markets[name]
        if info.get("status") != "OK" or info.get("price") is None:
            continue
        price = float(info["price"])
        run_price = baselines.run.platform_prices.get(name) if baselines.run else None
        day_price = baselines.day.platform_prices.get(name) if baselines.day else None

        # RUN Δ in M Tomans
        if run_price is not None:
            run_diff = price - run_price
            threshold = abs(run_price) * 0.0001  # 0.01%
            if abs(run_diff) < threshold:
                run_delta = "—"
            else:
                run_delta = format_m_tomans_short(run_diff, decimals=2)
        else:
            run_delta = "—"

        # vs DAY percentage
        day_pct = _pct_change(price, day_price)
        day_text = format_pct(day_pct, signed=True) if day_pct is not None else "—"

        price_str = format_m_tomans_short(price, decimals=2)
        rows.append(f"{name:<10} {price_str:>7} {run_delta:>7} {day_text:>8}")

    lines.append("<pre>" + "\n".join(rows) + "</pre>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CURRENT DECISION section
# ---------------------------------------------------------------------------

def _build_decision(signal_state):
    if signal_state is None:
        return ""
    final = signal_state.final_decision
    lines = [
        _update_sep(),
        "<b>CURRENT DECISION</b>",
        _update_sep(),
        f"<b>Valuation</b>  {signal_state.valuation}",
        f"<b>Momentum</b>  {signal_state.momentum}",
        f"<b>Structure</b>  {signal_state.structure.replace('_', ' ')}",
        f"<b>Conflict</b>  {signal_state.conflict.replace('_', ' ')}",
        "",
        f"<b>Candidate</b>  {signal_state.candidate_decision}",
    ]
    if final in {"BUY", "SELL", "WAIT"}:
        lines.append(f"<b>Final</b>  <b>{final}</b>")
    else:
        lines.append(f"<b>Final</b>  {final}")
    lines.append("")
    lines.append(f"<b>{format_timestamp()}</b>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main formatter
# ---------------------------------------------------------------------------

def send_update_v1(
    world: Optional[float],
    usd: Optional[float],
    fair: Optional[float],
    platform_avg: Optional[float],
    lowest: Optional[float],
    highest: Optional[float],
    spread: Optional[float],
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
        _build_market(world, usd, fair, platform_avg, lowest, highest, spread, premium, baselines),
        _build_dynamics(premium, baselines, momentum),
        _build_structure(markets, fair, baselines),
        _build_platforms(markets, baselines),
        _build_decision(signal_state),
    ])
    _send(body)
