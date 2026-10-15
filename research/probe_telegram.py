"""Probe, from GitHub's runner (SP-D, SP_D_HANDOFF.md section 35.5): can the owner's seven Telegram
channels be read, how much do they post, and did they carry the news behind the dollar's move of
2026-10-09 to 10-15 (267,700 -> 256,000 by 10-13 18:00 -> 266,800 on 10-15)?

Writes research/data/telegram_probe.json and prints one check-run notice per channel, plus the
dollar posts of 10-11 to 10-13: notices are readable through api.github.com when the log host is
not. Run: python research/probe_telegram.py [--notices]
"""

import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from collector.news.telegram_channels import fetch_since  # noqa: E402

CHANNELS = ["betasahm1", "trade_fundd", "bourse24ir", "fundbase_ir", "bidarbourse", "radpoool", "khabarfouri"]
SINCE = datetime(2026, 10, 8)                       # UTC
TEHRAN = timedelta(hours=3, minutes=30)
TOPICS = {
    "dollar": r"دلار|ارز|اسکناس|حواله|نیما|مرکز مبادله|یورو|درهم",
    "gold": r"طلا|سکه|مثقال|آبشده|اونس",
    "talks": r"مذاکره|مذاکرات|تحریم|آمریکا|توافق|اسنپ|ماشه|ترامپ|عراقچی|آژانس|اروپا",
    "central bank": r"بانک مرکزی|فرزین|سیاست پولی|نرخ بهره|سود بانکی|نقدینگی|تورم",
    "military": r"حمله|جنگ|موشک|اسرائیل|نظامی|پهپاد|آتش",
}
OUT = os.path.join(os.path.dirname(__file__), "data", "telegram_probe.json")


def main(notices=False):
    report, dollar_posts = {}, []
    for channel in CHANNELS:
        started = time.monotonic()
        try:
            posts = fetch_since(channel, SINCE, max_pages=60)
        except Exception as e:  # noqa: BLE001
            report[channel] = {"status": f"ERROR {type(e).__name__}: {str(e)[:120]}"}
            continue
        seconds = time.monotonic() - started
        topics = Counter()
        by_day = Counter()
        for p in posts:
            local_day = (p["at"] + TEHRAN).date().isoformat()
            for name, pattern in TOPICS.items():
                if re.search(pattern, p["text"]):
                    topics[name] += 1
                    if name == "dollar":
                        by_day[local_day] += 1
                        if "2026-10-11" <= local_day <= "2026-10-13":
                            dollar_posts.append((p["at"], channel, " ".join(p["text"].split())[:140]))
        span_days = max((posts[-1]["at"] - posts[0]["at"]).total_seconds() / 86400, 1e-9) if posts else 0
        report[channel] = {
            "status": "OK", "posts": len(posts), "seconds": round(seconds, 1),
            "first": posts[0]["at"].isoformat() if posts else None, "last": posts[-1]["at"].isoformat() if posts else None,
            "per_day": round(len(posts) / span_days, 1) if posts else 0,
            "topics": dict(topics), "dollar_by_tehran_day": dict(sorted(by_day.items())),
        }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"since": SINCE.isoformat(), "channels": report,
                   "dollar_posts_10_11_to_13": [(a.isoformat(), c, t) for a, c, t in sorted(dollar_posts)]},
                  f, ensure_ascii=False, indent=1)
    for channel, r in report.items():
        line = (f"{channel}: {r['status']}" if r["status"] != "OK" else
                f"{channel}: {r['posts']} posts {r['first'][:16]}..{r['last'][:16]} UTC, {r['per_day']}/day, "
                f"{r['seconds']}s; topics {r['topics']}; dollar by Tehran day {r['dollar_by_tehran_day']}")
        print(f"::notice title=telegram {channel}::{line}" if notices else line)
    dollar_posts.sort()
    chunks = [dollar_posts[k:k + 12] for k in range(0, min(len(dollar_posts), 36), 12)]
    for n, chunk in enumerate(chunks, 1):
        text = " || ".join(f"{(a + TEHRAN):%m-%d %H:%M} {c}: {t}" for a, c, t in chunk)
        print(f"::notice title=dollar posts {n}::{text}" if notices else text)
    print(f"dollar posts 10-11..10-13: {len(dollar_posts)}")


if __name__ == "__main__":
    main(notices="--notices" in sys.argv)
