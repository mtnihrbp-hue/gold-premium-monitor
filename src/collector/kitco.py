"""World gold (XAU/USD) from a chain of four sources, bounded as a whole.

Until 2026-09-30 the chain could hang a run. Kitco's endpoint is an event stream that
never closes, and it was read whole, so every run in which gold-api.com failed waited
inside Kitco until the 20-minute job timeout and wrote nothing: 09-24, 09-25 twice,
09-30 at 13:00 (SP_C_HANDOFF.md sections 33.2 and 42). Kitco is now read line by line
and abandoned after KITCO_SSE_SECONDS, and the whole chain runs under one deadline on
a daemon thread, the pattern collector/iran.py uses since SP-C.9, because requests'
timeout bounds neither a stream's total length nor DNS resolution. A chain that runs
out of time returns None, and main falls back to the last stored price with degraded
provenance, which also holds any signal (world gold is not live).

Kitco had a second, hidden defect: it took the first metal in the stream, often
palladium or platinum. It never mattered only because the read never finished. It now
takes gold by its symbol.
"""

import json
import threading
import time

import requests

# Kitco opens with a snapshot of every metal, one event each: gold arrived 1.2-1.3 s
# after connecting on 2026-09-30 (first byte took 7 s on 09-27).
KITCO_SSE_SECONDS = 15

# The whole chain: four sources, normally one answers within a second. 60 s is the
# bound bonbast has had since SP-C.6.
WORLD_GOLD_DEADLINE_SECONDS = 60


API_URL_1 = "https://api.kitco.com/sse/full"
API_URL_2 = "https://api.gold-api.com/price/XAU"
API_URL_3 = "https://data-asg.goldprice.org/dbXRates/USD"
API_URL_4 = "https://query1.finance.yahoo.com/v8/finance/chart/XAUUSD=X?interval=1d&range=1d"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/138.0 Safari/537.36"
    ),
    "Accept": "application/json",
}



def _try_kitco_sse():
    """Kitco's live event stream: the first gold (Symbol AU) price in it, which
    arrived about 1.2 s after connecting on 2026-09-30.

    The stream never ends, so it is read line by line (stream=True) and abandoned
    after KITCO_SSE_SECONDS. Reading the whole body waited for an end that never
    comes: timeout=10 bounds each read, not the total, and an event arrives about
    every second.
    """
    deadline = time.monotonic() + KITCO_SSE_SECONDS
    with requests.get(API_URL_1, stream=True, timeout=(5, 10)) as response:
        response.raise_for_status()

        # SSE format: lines like "data: {...json...}"
        for raw in response.iter_lines():
            if time.monotonic() > deadline:
                raise TimeoutError(f"no price within {KITCO_SSE_SECONDS}s of the stream")
            line = (raw.decode("utf-8", errors="replace")
                    if isinstance(raw, bytes) else (raw or "")).strip()
            if not line.startswith("data:"):
                continue

            json_str = line[5:].strip()
            if not json_str:
                continue

            try:
                payload = json.loads(json_str)
            except json.JSONDecodeError:
                continue

            # Each event carries one metal, named by Symbol, in no fixed order. Taking
            # the first returned palladium or platinum (1,202 and 1,705 on 09-30,
            # inside the world-gold validation range) whenever it moved first.
            for item in (payload.get("PreciousMetals") or {}).get("PM") or []:
                if item.get("Symbol") == "AU" and "asset_price" in item:
                    return float(item["asset_price"])

    raise RuntimeError("asset_price not found in SSE stream")

def _try_gold_api():
    """Secondary: api.gold-api.com"""
    response = requests.get(API_URL_2, timeout=10)
    response.raise_for_status()
    data = response.json()
    if "price" not in data:
        raise RuntimeError("'price' key missing in response")
    return float(data["price"])


def _try_goldprice_org():
    """Tertiary: goldprice.org public API."""
    response = requests.get(API_URL_3, headers=HEADERS, timeout=10)
    response.raise_for_status()
    data = response.json()

    items = data.get("items", [])
    if not items:
        raise RuntimeError("'items' array empty")

    price = items[0].get("xauPrice")
    if price is None:
        raise RuntimeError("'xauPrice' missing")

    return float(price)

### Yahoo Gold
def _try_yahoo_finance():
    """Primary: Yahoo Finance XAUUSD=X spot price."""
    response = requests.get(API_URL_4, headers=HEADERS, timeout=15)
    response.raise_for_status()
    data = response.json()

    result = data.get("chart", {}).get("result", [])
    if not result:
        raise RuntimeError("No chart result in Yahoo response")

    meta = result[0].get("meta", {})
    price = meta.get("regularMarketPrice") or meta.get("previousClose")
    if price is None:
        raise RuntimeError("No price in Yahoo meta")

    return float(price)




SOURCES = [
    ("gold-api.com", _try_gold_api),
    ("kitco.com/sse", _try_kitco_sse),
    ("goldprice.org", _try_goldprice_org),
    ("yahoo-finance", _try_yahoo_finance),
]


def _first_price(abandoned):
    """The first source that answers, in order. Silent once the caller has given up,
    so a late answer cannot print into the log as if it had been used."""
    for name, fetch in SOURCES:
        try:
            price = fetch()
        except Exception as e:
            if abandoned.is_set():
                return None
            print(f"  World Gold   {name:<20} FAILED ({e})")
            continue
        if abandoned.is_set():
            return None
        print(f"  World Gold   {name:<20} ${price:,.2f}")
        return price

    print("  World Gold   ALL SOURCES FAILED")
    return None


def get_world_gold_price():
    """World gold spot price in USD/oz, or None if no source answers in time.

    The chain runs on a daemon thread under WORLD_GOLD_DEADLINE_SECONDS. A chain still
    running at the deadline is abandoned, not awaited: it cannot hold the run or the
    interpreter, and main falls back to the last stored price.
    """
    result, abandoned = {}, threading.Event()
    thread = threading.Thread(target=lambda: result.update(price=_first_price(abandoned)),
                              daemon=True)
    thread.start()
    thread.join(timeout=WORLD_GOLD_DEADLINE_SECONDS)
    if thread.is_alive():
        abandoned.set()
        print(f"  World Gold   TIMED OUT after {WORLD_GOLD_DEADLINE_SECONDS}s")
        return None
    return result.get("price")
