"""G2, the money flow (SP_D_HANDOFF.md section 76): each of the 19 gold funds' whole TSETMC history in two
requests, from the workstation in Iran (TSETMC refuses addresses outside Iran): individuals' and institutions'
buys and sells by value and count (ClientType/GetClientTypeHistory), and the daily prices (ClosingPrice/
GetClosingPriceDailyList). Writes research/data/tsetmc_full.json (git-ignored).

    python research/fetch_tsetmc_full.py
"""

import json
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "iran_node"))
import node  # noqa: E402 -- the one list of the 19 gold funds

S = requests.Session()
S.trust_env = False
S.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"})
BASE = "https://cdn.tsetmc.com/api"


def get(url):
    for attempt in range(4):
        try:
            r = S.get(url, timeout=(10, 90))
            if r.ok:
                return r.json()
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2 + 3 * attempt)
    return None


def main():
    out = {}
    for code, name in node.GOLD_FUNDS:
        flows = get(f"{BASE}/ClientType/GetClientTypeHistory/{code}") or {}
        prices = get(f"{BASE}/ClosingPrice/GetClosingPriceDailyList/{code}/0") or {}
        out[code] = {"name": name, "flows": flows.get("clientType", []), "prices": prices.get("closingPriceDaily", [])}
        f, p = out[code]["flows"], out[code]["prices"]
        span = lambda xs, k: (min(str(x[k]) for x in xs), max(str(x[k]) for x in xs)) if xs else ("-", "-")
        print(f"{name}: {len(f)} flow days {span(f, 'recDate')}, {len(p)} price days {span(p, 'dEven')}", flush=True)
        time.sleep(0.5)
    with open(os.path.join(HERE, "data", "tsetmc_full.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)


if __name__ == "__main__":
    main()
