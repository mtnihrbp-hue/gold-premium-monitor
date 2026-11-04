"""SP-Ea, C2: each platform measured on the full record (SP_D_HANDOFF.md sections 63.3 and 96), the measures of
63.3 on every scheduled reading stored from 2026-08-04 on (and those of before 09-14, whose mode was not yet recorded), the outage's written-back readings included:
- coverage: the share of readings with the platform's price;
- offset: its typical distance from the other platforms' median (the median of price / median - 1);
- noise: the spread of that offset, as a robust standard deviation (1.4826 x the median absolute deviation);
- frozen: the share of readings where its price did not change from its previous reading while the others' median
  moved more than 0.10%; and the longest such run;
- jumps: changes of the offset larger than 1 point between its consecutive readings.
Read-only against production; prints a table, the earlier half and the later half beside each other.

    python research/rd_platforms_record.py
"""

import os
import statistics as st
from collections import defaultdict

import psycopg2

SPLIT = "2026-10-05"                     # 63.3 measured to 10-04: the later half is what it has not seen


def load():
    url = os.environ.get("DATABASE_URL") or open(os.path.expanduser("~/.gpm_neon_url")).read().strip()
    c = psycopg2.connect(url)
    c.set_session(readonly=True)
    q = c.cursor()
    q.execute("""select s.id, s.timestamp, p.platform_name, p.price_irr from market_snapshots s
                 join platform_prices p on p.snapshot_id = s.id
                 where s.collection_mode in ('scheduled', 'unknown') and s.timestamp >= '2026-08-04'
                 order by s.timestamp""")    # 'unknown': the readings before the mode was recorded (SP-C.1), as 63.3 had them
    readings = defaultdict(dict)
    times = {}
    for sid, ts, name, price in q.fetchall():
        readings[sid][name] = float(price)
        times[sid] = ts
    return [(times[k], readings[k]) for k in sorted(readings, key=times.get)]


def measure(rows):
    names = sorted({n for _, r in rows for n in r})
    out = {}
    for n in names:
        offsets, frozen, run, longest, jumps, have = [], 0, 0, 0, 0, 0
        prev = None                                          # (price, others' median, offset) at its last reading
        for _, r in rows:
            others = [v for k, v in r.items() if k != n]
            if n not in r or len(others) < 3:
                continue
            have += 1
            med = st.median(others)
            off = r[n] / med - 1
            offsets.append(off)
            if prev is not None:
                still = r[n] == prev[0] and abs(med / prev[1] - 1) > 0.001
                frozen += still
                run = run + 1 if still else 0
                longest = max(longest, run)
                jumps += abs(off - prev[2]) > 0.01
            prev = (r[n], med, off)
        total = sum(1 for _, r in rows if len(r) >= 4)
        if not offsets:
            continue
        mid = st.median(offsets)
        noise = 1.4826 * st.median(abs(o - mid) for o in offsets)
        out[n] = {"coverage": have / total, "offset": mid, "noise": noise, "frozen": frozen / max(have - 1, 1),
                  "longest": longest, "jumps": jumps, "n": have}
    return out


def main():
    rows = load()
    halves = {"to 10-04": [x for x in rows if x[0].isoformat() < SPLIT], "from 10-05": [x for x in rows if x[0].isoformat() >= SPLIT]}
    print(f"scheduled readings: {len(rows)} ({rows[0][0]:%Y-%m-%d} to {rows[-1][0]:%Y-%m-%d}); "
          + ", ".join(f"{k}: {len(v)}" for k, v in halves.items()))
    full, parts = measure(rows), {k: measure(v) for k, v in halves.items()}
    print(f"{'platform':10} {'coverage':>9} {'offset':>8} {'noise':>7} {'frozen':>7} {'longest':>8} {'jumps':>6} |"
          f" {'frozen to 10-04':>15} {'from 10-05':>11} | {'coverage from 10-05':>19}")
    for n, m in sorted(full.items(), key=lambda kv: (kv[1]["frozen"], kv[1]["noise"])):
        a, b = parts["to 10-04"].get(n, {}), parts["from 10-05"].get(n, {})
        print(f"{n:10} {m['coverage']:9.0%} {m['offset']:+8.2%} {100 * m['noise']:6.2f}pp {m['frozen']:7.0%} {m['longest']:8d}"
              f" {m['jumps']:6d} | {a.get('frozen', float('nan')):15.0%} {b.get('frozen', float('nan')):11.0%} |"
              f" {b.get('coverage', float('nan')):19.0%}")


if __name__ == "__main__":
    main()
