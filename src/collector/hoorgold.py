import requests
from bs4 import BeautifulSoup

URL = "https://hoorgold.com/"


def get_hoorgold_price():
    response = requests.get(URL, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Target: <span class="gold-cost">18,900,000 تومان</span>
    cost_span = soup.select_one("span.gold-price-18 span.gold-cost")
    if not cost_span:
        raise ValueError("Price element not found on page")

    raw_text = cost_span.get_text(strip=True)

    # Remove "تومان", commas, and whitespace → "18900000"
    cleaned = raw_text.replace("تومان", "").replace(",", "").replace(" ", "").strip()

    price = float(cleaned)

    # NOTE: The site displays prices in Tomans. If your other collectors
    # return Rials (1 Toman = 10 Rials), uncomment the next line:
    # price *= 10

    return {
        "platform": "HoorGold",
        "price": price,
    }
