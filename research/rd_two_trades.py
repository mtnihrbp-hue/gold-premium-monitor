"""Does a second trade a day add profit? (SP-D, 2026-10-04)

The owner widened the contract to at most two trades a Tehran day -- a maximum, not a
target. The daily tgju history cannot show intraday trading, so this replays the brave
trader on production's hourly readings (research/data/hourly.json, 2026-08-04 -> 10-04,
610 readings, 62 days), at every reading, with one or two trades allowed a day.

Venue prices per reading: Daric's offer as its buy (sell = buy x (1 - 0.30%)), and
Goldika's buy (sell = buy x (1 - 2.37%), its measured gap). Swing rules swept over the
targets of sections 10-14. 135M toman, whole grams. Against holding over the same days.
"""
import itertools
import json
import os
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
rows = [r for r in json.load(open(os.path.join(HERE, "data", "hourly.json")))]
START = 1_350_000_000


def tehran_day(ts):
    return (datetime.fromisoformat(ts) + timedelta(hours=3, minutes=30)).date()


def run(venue, gap, take, re_buy, max_out_days, max_trades):
    cash, grams, swing_n, entry, sold_at, sold_day = float(START), 0, 0, None, None, None
    trades, per_day = 0, {}
    first_buy = last_sell = None
    for r in rows:
        buy = r["prices"].get(venue)
        if not buy:
            continue
        sell = buy * (1 - gap / 100)
        day = tehran_day(r["ts"])
        if per_day.get(day, 0) >= max_trades:
            last_sell = sell
            continue
        action = None
        if entry is None:
            g = int(cash // buy)
            if g:
                cash, grams, entry, swing_n = cash - g * buy, grams + g, buy, max(1, round(g * 0.2))
                first_buy, action = buy, "BUY"
        elif sold_at is None and sell >= entry * (1 + take / 100) and grams >= swing_n:
            cash, grams, sold_at, sold_day, action = cash + swing_n * sell, grams - swing_n, sell, day, "SELL"
        elif sold_at is not None and (buy <= sold_at * (1 - re_buy / 100) or (day - sold_day).days >= max_out_days + 1):
            g = int(cash // buy)
            if g:
                cash, grams, entry, sold_at, action = cash - g * buy, grams + g, buy, None, "BUY"
        if action:
            trades += 1
            per_day[day] = per_day.get(day, 0) + 1
        last_sell = sell
    value = cash + grams * last_sell
    hold_grams = int(START // first_buy)
    hold = START - hold_grams * first_buy + hold_grams * last_sell
    return value, hold, trades, sum(1 for v in per_day.values() if v == 2)


def ceiling(series, gap, max_trades):
    """The most any trader could make: perfect foresight, all in or all out, at most
    `max_trades` a Tehran day, paying the round trip `gap`. Dynamic programming over the
    readings, state = (in gold or in cash, trades used today); wealth is linear in each
    state, so the best of each state is the best path through it."""
    neg = float("-inf")
    cash = [neg] * (max_trades + 1)
    gold = [neg] * (max_trades + 1)  # grams
    day0 = None
    first = series[0][1]
    gold[0] = START / first  # start in gold, like holding; the oracle may also start in cash
    cash[0] = float(START)
    for day, buy in series:
        sell = buy * (1 - gap / 100)
        if day != day0:
            cash = [max(cash)] + [neg] * max_trades
            gold = [max(gold)] + [neg] * max_trades
            day0 = day
        for j in range(max_trades):
            if gold[j] > neg and gold[j] * sell > cash[j + 1]:
                cash[j + 1] = gold[j] * sell
            if cash[j] > neg and cash[j] / buy > gold[j + 1]:
                gold[j + 1] = cash[j] / buy
        last_sell = sell
    return max(max(cash), max(gold) * last_sell)


def median_series():
    out = []
    for r in rows:
        p = sorted(v for v in r["prices"].values() if v)
        if len(p) >= 3:
            out.append((tehran_day(r["ts"]), p[len(p) // 2]))
    return out


print("CEILING: perfect foresight, all in or all out (M toman at the end, from 135M)")
for label, series, gap in (("Daric, its own 32 days", [(tehran_day(r["ts"]), r["prices"]["Daric"]) for r in rows
                                                        if r["prices"].get("Daric")], 0.30),
                           ("median platform, Daric's 0.30%, 62 days", median_series(), 0.30),
                           ("median platform, Goldika's 2.37%, 62 days", median_series(), 2.37)):
    hold = START / series[0][1] * series[-1][1] * (1 - gap / 100)
    one, two = ceiling(series, gap, 1), ceiling(series, gap, 2)
    print(f"   {label:42} hold {hold / 1e7:6.1f}M | 1 a day {one / 1e7:6.1f}M | 2 a day {two / 1e7:6.1f}M"
          f" | the second trade adds {(two / one - 1) * 100:+.1f}%")

for venue, gap in (("Daric", 0.30), ("Goldika", 2.37)):
    print(f"\n{venue} (round trip {gap}%), 62 days of hourly readings")
    print("   take  buy back  days | 1 trade a day           | 2 trades a day")
    for take, re_buy, max_out in itertools.product((1.5, 2, 3, 5), (1, 1.5, 2), (3, 5)):
        one = run(venue, gap, take, re_buy, max_out, 1)
        two = run(venue, gap, take, re_buy, max_out, 2)
        if one[2] <= 1 and two[2] <= 1:
            continue
        print(f"   +{take:<4} -{re_buy:<6} {max_out:2}d  | {one[0] / 1e7:7.2f}M, {one[2]:2} trades     "
              f"| {two[0] / 1e7:7.2f}M, {two[2]:2} trades ({two[3]} two-trade days)   hold {one[1] / 1e7:.2f}M")
