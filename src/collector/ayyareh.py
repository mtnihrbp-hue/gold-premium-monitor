import requests

URL = "https://ayyareh.com/general/getGoldPrice.php"


def get_ayyareh_price():
    response = requests.get(URL, timeout=15)
    response.raise_for_status()

    data = response.json()

    return {
        "platform": "Milli",
        "price": float(data["data"]["goldPrice"])
    }
