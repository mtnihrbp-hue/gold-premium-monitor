"""Premium momentum analysis using historical database data.

SP-A ADDITIONS:
  - get_premium_direction(): explicit discount/premium terminology
  - evaluate_momentum(): maps direction to IMPROVING/NEUTRAL/WEAKENING

PRESERVED:
  - build_momentum_context() (Task C)
  - _fallback_momentum() (Task C)
"""

from typing import Optional


# ---------------------------------------------------------------------------
# SP-A: get_premium_direction
# ---------------------------------------------------------------------------

def get_premium_direction(current_premium: float, previous_premium: Optional[float]) -> str:
    """Determine premium direction with explicit discount/premium terminology.

    For negative premium (discount):
      current < previous (more negative)  → DISCOUNT_WIDENING
      current > previous (less negative)  → DISCOUNT_NARROWING
      |diff| < 0.05%                      → DISCOUNT_STABLE

    For positive premium:
      current > previous (more positive)  → PREMIUM_WIDENING
      current < previous (less positive)  → PREMIUM_NARROWING
      |diff| < 0.05%                      → PREMIUM_STABLE
    """
    if previous_premium is None:
        return "DISCOUNT_STABLE" if current_premium < 0 else "PREMIUM_STABLE"

    diff = current_premium - previous_premium
    threshold = 0.05

    if abs(diff) < threshold:
        return "DISCOUNT_STABLE" if current_premium < 0 else "PREMIUM_STABLE"

    if current_premium < 0:
        if diff < 0:
            return "DISCOUNT_WIDENING"
        return "DISCOUNT_NARROWING"
    else:
        if diff > 0:
            return "PREMIUM_WIDENING"
        return "PREMIUM_NARROWING"


# ---------------------------------------------------------------------------
# SP-A: evaluate_momentum
# ---------------------------------------------------------------------------

def evaluate_momentum(premium_direction: str, fair_trend: Optional[dict] = None) -> str:
    """Map premium direction to momentum state.

    IMPROVING  = discount widening  (cheaper for buyer)
                 or premium narrowing (cheaper for buyer)
    WEAKENING  = discount narrowing (pricier for buyer)
                 or premium widening (pricier for buyer)
    NEUTRAL    = stable or unrecognized
    """
    if premium_direction in ("DISCOUNT_WIDENING", "PREMIUM_NARROWING"):
        return "IMPROVING"
    elif premium_direction in ("DISCOUNT_NARROWING", "PREMIUM_WIDENING"):
        return "WEAKENING"
    elif premium_direction in ("DISCOUNT_STABLE", "PREMIUM_STABLE"):
        return "NEUTRAL"
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# PRESERVED from Task C
# ---------------------------------------------------------------------------

def build_momentum_context(current_premium: float, session) -> dict:
    """Build a momentum context dict for alerts."""
    from database.repository import get_premium_momentum_context as _db_context

    try:
        return _db_context(current_premium, session)
    except Exception as e:
        print(f"Momentum DB query failed: {e}")
        return _fallback_momentum(current_premium)


def _fallback_momentum(current_premium: float) -> dict:
    """Return minimal momentum when DB is unavailable."""
    return {
        "premium_vs_today": None,
        "premium_vs_yesterday": None,
        "candlestick": None,
        "verbal_direction": "Neutral (no history)",
    }
