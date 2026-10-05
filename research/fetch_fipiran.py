"""Every commodity (gold) and fixed-income fund's daily NAV, net assets and units outstanding, from
fipiran (SP-D, 2026-10-05).

fipiran.ir's own page calls POST /services/fund/fundcompare {"date": ...}; for every fund on that day
it returns the issue and redemption NAV, the statistical NAV, net assets and the units outstanding
(investedUnits) -- the units' daily change is the money that came into or left the fund, and the
fund's exchange price against its redemption NAV is its premium. Kept: fundType 5 (commodity
deposits: the gold funds) and 4 (fixed income). From Iran, direct, about one request a second.
Every 7th day after 2020-02 (flows over 5-20 days need units only at their ends; fipiran slowed
to about 12 s a request); each gold fund's whole daily NAV-return history comes from one request to
/services/efficiency/fundefficiencychart (research/data/fipiran_nav.json). Writes
research/data/fipiran_funds.json (git-ignored); resumable.
"""
import json
import os
import time
from datetime import date, timedelta

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "fipiran_funds.json")
S = requests.Session()
S.trust_env = False
S.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36",
                  "Accept": "application/json, text/plain, */*", "Referer": "https://fipiran.ir/", "Content-Type": "application/json"})
KEEP = ("regNo", "name", "fundType", "date", "statisticalNav", "cancelNav", "issueNav", "netAsset", "investedUnits", "insCode",
        "dailyEfficiency")
data = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
day, last = date(2019, 1, 1), date(2026, 10, 4)
t0 = time.time()
while day <= last:
    key = day.isoformat()
    if key not in data:
        rows = None
        for attempt in range(4):
            try:
                r = S.post("https://fipiran.ir/services/fund/fundcompare", data=json.dumps({"date": f"{key}T00:00:00.000Z"}),
                           timeout=(8, 90))
                if r.ok:
                    rows = [{k: x.get(k) for k in KEEP} for x in r.json().get("items", []) if x.get("fundType") in (4, 5)]
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(3 + 4 * attempt)
        data[key] = rows or []
        if len(data) % 30 == 0:
            json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"{key}: {len(data)} days, {time.time() - t0:.0f}s", flush=True)
        time.sleep(0.7)
    day += timedelta(days=1 if day < date(2020, 2, 24) else 7)
json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
print(f"done: {len(data)} days in {time.time() - t0:.0f}s", flush=True)

# each gold fund's daily NAV returns, one request a fund
GOLD = set(json.load(open(os.path.join(HERE, "data", "tsetmc_gold_funds.json"), encoding="utf-8")))
NAV_OUT = os.path.join(HERE, "data", "fipiran_nav.json")
regs = {}
for rows in data.values():
    for x in rows:
        if str(x.get("insCode")) in GOLD:
            regs[x["regNo"]] = (x.get("insCode"), x.get("name"))
navs = {}
for reg, (ins, name) in regs.items():
    try:
        r = S.get(f"https://fipiran.ir/services/efficiency/fundefficiencychart?showAll=true&regNos={reg}", timeout=(8, 120))
        items = r.json()[0]["items"] if r.ok and r.json() else []
    except Exception:  # noqa: BLE001
        items = []
    navs[reg] = {"insCode": ins, "name": name, "items": [{"date": i["date"][:10], "daily": i["dailyEfficiency"]} for i in items]}
    print(f"NAV history {name}: {len(items)} days", flush=True)
    time.sleep(1)
json.dump(navs, open(NAV_OUT, "w", encoding="utf-8"), ensure_ascii=False)
