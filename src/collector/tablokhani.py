"""tablokhani.com's public figures: the Tehran stock index and each fund's last close and smart-money
averages (SP-D, SP_D_HANDOFF.md section 27).

GitHub's runner reaches api.tablokhani.com (TSETMC and fipiran it does not: section 26). Two public
endpoints its own pages read, no key:

  /public/market-indices         TEDPIX ("bourse" -> "index", "state" open or closed)
  /public/smart-money-averages   per symbol: individuals' 10-day average per-capita buy and sell, the
                                 buyer and seller counts, RSI14, MA20 and the last close
                                 ("closing_1d_ago") -- Afran's close values the PAPER room's fixed income

Today's values only; production stores one reading a day and the history before it comes from
src/seed (research/build_seeds.py). Collects only; main stores. Never raises.

The gold funds are the seed's 19 (src/seed/gold_fund_daily.json, the phone's list in iran_node/node.py
without saffron), so their 10-day figures stand in for the 7-day reading while the database is out of
reach (SP_D_HANDOFF.md section 47). Each fund's averages come back in rial a day: the per-head figures
are million toman. Until 2026-10-17 the list had رز, which tablokhani does not list, in place of درنا
and گلدیس; گنج, about 4% of individuals' buying, joined the seed and the phone the same day (section 48).
"""

import requests

BASE = "https://api.tablokhani.com/public"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36",
           "Accept": "application/json", "Origin": "https://tablokhani.com", "Referer": "https://tablokhani.com/"}
TIMEOUT = (5, 15)
AFRAN = "افران"
GOLD_FUNDS = ("عیار", "طلا", "زر", "گوهر", "کهربا", "آلتون", "مثقال", "نفیس", "جواهر", "زروان", "تابش", "ناب",
              "قیراط", "درخشان", "لیان", "درنا", "زرفام", "گلدیس", "گنج")
MILLION_TOMAN = 1e7                      # rial


def _number(text):
    try:
        return float(str(text).replace(",", ""))
    except (TypeError, ValueError):
        return None


def collect():
    """{"tedpix", "tse_state", "afran_close", "funds": {symbol: {...}}, "flows": {symbol: (buy value, buyers,
    sell value, sellers)}, "errors": [...]}: "flows" are individuals' 10-day averages a day, values in rial."""
    out = {"tedpix": None, "tse_state": None, "afran_close": None, "funds": {}, "flows": {}, "errors": []}
    try:
        r = requests.get(f"{BASE}/market-indices", headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        bourse = (r.json().get("data") or {}).get("bourse") or {}
        out["tedpix"] = _number(bourse.get("index"))
        out["tse_state"] = bourse.get("state")
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"market-indices: {type(e).__name__}")
    try:
        r = requests.get(f"{BASE}/smart-money-averages", headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json().get("data") or {}
        afran = data.get(AFRAN) or {}
        out["afran_close"] = _number(afran.get("closing_1d_ago"))
        out["funds"] = {s: data[s] for s in GOLD_FUNDS if s in data}
        for s, f in out["funds"].items():
            nums = [_number(f.get(k)) for k in ("avg_real_buy_count_10d", "avg_per_capita_buy_10d",
                                                 "avg_real_sell_count_10d", "avg_per_capita_sell_10d")]
            if all(x is not None for x in nums):
                bc, pb, sc, ps = nums
                out["flows"][s] = (bc * pb * MILLION_TOMAN, bc, sc * ps * MILLION_TOMAN, sc)
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"smart-money-averages: {type(e).__name__}")
    return out
