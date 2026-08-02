import re
import requests
from bs4 import BeautifulSoup

URL = "https://taline.ir/goldprice/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/138.0 Safari/537.36"
    )
}


def parse_price(text: str) -> float:
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        raise ValueError(f"Unable to parse price from: {text!r}")
    return float(digits)


def get_taline_price():
    response = requests.get(
        URL,
        headers=HEADERS,
        timeout=10,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    labels = soup.select("span.elementor-heading-title")

    for i, label in enumerate(labels):
        if "قیمت ۱گرم طلای ۱۸" in label.get_text(strip=True):
            if i + 1 >= len(labels):
                raise RuntimeError("Price label found but value is missing.")

            raw_text = labels[i + 1].get_text(strip=True)

            return {
                "platform": "Taline",
                "price": parse_price(raw_text) *10,  # Toman → Rial
                "raw": raw_text,
            }

    raise RuntimeError("18K gold price not found.")
