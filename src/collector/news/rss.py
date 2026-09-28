"""RSS news collector.

Fetches, parses, normalizes, and validates RSS feeds.
Non-fatal: returns [] on any failure.
"""

import hashlib
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import requests



from typing import List, Dict, Any, Optional, Union, Tuple
from urllib.parse import urlparse, parse_qs
...
def collect_rss_feed(url: str, timeout: Union[int, Tuple[int, int]] = 15) -> List[Dict[str, Any]]:
    """Fetch and parse a single RSS/Atom feed."""
    ...
    response = requests.get(url, timeout=timeout, headers=headers)
    # rest unchanged


def _parse_rss_date(date_str: str) -> Optional[datetime]:
    """Parse common RSS date formats. Returns None on failure."""
    if not date_str:
        return None
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%d %b %Y %H:%M:%S %z",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def fetch_rss_feed(url: str, timeout: int = 15) -> str:
    """Fetch raw RSS XML. Raises on failure."""
    response = requests.get(url, timeout=timeout, headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/138.0 Safari/537.36"
        ),
    })
    response.raise_for_status()
    return response.text


def source_label(url: str) -> str:
    """Stable, readable identity for a feed.

    news_events.source was the literal string "rss" on all 4,019 rows ever written,
    so which feed an item came from was only recoverable by parsing its URL -- and a
    per-source yield measurement is exactly what showed one feed producing 87% of the
    volume and none of the signal.

    Google News query feeds share a host, so the query is carried too; without it
    three different topic feeds would be indistinguishable.
    """
    try:
        parsed = urlparse(url or "")
        host = (parsed.netloc or "").replace("www.", "").lower()
        if not host:
            return "unknown"
        if "news.google.com" in host:
            query = (parse_qs(parsed.query).get("q") or [""])[0]
            topic = re.sub(r"\+?when:[^+]*", "", query).replace("+", " ").strip()
            return f"google:{topic}"[:200] if topic else "google"
        return host[:200]
    except Exception as e:
        # This used to swallow a missing-import NameError and return "unknown" for
        # every Google News feed, which is exactly the silent-degradation pattern
        # this module is meant to be fixing.
        print(f"  RSS   source label failed for {url}: {type(e).__name__}: {e}")
        return "unknown"


def parse_rss_xml(xml_text: str, source: str = "rss") -> List[Dict[str, Any]]:
    """Parse RSS XML into normalized news items.

    Supports RSS 2.0 <item> and Atom <entry> formats.
    Returns list of normalized dicts.
    """
    items = []
    try:
        import xml.etree.ElementTree as ET
    except ImportError:
        return items

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    # Determine namespace
    ns = {"": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}

    # RSS 2.0: <rss><channel><item>...</item></channel></rss>
    # Atom: <feed><entry>...</entry></feed>
    item_tag = "item"
    entry_tag = "entry"

    # Try RSS 2.0 items
    for item in root.iter(item_tag):
        parsed = _extract_item(item, ns, source)
        if parsed:
            items.append(parsed)

    # Try Atom entries
    if not items:
        for entry in root.iter(entry_tag):
            parsed = _extract_atom_entry(entry, ns, source)
            if parsed:
                items.append(parsed)

    return items


def _extract_item(item_elem, ns: Dict[str, str], source: str = "rss") -> Optional[Dict[str, Any]]:
    """Extract fields from an RSS <item>."""
    title = _get_text(item_elem, "title", ns)
    link = _get_text(item_elem, "link", ns)
    description = _get_text(item_elem, "description", ns)
    pub_date = _get_text(item_elem, "pubDate", ns)

    if not title:
        return None

    published = _parse_rss_date(pub_date) if pub_date else None
    if published is None:
        published = datetime.now(timezone.utc)

    return _normalize_item(
        title=title,
        summary=description or "",
        url=link or "",
        source=source,
        published_at=published,
    )


def _extract_atom_entry(entry_elem, ns: Dict[str, str], source: str = "rss") -> Optional[Dict[str, Any]]:
    """Extract fields from an Atom <entry>."""
    title = _get_text(entry_elem, "title", ns)
    link = ""
    for l in entry_elem.iter("{http://www.w3.org/2005/Atom}link"):
        link = l.get("href", "")
        if link:
            break
    summary = _get_text(entry_elem, "summary", ns) or _get_text(entry_elem, "content", ns)
    updated = _get_text(entry_elem, "updated", ns)
    published = _get_text(entry_elem, "published", ns)

    if not title:
        return None

    pub_date = _parse_rss_date(published or updated) if (published or updated) else None
    if pub_date is None:
        pub_date = datetime.now(timezone.utc)

    return _normalize_item(
        title=title,
        summary=summary or "",
        url=link or "",
        source=source,
        published_at=pub_date,
    )


def _get_text(parent, tag: str, ns: Dict[str, str]) -> Optional[str]:
    """Get text content of first matching child element."""
    # Try with namespace
    if ns and "" in ns:
        elem = parent.find(f"{{{ns['']}}}{tag}")
        if elem is not None and elem.text:
            return elem.text.strip()
    # Try without namespace
    elem = parent.find(tag)
    if elem is not None and elem.text:
        return elem.text.strip()
    return None


# Namespace for the deduplication key.
#
# The key used to be hashed over the `source` field, which was the constant string
# "rss" on every row ever written -- so in practice it has always been a hash of the
# title alone. Now that `source` carries real feed identity, hashing it would change
# every key and re-ingest the entire corpus as new, and would stop the same story
# arriving from two feeds from deduplicating at all. The namespace is therefore
# pinned to the historical value, deliberately, and is not the source label.
DEDUP_NAMESPACE = "rss"


def _normalize_item(
    title: str,
    summary: str,
    url: str,
    source: str,
    published_at: datetime,
) -> Dict[str, Any]:
    """Normalize a news item into the canonical schema."""
    collected_at = datetime.now(timezone.utc)
    dedup_key = hashlib.sha256(
        f"{DEDUP_NAMESPACE}:{title.strip().lower()}".encode("utf-8")
    ).hexdigest()[:32]

    return {
        "title": title.strip(),
        "summary": summary.strip(),
        "url": url.strip(),
        "source": source,
        "published_at": published_at,
        "collected_at": collected_at,
        "dedup_key": dedup_key,
    }


def collect_rss_feed(url: str, timeout: int = 15) -> List[Dict[str, Any]]:
    """Fetch and parse a single RSS feed.

    Returns normalized news items, or [] on any failure.
    """
    try:
        xml_text = fetch_rss_feed(url, timeout=timeout)
        items = parse_rss_xml(xml_text, source=source_label(url))
        print(f"  RSS   {url:<40} {len(items)} item(s)")
        return items
    except requests.exceptions.Timeout:
        print(f"  RSS   {url:<40} TIMEOUT")
        return []
    except requests.exceptions.HTTPError as e:
        print(f"  RSS   {url:<40} HTTP {e.response.status_code}")
        return []
    except requests.exceptions.RequestException as e:
        print(f"  RSS   {url:<40} ERROR ({e})")
        return []
    except Exception as e:
        print(f"  RSS   {url:<40} PARSE ERROR ({e})")
        return []


def collect_all_rss_feeds(sources: list, timeout: int = 15) -> List[Dict[str, Any]]:
    """Collect from multiple RSS sources, deduplicating across sources.

    Args:
        sources: list of RSS URLs
        timeout: per-source timeout in seconds

    Returns:
        List of unique normalized news items
    """
    all_items = []
    seen_keys = set()

    for url in sources:
        items = collect_rss_feed(url, timeout=timeout)
        for item in items:
            if item["dedup_key"] not in seen_keys:
                seen_keys.add(item["dedup_key"])
                all_items.append(item)

    return all_items
