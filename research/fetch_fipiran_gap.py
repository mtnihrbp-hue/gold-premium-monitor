"""fipiran's units outstanding, daily, across TSETMC's flow hole (SP_D_HANDOFF.md section 78.6): 2020-02-24 to
2021-10-31, where research/data/fipiran_funds.json holds one day in seven. Same request as fetch_fipiran.py
(POST /services/fund/fundcompare), same kept fields, the same file; days already held are skipped, so it resumes.
From Iran, direct.

    python research/fetch_fipiran_gap.py
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


def main():
    data = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    day, last = date(2020, 2, 24), date(2021, 10, 31)
    t0, fetched = time.time(), 0
    while day <= last:
        key = day.isoformat()
        if key not in data and day.weekday() not in (3, 4):        # no Thursday or Friday sessions
            rows = None
            for attempt in range(4):
                try:
                    r = S.post("https://fipiran.ir/services/fund/fundcompare",
                               data=json.dumps({"date": f"{key}T00:00:00.000Z"}), timeout=(8, 90))
                    if r.ok:
                        rows = [{k: x.get(k) for k in KEEP} for x in r.json().get("items", []) if x.get("fundType") in (4, 5)]
                        break
                except Exception:  # noqa: BLE001
                    pass
                time.sleep(3 + 4 * attempt)
            data[key] = rows or []
            fetched += 1
            if fetched % 10 == 0:
                json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
                print(f"{key}: {fetched} fetched, {time.time() - t0:.0f}s", flush=True)
            time.sleep(0.7)
        day += timedelta(days=1)
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"done: {fetched} days fetched in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
