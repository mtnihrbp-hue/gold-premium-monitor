import requests

URL = "https://milli.gold/api/v1/public/milli-price/external"


def get_milli_price():
    response = requests.get(URL, timeout=15)
    response.raise_for_status()

    data = response.json()

    return {
        "platform": "Milli",
        "priceIRR": float(data["data"]["price18"]) *1000
    }
