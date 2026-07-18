import re
import requests
from bs4 import BeautifulSoup

URL = "https://www.bonbast.com/"


def get_usd_sell_rate():
    """
    Returns USD sell price in IRR as integer.

    Example:
        1034500
    """

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/137.0 Safari/537.36"
        )
    }

    response = requests.get(URL, headers=headers, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    text = soup.get_text(" ", strip=True)

    # Find numbers appearing near USD / Dollar
    patterns = [
        r"USD.*?([0-9,]{5,})",
        r"US Dollar.*?([0-9,]{5,})",
        r"دلار.*?([0-9,]{5,})",
    ]

    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return int(m.group(1).replace(",", ""))

    raise RuntimeError("Unable to locate USD sell rate on Bonbast.")
