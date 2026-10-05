"""The chartist: reads a daily chart the way a technical analyst does (SP-D, 2026-10-05).

The owner: "we are missing a chartist in the committee room, the one who can read charts,
identify trends, sideways and so on ... a system that can see channels, and technically
analyze the chart."

Everything here is causal: `read(i)` uses only closes up to day i, and a swing counts only
from the day it is confirmed (the price has turned by the swing threshold). What it reads:

  swings      a ZigZag whose threshold is K_ATR times the 14-day ATR (as a share of the
              price), bounded 3-15%: a swing in a calm year and in 1405 mean the same thing
  structure   Dow: the last two confirmed swing highs and lows -- UP (higher highs and higher
              lows), DOWN (lower highs and lower lows), CONTRACTING (lower highs, higher lows:
              a triangle), EXPANDING (higher highs, lower lows), RANGE otherwise
  strength    ADX(14), the 50-day EMA's slope over 10 days
  channel     a straight line through log prices since the start of the current leg (20-150
              days): its slope (% a day), R^2, and where today's close sits in it (0 bottom,
              1 top, beyond 2 standard deviations outside)
  box         a sideways market's support and resistance: the lowest of the last two swing
              lows and the highest of the last two swing highs
  patterns    breakout / breakdown from the box; Wyckoff's spring (a close below the box's
              support as it stood that day, back inside within 10 days) and upthrust (the mirror); a double top /
              bottom confirmed by the close through the trough / peak between; a squeeze
              (Bollinger width at its lowest of 120 days); divergence (a higher swing high with
              a lower RSI, or the mirror); a pullback inside an uptrend that kept above half the
              prior leg (a flag)
  phase       MARKUP (structure UP, close over EMA50), MARKDOWN (DOWN, under EMA50),
              ACCUMULATION (sideways after a fall), DISTRIBUTION (sideways after a rise),
              judged by the leg into the range; a breakout carried by a rising EMA50 is
              MARKUP before its swing confirms (a breakdown under a falling one, MARKDOWN)

The view: a textbook chartist's reading, fixed before any test -- each finding adds or takes
away from a score for gold, clipped to [-1, 1]:

  MARKUP +0.5, MARKDOWN -0.5, DISTRIBUTION -0.25, ACCUMULATION +0.25
  breakout +0.5, breakdown -0.5, spring +0.5, upthrust -0.5
  double bottom +0.25, double top -0.25, divergence (bull +0.25, bear -0.25), flag +0.25,
  bear trap +0.25, bull trap -0.25 (added after the first run, from the owner's 1405/03/25 case)
  in a rising channel at its bottom (position < 0.2) +0.25; in a falling channel at its top
  (position > 0.8) -0.25
"""
import numpy as np
import talib

K_ATR = 3.0
SWING_MIN, SWING_MAX = 0.03, 0.15
TOL = 0.005


class Chartist:
    def __init__(self, high, low, close, usable=None):
        self.c = np.asarray(close, dtype=float)
        self.h = np.asarray(high, dtype=float)
        self.l = np.asarray(low, dtype=float)
        n = len(self.c)
        self.n = n
        if usable is not None:
            self.h = np.where(usable, self.h, self.c)
            self.l = np.where(usable, self.l, self.c)
        atr = talib.ATR(self.h, self.l, self.c, timeperiod=14)
        self.thr = np.clip(np.nan_to_num(K_ATR * atr / self.c, nan=0.08), SWING_MIN, SWING_MAX)
        self.adx = talib.ADX(self.h, self.l, self.c, timeperiod=14)
        self.ema50 = talib.EMA(self.c, timeperiod=50)
        self.rsi = talib.RSI(self.c, timeperiod=14)
        up, mid, lo = talib.BBANDS(self.c, timeperiod=20, nbdevup=2, nbdevdn=2)
        self.bbw = (up - lo) / mid
        self.swings = self._zigzag()          # (confirmed_on, pivot_day, price, "H" | "L")
        self._confirm_days = [s[0] for s in self.swings]

    def _zigzag(self):
        c, thr = self.c, self.thr
        out, state, ext = [], "up", 0
        for i in range(1, self.n):
            if state == "up":
                if c[i] > c[ext]:
                    ext = i
                elif c[i] <= c[ext] * (1 - thr[i]):
                    out.append((i, ext, c[ext], "H"))
                    state, ext = "down", i
            else:
                if c[i] < c[ext]:
                    ext = i
                elif c[i] >= c[ext] * (1 + thr[i]):
                    out.append((i, ext, c[ext], "L"))
                    state, ext = "up", i
        return out

    def known(self, i):
        """Swings confirmed by day i."""
        k = np.searchsorted(self._confirm_days, i, side="right")
        return self.swings[:k]

    def _box(self, i):
        """The sideways box known on day i, or None when the structure is a trend."""
        sw = self.known(i)
        highs = [x[2] for x in sw if x[3] == "H"][-2:]
        lows = [x[2] for x in sw if x[3] == "L"][-2:]
        if len(highs) < 2 or len(lows) < 2:
            return None
        trend = (highs[1] > highs[0] * (1 + TOL) and lows[1] > lows[0] * (1 + TOL)) or                 (highs[1] < highs[0] * (1 - TOL) and lows[1] < lows[0] * (1 - TOL))
        return None if trend else (min(lows), max(highs))

    def read(self, i):
        c = self.c
        sw = self.known(i)
        highs = [s for s in sw if s[3] == "H"]
        lows = [s for s in sw if s[3] == "L"]
        r = {"structure": None, "phase": None, "patterns": [], "score": 0.0}
        if len(highs) < 2 or len(lows) < 2 or not np.isfinite(self.ema50[i]):
            return r
        h1, h2 = highs[-2][2], highs[-1][2]
        l1, l2 = lows[-2][2], lows[-1][2]
        hh, hl = h2 > h1 * (1 + TOL), l2 > l1 * (1 + TOL)
        lh, ll = h2 < h1 * (1 - TOL), l2 < l1 * (1 - TOL)
        structure = ("UP" if hh and hl else "DOWN" if lh and ll else "CONTRACTING" if lh and hl
                     else "EXPANDING" if hh and ll else "RANGE")
        # the live leg can overturn the last confirmed structure: a close beyond the last
        # swing high or low is a break of structure before the next swing is confirmed
        if c[i] > h2 * (1 + TOL) and structure != "UP":
            r["patterns"].append("breakout")
        if c[i] < l2 * (1 - TOL) and structure != "DOWN":
            r["patterns"].append("breakdown")
        r["structure"] = structure
        box_lo, box_hi = min(l1, l2), max(h1, h2)
        r["box"] = (box_lo, box_hi)
        sideways = structure in ("RANGE", "CONTRACTING", "EXPANDING")
        r["sideways"] = sideways

        # Wyckoff: in the last 10 days a close broke the box as it stood that day, and the
        # price is back inside it now (a spring under the support, an upthrust over the
        # resistance). The box of that day, not today's: the dip itself confirms a new swing
        # low and moves today's box down to it.
        for j in range(max(1, i - 10), i):
            bj = self._box(j)
            if bj is None:
                continue
            if c[j] < bj[0] * (1 - TOL) and c[i] > bj[0] and "spring" not in r["patterns"]:
                r["patterns"].append("spring")
            if c[j] > bj[1] * (1 + TOL) and c[i] < bj[1] and "upthrust" not in r["patterns"]:
                r["patterns"].append("upthrust")
        # the same failure in any structure: a close through the last swing low (high) known
        # that day, back on the other side within 10 days -- a bear trap (bull trap)
        for j in range(max(1, i - 10), i):
            sj = self.known(j)
            lo_j = [x[2] for x in sj if x[3] == "L"]
            hi_j = [x[2] for x in sj if x[3] == "H"]
            if lo_j and c[j] < lo_j[-1] * (1 - TOL) and c[i] > lo_j[-1] and "bear trap" not in r["patterns"]:
                r["patterns"].append("bear trap")
            if hi_j and c[j] > hi_j[-1] * (1 + TOL) and c[i] < hi_j[-1] and "bull trap" not in r["patterns"]:
                r["patterns"].append("bull trap")

        # double top / bottom: the last two highs (lows) within 2%, the price through the
        # trough (peak) between them
        if abs(h2 / h1 - 1) < 0.02:
            between = [s[2] for s in lows if highs[-2][1] < s[1] < highs[-1][1]]
            if between and c[i] < min(between):
                r["patterns"].append("double top")
        if abs(l2 / l1 - 1) < 0.02:
            between = [s[2] for s in highs if lows[-2][1] < s[1] < lows[-1][1]]
            if between and c[i] > max(between):
                r["patterns"].append("double bottom")

        # divergence at the last two swing highs / lows
        rs = self.rsi
        if hh and np.isfinite(rs[highs[-1][1]]) and np.isfinite(rs[highs[-2][1]]) and rs[highs[-1][1]] < rs[highs[-2][1]] - 2:
            r["patterns"].append("bearish divergence")
        if ll and np.isfinite(rs[lows[-1][1]]) and np.isfinite(rs[lows[-2][1]]) and rs[lows[-1][1]] > rs[lows[-2][1]] + 2:
            r["patterns"].append("bullish divergence")

        # squeeze: Bollinger width at its lowest in 120 days
        bw = self.bbw[max(0, i - 119):i + 1]
        if np.isfinite(self.bbw[i]) and np.isfinite(bw).sum() > 60 and self.bbw[i] <= np.nanmin(bw) * 1.0001:
            r["patterns"].append("squeeze")

        # a flag: in an uptrend, the last low kept above half of the leg before it
        if structure == "UP" and sw[-1][3] == "L" and len(sw) >= 3:
            leg_lo = [s for s in sw[:-1] if s[3] == "L"]
            if leg_lo:
                a, b = leg_lo[-1][2], highs[-1][2]
                if l2 > a + (b - a) * 0.5:
                    r["patterns"].append("flag")

        # the channel since the start of the current leg
        start = sw[-1][1] if sw else i - 60     # the current leg begins at the last confirmed swing
        start = int(np.clip(start, i - 150, i - 20))
        y = np.log(c[start:i + 1])
        x = np.arange(len(y))
        slope, icpt = np.polyfit(x, y, 1)
        fit = icpt + slope * x
        res = y - fit
        sd = res.std() if res.std() > 0 else 1e-9
        r["channel"] = {"slope_pct_day": slope * 100, "r2": 1 - res.var() / y.var() if y.var() > 0 else 0,
                        "position": float((res[-1] / (2 * sd) + 1) / 2), "days": len(y),
                        "low": float(np.exp(fit[-1] - 2 * sd)), "high": float(np.exp(fit[-1] + 2 * sd))}

        ema_up = c[i] > self.ema50[i]
        ema_rising = i >= 10 and self.ema50[i] > self.ema50[i - 10]
        if structure == "UP" and ema_up:
            phase = "MARKUP"
        elif structure == "DOWN" and not ema_up:
            phase = "MARKDOWN"
        elif sideways:
            # the leg into the range decides, as a chartist reads it: a range that began
            # with a high came after a rise (distribution), one that began with a low after
            # a fall (accumulation)
            phase = "DISTRIBUTION" if highs[-2][1] < lows[-2][1] else "ACCUMULATION"
        else:
            phase = "TRANSITION"
        # the live leg overrides the last confirmed swings: out of the box and carried by
        # a rising (falling) 50-day average is a markup (markdown) before its swing confirms
        if "breakout" in r["patterns"] and ema_up and ema_rising:
            phase = "MARKUP"
        elif "breakdown" in r["patterns"] and not ema_up and not ema_rising:
            phase = "MARKDOWN"
        r["phase"] = phase
        r["adx"] = float(self.adx[i]) if np.isfinite(self.adx[i]) else None
        r["ema50_slope_pct"] = float((self.ema50[i] / self.ema50[i - 10] - 1) * 100) if i >= 10 else None

        s = {"MARKUP": 0.5, "MARKDOWN": -0.5, "DISTRIBUTION": -0.25, "ACCUMULATION": 0.25}.get(phase, 0.0)
        s += sum({"breakout": 0.5, "breakdown": -0.5, "spring": 0.5, "upthrust": -0.5, "double bottom": 0.25,
                  "double top": -0.25, "bullish divergence": 0.25, "bearish divergence": -0.25,
                  "flag": 0.25, "bear trap": 0.25, "bull trap": -0.25}.get(p, 0.0) for p in r["patterns"])
        ch = r["channel"]
        if ch["slope_pct_day"] > 0.05 and ch["position"] < 0.2:
            s += 0.25
        if ch["slope_pct_day"] < -0.05 and ch["position"] > 0.8:
            s -= 0.25
        r["score"] = float(np.clip(s, -1, 1))
        return r


PHASE_WORDS = {"MARKUP": "rising (markup)", "MARKDOWN": "falling (markdown)", "ACCUMULATION": "sideways after a fall (accumulation)",
               "DISTRIBUTION": "sideways after a rise (distribution)", "TRANSITION": "between phases"}


def describe(ch, i, label, unit=1e7):
    """The reading in a few short lines, prices in M toman; `label(j)` names day j (a Persian date)."""
    r = ch.read(i)
    if not r["structure"]:
        return ["Chart: not enough swings yet."]
    c = ch.c
    sw = ch.known(i)
    last = sw[-1]
    leg = "up" if last[3] == "L" else "down"
    lines = [f"Chart: {PHASE_WORDS[r['phase']]}; the current leg is {leg} from the "
             f"{last[2] / unit:.2f}M {'low' if last[3] == 'L' else 'high'} of {label(last[1])}."]
    chn = r["channel"]
    where = "upper half" if chn["position"] > 0.5 else "lower half"
    if chn["position"] > 1:
        where = "above its top line"
    elif chn["position"] < 0:
        where = "below its bottom line"
    lines.append(f"Channel: {chn['slope_pct_day']:+.2f}% a day, {chn['low'] / unit:.2f}-{chn['high'] / unit:.2f}M today; "
                 f"the price is in its {where}.")
    if r.get("box"):
        lo, hi = r["box"]
        side = "above" if c[i] > hi else "below" if c[i] < lo else "inside"
        lines.append(f"Box of the last swings: {lo / unit:.2f}-{hi / unit:.2f}M; the price is {side} it.")
    if r["patterns"]:
        lines.append("Patterns: " + ", ".join(r["patterns"]) + ".")
    return lines
