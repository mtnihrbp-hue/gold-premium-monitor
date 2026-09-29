"""The BUY signal message.

Sent only when `final_decision` is BUY, which since SP_C_HANDOFF.md section 38 means
the SP-A chain produced a BUY candidate, the candidate passed the confirmation checks,
and hysteresis let it through.

It replaces the SP-A alert layout for BUY. That layout printed the single-cheapest
`Premium`, which contradicted UPDATE's three-cheapest basis on the same reading, and it
printed internal labels (`DISCOUNT WIDENING`, `SUPPORTIVE`) that
`skills/market-analyst.md` keeps out of user-facing text.

Everything here reuses UPDATE's helpers and the values the caller already resolved,
so the same words carry the same numbers on every surface. A CHEAP valuation is shown
as "heavily discounted", by product decision on 2026-09-29: a large discount is not a
cheap market, and CHEAP is not BUY.
"""

from datetime import datetime, timedelta

from alerts.helpers import (
    format_clock,
    format_market_structure,
    format_m_tomans,
    format_m_tomans_short,
    format_timestamp,
)
from alerts.telegram import _send
from alerts.telegram_update_v1 import (
    _baseline_gap,
    _cheapest_platforms,
    _cont,
    _gap_movement,
    _gap_naming,
    _row,
    _update_sep,
)
from timeutil import local_date

MOMENTUM_WORDS = {
    "IMPROVING": "the discount is increasing",
    "WEAKENING": "the discount is decreasing",
    "NEUTRAL": "the discount is steady",
}


def _since(run_timestamp, now):
    """How much time the move line covers."""
    minutes = (now - run_timestamp).total_seconds() / 60
    if 45 <= minutes <= 75:
        return "in the last hour"
    return f"since {format_clock(run_timestamp)}"


def _repeat_not_before(now, cooldown_hours):
    """When the hysteresis cooldown lets the next BUY through, in the reader's clock."""
    next_at = now + timedelta(hours=cooldown_hours)
    clock = format_clock(next_at)
    days = (local_date(next_at) - local_date(now)).days
    if days == 0:
        return clock
    if days == 1:
        return f"{clock} tomorrow"
    return f"{local_date(next_at).isoformat()} {clock}"


def build_buy_signal_message(*, fair, markets, signal_state, confirmation, valuation,
                             baselines, now=None, cooldown_hours=24):
    """The BUY signal as Telegram HTML. Presentation only: it computes no market fact."""
    if now is None:
        now = datetime.utcnow()

    structure = format_market_structure(markets, fair) if markets else None
    total_platforms = structure["platform_count"] if structure else None
    gap = (valuation.gap if valuation is not None and valuation.gap is not None
           else signal_state.premium)
    basis_count = valuation.basis_count if valuation is not None else 0
    label, side = _gap_naming(gap)

    lines = [
        "<b>GOLDPremium: BUY SIGNAL</b>",
        "",
        "The discount is unusually large, and a second platform confirms it.",
        "",
        _update_sep(), "<b>THE NUMBER</b>", _update_sep(),
        _row(label, f"{abs(gap):.2f}%  {side} fair value"),
    ]
    if basis_count and total_platforms:
        lines.append(_cont(f"from the {basis_count} cheapest of {total_platforms}"))
    if valuation is not None and valuation.status == "OK":
        window = valuation.window_days
        lines.append(_row("Bigger than", f"{valuation.bigger_than}% of the last {window} days"))
        if valuation.deep_at is not None and gap is not None and gap < 0:
            lines.append(_row("Deep discount", f"If {valuation.deep_at:.2f}% or more  ({window}D)"))
    run = baselines.run if baselines else None
    basis_now = valuation.basis_price if valuation is not None else None
    run_move = _gap_movement(gap, _baseline_gap(run, basis_now))
    if run_move and run is not None and run.timestamp is not None:
        lines.append(_row(label, run_move))
        lines.append(_cont(_since(run.timestamp, now)))

    lines += ["", _update_sep(), "<b>WHY BUY</b>", _update_sep(),
              _row("Valuation", "Heavily discounted for its own record")]
    momentum = MOMENTUM_WORDS.get(getattr(signal_state, "momentum", None))
    if momentum:
        lines.append(_row("Momentum", momentum))
    below = getattr(signal_state, "platforms_below_fair", None)
    above = getattr(signal_state, "platforms_above_fair", None)
    if below is not None and above is not None and (below + above) > 0:
        total = below + above
        if below == total:
            lines.append(_row("Platforms", f"all {total} below fair value"))
        else:
            lines.append(_row("Platforms", f"{below} of {total} below fair value"))

    if confirmation is not None:
        lines += ["", _update_sep(), "<b>CHECKED</b>", _update_sep()]
        if confirmation.second_platform:
            lines.append(_row("Second platform", f"confirms ({confirmation.second_platform})"))
        updated = (f" (updated {format_clock(confirmation.dollar_updated_at)})"
                   if confirmation.dollar_updated_at is not None else "")
        lines.append(_row("Dollar rate", f"live{updated}"))
        lines.append(_row("World gold", "live"))

    cheapest = _cheapest_platforms(markets, basis_count or 3)
    lines.append("")
    if cheapest:
        lines.append(_row(f"Cheapest {len(cheapest)}", ", ".join(name for name, _ in cheapest)))
        lines.append(_cont(" / ".join(format_m_tomans_short(price) for _, price in cheapest)))
    lines.append(_row("Fair value", format_m_tomans(fair)))

    lines += [
        "",
        "History at this level: /Analyze",
        "<i>Decision support, not an instruction to trade.</i>",
        f"<i>No repeat BUY signal before {_repeat_not_before(now, cooldown_hours)}.</i>",
        f"<b>{format_timestamp()}</b>",
    ]
    return "\n".join(lines)


def send_buy_signal(text):
    _send(text)
