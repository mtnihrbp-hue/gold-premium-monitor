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

# Telegram renders <pre> blocks in a monospace font that fits roughly 32 characters
# on a phone. The previous 48-character table either wrapped, destroying the column
# alignment entirely, or forced horizontal scrolling. Everything here is sized to
# stay inside that budget.
MARKET_TABLE_WIDTH = 33


def _delta_bare(value):
    """Signed change with no unit suffix.

    At phone width a six-character column cannot hold "+0.04%" and still leave a
    space between columns, and numbers that touch each other are unreadable. The
    units are stated once in the footnote instead of on every cell.
    """
    return "—" if value is None else f"{value:+.2f}"


def _market_row(metric, now_text, run_text, day_text, seven_day_text):
    """Fixed-width row, 33 characters. Cell content must stay short or the columns
    shear apart, which is what made this table unreadable before."""
    return f"{metric:<8}{now_text:>7}{run_text:>6}{day_text:>6}{seven_day_text:>6}"


def _build_market(world, usd, fair, platform_avg, lowest, highest, spread, premium, baselines,
                  world_from_fallback=False, markets=None):
    run = baselines.run
    day = baselines.day
    seven = baselines.seven_day
    lines = [_update_sep(), "<b>MARKET</b>", _update_sep()]

    rows = [
        _market_row("", "Now", "Run", "Day", "7D"),
        "─" * MARKET_TABLE_WIDTH,
    ]

    rows.append(_market_row(
        "XAU/USD",
        f"${_money(world)}" if world is not None else "N/A",
        _delta_bare(_pct_change(world, run.xau_usd if run else None)),
        _delta_bare(_pct_change(world, day.xau_usd if day else None)),
        _delta_bare(_pct_change(world, seven.xau_usd)),
    ))
    rows.append(_market_row(
        "USD/IRR",
        _money(usd) if usd is not None else "N/A",
        _delta_bare(_pct_change(usd, run.usd_irr if run else None)),
        _delta_bare(_pct_change(usd, day.usd_irr if day else None)),
        _delta_bare(_pct_change(usd, seven.usd_irr)),
    ))
    rows.append(_market_row(
        "Fair",
        format_m_tomans_short(fair),
        _delta_bare(_pct_change(fair, run.fair_price if run else None)),
        _delta_bare(_pct_change(fair, day.fair_price if day else None)),
        _delta_bare(_pct_change(fair, seven.fair_price)),
    ))
    rows.append(_market_row(
        "Platform",
        format_m_tomans_short(platform_avg),
        _delta_bare(_pct_change(platform_avg, run.platform_average if run else None)),
        _delta_bare(_pct_change(platform_avg, day.platform_average if day else None)),
        _delta_bare(_pct_change(platform_avg, seven.platform_average)),
    ))
    rows.append(_market_row(
        "Bubble",
        f"{_number(premium)}%",
        _delta_bare((premium - run.premium_percent) if run and run.premium_percent is not None else None),
        _delta_bare((premium - day.premium_percent) if day and day.premium_percent is not None else None),
        _delta_bare((premium - seven.premium_percent) if seven.premium_percent is not None else None),
    ))

    lines.append("<pre>" + "\n".join(rows) + "</pre>")
    structure = format_market_structure(markets, fair) if markets else None
    if structure:
        lines.append(f"<b>Lowest</b>   {structure['low_name']}  {format_m_tomans(lowest)}")
        lines.append(f"<b>Highest</b>  {structure['high_name']}  {format_m_tomans(highest)}")
    else:
        lines.append(f"<b>Lowest</b>   {format_m_tomans(lowest)}")
        lines.append(f"<b>Highest</b>  {format_m_tomans(highest)}")
    lines.append(f"<b>Spread</b>   {format_m_tomans(spread)}")
    lines.append("")
    # Day is point-to-point; the 7D column compares against a mean. Saying so stops
    # the two being read as the same kind of measure.
    lines.append("<i>Run compares against the last scheduled reading,</i>")
    lines.append("<i>Day against the first scheduled reading today.</i>")
    lines.append("<i>7D compares against the mean of 7 completed days.</i>")
    lines.append("<i>Changes are %, except Bubble which is percentage points.</i>")
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

    # Graduated wording. Three bands drive the logic, but describing anything from
    # the 40th to the 80th percentile as "middle" overstates the case: a reading at
    # 76 of 100 is plainly toward the expensive end and should not read as neutral.
    line = None
    percentile = getattr(position, "percentile", None) if position else None
    if percentile is not None:
        if percentile < 20:
            line = "Cheap against its own recent range."
        elif percentile < 40:
            line = "Below its own recent average."
        elif percentile < 60:
            line = "Middle of its own recent range. No edge here."
        elif percentile < 80:
            line = "Toward the expensive end of its own range."
        else:
            line = "Expensive against its own recent range."

    parts = ["<b>GOLDPremium: UPDATE</b>", "", f"<b>{final}</b>"]
    if line:
        parts.append(line)

    # The candidate is surfaced only when it disagrees with the final decision. That
    # disagreement is the whole point of the hysteresis rule and must stay visible,
    # but printing both on every message when they almost always agree is noise.
    candidate = getattr(signal_state, "candidate_decision", None)
    if candidate and candidate != final:
        parts.append(f"<i>Candidate was {candidate}, held by the confirmation rule.</i>")

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
        reading = {
            "DISCOUNT_SHRINKING": "discount shrinking",
            "DISCOUNT_DEEPENING": "discount deepening",
            "DISCOUNT_FLAT": "discount steady",
        }.get(trend.reading, "")
        lines.append(f"<b>7D vs 15D</b>       {trend.cross.lower()}   {reading}".rstrip())

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

# ---------------------------------------------------------------------------
# PLATFORMS section — narrow table, M Tomans
# ---------------------------------------------------------------------------

def _build_platforms(markets, baselines, fair=None):
    lines = [_update_sep(), "<b>PLATFORMS</b>", _update_sep(), ""]
    rows = [
        f"{'Platform':<9}{'Price':>8}{'Run Δ':>8}{'vs Day':>8}",
        "─" * MARKET_TABLE_WIDTH,
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
        rows.append(f"{name:<9}{price_str:>8}{run_delta:>8}{day_text:>8}")

    lines.append("<pre>" + "\n".join(rows) + "</pre>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CURRENT DECISION section
# ---------------------------------------------------------------------------

def _build_timestamp():
    """Footer.

    The decision block that stood here repeated valuation, momentum, structure and
    the final decision, all of which the message now states before any detail. The
    candidate is surfaced next to the verdict when it disagrees with the final call,
    which is the only time that distinction carries information.
    """
    return f"<b>{format_timestamp()}</b>"


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
                      world_from_fallback=world_from_fallback, markets=markets),
        _build_dynamics(platform_avg, premium, baselines, momentum),
        _build_platforms(markets, baselines, fair=fair),
        _build_timestamp(),
    ])
    _send(body)
