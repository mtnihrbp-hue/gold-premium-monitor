"""Deterministic event classifier for news intelligence.

SP-B.2: keyword-based classification. No LLM required.
Conservative: prefers UNKNOWN/UNCERTAIN over fabricated certainty.
"""

from typing import Dict, Any, List, Tuple


# ---------------------------------------------------------------------------
# Controlled vocabulary
# ---------------------------------------------------------------------------

EVENT_TYPES = [
    "IRAN_US_NEGOTIATION",
    "SANCTIONS",
    "MILITARY_ESCALATION",
    "MILITARY_DEESCALATION",
    "TRUMP_STATEMENT",
    "IRAN_GOVERNMENT_STATEMENT",
    "CBI_POLICY",
    "CURRENCY_POLICY",
    "INFLATION",
    "ECONOMIC_POLICY",
    "GEOPOLITICAL_EVENT",
    "GLOBAL_GOLD_EVENT",
    "OTHER",
    "UNKNOWN",
]

RELEVANCE_STATES = ["RELEVANT", "NOT_RELEVANT", "UNKNOWN"]
DIRECTIONS = ["RISING", "FALLING", "NEUTRAL", "UNCERTAIN", "UNKNOWN"]
DURATIONS = ["SHORT", "MEDIUM", "LONG", "UNKNOWN"]
IMPACTS = ["HIGH", "MEDIUM", "LOW", "UNKNOWN"]
CONFIDENCES = ["HIGH", "MEDIUM", "LOW", "UNKNOWN"]


# ---------------------------------------------------------------------------
# Keyword rules
# ---------------------------------------------------------------------------

# (event_type, relevance, expected_usd, expected_gold, impact, duration, confidence)
# None = leave as UNKNOWN/UNCERTAIN
KEYWORD_RULES: List[Tuple[List[str], str, str, Any, Any, Any, Any, Any]] = [
    # Iran / US relations
    (["iran", "us", "negotiation", "talk", "diplomatic", "deal"],
     "IRAN_US_NEGOTIATION", "RELEVANT", None, None, None, None, None),
    (["sanction", "sanctions", "ofac", "embargo"],
     "SANCTIONS", "RELEVANT", "RISING", None, "HIGH", "LONG", "HIGH"),
    (["military", "attack", "strike", "war", "conflict", "missile", "drone"],
     "MILITARY_ESCALATION", "RELEVANT", "RISING", "RISING", "HIGH", "SHORT", "HIGH"),
    (["ceasefire", "peace", "de-escalation", "truce"],
     "MILITARY_DEESCALATION", "RELEVANT", "FALLING", "FALLING", "MEDIUM", "MEDIUM", "MEDIUM"),

    # Trump
    (["trump", "trump administration", "trump says"],
     "TRUMP_STATEMENT", "RELEVANT", None, None, None, None, None),

    # Iran government
    (["iran government", "iranian president", "khamenei", "raisi"],
     "IRAN_GOVERNMENT_STATEMENT", "RELEVANT", None, None, None, None, None),

    # CBI / Currency
    (["cbi", "central bank", "bank markazi", "rial", "irr"],
     "CBI_POLICY", "RELEVANT", None, None, None, None, None),
    (["currency", "exchange rate", "usd/irr", "dollar", "toman"],
     "CURRENCY_POLICY", "RELEVANT", None, None, None, None, None),

    # Inflation / Economic
    (["inflation", "cpi", "price index", "cost of living"],
     "INFLATION", "RELEVANT", "RISING", "RISING", "MEDIUM", "LONG", "HIGH"),
    (["economic policy", "budget", "fiscal", "subsidy", "reform"],
     "ECONOMIC_POLICY", "RELEVANT", None, None, None, None, None),

    # Geopolitical
    (["geopolitical", "tension", "crisis", "diplomatic", "embassy"],
     "GEOPOLITICAL_EVENT", "RELEVANT", None, None, None, None, None),

    # Gold global
    (["gold price", "xau", "bullion", "spot gold", "federal reserve", "fed", "interest rate"],
     "GLOBAL_GOLD_EVENT", "RELEVANT", None, "RISING", None, None, None),
]

# Words that indicate irrelevance
IRRELEVANT_KEYWORDS = [
    "sports", "football", "soccer", "basketball", "cricket",
    "celebrity", "movie", "film", "album", "music",
    "fashion", "recipe", "cooking", "travel", "tourism",
    "weather", "horoscope", "lottery", "entertainment",
]


# ---------------------------------------------------------------------------
# Classification engine
# ---------------------------------------------------------------------------

def classify_news_item(news_item: Dict[str, Any]) -> Dict[str, Any]:
    """Classify a normalized news item into a structured market event.

    Args:
        news_item: dict with keys title, summary, url, source, etc.

    Returns:
        dict with classification fields + original fields
    """
    text = f"{news_item.get('title', '')} {news_item.get('summary', '')}".lower()

    # Default: unknown
    result = {
        "event_type": "UNKNOWN",
        "topic": None,
        "relevance": "UNKNOWN",
        "expected_usd_direction": "UNKNOWN",
        "expected_gold_direction": "UNKNOWN",
        "expected_duration": "UNKNOWN",
        "impact": "UNKNOWN",
        "confidence": "UNKNOWN",
        "uncertainty_notes": None,
        "classification_method": "KEYWORD",
    }

    # Check irrelevance first
    if _has_any_keyword(text, IRRELEVANT_KEYWORDS):
        result["relevance"] = "NOT_RELEVANT"
        result["event_type"] = "OTHER"
        result["uncertainty_notes"] = "Classified as non-market news by keyword filter."
        return {**news_item, **result}

    # Apply keyword rules
    matched = False
    for keywords, event_type, relevance, usd_dir, gold_dir, impact, duration, confidence in KEYWORD_RULES:
        if _has_any_keyword(text, keywords):
            result["event_type"] = event_type
            result["relevance"] = relevance
            if usd_dir:
                result["expected_usd_direction"] = usd_dir
            if gold_dir:
                result["expected_gold_direction"] = gold_dir
            if impact:
                result["impact"] = impact
            if duration:
                result["expected_duration"] = duration
            if confidence:
                result["confidence"] = confidence
            matched = True
            break  # first match wins

    if not matched:
        # No keyword match — could be relevant but unclassifiable
        result["relevance"] = "UNKNOWN"
        result["uncertainty_notes"] = "No matching keyword pattern."

    return {**news_item, **result}


def _has_any_keyword(text: str, keywords: List[str]) -> bool:
    """Check if any keyword appears as a substring in text."""
    for kw in keywords:
        if kw in text:
            return True
    return False


def classify_batch(news_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Classify a batch of news items."""
    return [classify_news_item(item) for item in news_items]
