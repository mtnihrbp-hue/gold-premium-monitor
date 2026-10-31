"""The lens's case library (SP_D_HANDOFF.md sections 84-86): every deal and strike since 1394 that the research
table covers, with what the dollar, world gold and 18K did after it, written to src/seed/cases.json for
production, which reads it and never recomputes it.

- Each move runs from the last close before the news to 5, 10, 20 and 40 trading days after.
- "shut": calendar days the market gave no live price after the news, rows missing or tgju's quotes frozen
  (both dollar and 18K unchanged), when 7 or more.
- "base": over every day from 2015 on, how often 18K was higher 40 trading days later, and its typical absolute
  40-day move, so a case is read against any day rather than alone.

The 2025-06-24 ceasefire is not a case of its own: the market was shut from 06-12 to 06-25, so its moves are
the 12-day war's. A new case is added here, with the owner's review, and the seed rebuilt.

    python research/build_cases.py
"""

import json
import os
import statistics as st
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "src", "seed", "cases.json")
HORIZONS = (5, 10, 20, 40)
CASES = (("deal", "2015-04-02", "the Lausanne framework"),
         ("deal", "2015-07-14", "the JCPOA signed"),
         ("deal", "2016-01-16", "the JCPOA in force"),
         ("sanctions", "2018-05-08", "the US leaves the JCPOA"),
         ("strike", "2020-01-03", "Soleimani killed"),
         ("strike", "2020-01-08", "Iran strikes Al Asad"),
         ("strike", "2024-04-13", "Iran strikes Israel"),
         ("strike", "2024-10-01", "Iran strikes Israel"),
         ("strike", "2024-10-26", "Israel strikes Iran"),
         ("strike", "2025-06-13", "Israel strikes Iran: the 12-day war"),
         ("strike", "2026-02-28", "the US and Israel attack Iran"),
         ("deal", "2026-06-15", "a peace agreement announced"),
         ("strike", "2026-07-14", "the attacks resume"))
STILL = 5e-4            # a quote that moved less than this is frozen
SHUT_DAYS = 7


def shut_days(rows, b, i0):
    """Calendar days without a live price after the last close before the news (index b)."""
    day = lambda k: date.fromisoformat(rows[k]["date"])  # noqa: E731
    longest = (day(i0) - day(b)).days if i0 > b else 0          # rows missing
    for k in range(i0, min(i0 + 3, len(rows) - 1)):
        e = k
        while e + 1 < len(rows) and all(rows[e + 1].get(x) and rows[e].get(x)
                                        and abs(rows[e + 1][x] / rows[e][x] - 1) < STILL for x in ("g18", "usd")):
            e += 1
        if e > k and e + 1 < len(rows):
            longest = max(longest, (day(e + 1) - day(k)).days)
    return longest if longest >= SHUT_DAYS else 0


def move(rows, b, k, h):
    v0, j = rows[b].get(k), b + h
    v = rows[j].get(k) if j < len(rows) else None
    return round((v / v0 - 1) * 100, 1) if v and v0 else None


def main():
    with open(os.path.join(HERE, "data", "panel.json"), encoding="utf-8") as f:
        rows = json.load(f)["rows"]
    days = [r["date"] for r in rows]
    out = []
    for kind, d, name in CASES:
        b = max(i for i, x in enumerate(days) if x < d)
        i0 = next(i for i, x in enumerate(days) if x >= d)
        out.append({"kind": kind, "date": d, "name": name, "last_close_before": days[b],
                    "shut_days": shut_days(rows, b, i0),
                    **{f"{k}_{h}": move(rows, b, src, h) for k, src in (("dollar", "usd"), ("gold18", "g18"),
                                                                          ("world", "ons_prev")) for h in HORIZONS}})
    g = [r["g18"] for r in rows]
    ok = [i for i, r in enumerate(rows) if r["date"] >= "2015-01-01" and i + 40 < len(rows) and g[i] and g[i + 40]]
    ups = [g[i + 40] > g[i] for i in ok]
    size = [abs(g[i + 40] / g[i] - 1) * 100 for i in ok]
    base = {"from": rows[ok[0]]["date"], "to": rows[ok[-1]]["date"], "days": len(ok),
            "higher_40_share": round(sum(ups) / len(ups), 3), "typical_abs_move_40": round(st.median(size), 1)}
    json.dump({"built": date.today().isoformat(), "source": "tgju daily closes via research/data/panel.json",
               "horizons": HORIZONS, "base": base, "cases": out}, open(OUT, "w", encoding="utf-8"), indent=1)
    print(json.dumps(base))
    for c in out:
        print(c["kind"], c["date"], c["name"], "shut", c["shut_days"], "dollar 40", c["dollar_40"], "18K 40", c["gold18_40"])


if __name__ == "__main__":
    main()
