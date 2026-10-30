"""G2, the money flow measures (SP_D_HANDOFF.md section 76), scale-free so the number of funds alive does not
move them (the audit's B8): from research/data/tsetmc_full.json, for each day the funds that report:

- net_i:     individuals' net buying as a share of their trading, sum(buy_I - sell_I) / sum(buy_I + sell_I);
- power_i:   individuals' buying per buyer against selling per seller (the "buyer's power" Iranian traders read);
- turnover:  the funds' traded value against its own median of the 60 days before (a surge reads above 1);
- funds:     how many funds reported that day.

And from fipiran (research/data/fipiran_funds.json, daily to 2020-02, weekly after): units_flow, the net units
created or redeemed times the NAV, as a share of net assets, over each step between two fipiran days, for the
19 gold funds. It covers 2020, where TSETMC's own flow record is thin.

Writes research/data/flows_daily.json.

    python research/build_flows.py
"""

import json
import os
import statistics as st
import sys
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "iran_node"))
import node  # noqa: E402

GOLD = {c for c, _ in node.GOLD_FUNDS}


def iso(n):
    s = str(n)
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


def main():
    with open(os.path.join(HERE, "data", "tsetmc_full.json"), encoding="utf-8") as f:
        full = json.load(f)
    flows, value = defaultdict(dict), defaultdict(float)
    for code, fund in full.items():
        for x in fund["flows"]:
            flows[iso(x["recDate"])][code] = x
        for x in fund["prices"]:
            if x.get("qTotCap"):
                value[iso(x["dEven"])] += float(x["qTotCap"])
    days = sorted(set(flows) | set(value))
    out = {}
    values_seen = []
    for d in days:
        row = {"funds": len(flows.get(d, {}))}
        fl = flows.get(d, {}).values()
        bi = sum(float(x["buy_I_Value"]) for x in fl)
        si = sum(float(x["sell_I_Value"]) for x in fl)
        bc = sum(float(x["buy_I_Count"]) for x in fl)
        sc = sum(float(x["sell_I_Count"]) for x in fl)
        row["net_i"] = (bi - si) / (bi + si) if bi + si > 0 else None
        row["power_i"] = (bi / bc) / (si / sc) if bc and sc and si else None
        v = value.get(d)
        past = values_seen[-60:]
        row["turnover"] = v / st.median(past) if v and len(past) >= 20 and st.median(past) > 0 else None
        if v:
            values_seen.append(v)
        out[d] = row
    # fipiran's units: net creations between consecutive fipiran days, as a share of net assets
    with open(os.path.join(HERE, "data", "fipiran_funds.json"), encoding="utf-8") as f:
        fip = json.load(f)
    recs = []

    def walk(v):
        if isinstance(v, dict):
            if "investedUnits" in v:
                recs.append(v)
            else:
                for x in v.values():
                    walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(fip)
    by_fund = defaultdict(dict)
    for r in recs:
        if str(r.get("insCode")) in GOLD and r.get("investedUnits") and r.get("statisticalNav") and r.get("netAsset"):
            by_fund[str(r["insCode"])][r["date"][:10]] = r
    step = defaultdict(lambda: [0.0, 0.0])
    for code, series in by_fund.items():
        ds = sorted(series)
        for a, b in zip(ds, ds[1:]):
            ra, rb = series[a], series[b]
            created = (float(rb["investedUnits"]) - float(ra["investedUnits"])) * float(rb["statisticalNav"])
            step[b][0] += created
            step[b][1] += float(ra["netAsset"])
    for d, (created, assets) in step.items():
        out.setdefault(d, {"funds": 0, "net_i": None, "power_i": None, "turnover": None})["units_flow"] = created / assets if assets else None
    for d in out:
        out[d].setdefault("units_flow", None)
    with open(os.path.join(HERE, "data", "flows_daily.json"), "w", encoding="utf-8") as f:
        json.dump(dict(sorted(out.items())), f)
    by_year = defaultdict(lambda: [0, 0, 0])
    for d, r in out.items():
        y = d[:4]
        by_year[y][0] += r["net_i"] is not None
        by_year[y][1] += r.get("units_flow") is not None
        by_year[y][2] = max(by_year[y][2], r["funds"])
    print("year: days with TSETMC flows, fipiran unit steps, most funds reporting")
    for y in sorted(by_year):
        print(f"  {y}: {by_year[y][0]:4d} {by_year[y][1]:4d} {by_year[y][2]:3d}")


if __name__ == "__main__":
    main()
