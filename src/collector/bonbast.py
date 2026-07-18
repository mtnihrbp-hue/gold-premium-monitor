import requests
from bs4 import BeautifulSoup


URL = "https://www.bonbast.com"


def get_usd_sell_rate():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/137.0 Safari/537.36"
        )
    }

    response = requests.get(URL, headers=headers, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    usd_row = soup.find("td", string="USD")

    if usd_row is None:
        raise RuntimeError("USD row not found.")

    row = usd_row.parent

    cells = row.find_all("td")

    if len(cells) < 4:
        raise RuntimeError("Unexpected Bonbast table format.")

    sell_text = cells[2].get_text(strip=True)

    sell_text = sell_text.replace(",", "")

    return int(sell_text)
