import requests

URL = "https://api.goldika.ir/api/public/price"


def get_goldika_price():
    response = requests.get(URL, timeout=15)
    response.raise_for_status()

    data = response.json()

    return {
        "platform": "Goldika",
        "price": float(data["data"]["price"]["buy"])
    }
