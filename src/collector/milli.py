import requests


URL = "https://milli.gold/api/v1/public/milli-price/external"


def get_milli_price():

    r = requests.get(URL, timeout=15)

    r.raise_for_status()

    data = r.json()

    return int(data["price"])
