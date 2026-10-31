"""Temporary probe (SP-D 86, probe-lens only): the LENS's headlines through prompt variants, side by side with the
Persian, to fix the translation errors seen on 9 Aban ("پل هوایی" as "bridge operation", "فشرده" as "Compact").
One headline list, four calls; prints each pick and the tokens each call used. Sends nothing."""

import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
sys.stdout.reconfigure(encoding="utf-8")

import requests  # noqa: E402

from intelligence import news_lens  # noqa: E402

TAIL = """
Answer with JSON only: {"strike": [{"id": <number>, "en": "<line>"}], "deal": [{"id": <number>, "en": "<line>"}]}"""
PICK = """You read numbered headlines from Iranian news channels (Persian), from the last day. You never see
prices. Pick the headlines that point toward a US or Israeli strike on Iran, or the war resuming ("strike"),
and those that point toward a deal, talks or a de-escalation ("deal"): at most 3 a side, the most significant,
none on both sides; a side may be empty."""
EDITOR = """ Translate each pick as a news editor would: its meaning in one plain English line of at most 90
characters, not word for word; a Persian idiom becomes the English term for the same thing. Add nothing that is
not in the headline: no number, name or claim of your own."""
GLOSSARY = """ For example: "پل هوایی" is an airlift, "مذاکرات فشرده" are intensive talks, "سوخت‌رسان" is a
refuelling aircraft."""

VARIANTS = [
    ("A now (low)", news_lens.SYSTEM, "low"),
    ("B editor (low)", PICK + EDITOR + TAIL, "low"),
    ("C editor + examples (low)", PICK + EDITOR + GLOSSARY + TAIL, "low"),
    ("D editor (medium)", PICK + EDITOR + TAIL, "medium"),
]


def call(system, effort, heads):
    body = {"model": news_lens.MODEL, "temperature": 0, "reasoning_effort": effort, "max_completion_tokens": 4000,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": "\n".join(f"{i}. {h}" for i, h in enumerate(heads, start=1))}]}
    r = requests.post(news_lens.URL, headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"}, json=body,
                      timeout=120)
    if r.status_code == 429:
        time.sleep(min(float(r.headers.get("retry-after", 20)), 40) + 1)
        r = requests.post(news_lens.URL, headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
                          json=body, timeout=120)
    r.raise_for_status()
    data = r.json()
    return json.loads(data["choices"][0]["message"]["content"]), data.get("usage", {})


def main():
    heads = news_lens.day_headlines(datetime.utcnow())
    print(f"HEADLINES {len(heads)}")
    for i, h in enumerate(heads, start=1):
        print(f"  {i}. {h}")
    for name, system, effort in VARIANTS:
        print(f"\n=== {name}")
        try:
            reply, usage = call(system, effort, heads)
        except Exception as e:  # noqa: BLE001
            print(f"  failed: {type(e).__name__}: {str(e)[:200]}")
            continue
        print(f"  tokens: {usage.get('total_tokens')} (prompt {usage.get('prompt_tokens')}, "
              f"completion {usage.get('completion_tokens')})")
        kept = news_lens.validate(reply, heads) or {}
        for side in ("strike", "deal"):
            for p in reply.get(side) or []:
                k = p.get("id")
                fa = heads[k - 1] if isinstance(k, int) and 1 <= k <= len(heads) else "?"
                ok = any(en == p.get("en") or en == p.get("en", "").replace("&", "&amp;")
                         for _, en in kept.get(side, []))
                print(f"  {side:6} #{k} {'kept' if ok else 'DROPPED'}\n     fa: {fa}\n     en: {p.get('en')}")


if __name__ == "__main__":
    main()
