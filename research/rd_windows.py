"""The ground before any model (SP_D_HANDOFF.md section 75): 18K's history cut into its windows, rises, declines
and sideways stretches, and what the drivers did inside each. Descriptive, no test.

- Turning points: a zigzag on 18K's daily close, a new swing when the close reverses 8% from the last extreme.
- A swing is a rise or a decline. A sideways window is a stretch of 20 days or more whose closes stay within a
  band of 6% (high over low), found inside the swings.
- For each window: its days, 18K's change, fixed income's, the dollar's, world gold's (ons, in dollars), Tether's
  (from 2020-11), the coin premium's change, GVZ's mean.

    python research/rd_windows.py
"""

import json
import math
import os
import statistics as st
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
REVERSAL = 0.08
BAND = 0.06
MIN_SIDEWAYS = 20


def zigzag(closes):
    """Indices of the turning points: each reverses REVERSAL from the extreme before it."""
    pts, direction = [0], 0
    ext = 0
    for i in range(1, len(closes)):
        if direction >= 0:
            if closes[i] > closes[ext]:
                ext = i
            elif closes[i] < closes[ext] * (1 - REVERSAL):
                if direction == 1 or ext != pts[-1]:
                    pts.append(ext)
                direction, ext = -1, i
        if direction < 0:
            if closes[i] < closes[ext]:
                ext = i
            elif closes[i] > closes[ext] * (1 + REVERSAL):
                pts.append(ext)
                direction, ext = 1, i
        if direction == 0 and closes[i] < closes[0] * (1 - REVERSAL):
            direction = -1
    pts.append(len(closes) - 1)
    return sorted(set(pts))


def sideways(closes, a, b):
    """Sideways stretches inside [a, b]: maximal runs of MIN_SIDEWAYS days or more within BAND."""
    out, i = [], a
    while i < b:
        j, lo, hi = i, closes[i], closes[i]
        while j + 1 <= b:
            lo2, hi2 = min(lo, closes[j + 1]), max(hi, closes[j + 1])
            if hi2 / lo2 - 1 > BAND:
                break
            j, lo, hi = j + 1, lo2, hi2
        if j - i + 1 >= MIN_SIDEWAYS:
            out.append((i, j))
            i = j + 1
        else:
            i += 1
    return out


def change(series, a, b):
    x, y = series[a], series[b]
    return y / x - 1 if x and y else None


def main():
    with open(os.path.join(HERE, "data", "panel.json"), encoding="utf-8") as f:
        rows = [r for r in json.load(f)["rows"] if r["date"] >= "2015-03-15"]
    d = [r["date"] for r in rows]
    g = [r["g18"] for r in rows]
    col = {k: [r.get(k) for r in rows] for k in ("fi", "usd", "ons_prev", "tether", "coin_premium", "gvz_prev")}
    turns = zigzag(g)
    windows = []
    for a, b in zip(turns, turns[1:]):
        kind = "rise" if g[b] > g[a] else "decline"
        windows.append((kind, a, b))
        for s, e in sideways(g, a, b):
            windows.append(("sideways", s, e))
    windows.sort(key=lambda w: (w[1], w[0] != "sideways"))

    def describe(kind, a, b):
        cp0, cp1 = col["coin_premium"][a], col["coin_premium"][b]
        gv = [x for x in col["gvz_prev"][a:b + 1] if x]
        return {"kind": kind, "from": d[a], "to": d[b], "days": b - a, "g18": change(g, a, b), "fi": change(col["fi"], a, b),
                "usd": change(col["usd"], a, b), "world": change(col["ons_prev"], a, b),
                "tether": change(col["tether"], a, b), "coin_premium": (cp1 - cp0) if cp0 is not None and cp1 is not None else None,
                "gvz": st.mean(gv) if gv else None}

    table = [describe(*w) for w in windows]
    with open(os.path.join(HERE, "data", "windows.json"), "w", encoding="utf-8") as f:
        json.dump(table, f, ensure_ascii=False, indent=1)
    fmt = lambda x: f"{x:+6.1%}" if x is not None else "     -"
    print(f"{'kind':9} {'from':10} {'to':10} {'days':>4} {'18K':>7} {'FI':>7} {'dollar':>7} {'world':>7} {'Tether':>7} {'coin pp':>7} {'GVZ':>5}")
    for t in table:
        cp = f"{t['coin_premium']:+7.1f}" if t["coin_premium"] is not None else "      -"
        gv = f"{t['gvz']:5.1f}" if t["gvz"] else "    -"
        print(f"{t['kind']:9} {t['from']} {t['to']} {t['days']:4d} {fmt(t['g18'])} {fmt(t['fi'])} {fmt(t['usd'])} "
              f"{fmt(t['world'])} {fmt(t['tether'])} {cp} {gv}")
    print("\nBy kind (typical values):")
    for kind in ("rise", "decline", "sideways"):
        part = [t for t in table if t["kind"] == kind]
        med = lambda k: st.median([t[k] for t in part if t[k] is not None]) if any(t[k] is not None for t in part) else None
        fi_won = sum(1 for t in part if t["fi"] is not None and t["g18"] is not None and t["fi"] > t["g18"])
        print(f"  {kind:9} {len(part):3} windows, {med('days'):.0f} days typical; 18K {med('g18'):+.1%}, dollar {med('usd'):+.1%}, "
              f"world {med('world'):+.1%}, coin premium {med('coin_premium'):+.1f} pp; fixed income beat 18K in {fi_won} of {len(part)}")
    total = len(rows)
    for kind in ("rise", "decline"):
        days = sum(t["days"] for t in table if t["kind"] == kind)
        print(f"  share of days in a {kind}: {days / total:.0%}")
    sd = sum(t["days"] for t in table if t["kind"] == "sideways")
    print(f"  share of days in a sideways stretch: {sd / total:.0%}")


if __name__ == "__main__":
    main()
