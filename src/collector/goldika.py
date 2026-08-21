import requests

URL = "https://api.goldika.ir/api/public/price"


def get_goldika_price():
    response = requests.get(URL, timeout=10)
    response.raise_for_status()

    data = response.json()

    result = {
        "platform": "Goldika",
        "price": float(data["data"]["price"]["buy"]),
    }
    # Preserve explicit buy/sell semantics for C.14A candle infrastructure
    try:
        result["buy"] = float(data["data"]["price"]["buy"])
        result["sell"] = float(data["data"]["price"]["sell"])
    except (KeyError, TypeError):
        pass

    return result
