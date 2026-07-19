import requests

URL = "https://api.wallgold.ir/api/v1/price?side=buy&symbol=GLD_18C_750TMN"


def get_wallgold_price():
    response = requests.get(URL, timeout=15)
    response.raise_for_status()

    data = response.json()

    return {
        "platform": "WallGold",
        "price": float(data["result"]["price"]) * 10
    }
