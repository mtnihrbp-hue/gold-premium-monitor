"""Historical Intelligence Foundation — SP-B.1

Deterministic similarity engine for market state comparison.
No prediction. No scoring. No LLM.

Similarity model:
  Primary (hard):    valuation, momentum, premium distance
  Secondary (soft):  structure, USD/IRR direction, XAU/USD direction

Soft-match rule:
  If both sides have a known value (not UNKNOWN/None/empty),
  they must match. Otherwise, no blocking.

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
    usd_direction: str = "UNKNOWN"
    xau_direction: str = "UNKNOWN"
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

def _soft_match(field_a: Optional[str], field_b: Optional[str]) -> bool:
    """Soft-match: both known and equal, or either unknown/None/empty.

    Known = truthy and not "UNKNOWN".
    """
    a_known = _is_known(field_a)
    b_known = _is_known(field_b)
    if a_known and b_known:
        return field_a == field_b
    return True  # at least one unknown → no blocking


def _is_known(value) -> bool:
    """Return True if value is a known/non-empty categorical value."""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() not in ("", "UNKNOWN")
    return True


def calculate_similarity(
    reference: Dict[str, Any],
    candidate: Any,  # MarketState-like object
    premium_tolerance: float = 1.0,
) -> Optional[SimilarStateResult]:
    """Determine if a candidate state is similar to the reference.

    Deterministic rules (hard requirements — any failure → no match):
      1. Exact match on valuation_state
      2. Exact match on momentum_state
      3. Premium within tolerance

    Context filters (soft requirements — both known and different → no match):
      4. structure_state
      5. usd_direction
      6. xau_direction

    Returns None if any rule fails.
    """
    # --- Hard requirements ---
    if getattr(candidate, "valuation_state", None) != reference.get("valuation"):
        return None
    if getattr(candidate, "momentum_state", None) != reference.get("momentum"):
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

    # --- Soft / context filters ---
    if not _soft_match(
        getattr(candidate, "structure_state", None),
        reference.get("structure"),
    ):
        return None

    if not _soft_match(
        getattr(candidate, "usd_direction", None),
        reference.get("usd_direction"),
    ):
        return None

    if not _soft_match(
        getattr(candidate, "xau_direction", None),
        reference.get("xau_direction"),
    ):
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
        usd_direction=_extract_direction(candidate, "usd_direction"),
        xau_direction=_extract_direction(candidate, "xau_direction"),
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
        reference: dict with keys:
            premium, valuation, momentum, structure,
            usd_direction (optional), xau_direction (optional)
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
    if hasattr(candidate, "snapshot") and candidate.snapshot is not None:
        val = getattr(candidate.snapshot, "premium_percent", None)
        if val is not None:
            return float(val)
    val = getattr(candidate, "premium_percent", None)
    if val is not None:
        return float(val)
    return None


def _extract_direction(candidate, attr_name: str) -> str:
    """Extract a direction attribute, normalizing to UNKNOWN if missing."""
    val = getattr(candidate, attr_name, None)
    if val is None or (isinstance(val, str) and val.strip() == ""):
        return "UNKNOWN"
    return str(val)


def _extract_platform_count(candidate) -> int:
    """Count active platforms from state metadata."""
    below = getattr(candidate, "platforms_below_fair", 0) or 0
    above = getattr(candidate, "platforms_above_fair", 0) or 0
    return int(below) + int(above)
