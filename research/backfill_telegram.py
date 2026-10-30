"""Backfill one Telegram channel's history from GitHub's runner, for the news event study (SP-D,
SP_D_HANDOFF.md section 35.8): what the dollar and Tether did after each kind of event the owner's
channels reported. Telegram is blocked in Iran; the runner reads t.me/s/<channel> page by page back to
SINCE. Writes research/data/telegram/<channel>.jsonl.gz, one post a line: channel, id, at (UTC), text. A file
already held is extended further back from its oldest post (posts newer than its newest are not read), so a run
cut by MAX_SECONDS resumes. t.me also opens from the workstation through the system proxy (Psiphon).

Run: python research/backfill_telegram.py <channel> [since YYYY-MM-DD]
"""

import gzip
import json
import os
import sys
import time
from datetime import datetime

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from collector.news.telegram_channels import BASE, HEADERS, TIMEOUT, parse_page  # noqa: E402

PAUSE = 0.4            # seconds between pages, to stay a polite reader
MAX_SECONDS = int(os.environ.get("BACKFILL_SECONDS", 50 * 60))  # a run's budget; what was read is written either way


def page(channel, before):
    for attempt in range(5):
        try:
            r = requests.get(BASE.format(channel=channel), params={"before": before} if before else None,
                             headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 429:
                time.sleep(int(r.headers.get("Retry-After", 10)) + 1)
                continue
            r.raise_for_status()
            return parse_page(r.text, channel)
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{channel}: page before {before} failed five times")


def main(channel, since):
    out = os.path.join(os.path.dirname(__file__), "data", "telegram", f"{channel}.jsonl.gz")
    try:                                         # one reader per channel: two would overwrite each other's pages
        lock = os.open(out + ".lock", os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        print(f"{channel}: another run holds it")
        return
    try:
        read(channel, since, out)
    finally:
        os.close(lock)
        os.remove(out + ".lock")


def read(channel, since, out):
    started = time.monotonic()
    posts, before, pages = {}, None, 0
    if os.path.exists(out):                      # resume: extend the held file further back from its oldest post
        with gzip.open(out, "rt", encoding="utf-8") as f:
            for line in f:
                p = json.loads(line)
                posts[p["id"]] = {**p, "at": datetime.fromisoformat(p["at"])}
        if posts:
            before = min(posts)
            if posts[before]["at"] < since:
                print(f"{channel}: already held back to {posts[before]['at']:%Y-%m-%d}")
                return
    while time.monotonic() - started < MAX_SECONDS:
        try:
            batch = page(channel, before)
        except RuntimeError as e:                # the line dropped: keep what was read, the next run resumes
            print(e)
            break
        pages += 1
        fresh = [p for p in batch if p["id"] not in posts]
        for p in fresh:
            posts[p["id"]] = p
        if not batch:
            break
        oldest = min(p["id"] for p in batch)
        if batch[0]["at"] < since or oldest <= 1 or (before is not None and oldest >= before):
            break
        before = oldest
        time.sleep(PAUSE)
    kept = sorted((p for p in posts.values() if p["at"] >= since), key=lambda p: p["id"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with gzip.open(out + ".tmp", "wt", encoding="utf-8") as f:
        for p in kept:
            f.write(json.dumps({**p, "at": p["at"].isoformat()}, ensure_ascii=False) + "\n")
    os.replace(out + ".tmp", out)                # whole or not at all: a cut write never replaces the held year
    span = f"{kept[0]['at']:%Y-%m-%d} .. {kept[-1]['at']:%Y-%m-%d}" if kept else "none"
    print(f"{channel}: {len(kept)} posts {span}, {pages} pages, {time.monotonic() - started:.0f}s")


if __name__ == "__main__":
    main(sys.argv[1], datetime.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else datetime(2025, 10, 15))
