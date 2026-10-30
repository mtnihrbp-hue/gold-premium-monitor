"""G4, the windows read (SP_D_HANDOFF.md section 76.4): what the drivers showed on the day a window began.
Descriptive, not a test.

For every window of research/rd_windows.py (windows.json) its first day: the top before a decline, the low
before a rise, the first day of a sideways stretch. On that day, each driver's value is ranked against all days
from 2015-03 (a percentile, 50 = ordinary). A driver whose ranks bunch at one end before one kind of window is
a pattern to test; one near 50 says nothing.

The drivers, known at the day's close:
- 18K's 20 and 60-day returns, its 60-day efficiency ratio;
- the dollar's 20-day return, its acceleration (last 250 days against the 750-day pace), its real level
  (the dollar x US CPI / Iran CPI, CPI lagged one full month) against its own 5-year mean;
- Tether's 5-day return; world gold's 20-day return; GVZ and its 20-day change;
- the coin's premium and its 20-day change; the gap to the world price;
- the funds' flows: individuals' net buying and buyers' power (5-day means), turnover (5-day mean),
  fipiran units (the last step);
- E-1b's calm forecast.

    python research/rd_windows_read.py
"""

import bisect
import json
import math
import os
import statistics as st
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))


def lr(a, b):
    return math.log(a / b) if a and b and a > 0 and b > 0 else None


def mean5(xs, i):
    v = [x for x in xs[max(0, i - 4):i + 1] if x is not None]
    return st.mean(v) if len(v) >= 3 else None


def cpi_asof(series, day):
    """CPI of the month before the month before `day`'s month: a full month's lag for publication."""
    y, m = day.year, day.month - 2
    while m <= 0:
        y, m = y - 1, m + 12
    return series.get(f"{y:04d}-M{m:02d}")


def drivers(rows, macro, calm):
    n = len(rows)
    col = lambda k: [r.get(k) for r in rows]
    g, usd, teth, ons, gvz, coin, gap = (col(k) for k in ("g18", "usd", "tether", "ons_prev", "gvz_prev", "coin_premium", "gap"))
    net_i, power_i, turn, units = col("net_i"), col("power_i"), col("turnover"), col("units_flow")
    dates = [date.fromisoformat(r["date"]) for r in rows]
    cpi_ir = dict(macro["cpi_iran"])
    cpi_us = dict(macro["cpi_us"])
    real = []
    for i in range(n):
        a, b = cpi_asof(cpi_ir, dates[i]), cpi_asof(cpi_us, dates[i])
        real.append(math.log(usd[i] * b / a) if usd[i] and a and b else None)
    out = []
    last_units = None
    for i in range(n):
        if units[i] is not None:
            last_units = units[i]
        f = {}
        f["18K 20d"] = lr(g[i], g[i - 20]) if i >= 20 else None
        f["18K 60d"] = lr(g[i], g[i - 60]) if i >= 60 else None
        steps = [lr(g[j], g[j - 1]) for j in range(i - 59, i + 1)] if i >= 60 else []
        f["efficiency 60d"] = (abs(f["18K 60d"]) / sum(abs(s) for s in steps)
                               if steps and all(s is not None for s in steps) and f["18K 60d"] is not None and sum(abs(s) for s in steps) else None)
        f["dollar 20d"] = lr(usd[i], usd[i - 20]) if i >= 20 else None
        if i >= 750 and usd[i] and usd[i - 250] and usd[i - 749]:
            f["dollar acceleration"] = math.log(usd[i] / usd[i - 250]) - math.log(usd[i] / usd[i - 749]) * 250 / 749
        else:
            f["dollar acceleration"] = None
        past = [x for x in real[max(0, i - 1250):i + 1] if x is not None]
        f["real dollar vs 5y"] = real[i] - st.mean(past) if real[i] is not None and len(past) >= 500 else None
        f["Tether 5d"] = lr(teth[i], teth[i - 5]) if i >= 5 else None
        f["world gold 20d"] = lr(ons[i], ons[i - 20]) if i >= 20 else None
        f["GVZ"] = gvz[i]
        f["GVZ 20d"] = lr(gvz[i], gvz[i - 20]) if i >= 20 else None
        f["coin premium"] = coin[i]
        f["coin premium 20d"] = coin[i] - coin[i - 20] if i >= 20 and coin[i] is not None and coin[i - 20] is not None else None
        f["gap to world price"] = gap[i]
        f["individuals' net buying 5d"] = mean5(net_i, i)
        f["buyers' power 5d"] = mean5(power_i, i)
        f["turnover 5d"] = mean5(turn, i)
        f["fipiran units, last step"] = last_units if dates[i] >= date(2019, 1, 2) else None
        c = calm.get(rows[i]["date"], {}).get("X")
        f["calm forecast"] = c
        out.append(f)
    return out


def main():
    with open(os.path.join(HERE, "data", "panel.json"), encoding="utf-8") as f:
        rows = json.load(f)["rows"]
    with open(os.path.join(HERE, "data", "macro.json"), encoding="utf-8") as f:
        macro = json.load(f)
    with open(os.path.join(HERE, "data", "calm_forecasts_b.json"), encoding="utf-8") as f:
        calm = json.load(f)
    with open(os.path.join(HERE, "data", "windows.json"), encoding="utf-8") as f:
        windows = json.load(f)
    F = drivers(rows, macro, calm)
    idx = {r["date"]: i for i, r in enumerate(rows)}
    names = list(F[0].keys())
    pool = {k: sorted(F[i][k] for i in range(len(rows)) if rows[i]["date"] >= "2015-03-15" and F[i][k] is not None) for k in names}

    def pct(k, v):
        p = pool[k]
        return 100 * bisect.bisect_left(p, v) / len(p) if p else None

    kinds = ("decline", "sideways", "rise")
    starts = {k: [idx[w["from"]] for w in windows if w["kind"] == k and w["from"] in idx] for k in kinds}
    table = {}
    print(f"{'driver':30} " + " ".join(f"{k + ' (n, typical rank)':>26}" for k in kinds))
    for name in names:
        cells, row = [], {}
        for k in kinds:
            ranks = [pct(name, F[i][name]) for i in starts[k] if F[i][name] is not None]
            if ranks:
                row[k] = (len(ranks), st.median(ranks), sum(1 for r in ranks if r >= 80), sum(1 for r in ranks if r <= 20))
                cells.append(f"{len(ranks):4d}  {st.median(ranks):4.0f}  (top {row[k][2]:2d}, bottom {row[k][3]:2d})")
            else:
                cells.append(f"{'-':>26}")
        table[name] = row
        print(f"{name:30} " + " ".join(f"{c:>26}" for c in cells))
    now = F[-1]
    print(f"\nToday ({rows[-1]['date']}), each driver's rank:")
    print("   " + "; ".join(f"{k} {pct(k, v):.0f}" for k, v in now.items() if v is not None))
    with open(os.path.join(HERE, "data", "windows_read.json"), "w", encoding="utf-8") as f:
        json.dump({"table": table, "today": {k: pct(k, v) for k, v in now.items() if v is not None}}, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
