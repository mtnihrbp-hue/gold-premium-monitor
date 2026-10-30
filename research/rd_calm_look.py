"""A first look, not a registered test (SP_D_HANDOFF.md section 73): is calm forecastable for 18K, where direction
was not (72.3)? And in the windows the record forecast as calm, did fixed income win more often?

- realised volatility over the last 20 days, against the next 20 (from day t+2, a day's delay);
- the largest move within the next 20 days;
- terciles of today's volatility ranked against the 500 days before (no look-ahead), and in each, how often
  18K lost to fixed income over the next 20 days, and by how much.

    python research/rd_calm_look.py
"""

import json
import math
import os
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))


def spearman(a, b):
    def ranks(x):
        order = sorted(range(len(x)), key=lambda i: x[i])
        r = [0] * len(x)
        for k, i in enumerate(order):
            r[i] = k
        return r
    ra, rb = ranks(a), ranks(b)
    ma, mb = st.mean(ra), st.mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    return num / math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))


def main():
    with open(os.path.join(HERE, "data", "panel.json"), encoding="utf-8") as f:
        rows = json.load(f)["rows"]
    g = [r["g18"] for r in rows]
    usd = [r["usd"] for r in rows]
    fi = [r["fi"] for r in rows]
    n, H = len(rows), 20
    ret = [None] + [math.log(g[i] / g[i - 1]) for i in range(1, n)]
    uret = [None] + [math.log(usd[i] / usd[i - 1]) if usd[i] and usd[i - 1] else None for i in range(1, n)]
    out = []
    for i in range(520, n - H - 2):
        past = ret[i - 19:i + 1]
        fut = ret[i + 2:i + 2 + H]
        upast = [x for x in uret[i - 19:i + 1] if x is not None]
        if None in past or None in fut or not fi[i + 1] or not fi[i + 1 + H] or len(upast) < 15:
            continue
        rv, frv = st.pstdev(past), st.pstdev(fut)
        base = g[i + 1]
        maxmove = max(abs(math.log(g[i + 1 + k] / base)) for k in range(1, H + 1))
        excess = math.log(g[i + 1 + H] / g[i + 1]) - math.log(fi[i + 1 + H] / fi[i + 1])
        hist = [st.pstdev(ret[j - 19:j + 1]) for j in range(i - 500, i, 5) if None not in ret[j - 19:j + 1]]
        pct = sum(1 for x in hist if x < rv) / len(hist)
        out.append((rows[i]["date"], rv, frv, maxmove, excess, pct, st.pstdev(upast)))
    print(f"{len(out)} days, {out[0][0]} to {out[-1][0]}")
    print(f"realised volatility, last 20 days against the next 20: rank correlation {spearman([o[1] for o in out], [o[2] for o in out]):+.2f}")
    print(f"realised volatility against the largest move of the next 20 days: {spearman([o[1] for o in out], [o[3] for o in out]):+.2f}")
    print(f"the dollar's volatility against 18K's next 20 days: {spearman([o[6] for o in out], [o[2] for o in out]):+.2f}")
    print("\nToday's volatility, ranked against the 500 days before:")
    print(f"{'tercile':>12} {'days':>6} {'18K lost to fixed income':>26} {'typical excess':>15} {'largest move, typical':>22}")
    for name, lo, hi in (("calm third", 0, 1 / 3), ("middle", 1 / 3, 2 / 3), ("active third", 2 / 3, 1.01)):
        part = [o for o in out if lo <= o[5] < hi]
        lost = sum(1 for o in part if o[4] < 0) / len(part)
        print(f"{name:>12} {len(part):6} {lost:26.0%} {st.median(o[4] for o in part):+15.1%} {st.median(o[3] for o in part):22.1%}")
    for label, a, b in (("2015-2019", "2015", "2020"), ("2020-2023", "2020", "2024"), ("2024-2026", "2024", "2027")):
        part = [o for o in out if a <= o[0] < b]
        calm = [o for o in part if o[5] < 1 / 3]
        rest = [o for o in part if o[5] >= 1 / 3]
        if calm and rest:
            print(f"{label}: 18K lost to fixed income on {sum(o[4] < 0 for o in calm) / len(calm):.0%} of calm days, "
                  f"{sum(o[4] < 0 for o in rest) / len(rest):.0%} of the others ({len(calm)} calm days)")


if __name__ == "__main__":
    main()
