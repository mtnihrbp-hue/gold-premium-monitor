"""UPDATE v1 Telegram formatter — Chunk C (visual/mobile fixes).

Presentation-only module for the fast user-triggered UPDATE wing.
Consumes current values, resolved baselines, and existing analytical context.
Does not calculate market state or run the Analyze pipeline.

Visual design decisions:
- <code> tags removed from non-table sections (mobile readability)
- Vertical spacing compressed within sections
- All prices converted to Tomans (1 Toman = 10 Rials)
- Platform table uses abbreviated M-Tomans format for mobile width
- Signed deltas are shown directly (no directional arrows)
- 7D historical platform-average baseline shown alongside RUN/DAY
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


def _price_change_rate_per_hour(current, baseline, baseline_timestamp):
    """Return percentage change per elapsed hour from the RUN baseline."""
    if current is None or baseline in (None, 0) or baseline_timestamp is None:
        return None
    now = datetime.now(baseline_timestamp.tzinfo) if baseline_timestamp.tzinfo else datetime.now()
    elapsed_hours = (now - baseline_timestamp).total_seconds() / 3600.0
    if elapsed_hours <= 0:
        return None
    return _pct_change(current, baseline) / elapsed_hours


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


def _build_dynamics_interpretation(price_direction, price_change, price_rate, premium, gap_direction, gap_delta):
    """Build human-readable interpretation from measured price/gap movement."""
    price_phrase = None
    if price_direction == "RISING":
        price_phrase = "Local prices are rising"
    elif price_direction == "FALLING":
        price_phrase = "Local prices are falling"
    elif price_direction == "STABLE":
        price_phrase = "Local prices are stable"

    if price_phrase is not None and price_change is not None:
        price_phrase += f" ({price_change:+.2f}%)"
    if price_phrase is not None and price_rate is not None:
        price_phrase += f" at {price_rate:+.2f}%/h"

    gap_phrase = None
    if premium is not None:
        if premium < 0:
            if gap_direction == "MORE DISCOUNT":
                gap_phrase = "the discount is widening"
            elif gap_direction == "LESS DISCOUNT":
                gap_phrase = "the discount is narrowing"
            elif gap_direction == "STABLE":
                gap_phrase = "the discount is stable"
        elif premium > 0:
            if gap_direction == "MORE PREMIUM":
                gap_phrase = "the premium is widening"
            elif gap_direction == "LESS PREMIUM":
                gap_phrase = "the premium is narrowing"
            elif gap_direction == "STABLE":
                gap_phrase = "the premium is stable"

    if gap_phrase is not None and gap_delta is not None and abs(gap_delta) >= 0.05:
        gap_phrase += f" ({gap_delta:+.2f} pp)"

    if price_phrase and gap_phrase:
        return f"{price_phrase}, while {gap_phrase}."
    if price_phrase:
        return f"{price_phrase}."
    if gap_phrase:
        return f"{gap_phrase.capitalize()}."
    return "Insufficient data for interpretation."


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
    lines.append(f"               {format_pct(run_change, signed=True)} Run | {format_pct(day_change, signed=True)} Day")

    # USD/IRR
    run_change = _pct_change(usd, run.usd_irr if run else None)
    day_change = _pct_change(usd, day.usd_irr if day else None)
    lines.append(f"<b>USD/IRR</b>  {_money(usd)}")
    lines.append(f"               {format_pct(run_change, signed=True)} Run | {format_pct(day_change, signed=True)} Day")

    # Fair Price
    run_change = _pct_change(fair, run.fair_price if run else None)
    day_change = _pct_change(fair, day.fair_price if day else None)
    lines.append(f"<b>Fair Price</b>  {format_m_tomans(fair)}")
    lines.append(f"               {format_pct(run_change, signed=True)} Run | {format_pct(day_change, signed=True)} Day")

    # Platform Average
    run_change = _pct_change(platform_avg, run.platform_average if run else None)
    day_change = _pct_change(platform_avg, day.platform_average if day else None)
    seven_day_change = _pct_change(platform_avg, baselines.seven_day_platform_average)
    lines.append(f"<b>Platform Avg</b>  {format_m_tomans(platform_avg)}")
    lines.append(f"               {format_pct(run_change, signed=True)} Run | {format_pct(day_change, signed=True)} Day")
    if baselines.seven_day_platform_average is not None:
        lines.append(f"<b>7D Avg</b>  {format_m_tomans(baselines.seven_day_platform_average)}")
        lines.append(f"               {format_pct(seven_day_change, signed=True)} vs 7D Avg")
    else:
        lines.append("<b>7D Avg</b>  N/A")

    # Bubble
    run_pp = (premium - run.premium_percent) if run and run.premium_percent is not None else None
    day_pp = (premium - day.premium_percent) if day and day.premium_percent is not None else None
    lines.append(f"<b>Bubble</b>  {_number(premium)}%  {bubble_state_short(premium)}")
    lines.append(f"               {format_pp(run_pp, signed=True)} Run | {format_pp(day_pp, signed=True)} Day")

    # Lowest / Highest / Spread
    lines.append(f"<b>Lowest</b>  {format_m_tomans(lowest)}")
    lines.append(f"<b>Highest</b>  {format_m_tomans(highest)}")
    lines.append(f"<b>Spread</b>  {format_m_tomans(spread)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PRICE & BUBBLE DYNAMICS section
# ---------------------------------------------------------------------------

def _build_dynamics(platform_avg, premium, baselines, momentum):
    run = baselines.run
    price_change = _pct_change(platform_avg, run.platform_average if run else None)
    price_rate = _price_change_rate_per_hour(
        platform_avg,
        run.platform_average if run else None,
        run.timestamp if run else None,
    )
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
        price_rate,
        premium,
        gap_direction,
        gap_delta,
    )
    return "\n".join([
        _update_sep(),
        "<b>PRICE & BUBBLE DYNAMICS</b>",
        _update_sep(),
        f"<b>Price</b>  {baselines.price_direction}",
        f"<b>Change</b>  {format_pct(price_change, signed=True)}",
        f"<b>Speed</b>  {format_pct(price_rate, signed=True)}/h" if price_rate is not None else "<b>Speed</b>  N/A",
        "",
        f"<b>Bubble</b>  {bubble_state}",
        f"               {_number(premium)}%",
        f"<b>Direction toward</b>  {gap_direction}",
        f"<b>Gap Δ</b>  {format_pp(gap_delta, signed=True)}",
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
                run_delta = f"{run_diff / 10 / 1_000_000:+.2f}M"
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
        _build_dynamics(platform_avg, premium, baselines, momentum),
        _build_structure(markets, fair, baselines),
        _build_platforms(markets, baselines),
        _build_decision(signal_state),
    ])
    _send(body)
