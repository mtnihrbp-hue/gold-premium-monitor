"""Deterministic support/resistance analysis.

PRE-SP-C.3: local extrema + clustering on actual market-price observations.

Operates on the canonical price_observations series.
No external indicator libraries.
No LLM-generated levels.
No BUY/SELL signals.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

from database.repository import get_price_observations_by_instrument


@dataclass(frozen=True)
class PriceLevel:
    """A clustered support or resistance level."""

    price: float
    side: str  # SUPPORT | RESISTANCE
    touches: int
    strength: str  # WEAK | MODERATE | STRONG
    source: str
    lookback: int
    freshness: str


@dataclass(frozen=True)
class StructureState:
    """Complete support/resistance state for an instrument."""

    support_levels: List[PriceLevel]
    resistance_levels: List[PriceLevel]
    status: str  # COMPLETE | DEGRADED | INSUFFICIENT_DATA


def _find_local_extrema(
    prices: List[float],
    neighborhood: int = 1,
) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
    """Find local highs and lows using rolling neighborhood comparison.

    A local high is strictly greater than all neighbors in the window.
    A local low is strictly less than all neighbors in the window.

    Args:
        prices: ordered price series (oldest → newest)
        neighborhood: number of bars on each side to compare

    Returns:
        (highs, lows) where each is a list of (index, price) tuples.
    """
    highs: List[Tuple[int, float]] = []
    lows: List[Tuple[int, float]] = []

    n = len(prices)
    if n < 2 * neighborhood + 1:
        return highs, lows

    for i in range(neighborhood, n - neighborhood):
        window = prices[i - neighborhood : i + neighborhood + 1]
        current = prices[i]

        if current == max(window) and current != min(window):
            highs.append((i, current))
        if current == min(window) and current != max(window):
            lows.append((i, current))

    return highs, lows


def _cluster_extrema(
    extrema: List[Tuple[int, float]],
    tolerance_percent: float = 0.3,
) -> List[List[Tuple[int, float]]]:
    """Cluster nearby extrema into levels using price tolerance.

    Args:
        extrema: list of (index, price) tuples
        tolerance_percent: max percent difference to group into one cluster

    Returns:
        List of clusters, each cluster is a list of (index, price) tuples.
    """
    if not extrema:
        return []

    # Sort by price for clustering
    sorted_extrema = sorted(extrema, key=lambda x: x[1])
    clusters: List[List[Tuple[int, float]]] = []
    current: List[Tuple[int, float]] = [sorted_extrema[0]]

    for i in range(1, len(sorted_extrema)):
        prev_price = current[-1][1]
        curr_price = sorted_extrema[i][1]

        if prev_price == 0:
            # Avoid division by zero; treat as separate cluster
            clusters.append(current)
            current = [sorted_extrema[i]]
            continue

        diff_pct = abs(curr_price - prev_price) / prev_price * 100
        if diff_pct <= tolerance_percent:
            current.append(sorted_extrema[i])
        else:
            clusters.append(current)
            current = [sorted_extrema[i]]

    if current:
        clusters.append(current)

    return clusters


def _strength_from_touches(touches: int) -> str:
    """Deterministic strength label from touch count."""
    if touches >= 3:
        return "STRONG"
    if touches >= 2:
        return "MODERATE"
    return "WEAK"


def build_structure_state(
    instrument: str = "REP_IRAN_GOLD",
    lookback: int = 20,
    cluster_tolerance_percent: float = 0.3,
    min_history: int = 10,
    neighborhood_size: int = 1,
) -> StructureState:
    """Build support/resistance state from canonical price observations.

    Non-blocking: returns INSUFFICIENT_DATA if not enough history.

    Args:
        instrument: price_observations instrument to analyze
        lookback: max observations to retrieve
        cluster_tolerance_percent: price tolerance for clustering extrema
        min_history: minimum observations required for analysis
        neighborhood_size: bars on each side for local extrema

    Returns:
        StructureState with support/resistance levels and metadata.
    """
    obs = get_price_observations_by_instrument(instrument, limit=lookback)

    if len(obs) < min_history:
        return StructureState(
            support_levels=[],
            resistance_levels=[],
            status="INSUFFICIENT_DATA",
        )

    # Oldest → newest ordering for extrema detection
    prices = [float(o.price) for o in reversed(obs)]
    timestamps = [o.timestamp for o in reversed(obs)]
    latest_ts = timestamps[-1] if timestamps else None

    highs, lows = _find_local_extrema(prices, neighborhood=neighborhood_size)

    support_clusters = _cluster_extrema(lows, cluster_tolerance_percent)
    resistance_clusters = _cluster_extrema(highs, cluster_tolerance_percent)

    support_levels: List[PriceLevel] = []
    for cluster in support_clusters:
        avg_price = sum(p for _, p in cluster) / len(cluster)
        touches = len(cluster)
        support_levels.append(PriceLevel(
            price=round(avg_price, 2),
            side="SUPPORT",
            touches=touches,
            strength=_strength_from_touches(touches),
            source=instrument,
            lookback=lookback,
            freshness="FRESH" if latest_ts else "UNKNOWN",
        ))

    resistance_levels: List[PriceLevel] = []
    for cluster in resistance_clusters:
        avg_price = sum(p for _, p in cluster) / len(cluster)
        touches = len(cluster)
        resistance_levels.append(PriceLevel(
            price=round(avg_price, 2),
            side="RESISTANCE",
            touches=touches,
            strength=_strength_from_touches(touches),
            source=instrument,
            lookback=lookback,
            freshness="FRESH" if latest_ts else "UNKNOWN",
        ))

    if not support_levels and not resistance_levels:
        status = "DEGRADED"
    else:
        status = "COMPLETE"

    return StructureState(
        support_levels=support_levels,
        resistance_levels=resistance_levels,
        status=status,
    )
