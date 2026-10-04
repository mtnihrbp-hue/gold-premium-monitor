import requests

URL = "https://apisc.daric.gold/loan/api/v1/User/Collateral/GetGoldlPrice"


def get_daric_price():
    response = requests.get(
        URL,
        timeout=15,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response.raise_for_status()

    data = response.json()

    # Daric is an order book: BestSellPrice is the lowest offer (what a buyer pays),
    # BestBuyPrice the highest bid (what a seller is paid). Toman, hence x10.
    ask = float(data["Data"]["BestSellPrice"]) * 10
    bid = float(data["Data"]["BestBuyPrice"]) * 10
    return {
        "platform": "Daric",
        "price": ask,
        "buy": ask,
        "sell": bid,
    }
