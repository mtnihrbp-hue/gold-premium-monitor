"""A second model reviews a message line before the owner sees it (the owner, 2026-11-07; SP_D_HANDOFF.md section 102;
temporary probe). Reads research/review_input.json, a list of {"aim", "text"}; asks gpt-oss-120b and Qwen 3.8 on Groq
to read each line as its reader would; prints what each concluded, its scores, its problems and a better line.

    python research/review_message.py
"""

import json
import os
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8")
URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS = {"openai/gpt-oss-120b": {"reasoning_effort": "medium"}, "qwen/qwen3.8-27b": {"reasoning_format": "hidden"}}
SYSTEM = """You review one line of a Telegram message before it is sent. Its readers are Iranian retail investors in 18K
gold, reading English on a phone; they hold gold or rial and decide whether to buy, hold or move to fixed income. You are
given the line and its aim. Read it as such a reader would, and be demanding: a line that a reader cannot act on, or
cannot later check against what happened, has failed.
Answer with JSON only:
{"reader_concludes": "<one sentence: what the reader takes from it>",
 "clear": <1-10>, "judgeable": <1-10: can the reader check it later against what happened>, "useful": <1-10>,
 "problems": ["<each problem, short>"],
 "better": "<one better line with the SAME numbers and facts, no new number, no advice to buy or sell>"}"""


def main():
    key = os.environ["GROQ_API_KEY"]
    items = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "review_input.json"), encoding="utf-8"))
    for item in items:
        print(f"\n=== LINE: {item['text']}\n    AIM: {item['aim']}")
        for model, options in MODELS.items():
            body = {"model": model, "temperature": 0, "max_completion_tokens": 2000, **options,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "system", "content": SYSTEM},
                                 {"role": "user", "content": f"Aim: {item['aim']}\nLine: {item['text']}"}]}
            for attempt in range(3):
                r = requests.post(URL, headers={"Authorization": f"Bearer {key}"}, json=body, timeout=120)
                if r.status_code in (429, 503):
                    time.sleep(20)
                    continue
                break
            try:
                got = json.loads(r.json()["choices"][0]["message"]["content"])
                print(f"--- {model}: clear {got.get('clear')}, judgeable {got.get('judgeable')}, useful {got.get('useful')}")
                print(f"    concludes: {got.get('reader_concludes')}")
                for p in got.get("problems") or []:
                    print(f"    problem: {p}")
                print(f"    better: {got.get('better')}")
            except Exception as e:  # noqa: BLE001
                print(f"--- {model}: no review ({r.status_code}: {type(e).__name__})")


if __name__ == "__main__":
    main()
