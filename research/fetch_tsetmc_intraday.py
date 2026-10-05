"""TSETMC intraday data for the gold funds and the coin certificates (SP-D, 2026-10-05).

The owner: TSETMC access will come from an Iran-side server; for the R&D, fetch it from this
machine. Direct (trust_env=False), about one request a second, condensed as it arrives:

  minute bars   ClosingPrice/GetClosingPriceHistory/{ins}/{day}: the cumulative volume, value
                and trade count with the last price, cut into one-minute bars
                (open, high, low, close, volume, value, trades) and the day's final price
  trades        Trade/GetTradeHistory/{ins}/{day}/false on a sample of days: the value traded
                in large tickets (each trade's value against fixed bands), by minute
  order book    BestLimits/{ins}/{day} on the same sample: the top-five depth on each side,
                the spread and the imbalance, sampled each minute
  coin certificates   daily prices and the individual / institutional flow of the bank-vault
                coin certificates (tamam sekeh tarh-e jadid) traded on the commodity exchange

Writes research/data/tsetmc_intraday/*.json (git-ignored). Resumable: days already fetched
are skipped.
"""
import json
import os
import sys
import time
from collections import defaultdict

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "tsetmc_intraday")
os.makedirs(OUT, exist_ok=True)
B = "https://cdn.tsetmc.com/api"
S = requests.Session()
S.trust_env = False
S.headers.update({"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
FUNDS = {"عيار": "34144395039913458", "طلا": "46700660505281786"}
COINS = {"سكه0412پ03": "31447590411939048", "سكه0411پ02": "31916786560891464", "سكه0312پ01": "16255851958781005",
         "سكه0211پ02": "1626855364269097", "سكه0211پ04": "38139308735712080", "سكه0112پ03": "57675016001659793",
         "سكه0111پ05": "16382005745854279", "سكه0012پ01": "6183017539978894", "سكه0012پ04": "30799980755729585",
         "سكه0011پ02": "56394387537858740", "سكه9912پ04": "10427474943853556", "سكه9812-02": "40298535551132385",
         "سكه9812-03": "9657290597210645", "ربع سكه0312ن06": "69928201688954493"}
FIRST_DAY, LAST_DAY = 20231001, 20261004
SAMPLE_EVERY = 8              # trades and the order book on every 8th trading day


def get(path, timeout=90):
    for attempt in range(4):
        try:
            r = S.get(f"{B}/{path}", timeout=(8, timeout))
            if r.status_code == 200:
                return r.json()
            if r.status_code in (404, 400):
                return None
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2 + 3 * attempt)
    return None


def minute_bars(rows):
    rows = sorted((x for x in rows if x["hEven"] < 180000 and x["qTotTran5J"] > 0), key=lambda x: x["hEven"])
    bars, prev = {}, (0.0, 0.0, 0.0)
    for x in rows:
        m = x["hEven"] // 100
        p = x["pDrCotVal"]
        b = bars.get(m)
        if b is None:
            bars[m] = b = [m, p, p, p, p, 0.0, 0.0, 0.0]
        b[2], b[3], b[4] = max(b[2], p), min(b[3], p), p
        dv, dc, dt = x["qTotTran5J"] - prev[0], x["qTotCap"] - prev[1], x["zTotTran"] - prev[2]
        b[5] += max(dv, 0)
        b[6] += max(dc, 0)
        b[7] += max(dt, 0)
        prev = (x["qTotTran5J"], x["qTotCap"], x["zTotTran"])
    final = next((x["pClosing"] for x in rows[::-1]), None)
    return [bars[k] for k in sorted(bars)], final


BANDS = (1e9, 1e10, 5e10)      # rial per trade: under 100M toman, 100M-1B, 1B-5B, over 5B toman


def trade_summary(rows):
    by_min = defaultdict(lambda: [0.0] * (len(BANDS) + 1))
    for x in rows:
        if x.get("canceled"):
            continue
        v = x["qTitTran"] * x["pTran"]
        k = sum(v >= b for b in BANDS)
        by_min[x["hEven"] // 100][k] += v
    return [[m] + by_min[m] for m in sorted(by_min)]


def book_summary(rows):
    """Top-five depth each minute (the state after the last change in that minute)."""
    state = {}
    out = {}
    for x in sorted(rows, key=lambda x: (x["hEven"], x["refID"])):
        state[x["number"]] = (x["qTitMeDem"], x["pMeDem"], x["qTitMeOf"], x["pMeOf"])
        m = x["hEven"] // 100
        bid = sum(v[0] for v in state.values())
        ask = sum(v[2] for v in state.values())
        b1 = state.get(1, (0, 0, 0, 0))
        out[m] = [m, bid, ask, b1[1], b1[3]]
    return [out[k] for k in sorted(out)]


def fund_days(ins):
    j = get(f"ClosingPrice/GetClosingPriceDailyList/{ins}/0") or {}
    return sorted(int(p["dEven"]) for p in j.get("closingPriceDaily", []) if FIRST_DAY <= int(p["dEven"]) <= LAST_DAY
                  and p.get("qTotTran5J", 0) > 0)


def main():
    t0 = time.time()
    # coin certificates: daily
    coins_path = os.path.join(OUT, "coin_certificates.json")
    if not os.path.exists(coins_path):
        coins = {}
        for sym, ins in COINS.items():
            daily = (get(f"ClosingPrice/GetClosingPriceDailyList/{ins}/0") or {}).get("closingPriceDaily", [])
            flows = (get(f"ClientType/GetClientTypeHistory/{ins}") or {}).get("clientType", [])
            coins[sym] = {"ins": ins, "prices": [{"date": p["dEven"], "close": p["pDrCotVal"], "final": p["pClosing"],
                                                  "high": p["priceMax"], "low": p["priceMin"], "volume": p["qTotTran5J"],
                                                  "value": p["qTotCap"]} for p in daily], "flows": flows}
            print(f"coin {sym}: {len(daily)} days", flush=True)
            time.sleep(0.7)
        json.dump(coins, open(coins_path, "w", encoding="utf-8"), ensure_ascii=False)
    for sym, ins in FUNDS.items():
        path = os.path.join(OUT, f"{ins}.json")
        data = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"symbol": sym, "days": {}}
        days = fund_days(ins)
        print(f"{sym}: {len(days)} trading days to cover, {len(data['days'])} already", flush=True)
        for n, day in enumerate(days):
            key = str(day)
            if key in data["days"]:
                continue
            rec = {}
            j = get(f"ClosingPrice/GetClosingPriceHistory/{ins}/{day}")
            if j:
                rec["bars"], rec["final"] = minute_bars(j.get("closingPriceHistory", []))
            if n % SAMPLE_EVERY == 0:
                t = get(f"Trade/GetTradeHistory/{ins}/{day}/false", timeout=180)
                if t:
                    rec["trades"] = trade_summary(t.get("tradeHistory", []))
                bl = get(f"BestLimits/{ins}/{day}", timeout=180)
                if bl:
                    rec["book"] = book_summary(bl.get("bestLimitsHistory", []))
            data["days"][key] = rec
            if len(data["days"]) % 20 == 0:
                json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False)
                print(f"  {sym} {day}: {len(data['days'])}/{len(days)}  {time.time() - t0:.0f}s", flush=True)
            time.sleep(0.6)
        json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"{sym}: done, {len(data['days'])} days", flush=True)
    print(f"all done in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
