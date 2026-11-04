"""Which Groq model and which prompt sort the LENS's headlines best (SP_D_HANDOFF.md section 98; temporary probe).

On one list of tonight's headlines, each candidate model is asked three times with two prompts:
- A, the LENS's prompt as it runs (intelligence/news_lens.SYSTEM);
- B, the same with each side defined exactly, the political and legal limits on a war named as de-escalation,
  and a short reason for each pick.
Writes probe_lens_models.json: the headlines, the models Groq lists, and each round's picks with their side and
reason, for scoring by hand against a labelled set. Sends nothing; the key is never printed.

    python research/probe_lens_models.py
"""

import json
import os
import sys
import time

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
sys.stdout.reconfigure(encoding="utf-8")

from intelligence import news_lens  # noqa: E402

URL = "https://api.groq.com/openai/v1/chat/completions"
WANTED = ("openai/gpt-oss-120b", "openai/gpt-oss-20b", "moonshotai/kimi-k2-instruct-0905", "moonshotai/kimi-k2-instruct",
          "meta-llama/llama-4-maverick-17b-128e-instruct", "qwen/qwen3-32b", "llama-3.3-70b-versatile")
ROUNDS = 3

SIDES = """Each side, exactly:
- "strike": a step that makes a US or Israeli strike on Iran, or the war's return, MORE likely: military moves and
  deployments, threats and ultimatums, talks failing or broken off, attacks, sanctions snapping back.
- "deal": a step that makes talks, a deal or de-escalation more likely, or a strike LESS likely: talks under way,
  mediation, offers, a ceasefire kept, and limits on a war: a vote, a court, public opposition, an election that
  weakens a hawk, an ally refusing to join.
- Neither: commentary with no step either way, prices and markets alone, domestic news.
A headline that carries both steps goes to the side of its main step. When unsure, leave it out."""

PROMPT_B = news_lens.SYSTEM.replace(
    "none on both sides; a side may be empty.",
    "none on both sides; a side may be empty.\n" + SIDES).replace(
    '{"id": <number>, "en": "<line>"}', '{"id": <number>, "en": "<line>", "why": "<at most 12 words>"}')


def ask(key, model, system, heads):
    body = {"model": model, "temperature": 0, "max_completion_tokens": 2500,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": "\n".join(f"{i}. {h}" for i, h in enumerate(heads, start=1))}]}
    if model.startswith("openai/gpt-oss"):
        body["reasoning_effort"] = "low"
    for attempt in range(3):
        r = requests.post(URL, headers={"Authorization": f"Bearer {key}"}, json=body, timeout=120)
        if r.status_code == 429:
            time.sleep(min(float(r.headers.get("retry-after", 20)), 60) + 1)
            continue
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}: {r.text[:160]}"}
        try:
            reply = json.loads(r.json()["choices"][0]["message"]["content"])
        except Exception as e:  # noqa: BLE001
            return {"error": f"unreadable: {type(e).__name__}"}
        usage = r.json().get("usage", {})
        return {"reply": reply, "tokens": usage.get("total_tokens")}
    return {"error": "429 three times"}


def main():
    key = os.environ["GROQ_API_KEY"]
    listed = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {key}"},
                          timeout=30).json()
    available = sorted(m["id"] for m in listed.get("data", []))
    models = [m for m in WANTED if m in available]
    heads = news_lens.day_headlines()
    print(f"models listed: {len(available)}; tried: {models}; headlines: {len(heads)}")
    runs = []
    for model in models:
        for label, system in (("A", news_lens.SYSTEM), ("B", PROMPT_B)):
            for k in range(ROUNDS):
                got = ask(key, model, system, heads)
                picks = {}
                for side in ("strike", "deal"):
                    for p in (got.get("reply") or {}).get(side) or []:
                        try:
                            picks[int(p["id"])] = {"side": side, "en": str(p.get("en", ""))[:140],
                                                   "why": str(p.get("why", ""))[:100]}
                        except (KeyError, TypeError, ValueError):
                            continue
                runs.append({"model": model, "prompt": label, "round": k + 1, "tokens": got.get("tokens"),
                             "error": got.get("error"), "picks": picks})
                print(f"{model:48} {label} {k + 1}: {len(picks)} picks, {got.get('tokens')} tokens"
                      + (f"  {got['error']}" if got.get("error") else ""))
                time.sleep(2)
    json.dump({"available": available, "heads": heads, "runs": runs}, open("probe_lens_models.json", "w",
              encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
