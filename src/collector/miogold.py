import re
import requests
from bs4 import BeautifulSoup

URL = "https://mio-gold.ir/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/138.0 Safari/537.36"
    )
}


# 3s to establish connection, 10s to read response
REQUEST_TIMEOUT = (5, 10)

# Reject pages larger than 2MB (prevents infinite stream hangs)
MAX_HTML_SIZE = 3 * 1024 * 1024



def parse_price(text: str) -> float:
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        raise ValueError(f"Unable to extract numeric value from: {text!r}")
    return float(digits)


def get_miogold_price():
    response = requests.get(
        URL,
        headers=HEADERS,
        timeout=10,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    selectors = [
        "#lbPrice",
        "span#lbPrice",
        "span.price",
    ]
        

    price_element = None
    for selector in selectors:
        price_element = soup.select_one(selector)
        if price_element:
            break

    if price_element is None:
        raise RuntimeError("Could not locate 18K gold price element.")

    raw_text = price_element.get_text(" ", strip=True)

    return {
        "platform": "MioGold",
        "price": parse_price(raw_text) *10,
        "raw": raw_text,
    }
