"""Temporary probe (SP-D 86, probe-lens only): the LENS's headlines through today's prompt and a candidate, three
times each on one headline list, side by side with the Persian. Seen on 9 Aban: "پل هوایی" as "bridge operation",
"فشرده" as "Compact", "العربی الجدید" as "Arab News", Foreign Policy's analysis as "Gulf says". Calls are spaced to
stay under the per-minute limit. Sends nothing."""

import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
sys.stdout.reconfigure(encoding="utf-8")

import requests  # noqa: E402

from intelligence import news_lens  # noqa: E402

CANDIDATE = """You read numbered headlines from Iranian news channels (Persian), from the last day. You never see
prices. Pick the headlines that point toward a US or Israeli strike on Iran, or the war resuming ("strike"),
and those that point toward a deal, talks or a de-escalation ("deal"): at most 3 a side, the most significant,
none on both sides; a side may be empty.
Translate each pick as a news editor would, into one plain English line of at most 90 characters:
- the meaning, not word for word: an idiom becomes the English term ("پل هوایی" is an airlift, "مذاکرات فشرده"
  are intensive talks);
- who says it stays: a headline that opens with a source opens with that source in English ("Axios:",
  "Foreign Policy:"); an outlet you cannot name with certainty is transliterated, never replaced by another;
- a condition stays a condition, a claim stays a claim;
- nothing that is not in the headline: no number, name or claim of your own.
Answer with JSON only: {"strike": [{"id": <number>, "en": "<line>"}], "deal": [{"id": <number>, "en": "<line>"}]}"""

VARIANTS = [("A now", news_lens.SYSTEM), ("E candidate", CANDIDATE)]
ROUNDS = 3
GAP = 70


def call(system, heads):
    body = {"model": news_lens.MODEL, "temperature": 0, "reasoning_effort": "low", "max_completion_tokens": 2000,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": "\n".join(f"{i}. {h}" for i, h in enumerate(heads, start=1))}]}
    for _ in range(2):
        r = requests.post(news_lens.URL, headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
                          json=body, timeout=120)
        if r.status_code != 429:
            break
        time.sleep(min(float(r.headers.get("retry-after", 30)), 60) + 2)
    r.raise_for_status()
    data = r.json()
    return json.loads(data["choices"][0]["message"]["content"]), data.get("usage", {})


def main():
    heads = news_lens.day_headlines(datetime.utcnow())
    print(f"HEADLINES {len(heads)}")
    for i, h in enumerate(heads, start=1):
        print(f"  {i}. {h}")
    first = True
    for rnd in range(1, ROUNDS + 1):
        for name, system in VARIANTS:
            if not first:
                time.sleep(GAP)
            first = False
            print(f"\n=== {name}, round {rnd}")
            try:
                reply, usage = call(system, heads)
            except Exception as e:  # noqa: BLE001
                print(f"  failed: {type(e).__name__}: {str(e)[:200]}")
                continue
            kept = news_lens.validate(reply, heads) or {}
            print(f"  tokens {usage.get('total_tokens')}; kept {sum(len(v) for v in kept.values())}")
            for side in ("strike", "deal"):
                for p in reply.get(side) or []:
                    k = p.get("id")
                    fa = heads[k - 1] if isinstance(k, int) and 1 <= k <= len(heads) else "?"
                    print(f"  {side:6} #{k}: {p.get('en')}\n               {fa}")


if __name__ == "__main__":
    main()
