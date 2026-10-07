"""Seed the gold funds' money flow for the room's money-flow member (SP-D, SP_D_HANDOFF.md section 33).

TSETMC gives the funds' client types only to Iranian addresses; the history was pulled from Iran on
2026-10-04 (research/fetch_tsetmc_gold_funds.py, 19 funds, git-ignored). Written to
src/seed/gold_fund_flows.json as each day's buyer power -- individuals' value per buyer over value
per seller, summed over the funds that traded that day -- exactly as rd_committee_2y.py builds it.
From 2026-10-07 the owner's phone sends each fund's day (iran_node/node.py) and production appends
the days after the seed's last."""
import json
import os
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
F = json.load(open(os.path.join(HERE, "data", "tsetmc_gold_funds.json"), encoding="utf-8"))
agg = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0, 0])
for fund in F.values():
    for f in fund["flows"]:
        s = str(f["recDate"])
        a = agg[date(int(s[:4]), int(s[4:6]), int(s[6:]))]
        a[0] += float(f.get("buy_I_Value") or 0)
        a[1] += float(f.get("buy_I_Count") or 0)
        a[2] += float(f.get("sell_I_Value") or 0)
        a[3] += float(f.get("sell_I_Count") or 0)
        a[4] += 1
days = sorted(k for k, a in agg.items() if a[1] and a[3] and a[2])
power = {k.isoformat(): round((agg[k][0] / agg[k][1]) / (agg[k][2] / agg[k][3]), 6) for k in days}
out = {"funds": sorted(F), "power": power}
path = os.path.join(HERE, "..", "src", "seed", "gold_fund_flows.json")
json.dump(out, open(path, "w", encoding="utf-8"), separators=(",", ":"))
print(f"buyer power: {len(power)} days {min(power)} -> {max(power)}, {len(F)} funds -> {os.path.relpath(path, HERE)}")
