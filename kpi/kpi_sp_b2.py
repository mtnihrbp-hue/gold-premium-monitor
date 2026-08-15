"""SP-B.2 Sprint KPI — News Intelligence Layer.

Run: python kpi/kpi_sp_b2.py
Output: SP-B.2 COMPLETE  or  SP-B.2 FAILED
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from collector.news.rss import parse_rss_xml, _normalize_item
from collector.news.telegram_fallback import normalize_manual_news
from intelligence.event_classifier import classify_news_item, classify_batch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RSS_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Iran and US Resume Nuclear Negotiations</title>
      <link>https://example.com/1</link>
      <description>Talks resume.</description>
      <pubDate>Mon, 15 Aug 2026 10:00:00 +0000</pubDate>
    </item>
    <item>
      <title>CBI Raises Interest Rates to Stabilize Rial</title>
      <link>https://example.com/2</link>
      <description>Monetary policy update.</description>
      <pubDate>Mon, 15 Aug 2026 11:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Local Football Team Wins Championship</title>
      <link>https://example.com/3</link>
      <description>Sports.</description>
      <pubDate>Mon, 15 Aug 2026 12:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>"""


# ---------------------------------------------------------------------------
# KPI Checks
# ---------------------------------------------------------------------------

def kpi_1_rss_parsing():
    """1. RSS XML parses into normalized items."""
    items = parse_rss_xml(RSS_FIXTURE)
    assert len(items) == 3, f"FAIL: expected 3, got {len(items)}"
    assert items[0]["title"] == "Iran and US Resume Nuclear Negotiations"
    print("  ✓ KPI-1: RSS parsing works")


def kpi_2_rss_failure_handling():
    """2. Malformed XML returns empty list, no crash."""
    items = parse_rss_xml("<invalid>")
    assert items == [], "FAIL: malformed XML should return []"
    print("  ✓ KPI-2: RSS failure handling works")


def kpi_3_normalization():
    """3. RSS and manual input produce same schema."""
    rss = _normalize_item("Title", "Summary", "https://a.com", "rss", datetime.now(timezone.utc))
    manual = normalize_manual_news("Title", "Summary", "https://a.com")
    for key in ["title", "summary", "url", "source", "published_at", "collected_at", "dedup_key"]:
        assert key in rss, f"RSS missing {key}"
        assert key in manual, f"Manual missing {key}"
    print("  ✓ KPI-3: Normalization schema consistent")


def kpi_4_deduplication():
    """4. Same title+source produces same dedup key."""
    a = _normalize_item("Same", "", "", "rss", datetime.now(timezone.utc))
    b = _normalize_item("Same", "", "", "rss", datetime.now(timezone.utc))
    assert a["dedup_key"] == b["dedup_key"], "FAIL: dedup keys should match"
    print("  ✓ KPI-4: Deduplication key stable")


def kpi_5_relevant_article_classification():
    """5. Market-relevant articles classified as RELEVANT."""
    item = {"title": "US Imposes New Sanctions on Iran", "summary": ""}
    result = classify_news_item(item)
    assert result["relevance"] == "RELEVANT", f"FAIL: got {result['relevance']}"
    print("  ✓ KPI-5: Relevant article classified")


def kpi_6_unrelated_article_handling():
    """6. Unrelated articles classified as NOT_RELEVANT."""
    item = {"title": "Football Team Wins Championship", "summary": ""}
    result = classify_news_item(item)
    assert result["relevance"] == "NOT_RELEVANT", f"FAIL: got {result['relevance']}"
    print("  ✓ KPI-6: Unrelated article filtered")


def kpi_7_event_type_classification():
    """7. Event types assigned correctly."""
    cases = [
        ("Iran and US Resume Talks", "IRAN_US_NEGOTIATION"),
        ("CBI Raises Rates", "CBI_POLICY"),
        ("Gold Price Surges", "GLOBAL_GOLD_EVENT"),
    ]
    for title, expected in cases:
        result = classify_news_item({"title": title, "summary": ""})
        assert result["event_type"] == expected, f"FAIL: {title} → {result['event_type']}"
    print("  ✓ KPI-7: Event type classification works")


def kpi_8_direction_handling():
    """8. Clear directional signals captured; ambiguous remains UNKNOWN."""
    clear = classify_news_item({"title": "Sanctions Expected to Weaken Rial", "summary": ""})
    assert clear["expected_usd_direction"] == "RISING"
    ambiguous = classify_news_item({"title": "Government Issues Statement", "summary": ""})
    assert ambiguous["expected_usd_direction"] in ("UNKNOWN", "UNCERTAIN")
    print("  ✓ KPI-8: Direction handling conservative")


def kpi_9_event_persistence_schema():
    """9. Classified event contains all persistence fields."""
    item = {"title": "Test Headline", "summary": "Test summary"}
    result = classify_news_item(item)
    required = [
        "event_type", "relevance", "expected_usd_direction",
        "expected_gold_direction", "impact", "confidence",
        "classification_method",
    ]
    for key in required:
        assert key in result, f"FAIL: missing {key}"
    print("  ✓ KPI-9: Persistence schema complete")


def kpi_10_db_unavailable_degradation():
    """10. DB unavailable: repository functions return gracefully."""
    from database.repository import news_event_exists, get_recent_news_events
    # Without DATABASE_URL, these should not crash
    exists = news_event_exists("any-key")
    recent = get_recent_news_events()
    assert exists is False
    assert recent == []
    print("  ✓ KPI-10: DB unavailable degrades gracefully")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 50)
    print("SP-B.2 Sprint KPI")
    print("=" * 50)

    checks = [
        kpi_1_rss_parsing,
        kpi_2_rss_failure_handling,
        kpi_3_normalization,
        kpi_4_deduplication,
        kpi_5_relevant_article_classification,
        kpi_6_unrelated_article_handling,
        kpi_7_event_type_classification,
        kpi_8_direction_handling,
        kpi_9_event_persistence_schema,
        kpi_10_db_unavailable_degradation,
    ]

    passed = 0
    failed = 0
    for check in checks:
        try:
            check()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {check.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {check.__name__}: ERR {e}")
            failed += 1

    print("=" * 50)
    print(f"Result: {passed}/{len(checks)} passed, {failed} failed")
    if failed == 0:
        print("\n🟢 SP-B.2 COMPLETE")
    else:
        print("\n🔴 SP-B.2 FAILED")
        sys.exit(1)
