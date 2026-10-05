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
"""

import requests

BASE = "https://api.tablokhani.com/public"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36",
           "Accept": "application/json", "Origin": "https://tablokhani.com", "Referer": "https://tablokhani.com/"}
TIMEOUT = (5, 15)
AFRAN = "افران"
GOLD_FUNDS = ("عیار", "طلا", "زر", "گوهر", "کهربا", "آلتون", "مثقال", "نفیس", "جواهر", "زروان", "تابش", "ناب",
              "قیراط", "درخشان", "لیان", "گنج", "زرفام", "رز")


def _number(text):
    try:
        return float(str(text).replace(",", ""))
    except (TypeError, ValueError):
        return None


def collect():
    """{"tedpix", "tse_state", "afran_close", "funds": {symbol: {...}}, "errors": [...]}."""
    out = {"tedpix": None, "tse_state": None, "afran_close": None, "funds": {}, "errors": []}
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
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"smart-money-averages: {type(e).__name__}")
    return out
