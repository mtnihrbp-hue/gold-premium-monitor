"""The ceasefire's odds as real money prices them (SP_D_HANDOFF.md sections 84-86): Polymarket's markets "US x
Iran ceasefire continues through <Month> <day>?", read from its public API (no key). The lens shows them; nothing
here forecasts. GitHub's runner reaches it direct; the workstation through Psiphon (the system proxy).

Returns [(end date, probability the ceasefire holds, dollars traded)], soonest first, or [] when the API cannot be
read or no such market is open. Never raises."""

import json
import re
from datetime import date, datetime

import requests

API = "https://gamma-api.polymarket.com/markets"
QUESTION = re.compile(r"^US x Iran ceasefire continues through ([A-Z][a-z]+) (\d{1,2})\?$")
MONTHS = {m: i for i, m in enumerate(("January", "February", "March", "April", "May", "June", "July", "August",
                                      "September", "October", "November", "December"), start=1)}
TIMEOUT = (6, 20)


def parse(markets, today):
    """The ceasefire ladder from the API's market list: one row per date from today on, soonest first."""
    out = {}
    for m in markets or ():
        found = QUESTION.match((m.get("question") or "").strip())
        if not found or found.group(1) not in MONTHS:
            continue
        try:
            year = int((m.get("endDate") or "")[:4])
            end = date(year, MONTHS[found.group(1)], int(found.group(2)))
            yes = float(json.loads(m.get("outcomePrices") or "[]")[0])
            traded = float(m.get("volume") or 0)
        except (ValueError, IndexError, TypeError):
            continue
        if end >= today and 0.0 <= yes <= 1.0:
            out[end] = (end, yes, traded)
    return [out[k] for k in sorted(out)]


def ceasefire_odds(now=None):
    now = now or datetime.utcnow()
    try:
        r = requests.get(API, params={"active": "true", "closed": "false", "limit": 300, "order": "volume24hr",
                                      "ascending": "false"}, timeout=TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        return parse(r.json(), now.date())
    except Exception as e:  # noqa: BLE001 -- the lens says the odds were not read
        print(f"POLYMARKET: not read: {type(e).__name__}: {str(e)[:120]}")
        return []
