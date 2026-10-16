"""Tests for SP-B.2 news collector.

No network. No database. Deterministic fixtures only.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Path bootstrap — works from repo root/tests/ OR repo root/src/tests/
# ---------------------------------------------------------------------------
_file = Path(__file__).resolve()
# If we're inside src/tests/, src/ is the grandparent. If we're in tests/,
# src/ is a sibling of the parent directory.
if (_file.parent.parent / "collector").is_dir():
    _src = _file.parent.parent
elif (_file.parent.parent / "src" / "collector").is_dir():
    _src = _file.parent.parent / "src"
else:
    _src = _file.parent.parent / "src"
sys.path.insert(0, str(_src))

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
    original_keys = ingest_module.get_recent_dedup_keys
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

    def mock_keys(hours=24):
        return set()

    def mock_save(event):
        return 42

    try:
        ingest_module.collect_rss_feed = mock_collect
        ingest_module.classify_news_item = mock_classify
        ingest_module.get_recent_dedup_keys = mock_keys
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
        ingest_module.get_recent_dedup_keys = original_keys
        ingest_module.save_news_event = original_save
    print("PASS: test_ingest_orchestrator_persists_new_items")


def test_ingest_skips_duplicates():
    """Duplicate dedup_key items are skipped via batch dedup."""
    import collector.news.ingest as ingest_module
    original_collect = ingest_module.collect_rss_feed
    original_keys = ingest_module.get_recent_dedup_keys
    original_save = ingest_module.save_news_event

    def mock_collect(url, timeout=15):
        return [
            {"title": "Dup", "summary": "", "url": "", "source": "rss",
             "published_at": datetime.now(timezone.utc),
             "collected_at": datetime.now(timezone.utc), "dedup_key": "dupkey"},
        ]

    def mock_keys(hours=24):
        return {"dupkey"}

    def mock_save(event):
        return -1

    try:
        ingest_module.collect_rss_feed = mock_collect
        ingest_module.get_recent_dedup_keys = mock_keys
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
        ingest_module.get_recent_dedup_keys = original_keys
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
    original_keys = ingest_module.get_recent_dedup_keys
    original_save = ingest_module.save_news_event

    def mock_classify(item):
        return {**item, "event_type": "TEST", "relevance": "RELEVANT",
                "classification_method": "KEYWORD"}

    def mock_keys(hours=24):
        return set()

    def mock_save(event):
        return 1

    try:
        ingest_module.collect_rss_feed = mock_collect
        ingest_module.classify_news_item = mock_classify
        ingest_module.get_recent_dedup_keys = mock_keys
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
        ingest_module.get_recent_dedup_keys = original_keys
        ingest_module.save_news_event = original_save
    print("PASS: test_ingest_non_blocking_on_source_failure")
# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def test_ingest_stops_saving_when_the_database_is_out_of_reach():
    """Three failed saves in a row and the run stores nothing more (SP_D_HANDOFF.md section 35.8)."""
    import collector.news.ingest as ingest_module
    saved = (ingest_module.get_recent_dedup_keys, ingest_module.collect_rss_feed, ingest_module.save_news_event)
    items = [{"title": f"item {k}", "url": f"http://x/{k}", "source": "x", "dedup_key": f"k{k}"} for k in range(10)]
    calls = []
    try:
        ingest_module.get_recent_dedup_keys = lambda hours=24: set()
        ingest_module.collect_rss_feed = lambda url, timeout=None: items
        ingest_module.save_news_event = lambda event: calls.append(event) or -1
        result = ingest_module.run_news_ingestion({"news": {"enabled": True, "sources": ["http://a", "http://b"],
                                                            "max_items_per_source": 10}})
        assert len(calls) == ingest_module.MAX_CONSECUTIVE_FAILED, len(calls)
        assert result["total_failed"] == 3 and result["total_skipped"] == 17
    finally:
        ingest_module.get_recent_dedup_keys, ingest_module.collect_rss_feed, ingest_module.save_news_event = saved
    print("PASS: test_ingest_stops_saving_when_the_database_is_out_of_reach")


def test_a_feed_without_a_charset_is_read_as_utf8():
    """cbi.ir serves text/xml without a charset; requests decoded it as ISO-8859-1 and the feed, its
    byte-order mark and its Persian headlines, parsed to nothing (SP_D_HANDOFF.md section 37.13)."""
    import collector.news.rss as rss_module
    body = ("\ufeff<?xml version=\"1.0\" encoding=\"utf-8\"?><rss version=\"2.0\"><channel><title>CBI.ir</title>"
            "<item><title>\u0648\u0627\u06a9\u0646\u0634 \u0628\u0627\u0646\u06a9 \u0645\u0631\u06a9\u0632\u06cc</title>"
            "<link>http://www.cbi.ir/showitem/36517.aspx</link>"
            "<pubDate>Thu, 15 Oct 2026 09:48:23 GMT</pubDate></item></channel></rss>").encode("utf-8")

    class Served:
        headers = {"content-type": "text/xml"}
        content = body
        text = body.decode("iso-8859-1")    # what requests gives for text/xml without a charset

        def raise_for_status(self):
            pass

    real = rss_module.requests.get
    try:
        rss_module.requests.get = lambda url, **kwargs: Served()
        items = collect_rss_feed("https://www.cbi.ir/NewsRss.aspx?ln=fa")
    finally:
        rss_module.requests.get = real
    assert len(items) == 1, items
    assert items[0]["title"].startswith("\u0648\u0627\u06a9\u0646\u0634"), items[0]["title"]
    print("PASS: test_a_feed_without_a_charset_is_read_as_utf8")


def test_source_label_tells_numbered_feeds_apart():
    """Tasnim's economy and politics feeds share a host; their labels must not (section 37.13)."""
    from collector.news.rss import source_label
    assert source_label("https://www.tasnimnews.ir/fa/rss/feeds/7/0/0/0") == "tasnimnews.ir/feeds/7"
    assert source_label("https://www.tasnimnews.ir/fa/rss/feeds/1/0/0/0") == "tasnimnews.ir/feeds/1"
    assert source_label("https://donya-e-eqtesad.com/rss") == "donya-e-eqtesad.com", "an existing label is unchanged"
    assert source_label("https://www.cbi.ir/NewsRss.aspx?ln=fa") == "cbi.ir"
    print("PASS: test_source_label_tells_numbered_feeds_apart")


def test_ingest_holds_the_rest_once_the_database_is_out_of_reach():
    """The first save that finds the database out of reach holds its item (returns 0); the rest of the
    run is held without asking the database again, and an item already held is not held twice
    (section 37.13)."""
    import collector.news.ingest as ingest_module
    saved = (ingest_module.get_recent_dedup_keys, ingest_module.collect_rss_feed, ingest_module.save_news_event,
             ingest_module.hold_news_event, ingest_module.held_keys)
    items = [{"title": f"item {k}", "url": f"http://x/{k}", "source": "x", "dedup_key": f"k{k}"} for k in range(10)]
    saves, holds = [], []
    try:
        ingest_module.get_recent_dedup_keys = lambda hours=24: set()
        ingest_module.held_keys = lambda kind, field: {"k1", "k2"}
        ingest_module.collect_rss_feed = lambda url, timeout=None: items
        ingest_module.save_news_event = lambda event: saves.append(event) or 0
        ingest_module.hold_news_event = lambda event: holds.append(event) or True
        result = ingest_module.run_news_ingestion({"news": {"enabled": True, "sources": ["http://a"],
                                                            "max_items_per_source": 10}})
        assert len(saves) == 1, "one save finds the database out of reach"
        assert len(holds) == 7, len(holds)
        assert result["total_held"] == 8 and result["total_duplicate"] == 2, result
    finally:
        (ingest_module.get_recent_dedup_keys, ingest_module.collect_rss_feed, ingest_module.save_news_event,
         ingest_module.hold_news_event, ingest_module.held_keys) = saved
    print("PASS: test_ingest_holds_the_rest_once_the_database_is_out_of_reach")


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
        test_ingest_stops_saving_when_the_database_is_out_of_reach,
        test_a_feed_without_a_charset_is_read_as_utf8,
        test_source_label_tells_numbered_feeds_apart,
        test_ingest_holds_the_rest_once_the_database_is_out_of_reach,
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
