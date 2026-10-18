"""The pattern reader: ranges, tests of the 20-day average, breakouts and the classic patterns, on 3% swings
(SP-D, SP_D_HANDOFF.md section 37.4). The owner, 2026-10-16: "the patterns, like the flag pattern, or double
ceiling" (learning.emofid.com's classic patterns) and "gold started a side channel, then hit the ema and rose
up ... the system should be able to identify such moves technically".

caluclator/chartist.py confirms swings at 3 x ATR(14), about 6% on 18K, and saw nothing of the September
range, its test of the 20-day or the breakout of 2026-09-28. This reader works on 3% swings; its rules are
research/rd_patterns.py's, unchanged, so their record on 18K (section 37.4, against a control) applies:
the flag reached its target before its stop 14 times in 19 since 2014, against about 45 in 100 from any day;
breakouts and double bottoms about as often as any day in the uptrend; the bearish patterns rarely followed
through. Calculators calculate: it reads prices and decides nothing.
"""

import numpy as np
import talib

MINOR = 0.03                       # a swing: a 3% turn on closes
RANGE_MIN_DAYS, RANGE_MAX = 8, 0.06
INTO_RANGE = 0.08                  # a range follows a move of 8% or more
EMA_NEAR = 0.01
BREAK = 0.005
FLAG_POLE, FLAG_POLE_DAYS = 0.08, 15
FLAG_RECORD = (14, 19, 45)         # reached first, flags since 2014, the control's rate in 100 (section 37.4)

# Each pattern's record on 18K, 2014-2026, from section 37.4: (patterns that reached their target before their
# stop within 40 trading days, patterns counted, the same distances' rate from any day of the same era, in 100).
RECORD = {
    "FLAG": FLAG_RECORD,
    "RANGE BREAKOUT": (30, 39, 70),
    "RANGE BREAKDOWN": (12, 22, 44),
    "DOUBLE BOTTOM": (19, 24, 69),
    "DOUBLE TOP": (3, 12, 33),
    "RISING WEDGE": (2, 41, 8),
    "FALLING WEDGE": (4, 17, 39),
}
SHOWN = 0.5        # a pattern is shown, on the chart and in the caption, when more than half of its past ones on
                   # 18K reached their target (owner, 2026-10-17: the rising wedge and the double top dropped)


def shown(kind):
    """True when the pattern is shown: the EMA20 test (after it the next month ran a little stronger, section
    37.4), and the recorded patterns that reached their target more than SHOWN of the time. Head and
    shoulders, the triangles and the triple tops and bottoms are found but not shown: 1-13 cases each on
    18K, too few to rate (section 37.4)."""
    base = kind.replace(" (up)", "").replace(" (down)", "")
    return base == "EMA20 TEST" or (base in RECORD and RECORD[base][0] / RECORD[base][1] > SHOWN)


POINTS = {"FLAG": "up", "RANGE BREAKOUT": "up", "DOUBLE BOTTOM": "up", "FALLING WEDGE": "up",
          "RANGE BREAKDOWN": "down", "DOUBLE TOP": "down", "RISING WEDGE": "down"}   # where the textbooks say it goes
NAMES = {"EMA20 TEST": "EMA20 test", "FLAG": "flag breakout", "RANGE BREAKOUT": "range breakout",
         "RANGE BREAKDOWN": "range breakdown"}


def name(kind):
    """The plain name for a reader: no direction words, which would read as a forecast the record does not
    support (section 37.4)."""
    base = kind.replace(" (up)", "").replace(" (down)", "")
    return NAMES.get(base, base.lower())


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
                out.append((i, ext, c[ext], "H"))
                state, ext = "down", i
        else:
            if c[i] < c[ext]:
                ext = i
            elif c[i] >= c[ext] * (1 + thr):
                out.append((i, ext, c[ext], "L"))
                state, ext = "up", i
    return out


def ranges(c):
    """[(start, end, low, high, 'up'|'down')]: maximal runs of RANGE_MIN_DAYS or more closes within RANGE_MAX of
    each other, entered after a move of INTO_RANGE; low and high are the run's lowest and highest close."""
    out, i, n = [], 0, len(c)
    while i < n - RANGE_MIN_DAYS:
        j, lo, hi = i, c[i], c[i]
        while j + 1 < n and max(hi, c[j + 1]) / min(lo, c[j + 1]) - 1 <= RANGE_MAX:
            j += 1
            lo, hi = min(lo, c[j]), max(hi, c[j])
        if j - i + 1 >= RANGE_MIN_DAYS:
            before = c[max(0, i - 20):i + 1]
            move, drop = c[i] / before.min() - 1, c[i] / before.max() - 1
            if move >= INTO_RANGE or drop <= -INTO_RANGE:
                out.append((i, j, lo, hi, "up" if move >= INTO_RANGE else "down"))
            i = j + 1
        else:
            i += 1
    return out


def range_breaks(c, rngs):
    """[(day, kind, level, target, stop)] for the close that leaves each range: FLAG (a pole of FLAG_POLE within
    FLAG_POLE_DAYS, the range at most half the pole; target the pole's height), RANGE BREAKOUT and RANGE
    BREAKDOWN (target the range's height)."""
    out = []
    for (s, e, lo, hi, into) in rngs:
        k = e + 1
        if k >= len(c):
            continue
        height = hi - lo
        pole_lo = c[max(0, s - FLAG_POLE_DAYS):s + 1].min()
        pole = c[s] - pole_lo
        flag = into == "up" and pole >= FLAG_POLE * pole_lo and height <= 0.5 * pole
        if c[k] >= hi * (1 + BREAK):
            out.append((k, "FLAG" if flag else "RANGE BREAKOUT", hi, hi + (pole if flag else height), lo))
        elif c[k] <= lo * (1 - BREAK):
            out.append((k, "RANGE BREAKDOWN", lo, lo - height, hi))
    return out


def ema_tests(h, l, c):
    """[(day, 'EMA20 TEST', ema20, None, stop)]: in an uptrend (EMA20 above EMA50, both rising over 5 days), a
    low within EMA_NEAR of the 20-day and a close above it; at most one in 5 days."""
    e20, e50 = talib.EMA(c, 20), talib.EMA(c, 50)
    out, last = [], -10
    for i in range(55, len(c)):
        up = e20[i] > e50[i] and e20[i] > e20[i - 5] and e50[i] > e50[i - 5]
        if up and l[i] <= e20[i] * (1 + EMA_NEAR) and c[i] > e20[i] and i - last > 5:
            out.append((i, "EMA20 TEST", float(e20[i]), None, float(e20[i] * 0.97)))
            last = i
    return out


def swing_patterns(c, sw):
    """Double and triple tops and bottoms, head and shoulders (and inverse), triangles and wedges on the swings
    known each day, each at its first close through its neckline or line: [(day, kind, level, target, stop)]."""
    out, seen = [], set()
    for idx in range(4, len(sw)):
        known = sw[:idx + 1]
        highs = [s for s in known if s[3] == "H"][-3:]
        lows = [s for s in known if s[3] == "L"][-3:]
        conf = known[-1][0]
        cands = []
        if len(highs) >= 2 and lows:
            h1, h2 = highs[-2], highs[-1]
            mid = [s for s in lows if h1[1] < s[1] < h2[1]]
            if mid and abs(h2[2] / h1[2] - 1) <= 0.02 and min(h1[2], h2[2]) / mid[-1][2] - 1 >= 0.03:
                neck = mid[-1][2]
                cands.append(("DOUBLE TOP", neck, neck - (max(h1[2], h2[2]) - neck), max(h1[2], h2[2]), "down", (h1, mid[-1], h2)))
        if len(lows) >= 2 and highs:
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
            for k in range(conf, min(len(c), conf + 30)):
                if level is not None:
                    if (side == "down" and c[k] < level * (1 - BREAK)) or (side == "up" and c[k] > level * (1 + BREAK)):
                        out.append((k, kind, level, target, stop))
                        break
                else:
                    ha, hb, la, lb = piv
                    up_line = ha[2] + (hb[2] - ha[2]) * (k - ha[1]) / (hb[1] - ha[1])
                    lo_line = la[2] + (lb[2] - la[2]) * (k - la[1]) / (lb[1] - la[1])
                    if side in ("up", "either") and c[k] > up_line * (1 + BREAK):
                        out.append((k, kind + " (up)", up_line, up_line + target, lo_line))
                        break
                    if side in ("down", "either") and c[k] < lo_line * (1 - BREAK):
                        out.append((k, kind + " (down)", lo_line, lo_line - target, up_line))
                        break
                    if lo_line >= up_line:
                        break
    return out


def read(dates, high, low, close, window=60):
    """What the chart shows now, on completed candles: {"ranges": the last two [(start date, end date, low,
    high)], the last one running to today when it has not been left; "events": [(date, kind, level, target,
    stop)] of the last `window` days; "flag": the latest flag whose target is not reached and whose stop is
    not broken, or None; "tests": the dates of the EMA20 tests inside the current range}."""
    h, l, c = (np.asarray(x, dtype=float) for x in (high, low, close))
    n = len(c)
    if n < 60:
        return {"ranges": [], "events": [], "flag": None, "tests": []}
    rngs = ranges(c)
    events = sorted(range_breaks(c, rngs) + ema_tests(h, l, c) + swing_patterns(c, zigzag(c)), key=lambda e: e[0])
    last_two = rngs[-2:]
    shown = []
    for s, e, lo, hi, _ in last_two:
        running = e == n - 1
        shown.append((dates[s], dates[e], float(lo), float(hi), running))
    flag = None
    for (k, kind, level, target, stop) in reversed(events):
        if kind == "FLAG":
            after = c[k + 1:]
            if not len(after) or (after.max() < target and after.min() > stop):
                flag = (dates[k], float(level), float(target), float(stop))
            break
    current = rngs[-1] if rngs and rngs[-1][1] == n - 1 else None
    tests = [dates[k] for (k, kind, *_r) in events if kind == "EMA20 TEST" and current and k >= current[0]]
    recent = [(dates[k], kind, float(level), None if target is None else float(target), float(stop))
              for (k, kind, level, target, stop) in events if k >= n - window]
    return {"ranges": shown, "events": recent, "flag": flag, "tests": tests}
