"""Tests for SP-B.2 deterministic event classifier.

No network. No database. No LLM.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from intelligence.event_classifier import (
    classify_news_item,
    classify_batch,
    _has_any_keyword,
    EVENT_TYPES,
    RELEVANCE_STATES,
)


# ---------------------------------------------------------------------------
# Keyword detection
# ---------------------------------------------------------------------------

def test_has_any_keyword_match():
    """Keyword substring match works."""
    assert _has_any_keyword("iran sanctions announced", ["sanctions"])
    print("PASS: test_has_any_keyword_match")


def test_has_any_keyword_no_match():
    """No keyword present returns False."""
    assert not _has_any_keyword("sports team wins", ["sanctions", "gold"])
    print("PASS: test_has_any_keyword_no_match")


# ---------------------------------------------------------------------------
# Classification — relevance
# ---------------------------------------------------------------------------

def test_relevant_iran_us():
    """Iran/US negotiation headline classified as relevant."""
    item = {
        "title": "Iran and US Resume Nuclear Negotiations in Geneva",
        "summary": "Diplomatic talks have resumed.",
    }
    result = classify_news_item(item)
    assert result["relevance"] == "RELEVANT"
    assert result["event_type"] == "IRAN_US_NEGOTIATION"
    assert result["classification_method"] == "KEYWORD"
    print("PASS: test_relevant_iran_us")


def test_relevant_sanctions():
    """Sanctions headline classified with expected directions."""
    item = {
        "title": "US Imposes New Sanctions on Iranian Banks",
        "summary": "OFAC announces new restrictions.",
    }
    result = classify_news_item(item)
    assert result["relevance"] == "RELEVANT"
    assert result["event_type"] == "SANCTIONS"
    assert result["expected_usd_direction"] == "RISING"
    assert result["impact"] == "HIGH"
    print("PASS: test_relevant_sanctions")


def test_relevant_cbi():
    """CBI policy headline classified as relevant."""
    item = {
        "title": "CBI Raises Interest Rates to Combat Inflation",
        "summary": "Central Bank of Iran moves on monetary policy.",
    }
    result = classify_news_item(item)
    assert result["relevance"] == "RELEVANT"
    assert result["event_type"] == "CBI_POLICY"
    print("PASS: test_relevant_cbi")


def test_relevant_gold_global():
    """Fed/gold headline classified as global gold event."""
    item = {
        "title": "Federal Reserve Signals Rate Cut, Gold Surges",
        "summary": "Markets react to dovish Fed stance.",
    }
    result = classify_news_item(item)
    assert result["relevance"] == "RELEVANT"
    assert result["event_type"] == "GLOBAL_GOLD_EVENT"
    assert result["expected_gold_direction"] == "RISING"
    print("PASS: test_relevant_gold_global")


def test_not_relevant_sports():
    """Sports news classified as NOT_RELEVANT."""
    item = {
        "title": "Local Football Team Wins Championship",
        "summary": "Celebrations in the streets.",
    }
    result = classify_news_item(item)
    assert result["relevance"] == "NOT_RELEVANT"
    assert result["event_type"] == "OTHER"
    print("PASS: test_not_relevant_sports")


def test_not_relevant_entertainment():
    """Entertainment news classified as NOT_RELEVANT."""
    item = {
        "title": "New Movie Breaks Box Office Records",
        "summary": "Hollywood blockbuster success.",
    }
    result = classify_news_item(item)
    assert result["relevance"] == "NOT_RELEVANT"
    print("PASS: test_not_relevant_entertainment")


def test_unknown_ambiguous():
    """Ambiguous headline with no clear keywords → UNKNOWN."""
    item = {
        "title": "Market Update: Mixed Signals Across Sectors",
        "summary": "Analysts debate next moves.",
    }
    result = classify_news_item(item)
    assert result["relevance"] == "UNKNOWN"
    assert result["event_type"] == "UNKNOWN"
    print("PASS: test_unknown_ambiguous")


# ---------------------------------------------------------------------------
# Classification — direction conservatism
# ---------------------------------------------------------------------------

def test_conservative_direction():
    """Headlines without clear direction signals remain UNKNOWN/UNCERTAIN."""
    item = {
        "title": "Iran Government Issues Statement on Economy",
        "summary": "Officials discuss current conditions.",
    }
    result = classify_news_item(item)
    assert result["relevance"] == "RELEVANT"
    assert result["event_type"] == "IRAN_GOVERNMENT_STATEMENT"
    # No strong directional signal in this headline
    assert result["expected_usd_direction"] in ("UNKNOWN", "UNCERTAIN", None)
    print("PASS: test_conservative_direction")


# ---------------------------------------------------------------------------
# Classification — impact
# ---------------------------------------------------------------------------

def test_impact_high_for_sanctions():
    """Sanctions get HIGH impact."""
    item = {"title": "US Expands Sanctions on Iran", "summary": ""}
    result = classify_news_item(item)
    assert result["impact"] == "HIGH"
    print("PASS: test_impact_high_for_sanctions")


def test_impact_unknown_for_unclear():
    """Unclear events keep UNKNOWN impact."""
    item = {"title": "Some Political Development Occurs", "summary": ""}
    result = classify_news_item(item)
    assert result["impact"] == "UNKNOWN"
    print("PASS: test_impact_unknown_for_unclear")


# ---------------------------------------------------------------------------
# Batch classification
# ---------------------------------------------------------------------------

def test_classify_batch():
    """Batch processing handles multiple items."""
    items = [
        {"title": "Iran and US Resume Talks", "summary": ""},
        {"title": "Sports Team Wins", "summary": ""},
        {"title": "Gold Price Rises on Fed News", "summary": ""},
    ]
    results = classify_batch(items)
    assert len(results) == 3
    assert results[0]["event_type"] == "IRAN_US_NEGOTIATION"
    assert results[1]["relevance"] == "NOT_RELEVANT"
    assert results[2]["event_type"] == "GLOBAL_GOLD_EVENT"
    print("PASS: test_classify_batch")


# ---------------------------------------------------------------------------
# Schema completeness
# ---------------------------------------------------------------------------

def test_output_schema_complete():
    """Classified output contains all required fields."""
    item = {"title": "Sanctions Announced", "summary": ""}
    result = classify_news_item(item)
    required = [
        "title", "summary", "url", "source",
        "event_type", "topic", "relevance",
        "expected_usd_direction", "expected_gold_direction",
        "expected_duration", "impact", "confidence",
        "uncertainty_notes", "classification_method",
    ]
    for key in required:
        assert key in result, f"Missing key: {key}"
    print("PASS: test_output_schema_complete")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_has_any_keyword_match,
        test_has_any_keyword_no_match,
        test_relevant_iran_us,
        test_relevant_sanctions,
        test_relevant_cbi,
        test_relevant_gold_global,
        test_not_relevant_sports,
        test_not_relevant_entertainment,
        test_unknown_ambiguous,
        test_conservative_direction,
        test_impact_high_for_sanctions,
        test_impact_unknown_for_unclear,
        test_classify_batch,
        test_output_schema_complete,
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
