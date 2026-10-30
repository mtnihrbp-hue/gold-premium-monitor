"""Why E-2 lost (SP_D_HANDOFF.md section 74.6): each half-in-fixed-income window of the registered policy at
WallGold's fee, model X, with the parameters it chose, and what 18K and fixed income did inside it, and in the
20 days after the way back. Diagnostic, not a test.

    python research/rd_engine_trades.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rd_engine_policy as e2  # noqa: E402


def main():
    data = e2.load("X")
    d, g, fi, teth, pred, rv5 = data
    chosen = {y: e2.choose(data, y, 0.005)[0] for y in range(2018, 2027)}
    trades = []
    # replay the state machine and keep each window
    for name, a, b in e2.PERIODS:
        idx = [i for i in range(len(d)) if a <= d[i] <= b and fi[i]]
        state, entry, sigma, pending = "gold", None, None, None
        for n, i in enumerate(idx):
            if pending == "enter":
                state, entry = "half", i
            elif pending == "exit":
                trades.append((entry, i, reason))
                state, entry = "gold", None
            pending = None
            q, k, m = chosen[d[i].year]
            if state == "gold":
                if pred[i] is None or i < 60:
                    continue
                past = [pred[j] for j in range(max(0, i - e2.LOOKBACK), i) if pred[j] is not None]
                if len(past) < 250:
                    continue
                threshold = sorted(past)[int(q * (len(past) - 1))]
                if pred[i] <= threshold and math.log(g[i] / g[i - 60]) <= m:
                    pending, sigma = "enter", math.exp(pred[i])
            else:
                days = i - entry
                if days < 3:
                    continue
                up = math.log(g[i] / g[entry]) > k * sigma * math.sqrt(days)
                turb = rv5[i] is not None and math.exp(rv5[i]) > 2 * sigma
                tet = teth[i] and teth[i - 5] and teth[i] / teth[i - 5] - 1 > 0.03
                if up or turb or tet or days >= 40:
                    reason = "up break" if up else "turbulence" if turb else "Tether" if tet else "40 days"
                    pending = "exit"
    print(f"{'in':10} {'out':10} {'days':>4} {'why out':10} {'18K in':>7} {'FI in':>6} {'18K 20d after':>13}")
    lost = 0.0
    for e, x, why in trades:
        gr = g[x] / g[e] - 1
        fr = fi[x] / fi[e] - 1
        after = g[min(x + 20, len(g) - 1)] / g[x] - 1
        lost += 0.5 * (fr - gr)
        print(f"{d[e].isoformat():10} {d[x].isoformat():10} {x - e:4d} {why:10} {gr:+7.1%} {fr:+6.1%} {after:+13.1%}")
    print(f"\nhalf the savings inside the windows: fixed income minus 18K, summed, {lost:+.1%} (before fees)")


if __name__ == "__main__":
    main()
