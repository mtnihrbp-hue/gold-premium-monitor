"""Frozen platform quotes in the stored record (SP-D, SP_D_HANDOFF.md section 32). Read-only.

On 2026-10-06/07 Taline was stored at 267,410,000 for five hours while the others moved,
then alternated between that value and 266,850,000 the next morning; HoorGold sat at
267,990,000 for seventeen hours. Both passed every rule of validation/data.py: a frozen
copy inside a platform's usual 1 pp is not deferred by the repeat rule.

For each platform, over production's stored readings (scheduled and user, oldest first):

  hold      a run of identical prices spanning 3 hours or more inside one Tehran day
            (06:00-21:00), with the other platforms' median moving by MOVE_PP or more over
            the same span -- the price stood still while the market did not
  return    a price equal to one the platform left earlier (A, then B, then A again within
            RETURN_DAYS) -- a cache handing back an older copy

Each count is set against the platform's readings, and against the same counts for the
platforms the record has no reason to suspect, so a platform that is merely slow to
reprice is told apart from one served a copy.

Connection: ~/.gpm_neon_url (PROJECT_OPERATIONS.md section 15), opened read-only.
"""
import os
import sys
from collections import defaultdict
from datetime import timedelta
from statistics import median

import psycopg2

sys.stdout.reconfigure(encoding="utf-8")

HOLD_HOURS = 3
MOVE_PP = 0.3          # about the others' median move over 3 hours on an ordinary day (printed below)
RETURN_DAYS = 3
TEHRAN = timedelta(hours=3, minutes=30)

conn = psycopg2.connect(open(os.path.expanduser("~/.gpm_neon_url")).read().strip(), connect_timeout=15)
conn.set_session(readonly=True)
cur = conn.cursor()
cur.execute("""SELECT ms.timestamp, pp.platform_name, pp.price_irr
               FROM platform_prices pp JOIN market_snapshots ms ON ms.id = pp.snapshot_id
               WHERE ms.timestamp >= '2026-09-14' AND pp.price_irr IS NOT NULL
               ORDER BY ms.timestamp""")
rows = [(t, name, float(p)) for t, name, p in cur.fetchall()]
conn.close()

by_time = defaultdict(dict)
for t, name, p in rows:
    by_time[t][name] = p
times = sorted(by_time)
series = defaultdict(list)
for t in times:
    for name, p in by_time[t].items():
        series[name].append((t, p))


def others_median(t, name):
    vals = [p for n, p in by_time[t].items() if n != name]
    return median(vals) if len(vals) >= 3 else None


# The yardstick: how far the median of all platforms moves over 3 hours inside a day.
moves = []
for i, t in enumerate(times):
    local = t + TEHRAN
    for u in times[i + 1:]:
        if (u - t) >= timedelta(hours=HOLD_HOURS):
            if (u + TEHRAN).date() == local.date():
                a, b = median(by_time[t].values()), median(by_time[u].values())
                moves.append(abs(b / a - 1) * 100)
            break
moves.sort()
print(f"readings {len(times)} from {times[0] + TEHRAN:%m-%d %H:%M} to {times[-1] + TEHRAN:%m-%d %H:%M} Tehran")
print(f"the market's own move over {HOLD_HOURS} h inside a day: median {moves[len(moves) // 2]:.2f} pp, "
      f"75th pct {moves[int(len(moves) * .75)]:.2f} pp (n={len(moves)})\n")

print(f"{'platform':10} {'readings':>8} {'holds':>6} {'in holds':>9} {'share':>6} {'returns':>8} {'share':>6}  longest hold")
examples = {}
for name in sorted(series):
    s = series[name]
    holds, held_readings, longest = 0, 0, (timedelta(0), None)
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1][1] == s[i][1] and (s[j + 1][0] + TEHRAN).date() == (s[i][0] + TEHRAN).date():
            j += 1
        span = s[j][0] - s[i][0]
        if span >= timedelta(hours=HOLD_HOURS):
            m0, m1 = others_median(s[i][0], name), others_median(s[j][0], name)
            if m0 and m1 and abs(m1 / m0 - 1) * 100 >= MOVE_PP:
                holds += 1
                held_readings += j - i + 1
                if span > longest[0]:
                    longest = (span, s[i][0], s[i][1], abs(m1 / m0 - 1) * 100)
        i = j + 1
    returns = 0
    for k in range(2, len(s)):
        t, p = s[k]
        if p == s[k - 1][1]:
            continue
        earlier = [q for (u, q) in s[:k - 1] if t - u <= timedelta(days=RETURN_DAYS)]
        if p in earlier and s[k - 1][1] != p:
            returns += 1
    n = len(s)
    lh = (f"{longest[0].total_seconds() / 3600:.1f} h at {longest[2]:,.0f} from {longest[1] + TEHRAN:%m-%d %H:%M}"
          f" (others {longest[3]:.2f} pp)" if longest[1] else "-")
    print(f"{name:10} {n:8} {holds:6} {held_readings:9} {held_readings / n:6.1%} {returns:8} {returns / n:6.1%}  {lh}")
