"""E-10 (d): hot money, accumulation and distribution in the gold funds, by trading week (SP_D_HANDOFF.md sections 97.3
and 98). Registered: these rules were committed before the run.

The weeks: Iranian trading weeks, Saturday to Wednesday, each with 3 or more fund sessions (a session counts with
15 of the 19 funds, gold_demand.MIN_FUNDS). The data: src/seed/gold_fund_daily.json (individuals' buy and sell
value and count, summed over the funds), then the Iran node's closed days from production; 18K's closes from the
research table (tgju).

Each week's measures, ranked as a percentile against the 52 weeks before it (26 at least):
- share: individuals' net money as a share of their buying and selling, (buy - sell) / (buy + sell); scale-free,
  since the funds grew from 1 to 19;
- crowd: buyers a session;
- power: money per buyer against money per seller, (buy / buyers) / (sell / sellers): above 1, bigger buyers;
- run: 18K over the 4 weeks to the week's last close.

The classes:
- HOT: share >= 80, crowd >= 80, power <= 50 and run >= 70 (many small buyers piling in after a rise);
- ACCUMULATION: power >= 80 and run <= 50 (big buyers against small sellers while 18K is flat or down);
- DISTRIBUTION: power <= 20 and run >= 50 (big sellers against small buyers while 18K is up).

The outcome: 18K from the week's last close to the close 1 week and 4 weeks later (7 and 28 days, the last close on
or before), against every week. The halves: the weeks before 2022 and from 2022 (the seed's 2020-2021 is thin,
B8). The verdict: LEANS when both halves differ from every week the same way by 1.5 points or more at 4 weeks, with
3 or more episodes in each; else describes only.

    python research/rd_fund_week_classes.py
"""

import bisect
import json
import math
import os
import statistics as st
import sys
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
MIN_FUNDS, TRAIL, MIN_TRAIL = 15, 52, 26


def daily_flows():
    seed = json.load(open(os.path.join(ROOT, "src", "seed", "gold_fund_daily.json"), encoding="utf-8"))
    funds = set(seed["funds"])
    totals = {date.fromisoformat(k): v[:4] for k, v in seed["days"].items()}
    end = max(totals)
    try:
        import psycopg2
        url = os.environ.get("DATABASE_URL") or open(os.path.expanduser("~/.gpm_neon_url")).read().strip()
        c = psycopg2.connect(url)
        c.set_session(readonly=True)
        q = c.cursor()
        q.execute("select instrument, detail, payload from iran_node_readings where source = 'tsetmc' and status = 'OK'"
                  " and observed_at >= %s", (end,))
        by_day = {}
        for inst, d, p in q.fetchall():
            code = str(p.get("insCode") or inst.replace("CLIENTTYPE_", ""))
            if len(d or "") == 8 and code in funds:
                day = date(int(d[:4]), int(d[4:6]), int(d[6:]))
                if day > end:
                    by_day.setdefault(day, {})[code] = p
        for day, recs in by_day.items():
            if len(recs) >= MIN_FUNDS:
                totals[day] = [sum(float(r.get(k) or 0) for r in recs.values())
                               for k in ("buy_I_Value", "buy_I_Count", "sell_I_Value", "sell_I_Count")]
    except Exception as e:  # noqa: BLE001 -- the seed alone
        print(f"(production's days not read: {type(e).__name__}; the seed alone)")
    return totals


def closes():
    rows = json.load(open(os.path.join(HERE, "data", "panel.json"), encoding="utf-8"))["rows"]
    pts = [(date.fromisoformat(r["date"]), r["g18"]) for r in rows if r.get("g18")]
    return [d for d, _ in pts], [v for _, v in pts]


def on_or_before(ds, vs, day):
    k = bisect.bisect_right(ds, day) - 1
    return vs[k] if k >= 0 else None


def rank(history, value):
    h = [x for x in history if x is not None and math.isfinite(x)]
    return 100 * sum(1 for x in h if x < value) / len(h) if len(h) >= MIN_TRAIL and value is not None else None


def main():
    flows = daily_flows()
    ds, vs = closes()
    week = lambda d: d - timedelta(days=(d.weekday() - 5) % 7)
    weeks = {}
    for d in sorted(flows):
        weeks.setdefault(week(d), []).append(d)
    rows = []
    for w in sorted(weeks):
        sessions = weeks[w]
        if len(sessions) < 3:
            continue
        bv, bc, sv, sc = (sum(flows[d][k] for d in sessions) for k in range(4))
        if not (bc and sc and sv and bv):
            continue
        last = max(sessions)
        c0, c4b = on_or_before(ds, vs, last), on_or_before(ds, vs, last - timedelta(days=28))
        c1, c4 = on_or_before(ds, vs, last + timedelta(days=7)), on_or_before(ds, vs, last + timedelta(days=28))
        future_ok = ds and last + timedelta(days=28) <= ds[-1]
        rows.append({"week": w, "n": len(sessions), "share": (bv - sv) / (bv + sv), "crowd": bc / len(sessions),
                     "power": (bv / bc) / (sv / sc), "run": math.log(c0 / c4b) if c0 and c4b else None,
                     "next1": math.log(c1 / c0) if c0 and c1 and last + timedelta(days=7) <= ds[-1] else None,
                     "next4": math.log(c4 / c0) if c0 and c4 and future_ok else None})
    for i, r in enumerate(rows):
        past = rows[max(0, i - TRAIL):i]
        for k in ("share", "crowd", "power", "run"):
            r[k + "_rank"] = rank([p[k] for p in past], r[k])
    classes = {
        "HOT": lambda r: r["share_rank"] >= 80 and r["crowd_rank"] >= 80 and r["power_rank"] <= 50 and r["run_rank"] >= 70,
        "ACCUMULATION": lambda r: r["power_rank"] >= 80 and r["run_rank"] <= 50,
        "DISTRIBUTION": lambda r: r["power_rank"] <= 20 and r["run_rank"] >= 50,
    }
    ranked = [r for r in rows if None not in (r["share_rank"], r["crowd_rank"], r["power_rank"], r["run_rank"])]
    halves = {"before 2022": [r for r in ranked if r["week"] < date(2022, 1, 1)],
              "from 2022": [r for r in ranked if r["week"] >= date(2022, 1, 1)]}
    print(f"weeks: {len(rows)} ({rows[0]['week']} to {rows[-1]['week']}); ranked: {len(ranked)}; "
          + ", ".join(f"{k}: {len(v)}" for k, v in halves.items()))

    def stats(rs, key):
        v = [r[key] for r in rs if r[key] is not None]
        return (len(v), st.mean(v) if v else None, sum(x > 0 for x in v) / len(v) if v else None)

    verdicts = {}
    for name, rule in classes.items():
        line, diffs = [], []
        for hname, hrows in halves.items():
            hits = [r for r in hrows if rule(r)]
            n1, m1, u1 = stats(hits, "next1")
            n4, m4, u4 = stats(hits, "next4")
            b1 = stats(hrows, "next1")
            b4 = stats(hrows, "next4")
            line.append(f"{hname}: {len(hits)} weeks; next week {m1 * 100 if m1 is not None else float('nan'):+.1f}% "
                        f"(every week {b1[1] * 100:+.1f}%), up {u1 or 0:.0%} ({b1[2]:.0%}); 4 weeks "
                        f"{m4 * 100 if m4 is not None else float('nan'):+.1f}% ({b4[1] * 100:+.1f}%), up {u4 or 0:.0%} ({b4[2]:.0%})")
            diffs.append((n4, (m4 - b4[1]) * 100 if m4 is not None else None))
        same = all(n >= 3 and d is not None for n, d in diffs) and (all(d >= 1.5 for _, d in diffs) or all(d <= -1.5 for _, d in diffs))
        verdicts[name] = "LEANS " + ("UP" if diffs[0][1] > 0 else "DOWN") if same else "describes only"
        print(f"\n{name}: {verdicts[name]}")
        for x in line:
            print("  " + x)
    last = rows[-1]
    now = [name for name, rule in classes.items() if None not in (last["share_rank"], last["crowd_rank"], last["power_rank"],
                                                                  last["run_rank"]) and rule(last)]
    print(f"\nthe latest week, {last['week']} ({last['n']} sessions): share {last['share']:+.1%} (rank {last['share_rank']:.0f}),"
          f" crowd rank {last['crowd_rank']:.0f}, power {last['power']:.2f} (rank {last['power_rank']:.0f}),"
          f" 18K's 4 weeks {last['run'] * 100:+.1f}% (rank {last['run_rank']:.0f}): {now or 'no class'}")


if __name__ == "__main__":
    main()
