"""The lens's news (SP_D_HANDOFF.md sections 84-86): the day's headlines from the owner's four channels, and
which of them point toward a strike or toward a deal, picked and translated by the AI model (Groq).

The model only picks and translates. It sees the headlines, never a price; it returns headline numbers and an
English line for each; nothing it writes is a claim of its own:
- a pick must be a headline it was given, at most three a side, none on both sides;
- a translation may carry no number the headline does not carry;
- anything else is dropped, and a reply that cannot be read leaves the news out.

The headline filter is research/label_news_days.py's, copied: that script is frozen while E-9 labels with it
(section 80), and kpi_lens holds the two equal. Never raises: the lens says the news was not read.
"""

import html
import json
import os
import re
import time
from datetime import datetime, timedelta

import requests

CHANNELS = ("khabarfouri", "betasahm1", "bourse24ir", "bidarbourse")
MAX_HEADLINES = 70
RELEVANT = re.compile(r"دلار|ارز|ریال|بانک مرکزی|فرزین|مرکز مبادله|نرخ|تورم|مذاکر|توافق|تفاهم|آتش‌بس|آتش بس|جنگ|حمله|"
                      r"موشک|تحریم|اسنپ|ماشه|نفت|تنگه|هرمز|ترامپ|عراقچی|آمریکا|اسرائیل|اروپا|آژانس|طلا|سکه|تتر")
MARKS = re.compile(r"[🔺🔹🔸🔻▪️⭕️✅❌📌📊📈📉🔴🟢🟠🟣⚡️🚨‼️❗️◀️↗️↘️💵🏆📺🔍🔝]")
MODEL = "openai/gpt-oss-120b"
URL = "https://api.groq.com/openai/v1/chat/completions"
PER_SIDE = 3
SYSTEM = """You read numbered headlines from Iranian news channels (Persian), from the last day. You never see
prices. Pick the headlines that point toward a US or Israeli strike on Iran, or the war resuming ("strike"),
and those that point toward a deal, talks or a de-escalation ("deal"): at most 3 a side, the most significant,
none on both sides; a side may be empty. Translate each pick into one plain English line of at most 90
characters, adding nothing that is not in the headline: no number, name or claim of your own.
Answer with JSON only: {"strike": [{"id": <number>, "en": "<line>"}], "deal": [{"id": <number>, "en": "<line>"}]}"""
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def headline(text):
    """A post's first line as the labelling reads it, or None when it is too short or off the topics."""
    head = " ".join(MARKS.sub("", (text or "").strip().split("\n")[0]).split())[:140]
    return head if len(head) >= 15 and RELEVANT.search(head) else None


def day_headlines(now=None, hours=24, fetch=None):
    """The last `hours` of the four channels' headlines, deduplicated, newest first, at most MAX_HEADLINES."""
    if fetch is None:
        from collector.news.telegram_channels import fetch_since as fetch
    since = (now or datetime.utcnow()) - timedelta(hours=hours)
    seen, out = set(), []
    for channel in CHANNELS:
        try:
            posts = fetch(channel, since, max_pages=15)
        except Exception as e:  # noqa: BLE001 -- one channel failing never stops the others
            print(f"LENS NEWS: {channel} not read: {type(e).__name__}")
            continue
        for p in posts:
            head = headline(p["text"])
            key = re.sub(r"\W", "", head or "")[:60]
            if head and key not in seen:
                seen.add(key)
                out.append((p["at"], head))
    return [h for _, h in sorted(out, reverse=True)][:MAX_HEADLINES]


def _numbers(text):
    return set(re.findall(r"\d+", re.sub(r"(?<=\d)[,.٬٫](?=\d)", "", (text or "").translate(DIGITS))))


def validate(reply, heads):
    """The model's picks that hold, as {"strike": [(headline, english)], "deal": [...]}; None when unreadable."""
    if not isinstance(reply, dict):
        return None
    out, used = {}, set()
    for side in ("strike", "deal"):
        picks = reply.get(side) if isinstance(reply.get(side), list) else []
        kept = []
        for p in picks:
            try:
                k, en = int(p["id"]), " ".join(str(p["en"]).split())
            except (KeyError, TypeError, ValueError):
                continue
            if not 1 <= k <= len(heads) or k in used or not 8 <= len(en) <= 120 or len(kept) == PER_SIDE:
                continue
            if not _numbers(en) <= _numbers(heads[k - 1]):       # a number the headline does not carry
                continue
            used.add(k)
            kept.append((heads[k - 1], html.escape(en, quote=False)))
        out[side] = kept
    return out


def read(heads, key=None, post=None):
    """The model's validated picks for the headlines, or None: no key, no headlines, the quota spent, no reply."""
    key = key or os.environ.get("GROQ_API_KEY")
    if not key or not heads:
        return None
    post = post or requests.post
    body = {"model": MODEL, "temperature": 0, "reasoning_effort": "low", "max_completion_tokens": 2000,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": "\n".join(f"{i}. {h}" for i, h in enumerate(heads, start=1))}]}
    for attempt in range(2):
        try:
            r = post(URL, headers={"Authorization": f"Bearer {key}"}, json=body, timeout=90)
            if r.status_code == 429 and attempt == 0 and "per day" not in r.text.lower():
                time.sleep(min(float(r.headers.get("retry-after", 20)), 30) + 1)
                continue
            r.raise_for_status()
            return validate(json.loads(r.json()["choices"][0]["message"]["content"]), heads)
        except Exception as e:  # noqa: BLE001 -- the lens says the news was not read
            print(f"LENS NEWS: the model did not answer: {type(e).__name__}: {str(e)[:120]}")
            return None
    return None
