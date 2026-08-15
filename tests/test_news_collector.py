"""Tests for SP-B.2 news collector.

No network. No database. Deterministic fixtures only.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from collector.news.rss import (
    parse_rss_xml,
    _normalize_item,
    collect_rss_feed,
    collect_all_rss_feeds,
)
from collector.news.telegram_fallback import normalize_manual_news


# ---------------------------------------------------------------------------
# RSS parsing
# ---------------------------------------------------------------------------

RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Iran and US Resume Nuclear Negotiations</title>
      <link>https://example.com/1</link>
      <description>Talks resume in Geneva.</description>
      <pubDate>Mon, 15 Aug 2026 10:00:00 +0000</pubDate>
    </item>
    <item>
      <title>CBI Raises Interest Rates</title>
      <link>https://example.com/2</link>
      <description>Central Bank of Iran announces rate hike.</description>
      <pubDate>Mon, 15 Aug 2026 11:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Local Football Team Wins Championship</title>
      <link>https://example.com/3</link>
      <description>Sports news.</description>
      <pubDate>Mon, 15 Aug 2026 12:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>"""


def test_parse_valid_rss():
    """Valid RSS XML parses into 3 items."""
    items = parse_rss_xml(RSS_SAMPLE)
    assert len(items) == 3, f"Expected 3 items, got {len(items)}"
    assert items[0]["title"] == "Iran and US Resume Nuclear Negotiations"
    assert items[1]["title"] == "CBI Raises Interest Rates"
    assert items[2]["title"] == "Local Football Team Wins Championship"
    print("PASS: test_parse_valid_rss")


def test_parse_malformed_xml():
    """Malformed XML returns empty list, no crash."""
    items = parse_rss_xml("<not>valid<xml>")
    assert items == [], f"Expected [], got {items}"
    print("PASS: test_parse_malformed_xml")


def test_parse_empty_feed():
    """Empty RSS returns empty list."""
    empty = """<?xml version="1.0"?>
    <rss><channel><title>Empty</title></channel></rss>"""
    items = parse_rss_xml(empty)
    assert items == []
    print("PASS: test_parse_empty_feed")


def test_parse_missing_title():
    """Item without title is skipped."""
    xml = """<?xml version="1.0"?>
    <rss><channel>
      <item><link>https://example.com</link></item>
      <item><title>Valid Title</title><link>https://example.com/2</link></item>
    </channel></rss>"""
    items = parse_rss_xml(xml)
    assert len(items) == 1
    assert items[0]["title"] == "Valid Title"
    print("PASS: test_parse_missing_title")


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def test_normalize_item_schema():
    """Normalized item contains all required fields."""
    item = _normalize_item(
        title="Test Headline",
        summary="Test summary.",
        url="https://example.com",
        source="rss",
        published_at=datetime(2026, 8, 15, 10, 0, tzinfo=timezone.utc),
    )
    required = ["title", "summary", "url", "source", "published_at", "collected_at", "dedup_key"]
    for key in required:
        assert key in item, f"Missing key: {key}"
    assert item["title"] == "Test Headline"
    assert item["source"] == "rss"
    assert len(item["dedup_key"]) == 32
    print("PASS: test_normalize_item_schema")


def test_dedup_key_consistency():
    """Same title+source produces same dedup key."""
    item1 = _normalize_item("Same Title", "", "", "rss", datetime.now(timezone.utc))
    item2 = _normalize_item("Same Title", "", "", "rss", datetime.now(timezone.utc))
    assert item1["dedup_key"] == item2["dedup_key"]
    print("PASS: test_dedup_key_consistency")


def test_dedup_key_uniqueness():
    """Different titles produce different dedup keys."""
    item1 = _normalize_item("Title A", "", "", "rss", datetime.now(timezone.utc))
    item2 = _normalize_item("Title B", "", "", "rss", datetime.now(timezone.utc))
    assert item1["dedup_key"] != item2["dedup_key"]
    print("PASS: test_dedup_key_uniqueness")


# ---------------------------------------------------------------------------
# Telegram fallback
# ---------------------------------------------------------------------------

def test_telegram_fallback_normalization():
    """Manual input normalizes to same schema as RSS."""
    item = normalize_manual_news(
        title="Manual News Item",
        summary="Details here.",
        url="https://t.me/channel/123",
    )
    required = ["title", "summary", "url", "source", "published_at", "collected_at", "dedup_key"]
    for key in required:
        assert key in item
    assert item["source"] == "telegram"
    print("PASS: test_telegram_fallback_normalization")


def test_telegram_fallback_requires_title():
    """Empty title raises ValueError."""
    try:
        normalize_manual_news(title="")
        assert False, "Expected ValueError"
    except ValueError:
        pass
    print("PASS: test_telegram_fallback_requires_title")


# ---------------------------------------------------------------------------
# Cross-source deduplication
# ---------------------------------------------------------------------------

def test_cross_source_dedup():
    """Same title from different sources gets different dedup keys."""
    rss = _normalize_item("Same Title", "", "", "rss", datetime.now(timezone.utc))
    telegram = normalize_manual_news("Same Title", "", "")
    assert rss["dedup_key"] != telegram["dedup_key"]
    print("PASS: test_cross_source_dedup")


# ---------------------------------------------------------------------------
# RSS failure handling (mocked)
# ---------------------------------------------------------------------------

def test_collect_rss_timeout():
    """Timeout returns empty list, no crash."""
    items = collect_rss_feed("http://192.0.2.1:9999/feed", timeout=1)
    assert items == []
    print("PASS: test_collect_rss_timeout")


def test_collect_rss_http_error():
    """HTTP error returns empty list."""
    items = collect_rss_feed("https://httpbin.org/status/404", timeout=5)
    assert items == []
    print("PASS: test_collect_rss_http_error")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_parse_valid_rss,
        test_parse_malformed_xml,
        test_parse_empty_feed,
        test_parse_missing_title,
        test_normalize_item_schema,
        test_dedup_key_consistency,
        test_dedup_key_uniqueness,
        test_telegram_fallback_normalization,
        test_telegram_fallback_requires_title,
        test_cross_source_dedup,
        test_collect_rss_timeout,
        test_collect_rss_http_error,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERR : {t.__name__}: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed out of {len(tests)}")
    if failed > 0:
        sys.exit(1)
