"""ANALYZE and the deep-discount push.

Both surfaces share UPDATE's vocabulary deliberately. A discount increases or
decreases -- never widens, grows or deepens. A move is a move. The same quantity
named two ways reads as two quantities to someone who did not write it, and this
message is read beside UPDATE.

ANALYZE reports what the record shows. It carries no BUY, SELL or WAIT, no
recommendation, and no forecast: every figure is a count or a rank over readings that
have already happened.
"""

from typing import Optional

from alerts.telegram import _send
from alerts.helpers import format_m_tomans_short, format_timestamp, to_tehran

LABEL_WIDTH = 20


def _sep():
    return "━━━━━━━━━━━━━━━━━━━━"


def _row(label, value):
    """Bold label padded to a fixed column; padding sits outside the tag because
    Telegram collapses whitespace held inside one."""
    return f"<b>{label}</b>{' ' * max(1, LABEL_WIDTH - len(label))}{value}"


def _cont(value):
    return f"{' ' * LABEL_WIDTH}{value}"


def _pp(value):
    return "—" if value is None else f"{abs(value):.2f} pp"


def _pct(value):
    return "—" if value is None else f"{abs(value):.2f}%"


def _times(count):
    return f"{count} time" if count == 1 else f"{count} times"


def _counted(count, average):
    """A count, and its average only when there is something to average."""
    if not count or average is None:
        return _times(count)
    return f"{_times(count)} — average {_pp(average)}"


def _hours(value):
    """Duration in the reader's units, singular when it is one.

    `1 hours` shipped for a day after the episode measurement was corrected, because
    the format string never considered that the number could round to one.
    """
    if value is None:
        return "—"
    if value < 1:
        minutes = int(round(value * 60))
        return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"
    hours = round(value)
    return f"{hours} hour" if hours == 1 else f"{hours} hours"


# ---------------------------------------------------------------------------
# ANALYZE
# ---------------------------------------------------------------------------

def _build_level(level):
    """What the discount did after past readings at this level.

    The heading names the level, not the day. "Readings like today" was misread as
    "today's reading" by the product owner on first sight, which is the heading's
    fault: today supplies only the level, and nothing about today as a period is
    involved. The band is printed so "this level" is a number rather than a claim.
    """
    lines = [_sep(), "<b>WHEN THE DISCOUNT WAS AT THIS LEVEL</b>", _sep()]
    if level.status == "TOO_FEW":
        # The window is fine; it is this *level* the record has nothing near. Saying
        # "not enough history" would blame the wrong thing, and printing the two or
        # three readings it did find would lend them the authority of a hundred.
        lines.append(_row("Today's discount", _pct(level.gap)))
        lines.append(_row("Similar past",
                          "none at this level" if not level.cases
                          else f"{level.cases} readings — too few to report"))
        lines.append("")
        lines.append("<i>The last 30 days hold almost no readings at this level,</i>")
        lines.append("<i>so there is nothing to count.</i>")
        return "\n".join(lines)
    if level.status != "OK":
        lines.append(_row("Not enough history", "yet"))
        return "\n".join(lines)

    lines.append(_row("Today's discount", _pct(level.gap)))
    if level.band_low is not None and level.band_high is not None:
        lines.append(_row("Similar past", f"{level.cases} readings between "
                                          f"{_pct(level.band_high)} and {_pct(level.band_low)}"))
    else:
        lines.append(_row("Similar past", f"{level.cases} readings"))

    lines.append("")
    lines.append("<i>In the 24 hours after:</i>")
    # "0 times — average —" is two pieces of punctuation standing in for nothing.
    lines.append(_row("Discount increased", _counted(
        level.increased, level.average_increase_pp)))
    lines.append(_row("Discount decreased", _counted(
        level.decreased, level.average_decrease_pp)))
    lines.append(_row("Unchanged", _times(level.unchanged)))

    if level.average_change_pp is not None:
        # Direction stated in the same two words the counts above use.
        verb = "increased" if level.average_change_pp > 0 else "decreased"
        lines.append("")
        lines.append(_row("Average change", f"{verb} {_pp(level.average_change_pp)}"))

    lines.append("")
    lines.append("<i>This is the historical record, not a forecast.</i>")
    return "\n".join(lines)


def _build_distribution(distribution, deep_zone):
    lines = [_sep(), "<b>THE LAST 30 DAYS</b>", _sep()]
    if distribution.status != "OK":
        lines.append(_row("Not enough history", "yet"))
        return "\n".join(lines)

    lines.append(_row("Discount range", f"{_pct(distribution.low)} to {_pct(distribution.high)}"))
    lines.append(_row("Typical", _pct(distribution.typical)))
    if distribution.today is not None and distribution.typical is not None:
        side = "below" if distribution.today < distribution.typical else "above"
        lines.append(_row("Today", f"{_pct(distribution.today)} — {side} typical"))

    if deep_zone.status == "OK":
        lines.append("")
        lines.append(_row("Deep discount", f"{_pct(deep_zone.threshold)} or more"))
        lines.append(_row("Appeared", _times(deep_zone.episodes)))
        if deep_zone.typical_hours is None and deep_zone.longest_hours:
            # Kaplan-Meier never reached half, so there is no median. The largest
            # duration observed is not a substitute for one, and saying so is the
            # only honest thing available.
            lines.append(_row("Typical duration", "not reached"))
            lines.append(_cont(f"over half were still open at "
                               f"{_hours(deep_zone.longest_hours)}"))
        else:
            lines.append(_row("Typical duration", _hours(deep_zone.typical_hours)))
        lines.append(_row("Longest spell", _hours(deep_zone.longest_hours)))
        lines.append(_row("Right now", "inside it" if deep_zone.inside_now else "outside it"))
    return "\n".join(lines)


def _build_movement(movement):
    lines = [_sep(), "<b>PRICE MOVEMENT</b>", _sep()]
    if movement.status != "OK":
        lines.append(_row("Not enough history", "yet"))
        return "\n".join(lines)

    lines.append(_row("Typical hourly move", _pct(movement.typical_move_percent)))
    lines.append(_row("Sharp move", f"{_pct(movement.sharp_move_percent)} or more"))
    lines.append(_row("Occurred", f"{_times(movement.sharp_count)} in 30 days"))
    if movement.last_sharp_at is not None:
        local = to_tehran(movement.last_sharp_at)
        lines.append(_row("Last occurrence",
                          f"{local:%m-%d %H:%M}   {movement.last_sharp_percent:+.2f}%"))
    return "\n".join(lines)


def _build_health(health):
    """Sample and sampling.

    The decision record is deliberately absent until it has a sample. Three decisions
    is an anecdote, and a track record printed from one invites exactly the confidence
    `skills/market-analyst.md` forbids manufacturing. The section appears on its own
    once the engine has decided enough times to be scored.
    """
    lines = [_sep(), "<b>DATA</b>", _sep()]
    lines.append(_row("Readings", f"{health.readings} over {health.coverage_days} days"))
    sampling = "mixed" if health.sampling == "MIXED" else "scheduled only"
    if health.sampling == "MIXED" and health.clean_from:
        sampling += f" — clean from {health.clean_from}"
    lines.append(_row("Sampling", sampling))
    lines.append(_row("Outcomes resolved",
                      f"{health.outcomes_resolved} of {health.outcomes_total}"))
    return "\n".join(lines)


def build_analyze_message(report) -> str:
    """Assemble ANALYZE. Returns the body so it can be rendered without sending."""
    blocks = ["<b>GOLDPremium: ANALYZE</b>"]
    if report.status != "OK":
        blocks.append("Not enough history yet to report against.")
        blocks.append(f"<b>{format_timestamp()}</b>")
        return "\n\n".join(blocks)

    blocks.append(_build_level(report.level))
    blocks.append(_build_distribution(report.distribution, report.deep_zone))
    blocks.append(_build_movement(report.movement))
    blocks.append(_build_health(report.health))
    blocks.append(f"<b>{format_timestamp()}</b>")
    return "\n\n".join(blocks)


def send_analyze(report):
    _send(build_analyze_message(report))


# ---------------------------------------------------------------------------
# Deep-discount push
# ---------------------------------------------------------------------------

def build_push_message(decision, deep_zone, lowest=None, low_name=None,
                       basis_count=None, platform_count=None) -> str:
    """The interrupt.

    Short because it is unsolicited. It states the measurement, says how long the
    zone usually stays open, and points at ANALYZE rather than repeating it.

    It contains no BUY, SELL or WAIT. `skills/telegram-product.md` reserves external
    BUY/SELL alerts to the deterministic final_decision, and a push that reads as a
    recommendation would take that authority without holding it.
    """
    lines = ["<b>GOLDPremium: DEEP DISCOUNT</b>", ""]
    lines.append(_row("Discount", f"{_pct(decision.gap)}  below fair value"))
    if basis_count and platform_count:
        lines.append(_cont(f"from the {basis_count} cheapest of {platform_count}"))
    lines.append(_row("Deep discount", f"{_pct(decision.fire_at)} or more  (30D)"))

    if lowest is not None:
        suffix = f"  {low_name}" if low_name else ""
        lines.append("")
        lines.append(_row("Market low", f"{format_m_tomans_short(lowest)} Tomans{suffix}"))
    if deep_zone is not None and deep_zone.typical_hours is not None:
        lines.append(_row("Typical duration", _hours(deep_zone.typical_hours)))

    lines.append("")
    lines.append("<i>Send Analyze for the record.</i>")
    lines.append(f"<b>{format_timestamp()}</b>")
    return "\n".join(lines)


def send_push(decision, deep_zone, **kwargs):
    _send(build_push_message(decision, deep_zone, **kwargs))
