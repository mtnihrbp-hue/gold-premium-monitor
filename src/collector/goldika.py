"""Goldika's 18K price, with the time Goldika set it.

The API stamps every price (`createdAt`, UTC). That stamp is why this quote can be
judged stale exactly: on 2026-10-01 the Sotoon CDN began serving the non-Iranian
runner a copy priced 2026-09-13 while Iranian clients got the live price, and any
uncached request from abroad returns 502 (SP_C_HANDOFF.md section 44).
`validation.data` discards a quote whose stamp is too old.
"""

from datetime import datetime

import requests

URL = "https://api.goldika.ir/api/public/price"


def _utc(stamp):
    """'2026-10-02T07:45:18.000000Z' -> naive UTC, or None."""
    try:
        return datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def get_goldika_price():
    response = requests.get(URL, timeout=10)
    response.raise_for_status()

    data = response.json()
    price = data["data"]["price"]

    result = {
        "platform": "Goldika",
        "price": float(price["buy"]),
        "quoted_at": _utc(price.get("createdAt") or price.get("created_at")),
    }
    # Preserve explicit buy/sell semantics for C.14A candle infrastructure
    try:
        result["buy"] = float(price["buy"])
        result["sell"] = float(price["sell"])
    except (KeyError, TypeError):
        pass

    return result
