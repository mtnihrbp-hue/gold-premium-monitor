import json
import re

import requests

URL = "https://invi.ir/gold-price/18carat"


def _normalize_price(value):
    """Normalize Invi's current price to the collector contract."""
    if isinstance(value, (int, float)):
        return float(value)

    digits = re.sub(r"[^\d.]", "", str(value))
    if not digits:
        raise ValueError("Invalid Invi current_price")
    return float(digits)


def get_invi_price():
    response = requests.get(URL, timeout=10)
    response.raise_for_status()

    # Method 1: Try to extract from __NEXT_DATA__ script tag
    try:
        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>',
            response.text,
            re.DOTALL,
        )
        if match:
            data = json.loads(match.group(1))
            current_price = data["props"]["pageProps"]["success"]["result"]["summary"]["current_price"]

            return {
                "platform": "Invi",
                "price": _normalize_price(current_price),
                "status": "OK",
            }
    except (KeyError, json.JSONDecodeError, AttributeError, TypeError, ValueError):
        # Fallback to regex method
        pass

    # Method 2: Direct regex extraction as fallback
    match = re.search(r'"current_price":"(\d+)"', response.text)
    if match:
        raw_text = match.group(1)
        return {
            "platform": "Invi",
            "price": _normalize_price(raw_text),
            "status": "OK",
        }

    raise ValueError("Could not extract current_price from the page")
