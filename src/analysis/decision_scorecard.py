"""Did the system's own decisions turn out to be right?

Scores each recorded decision against what the market did next, and compares the
result against naive baselines so the number means something.

Why the obvious scoring rule is wrong
-------------------------------------
The intuitive test is "the system said BUY and the price went up, so it was
right". Measured on this project's own history, the fair price rose in 107 of 183
cases with a +24h reading, or 58%. Rial devaluation pushes the local price up on
its own. A system that said BUY every single time would therefore score 58% while
knowing nothing at all, and a confidence score built that way would climb toward
58% and read as skill.

The bubble rose in 86 of the same 183 cases, 47%. Close to even, with no built-in
direction. So the bubble is what gets scored here.

What correct means
------------------
Every decision is really a choice between acting now and waiting, so that is the
test applied:

    BUY   was right if the discount shrank afterwards
          (the cheap price was taken before it disappeared)

    WAIT  was right if the discount grew afterwards
          (waiting bought the same gold cheaper)

    SELL  was right if the discount grew afterwards
          (selling happened before the market got cheaper)

Movements inside the dead-band are recorded as inconclusive rather than being
forced into a verdict, because noise is not evidence either way.

Why baselines are mandatory
---------------------------
A hit rate alone is not interpretable. If always-WAIT scores 53% and the system
scores 55%, the system has almost nothing. Both naive strategies are therefore
scored on the identical sample, and the edge is reported against the stronger of
the two.

Boundary
--------
This module measures. It does not tune anything. Feeding a scorecard back into
thresholds automatically would let the system overfit its own history and then
report confidence in itself, which the project's adaptive boundary forbids.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from database.models import MarketSnapshot, MarketState

# Matches the bubble movement dead-band used elsewhere in the project.
INCONCLUSIVE_DEADBAND_PP = 0.05

DEFAULT_HORIZON_HOURS = 24
DEFAULT_TOLERANCE_HOURS = 2.0

# Below this many scored decisions the hit rate is noise.
MIN_SCORED_DECISIONS = 20
MEDIUM_CONFIDENCE_DECISIONS = 100

# Decisions that mean "do not buy now" and are therefore vindicated by a widening
# discount, versus the one that is vindicated by a narrowing discount.
ACT_NOW_DECISIONS = {"BUY"}
HOLD_OFF_DECISIONS = {"WAIT", "SELL"}


@dataclass
class DecisionScorecard:
    horizon_hours: int
    scored: int
    correct: int
    incorrect: int
    inconclusive: int
    unresolved: int
    hit_rate: Optional[float]
    always_buy_rate: Optional[float]
    always_wait_rate: Optional[float]
    best_baseline_rate: Optional[float]
    edge_vs_baseline: Optional[float]
    by_decision: Dict[str, Dict[str, int]] = field(default_factory=dict)
    status: str = "INSUFFICIENT_DATA"
    confidence: str = "INSUFFICIENT_DATA"


def _empty(horizon_hours: int) -> DecisionScorecard:
    return DecisionScorecard(
        horizon_hours=horizon_hours,
        scored=0,
        correct=0,
        incorrect=0,
        inconclusive=0,
        unresolved=0,
        hit_rate=None,
        always_buy_rate=None,
        always_wait_rate=None,
        best_baseline_rate=None,
        edge_vs_baseline=None,
        by_decision={},
        status="INSUFFICIENT_DATA",
        confidence="INSUFFICIENT_DATA",
    )


def _verdict(decision: str, move_pp: float) -> str:
    """Score one decision against the bubble movement that followed it."""
    if abs(move_pp) <= INCONCLUSIVE_DEADBAND_PP:
        return "INCONCLUSIVE"
    discount_shrank = move_pp > 0
    if decision in ACT_NOW_DECISIONS:
        return "CORRECT" if discount_shrank else "INCORRECT"
    if decision in HOLD_OFF_DECISIONS:
        return "INCORRECT" if discount_shrank else "CORRECT"
    return "INCONCLUSIVE"


def _rate(correct: int, incorrect: int) -> Optional[float]:
    decided = correct + incorrect
    if decided == 0:
        return None
    return round(100.0 * correct / decided, 1)


def _classify_confidence(scored: int) -> str:
    if scored < MIN_SCORED_DECISIONS:
        return "INSUFFICIENT_DATA"
    if scored < MEDIUM_CONFIDENCE_DECISIONS:
        return "LOW"
    return "MEDIUM"


def _resolve_forward_bubble(
    series: List[Tuple[datetime, float]],
    start_index: int,
    target: datetime,
    tolerance: timedelta,
) -> Optional[float]:
    """Nearest later reading to the target, or None. Never looks backwards."""
    best = None
    best_gap = None
    for later_timestamp, later_bubble in series[start_index + 1:]:
        if later_timestamp > target + tolerance:
            break
        gap = abs(later_timestamp - target)
        if gap <= tolerance and (best_gap is None or gap < best_gap):
            best = later_bubble
            best_gap = gap
    return best


def score_decisions(
    session,
    horizon_hours: int = DEFAULT_HORIZON_HOURS,
    tolerance_hours: float = DEFAULT_TOLERANCE_HOURS,
) -> DecisionScorecard:
    """Score every recorded decision that has a resolvable outcome."""
    if session is None:
        return _empty(horizon_hours)

    try:
        snapshot_rows = (
            session.query(MarketSnapshot.id, MarketSnapshot.timestamp,
                          MarketSnapshot.premium_percent)
            .filter(MarketSnapshot.premium_percent.isnot(None))
            .order_by(MarketSnapshot.timestamp.asc())
            .all()
        )
        state_rows = (
            session.query(MarketState.snapshot_id, MarketState.final_decision)
            .filter(MarketState.final_decision.isnot(None))
            .all()
        )
    except Exception as e:
        print(f"Decision scorecard query failed: {e}")
        return _empty(horizon_hours)

    if not snapshot_rows or not state_rows:
        return _empty(horizon_hours)

    series = [(ts, float(premium)) for _, ts, premium in snapshot_rows]
    index_by_snapshot = {
        snapshot_id: position for position, (snapshot_id, _, _) in enumerate(snapshot_rows)
    }
    bubble_by_snapshot = {
        snapshot_id: float(premium) for snapshot_id, _, premium in snapshot_rows
    }

    horizon = timedelta(hours=horizon_hours)
    tolerance = timedelta(hours=tolerance_hours)

    correct = incorrect = inconclusive = unresolved = 0
    buy_correct = buy_incorrect = 0
    wait_correct = wait_incorrect = 0
    by_decision: Dict[str, Dict[str, int]] = {}

    for snapshot_id, decision in state_rows:
        position = index_by_snapshot.get(snapshot_id)
        if position is None:
            unresolved += 1
            continue

        reference_bubble = bubble_by_snapshot[snapshot_id]
        reference_time = series[position][0]
        forward = _resolve_forward_bubble(
            series, position, reference_time + horizon, tolerance
        )
        if forward is None:
            unresolved += 1
            continue

        move_pp = forward - reference_bubble
        verdict = _verdict(decision, move_pp)

        bucket = by_decision.setdefault(
            decision, {"correct": 0, "incorrect": 0, "inconclusive": 0}
        )
        if verdict == "CORRECT":
            correct += 1
            bucket["correct"] += 1
        elif verdict == "INCORRECT":
            incorrect += 1
            bucket["incorrect"] += 1
        else:
            inconclusive += 1
            bucket["inconclusive"] += 1

        # Baselines are scored on exactly the same resolved sample.
        if verdict != "INCONCLUSIVE":
            if move_pp > 0:
                buy_correct += 1
                wait_incorrect += 1
            else:
                buy_incorrect += 1
                wait_correct += 1

    scored = correct + incorrect + inconclusive
    if scored == 0:
        result = _empty(horizon_hours)
        result.unresolved = unresolved
        return result

    hit_rate = _rate(correct, incorrect)
    always_buy_rate = _rate(buy_correct, buy_incorrect)
    always_wait_rate = _rate(wait_correct, wait_incorrect)

    baselines = [r for r in (always_buy_rate, always_wait_rate) if r is not None]
    best_baseline = max(baselines) if baselines else None
    edge = None
    if hit_rate is not None and best_baseline is not None:
        edge = round(hit_rate - best_baseline, 1)

    return DecisionScorecard(
        horizon_hours=horizon_hours,
        scored=scored,
        correct=correct,
        incorrect=incorrect,
        inconclusive=inconclusive,
        unresolved=unresolved,
        hit_rate=hit_rate,
        always_buy_rate=always_buy_rate,
        always_wait_rate=always_wait_rate,
        best_baseline_rate=best_baseline,
        edge_vs_baseline=edge,
        by_decision=by_decision,
        status="OK",
        confidence=_classify_confidence(scored),
    )
