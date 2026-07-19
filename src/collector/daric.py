import requests

URL = "https://apisc.daric.gold/loan/api/v1/User/Collateral/GetGoldlPrice"


def get_daric_price():
    response = requests.get(URL, timeout=15)
    response.raise_for_status()

    data = response.json()

    return {
        "platform": "Daric",
        "priceIRR": float(data["Data"]["BestSellPrice"*10])
    }
