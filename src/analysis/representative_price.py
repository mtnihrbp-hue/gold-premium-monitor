"""Deterministic representative Iranian gold price selection.

PRE-SP-C.3: canonical fallback chain over price_observations.

The representative price is an actual market-price series, NOT premium,
NOT fair value, and NOT an average of all platforms.

Approved fallback chain (code-enforced, not config-enforced):
    Milli → Ayyareh → WallGold → UNKNOWN
"""

from dataclasses import dataclass
from typing import Optional

from database.repository import get_latest_price_observation

# Architectural invariant: fallback order is fixed by design.
# Config may describe operational parameters (freshness requirements),
# but the priority chain itself is not user-configurable.
FALLBACK_CHAIN = ["milli", "ayyareh", "wallgold"]


@dataclass(frozen=True)
class RepresentativePrice:
    """Result of representative-price selection."""

    price: Optional[float]
    source: str
    status: str  # AVAILABLE | UNKNOWN
    fallback_reason: Optional[str] = None


def get_representative_price(
    freshness_required: str = "FRESH",
) -> RepresentativePrice:
    """Select the representative Iranian gold price via canonical fallback.

    Queries price_observations for each approved source in priority order.
    Returns the first valid observation that meets freshness requirements.

    Args:
        freshness_required: minimum freshness to accept (FRESH | STALE | ANY)

    Returns:
        RepresentativePrice with selected price, source, and status.
    """
    for source in FALLBACK_CHAIN:
        obs = get_latest_price_observation(
            instrument="REP_IRAN_GOLD",
            source=source,
        )
        if obs is None:
            continue

        if freshness_required == "FRESH" and obs.freshness != "FRESH":
            continue
        if freshness_required == "STALE" and obs.freshness == "UNKNOWN":
            continue
        # freshness_required == "ANY" accepts everything

        try:
            price_val = float(obs.price)
            if price_val <= 0:
                continue
            return RepresentativePrice(
                price=price_val,
                source=source,
                status="AVAILABLE",
            )
        except (ValueError, TypeError):
            continue

    return RepresentativePrice(
        price=None,
        source="UNKNOWN",
        status="UNKNOWN",
        fallback_reason="No valid observation from Milli, Ayyareh, or WallGold",
    )
