"""Seed Direction's gold demand (SP-D, SP_D_HANDOFF.md section 35.11): each day's individual buying and
selling summed over the 18 gold funds -- research/data/tsetmc_gold_funds.json, pulled from Iran on
2026-10-04; سافرون, a saffron fund, excluded (section 35.7). Written to src/seed/gold_fund_daily.json as
{"funds": [...], "days": {date: [buy value, buyers, sell value, sellers, funds]}}, values in rial.
Production appends the days the phone sends after it (main._gold_demand)."""
import json
import os
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
NOT_GOLD = {"51200575796028449"}
F = json.load(open(os.path.join(HERE, "data", "tsetmc_gold_funds.json"), encoding="utf-8"))
agg = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0, 0])
for code, fund in F.items():
    if code in NOT_GOLD:
        continue
    for f in fund["flows"]:
        s = str(f["recDate"])
        a = agg[date(int(s[:4]), int(s[4:6]), int(s[6:])).isoformat()]
        for k, key in enumerate(("buy_I_Value", "buy_I_Count", "sell_I_Value", "sell_I_Count")):
            a[k] += float(f.get(key) or 0)
        a[4] += 1
days = {d: [round(x) if k < 4 else x for k, x in enumerate(v)] for d, v in sorted(agg.items()) if v[1] and v[3] and v[2]}
out = {"funds": sorted(c for c in F if c not in NOT_GOLD), "days": days}
path = os.path.join(HERE, "..", "src", "seed", "gold_fund_daily.json")
json.dump(out, open(path, "w", encoding="utf-8"), separators=(",", ":"))
print(f"{len(days)} days {min(days)} -> {max(days)}, {len(out['funds'])} funds -> {os.path.relpath(path, HERE)} ({os.path.getsize(path):,} bytes)")
