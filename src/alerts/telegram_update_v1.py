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

from alerts.telegram import _money, _send
from alerts.helpers import (
    format_clock,
    format_pct,
    format_market_structure,
    format_timestamp,
    format_m_tomans,
    format_m_tomans_short,
)
from analysis.bubble_position import cheap_basis_price, signed_gap
from update.baseline_resolver import UpdateBaselines


def _update_sep():
    return "━━━━━━━━━━━━━━━━━━━━"


def _pct_change(current, baseline):
    if current is None or baseline in (None, 0):
        return None
    return (current - baseline) / baseline * 100


# Label column for the non-table sections. Telegram renders these in a
# proportional font, so the padding aligns approximately rather than exactly;
# it is wide enough that the values still form a readable column.
LABEL_WIDTH = 17


def _row(label, value):
    """Bold label padded to a fixed column.

    The padding sits outside the tag because Telegram collapses whitespace held
    inside one.
    """
    return f"<b>{label}</b>{' ' * max(1, LABEL_WIDTH - len(label))}{value}"


def _cont(value):
    """Continuation of the row above, aligned under its value."""
    return f"{' ' * LABEL_WIDTH}{value}"


def _gap_naming(premium):
    """Discount and premium are one measure with opposite signs.

    Every line describing the gap has to flip with that sign, so the naming is
    resolved once here rather than being decided again at each call site.
    """
    if premium is None:
        return "Gap", "from"
    return ("Discount", "below") if premium < 0 else ("Premium", "above")


def _gap_delta(premium, reference):
    """Change in the size of the gap, in percentage points.

    Percentage points, not percent: the premium is already a percentage and in
    this market always negative, so a percent change of it inverts the sign.
    """
    if premium is None or reference is None:
        return None
    return abs(premium) - abs(reference)


def _gap_movement(premium, reference, with_consequence=True):
    """The move as a verb, a size, and what it means for a buyer.

    The consequence is taken from the signed premium rather than from the size of
    the gap. Moving toward a larger premium is always more expensive and toward a
    larger discount always cheaper, including across the zero line, where the two
    magnitudes can be equal while the market has actually moved a full point.
    """
    if premium is None or reference is None:
        return None

    signed_delta = premium - reference
    if signed_delta > 0:
        consequence = "more expensive"
    elif signed_delta < 0:
        consequence = "cheaper"
    else:
        consequence = None

    # A sign change means the market crossed fair value. Reporting that as an
    # increase or decrease in the gap would describe the smaller half of the move.
    if (premium < 0) != (reference < 0):
        if with_consequence and consequence:
            return f"crossed fair value — {consequence}"
        return "crossed fair value"

    change = _gap_delta(premium, reference)
    # Below half of the last displayed decimal the text would claim a movement
    # the reader cannot see in the number above it.
    if consequence is None or abs(change) < 0.005:
        return "unchanged"

    verb = "increased" if change > 0 else "decreased"
    if with_consequence:
        return f"{verb} {abs(change):.2f} pp — {consequence}"
    return f"{verb} {abs(change):.2f} pp"


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
                  world_from_fallback=False, markets=None, valuation=None):
    run = baselines.run
    day = baselines.day
    seven = baselines.seven_day
    lines = [_update_sep(), "<b>MARKET</b>", _update_sep()]

    # "Today" rather than "Day", matching the vs Today row in THE NUMBER. The two
    # sections described the same reference with two different words and then spent
    # a footnote each explaining them separately.
    rows = [
        _market_row("", "Now", "Run", "Today", "7D"),
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
    # The price the valuation rests on, so the table and the block above it are
    # built from the same number rather than pairing a trimmed reading against an
    # untrimmed row.
    basis_now = valuation.basis_price if valuation is not None else None
    basis_count = valuation.basis_count if valuation is not None else 0
    if basis_now is not None:
        rows.append(_market_row(
            f"Cheap {basis_count}",
            format_m_tomans_short(basis_now),
            _delta_bare(_pct_change(basis_now, _baseline_basis(run))),
            _delta_bare(_pct_change(basis_now, _baseline_basis(day))),
            _delta_bare(_pct_change(basis_now, seven.cheap_basis)),
        ))
    else:
        rows.append(_market_row(
            "Platform",
            format_m_tomans_short(platform_avg),
            _delta_bare(_pct_change(platform_avg, run.platform_average if run else None)),
            _delta_bare(_pct_change(platform_avg, day.platform_average if day else None)),
            _delta_bare(_pct_change(platform_avg, seven.platform_average)),
        ))

    # Same naming and same direction as THE NUMBER. The row previously carried the
    # signed premium, so the identical market movement appeared here with the
    # opposite sign to the block above it.
    gap = valuation.gap if valuation is not None and valuation.gap is not None else premium
    gap_label, _ = _gap_naming(gap)
    rows.append(_market_row(
        gap_label,
        f"{abs(gap):.2f}%" if gap is not None else "N/A",
        _delta_bare(_gap_delta(gap, _baseline_gap(run))),
        _delta_bare(_gap_delta(gap, _baseline_gap(day))),
        _delta_bare(_gap_delta(gap, seven.cheap_basis_gap)),
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
    # One footnote for the whole message. THE NUMBER used to carry its own pair of
    # lines naming the same two references, so the reader was told twice.
    # Day is point-to-point; the 7D column compares against a mean, and saying so
    # stops the two being read as the same kind of measure.
    run_clock = format_clock(run.timestamp) if run and run.timestamp else None
    day_clock = format_clock(day.timestamp) if day and day.timestamp else None
    if run_clock and day_clock:
        lines.append(f"<i>Run = {run_clock} (last scheduled), "
                     f"Today = {day_clock} (first today).</i>")
    else:
        lines.append("<i>Run = the last scheduled reading, "
                     "Today = the first one today.</i>")
    lines.append("<i>7D = mean of 7 completed days, each weighted equally.</i>")
    lines.append(f"<i>Changes are %, except {gap_label} which is percentage points.</i>")
    # Which direction is good for a buyer flips with the sign, so the sentence has
    # to flip with it too rather than being written for the discount case alone.
    if premium is not None and premium < 0:
        lines.append("<i>A bigger discount is cheaper.</i>")
    elif premium is not None:
        lines.append("<i>A bigger premium is more expensive.</i>")
    if world_from_fallback:
        # Fail-safe rule: a fallback value must carry degraded provenance to the reader,
        # otherwise a cached price is indistinguishable from a fresh quote.
        lines.append("")
        lines.append("⚠ XAU/USD is a cached fallback, not a fresh quote.")
        lines.append(f"Fair value and {gap_label} derive from it.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PRICE & BUBBLE DYNAMICS section
# ---------------------------------------------------------------------------

def _build_verdict(signal_state, position):
    """Header and where this reading sits in its own recent range.

    The BUY/WAIT/SELL verdict was removed from here by product decision. UPDATE is
    a view of the market, not a recommendation, and a bare verdict carried none of
    the reasoning behind it: the valuation, momentum, structure and conflict chain
    that produces the decision is not in this message, so the word on its own asked
    to be trusted rather than understood. It belongs in ANALYZE, where the chain
    can be shown alongside it.

    The position line stays. It describes where the reading sits, which is a
    measurement rather than an instruction, and CHEAP is not BUY.
    """
    if signal_state is None:
        return "<b>GOLDPremium: UPDATE</b>"

    # The band sentence was removed too. "Below its own recent average" restated
    # what "Bigger than 29% of the last 30 days" says one line later, in vaguer
    # terms and without the figure behind it.
    return "<b>GOLDPremium: UPDATE</b>"


def _build_the_number(premium, lowest, fair, platform_avg, markets, signal_state,
                      position, magnitude, baselines, valuation=None):
    """The figures a decision actually rests on, in one block.

    Everything here is stated in the direction the market is actually in. The gap
    is a positive size with its side named once, movement is an increase or a
    decrease of that size, and each line carries what the move means for a buyer
    so nothing has to be inferred from a sign.
    """
    label, side = _gap_naming(premium)
    run = baselines.run if baselines else None
    day = baselines.day if baselines else None
    lines = [_update_sep(), "<b>THE NUMBER</b>", _update_sep()]

    structure = format_market_structure(markets, fair) if markets else None
    low_name = structure["low_name"] if structure else None
    total_platforms = structure["platform_count"] if structure else None

    # Everything below rests on the trimmed basis, not on the single cheapest
    # platform. `premium` is still the stored, minimum-based value and is used only
    # where a valuation is unavailable.
    gap = valuation.gap if valuation is not None and valuation.gap is not None else premium
    label, side = _gap_naming(gap)
    basis_now = valuation.basis_price if valuation is not None else None
    basis_count = valuation.basis_count if valuation is not None else 0

    lines.append(_row(label, f"{abs(gap):.2f}%  {side} fair value"))
    if basis_count and total_platforms:
        lines.append(_cont(f"from the {basis_count} cheapest of {total_platforms}"))

    run_gap = _baseline_gap(run, basis_now)
    run_move = _gap_movement(gap, run_gap)
    if run_move:
        lines.append(_row(label, run_move))
        # Ranking the size of a move that did not happen reads as a contradiction.
        move = valuation.move_label if valuation is not None else None
        if move and move != "UNKNOWN" and run_move != "unchanged":
            lines.append(_cont(move))

    # The consequence is dropped here because the line above already carries it
    # for the same gap; repeating it adds length without adding information.
    day_move = _gap_movement(gap, _baseline_gap(day, basis_now), with_consequence=False)
    if day_move:
        lines.append(_row("vs Today", day_move))

    if valuation is not None and valuation.status == "OK":
        window = valuation.window_days
        # "Bigger" rather than "cheaper": the subject is the discount, and the
        # footnote already defines a bigger discount as the cheaper one. "Cheaper
        # than 29%" left the reader asking cheaper than what.
        lines.append(_row("Bigger than",
                          f"{valuation.bigger_than}% of the last {window} days"))
        if valuation.deep_at is not None:
            # A rank inside the window, not a level measured against outcomes, so it
            # is named for what it describes and claims nothing about what follows
            # from reaching it.
            if valuation.deep_at < 0:
                lines.append(_row("Deep discount",
                                  f"If {abs(valuation.deep_at):.2f}% or more  ({window}D)"))
            else:
                lines.append(_row("Cheap zone",
                                  f"If {valuation.deep_at:.2f}% or less  ({window}D)"))

    below = getattr(signal_state, "platforms_below_fair", None) if signal_state else None
    above = getattr(signal_state, "platforms_above_fair", None) if signal_state else None
    if below is not None and above is not None and (below + above) > 0:
        total = below + above
        lines.append("")
        if below == total:
            lines.append(_row("Platforms", f"all {total} below fair value"))
        elif above == total:
            lines.append(_row("Platforms", f"all {total} above fair value"))
        else:
            lines.append(_row("Platforms", f"{below} of {total} below fair value"))

    lines.append("")
    cheapest = _cheapest_platforms(markets, basis_count)
    if cheapest:
        lines.append(_row("Cheapest " + str(len(cheapest)),
                          ", ".join(name for name, _ in cheapest)))
        lines.append(_cont(" / ".join(format_m_tomans_short(p) for _, p in cheapest)))
    lines.append(_row("Market low", format_m_tomans(lowest)
                      + (f"  {low_name}" if low_name else "")))
    lines.append(_row("Fair value", _level_with_change(
        fair, _pct_change(fair, run.fair_price if run else None))))

    # Valuation is trimmed, execution is not. Showing where the platforms outside
    # the basis sit lets the reader tell one vendor moving alone from the market
    # moving, which is what a single stale quote looked like before.
    others = _outside_basis_prices(markets, [name for name, _ in cheapest])
    if others:
        lines.append("")
        lines.append(f"<i>The other {len(others)} platforms: "
                     f"{format_m_tomans_short(others[0])} - "
                     f"{format_m_tomans_short(others[-1])}.</i>")

    return "\n".join(lines)


def _baseline_basis(baseline):
    """Trimmed basis price of a baseline snapshot, rebuilt from its platform prices."""
    if baseline is None or not baseline.platform_prices:
        return None
    return cheap_basis_price(baseline.platform_prices.values())


def _baseline_gap(baseline, fallback_basis=None):
    """Signed gap of a baseline snapshot, rebuilt on the trimmed basis.

    The baseline carries every platform price it recorded, so the basis is
    recomputed rather than read from its stored premium, which was minimum-based.
    """
    if baseline is None or not baseline.fair_price:
        return None
    basis = cheap_basis_price(baseline.platform_prices.values())
    if basis is None:
        return baseline.premium_percent
    return signed_gap(basis, baseline.fair_price)


def _level_with_change(value, change):
    text = format_m_tomans(value)
    if change is not None:
        text += f"  {change:+.2f}%"
    return text


def _cheapest_platforms(markets, count):
    """The `count` cheapest platforms as (name, price), cheapest first."""
    if not markets or not count:
        return []
    valid = [
        (name, float(info["price"])) for name, info in markets.items()
        if info.get("status") == "OK" and info.get("price") is not None
    ]
    return sorted(valid, key=lambda item: item[1])[:count]


def _outside_basis_prices(markets, basis_names):
    """Sorted prices of every platform not inside the valuation basis."""
    if not markets:
        return []
    excluded = set(basis_names or ())
    return sorted(
        float(info["price"])
        for name, info in markets.items()
        if name not in excluded
        and info.get("status") == "OK" and info.get("price") is not None
    )


# PRICE & BUBBLE DYNAMICS was removed here. Every figure it carried is now stated
# once in THE NUMBER, in the same vocabulary as the rest of the message: the local
# price direction and change became the Local price line, the gap delta became the
# movement line, and the interpretation sentence became the consequence word
# attached to that movement. The section restated the same numbers in a second,
# sign-based vocabulary, which is what made the two halves of the message appear
# to disagree with each other.


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
    # Accepted and resolved, but not rendered. The 7-day and 15-day average lines
    # were parked by the product owner as message clutter, with the intention of
    # revisiting them in ANALYZE rather than UPDATE. The parameter stays so the
    # resolver keeps a caller and the decision is reversible without rewiring.
    trend=None,
    magnitude=None,
    valuation=None,
):
    if baselines is None:
        raise RuntimeError("UPDATE v1 requires resolved baselines")
    body = "\n\n".join([
        _build_verdict(signal_state, position),
        _build_the_number(premium, lowest, fair, platform_avg, markets, signal_state,
                          position, magnitude, baselines, valuation=valuation),
        _build_market(world, usd, fair, platform_avg, lowest, highest, spread, premium, baselines,
                      world_from_fallback=world_from_fallback, markets=markets,
                      valuation=valuation),
        _build_platforms(markets, baselines, fair=fair),
        _build_timestamp(),
    ])
    _send(body)
