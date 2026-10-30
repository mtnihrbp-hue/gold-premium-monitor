"""The news, read against what followed (SP_D_HANDOFF.md section 77.5). Descriptive, not a test.

For each label value of research/data/news_days.jsonl (318 days, 2025-10-15 to 2026-09-06; labelled from the
day's news by an LLM that never saw a later price), the dollar's move over the next 5 trading days, 18K's over
the next 20, and how often a 10% fall came within 40 days, against all labelled days. A value is shown with 8
days or more. And the labels in the 10 days before each top of a decline in the labelled span.

    python research/rd_news_read.py
"""

import json
import math
import os
import statistics as st
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    with open(os.path.join(HERE, "data", "panel.json"), encoding="utf-8") as f:
        rows = json.load(f)["rows"]
    with open(os.path.join(HERE, "data", "windows.json"), encoding="utf-8") as f:
        windows = json.load(f)
    days = [r["date"] for r in rows]
    pos = {d: i for i, d in enumerate(days)}
    news = {}
    with open(os.path.join(HERE, "data", "news_days.jsonl"), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                x = json.loads(line)
                news[x["day"]] = {k: v for k, v in (x.get("labels") or {}).items() if k != "summary"}
    g = [r["g18"] for r in rows]
    usd = [r["usd"] for r in rows]

    def after(day):
        """The first trading day on or after a news day, and what followed from its close."""
        i = next((pos[d] for d in days if d >= day), None)
        if i is None or i + 40 >= len(rows):
            return None
        u5 = math.log(usd[i + 5] / usd[i]) if usd[i] and usd[i + 5] else None
        g20 = math.log(g[i + 20] / g[i])
        fall = min(g[i + 1:i + 41]) / g[i] - 1 <= -0.10
        return u5, g20, fall

    outcomes = {d: after(d) for d in news}
    base = [o for o in outcomes.values() if o]
    print(f"{len(base)} labelled days with 40 days after; all: dollar 5d {st.mean(o[0] for o in base if o[0] is not None):+.2%}, "
          f"18K 20d {st.mean(o[1] for o in base):+.2%}, a 10% fall within 40 days on {sum(o[2] for o in base) / len(base):.0%}")
    groups = defaultdict(list)
    for d, labels in news.items():
        o = outcomes.get(d)
        if not o:
            continue
        for k, v in labels.items():
            groups[(k, str(v))].append(o)
    print(f"\n{'label = value':38} {'days':>5} {'dollar 5d':>10} {'18K 20d':>9} {'10% fall in 40d':>16}")
    for (k, v), os_ in sorted(groups.items()):
        if len(os_) < 8:
            continue
        u = [o[0] for o in os_ if o[0] is not None]
        print(f"{k + ' = ' + v:38} {len(os_):5d} {st.mean(u):+10.2%} {st.mean(o[1] for o in os_):+9.2%} {sum(o[2] for o in os_) / len(os_):16.0%}")
    print("\nThe 10 labelled days before each top of a decline in the labelled span:")
    for w in windows:
        if w["kind"] != "decline" or not ("2025-10-25" <= w["from"] <= "2026-09-06"):
            continue
        i = pos[w["from"]]
        before = [days[j] for j in range(max(0, i - 10), i + 1) if days[j] in news]
        tally = defaultdict(int)
        for d in before:
            for k, v in news[d].items():
                if str(v) not in ("none", "False", "flat", "None"):
                    tally[f"{k}={v}"] += 1
        print(f"  top {w['from']} ({w['g18']:+.1%} to {w['to']}): {len(before)} labelled days; {dict(sorted(tally.items(), key=lambda x: -x[1]))}")


if __name__ == "__main__":
    main()
