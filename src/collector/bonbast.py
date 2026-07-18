import requests
from bs4 import BeautifulSoup


def get_usd_sell_rate():
    url = "https://www.bonbast.com"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    r = requests.get(url, headers=headers, timeout=20)

    soup = BeautifulSoup(r.text, "html.parser")

    for table in soup.find_all("table"):
        print("=" * 80)
        print(table.get_text(" ", strip=True))
        print("=" * 80)

    raise RuntimeError("STOP")
