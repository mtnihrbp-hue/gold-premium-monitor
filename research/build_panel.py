"""The research table for SP-Eb.RD (SP_D_HANDOFF.md section 72; KPI Eb-2): one row per 18K trading day, each
column built only from what was known by that day's close in Tehran.

Columns, and when each is known:
- g18, usd, tether, coin, mesghal: tgju's close of the day itself (Tehran's session).
- ons_prev: world gold's close of the last day before (New York closes after Tehran's day ends).
- world18: the world price, ons_prev x usd x 0.75 / 31.1035; gap: g18 against it, in percent.
- coin_premium: the Emami coin against its gold in 18K terms (8.133 g at 0.900 = 9.7596 grams of 18K).
- melted_premium: the bazaar's mesghal (4.6083 g at 0.705 = 4.3318 grams of 18K) against 18K.
- fi: the fixed-income level (src/seed/fixed_income.json) of the day or the last before.
- tedpix: the stock index (src/seed/tedpix.json), the day or the last before.
- flow_power: the gold funds' money-flow power (src/seed/gold_fund_flows.json) of the day itself, never carried.
  None across 2019-10 to 2021-10, the seed's gap (B8).
- news: the day's labels (research/data/news_days.jsonl), None where the day is not labelled.

Saved to research/data/panel.json with its rules. A row never changes when later data is added
(tests/test_panel.py).

    python research/build_panel.py
"""

import bisect
import json
import os
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
COIN_GRAMS_18K = 8.133 * 0.900 / 0.75
MESGHAL_GRAMS_18K = 4.6083 * 0.705 / 0.75
FLOW_GAP = (date(2019, 10, 30), date(2021, 10, 18))

RULES = {
    "g18": "tgju geram18 close, the day itself", "usd": "tgju price_dollar_rl close, the day itself",
    "tether": "tgju crypto-tether-irr close, the day itself", "coin": "tgju sekee close, the day itself",
    "mesghal": "tgju mesghal close, the day itself", "ons_prev": "tgju ons close of the last day before",
    "world18": "ons_prev x usd x 0.75 / 31.1035", "gap": "(g18 / world18 - 1) x 100",
    "coin_premium": "(coin / (9.7596 x g18) - 1) x 100", "melted_premium": "(mesghal / (4.3318 x g18) - 1) x 100",
    "fi": "seed fixed income, the day or the last before", "tedpix": "seed tedpix, the day or the last before",
    "flow_power": "seed gold-fund flow power of the day itself; None in 2019-10..2021-10",
    "news": "research/data/news_days.jsonl labels of the day, or None",
}


class Series:
    """A dated series read as of a day: the value on that day or the last before it, optionally strictly before."""

    def __init__(self, pairs):
        pairs = sorted((d, v) for d, v in pairs if v is not None)
        self.days = [d for d, _ in pairs]
        self.values = [v for _, v in pairs]

    def asof(self, day, strictly_before=False, max_age_days=None):
        i = (bisect.bisect_left if strictly_before else bisect.bisect_right)(self.days, day) - 1
        if i < 0:
            return None
        if max_age_days is not None and (day - self.days[i]).days > max_age_days:
            return None
        return self.values[i]

    def on(self, day):
        i = bisect.bisect_left(self.days, day)
        return self.values[i] if i < len(self.days) and self.days[i] == day else None


def build(tgju, fi, tedpix, flow_power, news):
    """Rows from the inputs: `tgju` {key: [(date, close)]}, the others [(date, value)] or {date: labels}."""
    s = {k: Series(v) for k, v in tgju.items()}
    fi_s, ted_s, flow_s = Series(fi), Series(tedpix), Series(flow_power)
    rows = []
    for day in s["geram18"].days:
        g18 = s["geram18"].on(day)
        usd = s["price_dollar_rl"].on(day) if "price_dollar_rl" in s else None
        ons_prev = s["ons"].asof(day, strictly_before=True, max_age_days=5) if "ons" in s else None
        row = {"date": day.isoformat(), "g18": g18, "usd": usd,
               "tether": s["crypto-tether-irr"].on(day) if "crypto-tether-irr" in s else None,
               "coin": s["sekee"].on(day) if "sekee" in s else None,
               "mesghal": s["mesghal"].on(day) if "mesghal" in s else None,
               "ons_prev": ons_prev}
        world18 = ons_prev * usd * 0.75 / 31.1035 if ons_prev and usd else None
        row["world18"] = world18
        row["gap"] = (g18 / world18 - 1) * 100 if world18 else None
        row["coin_premium"] = (row["coin"] / (COIN_GRAMS_18K * g18) - 1) * 100 if row["coin"] else None
        row["melted_premium"] = (row["mesghal"] / (MESGHAL_GRAMS_18K * g18) - 1) * 100 if row["mesghal"] else None
        row["fi"] = fi_s.asof(day, max_age_days=10)
        row["tedpix"] = ted_s.asof(day, max_age_days=10)
        row["flow_power"] = None if FLOW_GAP[0] <= day < FLOW_GAP[1] else flow_s.on(day)   # a day's flow, never carried
        row["news"] = news.get(day)
        rows.append(row)
    return rows


def load_inputs():
    with open(os.path.join(HERE, "data", "tgju_more.json"), encoding="utf-8") as f:
        raw = json.load(f)
    tgju = {k: [(date.fromisoformat(r["date"]), float(r["close"])) for r in v if r.get("close")] for k, v in raw.items()}
    with open(os.path.join(ROOT, "src", "seed", "fixed_income.json"), encoding="utf-8") as f:
        fi = [(date.fromisoformat(k), float(v)) for k, v in json.load(f)["level"].items()]
    with open(os.path.join(ROOT, "src", "seed", "tedpix.json"), encoding="utf-8") as f:
        ted = [(date.fromisoformat(k), float(v if not isinstance(v, (list, dict)) else (v[0] if isinstance(v, list) else v.get("close"))))
               for k, v in json.load(f).items()]
    with open(os.path.join(ROOT, "src", "seed", "gold_fund_flows.json"), encoding="utf-8") as f:
        flows = [(date.fromisoformat(k), float(v)) for k, v in json.load(f)["power"].items()]
    news = {}
    path = os.path.join(HERE, "data", "news_days.jsonl")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    x = json.loads(line)
                    news[date.fromisoformat(x["day"])] = {k: v for k, v in (x.get("labels") or {}).items() if k != "summary"}
    return tgju, fi, ted, flows, news


def main():
    rows = build(*load_inputs())
    with open(os.path.join(HERE, "data", "panel.json"), "w", encoding="utf-8") as f:
        json.dump({"rules": RULES, "rows": rows}, f, ensure_ascii=False)
    have = {k: sum(1 for r in rows if r.get(k) is not None) for k in RULES}
    first = {k: next((r["date"] for r in rows if r.get(k) is not None), None) for k in RULES}
    print(f"{len(rows)} days, {rows[0]['date']} to {rows[-1]['date']}")
    for k in RULES:
        print(f"  {k:15} {have[k]:5} days, from {first[k]}")


if __name__ == "__main__":
    main()
