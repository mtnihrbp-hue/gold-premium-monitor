"""Which model sorts and words the LENS best (SP_D_HANDOFF.md sections 98-100; temporary probe).

Five models, three rounds each, on one list of tonight's headlines, with the LENS's prompt as it ships
(intelligence/news_lens.SYSTEM): Qwen 3.8 and gpt-oss-120b on Groq, Kimi K2.6 through Hugging Face (Novita),
NVIDIA Nemotron 3 Ultra and Google Gemma 4 31B on OpenRouter's free tier. Writes probe_lens_models.json: the headlines,
and each round's picks (side, English, reason), its gold picks and its sum-up, for scoring by hand. Sends nothing;
no key is printed.

    python research/probe_lens_models.py
"""

import json
import os
import re
import sys
import time

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
sys.stdout.reconfigure(encoding="utf-8")

from intelligence import news_lens  # noqa: E402

GROQ = "https://api.groq.com/openai/v1/chat/completions"
HF = "https://router.huggingface.co/v1/chat/completions"
OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"
CANDIDATES = [
    ("Qwen 3.8 (Groq)", GROQ, "qwen/qwen3.8-27b", "GROQ_API_KEY", {"reasoning_format": "hidden"}),
    ("gpt-oss-120b (Groq)", GROQ, "openai/gpt-oss-120b", "GROQ_API_KEY", {"reasoning_effort": "low"}),
    ("Kimi K2.6 (Hugging Face)", HF, "moonshotai/Kimi-K2.6:novita", "HF_TOKEN", {}),
    ("Nemotron 3 Ultra (OpenRouter)", OPENROUTER, "nvidia/nemotron-3-ultra-550b-a55b:free", "OPENROUTER_API_KEY", {}),
    ("Gemma 4 31B (OpenRouter)", OPENROUTER, "google/gemma-4-31b-it:free", "OPENROUTER_API_KEY", {}),
]
ROUNDS = 3


def parse(text):
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        m = re.search(r"\{.*\}", text or "", re.S)          # a reply around its JSON
        return json.loads(m.group(0)) if m else None


def ask(url, model, key, options, heads):
    body = {"model": model, "temperature": 0, "max_tokens": 3000, **options, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": news_lens.SYSTEM},
                         {"role": "user", "content": "\n".join(f"{i}. {h}" for i, h in enumerate(heads, start=1))}]}
    for attempt in range(4):
        t0 = time.time()
        try:
            r = requests.post(url, headers={"Authorization": f"Bearer {key}"}, json=body, timeout=180)
        except requests.RequestException as e:
            return {"error": f"{type(e).__name__}"}
        if r.status_code in (429, 503) and attempt < 3:
            time.sleep(min(float(r.headers.get("retry-after", 20) or 20), 60) + 5)
            continue
        if r.status_code == 400 and "response_format" in body:
            body.pop("response_format")
            continue
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}: {r.text[:200]}"}
        try:
            data = r.json()
            reply = parse(data["choices"][0]["message"]["content"])
        except Exception as e:  # noqa: BLE001
            return {"error": f"unreadable: {type(e).__name__}"}
        return {"reply": reply, "tokens": (data.get("usage") or {}).get("total_tokens"), "seconds": round(time.time() - t0, 1)}
    return {"error": "refused four times"}


def main():
    heads = news_lens.day_headlines()
    print(f"headlines: {len(heads)}")
    runs = []
    for label, url, model, key_env, options in CANDIDATES:
        key = os.environ.get(key_env)
        if not key:
            print(f"{label}: no {key_env}")
            continue
        for k in range(ROUNDS):
            got = ask(url, model, key, options, heads)
            reply = got.get("reply") if isinstance(got.get("reply"), dict) else {}
            picks = {}
            for side in ("strike", "deal", "gold"):
                for p in reply.get(side) or []:
                    try:
                        picks.setdefault(side, []).append({"id": int(p["id"]), "en": str(p.get("en", ""))[:160],
                                                           "why": str(p.get("why", ""))[:100]})
                    except (KeyError, TypeError, ValueError):
                        continue
            kept = news_lens.validate(reply, heads) if reply else None
            runs.append({"model": label, "round": k + 1, "tokens": got.get("tokens"), "seconds": got.get("seconds"),
                         "error": got.get("error"), "picks": picks, "read": str(reply.get("read", ""))[:300],
                         "kept_read": (kept or {}).get("read")})
            print(f"{label:32} {k + 1}: " + ", ".join(f"{s} {len(v)}" for s, v in picks.items())
                  + f" | {got.get('tokens')} tokens, {got.get('seconds')} s" + (f" | {got['error'][:120]}" if got.get("error") else ""))
            time.sleep(4)
    json.dump({"heads": heads, "runs": runs}, open("probe_lens_models.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
