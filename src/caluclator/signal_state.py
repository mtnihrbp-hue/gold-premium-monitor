"""Signal state orchestrator — builds the complete market state pipeline.

Deterministic, no ML.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional

from caluclator.valuation import evaluate_valuation
from caluclator.momentum import get_premium_direction, evaluate_momentum
from caluclator.structure import evaluate_structure
from caluclator.conflict import evaluate_conflict, build_reason
from caluclator.signals import apply_hysteresis


@dataclass
class SignalState:
    """Complete interpreted market state for a single snapshot.

    Inputs + Valuation + Momentum + Structure + Conflict + Decision.
    """

    # Inputs
    premium: float
    fair_price: float
    lowest_price: float

    # Valuation
    valuation: str = "UNKNOWN"

    # Momentum
    momentum: str = "UNKNOWN"
    premium_direction: str = "DISCOUNT_STABLE"

    # Structure
    structure: str = "UNKNOWN"
    platform_average: float = 0.0
    platform_high: float = 0.0
    platform_low: float = 0.0
    platform_spread: float = 0.0
    platforms_below_fair: int = 0
    platforms_above_fair: int = 0

    # Conflict
    conflict: str = "UNKNOWN"

    # Decision
    candidate_decision: str = "UNKNOWN"
    final_decision: str = "UNKNOWN"
    reason: str = ""

    # Meta
    timestamp: datetime = field(default_factory=datetime.now)
    snapshot_id: int = 0


def build_signal_state(
    premium: float,
    fair_price: float,
    lowest_price: float,
    markets: Dict[str, Any],
    previous_premium: Optional[float],
    thresholds: dict,
    last_alert: Optional[str],
    snapshot_id: int = 0,
) -> SignalState:
    """Orchestrate the full signal state pipeline.

    Args:
        premium: current premium percentage
        fair_price: calculated fair price
        lowest_price: lowest market price
        markets: dict of {name: {price, status, ...}}
        previous_premium: previous premium for direction calculation
        thresholds: config dict with buy_premium, sell_premium
        last_alert: last alert type sent (BUY, SELL, or None)
        snapshot_id: FK to market_snapshots (updated after DB save)

    Returns:
        fully populated SignalState
    """
    # Valuation
    valuation = evaluate_valuation(premium, thresholds)

    # Momentum
    premium_direction = get_premium_direction(premium, previous_premium)
    momentum = evaluate_momentum(premium_direction)

    # Structure
    structure_result = evaluate_structure(markets, fair_price)
    structure = structure_result["state"]

    # Conflict
    conflict, candidate = evaluate_conflict(valuation, momentum, structure)

    # Hysteresis gate
    final = apply_hysteresis(candidate, last_alert, thresholds)

    # Human-readable reason
    reason = build_reason(
        valuation=valuation,
        momentum=momentum,
        premium_direction=premium_direction,
        structure=structure,
        conflict=conflict,
    )

    # SP-A STABILIZATION: explain when candidate differs from final
    if candidate != final:
        if candidate in ("BUY", "SELL") and final == "WAIT":
            reason += " Candidate conditions are met, but the transition is not yet confirmed by hysteresis."
        else:
            reason += f" Candidate is {candidate}, but final decision is {final}."

    return SignalState(
        premium=premium,
        fair_price=fair_price,
        lowest_price=lowest_price,
        valuation=valuation,
        momentum=momentum,
        premium_direction=premium_direction,
        structure=structure,
        platform_average=structure_result["platform_average"],
        platform_high=structure_result["platform_high"],
        platform_low=structure_result["platform_low"],
        platform_spread=structure_result["platform_spread"],
        platforms_below_fair=structure_result["platforms_below_fair"],
        platforms_above_fair=structure_result["platforms_above_fair"],
        conflict=conflict,
        candidate_decision=candidate,
        final_decision=final,
        reason=reason,
        timestamp=datetime.now(),
        snapshot_id=snapshot_id,
    )
