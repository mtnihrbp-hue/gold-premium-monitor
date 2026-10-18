"""Fetch the Iranian gold funds' daily prices, volume and money flow from TSETMC for the
analyst R&D (SP-D, 2026-10-04). TSETMC answers Iranian addresses only (GitHub's runner is
refused), so this runs from an Iranian connection and writes research/data/
tsetmc_gold_funds.json (git-ignored, like the tgju history).

Per fund and day: open/high/low/close and the final price, volume (units), value (rial),
trade count; and the money flow split between individuals (I) and institutions (N):
buy/sell volume, value and count.

گنج (صندوق س. سيماي كاردان) is a gold fund whose title names neither gold nor a commodity, so the
title filter dropped it until 2026-10-17; it is named in GOLD_BY_SYMBOL (SP_D_HANDOFF.md section 48).
سافرون (صندوق س.كالاي گنجينه زمين) is a saffron fund that the commodity filter let in; it is left out
here, at the source, so nothing downstream counts it (owner, 2026-10-18: "drop the saffron thing totally";
section 49).
"""
import json
import os
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "tsetmc_gold_funds.json")
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
BASE = "https://cdn.tsetmc.com/api"
SEARCH = ("عیار", "طلا", "کهربا", "زر", "گوهر", "مثقال", "آلتون", "جواهر", "نفیس", "زروان", "تابش",
          "قیراط", "ناب", "رز", "درخشان", "لیان", "گنج", "زرفام", "ناب", "سکه")
GOLD_BY_SYMBOL = {"گنج"}             # gold funds whose title does not say so
NOT_GOLD = {"51200575796028449"}     # سافرون, saffron


def get(path):
    for attempt in range(3):
        try:
            r = requests.get(f"{BASE}/{path}", headers=UA, timeout=(8, 40))
            r.raise_for_status()
            return r.json()
        except Exception:
            time.sleep(2 + attempt * 3)
    return None


funds = {}
for name in SEARCH:
    data = get(f"Instrument/GetInstrumentSearch/{name}") or {}
    for x in data.get("instrumentSearch", []):
        title = x.get("lVal30") or ""
        if ("طلا" in title or "كالاي" in title or "کالای" in title or x.get("lVal18AFC") in ("عيار",)
                or x.get("lVal18AFC") in GOLD_BY_SYMBOL):
            if ("صندوق" in title and x.get("lVal18AFC") and not x.get("lVal18AFC").endswith(("ح", "1"))
                    and x["insCode"] not in NOT_GOLD):
                funds[x["insCode"]] = (x.get("lVal18AFC"), title)
print(len(funds), "candidate funds:")
for code, (sym, title) in funds.items():
    print("  ", code, sym, title)

out = {}
for code, (sym, title) in funds.items():
    prices = (get(f"ClosingPrice/GetClosingPriceDailyList/{code}/0") or {}).get("closingPriceDaily", [])
    flows = (get(f"ClientType/GetClientTypeHistory/{code}") or {}).get("clientType", [])
    if len(prices) < 250:
        print(f"skip {sym}: {len(prices)} days")
        continue
    out[code] = {"symbol": sym, "title": title,
                 "prices": [{"date": str(p["dEven"]), "open": p["priceFirst"], "high": p["priceMax"], "low": p["priceMin"],
                             "close": p["pDrCotVal"], "final": p["pClosing"], "volume": p["qTotTran5J"],
                             "value": p["qTotCap"], "trades": p["zTotTran"]} for p in prices],
                 "flows": flows}
    print(f"{sym}: {len(prices)} days of prices ({prices[-1]['dEven']} -> {prices[0]['dEven']}), {len(flows)} days of flow")
    time.sleep(0.5)
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
print("wrote", OUT)
