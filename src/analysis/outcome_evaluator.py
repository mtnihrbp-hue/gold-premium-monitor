"""Outcome Evaluation Foundation — PRE-SP-C.5

Deterministic outcome evaluation for persisted analysis snapshots.
Measures what happened after time T without prediction or trading logic.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple

from database.connection import get_session
from database.models import AnalysisSnapshot, PriceObservation
from database.repository import save_outcome_evaluation

DEFAULT_HORIZONS = [1, 6, 24]
DEFAULT_TOLERANCE_MINUTES = 15
DEFAULT_FLAT_TOLERANCE = 0.01
REPRESENTATIVE_FALLBACK_CHAIN = ["milli", "ayyareh", "wallgold"]


def _get_nearest_observation(
    instrument: str,
    target_time: datetime,
    after_time: datetime,
    tolerance_minutes: int,
    source: Optional[str] = None,
    session=None,
) -> Optional[PriceObservation]:
    """Find the nearest future canonical observation within tolerance.

    Observations must be strictly after after_time (no look-ahead leakage).
    The nearest observation to target_time is selected.
    Accepted only if within tolerance_minutes of target_time.
    """
    if session is None:
        session = get_session()
        if session is None:
            return None
        should_close = True
    else:
        should_close = False

    try:
        tolerance = timedelta(minutes=tolerance_minutes)
        upper_bound = target_time + tolerance

        query = session.query(PriceObservation).filter(
            PriceObservation.instrument == instrument,
            PriceObservation.timestamp > after_time,
            PriceObservation.timestamp <= upper_bound,
        )

        if source is not None:
            query = query.filter(PriceObservation.source == source)

        candidates = query.all()
        if not candidates:
            return None

        nearest = min(candidates, key=lambda o: abs(o.timestamp - target_time))
        if abs(nearest.timestamp - target_time) <= tolerance:
            return nearest
        return None
    finally:
        if should_close:
            session.close()


def _get_historical_representative_price(
    target_time: datetime,
    after_time: datetime,
    tolerance_minutes: int,
    session=None,
) -> Optional[PriceObservation]:
    """Apply the representative price fallback chain historically.

    Milli -> Ayyareh -> WallGold -> UNKNOWN
    Invi is NOT part of this chain.
    """
    for source in REPRESENTATIVE_FALLBACK_CHAIN:
        obs = _get_nearest_observation(
            instrument="REP_IRAN_GOLD",
            target_time=target_time,
            after_time=after_time,
            tolerance_minutes=tolerance_minutes,
            source=source,
            session=session,
        )
        if obs is not None:
            return obs
    return None


def _calculate_movement(
    reference: Optional[float],
    actual: Optional[float],
    flat_tolerance: float,
) -> Tuple[Optional[float], str]:
    """Calculate movement percent and direction.

    Returns (movement_percent, direction).
    direction: UP, DOWN, FLAT, or INSUFFICIENT_DATA.
    """
    if reference is None or actual is None or reference == 0:
        return None, "INSUFFICIENT_DATA"

    movement = ((actual - reference) / reference) * 100

    if abs(movement) <= flat_tolerance:
        direction = "FLAT"
    elif movement > 0:
        direction = "UP"
    else:
        direction = "DOWN"

    return round(movement, 4), direction


def evaluate_snapshot(
    snapshot_id: int,
    horizons: Optional[List[int]] = None,
    tolerance_minutes: Optional[int] = None,
    flat_tolerance: Optional[float] = None,
    config: Optional[Dict] = None,
) -> List[int]:
    """Evaluate outcomes for a single analysis snapshot.

    Idempotent: re-running for the same snapshot/horizon updates the
    existing evaluation rather than creating duplicates.

    Args:
        snapshot_id: analysis snapshot ID
        horizons: list of horizon hours (default from config)
        tolerance_minutes: target matching tolerance
        flat_tolerance: threshold for FLAT direction
        config: optional configuration dict

    Returns:
        List of evaluation IDs (or -1 on failure per horizon)
    """
    if config is None:
        config = {}

    outcome_cfg = config.get("outcome_evaluation", {})
    if horizons is None:
        horizons = outcome_cfg.get("horizons_hours", DEFAULT_HORIZONS)
    if tolerance_minutes is None:
        tolerance_minutes = outcome_cfg.get("target_tolerance_minutes", DEFAULT_TOLERANCE_MINUTES)
    if flat_tolerance is None:
        flat_tolerance = outcome_cfg.get("flat_movement_tolerance", DEFAULT_FLAT_TOLERANCE)

    session = get_session()
    if session is None:
        print("DB unavailable — cannot evaluate outcomes")
        return []

    try:
        snapshot = session.query(AnalysisSnapshot).filter(
            AnalysisSnapshot.id == snapshot_id
        ).first()

        if snapshot is None:
            print(f"Snapshot {snapshot_id} not found")
            return []

        reference_time = snapshot.analysis_timestamp
        result_ids = []

        for horizon in horizons:
            target_time = reference_time + timedelta(hours=horizon)

            # Find future observations strictly after reference_time
            xau_obs = _get_nearest_observation(
                "XAUUSD", target_time, reference_time, tolerance_minutes, session=session
            )
            usd_obs = _get_nearest_observation(
                "USD/IRR", target_time, reference_time, tolerance_minutes, session=session
            )
            rep_obs = _get_historical_representative_price(
                target_time, reference_time, tolerance_minutes, session=session
            )

            # Reference values from snapshot
            ref_xau = float(snapshot.xau_usd) if snapshot.xau_usd is not None else None
            ref_usd = float(snapshot.usd_irr) if snapshot.usd_irr is not None else None
            ref_rep = float(snapshot.rep_gold_price) if snapshot.rep_gold_price is not None else None
            ref_premium = float(snapshot.premium_percent) if snapshot.premium_percent is not None else None

            # Actual values
            act_xau = float(xau_obs.price) if xau_obs else None
            act_usd = float(usd_obs.price) if usd_obs else None
            act_rep = float(rep_obs.price) if rep_obs else None
            act_premium = None  # Cannot reconstruct without historical fair value

            # Actual observation time: earliest valid observation timestamp
            valid_obs = [o for o in (xau_obs, usd_obs, rep_obs) if o is not None]
            actual_time = min((o.timestamp for o in valid_obs), default=None)

            # Calculate movements
            xau_move, xau_dir = _calculate_movement(ref_xau, act_xau, flat_tolerance)
            usd_move, usd_dir = _calculate_movement(ref_usd, act_usd, flat_tolerance)
            rep_move, rep_dir = _calculate_movement(ref_rep, act_rep, flat_tolerance)
            prem_move, prem_dir = _calculate_movement(ref_premium, act_premium, flat_tolerance)

            # Determine overall status
            has_any_data = any(v is not None for v in (act_xau, act_usd, act_rep))
            if not has_any_data:
                status = "INSUFFICIENT_DATA"
            else:
                status = "COMPLETE"

            ev_id = save_outcome_evaluation(
                analysis_snapshot_id=snapshot_id,
                horizon_hours=horizon,
                reference_time=reference_time,
                target_time=target_time,
                actual_observation_time=actual_time,
                outcome_status=status,
                reference_rep_gold_price=ref_rep,
                reference_xau_usd=ref_xau,
                reference_usd_irr=ref_usd,
                reference_premium_percent=ref_premium,
                actual_rep_gold_price=act_rep,
                actual_xau_usd=act_xau,
                actual_usd_irr=act_usd,
                actual_premium_percent=act_premium,
                rep_gold_movement_percent=rep_move,
                rep_gold_direction=rep_dir,
                xau_usd_movement_percent=xau_move,
                xau_usd_direction=xau_dir,
                usd_irr_movement_percent=usd_move,
                usd_irr_direction=usd_dir,
                premium_movement_percent=prem_move,
                premium_direction=prem_dir,
            )
            result_ids.append(ev_id)

        return result_ids
    finally:
        session.close()


def backfill_outcome_evaluations(
    hours: int = 168,
    horizons: Optional[List[int]] = None,
    tolerance_minutes: Optional[int] = None,
    flat_tolerance: Optional[float] = None,
    config: Optional[Dict] = None,
) -> int:
    """Backfill outcome evaluations for recent analysis snapshots.

    Safe to run repeatedly. Evaluates only snapshots that do not already
    have a COMPLETE evaluation for each horizon.

    Args:
        hours: lookback window from now
        horizons: horizon hours to evaluate
        tolerance_minutes: target matching tolerance
        flat_tolerance: FLAT threshold
        config: optional configuration dict

    Returns:
        Number of evaluations created/updated
    """
    from database.models import OutcomeEvaluation

    session = get_session()
    if session is None:
        return 0

    try:
        since = datetime.now() - timedelta(hours=hours)
        snapshots = session.query(AnalysisSnapshot).filter(
            AnalysisSnapshot.analysis_timestamp >= since,
        ).order_by(AnalysisSnapshot.analysis_timestamp.desc()).all()

        count = 0
        for snap in snapshots:
            existing_evals = session.query(OutcomeEvaluation).filter(
                OutcomeEvaluation.analysis_snapshot_id == snap.id,
                OutcomeEvaluation.outcome_status == "COMPLETE",
            ).all()
            existing_horizons = {e.horizon_hours for e in existing_evals}

            needed_horizons = [h for h in (horizons or DEFAULT_HORIZONS) if h not in existing_horizons]
            if not needed_horizons:
                continue

            result = evaluate_snapshot(
                snap.id,
                horizons=needed_horizons,
                tolerance_minutes=tolerance_minutes,
                flat_tolerance=flat_tolerance,
                config=config,
            )
            count += len([r for r in result if r > 0])

        return count
    finally:
        session.close()


def run_outcome_evaluation_for_snapshot(snapshot_id: int, config: Optional[Dict] = None) -> List[int]:
    """Minimal integration point: evaluate outcomes after snapshot creation.

    Non-blocking: exceptions are caught and logged.
    """
    try:
        return evaluate_snapshot(snapshot_id, config=config)
    except Exception as e:
        print(f"Outcome evaluation failed for snapshot {snapshot_id}: {e}")
        return []
