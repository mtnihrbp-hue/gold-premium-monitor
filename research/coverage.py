"""G1, completeness (SP_D_HANDOFF.md section 76): each input of the research table, by year, against 18K's own
trading days, and the weekdays each series trades. A model may only run where its inputs are present; this is
the record of where they are.

    python research/coverage.py
"""

import json
import os
from collections import Counter, defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
INPUTS = ("usd", "tether", "coin", "ons_prev", "gvz_prev", "vix_prev", "fi", "tedpix", "flow_power", "news")
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def main():
    with open(os.path.join(HERE, "data", "panel.json"), encoding="utf-8") as f:
        rows = json.load(f)["rows"]
    by_year = defaultdict(list)
    for r in rows:
        by_year[r["date"][:4]].append(r)
    print(f"{'year':5} {'18K days':>8} " + " ".join(f"{k[:9]:>9}" for k in INPUTS))
    report = {}
    for y in sorted(by_year):
        part = by_year[y]
        cells = {k: sum(1 for r in part if r.get(k) is not None) / len(part) for k in INPUTS}
        report[y] = {"days": len(part), **cells}
        print(f"{y:5} {len(part):8d} " + " ".join(f"{cells[k]:9.0%}" for k in INPUTS))
    wd = Counter(date.fromisoformat(r["date"]).weekday() for r in rows)
    print("\n18K's trading weekdays:", {WEEKDAYS[k]: v for k, v in sorted(wd.items())})
    with open(os.path.join(HERE, "data", "tgju_more.json"), encoding="utf-8") as f:
        raw = json.load(f)
    for key in ("price_dollar_rl", "crypto-tether-irr", "sekee", "ons"):
        w = Counter(date.fromisoformat(r["date"]).weekday() for r in raw[key] if r["date"] >= "2021-01-01")
        print(f"{key:18} weekdays from 2021:", {WEEKDAYS[k]: v for k, v in sorted(w.items())})
    gaps = []
    for name in ("usd", "tether"):
        run, worst, start = 0, (0, None), None
        for r in rows:
            if r["date"] < ("2020-11-12" if name == "tether" else "2013-07-22"):
                continue
            if r.get(name) is None:
                run, start = run + 1, start or r["date"]
                if run > worst[0]:
                    worst = (run, start)
            else:
                run, start = 0, None
        gaps.append((name, worst))
    print("\nlongest run of missing days:", gaps)
    with open(os.path.join(HERE, "data", "coverage.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)


if __name__ == "__main__":
    main()
