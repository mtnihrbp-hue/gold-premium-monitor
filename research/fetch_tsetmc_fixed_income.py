"""Fetch fixed-income ETFs' daily prices from TSETMC, for parking the trader's cash (SP-D, 2026-10-04).

The owner: "let's add another factor, fixed income etf, and say the money is parked in that
etf (Afran) for example." TSETMC answers Iranian addresses only, so this runs from an
Iranian connection, direct (trust_env=False: the system proxy would leave the country), and
writes research/data/tsetmc_fixed_income.json (git-ignored).
"""
import json
import os
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "tsetmc_fixed_income.json")
BASE = "https://cdn.tsetmc.com/api"
S = requests.Session()
S.trust_env = False
S.headers.update({"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
SEARCH = ("افران", "اطلس", "کمند", "اعتماد", "یاقوت", "سپیدما", "کارین", "آکورد", "فیروزا", "گنجینه", "لبخند", "آساس",
          "درآمد ثابت")


def get(path):
    for attempt in range(3):
        try:
            r = S.get(f"{BASE}/{path}", timeout=(8, 40))
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            print("  retry", path[:60], type(e).__name__)
            time.sleep(2 + attempt * 3)
    return None


found = {}
for name in SEARCH:
    for x in (get(f"Instrument/GetInstrumentSearch/{name}") or {}).get("instrumentSearch", []):
        title = (x.get("lVal30") or "").replace("ي", "ی").replace("ك", "ک")
        sym = (x.get("lVal18AFC") or "").replace("ي", "ی").replace("ك", "ک")
        if "صندوق" in title and ("ثابت" in title or sym in SEARCH) and not sym.endswith(("ح", "1")):
            found[x["insCode"]] = (sym, title)
print(len(found), "candidates")
out = {}
for code, (sym, title) in found.items():
    prices = (get(f"ClosingPrice/GetClosingPriceDailyList/{code}/0") or {}).get("closingPriceDaily", [])
    if len(prices) < 250:
        continue
    out[code] = {"symbol": sym, "title": title,
                 "prices": [{"date": str(p["dEven"]), "close": p["pDrCotVal"], "final": p["pClosing"], "value": p["qTotCap"]}
                            for p in prices]}
    print(f"  {sym:10} {title[:40]:40} {len(prices):5} days  {prices[-1]['dEven']} -> {prices[0]['dEven']}")
    time.sleep(0.4)
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
print("wrote", OUT)
