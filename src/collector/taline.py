import re
import time

import requests
from bs4 import BeautifulSoup

URL = "https://taline.ir/goldprice/"

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
        raise ValueError(f"Unable to parse price from: {text!r}")
    return float(digits)


PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
BUY_LABEL, SELL_LABEL = "قیمت خرید طلا", "قیمت فروش طلا"


def sides(text):
    """{"buy", "sell"} in rial from the page's calculator block ("قیمت خرید طلا: ۲۶,۲۹۴,۷۰۰ قیمت فروش طلا:
    ۲۶,۰۸۵,۲۰۰", toman, Persian digits), or {} when either is missing or they are not in order. `price`
    stays the page's 18K label, which sits between them (SP_D_HANDOFF.md section 37.7)."""
    found = {}
    for key, label in (("buy", BUY_LABEL), ("sell", SELL_LABEL)):
        m = re.search(label + r"\s*:?\s*([0-9۰-۹,٬]+)", text)
        if m:
            digits = re.sub(r"[^0-9]", "", m.group(1).translate(PERSIAN_DIGITS))
            if digits:
                found[key] = float(digits) * 10
    if "buy" in found and "sell" in found and 0 < found["sell"] <= found["buy"]:
        return found
    return {}


def get_taline_price():
    # The page sits behind a CDN that, on 2026-09-29, served GitHub's non-Iranian
    # runners copies up to a day old while serving Iran the live price (SP_C_HANDOFF.md
    # section 37.2). Ask for a fresh copy explicitly. The stale copies were
    # intermittent, so this is hardening rather than a proven cure; the confirmation
    # check in analysis/confirmation.py is what stops a stale price from alerting.
    response = requests.get(
        URL,
        headers={**HEADERS, "Cache-Control": "no-cache", "Pragma": "no-cache"},
        params={"_": int(time.time())},
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

            result = {
                "platform": "Taline",
                "price": parse_price(raw_text) *10,  # Toman → Rial
                "raw": raw_text,
            }
            result.update(sides(soup.get_text(" ", strip=True)))
            return result

    raise RuntimeError("18K gold price not found.")
