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
# Ingest orchestrator (SP-B.2 — operational wiring)
# ---------------------------------------------------------------------------

def test_ingest_respects_enabled_false():
    """When news.enabled is false, ingest returns DISABLED."""
    from collector.news.ingest import run_news_ingestion
    result = run_news_ingestion({"news": {"enabled": False}})
    assert result["status"] == "DISABLED"
    assert result["total_new"] == 0
    print("PASS: test_ingest_respects_enabled_false")


def test_ingest_orchestrator_persists_new_items():
    """RSS items are classified, deduped, and persisted."""
    import collector.news.ingest as ingest_module
    original_collect = ingest_module.collect_rss_feed
    original_classify = ingest_module.classify_news_item
    original_exists = ingest_module.news_event_exists
    original_save = ingest_module.save_news_event

    def mock_collect(url, timeout=15):
        return [
            {"title": "Test News", "summary": "Summary", "url": "http://example.com/1",
             "source": "rss", "published_at": datetime.now(timezone.utc),
             "collected_at": datetime.now(timezone.utc), "dedup_key": "abc123"},
        ]

    def mock_classify(item):
        return {**item, "event_type": "TEST", "relevance": "RELEVANT",
                "classification_method": "KEYWORD"}

    def mock_exists(dedup_key):
        return False

    def mock_save(event):
        return 42

    try:
        ingest_module.collect_rss_feed = mock_collect
        ingest_module.classify_news_item = mock_classify
        ingest_module.news_event_exists = mock_exists
        ingest_module.save_news_event = mock_save

        from collector.news.ingest import run_news_ingestion
        result = run_news_ingestion({
            "news": {
                "enabled": True,
                "sources": ["http://example.com/feed"],
                "max_items_per_source": 20,
            }
        })
        assert result["status"] == "OK"
        assert result["total_new"] == 1
        assert result["sources"]["http://example.com/feed"]["new"] == 1
    finally:
        ingest_module.collect_rss_feed = original_collect
        ingest_module.classify_news_item = original_classify
        ingest_module.news_event_exists = original_exists
        ingest_module.save_news_event = original_save
    print("PASS: test_ingest_orchestrator_persists_new_items")


def test_ingest_skips_duplicates():
    """Duplicate dedup_key items are skipped."""
    import collector.news.ingest as ingest_module
    original_collect = ingest_module.collect_rss_feed
    original_exists = ingest_module.news_event_exists
    original_save = ingest_module.save_news_event

    def mock_collect(url, timeout=15):
        return [
            {"title": "Dup", "summary": "", "url": "", "source": "rss",
             "published_at": datetime.now(timezone.utc),
             "collected_at": datetime.now(timezone.utc), "dedup_key": "dupkey"},
        ]

    def mock_exists(dedup_key):
        return True

    def mock_save(event):
        return -1

    try:
        ingest_module.collect_rss_feed = mock_collect
        ingest_module.news_event_exists = mock_exists
        ingest_module.save_news_event = mock_save

        from collector.news.ingest import run_news_ingestion
        result = run_news_ingestion({
            "news": {
                "enabled": True,
                "sources": ["http://example.com/feed"],
                "max_items_per_source": 20,
            }
        })
        assert result["total_new"] == 0
        assert result["total_duplicate"] == 1
    finally:
        ingest_module.collect_rss_feed = original_collect
        ingest_module.news_event_exists = mock_exists
        ingest_module.save_news_event = original_save
    print("PASS: test_ingest_skips_duplicates")


def test_ingest_non_blocking_on_source_failure():
    """A failed source does not abort other sources."""
    import collector.news.ingest as ingest_module
    original_collect = ingest_module.collect_rss_feed

    def mock_collect(url, timeout=15):
        if "bad" in url:
            raise RuntimeError("Network error")
        return [
            {"title": "OK", "summary": "", "url": "", "source": "rss",
             "published_at": datetime.now(timezone.utc),
             "collected_at": datetime.now(timezone.utc), "dedup_key": "okkey"},
        ]

    original_classify = ingest_module.classify_news_item
    original_exists = ingest_module.news_event_exists
    original_save = ingest_module.save_news_event

    def mock_classify(item):
        return {**item, "event_type": "TEST", "relevance": "RELEVANT",
                "classification_method": "KEYWORD"}

    def mock_exists(dedup_key):
        return False

    def mock_save(event):
        return 1

    try:
        ingest_module.collect_rss_feed = mock_collect
        ingest_module.classify_news_item = mock_classify
        ingest_module.news_event_exists = mock_exists
        ingest_module.save_news_event = mock_save

        from collector.news.ingest import run_news_ingestion
        result = run_news_ingestion({
            "news": {
                "enabled": True,
                "sources": ["http://bad.com/feed", "http://good.com/feed"],
                "max_items_per_source": 20,
            }
        })
        assert result["status"] == "OK"
        assert result["sources"]["http://bad.com/feed"]["status"] == "ERROR"
        assert result["sources"]["http://good.com/feed"]["status"] == "OK"
        assert result["total_new"] == 1
    finally:
        ingest_module.collect_rss_feed = original_collect
        ingest_module.classify_news_item = original_classify
        ingest_module.news_event_exists = original_exists
        ingest_module.save_news_event = original_save
    print("PASS: test_ingest_non_blocking_on_source_failure")


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
        test_ingest_respects_enabled_false,
        test_ingest_orchestrator_persists_new_items,
        test_ingest_skips_duplicates,
        test_ingest_non_blocking_on_source_failure,
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
