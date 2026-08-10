"""Signal state orchestrator — pipelines observations into decisions.

SP-A: Valuation → Momentum → Structure → Conflict → Hysteresis.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from caluclator.valuation import evaluate_valuation
from caluclator.momentum import get_premium_direction, evaluate_momentum
from caluclator.structure import evaluate_structure
from caluclator.conflict import evaluate_conflict, build_reason


@dataclass
class SignalState:
    """Complete market state after full signal pipeline evaluation."""

    # Inputs
    premium: float
    fair_price: float
    lowest_price: float

    # Valuation
    valuation: str          # CHEAP | FAIR | EXPENSIVE | UNKNOWN

    # Momentum
    momentum: str           # IMPROVING | NEUTRAL | WEAKENING | UNKNOWN
    premium_direction: str  # DISCOUNT_WIDENING | DISCOUNT_NARROWING | DISCOUNT_STABLE
                            # PREMIUM_WIDENING | PREMIUM_NARROWING | PREMIUM_STABLE

    # Structure
    structure: str          # DISCOUNT_DOMINANT | PREMIUM_DOMINANT | MIXED | UNKNOWN
    platform_average: float
    platform_high: float
    platform_low: float
    platform_spread: float
    platforms_below_fair: int
    platforms_above_fair: int

    # Conflict
    conflict: str           # SUPPORTIVE | CAUTION | SUPPORTIVE_FOR_SELL | NEUTRAL | UNKNOWN

    # Decision
    candidate_decision: str # BUY | WAIT | SELL | UNKNOWN
    final_decision: str     # BUY | WAIT | SELL | UNKNOWN (after hysteresis)
    reason: str             # Human-readable explanation

    # Meta
    timestamp: datetime
    snapshot_id: int        # FK to market_snapshots


def build_signal_state(
    premium: float,
    fair_price: float,
    lowest_price: float,
    markets: Dict[str, Any],
    previous_premium: Optional[float],
    thresholds: dict,
    last_alert: Optional[str],
    snapshot_id: int,
    timestamp: Optional[datetime] = None,
) -> SignalState:
    """Orchestrate the full signal intelligence pipeline."""
    if timestamp is None:
        timestamp = datetime.utcnow()

    # 1. VALUATION
    valuation = evaluate_valuation(premium, thresholds)

    # 2. MOMENTUM
    premium_direction = get_premium_direction(premium, previous_premium)
    momentum = evaluate_momentum(premium_direction)

    # 3. STRUCTURE
    structure_result = evaluate_structure(markets, fair_price)
    structure = structure_result["state"]

    # 4. CONFLICT → CANDIDATE
    conflict, candidate_decision = evaluate_conflict(valuation, momentum, structure)

    # 5. HYSTERESIS → FINAL
    from caluclator.signals import apply_hysteresis
    final_decision = apply_hysteresis(candidate_decision, last_alert, thresholds)

    # 6. REASON
    reason = build_reason(
        valuation=valuation,
        momentum=momentum,
        premium_direction=premium_direction,
        structure=structure,
        conflict=conflict,
    )

    return SignalState(
        premium=premium,
        fair_price=fair_price,
        lowest_price=lowest_price,
        valuation=valuation,
        momentum=momentum,
        premium_direction=premium_direction,
        structure=structure,
        platform_average=structure_result.get("platform_average", 0.0),
        platform_high=structure_result.get("platform_high", 0.0),
        platform_low=structure_result.get("platform_low", 0.0),
        platform_spread=structure_result.get("platform_spread", 0.0),
        platforms_below_fair=structure_result.get("platforms_below_fair", 0),
        platforms_above_fair=structure_result.get("platforms_above_fair", 0),
        conflict=conflict,
        candidate_decision=candidate_decision,
        final_decision=final_decision,
        reason=reason,
        timestamp=timestamp,
        snapshot_id=snapshot_id,
    )
