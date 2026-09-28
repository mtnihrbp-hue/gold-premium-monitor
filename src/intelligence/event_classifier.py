"""Deterministic event classifier for news intelligence.

SP-B.2: keyword-based classification. No LLM required.
Conservative: prefers UNKNOWN/UNCERTAIN over fabricated certainty.

--------------------------------------------------------------------------------
What was wrong with it, measured 2026-09-21
--------------------------------------------------------------------------------

`IRAN_US_NEGOTIATION` held 879 of 1441 articles. A sample of that bucket:

    "ادارات این استان تا پایان سال 1405 دورکار شدند"   (remote working notice)
    "بلو بیزنس در دسترس همه"                            (an advertisement)
    "Foreign diplomats visit historic, natural sites in Urmia"
    "تماس تلفنی وزیر خارجه عربستان با وزرای خارجه..."   (a Saudi phone call)

None of them is a negotiation. The cause, traced by replaying the rules over the
stored corpus: the keyword `"us"` fired on 74% of that bucket, matching as a bare
substring inside base64 image tokens embedded in the RSS summary HTML:

    ...jrxp5qg1cmewilhah818sdxwp2hnfnwfxyaiaicmusgadyj8ofnnlsj37wf3nzt_kglo0...
                                            ^^

Four separate faults, all now fixed:

- **Markup was classified.** The summary went in raw, so image URLs, tracking
  tokens and HTML attributes were treated as prose. Text is stripped first.
- **Substring matching.** `"us"` is inside "business", "because", "Russia" and any
  random blob. Matching is on word boundaries now.
- **A rule that fired on any one of six common words.** `iran` OR `us` OR `talk`
  was enough to call something an Iran-US negotiation. The specific rules now
  require a subject *and* an action.
- **English-only keywords against a mostly Persian corpus.** The two
  highest-volume sources publish in Persian, where `طلا` (gold) appeared 6 times
  and `ریال` (rial) once across 1441 rows -- so the Iranian sources, the ones
  closest to this market, were matching on nothing and falling through.

`classification_method` reads KEYWORD on all 1441 rows: the LLM path has never
run. Nothing here fabricates certainty to compensate -- unmatched items stay
UNKNOWN, which is the honest answer and the one `skills/llm-news-intelligence.md`
requires.
"""

import re
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
# Rules are ordered specific-first, because the first match wins. A broad rule
# placed early swallows the corpus, which is exactly what happened: the Iran/US rule
# sat first and matched on any one of six common words.
#
# Each rule is (groups, event_type, relevance, usd, gold, impact, duration,
# confidence). `groups` is a list of keyword lists and **every group must match** --
# a subject and an action, not either alone. A single-group rule is an explicit "any
# of these is enough", used only where the words are unambiguous on their own.
#
# Persian terms sit beside the English ones because the two highest-volume sources
# in this feed publish in Persian, and an English-only list left them matching
# nothing: across 1441 stored articles `طلا` appeared 6 times and `ریال` once.
KEYWORD_RULES: List[Tuple[List[List[str]], str, str, Any, Any, Any, Any, Any]] = [
    # --- unambiguous on their own -----------------------------------------
    ([["sanction", "sanctions", "ofac", "embargo", "تحریم", "تحریم‌ها"]],
     "SANCTIONS", "RELEVANT", "RISING", None, "HIGH", "LONG", "HIGH"),

    ([["ceasefire", "truce", "de-escalation", "آتش‌بس", "آتش بس"]],
     "MILITARY_DEESCALATION", "RELEVANT", "FALLING", "FALLING", "MEDIUM", "MEDIUM",
     "MEDIUM"),

    ([["missile", "airstrike", "air strike", "warplane", "drone strike",
       "موشک", "پهپاد", "حمله هوایی"]],
     "MILITARY_ESCALATION", "RELEVANT", "RISING", "RISING", "HIGH", "SHORT", "HIGH"),

    # --- subject AND action ------------------------------------------------
    ([["iran", "tehran", "ایران", "تهران"],
      ["negotiation", "negotiations", "talks", "deal", "agreement", "diplomacy",
       "مذاکره", "مذاکرات", "توافق"]],
     "IRAN_US_NEGOTIATION", "RELEVANT", None, None, None, None, None),

    # "us" is deliberately absent. The text is lowercased, so the country and the
    # English pronoun are the same token -- it put "Europe at a Crossroads" in this
    # bucket on the strength of "...tells us...". Washington and "united states" say
    # the same thing without the collision.
    ([["war", "attack", "conflict", "strike", "جنگ", "حمله", "درگیری"],
      ["iran", "israel", "united states", "washington", "middle east", "gulf",
       "ایران", "اسرائیل", "خاورمیانه"]],
     "MILITARY_ESCALATION", "RELEVANT", "RISING", "RISING", "HIGH", "SHORT", "HIGH"),

    ([["central bank", "cbi", "bank markazi", "بانک مرکزی"],
      # Plurals and inflections are listed explicitly. Word-boundary matching buys
      # precision at the cost of stemming: "rates" is not "rate", and the first
      # version of this rule missed "CBI Raises Rates" because of it.
      ["policy", "policies", "rate", "rates", "reserve", "reserves",
       "intervention", "circular", "raises", "raised", "cut", "cuts",
       "سیاست", "نرخ", "ذخایر", "بخشنامه"]],
     "CBI_POLICY", "RELEVANT", None, None, None, None, None),

    ([["rial", "toman", "currency", "exchange rate", "ریال", "تومان", "ارز", "دلار"],
      ["rate", "rates", "market", "markets", "devaluation", "surge", "surges",
       "fell", "falls", "rose", "rises", "policy", "plunge", "plunges",
       "نرخ", "بازار", "کاهش", "افزایش"]],
     "CURRENCY_POLICY", "RELEVANT", None, None, None, None, None),

    ([["inflation", "cpi", "cost of living", "تورم", "گرانی"],
      ["rate", "rates", "rise", "rises", "rose", "data", "report", "reports",
       "percent", "نرخ", "افزایش", "درصد", "گزارش"]],
     "INFLATION", "RELEVANT", "RISING", "RISING", "MEDIUM", "LONG", "HIGH"),

    ([["gold", "bullion", "xau", "طلا", "سکه"],
      ["price", "prices", "rose", "rises", "fell", "falls", "record", "records",
       "rally", "ounce", "spot", "bullish", "bearish", "close", "high", "low",
       "قیمت", "بازار", "اونس", "افزایش", "کاهش"]],
     "GLOBAL_GOLD_EVENT", "RELEVANT", None, None, None, None, None),

    ([["federal reserve", "fed", "fomc"],
      ["rate", "rates", "cut", "cuts", "hike", "hikes", "policy", "meeting",
       "minutes", "decision"]],
     "GLOBAL_GOLD_EVENT", "RELEVANT", None, None, None, None, None),

    ([["trump", "ترامپ"],
      ["said", "says", "statement", "announced", "warned", "threat",
       "گفت", "اعلام", "هشدار"]],
     "TRUMP_STATEMENT", "RELEVANT", None, None, None, None, None),

    ([["khamenei", "pezeshkian", "iranian president", "iran government",
       "خامنه‌ای", "پزشکیان", "دولت"],
      ["said", "says", "statement", "announced", "ordered", "گفت", "اعلام",
       "دستور"]],
     "IRAN_GOVERNMENT_STATEMENT", "RELEVANT", None, None, None, None, None),

    ([["budget", "subsidy", "fiscal", "economic reform", "بودجه", "یارانه"],
      ["government", "parliament", "plan", "bill", "approved", "دولت", "مجلس",
       "طرح", "لایحه"]],
     "ECONOMIC_POLICY", "RELEVANT", None, None, None, None, None),

    ([["geopolitical", "tension", "tensions", "crisis", "تنش", "بحران"],
      ["region", "middle east", "gulf", "iran", "israel", "منطقه", "خاورمیانه",
       "ایران"]],
     "GEOPOLITICAL_EVENT", "RELEVANT", None, None, None, None, None),
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
    text = clean_text(
        f"{news_item.get('title', '') or ''} {news_item.get('summary', '') or ''}")

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
    for groups, event_type, relevance, usd_dir, gold_dir, impact, duration, confidence in KEYWORD_RULES:
        if _has_all_groups(text, groups):
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


_TAG = re.compile(r"<[^>]+>")
_URL = re.compile(r"https?://\S+|www\.\S+|\S+\.(?:com|ir|net|org|co)/\S*")
_LONG_TOKEN = re.compile(r"\b\w{25,}\b")
_ENTITY = re.compile(r"&[a-z]+;|&#\d+;")


def clean_text(raw: str) -> str:
    """Prose only: no markup, no links, no base64.

    The image token that produced 879 misclassifications lived in the summary HTML.
    Anything long enough to be a hash rather than a word goes too -- no natural word
    in either language runs to 25 characters, and every such token in this corpus was
    machine-generated.
    """
    if not raw:
        return ""
    text = _TAG.sub(" ", raw)
    text = _ENTITY.sub(" ", text)
    text = _URL.sub(" ", text)
    text = _LONG_TOKEN.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def _has_any_keyword(text: str, keywords: List[str]) -> bool:
    """True if any keyword appears as a whole word.

    Word boundaries, not substrings. `"us"` inside "business" is not a mention of
    the United States, and for months it was the single largest driver of this
    system's news classification.
    """
    for kw in keywords:
        if re.search(rf"(?<!\w){re.escape(kw)}(?!\w)", text):
            return True
    return False


def _has_all_groups(text: str, groups: List[List[str]]) -> bool:
    """Every group must contribute at least one match.

    A subject and an action, rather than either alone. "Iran" on its own is not a
    negotiation; it is the country most of this feed is about.
    """
    return all(_has_any_keyword(text, group) for group in groups)


def classify_batch(news_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Classify a batch of news items."""
    return [classify_news_item(item) for item in news_items]
