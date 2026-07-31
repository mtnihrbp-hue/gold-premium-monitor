import re
import requests
from bs4 import BeautifulSoup


URL = "https://eligoldgallery.com/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/138.0 Safari/537.36"
    )
}


def parse_price(text: str) -> int:
    """
    Extract gold price from Persian gold text.

    Example:
    'قیمت طلای 18 عیار 18,602,000 تومان'
    returns:
    18602000
    """

    matches = re.findall(
        r"\d[\d,]*",
        text
    )

    if not matches:
        raise ValueError(
            f"Unable to extract numeric value from: {text!r}"
        )

    # Last number is the actual price
    price = matches[-1]

    return int(
        price.replace(",", "")
    )


def get_eligold_price():

    response = requests.get(
        URL,
        headers=HEADERS,
        timeout=15,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    selectors = [
        ".head-price p",
        ".elementor-widget-container p",
        ".elementor-widget-container",
        "p",
        "span",
        "div",
    ]

    price_element = None

    price_pattern = re.compile(
        r"قیمت.*?18.*?عیار.*?\d[\d,]*.*?تومان"
    )

    for selector in selectors:

        elements = soup.select(selector)

        for element in elements:

            text = element.get_text(
                " ",
                strip=True
            )

            if price_pattern.search(text):
                price_element = element
                break

        if price_element:
            break


    if price_element is None:
        raise RuntimeError(
            "Could not locate Eligold gold price element."
        )


    raw_text = price_element.get_text(
        " ",
        strip=True
    )


    return {
        "platform": "Eligold",
        "price": parse_price(raw_text) * 10,
        "raw": raw_text,
    }
