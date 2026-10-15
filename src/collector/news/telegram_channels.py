"""Public Telegram channels as a news source (SP-D, SP_D_HANDOFF.md section 35.5).

Iranian market news breaks first on Telegram channels, and a public channel can be read without an
account at https://t.me/s/<channel>, the page Telegram serves as the channel's web preview: its last
20 or so posts, and older ones through `?before=<post id>`. Telegram is blocked inside Iran; GitHub's
runner reads it. A post is its channel, id, UTC time and text. A channel that fails returns nothing
and never stops the others.
"""

from datetime import datetime

import requests
from bs4 import BeautifulSoup

BASE = "https://t.me/s/{channel}"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
TIMEOUT = (5, 15)


def parse_page(html, channel):
    """The posts on one channel page, oldest first: {"channel", "id", "at" (naive UTC), "text"}.
    Posts without text (a photo alone, a sticker) are left out."""
    soup = BeautifulSoup(html, "lxml")
    posts = []
    for node in soup.select("div.tgme_widget_message[data-post]"):
        try:
            post_id = int(node["data-post"].rsplit("/", 1)[1])
        except (ValueError, IndexError):
            continue
        body = node.select_one("div.tgme_widget_message_text")
        stamp = node.select_one("a.tgme_widget_message_date time[datetime]") or node.select_one("time[datetime]")
        if body is None or stamp is None:
            continue
        for br in body.find_all("br"):
            br.replace_with("\n")
        text = body.get_text().strip()
        if not text:
            continue
        at = datetime.fromisoformat(stamp["datetime"])
        if at.tzinfo is not None:                       # Telegram stamps posts in UTC, "+00:00"
            at = at.replace(tzinfo=None) - at.utcoffset()
        posts.append({"channel": channel, "id": post_id, "at": at, "text": text})
    posts.sort(key=lambda p: p["id"])
    return posts


def fetch_page(channel, before=None):
    """One page of a channel's posts, oldest first. Raises on failure."""
    response = requests.get(BASE.format(channel=channel), params={"before": before} if before else None,
                            headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    return parse_page(response.text, channel)


def fetch_since(channel, since, max_pages=30):
    """The channel's posts from `since` (naive UTC) on, oldest first, paging back at most
    `max_pages` pages. Raises when the first page cannot be read."""
    posts = fetch_page(channel)
    pages = 1
    while posts and posts[0]["at"] > since and pages < max_pages:
        try:
            older = fetch_page(channel, before=posts[0]["id"])
        except Exception:  # noqa: BLE001 -- what was read is kept
            break
        pages += 1
        older = [p for p in older if p["id"] < posts[0]["id"]]
        if not older:
            break
        posts = older + posts
    return [p for p in posts if p["at"] >= since]
