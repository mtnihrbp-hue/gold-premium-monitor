"""The dollar and Tether after the days the AI model labelled (SP-D, SP_D_HANDOFF.md section 35.9).

Rules, fixed before the labels came back:
- Labels: research/data/news_days.jsonl (label_news_days.py: one request per Tehran day of the owner's
  four news-bearing channels; the model never saw a price after the day).
- For each label value: the dollar's (tgju price_dollar_rl) and Tether's (tgju crypto-tether-irr) move
  from the last close before the day to the close 1 and 3 trading days after it, against every labelled
  day. A value is reported when it has at least 8 days; its sign agreement with the model's own
  "dollar_pressure" is reported too, as the model's forward record on the past year.
"""

import json
import os
import sys
from collections import defaultdict
from datetime import date

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rd_news_events import moves, series  # noqa: E402

MIN_DAYS = 8


def main():
    rows = [json.loads(l) for l in open(os.path.join(HERE, "data", "news_days.jsonl"), encoding="utf-8") if l.strip()]
    rows = [r for r in rows if isinstance(r.get("labels"), dict)]
    print(f"{len(rows)} labelled days, {rows[0]['day']} .. {rows[-1]['day']}")
    usd, usdt = series("price_dollar_rl"), series("crypto-tether-irr")
    keys = ("cbi_fx_intervention", "talks", "conflict", "sanctions", "oil_exports", "dollar_pressure")
    for label, prices in (("dollar", usd), ("tether", usdt)):
        out = {}
        for r in rows:
            d = date.fromisoformat(r["day"])
            out[r["day"]] = (moves(prices, d, 1), moves(prices, d, 3))
        allm = [v for v in out.values() if v[1] is not None]
        a1 = np.array([v[0] for v in allm]); a3 = np.array([v[1] for v in allm])
        print(f"\n== {label}: all labelled days n={len(allm)}: 1 day {np.median(a1):+.2f}% (fell {np.mean(a1 < 0):.0%}),"
              f" 3 days {np.median(a3):+.2f}% (fell {np.mean(a3 < 0):.0%})")
        for key in keys:
            groups = defaultdict(list)
            for r in rows:
                v = out[r["day"]]
                if v[1] is not None:
                    groups[str(r["labels"].get(key))].append(v)
            for value, vs in sorted(groups.items()):
                if len(vs) < MIN_DAYS:
                    print(f"  {key}={value:<13} n={len(vs):>3}: too few")
                    continue
                m1 = np.array([x[0] for x in vs]); m3 = np.array([x[1] for x in vs])
                print(f"  {key}={value:<13} n={len(vs):>3}: 1 day {np.median(m1):+.2f}% (fell {np.mean(m1 < 0):.0%}),"
                      f" 3 days {np.median(m3):+.2f}% (fell {np.mean(m3 < 0):.0%})")
    print("\n-- the model's central-bank days:")
    for r in rows:
        if r["labels"].get("cbi_fx_intervention") is True:
            print(f"   {r['day']}: {r['labels'].get('summary', '')[:160]}")


if __name__ == "__main__":
    main()
