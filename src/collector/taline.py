import requests

URL = "https://app.tlyn.ir/api/v1/get-price"


def get_taline_price():
    response = requests.get(URL, timeout=15)
    response.raise_for_status()

    data = response.json()

    return {
        "platform": "Milli",
        "price": float(data["price"]["price"])
    }
