"""E-9, the news leads on years they did not come from (SP_D_HANDOFF.md section 80; registered in 454ed80 before
the labels existed, and this script written before them too).

77.5's reading (research/rd_news_read.py: the first trading day on or after a news day, the dollar's log move over
the next 5 trading days, a fall of 10% or more in 18K's close within the next 40) on the span tested,
2022-01-01 to 2025-10-14. The year the leads came from is printed beside it and never counted.

  L1  the fall rate after talks = progress, 10 points or more above talks = none
  L2  conflict = escalation, 10 points or more above conflict = none
  L3  dollar_pressure = up, 10 points or more above dollar_pressure = down
  L4  the dollar's median 5 days after cbi_fx_intervention below the median of all days, with 15 or more such days

And each with the same sign in at least 2 of the 3 sub-spans. It runs once 600 or more days of the span tested
are labelled, and says how many.

    python research/rd_news_e9.py
"""

import json
import math
import os
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
TESTED = ("2022-01-01", "2025-10-14")
SEEN = ("2025-10-15", "2026-09-06")
SUBSPANS = (("2022-2023", "2022-01-01", "2023-12-31"), ("2024", "2024-01-01", "2024-12-31"),
            ("2025 to 10-14", "2025-01-01", "2025-10-14"))
LEADS = (("L1", "talks", "progress", "none"), ("L2", "conflict", "escalation", "none"),
         ("L3", "dollar_pressure", "up", "down"))
MIN_DAYS, GAP, MIN_INTERVENTIONS = 600, 0.10, 15


def load():
    with open(os.path.join(HERE, "data", "panel.json"), encoding="utf-8") as f:
        rows = json.load(f)["rows"]
    days = [r["date"] for r in rows]
    g = [r["g18"] for r in rows]
    usd = [r["usd"] for r in rows]

    def after(day):
        i = next((k for k, d in enumerate(days) if d >= day), None)
        if i is None or i + 40 >= len(rows):
            return None
        u5 = math.log(usd[i + 5] / usd[i]) if usd[i] and usd[i + 5] else None
        fall = min(g[i + 1:i + 41]) / g[i] - 1 <= -0.10
        return u5, fall

    out = {}
    with open(os.path.join(HERE, "data", "news_days.jsonl"), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                x = json.loads(line)
                o = after(x["day"])
                if o:
                    out[x["day"]] = ({k: str(v) for k, v in (x.get("labels") or {}).items() if k != "summary"}, o)
    return out


def rate(items, key, value):
    hits = [o[1] for labels, o in items if labels.get(key) == value]
    return (sum(hits) / len(hits), len(hits)) if hits else (None, 0)


def lead_gap(items, key, a, b):
    ra, na = rate(items, key, a)
    rb, nb = rate(items, key, b)
    return (ra - rb if ra is not None and rb is not None else None), (ra, na), (rb, nb)


def l4(items):
    every = [o[0] for _, o in items if o[0] is not None]
    cbi = [o[0] for labels, o in items if labels.get("cbi_fx_intervention") == "True" and o[0] is not None]
    if not cbi or not every:
        return None, len(cbi), None, None
    return st.median(cbi) - st.median(every), len(cbi), st.median(cbi), st.median(every)


def span(news, lo, hi):
    return [v for d, v in sorted(news.items()) if lo <= d <= hi]


def main():
    news = load()
    tested = span(news, *TESTED)
    print(f"labelled days with 40 days after: {len(tested)} in the span tested, {len(span(news, *SEEN))} in the seen year")
    if len(tested) < MIN_DAYS:
        print(f"E-9 waits: {len(tested)} of the {MIN_DAYS} days it needs")
        return
    base = sum(o[1] for _, o in tested) / len(tested)
    print(f"the span tested: a 10% fall within 40 days after {base:.0%} of days\n")
    for name, key, a, b in LEADS:
        gap, (ra, na), (rb, nb) = lead_gap(tested, key, a, b)
        signs = []
        for sname, lo, hi in SUBSPANS:
            sg = lead_gap(span(news, lo, hi), key, a, b)[0]
            signs.append((sname, sg))
        same = sum(1 for _, sg in signs if sg is not None and sg > 0)
        ok = gap is not None and gap >= GAP and same >= 2
        seen = lead_gap(span(news, *SEEN), key, a, b)[0]
        print(f"{name} {key}: {a} {ra:.0%} ({na} days) against {b} {rb:.0%} ({nb} days): {gap * 100:+.0f} points; "
              f"by sub-span {', '.join(f'{s} {g * 100:+.0f}' if g is not None else f'{s} n/a' for s, g in signs)}; "
              f"the seen year {seen * 100:+.0f} -> {'PASS' if ok else 'fails'}")
    gap, n, mc, ma = l4(tested)
    signs = [(s, l4(span(news, lo, hi))[0]) for s, lo, hi in SUBSPANS]
    same = sum(1 for _, g in signs if g is not None and g < 0)
    ok = gap is not None and n >= MIN_INTERVENTIONS and gap < 0 and same >= 2
    print(f"L4 the central bank: {n} intervention days; the dollar's median 5 days after "
          f"{(f'{mc:+.2%} against {ma:+.2%} on all days') if gap is not None else 'n/a'}; by sub-span "
          f"{', '.join(f'{s} {g:+.2%}' if g is not None else f'{s} n/a' for s, g in signs)} -> {'PASS' if ok else 'fails'}")


if __name__ == "__main__":
    main()
