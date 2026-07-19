import re
import requests

URL = "https://taline.ir/"


def persian_to_english(text):
    return text.translate(str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹",
        "0123456789"
    ))


def get_taline_price():
    response = requests.get(
        URL,
        timeout=15,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response.raise_for_status()

    html = response.text

    match = re.search(
        r"نرخ فعلی طلا.*?([\d,۰-۹]+)",
        html,
        re.S
    )

    if not match:
        raise RuntimeError("Taline price not found.")

    price = persian_to_english(match.group(1))
    price = float(price.replace(",", ""))

    return {
        "platform": "Taline",
        "price": price
    }
