"""Label each day of the owner's channels with what happened, by the AI model, for the news event study
(SP-D, SP_D_HANDOFF.md section 35.9). Keywords could not tell a central-bank intervention from a steel
exporters' currency agreement or Japan's yen (rd_news_events.py); the owner's design is the model reading.

One request per Tehran day: that day's headlines (the first line of each post from the four news-bearing
channels, deduplicated, filtered to the economy and politics, at most MAX_HEADLINES), never a price. The
model returns a fixed set of labels. Run on GitHub's runner (Groq; GROQ_API_KEY from the environment,
never printed), paced under the free tier's 8,000 tokens a minute. Appends to research/data/news_days.jsonl,
skipping days already labelled, so a cut run resumes. The daily quota (200,000 tokens for this model, shared
with the TSE project's account) stops a run cleanly; LABEL_TOKEN_BUDGET stops it earlier, and LABEL_FROM,
LABEL_TO and LABEL_STRIDE choose and order the days (section 80). None of them changes a label.

Run: python research/label_news_days.py [max_minutes]
"""

import glob
import gzip
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "news_days.jsonl")
CHANNELS = ("khabarfouri", "betasahm1", "bourse24ir", "bidarbourse")
TEHRAN = timedelta(hours=3, minutes=30)
MAX_HEADLINES = 70
RELEVANT = re.compile(r"دلار|ارز|ریال|بانک مرکزی|فرزین|مرکز مبادله|نرخ|تورم|مذاکر|توافق|تفاهم|آتش‌بس|آتش بس|جنگ|حمله|"
                      r"موشک|تحریم|اسنپ|ماشه|نفت|تنگه|هرمز|ترامپ|عراقچی|آمریکا|اسرائیل|اروپا|آژانس|طلا|سکه|تتر")
MODEL = "openai/gpt-oss-120b"
URL = "https://api.groq.com/openai/v1/chat/completions"
TOKENS_PER_MINUTE = 7000
SYSTEM = """You read one day of headlines from Iranian news channels (Persian). You never see prices.
Report only what the headlines say happened that day, as JSON with exactly these keys:
"cbi_fx_intervention": true if the Central Bank of Iran sold or injected foreign currency, or acted in the
  market to push the dollar down (not a routine rate announcement, not an exporters' currency agreement,
  not another country's central bank); else false.
"talks": "progress" | "setback" | "none"   (Iran's negotiations with the US or Europe)
"conflict": "escalation" | "deescalation" | "none"   (attacks, threats; or ceasefire, truce)
"sanctions": "tightened" | "eased" | "none"
"oil_exports": "up" | "down" | "none"
"dollar_pressure": "up" | "down" | "unclear"   (what today's news, taken together, implies for the
  dollar in Iran's free market)
"summary": one plain English sentence on the day's main events.
Answer with the JSON object only."""


def days():
    by_day = defaultdict(dict)
    for channel in CHANNELS:
        path = os.path.join(HERE, "data", "telegram", f"{channel}.jsonl.gz")
        if not os.path.exists(path):
            continue
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                p = json.loads(line)
                head = re.sub(r"[🔺🔹🔸🔻▪️⭕️✅❌📌📊📈📉🔴🟢🟠🟣⚡️🚨‼️❗️◀️↗️↘️💵🏆📺🔍🔝]", "", p["text"].strip().split("\n")[0])
                head = " ".join(head.split())[:140]
                if len(head) < 15 or not RELEVANT.search(head):
                    continue
                day = (datetime.fromisoformat(p["at"]) + TEHRAN).date().isoformat()
                key = re.sub(r"\W", "", head)[:60]
                by_day[day].setdefault(key, (p["at"], channel, head))
    return {d: [h for _, _, h in sorted(v.values())][:MAX_HEADLINES] for d, v in by_day.items()}


class DailyQuota(Exception):
    pass


def order(todo):
    """The days to label: those in LABEL_FROM..LABEL_TO (ISO, optional), every LABEL_STRIDE-th day first, then
    the next offset, so a run stopped by the quota still spans the whole period (SP_D_HANDOFF.md section 80)."""
    lo, hi = os.environ.get("LABEL_FROM", "0000"), os.environ.get("LABEL_TO", "9999")
    stride = int(os.environ.get("LABEL_STRIDE", "1"))
    span = sorted(d for d in todo if lo <= d <= hi)
    return [d for _, d in sorted((i % stride, d) for i, d in enumerate(span))]


def label(day, headlines, key):
    body = {"model": MODEL, "temperature": 0, "reasoning_effort": "low", "max_completion_tokens": 2500,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": f"Day {day}, {len(headlines)} headlines:\n" + "\n".join(f"- {h}" for h in headlines)}]}
    for attempt in range(6):
        r = requests.post(URL, headers={"Authorization": f"Bearer {key}"}, json=body, timeout=120)
        if r.status_code == 429:
            if "per day" in r.text.lower():      # the daily quota, not the minute's: retrying only burns the job
                raise DailyQuota(r.text[:160])
            time.sleep(float(r.headers.get("retry-after", 20)) + 1)
            continue
        if r.status_code >= 500:
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
        data = r.json()
        return json.loads(data["choices"][0]["message"]["content"]), data.get("usage", {}).get("total_tokens", 0)
    raise RuntimeError(f"{day}: no answer after six tries")


def main(max_minutes):
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        sys.exit("GROQ_API_KEY not set")
    done = set()
    if os.path.exists(OUT):
        done = {json.loads(l)["day"] for l in open(OUT, encoding="utf-8") if l.strip()}
    todo = {d: h for d, h in days().items() if d not in done and h}
    queue = order(todo)
    budget = int(os.environ.get("LABEL_TOKEN_BUDGET", "0")) or None   # leave the shared account's other users some
    print(f"{len(todo)} days to label, {len(queue)} in this run's span, {len(done)} already")
    started, spent, window, total = time.monotonic(), [], 60.0, 0
    with open(OUT, "a", encoding="utf-8") as out:
        for day in queue:
            if time.monotonic() - started > max_minutes * 60:
                print("time budget reached")
                break
            if budget and total >= budget:
                print(f"token budget reached: {total}")
                break
            now = time.monotonic()
            spent = [(t, n) for t, n in spent if now - t < window]
            if sum(n for _, n in spent) > TOKENS_PER_MINUTE - 4500:
                time.sleep(window - (now - spent[0][0]) + 0.5)
            try:
                labels, tokens = label(day, todo[day], key)
            except DailyQuota as e:
                print(f"{day}: the daily quota is spent, stopping: {e}")
                break
            except Exception as e:  # noqa: BLE001 -- a day that fails is retried on the next run
                print(f"{day}: {type(e).__name__}: {str(e)[:120]}")
                continue
            spent.append((time.monotonic(), tokens))
            total += tokens
            out.write(json.dumps({"day": day, "n": len(todo[day]), "labels": labels, "tokens": tokens}, ensure_ascii=False) + "\n")
            out.flush()
            print(f"{day} n={len(todo[day])} tokens={tokens} {json.dumps({k: v for k, v in labels.items() if k != 'summary'})}")


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 330)
