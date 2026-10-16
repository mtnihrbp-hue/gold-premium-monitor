"""Chart patterns on 18K, read as a chartist reads them and measured on the record (SP-D, SP_D_HANDOFF.md
section 37.4). The owner, 2026-10-16: "the patterns, like the flag pattern, or double ceiling ... some useful
info can be found at learning.emofid.com" and "gold started a side channel, then hit the ema and rose up ...
the system should be able to identify such moves technically".

Why a new reader: caluclator/chartist.py confirms a swing at 3 x ATR(14) (3-15% of the price), which on
18K's ~2% ATR is 6% and more. It has found no swing since the 15.65M low of 2026-06-16, so the September
range (23.0-24.6M), its test of the 20-day average and the breakout of 09-28 are invisible to it.

Rules, fixed before the measurement:
- Swings: a ZigZag on closes confirmed when the price turns by MINOR (3%) from the extreme. Causal: a swing
  exists from the day it is confirmed.
- RANGE: at least RANGE_MIN_DAYS (8) consecutive trading days whose closes stay within RANGE_MAX (6%) of each
  other, after a move of 8% or more into it. Its top and bottom are the highest and lowest close.
- EMA TEST: inside an uptrend (EMA20 above EMA50, both rising over 5 days), a day whose low comes within
  1% of the EMA20 (or under it) and whose close stays above it.
- BREAKOUT / BREAKDOWN of a range: the first close beyond its top (bottom) by 0.5%. Target: the range's
  height added (subtracted) from the edge (Emofid's measured move for the rectangle).
- FLAG: a pole of +8% or more within 15 days, then a range (as above) of at most half the pole's height;
  the breakout's target is the pole's height from the breakout.
- DOUBLE TOP (BOTTOM): two swing highs (lows) within 2% of each other with a swing low (high) between them at
  least 3% away; confirmed on the first close beyond that middle swing (the neckline). Target: the height.
- TRIPLE TOP (BOTTOM): three such highs (lows).
- HEAD AND SHOULDERS (and inverse): three swing highs, the middle one at least 2% above both shoulders, the
  shoulders within 3% of each other; the neckline through the two lows between them; confirmed on a close
  through the neckline. Target: the head's height from the neckline.
- TRIANGLE: the last two swing highs and lows converging -- highs falling and lows rising (symmetrical),
  highs flat within 1% and lows rising (ascending), highs falling and lows flat (descending); confirmed on a
  close beyond the line through the last two highs (up) or lows (down). Target: the triangle's first height.
- WEDGE: highs and lows both rising (rising wedge) or both falling (falling wedge), converging; confirmed on
  a close through the lower line (rising wedge, down) or the upper line (falling wedge, up).
- Outcome of each confirmed pattern, counted once per pattern (episodes): the close 20 trading days later
  against the confirmation close, against all days of the same era (2014-2020, 2021-2026); and whether the
  target was reached before the pattern's invalidation (the other side of the range, the head, the last
  swing) within 40 trading days.
"""

import os
import pickle
import sys
from collections import defaultdict

import numpy as np
import talib

HERE = os.path.dirname(os.path.abspath(__file__))
MINOR = 0.03
RANGE_MIN_DAYS, RANGE_MAX = 8, 0.06
EMA_NEAR = 0.01
BREAK = 0.005
HORIZON, TARGET_DAYS = 20, 40


def zigzag(c, thr=MINOR):
    """[(confirmed_on, pivot_day, price, 'H'|'L')] on closes, causal."""
    out, state, ext = [], None, 0
    for i in range(1, len(c)):
        if state is None:
            if c[i] >= c[0] * (1 + thr):
                state, ext = "up", i
                out.append((i, 0, c[0], "L"))
            elif c[i] <= c[0] * (1 - thr):
                state, ext = "down", i
                out.append((i, 0, c[0], "H"))
            continue
        if state == "up":
            if c[i] > c[ext]:
                ext = i
            elif c[i] <= c[ext] * (1 - thr):
                out.append((i, ext, c[ext], "H")); state, ext = "down", i
        else:
            if c[i] < c[ext]:
                ext = i
            elif c[i] >= c[ext] * (1 + thr):
                out.append((i, ext, c[ext], "L")); state, ext = "up", i
    return out


def ranges(c):
    """Ranges: (start, end, low, high) -- maximal runs of >= RANGE_MIN_DAYS closes within RANGE_MAX, entered
    after a move of 8%; `end` is the last day inside. Causal use: a range is known from start+RANGE_MIN_DAYS-1."""
    out, i, n = [], 0, len(c)
    while i < n - RANGE_MIN_DAYS:
        j = i
        lo = hi = c[i]
        while j + 1 < n and max(hi, c[j + 1]) / min(lo, c[j + 1]) - 1 <= RANGE_MAX:
            j += 1
            lo, hi = min(lo, c[j]), max(hi, c[j])
        if j - i + 1 >= RANGE_MIN_DAYS:
            before = c[max(0, i - 20):i + 1]
            move = c[i] / before.min() - 1 if len(before) else 0
            drop = c[i] / before.max() - 1 if len(before) else 0
            if move >= 0.08 or drop <= -0.08:
                out.append((i, j, lo, hi, "up" if move >= 0.08 else "down"))
            i = j + 1
        else:
            i += 1
    return out


def breaks(c, rngs):
    """Range breakouts/breakdowns: [(day, kind, level, target, stop, range)]. A range that turns out to be
    a flag (pole of 8%+ in 15 days, range at most half the pole) gets the pole's height as its target."""
    out = []
    for (s, e, lo, hi, into) in rngs:
        height = hi - lo
        k = e + 1
        if k >= len(c):
            continue
        pole_lo = c[max(0, s - 15):s + 1].min()
        pole = c[s] - pole_lo
        flag = into == "up" and pole >= 0.08 * pole_lo and height <= 0.5 * pole
        if c[k] >= hi * (1 + BREAK):
            out.append((k, "FLAG" if flag else "RANGE BREAKOUT", hi, hi + (pole if flag else height), lo, (s, e, lo, hi)))
        elif c[k] <= lo * (1 - BREAK):
            out.append((k, "RANGE BREAKDOWN", lo, lo - height, hi, (s, e, lo, hi)))
    return out


def ema_tests(h, l, c):
    e20, e50 = talib.EMA(c, 20), talib.EMA(c, 50)
    out, last = [], -10
    for i in range(55, len(c)):
        up = e20[i] > e50[i] and e20[i] > e20[i - 5] and e50[i] > e50[i - 5]
        if up and l[i] <= e20[i] * (1 + EMA_NEAR) and c[i] > e20[i] and i - last > 5:
            out.append((i, "EMA20 TEST", e20[i], None, e20[i] * 0.97, None))
            last = i
    return out


def swing_patterns(c, sw):
    """Double/triple tops and bottoms, head and shoulders, triangles, wedges on the swings known each day;
    each confirmed at the first close through its neckline/line. [(day, kind, level, target, stop, pivots)]."""
    out, seen = [], set()
    for idx in range(4, len(sw)):
        known = sw[:idx + 1]
        highs = [s for s in known if s[3] == "H"][-3:]
        lows = [s for s in known if s[3] == "L"][-3:]
        conf = known[-1][0]
        cands = []
        if len(highs) >= 2 and len(lows) >= 1:
            h1, h2 = highs[-2], highs[-1]
            mid = [s for s in lows if h1[1] < s[1] < h2[1]]
            if mid and abs(h2[2] / h1[2] - 1) <= 0.02 and min(h1[2], h2[2]) / mid[-1][2] - 1 >= 0.03:
                neck = mid[-1][2]
                cands.append(("DOUBLE TOP", neck, neck - (max(h1[2], h2[2]) - neck), max(h1[2], h2[2]), "down", (h1, mid[-1], h2)))
        if len(lows) >= 2 and len(highs) >= 1:
            l1, l2 = lows[-2], lows[-1]
            mid = [s for s in highs if l1[1] < s[1] < l2[1]]
            if mid and abs(l2[2] / l1[2] - 1) <= 0.02 and mid[-1][2] / max(l1[2], l2[2]) - 1 >= 0.03:
                neck = mid[-1][2]
                cands.append(("DOUBLE BOTTOM", neck, neck + (neck - min(l1[2], l2[2])), min(l1[2], l2[2]), "up", (l1, mid[-1], l2)))
        if len(highs) == 3 and len(lows) >= 2:
            a, b, d_ = highs
            between = [s for s in lows if a[1] < s[1] < d_[1]][-2:]
            if len(between) == 2:
                neck = min(x[2] for x in between)
                if b[2] >= 1.02 * max(a[2], d_[2]) and abs(a[2] / d_[2] - 1) <= 0.03:
                    cands.append(("HEAD AND SHOULDERS", neck, neck - (b[2] - neck), b[2], "down", (a, b, d_)))
                elif max(a[2], b[2], d_[2]) / min(a[2], b[2], d_[2]) - 1 <= 0.02:
                    cands.append(("TRIPLE TOP", neck, neck - (max(a[2], b[2], d_[2]) - neck), max(a[2], b[2], d_[2]), "down", (a, b, d_)))
        if len(lows) == 3 and len(highs) >= 2:
            a, b, d_ = lows
            between = [s for s in highs if a[1] < s[1] < d_[1]][-2:]
            if len(between) == 2:
                neck = max(x[2] for x in between)
                if b[2] <= 0.98 * min(a[2], d_[2]) and abs(a[2] / d_[2] - 1) <= 0.03:
                    cands.append(("INVERSE HEAD AND SHOULDERS", neck, neck + (neck - b[2]), b[2], "up", (a, b, d_)))
                elif max(a[2], b[2], d_[2]) / min(a[2], b[2], d_[2]) - 1 <= 0.02:
                    cands.append(("TRIPLE BOTTOM", neck, neck + (neck - min(a[2], b[2], d_[2])), min(a[2], b[2], d_[2]), "up", (a, b, d_)))
        if len(highs) >= 2 and len(lows) >= 2:
            (ha, hb), (la, lb) = highs[-2:], lows[-2:]
            hs, ls = hb[2] / ha[2] - 1, lb[2] / la[2] - 1
            height = max(ha[2], hb[2]) - min(la[2], lb[2])
            if hs < -0.01 and ls > 0.01:
                cands.append(("SYMMETRICAL TRIANGLE", None, height, None, "either", (ha, hb, la, lb)))
            elif abs(hs) <= 0.01 and ls > 0.01:
                cands.append(("ASCENDING TRIANGLE", None, height, None, "either", (ha, hb, la, lb)))
            elif hs < -0.01 and abs(ls) <= 0.01:
                cands.append(("DESCENDING TRIANGLE", None, height, None, "either", (ha, hb, la, lb)))
            elif hs > 0.01 and ls > 0.01 and ls > hs:
                cands.append(("RISING WEDGE", None, height, None, "down", (ha, hb, la, lb)))
            elif hs < -0.01 and ls < -0.01 and ls > hs:
                cands.append(("FALLING WEDGE", None, height, None, "up", (ha, hb, la, lb)))
        for kind, level, target, stop, side, piv in cands:
            key = (kind, tuple(p[1] for p in piv))
            if key in seen:
                continue
            seen.add(key)
            last_pivot = max(p[1] for p in piv)
            for k in range(conf, min(len(c), conf + 30)):
                if level is not None:
                    hit = (side == "down" and c[k] < level * (1 - BREAK)) or (side == "up" and c[k] > level * (1 + BREAK))
                    if hit:
                        out.append((k, kind, level, target, stop, piv)); break
                else:                                   # lines through the last two highs / lows
                    ha, hb, la, lb = piv
                    up_line = ha[2] + (hb[2] - ha[2]) * (k - ha[1]) / (hb[1] - ha[1])
                    lo_line = la[2] + (lb[2] - la[2]) * (k - la[1]) / (lb[1] - la[1])
                    height = target
                    if side in ("up", "either") and c[k] > up_line * (1 + BREAK):
                        out.append((k, kind + " (up)", up_line, up_line + height, lo_line, piv)); break
                    if side in ("down", "either") and c[k] < lo_line * (1 - BREAK):
                        out.append((k, kind + " (down)", lo_line, lo_line - height, up_line, piv)); break
                    if lo_line >= up_line:
                        break
    return out


def measure(c, d, events):
    fwd = np.full(len(c), np.nan)
    fwd[:-HORIZON] = (c[HORIZON:] / c[:-HORIZON] - 1) * 100
    base = {era: np.nanmedian([fwd[i] for i in range(len(c)) if era_of(d[i]) == era]) for era in ("2014-2020", "2021-2026")}
    table = defaultdict(lambda: defaultdict(list))
    for (k, kind, level, target, stop, _) in events:
        if d[k].year < 2014 or not np.isfinite(fwd[k]):
            continue
        reached = None
        if target is not None and stop is not None:
            up = target > c[k]
            reached = False
            for j in range(k + 1, min(len(c), k + TARGET_DAYS + 1)):
                if (up and c[j] >= target) or (not up and c[j] <= target):
                    reached = True; break
                if (up and c[j] <= stop) or (not up and c[j] >= stop):
                    break
        table[kind][era_of(d[k])].append((fwd[k], reached))
    return base, table


def era_of(day):
    return "2014-2020" if day.year <= 2020 else "2021-2026"


def main(pickle_path):
    G = pickle.load(open(pickle_path, "rb"))["gold"]
    d, h, l, c = G[0], np.array(G[1], float), np.array(G[2], float), np.array(G[3], float)
    sw = zigzag(c)
    rngs = ranges(c)
    events = breaks(c, rngs) + ema_tests(h, l, c) + swing_patterns(c, sw)
    base, table = measure(c, d, events)
    print(f"swings {len(sw)}, ranges {len(rngs)}, events {len(events)}; all days, next 20 trading days: "
          f"2014-2020 median {base['2014-2020']:+.2f}%, 2021-2026 {base['2021-2026']:+.2f}%")
    for kind in sorted(table):
        parts = []
        for era in ("2014-2020", "2021-2026"):
            rows = table[kind][era]
            if not rows:
                parts.append(f"{era}: none"); continue
            mv = np.array([r[0] for r in rows]); rc = [r[1] for r in rows if r[1] is not None]
            parts.append(f"{era}: n={len(rows):>3} next 20d {np.median(mv):+6.2f}% (vs {base[era]:+.2f}), higher {np.mean(mv > 0):.0%}"
                         + (f", target before stop {np.mean(rc):.0%} of {len(rc)}" if rc else ""))
        print(f"{kind:<34} " + " | ".join(parts))
    print("\nlast 120 days:")
    for (k, kind, level, target, stop, _) in sorted(events, key=lambda e: e[0]):
        if k >= len(c) - 120:
            print(f"   {d[k]} {kind:<30} level {level/1e7:6.2f}M" + (f" target {target/1e7:6.2f}M" if target else "")
                  + (f" stop {stop/1e7:6.2f}M" if stop else ""))
    print("ranges in the last 120 days:", [(str(d[s]), str(d[e]), round(lo / 1e7, 2), round(hi / 1e7, 2)) for s, e, lo, hi, _ in rngs if e >= len(c) - 120])
    return d, h, l, c, sw, rngs, events


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(HERE, "..", "src"))
    main(sys.argv[1])
