"""PAPER (SP-D): the analyst's trade push and its 21:00 report.

DRAFT for the owner's review (2026-10-04). Labelled PAPER everywhere: the account is
hypothetical and its BUY/SELL are what it did, not a signal; the system's own BUY alert
keeps its authority. Plain words, read on a phone: grams, toman, the platform, the
reason, and the account after the trade. Dates in the Persian calendar, which is how
the quarters run. Only <b> and <i>; no bare "<", ">" or "&".
"""

from alerts.helpers import format_m_tomans_short
from alerts.telegram import _send
from timeutil import to_jalali, to_tehran

PERSIAN_MONTHS = ("Farvardin", "Ordibehesht", "Khordad", "Tir", "Mordad", "Shahrivar",
                  "Mehr", "Aban", "Azar", "Dey", "Bahman", "Esfand")


def _m(rial):
    return format_m_tomans_short(rial)


def persian_day(day, year=False):
    jy, jm, jd = to_jalali(day)
    return f"{jd} {PERSIAN_MONTHS[jm - 1]}" + (f" {jy}" if year else "")


def _signed(value):
    return f"{value:+.2f}%".replace("-", "−")


def _book(holding, cash, sell):
    return f"{holding} g gold + {_m(cash)} cash = <b>{_m(cash + holding * sell)}</b>"


def build_trade_message(action, grams, price, venue, at_utc, reason, holding, cash, sell):
    local = to_tehran(at_utc)
    verb = "Bought" if action == "BUY" else "Sold"
    return "\n".join([
        f"<b>GOLDPremium: PAPER {action}</b>",
        f"{verb} {grams} g at {_m(price)} ({venue}) · {persian_day(local.date())} {local:%H:%M}",
        f"Why: {reason}",
        f"Now: {_book(holding, cash, sell)}",
    ])


def _exit_line(sig, out):
    if not sig:
        return None
    if out:
        return (f"Analyst: out of gold; back in above the 50-day average ({_m(sig['sma50'])}) "
                f"with EMA20 above EMA50, or on a new rally")
    parts = ["Analyst: invested; sells only on a confirmed break"]
    if sig.get("rally_end"):
        parts.append(f"(below {_m(sig['rally_end'])} and the 50-day average, now {_m(sig['sma50'])})")
    return " ".join(parts)


def build_report_message(day, venue, sell, sell_note, analyst, hold, base_day, trades, sig, out):
    """`analyst`/`hold`: (holding, cash, quarter base value); `trades`: today's analyst
    trades as (action, grams, price, local HH:MM)."""
    holding, cash, base = analyst
    total = cash + holding * sell
    lines = [f"<b>GOLDPremium: PAPER</b> · {persian_day(day, year=True)}, 21:00",
             f"Gold: {holding} g = {_m(holding * sell)} ({venue} pays {_m(sell)} a gram{sell_note})",
             f"Cash: {_m(cash)}",
             f"<b>Total: {_m(total)}</b>",
             f"This quarter (since {persian_day(base_day)}): {_signed((total / base - 1) * 100)}"]
    if hold is not None:
        h_holding, h_cash, h_base = hold
        h_total = h_cash + h_holding * sell
        lines.append(f"Holding from the start instead: {_m(h_total)} ({_signed((h_total / h_base - 1) * 100)})")
    if trades:
        for action, grams, price, clock in trades:
            lines.append(f"Today: {'bought' if action == 'BUY' else 'sold'} {grams} g at {_m(price)} ({clock})")
    else:
        lines.append("Today: no trade")
    exit_line = _exit_line(sig, out)
    if exit_line:
        lines.append(exit_line)
    return "\n".join(lines)


def send_paper(text):
    _send(text)
