"""The control for rd_patterns.py's target rates (SP-D, SP_D_HANDOFF.md section 37.4).

18K rose about 40-fold since 2014, so an upside target is often reached from any day. For every pattern with
a target and a stop, the same two distances (as percentages of the confirmation close) are tried from every
day of the same era; the control rate is the share of days on which the target came before the stop within
40 trading days. The pattern's edge is its own rate minus the control's, per era.
"""
import os
import sys
from collections import defaultdict

import numpy as np

import rd_patterns as P


def hit(c, k, up_pct, down_pct, days=P.TARGET_DAYS):
    up, dn = c[k] * (1 + up_pct), c[k] * (1 - down_pct)
    for j in range(k + 1, min(len(c), k + days + 1)):
        if c[j] >= up:
            return True
        if c[j] <= dn:
            return False
    return False


def main(pickle_path):
    d, h, l, c, sw, rngs, events = P.main(pickle_path)
    days = {era: [i for i in range(len(c) - P.TARGET_DAYS) if d[i].year >= 2014 and P.era_of(d[i]) == era]
            for era in ("2014-2020", "2021-2026")}
    rows = defaultdict(lambda: defaultdict(list))
    for (k, kind, level, target, stop, _) in events:
        if target is None or stop is None or d[k].year < 2014 or k + P.TARGET_DAYS >= len(c):
            continue
        up = target > c[k]
        t_pct, s_pct = abs(target / c[k] - 1), abs(stop / c[k] - 1)
        if not up:                      # a downside target: mirror the control (target below, stop above)
            own = any(c[j] <= target for j in range(k + 1, k + P.TARGET_DAYS + 1)
                      if not any(c[x] >= stop for x in range(k + 1, j + 1)))
            ctrl = np.mean([not hit(c, i, s_pct, t_pct) and any(c[j] <= c[i] * (1 - t_pct) for j in range(i + 1, i + P.TARGET_DAYS + 1))
                            for i in days[P.era_of(d[k])][::5]])
        else:
            own = hit(c, k, t_pct, s_pct)
            ctrl = np.mean([hit(c, i, t_pct, s_pct) for i in days[P.era_of(d[k])][::5]])
        rows[kind][P.era_of(d[k])].append((own, ctrl))
    print("\nTARGET BEFORE STOP, against the same distances from every 5th day of the era (the control):")
    for kind in sorted(rows):
        parts = []
        for era in ("2014-2020", "2021-2026"):
            r = rows[kind][era]
            if not r:
                parts.append(f"{era}: none"); continue
            own = np.mean([x[0] for x in r]); ctrl = np.mean([x[1] for x in r])
            parts.append(f"{era}: n={len(r):>2} pattern {own:4.0%} control {ctrl:4.0%} edge {(own - ctrl) * 100:+4.0f} pp")
        print(f"{kind:<34} " + " | ".join(parts))


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(P.HERE, "..", "src"))
    main(sys.argv[1])
