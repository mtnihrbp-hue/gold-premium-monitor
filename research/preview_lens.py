"""Render tonight's LENS from live data without sending it (SP_D_HANDOFF.md section 86): the platforms through
the production collectors, world gold and the dollar through production's readers, or tgju's last closes when
those fail, then analysis/lens.build_view and the message. Prints the message and its length; sends nothing.
The headlines are read by the AI model only where GROQ_API_KEY is set (GitHub's runner).

    python research/preview_lens.py
"""

import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
sys.stdout.reconfigure(encoding="utf-8")

from collector.iran import get_market_prices  # noqa: E402
from collector.tgju import fetch_daily_candles  # noqa: E402


def main():
    markets = get_market_prices()
    try:
        from collector.kitco import get_world_gold_price
        world = get_world_gold_price()
    except Exception:  # noqa: BLE001
        world = None
    try:
        from collector.bonbast import get_usd_sell_rate
        usd = get_usd_sell_rate() * 10
    except Exception:  # noqa: BLE001
        usd = None
    if not world:
        world = fetch_daily_candles("ons", rows=1)[0]["close"]
        print(f"(world gold from tgju's last close: {world})")
    if not usd:
        usd = fetch_daily_candles("price_dollar_rl", rows=1)[0]["close"]
        print(f"(the dollar from tgju's last close: {usd})")
    from analysis.lens import build_view
    from alerts.telegram_lens import build_lens_message
    view = build_view(markets, world, usd, datetime.utcnow())
    text = build_lens_message(view)
    print(text)
    print(f"\n[{len(re.sub(r'</?[bi]>', '', text))} characters of 4,096; headlines read {view['headlines']}]")


if __name__ == "__main__":
    main()
