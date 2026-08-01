import re
import requests
from bs4 import BeautifulSoup

URL = "https://hoorgold.com/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/138.0 Safari/537.36"
    )
}


def parse_price(text: str) -> float:
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        raise ValueError(f"Unable to extract numeric value from: {text!r}")
    return float(digits)


def get_hoorgold_price():
    response = requests.get(
        URL,
        headers=HEADERS,
        timeout=10,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    selectors = [
        "span.gold-price-18 span.gold-cost",
        ".gold-price-18 .gold-cost",
        ".gold-cost",
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
        "platform": "HoorGold",
        "price": parse_price(raw_text) *10,
        "raw": raw_text,
    }
