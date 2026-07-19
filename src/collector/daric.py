import requests

URL = "https://apisc.daric.gold/loan/api/v1/User/Collateral/GetGoldlPrice"


def get_daric_price():
    response = requests.get(
        URL,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response.raise_for_status()

    data = response.json()

    return {
        "platform": "Daric",
        "price": float(data["Data"]["BestSellPrice"]) * 10
    }
