"""tgju's daily histories of the candidate drivers the research table needs beyond 18K, the dollar and the ounce
(SP_D_HANDOFF.md section 72): the Emami coin, the Bahar Azadi coin, the bazaar's melted gold (mesghal), Tether; and fresh copies of 18K,
the dollar and the ounce (tgju_history.json stays as 66.2 used it).
Saved to research/data/tgju_more.json (git-ignored). Read from the workstation directly: tgju answers Iran.

    python research/fetch_tgju_more.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

import requests  # noqa: E402

_session = requests.Session()
_session.trust_env = False        # Iranian sites direct, not through the system proxy
requests.get = _session.get

from collector.tgju import fetch_daily_candles  # noqa: E402

KEYS = ("geram18", "price_dollar_rl", "ons", "sekee", "sekeb", "mesghal", "crypto-tether-irr", "nim", "rob")


def main():
    out = {}
    for key in KEYS:
        try:
            rows = fetch_daily_candles(key, 6000, order="desc")
            rows = sorted(rows, key=lambda r: r["date"])
            out[key] = rows
            print(f"{key}: {len(rows)} days, {rows[0]['date']} to {rows[-1]['date']}, last close {rows[-1]['close']:,.0f}")
        except Exception as e:  # noqa: BLE001
            print(f"{key}: {type(e).__name__}: {str(e)[:120]}")
    with open(os.path.join(HERE, "data", "tgju_more.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)


if __name__ == "__main__":
    main()
