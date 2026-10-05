"""etfbaz.com's public landing figures: the dollar in Tether, the bazaar's melted-gold quote, and the
stock index (SP-D, SP_D_HANDOFF.md section 27).

GitHub's runner reaches api.etfbaz.com (Nobitex it does not: section 26), so Tether (USDT/IRR), which
trades through the night and the Iranian weekend, arrives without the Iran-side collector. One public
endpoint its own page reads, no key: /instrument/landing, sections of {"symbol", "price"} items.
Today's values only; production records one a day for a future member. Collects only; main stores.
Never raises.
"""

import requests

URL = "https://api.etfbaz.com/instrument/landing"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36",
           "Accept": "application/json", "Origin": "https://etfbaz.com", "Referer": "https://etfbaz.com/"}
TIMEOUT = (5, 15)
# etfbaz's symbol -> the name stored
SYMBOLS = {"USDT": "ETFBAZ_USDT_IRR", "USD": "ETFBAZ_USD_IRR", "مظنه آبشده نقدی (اتحادیه)": "ETFBAZ_MELTED_GOLD",
           "طلا گرم 18 عیار": "ETFBAZ_GOLD_18K", "انس طلا": "ETFBAZ_XAU_USD", "شاخص کل": "ETFBAZ_TEDPIX"}


def collect():
    """{stored name: price}, and "errors"."""
    out = {"errors": []}
    try:
        r = requests.get(URL, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        for section in r.json():
            for item in section.get("items") or []:
                name = SYMBOLS.get(item.get("symbol"))
                price = item.get("price")
                if name and isinstance(price, (int, float)) and price > 0:
                    out[name] = float(price)
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"landing: {type(e).__name__}")
    return out
