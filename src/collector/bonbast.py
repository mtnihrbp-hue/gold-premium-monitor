import requests
from bs4 import BeautifulSoup


URL = "https://www.bonbast.com"


def get_usd_sell_rate():
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    r = requests.get("https://www.bonbast.com", headers=headers, timeout=20)
    r.raise_for_status()

    print(r.text[:5000])

    raise RuntimeError("STOP")
