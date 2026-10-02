"""Milli's 18K price, with the time Milli set it.

The API stamps the price in Tehran local time, without a zone ("date":
"2026-10-02T11:32:00"); it is converted to UTC here, like every stored time.
`validation.data` discards a quote whose stamp is too old (SP_C_HANDOFF.md
section 44).
"""

from datetime import datetime

import requests

from timeutil import to_utc

URL = "https://milli.gold/api/v1/public/milli-price/external"


def _utc(stamp):
    try:
        return to_utc(datetime.fromisoformat(str(stamp)).replace(tzinfo=None))
    except (TypeError, ValueError):
        return None


def get_milli_price():
    response = requests.get(URL, timeout=10)
    response.raise_for_status()

    data = response.json()

    return {
        "platform": "Milli",
        "price": float(data["data"]["price18"]) * 1000,
        "quoted_at": _utc(data["data"].get("date")),
    }
