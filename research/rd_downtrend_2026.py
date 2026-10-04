"""What drove 18K from 20.61M (2026-01-29) to 15.65M (2026-06-16), and what was visible on
the way? (SP-D, 2026-10-04)

Month by month: 18K (tgju), the dollar and world gold (tgju), the fair value they imply
(world gold x dollar x 0.75 / 31.1035), 18K's gap to it, and the gold funds' money flow
from TSETMC: individuals' net buying (buy value - sell value, billion toman) and the value
traded, summed over every gold fund that traded that day.
"""
import json
import os
from bisect import bisect_right
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))
F = json.load(open(os.path.join(HERE, "data", "tsetmc_gold_funds.json"), encoding="utf-8"))
NOT_GOLD = {"سافرون"}


def series(k):
    rows = T[k]
    return [date.fromisoformat(r["date"]) for r in rows], [float(r["close"]) for r in rows]


gd, gc = series("geram18")
ud, uc = series("price_dollar_rl")
xd, xc = series("ons")


def at(dates, closes, day):
    k = bisect_right(dates, day) - 1
    return closes[k] if k >= 0 else None


flow = defaultdict(float)       # day -> individuals' net buying, rial
value = defaultdict(float)      # day -> value traded, rial
for code, f in F.items():
    if f["symbol"] in NOT_GOLD:
        continue
    for r in f["flows"]:
        day = str(r["recDate"])
        flow[day] += r["buy_I_Value"] - r["sell_I_Value"]
    for p in f["prices"]:
        value[p["date"]] += p["value"]

print("month     18K     dollar   world gold  fair    18K vs fair   individuals' net   value traded")
print("          (M T)   (T)      ($/oz)      (M T)                 (bn toman)        (bn toman)")
months = sorted({d.strftime("%Y-%m") for d in gd if d >= date(2025, 10, 1)})
for m in months:
    days = [d for d in gd if d.strftime("%Y-%m") == m]
    end = days[-1]
    g, u, x = at(gd, gc, end), at(ud, uc, end), at(xd, xc, end)
    fair = x * u * 0.75 / 31.1035
    keys = [k for k in flow if k.startswith(m.replace("-", ""))]
    net = sum(flow[k] for k in keys) / 1e10
    traded = sum(value[k] for k in value if k.startswith(m.replace("-", ""))) / 1e10
    print(f"{m}  {g / 1e7:6.2f}  {u / 10:8,.0f}  {x:8,.0f}   {fair / 1e7:6.2f}   {(g / fair - 1) * 100:+6.1f}%       "
          f"{net:+9,.0f}        {traded:9,.0f}")

a, b = date(2026, 1, 29), date(2026, 6, 16)
for name, (dd, cc) in (("18K", (gd, gc)), ("dollar", (ud, uc)), ("world gold", (xd, xc))):
    print(f"{name:10} {a} -> {b}: {(at(dd, cc, b) / at(dd, cc, a) - 1) * 100:+.1f}%")
