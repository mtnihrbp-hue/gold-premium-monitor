"""The dollar and Tether after each kind of news (SP-D, SP_D_HANDOFF.md section 35.8). For Direction's
DOLLAR FROM NEWS line (owner, 2026-10-15: "whenever the cbi intervened the prices dropped. so if the llm
now ... is concluding the cbi intervention from news, so the usd rates or tether will decrease").

Rules, fixed before the run (a first pass on keywords; the AI model's labels replace them later):
- Posts: the owner's six channels, a year back (research/backfill_telegram.py, from GitHub's runner).
- Event types, each a pair of keyword sets that must both appear in one post:
    cbi_intervention  بانک مرکزی | فرزین  AND  مداخله | عرضه ارز | تزریق ارز | عرضه دلار | کنترل بازار ارز | عرضه اسکناس
    talks_progress    مذاکره | مذاکرات | گفتگو  AND  توافق | پیشرفت | مثبت | سازنده | امیدوار
    talks_setback     مذاکره | مذاکرات | گفتگو  AND  تعلیق | شکست | لغو | تعویق | بن‌بست | ناکام | قطع
    sanctions         تحریم | اسنپ | ماشه  AND  جدید | اعمال | بازگشت | فعال | تشدید
    military          حمله | اصابت | موشک | پهپاد | انفجار  AND  اسرائیل | آمریکا | ایران | تهران
- An event day: a Tehran day on which at least two of the six channels carry the type (one channel
  alone is too often a repost or an opinion).
- Outcome: the dollar's (tgju price_dollar_rl) and Tether's (tgju crypto-tether-irr) move from the last
  close before the day to the close 1 and 3 trading days after it. Compared with every day of the same
  span, because the dollar trended through it.
"""

import glob
import gzip
import json
import os
import random
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TEHRAN = timedelta(hours=3, minutes=30)
TYPES = {
    "cbi_intervention": (r"بانک مرکزی|فرزین", r"مداخله|عرضه ارز|تزریق ارز|عرضه دلار|کنترل بازار ارز|عرضه اسکناس"),
    "talks_progress": (r"مذاکره|مذاکرات|گفتگو", r"توافق|پیشرفت|مثبت|سازنده|امیدوار"),
    "talks_setback": (r"مذاکره|مذاکرات|گفتگو", r"تعلیق|شکست|لغو|تعویق|بن‌بست|بن بست|ناکام|قطع"),
    "sanctions": (r"تحریم|اسنپ|ماشه", r"جدید|اعمال|بازگشت|فعال|تشدید"),
    "military": (r"حمله|اصابت|موشک|پهپاد|انفجار", r"اسرائیل|آمریکا|ایران|تهران"),
}
MIN_CHANNELS = 2


def posts():
    for path in sorted(glob.glob(os.path.join(HERE, "data", "telegram", "*.jsonl.gz"))):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                p = json.loads(line)
                p["day"] = (datetime.fromisoformat(p["at"]) + TEHRAN).date()
                yield p


def series(key):
    sys.path.insert(0, os.path.join(HERE, "..", "src"))
    import requests
    from collector.tgju import fetch_daily_candles
    session_get = requests.Session()
    session_get.trust_env = False                 # Iranian sites directly from the workstation
    requests.get = session_get.get
    rows, start = [], 0
    while True:
        page = fetch_daily_candles(key, 1000, start=start, order="asc")
        rows += page
        if len(page) < 1000:
            break
        start += 1000
    out = {}
    for r in rows:
        if r["close"] and r["close"] > 0:
            out[date.fromisoformat(r["date"])] = float(r["close"])
    return out


def moves(prices, day, ahead):
    days = sorted(prices)
    before = [d for d in days if d < day]
    after = [d for d in days if d >= day]
    if not before or len(after) < ahead:
        return None
    return (prices[after[ahead - 1]] / prices[before[-1]] - 1) * 100


def main():
    hits = defaultdict(lambda: defaultdict(set))         # type -> day -> channels
    samples = defaultdict(list)
    first, last, n = None, None, 0
    for p in posts():
        n += 1
        first = min(first, p["day"]) if first else p["day"]
        last = max(last, p["day"]) if last else p["day"]
        for name, (a, b) in TYPES.items():
            if re.search(a, p["text"]) and re.search(b, p["text"]):
                hits[name][p["day"]].add(p["channel"])
                samples[name].append((p["day"], p["channel"], " ".join(p["text"].split())[:150]))
    print(f"{n} posts, {first} .. {last}")
    usd, usdt = series("price_dollar_rl"), series("crypto-tether-irr")
    span = [d for d in sorted(usd) if first <= d <= last]
    for label, prices in (("dollar", usd), ("tether", usdt)):
        base1 = [m for m in (moves(prices, d, 1) for d in span) if m is not None]
        base3 = [m for m in (moves(prices, d, 3) for d in span) if m is not None]
        print(f"\n== {label}: every day of the span: 1 day median {np.median(base1):+.2f}% (fell {np.mean(np.array(base1) < 0):.0%}),"
              f" 3 days median {np.median(base3):+.2f}% (fell {np.mean(np.array(base3) < 0):.0%})")
        for name in TYPES:
            days = sorted(d for d, ch in hits[name].items() if len(ch) >= MIN_CHANNELS)
            m1 = [m for m in (moves(prices, d, 1) for d in days) if m is not None]
            m3 = [m for m in (moves(prices, d, 3) for d in days) if m is not None]
            if len(m3) < 5:
                print(f"  {name:<17} {len(days)} event days: too few")
                continue
            print(f"  {name:<17} {len(days):>3} event days: 1 day median {np.median(m1):+.2f}% (fell {np.mean(np.array(m1) < 0):.0%}),"
                  f" 3 days median {np.median(m3):+.2f}% (fell {np.mean(np.array(m3) < 0):.0%})")
    random.seed(0)
    for name in TYPES:
        print(f"\n-- {name}: {sum(1 for d, ch in hits[name].items() if len(ch) >= MIN_CHANNELS)} event days, samples:")
        for day, channel, text in random.sample(samples[name], min(6, len(samples[name]))):
            print(f"   {day} {channel}: {text}")


if __name__ == "__main__":
    main()
