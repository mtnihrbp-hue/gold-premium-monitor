"""UPDATE v1 Telegram formatter — Chunk C (visual/mobile fixes).

Presentation-only module for the fast user-triggered UPDATE wing.
Consumes current values, resolved baselines, and existing analytical context.
Does not calculate market state or run the Analyze pipeline.

Visual design decisions:
- <code> tags removed from non-table sections (mobile readability)
- Vertical spacing compressed within sections
- All prices converted to Tomans (1 Toman = 10 Rials)
- Market and platform tables use compact fixed-width layouts
- Signed deltas are shown directly (no directional arrows)
- 7D context is shown as a reusable historical trend reference
"""

from datetime import datetime
from typing import Any, Dict, Optional

from alerts.telegram import _money, _number, _send
from alerts.helpers import (
    classify_candle,
    bubble_state_short,
    format_pct,
    format_pp,
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


def _bubble_direction(premium, gap_delta):
    """Describe movement toward a larger/smaller premium or discount."""
    if premium is None or gap_delta is None:
        return "N/A"
    threshold = 0.05
    if abs(gap_delta) < threshold:
        return "STABLE"
    if premium < 0:
        return "MORE DISCOUNT" if gap_delta < 0 else "LESS DISCOUNT"
    if premium > 0:
        return "MORE PREMIUM" if gap_delta > 0 else "LESS PREMIUM"
    return "MORE PREMIUM" if gap_delta > 0 else "MORE DISCOUNT"


def _build_dynamics_interpretation(price_direction, price_change, premium, gap_direction, gap_delta):
    """Build human-readable interpretation from measured price/gap movement.

    Describes observable relationships only. Per C14_HANDOFF.md and
    RESEARCH_ADOPTION.md, the internal DISCOUNT WIDENING / NARROWING vocabulary
    must not be surfaced in user-facing output, and no causal claim is made.
    """
    price_phrase = None
    if price_direction == "RISING":
        price_phrase = "Local prices are rising"
    elif price_direction == "FALLING":
        price_phrase = "Local prices are falling"
    elif price_direction == "STABLE":
        price_phrase = "Local prices are stable"

    if price_phrase is not None and price_change is not None:
        price_phrase += f" ({price_change:+.2f}%)"

    gap_phrase = None
    if premium is not None:
        if gap_direction in ("MORE DISCOUNT", "MORE PREMIUM"):
            side = "below" if premium < 0 else "above"
            gap_phrase = f"moving further {side} fair value"
        elif gap_direction in ("LESS DISCOUNT", "LESS PREMIUM"):
            gap_phrase = "closing the gap to fair value"
        elif gap_direction == "STABLE":
            gap_phrase = "holding their distance from fair value"

    if gap_phrase is not None and gap_delta is not None and abs(gap_delta) >= 0.05:
        gap_phrase += f" ({gap_delta:+.2f} pp)"

    if price_phrase and gap_phrase:
        return f"{price_phrase}, while {gap_phrase}."
    if price_phrase:
        return f"{price_phrase}."
    if gap_phrase:
        return f"Local prices are {gap_phrase}."
    return "Insufficient data for interpretation."


# ---------------------------------------------------------------------------
# MARKET section
# ---------------------------------------------------------------------------

MARKET_TABLE_WIDTH = 48


def _pp_compact(value):
    """Percentage points without the unit space, so table columns keep a gutter."""
    return "—" if value is None else f"{value:+.2f}pp"


def _market_row(metric, now_text, run_text, day_text, seven_day_text):
    """Fixed-width row. Cell content must stay short or columns shear apart."""
    return f"{metric:<12}{now_text:>9}{run_text:>9}{day_text:>9}{seven_day_text:>9}"


def _build_market(world, usd, fair, platform_avg, lowest, highest, spread, premium, baselines,
                  world_from_fallback=False):
    run = baselines.run
    day = baselines.day
    seven = baselines.seven_day
    lines = [_update_sep(), "<b>MARKET</b>", _update_sep()]

    rows = [
        _market_row("", "Now", "Run", "Day", "7D avg"),
        "─" * MARKET_TABLE_WIDTH,
    ]

    rows.append(_market_row(
        "XAU/USD",
        f"${_money(world)}" if world is not None else "N/A",
        format_pct(_pct_change(world, run.xau_usd if run else None), signed=True),
        format_pct(_pct_change(world, day.xau_usd if day else None), signed=True),
        format_pct(_pct_change(world, seven.xau_usd), signed=True),
    ))
    rows.append(_market_row(
        "USD/IRR",
        _money(usd) if usd is not None else "N/A",
        format_pct(_pct_change(usd, run.usd_irr if run else None), signed=True),
        format_pct(_pct_change(usd, day.usd_irr if day else None), signed=True),
        format_pct(_pct_change(usd, seven.usd_irr), signed=True),
    ))
    rows.append(_market_row(
        "Fair Price",
        format_m_tomans_short(fair),
        format_pct(_pct_change(fair, run.fair_price if run else None), signed=True),
        format_pct(_pct_change(fair, day.fair_price if day else None), signed=True),
        format_pct(_pct_change(fair, seven.fair_price), signed=True),
    ))
    rows.append(_market_row(
        "Platform Avg",
        format_m_tomans_short(platform_avg),
        format_pct(_pct_change(platform_avg, run.platform_average if run else None), signed=True),
        format_pct(_pct_change(platform_avg, day.platform_average if day else None), signed=True),
        format_pct(_pct_change(platform_avg, seven.platform_average), signed=True),
    ))
    rows.append(_market_row(
        "Bubble",
        f"{_number(premium)}%",
        _pp_compact((premium - run.premium_percent) if run and run.premium_percent is not None else None),
        _pp_compact((premium - day.premium_percent) if day and day.premium_percent is not None else None),
        _pp_compact((premium - seven.premium_percent) if seven.premium_percent is not None else None),
    ))

    lines.append("<pre>" + "\n".join(rows) + "</pre>")
    lines.append(f"<b>Lowest</b>  {format_m_tomans(lowest)}")
    lines.append(f"<b>Highest</b>  {format_m_tomans(highest)}")
    lines.append(f"<b>Spread</b>  {format_m_tomans(spread)}")
    lines.append("")
    # Run and Day are point-to-point; the 7D column is a comparison against a mean.
    # Labelling it plainly stops the three being read as the same kind of measure.
    lines.append("<i>Run and Day compare against a single earlier reading.</i>")
    lines.append("<i>7D avg compares against the mean of 7 completed days.</i>")
    if world_from_fallback:
        # Fail-safe rule: a fallback value must carry degraded provenance to the reader,
        # otherwise a cached price is indistinguishable from a fresh quote.
        lines.append("")
        lines.append("⚠ XAU/USD is a cached fallback, not a fresh quote.")
        lines.append("Fair Price and Bubble derive from it.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PRICE & BUBBLE DYNAMICS section
# ---------------------------------------------------------------------------

def _build_verdict(signal_state, position):
    """Decision first, with the one line that justifies it.

    The decision previously sat at the foot of the message, below several hundred
    characters of detail. A reader wanting to know whether to act had to reach the
    end to find out.
    """
    if signal_state is None:
        return "<b>GOLDPremium: UPDATE</b>"

    final = signal_state.final_decision
    line = None
    if position is not None and position.band == "CHEAP":
        line = "Cheap against its own recent range."
    elif position is not None and position.band == "EXPENSIVE":
        line = "Expensive against its own recent range."
    elif position is not None and position.band == "TYPICAL":
        line = "Middle of its own recent range. No edge here."

    parts = ["<b>GOLDPremium: UPDATE</b>", "", f"<b>{final}</b>"]
    if line:
        parts.append(line)
    return "\n".join(parts)


def _build_the_number(premium, lowest, fair, signal_state, position, trend):
    """The figures a decision actually rests on, in one block."""
    lines = [_update_sep(), "<b>THE NUMBER</b>", _update_sep()]
    lines.append(f"<b>Bubble</b>          {_number(premium)}%")

    if position is not None and position.percentile is not None:
        lines.append(f"<b>Position</b>        {position.percentile} of 100")
        lines.append("                0 = cheapest, 100 = most expensive")
        if position.cheap_below is not None:
            lines.append(f"<b>Cheap below</b>     {_number(position.cheap_below)}%")
        if position.confidence in ("LOW", "INSUFFICIENT_DATA"):
            lines.append(f"<b>Confidence</b>      {position.confidence.replace('_', ' ')}")
    else:
        lines.append("<b>Position</b>        not enough history yet")

    lines.append("")
    if signal_state is not None:
        lines.append(f"<b>Momentum</b>        {signal_state.momentum}")
        below = getattr(signal_state, "platforms_below_fair", None)
        above = getattr(signal_state, "platforms_above_fair", None)
        if below is not None and above is not None:
            lines.append(f"<b>Structure</b>       {below} of {below + above} below fair")

    if trend is not None and trend.status == "OK":
        # Name both sides of every comparison. "now below" on its own leaves the
        # reader asking below what.
        lines.append(f"<b>7-day average</b>   {_number(trend.short_average)}%")
        lines.append(f"<b>Bubble vs 7D</b>    {trend.versus_short.lower()}")
        reading = "discount shrinking" if trend.reading == "DISCOUNT_SHRINKING" else "discount deepening"
        lines.append(f"<b>7D vs 15D</b>       {trend.cross.lower()}   {reading}")

    lines.append("")
    lines.append(f"<b>Market low</b>      {format_m_tomans(lowest)}")
    lines.append(f"<b>Fair value</b>      {format_m_tomans(fair)}")
    return "\n".join(lines)


def _build_dynamics(platform_avg, premium, baselines, momentum):
    run = baselines.run
    price_change = _pct_change(platform_avg, run.platform_average if run else None)
    gap_delta = (
        premium - run.premium_percent
        if run and run.premium_percent is not None and premium is not None
        else None
    )
    gap_direction = _bubble_direction(premium, gap_delta)
    bubble_state = bubble_state_short(premium)
    interpretation = _build_dynamics_interpretation(
        baselines.price_direction,
        price_change,
        premium,
        gap_direction,
        gap_delta,
    )
    return "\n".join([
        _update_sep(),
        "<b>PRICE & BUBBLE DYNAMICS</b>",
        _update_sep(),
        f"<b>Local price</b>  {baselines.price_direction}",
        f"<b>Change</b>  {format_pct(price_change, signed=True)}  (platform avg)",
        "",
        # The bubble level itself is stated in THE NUMBER; repeating it here only
        # gave the reader the same figure twice.
        f"<b>Direction toward</b>  {gap_direction}",
        f"<b>Gap Δ</b>  {format_pp(gap_delta, signed=True)}",
        "",
        f"<b>Bubble candle</b>  {classify_candle(momentum)}",
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

    high_name = structure["high_name"]
    high_price = structure["high_price"]
    day_high_price = baselines.day.platform_prices.get(high_name) if baselines.day else None
    high_day_pct = _pct_change(high_price, day_high_price)
    lines.append(f"<b>Highest</b>  {high_name}")
    lines.append(f"               {format_m_tomans(high_price)}")
    if high_day_pct is not None:
        lines.append(f"               {format_pct(high_day_pct, signed=True)} vs Day")
    lines.append("")

    low_name = structure["low_name"]
    low_price = structure["low_price"]
    day_low_price = baselines.day.platform_prices.get(low_name) if baselines.day else None
    low_day_pct = _pct_change(low_price, day_low_price)
    lines.append(f"<b>Lowest</b>  {low_name}")
    lines.append(f"               {format_m_tomans(low_price)}")
    if low_day_pct is not None:
        lines.append(f"               {format_pct(low_day_pct, signed=True)} vs Day")
    lines.append("")

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

        if run_price is not None:
            run_diff = price - run_price
            threshold = abs(run_price) * 0.0001
            if abs(run_diff) < threshold:
                run_delta = "—"
            else:
                run_delta = f"{run_diff / 10 / 1_000_000:+.2f}M"
        else:
            run_delta = "—"

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
    world_from_fallback: bool = False,
    position=None,
    trend=None,
):
    if baselines is None:
        raise RuntimeError("UPDATE v1 requires resolved baselines")
    body = "\n\n".join([
        _build_verdict(signal_state, position),
        _build_the_number(premium, lowest, fair, signal_state, position, trend),
        _build_market(world, usd, fair, platform_avg, lowest, highest, spread, premium, baselines,
                      world_from_fallback=world_from_fallback),
        _build_dynamics(platform_avg, premium, baselines, momentum),
        _build_structure(markets, fair, baselines),
        _build_platforms(markets, baselines),
        _build_decision(signal_state),
    ])
    _send(body)
