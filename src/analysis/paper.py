"""PAPER: the analyst trades a hypothetical 135,000,000 toman in whole grams of 18K.

The owner's scenario and contract (2026-10-04, SP_D_HANDOFF.md sections 9-10):

1. Capital: 135,000,000 toman in cash on the start day. "Strict numbers, residue around
   1 to 2%": at 2026-10-04's prices 5 g leave 2.0% at Daric and 0.85% at Goldika.
2. Venues: Daric first (an order book, 0.26% between buying and selling), then Goldika
   (2.37%), then Ayyareh (its price plus or minus its fee, 1-2% a side): each trade runs
   on the first venue whose quote is fresh, buying at its buy price and selling at its
   sell price from the same reading, and records which. The grams are one holding.
3. Units: whole grams, at least 1 g a trade; the residue stays as cash.
4. At most one trade per Tehran day, at any scheduled run (06:00-21:00).
5. No borrowing and no short selling.
6. No trade without a fresh quote with both sides on some venue of the chain.
7. A report at 21:00: gold, cash, total, and the profit or loss against the quarter's
   first day. Quarters are Persian seasons (1 Farvardin, Tir, Mehr, Dey).
8. A push on every trade, labelled PAPER: the system's own BUY/SELL alert keeps its
   authority, this is a hypothetical account reporting what it did.
9. Every run is logged with its inputs, UNDECIDED where the signals conflict.
10. Rules change only at a quarter boundary, under a new version name.

ANALYST v1.1, "brave" (owner: "the system trader is a brave one"; "reverse one, let it
trade more", 2026-10-04). It trades a swing part, about a fifth of its grams: sells it
once a venue pays TAKE_PCT over its cost, buys it back RE_BUY_PCT under the sale or
after MAX_OUT trading days at the latest, and buys more whenever the cash covers a gram.
Over it sits the quant engine's volatility brake (analysis/quant.py): the gold share
never exceeds the growth-optimal f* = mu/sigma^2, so in a storm the brake sells down.
At Daric's cost (research/rd_trade_more.py): swing + brake x29.13 against holding's
x26.19 on 2016-2023 (+11.2%, 26 trades a year), x9.22 against x9.91 on 2024-2026
(-7.0%); the swing alone +0.7% and -6.5%. Trading more measurably costs more: a +3%
target or a 40% swing lost 12-25% against holding on 2024-2026, so the target stays +5%.

Shadow accounts, silent, for the quarterly review: the quant engine alone ("quant": the
growth-optimal share inside its Davis-Norman band, +13.1% / -0.7% against holding), v0
("cautious"), buy-and-hold, and the system's own final BUY/SELL.
"""

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Optional

import numpy as np

START_CASH_IRR = 1_350_000_000            # 135,000,000 toman
VENUES = ("Daric", "Goldika", "Ayyareh")
SWING_SHARE = 0.2                         # the part of the grams the brave analyst trades
TAKE_PCT = 5.0                            # sell the swing at +5% over what it cost
RE_BUY_PCT = 2.0                          # buy it back 2% under the sale price ...
MAX_OUT_DAYS = 5                          # ... or after 5 trading days at the latest
BAND = 0.2                                # v0: trade only this far off its target
REPORT_HOUR = 21                          # the first run from 21:00 Tehran reports the day
ANALYST, QUANT, CAUTIOUS, HOLD, SYSTEM = "analyst", "quant", "cautious", "buy_and_hold", "system"
ACCOUNTS = (                              # (name, policy version, pushes to Telegram)
    (ANALYST, "analyst-v1.1-brave-braked", True),
    (QUANT, "quant-v1-growth-optimal", False),
    (CAUTIOUS, "analyst-v0-cautious", False),
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
class Quote:
    venue: str
    buy: float
    sell: float


@dataclass
class Decision:
    action: str                           # BUY, SELL, HOLD, UNDECIDED
    grams: int
    price: Optional[float]
    reason: str
    swing: Dict = field(default_factory=dict)     # the brave analyst's state after it
    plan: str = ""                                # what it will do next, for the report


def venue_quote(markets, venues=VENUES):
    """The first venue of the chain whose quote passed validation with both sides."""
    for venue in venues:
        info = (markets or {}).get(venue)
        if not info or info.get("status") != "OK":
            continue
        buy, sell = info.get("buy"), info.get("sell")
        if buy and sell and 0 < sell <= buy:
            return Quote(venue, float(buy), float(sell))
    return None


# -- v1, brave ----------------------------------------------------------------------------

def _trading_days_since(start, today):
    from analysis.direction import trading_date
    days = 0
    while trading_date(start, days + 1) <= today:
        days += 1
    return days


def brave(book, quote, swing, today, traded_today, cap=1.0):
    """The brave analyst's decision this run. `swing`: its state from the last run --
    {"grams", "entry", "sold_at", "sold_day"} -- or {} before its first trade. `cap`: the
    quant engine's growth-optimal share f*, the most of the account it holds in gold."""
    swing = dict(swing or {})
    if traded_today:
        return Decision("HOLD", 0, None, "one trade a day: already traded today", swing, plan(swing))
    if quote is None:
        return Decision("HOLD", 0, None, "no fresh buy and sell price on any venue", swing, plan(swing))
    cap = 1.0 if cap is None else float(cap)
    value = book.value(quote.sell)
    allowed = int(math.floor(cap * value / quote.sell))
    if book.grams > allowed:                                  # the brake: a storm, sell down
        return Decision("SELL", book.grams - allowed, quote.sell,
                        f"volatility brake: the growth-optimal share is {cap:.0%}", swing, plan(swing))
    affordable = max(0, min(int(book.cash // quote.buy), int(math.floor(cap * value / quote.buy)) - book.grams))

    if not swing:                                         # day one: all in, a fifth to trade
        if affordable < 1:
            return Decision("HOLD", 0, None, "cash below the price of one gram", swing, "")
        total = book.grams + affordable
        swing = {"grams": max(1, int(round(total * SWING_SHARE))), "entry": quote.buy,
                 "sold_at": None, "sold_day": None}
        return Decision("BUY", affordable, quote.buy, f"opening: {total} g, {swing['grams']} g of them to trade",
                        swing, plan(swing))

    if swing.get("sold_at") is None:                      # swing held: take the profit
        gain = (quote.sell / swing["entry"] - 1) * 100
        if gain >= TAKE_PCT and book.grams >= swing["grams"]:
            sold = dict(swing, sold_at=quote.sell, sold_day=str(today))
            return Decision("SELL", swing["grams"], quote.sell,
                            f"{gain:+.1f}% over its {swing['entry'] / 1e7:.2f}M cost: profit taken", sold, plan(sold))
        if affordable >= 1:                               # residue grown: stay fully in
            return Decision("BUY", affordable, quote.buy, "cash covers another gram: fully invested again",
                            swing, plan(swing))
        return Decision("HOLD", 0, None, f"swing {gain:+.1f}% over its cost, waiting for +{TAKE_PCT:.0f}%",
                        swing, plan(swing))

    # swing sold: buy it back lower, or after MAX_OUT trading days
    drop = (quote.buy / swing["sold_at"] - 1) * 100
    days_out = _trading_days_since(date.fromisoformat(swing["sold_day"]), today)
    if affordable >= 1 and (drop <= -RE_BUY_PCT or days_out >= MAX_OUT_DAYS):
        why = (f"{drop:+.1f}% under its {swing['sold_at'] / 1e7:.2f}M sale: bought back lower" if drop <= -RE_BUY_PCT
               else f"{days_out} trading days out: back in so a rising market is not missed")
        back = {"grams": max(1, int(round((book.grams + affordable) * SWING_SHARE))), "entry": quote.buy,
                "sold_at": None, "sold_day": None}
        return Decision("BUY", affordable, quote.buy, why, back, plan(back))
    return Decision("HOLD", 0, None, f"waiting to buy back: {drop:+.1f}% from the sale, {days_out} days out",
                    swing, plan(swing))


def plan(swing):
    """The brave analyst's next move in plain words, for the report and the push."""
    if not swing:
        return ""
    if swing.get("sold_at") is None:
        return (f"sell {swing['grams']} g if a venue pays {swing['entry'] * (1 + TAKE_PCT / 100) / 1e7:.2f}M "
                f"or more (+{TAKE_PCT:.0f}% over its cost)")
    from analysis.direction import trading_date
    from timeutil import persian_day
    by = trading_date(date.fromisoformat(swing["sold_day"]), MAX_OUT_DAYS)
    return (f"buy {swing['grams']} g back at {swing['sold_at'] * (1 - RE_BUY_PCT / 100) / 1e7:.2f}M or less, "
            f"or on {persian_day(by)} at the latest")


# -- v0, cautious (a shadow since v1) -------------------------------------------------

def signals(close):
    """v0's signals on completed daily closes (oldest first), for the last day."""
    from caluclator.technical import RALLY_REVERSAL, moving_averages, rally_legs
    import talib
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
    """(target gold share, out, reason) of v0."""
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
    """The trade a target-share account (v0, hold, system) makes this run, or a HOLD."""
    if traded_today:
        return Decision("HOLD", 0, None, "one trade a day: already traded today")
    if quote is None:
        return Decision("HOLD", 0, None, "no fresh buy and sell price on any venue")
    value, share = book.value(quote.sell), book.share(quote.sell)
    if abs(target - share) <= band:
        return Decision("HOLD", 0, None, "on target")
    if target > share:
        want = int(math.floor(target * value / quote.buy))
        grams = min(want - book.grams, int(book.cash // quote.buy))
        if grams < 1:
            return Decision("HOLD", 0, None, "cash below the price of one gram")
        return Decision("BUY", grams, quote.buy, "")
    keep = int(math.floor(target * value / quote.sell))
    grams = book.grams - keep
    if grams < 1:
        return Decision("HOLD", 0, None, "less than one gram to sell")
    return Decision("SELL", grams, quote.sell, "")


def apply(book, decision):
    if decision.action == "BUY":
        return Book(book.cash - decision.grams * decision.price, book.grams + decision.grams)
    if decision.action == "SELL":
        return Book(book.cash + decision.grams * decision.price, book.grams - decision.grams)
    return Book(book.cash, book.grams)


def conflicts(stance_score, final_decision, swing):
    """Where the signals disagree with the brave analyst: logged as UNDECIDED when it does
    not trade, the cases the quarterly review studies."""
    found = []
    holding_swing = bool(swing) and swing.get("sold_at") is None
    if holding_swing and stance_score is not None and stance_score <= -1:
        found.append("analyst stance bearish while the swing is held")
    if swing and swing.get("sold_at") is not None and stance_score is not None and stance_score >= 3:
        found.append("analyst stance strongly bullish while the swing is sold")
    if final_decision == "BUY" and swing and swing.get("sold_at") is not None:
        found.append("system BUY while the swing is sold")
    if final_decision == "SELL" and holding_swing:
        found.append("system SELL while fully invested")
    return found
