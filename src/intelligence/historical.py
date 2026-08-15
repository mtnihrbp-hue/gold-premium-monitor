"""Historical Intelligence Foundation — SP-B.1

Deterministic similarity engine for market state comparison.
No prediction. No scoring. No LLM.

Uses existing market_states + market_snapshots tables.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SimilarStateResult:
    """A single comparable historical market state."""
    state_id: int
    snapshot_id: int
    timestamp: datetime
    premium_percent: float
    valuation: str
    momentum: str
    premium_direction: str
    structure: str
    conflict: str
    candidate_decision: str
    final_decision: str
    platform_count: int = 0
    platform_spread: float = 0.0
    premium_distance: float = 0.0
    days_ago: int = 0


@dataclass
class HistoricalComparison:
    """Complete result of a historical similarity query."""
    reference_premium: float
    reference_valuation: str
    reference_momentum: str
    reference_structure: str
    similar_states: List[SimilarStateResult] = field(default_factory=list)
    total_candidates: int = 0
    lookback_days: int = 90
    premium_tolerance: float = 1.0
    query_time: datetime = field(default_factory=datetime.now)

    @property
    def match_count(self) -> int:
        return len(self.similar_states)

    @property
    def has_sufficient_data(self) -> bool:
        """Sample-size aware: 3+ matches considered sufficient for comparison."""
        return self.match_count >= 3

    def to_text(self) -> str:
        """Human-readable summary. No prediction."""
        lines = [
            f"Historical Comparison ({self.lookback_days}d lookback)",
            f"Reference: {self.reference_valuation} + {self.reference_momentum} + {self.reference_structure}",
            f"Premium: {self.reference_premium:+.2f}%",
            "",
        ]
        if not self.similar_states:
            lines.append("No comparable historical states found.")
            return "\n".join(lines)

        lines.append(f"Found {self.match_count} similar state{'s' if self.match_count > 1 else ''}.")
        if not self.has_sufficient_data:
            lines.append("(Limited sample — interpret with caution.)")
        lines.append("")

        for i, s in enumerate(self.similar_states[:5], 1):
            lines.append(
                f"{i}. {s.timestamp.strftime('%Y-%m-%d %H:%M')}  "
                f"Premium {s.premium_percent:+.2f}%  "
                f"Final: {s.final_decision}  "
                f"({s.days_ago}d ago)"
            )

        if len(self.similar_states) > 5:
            lines.append(f"... and {len(self.similar_states) - 5} more")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Similarity engine
# ---------------------------------------------------------------------------

def calculate_similarity(
    reference: Dict[str, Any],
    candidate: Any,  # MarketState-like object
    premium_tolerance: float = 1.0,
) -> Optional[SimilarStateResult]:
    """Determine if a candidate state is similar to the reference.

    Deterministic rules:
      1. Exact match on valuation_state
      2. Exact match on momentum_state
      3. Exact match on structure_state
      4. Premium within tolerance

    Returns None if any rule fails.
    """
    # Categorical exact-match check
    if getattr(candidate, "valuation_state", None) != reference.get("valuation"):
        return None
    if getattr(candidate, "momentum_state", None) != reference.get("momentum"):
        return None
    if getattr(candidate, "structure_state", None) != reference.get("structure"):
        return None

    # Premium proximity check (join through snapshot)
    candidate_premium = _extract_premium(candidate)
    if candidate_premium is None:
        return None

    ref_premium = reference.get("premium")
    if ref_premium is None:
        return None

    premium_distance = abs(candidate_premium - ref_premium)
    if premium_distance > premium_tolerance:
        return None

    # Build result
    now = datetime.now()
    ts = getattr(candidate, "timestamp", now)
    days_ago = (now - ts).days if isinstance(ts, datetime) else 0

    return SimilarStateResult(
        state_id=getattr(candidate, "id", 0),
        snapshot_id=getattr(candidate, "snapshot_id", 0),
        timestamp=ts,
        premium_percent=round(candidate_premium, 4),
        valuation=candidate.valuation_state,
        momentum=candidate.momentum_state,
        premium_direction=getattr(candidate, "premium_direction", "UNKNOWN"),
        structure=candidate.structure_state,
        conflict=getattr(candidate, "conflict_state", "UNKNOWN"),
        candidate_decision=getattr(candidate, "candidate_decision", "UNKNOWN"),
        final_decision=getattr(candidate, "final_decision", "UNKNOWN"),
        platform_count=_extract_platform_count(candidate),
        platform_spread=float(getattr(candidate, "platform_spread", 0) or 0),
        premium_distance=round(premium_distance, 4),
        days_ago=max(0, days_ago),
    )


def rank_similar_states(states: List[SimilarStateResult]) -> List[SimilarStateResult]:
    """Sort by: premium distance (asc), then recency (desc)."""
    return sorted(states, key=lambda s: (s.premium_distance, s.days_ago))


def build_historical_comparison(
    reference: Dict[str, Any],
    candidates: List[Any],
    config: Optional[Dict[str, Any]] = None,
) -> HistoricalComparison:
    """Build a complete historical comparison from reference + candidate states.

    Args:
        reference: dict with keys: premium, valuation, momentum, structure
        candidates: list of MarketState-like objects (from DB query)
        config: optional dict with lookback_days, premium_tolerance, max_results

    Returns:
        HistoricalComparison with matched + ranked similar states
    """
    cfg = config or {}
    premium_tolerance = cfg.get("premium_tolerance", 1.0)
    lookback_days = cfg.get("lookback_days", 90)
    max_results = cfg.get("max_results", 20)

    matches = []
    for candidate in candidates:
        result = calculate_similarity(reference, candidate, premium_tolerance)
        if result is not None:
            matches.append(result)

    ranked = rank_similar_states(matches)[:max_results]

    return HistoricalComparison(
        reference_premium=reference.get("premium", 0.0),
        reference_valuation=reference.get("valuation", "UNKNOWN"),
        reference_momentum=reference.get("momentum", "UNKNOWN"),
        reference_structure=reference.get("structure", "UNKNOWN"),
        similar_states=ranked,
        total_candidates=len(candidates),
        lookback_days=lookback_days,
        premium_tolerance=premium_tolerance,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_premium(candidate) -> Optional[float]:
    """Extract premium from a candidate state object."""
    # If candidate has a joined snapshot with premium_percent
    if hasattr(candidate, "snapshot") and candidate.snapshot is not None:
        val = getattr(candidate.snapshot, "premium_percent", None)
        if val is not None:
            return float(val)
    # Fallback: try premium_percent attribute directly
    val = getattr(candidate, "premium_percent", None)
    if val is not None:
        return float(val)
    return None


def _extract_platform_count(candidate) -> int:
    """Count active platforms from state metadata."""
    below = getattr(candidate, "platforms_below_fair", 0) or 0
    above = getattr(candidate, "platforms_above_fair", 0) or 0
    return int(below) + int(above)
