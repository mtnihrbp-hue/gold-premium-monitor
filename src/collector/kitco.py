import json
import requests


API_URL_1 = "https://api.kitco.com/sse/full"
API_URL_2 = "https://api.gold-api.com/price/XAU"
API_URL_3 = "https://data-asg.goldprice.org/dbXRates/USD"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/138.0 Safari/537.36"
    ),
    "Accept": "application/json",
}



def _try_kitco_sse():
    """Primary: Kitco SSE stream."""
    response = requests.get(API_URL_1, timeout=10)
    response.raise_for_status()

    # SSE format: lines like "data: {...json...}"
    for line in response.text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue

        json_str = line[5:].strip()
        if not json_str:
            continue

        try:
            payload = json.loads(json_str)
        except json.JSONDecodeError:
            continue

        pm_list = payload.get("PreciousMetals", {}).get("PM", [])
        if pm_list and "asset_price" in pm_list[0]:
            return float(pm_list[0]["asset_price"])

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


def get_world_gold_price():
    """Fetch world gold spot price with 3-level fallback.

    Returns:
        float price in USD/oz, or None if all sources fail.
    """
    sources = [
        ("gold-api.com", _try_gold_api),
        ("kitco.com/sse", _try_kitco_sse),
        ("goldprice.org", _try_goldprice_org),
    ]

    for name, fetch in sources:
        try:
            price = fetch()
            print(f"  World Gold   {name:<20} ${price:,.2f}")
            return price
        except Exception as e:
            print(f"  World Gold   {name:<20} FAILED ({e})")
            continue

    print("  World Gold   ALL SOURCES FAILED")
    return None
