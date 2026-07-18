import requests


API_URL = "https://api.gold-api.com/price/XAU"


def get_world_gold_price() -> float:
    response = requests.get(API_URL, timeout=15)
    response.raise_for_status()

    data = response.json()

    if "price" not in data:
        raise RuntimeError("Gold price not found in API response.")

    return float(data["price"])
