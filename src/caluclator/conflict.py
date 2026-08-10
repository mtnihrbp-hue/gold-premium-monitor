"""Conflict engine — combines valuation, momentum, structure into decision.

Deterministic matrix. No scoring. No ML.
"""


# Hardcoded conflict matrix — explicit, testable, no configuration
CONFLICT_MATRIX = {
    ("CHEAP", "IMPROVING", "DISCOUNT_DOMINANT"): ("SUPPORTIVE", "BUY"),
    ("CHEAP", "IMPROVING", "MIXED"): ("SUPPORTIVE", "BUY"),
    ("CHEAP", "IMPROVING", "PREMIUM_DOMINANT"): ("CAUTION", "WAIT"),
    ("CHEAP", "WEAKENING", "DISCOUNT_DOMINANT"): ("CAUTION", "WAIT"),
    ("CHEAP", "WEAKENING", "MIXED"): ("CAUTION", "WAIT"),
    ("CHEAP", "WEAKENING", "PREMIUM_DOMINANT"): ("CAUTION", "WAIT"),
    ("CHEAP", "NEUTRAL", "DISCOUNT_DOMINANT"): ("NEUTRAL", "WAIT"),
    ("CHEAP", "NEUTRAL", "MIXED"): ("NEUTRAL", "WAIT"),
    ("CHEAP", "NEUTRAL", "PREMIUM_DOMINANT"): ("NEUTRAL", "WAIT"),
    ("FAIR", "IMPROVING", "DISCOUNT_DOMINANT"): ("NEUTRAL", "WAIT"),
    ("FAIR", "IMPROVING", "MIXED"): ("NEUTRAL", "WAIT"),
    ("FAIR", "IMPROVING", "PREMIUM_DOMINANT"): ("NEUTRAL", "WAIT"),
    ("FAIR", "WEAKENING", "DISCOUNT_DOMINANT"): ("NEUTRAL", "WAIT"),
    ("FAIR", "WEAKENING", "MIXED"): ("NEUTRAL", "WAIT"),
    ("FAIR", "WEAKENING", "PREMIUM_DOMINANT"): ("NEUTRAL", "WAIT"),
    ("FAIR", "NEUTRAL", "DISCOUNT_DOMINANT"): ("NEUTRAL", "WAIT"),
    ("FAIR", "NEUTRAL", "MIXED"): ("NEUTRAL", "WAIT"),
    ("FAIR", "NEUTRAL", "PREMIUM_DOMINANT"): ("NEUTRAL", "WAIT"),
    ("EXPENSIVE", "IMPROVING", "DISCOUNT_DOMINANT"): ("CAUTION", "WAIT"),
    ("EXPENSIVE", "IMPROVING", "MIXED"): ("CAUTION", "WAIT"),
    ("EXPENSIVE", "IMPROVING", "PREMIUM_DOMINANT"): ("CAUTION", "WAIT"),
    ("EXPENSIVE", "WEAKENING", "DISCOUNT_DOMINANT"): ("SUPPORTIVE_FOR_SELL", "SELL"),
    ("EXPENSIVE", "WEAKENING", "MIXED"): ("SUPPORTIVE_FOR_SELL", "SELL"),
    ("EXPENSIVE", "WEAKENING", "PREMIUM_DOMINANT"): ("SUPPORTIVE_FOR_SELL", "SELL"),
    ("EXPENSIVE", "NEUTRAL", "DISCOUNT_DOMINANT"): ("NEUTRAL", "WAIT"),
    ("EXPENSIVE", "NEUTRAL", "MIXED"): ("NEUTRAL", "WAIT"),
    ("EXPENSIVE", "NEUTRAL", "PREMIUM_DOMINANT"): ("NEUTRAL", "WAIT"),
}


def evaluate_conflict(valuation: str, momentum: str, structure: str) -> tuple:
    """Return (conflict_state, candidate_decision) from the deterministic matrix.

    Args:
        valuation: CHEAP | FAIR | EXPENSIVE | UNKNOWN
        momentum: IMPROVING | NEUTRAL | WEAKENING | UNKNOWN
        structure: DISCOUNT_DOMINANT | PREMIUM_DOMINANT | MIXED | UNKNOWN

    Returns:
        (conflict_state, candidate_decision)
    """
    key = (valuation, momentum, structure)
    if key in CONFLICT_MATRIX:
        return CONFLICT_MATRIX[key]

    # Any UNKNOWN input → UNKNOWN output
    return ("UNKNOWN", "UNKNOWN")


def build_reason(
    valuation: str,
    momentum: str,
    premium_direction: str,
    structure: str,
    conflict: str,
) -> str:
    """Build a human-readable reason from state components."""
    parts = []

    if valuation == "CHEAP":
        parts.append("Market deeply discounted.")
    elif valuation == "EXPENSIVE":
        parts.append("Market expensive.")
    elif valuation == "FAIR":
        parts.append("Market fairly priced.")

    if "DISCOUNT" in premium_direction:
        if "WIDENING" in premium_direction:
            parts.append("Discount widening (improving for buyer).")
        elif "NARROWING" in premium_direction:
            parts.append("Discount narrowing (weakening for buyer).")
        elif "STABLE" in premium_direction:
            parts.append("Discount stable.")
    elif "PREMIUM" in premium_direction:
        if "WIDENING" in premium_direction:
            parts.append("Premium widening (weakening for buyer).")
        elif "NARROWING" in premium_direction:
            parts.append("Premium narrowing (improving for buyer).")
        elif "STABLE" in premium_direction:
            parts.append("Premium stable.")

    if structure == "DISCOUNT_DOMINANT":
        parts.append("Platform consensus: discount dominant.")
    elif structure == "PREMIUM_DOMINANT":
        parts.append("Platform consensus: premium dominant.")
    elif structure == "MIXED":
        parts.append("Platform consensus: mixed.")

    if conflict == "SUPPORTIVE":
        parts.append("All factors aligned for buying.")
    elif conflict == "SUPPORTIVE_FOR_SELL":
        parts.append("All factors aligned for selling.")
    elif conflict == "CAUTION":
        parts.append("Conflicting evidence — caution advised.")
    elif conflict == "NEUTRAL":
        parts.append("No strong directional signal.")

    return " ".join(parts)
