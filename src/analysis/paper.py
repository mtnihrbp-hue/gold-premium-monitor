"""PAPER: the analyst trades a hypothetical 100,000,000 toman in whole grams of 18K.

The owner's scenario and contract (2026-10-04, SP_D_HANDOFF.md section 9):

1. Capital: 100,000,000 toman in cash on the start day.
2. Venue: one platform, buying at its buy price and selling at its sell price, both from
   the same reading. Goldika for now: the only platform the runner reaches that publishes
   both sides, with a source time stamp. Daric (an order book, 0.26% apart against
   Goldika's 2.37%) joins at a quarter boundary once an Iranian route reaches it.
3. Units: whole grams, at least 1 g a trade; the residue stays as cash.
4. At most one trade per Tehran day, at any scheduled run (06:00-21:00).
5. No borrowing and no short selling.
6. No trade without a fresh venue price: a quote validation discarded or deferred, or one
   without both sides, makes that run a HOLD.
7. A report at 21:00: gold, cash, total, and the profit or loss against the quarter's
   first day. Quarters are Persian seasons (1 Farvardin, Tir, Mehr, Dey).
8. A push on every trade, labelled PAPER: the system's own BUY/SELL alert keeps its
   authority, this is a hypothetical account reporting what it did.
9. Every run's evaluation is logged with its inputs, including the runs where the signals
   conflict (UNDECIDED), which is what the quarterly review learns from.
10. Rules change only at a quarter boundary, under a new version name.

ANALYST v0 (research/rd_paper_v0.py). Invested by default; out only on a confirmed break
-- the 8% rally broken AND the close below its 50-day average -- and back in when the
close is above the 50-day with EMA20 above EMA50, or a new rally starts. Of the rules
tested it came closest to holding (2024-2026 at Daric's cost: x9.76 against x10.01) and
gave back less of the 2026-01-29 -> 06-16 drop (-18.5% against -24.1%). No tested rule
beat holding; v0 is the baseline the R&D has to beat, not a claim of an edge. Signals
use completed tgju candles only, so an intraday dip never triggers a sale.

Two shadow accounts run beside it under the same contract, for the quarterly review:
buy-and-hold (buys at the first run, never sells) and the system's own final BUY/SELL.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

START_CASH_IRR = 1_000_000_000            # 100,000,000 toman
VENUE = "Goldika"
BAND = 0.2                                # trade only when the gold share is this far off target
REPORT_HOUR = 21                          # the first run from 21:00 Tehran reports the day
ANALYST, HOLD, SYSTEM = "analyst", "buy_and_hold", "system"
ACCOUNTS = (                              # (name, policy version, pushes to Telegram)
    (ANALYST, "analyst-v0", True),
    (HOLD, "buy-and-hold", False),
    (SYSTEM, "follow-final-decision", False),
)


@dataclass
class Book:
    cash: float                           # rial
    grams: int

    def value(self, sell):
        return self.cash + self.grams * sell

    def share(self, sell):
        value = self.value(sell)
        return self.grams * sell / value if value > 0 else 0.0


@dataclass
class Decision:
    action: str                           # BUY, SELL, HOLD, UNDECIDED
    grams: int
    price: Optional[float]
    reason: str


def venue_quote(markets, venue=VENUE):
    """(buy, sell) of the venue if it passed validation with both sides, else None."""
    info = (markets or {}).get(venue)
    if not info or info.get("status") != "OK":
        return None
    buy, sell = info.get("buy"), info.get("sell")
    if not buy or not sell or sell > buy:
        return None
    return float(buy), float(sell)


def signals(close):
    """The v0 signals on completed daily closes (oldest first), for the last day."""
    from caluclator.technical import moving_averages, rally_legs
    import talib
    from caluclator.technical import RALLY_REVERSAL
    c = np.asarray(close, dtype=float)
    direction, start = rally_legs(c)
    s50 = moving_averages(c)[50]
    e20, e50 = talib.EMA(c, 20), talib.EMA(c, 50)
    i = len(c) - 1
    rally = direction[i] == "up"
    started = rally and i > 0 and direction[i - 1] != "up"
    peak = float(c[start[i]:i + 1].max())
    return {
        "close": float(c[i]), "sma50": float(s50[i]), "ema20": float(e20[i]), "ema50": float(e50[i]),
        "rally": bool(rally), "rally_started": bool(started),
        "rally_end": peak * (1 - RALLY_REVERSAL) if rally else None,
        "broke": bool(not rally and c[i] < s50[i]),
        "back": bool((c[i] > s50[i] and e20[i] > e50[i]) or started),
    }


def analyst_target(sig, was_out):
    """(target gold share, out, reason) of analyst v0."""
    out = (was_out or sig["broke"]) and not sig["back"]
    if out and not was_out:
        return 0.0, True, "confirmed break: rally over and below the 50-day average"
    if out:
        return 0.0, True, "still out: no recovery above the 50-day with EMA20 above EMA50"
    if was_out:
        return 1.0, False, ("new rally" if sig["rally_started"] else
                            "recovered: above the 50-day with EMA20 above EMA50")
    return 1.0, False, "uptrend intact: no confirmed break"


def system_target(final_decision, current_share):
    if final_decision == "BUY":
        return 1.0, "system BUY"
    if final_decision == "SELL":
        return 0.0, "system SELL"
    return current_share, f"system {final_decision or 'UNKNOWN'}: hold"


def decide(book, target, quote, traded_today, band=BAND):
    """The trade this run makes toward `target`, under the contract, or a HOLD."""
    if traded_today:
        return Decision("HOLD", 0, None, "one trade a day: already traded today")
    if quote is None:
        return Decision("HOLD", 0, None, f"no fresh {VENUE} buy and sell price at this run")
    buy, sell = quote
    value, share = book.value(sell), book.share(sell)
    if abs(target - share) < band:
        return Decision("HOLD", 0, None, "on target")
    if target > share:
        want = int(math.floor(target * value / buy))
        grams = min(want - book.grams, int(book.cash // buy))
        if grams < 1:
            return Decision("HOLD", 0, None, "cash below the price of one gram")
        return Decision("BUY", grams, buy, "")
    keep = int(math.floor(target * value / sell))
    grams = book.grams - keep
    if grams < 1:
        return Decision("HOLD", 0, None, "less than one gram to sell")
    return Decision("SELL", grams, sell, "")


def apply(book, decision):
    if decision.action == "BUY":
        return Book(book.cash - decision.grams * decision.price, book.grams + decision.grams)
    if decision.action == "SELL":
        return Book(book.cash + decision.grams * decision.price, book.grams - decision.grams)
    return Book(book.cash, book.grams)


def conflicts(target, stance_score, final_decision):
    """Where the signals disagree with v0's target: logged as UNDECIDED when no trade is
    made, the cases the quarterly review studies."""
    found = []
    if target >= 1.0 and stance_score is not None and stance_score <= -1:
        found.append("analyst stance bearish while v0 stays invested")
    if target <= 0.0 and stance_score is not None and stance_score >= 2:
        found.append("analyst stance bullish while v0 is out")
    if target <= 0.0 and final_decision == "BUY":
        found.append("system BUY while v0 is out")
    if target >= 1.0 and final_decision == "SELL":
        found.append("system SELL while v0 is invested")
    return found


def quarter_change(value, base):
    return (value / base - 1) * 100 if base else None
