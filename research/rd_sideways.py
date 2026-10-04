"""Sideways markets, the jump out of them, and cash parked in a fixed-income ETF (SP-D, 2026-10-04).

The owner: "idk if the system can understand the side moves. For a long time the price was
in 18m channel, up down side, then it jumped up up up. Again this could happen; knowing the
side and the start of the new jump is a key decision. Let's add another factor, fixed
income etf, and say the money is parked in that etf (Afran) for example."

1. FIXED INCOME. research/data/tsetmc_fixed_income.json (fetch_tsetmc_fixed_income.py, from
   Iran): each fund's yearly total return, a distribution day (a price drop) counted at the
   fund's usual daily accrual. The index is the median fund's daily return.
2. SIDEWAYS, found causally on 18K's daily closes (tgju, 2014-2026): the efficiency ratio
   (net move / total movement) over the last N days, against a random walk's 1/sqrt(N). The
   main definition (60 days, under a random walk) was fixed before the policies were run;
   the others are shown beside it. The episodes it finds are listed for the owner to check.
3. THE JUMP OUT. A breakout is a new 60-day closing high (low) after at least 10 of the last
   20 days sideways. What followed it, and whether the dollar had broken out first.
4. POLICIES, signal at day i, trade at day i+1's close, Daric's 0.30% round trip, against
   holding; cash either idle on the platform or parked in fixed income. Parking is slow:
   money from a gold sale reaches the fund 2 trading days later, and money from the fund
   reaches the platform 2 days after it is called, when the gold is bought at that day's
   price. The fund's own round trip: 0.10%.
"""
import json
import os
from bisect import bisect_right
from collections import defaultdict
from datetime import date

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))
FI = json.load(open(os.path.join(HERE, "data", "tsetmc_fixed_income.json"), encoding="utf-8"))
rows = T["geram18"]
d = [date.fromisoformat(r["date"]) for r in rows]
o, h, l, c = (np.array([float(r[k]) for r in rows]) for k in ("open", "high", "low", "close"))
flat = (o == h) & (h == l) & (l == c)
n = len(c)
ud = [date.fromisoformat(r["date"]) for r in T["price_dollar_rl"]]
uc = np.array([float(r["close"]) for r in T["price_dollar_rl"]])
usd = np.array([uc[bisect_right(ud, x) - 1] for x in d])

# 1. fixed income ----------------------------------------------------------------------------
EQUITY = ("اطلس", "آساس")   # equity funds the search also returned
fund_ret = {}
print("1. FIXED-INCOME FUNDS, total return by year (a distribution counted at the usual accrual)")
years = list(range(2016, 2027))
print("   " + " " * 10 + "".join(f"{y:>7}" for y in years))
for code, f in FI.items():
    if f["symbol"] in EQUITY:
        continue
    p = sorted(((date(int(x["date"][:4]), int(x["date"][4:6]), int(x["date"][6:])), x["close"]) for x in f["prices"]
                if x["close"] > 0), key=lambda t: t[0])
    ds = [t[0] for t in p]
    px = np.array([t[1] for t in p], dtype=float)
    r = px[1:] / px[:-1] - 1
    out = np.empty_like(r)
    for k in range(len(r)):
        recent = r[max(0, k - 20):k]
        usual = np.median(recent[recent > -0.003]) if len(recent[recent > -0.003]) else 0.0
        out[k] = usual if r[k] < -0.003 else r[k]
    series = dict(zip(ds[1:], out))
    fund_ret[f["symbol"]] = series
    by_year = defaultdict(lambda: 1.0)
    for k, v in series.items():
        by_year[k.year] *= 1 + v
    cells = "".join(f"{(by_year[y] - 1) * 100:6.1f}%" if any(k.year == y for k in series) else "       " for y in years)
    print(f"   {f['symbol']:10}{cells}")

fi_days = sorted({k for s in fund_ret.values() for k in s})
fi_index = {k: float(np.median([s[k] for s in fund_ret.values() if k in s])) for k in fi_days}
fi_daily = np.zeros(n)          # the index's return from day i-1 to day i on 18K's calendar
cum = np.cumsum([np.log1p(fi_index[k]) for k in fi_days])
for i in range(1, n):
    a, b = bisect_right(fi_days, d[i - 1]) - 1, bisect_right(fi_days, d[i]) - 1
    if a >= 0 and b > a:
        fi_daily[i] = np.expm1(cum[b] - cum[a])
by_year = defaultdict(lambda: 1.0)
for i in range(1, n):
    by_year[d[i].year] *= 1 + fi_daily[i]
g_year = {y: c[[i for i in range(n) if d[i].year == y][-1]] / c[[i for i in range(n) if d[i].year == y][0]] - 1 for y in years}
print("   " + "-" * 10 + "".join(f"{'':>7}" for _ in years))
print("   index     " + "".join(f"{(by_year[y] - 1) * 100:6.1f}%" for y in years))
print("   18K       " + "".join(f"{g_year[y] * 100:6.1f}%" for y in years))
af = fund_ret.get("افران", {})
if af:
    tail = [k for k in af if k >= date(2025, 10, 3)]
    print(f"   Afran, last 12 months: {(np.prod([1 + af[k] for k in tail]) - 1) * 100:.1f}%")

# 2. sideways --------------------------------------------------------------------------------
FIRST = next(i for i in range(n) if d[i] >= date(2014, 1, 1))


def efficiency(N):
    """Kaufman's efficiency ratio over N days: net move / total movement. A driftless random
    walk averages 1/sqrt(N); well under that is back and forth, well over it a trend."""
    er = np.full(n, np.nan)
    for i in range(N, n):
        if flat[i - N + 1:i + 1].mean() > 0.3:
            continue
        moves = np.abs(np.diff(c[i - N:i + 1])).sum()
        er[i] = abs(c[i] - c[i - N]) / moves if moves else 0
    return er


def forward(a, h):
    out = np.full(n, np.nan)
    out[:n - h] = (a[h:] / a[:n - h] - 1) * 100
    return out


F20, F60 = forward(c, 20), forward(c, 60)
fi_level = np.cumprod(1 + fi_daily)
FI20, FI60 = forward(fi_level, 20), forward(fi_level, 60)
CHANNEL = np.array([date(2026, 2, 1) <= x <= date(2026, 8, 17) for x in d])
since = np.arange(n) >= FIRST
print("\n2. SIDEWAYS, by definition (since 2014; next 20 / 60 days of 18K, and the fixed-income index's)")
print(f"   all days: 18K {np.nanmean(F20[since]):+.2f}% / {np.nanmean(F60[since]):+.2f}%, fixed income "
      f"{np.nanmean(FI20[since]):+.2f}% / {np.nanmean(FI60[since]):+.2f}%")
for N in (40, 60, 100):
    er = efficiency(N)
    for label, thr in (("under a random walk's", 1 / np.sqrt(N)), ("under 0.30", 0.30)):
        flag = np.nan_to_num(er, nan=1) < thr
        sel, rest = since & flag, since & ~flag & np.isfinite(er)
        beat = np.nanmean((F60 > FI60)[sel & np.isfinite(F60)]) * 100
        print(f"   {N:3} days, ER {label:22} ({thr:.2f}): {flag[since].mean() * 100:3.0f}% of days, the 1405 channel "
              f"{flag[CHANNEL].mean() * 100:3.0f}%;  sideways {np.nanmean(F20[sel]):+5.2f}% / {np.nanmean(F60[sel]):+6.2f}%,"
              f" other {np.nanmean(F20[rest]):+5.2f}% / {np.nanmean(F60[rest]):+6.2f}%;  18K beat fixed income over 60 days "
              f"on {beat:.0f}% of sideways days")

# the main definition, fixed before looking at the policies: 60 days, less net progress than a random walk
N = 60
ER = efficiency(N)
side = np.nan_to_num(ER, nan=1) < 1 / np.sqrt(N)
episodes, k = [], FIRST
while k < n:
    if side[k]:
        j = k
        while j + 1 < n and (side[j + 1] or (j + 6 < n and side[j + 1:j + 6].any())):
            j += 1
        episodes.append((k, j))
        k = j + 1
    else:
        k += 1


def jdate(i):
    return rows[i]["jdate"]


up_bo, down_bo = [], []
for i in range(FIRST + N + 1, n):
    if side[i - 20:i].sum() >= 10:
        prior = c[i - N:i]
        if c[i] > prior.max() and not any(i - b < 20 for b in up_bo):
            up_bo.append(i)
        elif c[i] < prior.min() and not any(i - b < 20 for b in down_bo):
            down_bo.append(i)

print(f"\n   MAIN: {N} days, ER under {1 / np.sqrt(N):.2f}: episodes of 20+ trading days, the 60-day range, and what came next")
for a, b in episodes:
    if b - a + 1 < 20:
        continue
    w = c[max(0, a - N + 1):b + 1]
    nxt = next((("up" if x in up_bo else "down", x) for x in range(a, min(n, b + 30)) if x in up_bo or x in down_bo), None)
    tail = f"then {nxt[0]} on {jdate(nxt[1])}, 60 days later {F60[nxt[1]]:+.0f}%" if nxt and np.isfinite(F60[nxt[1]]) else \
        (f"then {nxt[0]} on {jdate(nxt[1])}" if nxt else "")
    print(f"   {jdate(a)} -> {jdate(b)}  {b - a + 1:3} days  {w.min() / 1e7:6.2f} - {w.max() / 1e7:6.2f}M  {tail}")

print("\n   1405 day by day (every 5th trading day): S = sideways, U/D = breakout up/down")
line = []
for i in range(n):
    if d[i] >= date(2026, 1, 20) and (i % 5 == 0 or i in up_bo or i in down_bo):
        mark = "U" if i in up_bo else "D" if i in down_bo else "S" if side[i] else "."
        line.append(f"{jdate(i)[5:]} {c[i] / 1e7:.1f} {mark}")
for k in range(0, len(line), 6):
    print("   " + "   ".join(line[k:k + 6]))

print("\n3. THE JUMP OUT OF A SIDEWAYS MARKET (18K's next days, mean; all days in brackets)")
base20, base60 = np.nanmean(F20[since]), np.nanmean(F60[since])
other_highs = [i for i in range(FIRST + N, n) if c[i] > c[i - N:i].max() and side[i - 20:i].sum() == 0]
other_highs = [i for k_, i in enumerate(other_highs) if k_ == 0 or i - other_highs[k_ - 1] >= 20]
for label, events in (("up out of a range", up_bo), ("down out of a range", down_bo), (f"new {N}-day high, no range", other_highs)):
    ev = [i for i in events if np.isfinite(F20[i])]
    ev60 = [i for i in events if np.isfinite(F60[i])]
    if not ev:
        continue
    failed = 0
    for i in ev:
        mid = (c[i - N:i].max() + c[i - N:i].min()) / 2
        if (label.startswith("down") and (c[i + 1:i + 21] > mid).any()) or (not label.startswith("down") and (c[i + 1:i + 21] < mid).any()):
            failed += 1
    lead = sum(1 for i in ev if usd[i - 10:i].max() >= usd[i - N:i - 10].max() * 1.0)
    print(f"   {label:24} {len(ev):3}: 20d {np.mean(F20[ev]):+6.2f}% ({base20:+.2f}),  60d {np.mean(F60[ev60]) if ev60 else np.nan:+6.2f}%"
          f" ({base60:+.2f}),  back through the middle within 20 days {failed / len(ev) * 100:.0f}%,  the dollar at a new"
          f" {N}-day high in the 10 days before {lead}/{len(ev)}")
    if not label.startswith("new"):
        print("      " + ", ".join(f"{jdate(i)} {F20[i]:+.0f}%" for i in ev[-12:] if np.isfinite(F20[i])))

# 4. policies --------------------------------------------------------------------------------
F_STAR = np.clip(np.load(os.path.join(HERE, "data", "quant_D.npy")) /
                 (lambda r: [v := np.var(r[1:60])] and np.array([v := 0.94 * v + 0.06 * x ** 2 for x in r]))(
                     np.concatenate([[0.0], np.diff(np.log(c))])), 0, 1)
COST, FI_COST, LAG = 0.30, 0.10, 2


def simulate(target, lo, hi, park, idle=0):
    """target(i) -> gold share wanted after day i. Returns the end value of 1.0. With `park`,
    cash that has sat on the platform `idle` trading days goes to the fund."""
    idx = [i for i in range(n - 1) if lo <= d[i] <= hi]
    half = COST / 200
    gold, cash, fund = 0.0, 1.0, 0.0
    to_fund, to_cash = [], []        # (day index it arrives, amount)
    start = None
    idle_since = None
    for i in idx[:-1]:
        j = i + 1
        tg = target(i)
        fund *= 1 + fi_daily[j]
        for q in [x for x in to_fund if x[0] <= j]:
            fund += q[1] * (1 - FI_COST / 200)
            to_fund.remove(q)
        for q in [x for x in to_cash if x[0] <= j]:
            cash += q[1]
            to_cash.remove(q)
        buy, sell = c[j] * (1 + half), c[j] * (1 - half)
        pending = sum(q[1] for q in to_fund) + sum(q[1] for q in to_cash)
        value = cash + fund + pending + gold * sell
        want = tg * value
        have = gold * sell
        if want > have * 1.05 or (start is None):
            spend = min(cash, want - have)
            if spend > 0:
                gold, cash = gold + spend / buy, cash - spend
            short = want - have - max(spend, 0)
            if park and short > value * 0.05 and fund > 0:
                call = min(fund, short)
                fund -= call
                to_cash.append((j + LAG, call * (1 - FI_COST / 200)))
        elif want < have * 0.95:
            q = (have - want) / sell
            gold, cash = gold - q, cash + q * sell
        if cash > value * 0.01 and tg < 0.99:
            idle_since = j if idle_since is None else idle_since
            if park and j - idle_since >= idle:
                to_fund.append((j + LAG, cash))
                cash, idle_since = 0.0, None
        else:
            idle_since = None
        start = start or j
    j = idx[-1]
    return cash + fund + sum(q[1] for q in to_fund) + sum(q[1] for q in to_cash) + gold * c[j] * (1 - half)


def brave_target():
    """The brave trader of sections 10-14, swing 20%, +3% / -1.5% / 5 days, under the brake."""
    state = {"entry": None, "sold": None, "since": None}

    def t(i):
        cap = F_STAR[i] if np.isfinite(F_STAR[i]) else 1.0
        s = state
        if s["entry"] is None:
            s["entry"] = c[i]
            return cap
        if s["sold"] is None:
            if c[i] >= s["entry"] * 1.03:
                s["sold"], s["since"] = c[i], i
                return cap * 0.8
            return cap
        if c[i] <= s["sold"] * 0.985 or i - s["since"] >= 5:
            s["entry"], s["sold"] = c[i], None
            return cap
        return cap * 0.8
    return t


def range_park(share):
    """Inside a sideways market keep `share` of the money out of gold; all in otherwise."""
    return lambda i: 1 - share if side[i] else 1.0


def range_trade(share):
    """Trade the channel: inside a sideways market, sell `share` in the top quarter of the
    40-day range and buy it back in the bottom quarter; all in outside a range."""
    state = {"t": 1.0}

    def t(i):
        if not side[i]:
            state["t"] = 1.0
            return 1.0
        w = c[i - N + 1:i + 1]
        pos = (c[i] - w.min()) / (w.max() - w.min()) if w.max() > w.min() else 0.5
        if pos >= 0.75:
            state["t"] = 1 - share
        elif pos <= 0.25:
            state["t"] = 1.0
        return state["t"]
    return t


SPANS = (("2016-2023", date(2016, 1, 1), date(2023, 12, 31)), ("2024-2026", date(2024, 1, 1), date(2026, 12, 31)),
         ("the 1405 channel and jump", date(2026, 2, 1), date(2026, 12, 31)))
POLICIES = [("brake only", lambda: (lambda i: F_STAR[i] if np.isfinite(F_STAR[i]) else 1.0)),
            ("brave + brake", brave_target), ("sideways: 50% out", lambda: range_park(0.5)),
            ("sideways: 100% out", lambda: range_park(1.0)), ("sideways: trade the channel 40%", lambda: range_trade(0.4))]
print("\n4. POLICIES: end value of 1, against holding; cash idle | parked at once | parked after 5 idle days")
for label, lo, hi in SPANS:
    hold = simulate(lambda i: 1.0, lo, hi, False)
    print(f"   {label}: hold x{hold:.2f}")
    for name, make in POLICIES:
        res = [simulate(make(), lo, hi, False), simulate(make(), lo, hi, True, 0), simulate(make(), lo, hi, True, 5)]
        print(f"      {name:32} " + " | ".join(f"x{v:6.2f} ({(v / hold - 1) * 100:+6.1f}%)" for v in res))
