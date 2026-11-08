"""The discount's basis on the record: the three lowest gram platforms, the WallGold index, or the gram median
(the owner, 2026-11-08; SP_D_HANDOFF.md sections 64.3 and 105).

Every scheduled reading with a fair price from `FROM` on, on the six gram platforms production still reads (Taline's
history left out, as it no longer is read):
- level: the discount each basis shows, and how far apart they sit;
- noise: the size of a reading-to-reading change, and the share of it that reverses at the next reading;
- stale exposure: the share of readings where a quote inside the basis did not move while the others' median moved;
- who sets it: each platform's share of the three lowest;
- the deep level: each basis's own, 85th percentile of its settled last 30 days, as `deep_discount_threshold`;
- what followed: tgju's 18K close 1, 3 and 7 days on, against the day's last reading of each basis.

Read-only against production. Saves what it read to `--cache` so a second look costs Neon nothing.

    python research/rd_discount_basis.py [--cache path.json]
"""

import json
import os
import statistics as st
import sys
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, "src")
from analysis.bubble_position import DEEP_DISCOUNT_PERCENTILE, _value_at_percentile  # noqa: E402

FROM = "2026-08-04"
GRAM = ("Milli", "Goldika", "WallGold", "Ayyareh", "Daric", "Invi")
CLEAN_FROM = datetime(2026, 9, 29)       # the stale-quote rules began here (SP_C_HANDOFF.md 37-38)
FROZEN_MOVE = 0.001                      # as research/rd_platforms_record.py
NEAR_MINUTES = 90                        # two readings this close count as consecutive
MIN_POOL = 30                            # bubble_position.MIN_OBSERVATIONS' order of size
TEHRAN = timedelta(hours=3, minutes=30)


def load(cache):
    if cache and os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            return json.load(f)
    import psycopg2
    url = os.environ.get("DATABASE_URL") or open(os.path.expanduser("~/.gpm_neon_url")).read().strip()
    c = psycopg2.connect(url)
    c.set_session(readonly=True)
    q = c.cursor()
    q.execute("""select s.id, s.timestamp, s.fair_price, p.platform_name, p.price_irr
                 from market_snapshots s join platform_prices p on p.snapshot_id = s.id
                 where s.collection_mode in ('scheduled', 'unknown') and s.fair_price is not null
                   and s.timestamp >= %s and p.platform_name = any(%s) order by s.timestamp""", (FROM, list(GRAM)))
    readings = {}
    for sid, ts, fair, name, price in q.fetchall():
        readings.setdefault(sid, {"t": ts.isoformat(), "fair": float(fair), "p": {}})["p"][name] = float(price)
    q.execute("""select trade_date, close from market_daily_candles where source = 'tgju' and instrument = %s
                 and trade_date >= %s order by trade_date""", ("TGJU_GOLD_18K", FROM))
    tgju = [(str(d), float(v)) for d, v in q.fetchall()]
    data = {"readings": [readings[k] for k in sorted(readings, key=lambda s: readings[s]["t"])], "tgju": tgju}
    if cache:
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(data, f)
    return data


def bases(prices):
    values = sorted(prices.values())
    if len(values) < 3:
        return None
    index = prices.get("WallGold") if prices.get("WallGold") else prices.get("Goldika")
    return {"LOW3": st.mean(values[:3]), "INDEX": index, "MEDIAN": st.median(values)}


def percent(x, fair):
    return (x / fair - 1) * 100


def robust_sd(xs):
    if len(xs) < 3:
        return float("nan")
    m = st.median(xs)
    return 1.4826 * st.median([abs(x - m) for x in xs])


def noise(series):
    """The size of the change between consecutive readings, and the share of its variance that reverses next time."""
    steps = []
    for (t0, a), (t1, b) in zip(series, series[1:]):
        if t1 - t0 <= timedelta(minutes=NEAR_MINUTES):
            steps.append((t0, b - a))
    pairs = [(x, y) for (t0, x), (t1, y) in zip(steps, steps[1:]) if t1 - t0 <= timedelta(minutes=NEAR_MINUTES)]
    if len(pairs) < 10:
        return {}
    xs = [p[0] for p in pairs]
    mean_x = st.mean(xs)
    mean_y = st.mean([p[1] for p in pairs])
    cov = st.mean([(x - mean_x) * (y - mean_y) for x, y in pairs])
    var = st.pvariance(xs)
    reversing = max(0.0, -cov) * 2 / var if var else 0.0
    return {"steps": len(steps), "sd": robust_sd([s for _, s in steps]),
            "big": sum(abs(s) > 0.5 for _, s in steps) / len(steps), "reversing": reversing}


def members(prices, k=3):
    return tuple(sorted(sorted(prices, key=prices.get)[:k]))


def run(rows, tgju, label):
    print(f"\n===== {label}: {len(rows)} readings, {rows[0]['t'][:10]} to {rows[-1]['t'][:10]}")
    names = ("LOW3", "INDEX", "MEDIAN")
    series = {n: [] for n in names}
    built = []
    for r in rows:
        b = bases(r["p"])
        if b is None or b["INDEX"] is None:
            continue
        t = datetime.fromisoformat(r["t"])
        d = {n: percent(b[n], r["fair"]) for n in names}
        built.append((t, r, d))
        for n in names:
            series[n].append((t, d[n]))

    print("\n-- the discount shown (negative = below world price)")
    for n in names:
        v = [x for _, x in series[n]]
        print(f"   {n:7s} typical {st.median(v):+.2f}  p5 {sorted(v)[len(v)//20]:+.2f}  p95 {sorted(v)[-len(v)//20]:+.2f}")
    for n in ("INDEX", "MEDIAN"):
        gap = sorted(d[n] - d["LOW3"] for _, _, d in built)
        print(f"   {n} minus LOW3: typical {st.median(gap):+.2f} pp, p5 {gap[len(gap)//20]:+.2f}, p95 {gap[-len(gap)//20]:+.2f}")

    print("\n-- noise, reading to reading")
    for n in names:
        s = noise(series[n])
        if s:
            print(f"   {n:7s} step sd {s['sd']:.3f} pp   over 0.5 pp in {s['big']*100:.1f}% of steps   "
                  f"{s['reversing']*100:.0f}% of the move's variance reverses next reading   ({s['steps']} steps)")

    print("\n-- a frozen quote inside the basis (unchanged while the others' median moved more than 0.10%)")
    frozen = defaultdict(int)
    judged = 0
    prev = None
    for t, r, d in built:
        if prev is not None and t - prev[0] <= timedelta(minutes=NEAR_MINUTES):
            judged += 1
            still = {}
            for name in r["p"]:
                if name in prev[1]["p"]:
                    others = [v for k, v in r["p"].items() if k != name]
                    before = [v for k, v in prev[1]["p"].items() if k != name]
                    if len(others) >= 3 and len(before) >= 3:
                        still[name] = (r["p"][name] == prev[1]["p"][name]
                                       and abs(st.median(others) / st.median(before) - 1) > FROZEN_MOVE)
            low = members(r["p"])
            frozen["LOW3"] += any(still.get(n) for n in low)
            source = "WallGold" if r["p"].get("WallGold") else "Goldika"
            frozen["INDEX"] += bool(still.get(source))
            ordered = sorted(r["p"], key=r["p"].get)
            mid = ordered[(len(ordered) - 1) // 2:len(ordered) // 2 + 1]
            frozen["MEDIAN"] += any(still.get(n) for n in mid)
        prev = (t, r)
    for n in names:
        print(f"   {n:7s} {frozen[n]/judged*100:.1f}% of {judged} readings")

    print("\n-- who is in the three lowest")
    seen = defaultdict(int)
    changed = same = 0
    last = None
    for _, r, _ in built:
        low = members(r["p"])
        for n in low:
            seen[n] += 1
        if last is not None:
            changed += low != last
            same += low == last
        last = low
    for n, k in sorted(seen.items(), key=lambda kv: -kv[1]):
        print(f"   {n:9s} {k/len(built)*100:.0f}%")
    print(f"   the set of three changed between readings in {changed/(changed+same)*100:.0f}% of them")
    source_index = sum(1 for _, r, _ in built if not r["p"].get("WallGold"))
    print(f"   the index used Goldika in {source_index} readings of {len(built)}")

    # deep level, the day's last reading against the settled 30 days before it
    days = defaultdict(list)
    for t, r, d in built:
        days[(t + TEHRAN).date()].append((t, d))
    day_list = sorted(days)
    state = {}
    for day in day_list:
        last_d = days[day][-1][1]
        today = {}
        for n in names:
            pool = [-x for q in day_list if day - timedelta(days=30) <= q < day for _, dd in days[q] for x in [dd[n]] if x < 0]
            if len(pool) < MIN_POOL:
                continue
            level = _value_at_percentile(sorted(pool), DEEP_DISCOUNT_PERCENTILE)
            today[n] = {"deep": -last_d[n] >= level, "level": level, "value": last_d[n]}
        if len(today) == 3:
            state[day] = today
    print(f"\n-- the deep level on the day's last reading ({len(state)} days with 30 days behind them)")
    for n in names:
        lv = [s[n]["level"] for s in state.values()]
        print(f"   {n:7s} deep on {sum(s[n]['deep'] for s in state.values())} days; its level typically {st.median(lv):.2f}%")
    both = sum(s["LOW3"]["deep"] and s["INDEX"]["deep"] for s in state.values())
    only_low = sum(s["LOW3"]["deep"] and not s["INDEX"]["deep"] for s in state.values())
    only_idx = sum(s["INDEX"]["deep"] and not s["LOW3"]["deep"] for s in state.values())
    print(f"   LOW3 and INDEX both deep {both}; only LOW3 {only_low}; only INDEX {only_idx}")

    close = {datetime.fromisoformat(d).date(): v for d, v in tgju}
    print(f"\n-- what followed: tgju's 18K close h days on ({len(close)} closes)")
    for h in (1, 3, 7):
        print(f"   h = {h} days")
        for n in names:
            xs, ys, deep_y, rest_y = [], [], [], []
            for day in day_list:
                if day not in close or day + timedelta(days=h) not in close:
                    continue
                y = (close[day + timedelta(days=h)] / close[day] - 1) * 100
                xs.append(days[day][-1][1][n])
                ys.append(y)
                if day in state:
                    (deep_y if state[day][n]["deep"] else rest_y).append(y)
            if len(xs) < 10:
                continue
            print(f"     {n:7s} n={len(xs):3d}  rank correlation of the discount with the move {spearman(xs, ys):+.2f}   "
                  f"deep: {len(deep_y):2d} days, typical {st.median(deep_y) if deep_y else float('nan'):+.2f}%   "
                  f"other: {len(rest_y):2d} days, typical {st.median(rest_y) if rest_y else float('nan'):+.2f}%")


def spearman(xs, ys):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        out = [0.0] * len(v)
        for rank, i in enumerate(order):
            out[i] = float(rank)
        return out
    rx, ry = ranks(xs), ranks(ys)
    mx, my = st.mean(rx), st.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else 0.0


def main(argv):
    cache = argv[argv.index("--cache") + 1] if "--cache" in argv else None
    data = load(cache)
    rows = data["readings"]
    print(f"read {len(rows)} readings, {len(data['tgju'])} tgju closes")
    run(rows, data["tgju"], "the whole record")
    run([r for r in rows if datetime.fromisoformat(r["t"]) >= CLEAN_FROM], data["tgju"], "since the stale-quote rules (09-29)")


if __name__ == "__main__":
    main(sys.argv[1:])
