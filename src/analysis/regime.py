"""Deterministic market-regime classifier.

PRE-SP-C.3: multi-factor regime with hysteresis, separate from SP-A decision logic.

Regime states:
    NORMAL | FEAR | PANIC | RELIEF | UNKNOWN

Evidence families:
    A. Premium Stress
    B. Volatility Stress
    C. USD / Market Structure Stress
    D. External Event Stress

Invariant: CHEAP + PANIC is valid.
Regime does NOT issue BUY/SELL.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median
from typing import Optional, Dict, List


# Regime states — fixed by architecture, not configurable
REGIME_STATES = ["NORMAL", "FEAR", "PANIC", "RELIEF", "UNKNOWN"]

# Stress thresholds were fixed constants calibrated for a market whose premium sits
# near zero. This market does not: the discount ranged 1.82% to 8.19% over 30 days,
# so `abs(premium) > 2.0` was satisfied by all but a sliver of the observed range,
# and `platform_spread > 500000` Rials was satisfied by every reading, since a normal
# spread is around 3.3 million. Two of the four families were therefore permanently
# stressed, and the hysteresis at _apply_hysteresis latched the result: regime_state
# read PANIC on all 96 analysis snapshots ever written.
#
# This is the same failure as valuation_state reading CHEAP on every reading, and it
# takes the same treatment as SP-C.2: a threshold that recalculates itself from the
# market's own recent distribution rather than a constant the market never crosses.
#
# The 80th percentile matches EXPENSIVE_PERCENTILE in bubble_position, so "stressed"
# means the same thing here as "expensive" does there: the top fifth of its own
# recent range. Calibration is a separate module-level function, so the classifier
# stays a pure, deterministic function of its inputs and its injected thresholds.
STRESS_PERCENTILE = 80
CALIBRATION_WINDOW_DAYS = 30

# Below this many readings the window cannot support a percentile, and the fixed
# defaults are kept rather than a threshold derived from a handful of points.
MIN_CALIBRATION_OBSERVATIONS = 30


@dataclass(frozen=True)
class EvidenceFamily:
    """One evidence family evaluation result."""

    name: str
    stressed: bool
    evidence: Dict


@dataclass(frozen=True)
class RegimeResult:
    """Complete regime classification result."""

    state: str
    previous_state: Optional[str]
    evidence: List[EvidenceFamily]
    confirmation_count: int
    hysteresis_active: bool


class RegimeClassifier:
    """Deterministic regime classifier with configurable thresholds and hysteresis.

    Hysteresis is separate from SP-A decision hysteresis.
    """

    def __init__(self, config: Optional[Dict] = None):
        """Initialize with regime configuration.

        Args:
            config: dict with keys:
                - stress_thresholds: dict of numeric thresholds
                - confirmation_periods: int, default 2
                - hysteresis_enabled: bool, default True
        """
        if config is None:
            config = {}

        self._thresholds = config.get("stress_thresholds", {})
        self._confirmation_periods = config.get("confirmation_periods", 2)
        self._hysteresis_enabled = config.get("hysteresis_enabled", True)

        # Internal hysteresis state (not persisted — caller may persist if needed)
        self._previous_state: Optional[str] = None
        self._candidate_state: Optional[str] = None
        self._confirmation_count: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, evidence: Dict) -> RegimeResult:
        """Classify market regime from evidence dictionary.

        Args:
            evidence: dict with optional keys:
                - premium_percent: float
                - premium_change: float (change in premium over period)
                - volatility: float (normalized or ATR-like measure)
                - usd_change: float (USD/IRR percent change)
                - platform_spread: float (absolute spread in IRR)
                - high_impact_news_count: int
                - previous_regime: str (optional, for relief detection)

        Returns:
            RegimeResult with state, evidence, and hysteresis metadata.
        """
        families = self._evaluate_families(evidence)
        stressed_count = sum(1 for f in families if f.stressed)

        # Determine raw candidate regime
        candidate = self._candidate_from_stress(stressed_count, evidence, families)

        # Apply hysteresis
        final_state, hysteresis_active = self._apply_hysteresis(candidate)

        return RegimeResult(
            state=final_state,
            previous_state=self._previous_state,
            evidence=families,
            confirmation_count=self._confirmation_count,
            hysteresis_active=hysteresis_active,
        )

    def reset_hysteresis(self):
        """Reset internal hysteresis state. Useful for testing."""
        self._previous_state = None
        self._candidate_state = None
        self._confirmation_count = 0


    def restore_state(
        self,
        previous_state: Optional[str] = None,
        candidate_state: Optional[str] = None,
        confirmation_count: int = 0,
    ):
        """Restore hysteresis state from a persisted snapshot.

        Used by the Analysis Wing to reconstruct regime state across
        independent scheduled runs (e.g., GitHub Actions).

        Args:
            previous_state: last confirmed regime state
            candidate_state: current candidate regime state
            confirmation_count: current confirmation progress
        """
        self._previous_state = previous_state
        self._candidate_state = candidate_state
        self._confirmation_count = confirmation_count

    # ------------------------------------------------------------------
    # Internal logic
    # ------------------------------------------------------------------

    def _evaluate_families(self, evidence: Dict) -> List[EvidenceFamily]:
        """Evaluate all four evidence families against thresholds."""
        families = []

        # --- Family A: Premium Stress ---
        premium = evidence.get("premium_percent", 0.0)
        premium_change = evidence.get("premium_change", 0.0)
        premium_stressed = (
            abs(premium) > self._thresholds.get("premium_magnitude", 2.0)
            or abs(premium_change) > self._thresholds.get("premium_change", 1.0)
        )
        families.append(EvidenceFamily(
            name="PREMIUM_STRESS",
            stressed=premium_stressed,
            evidence={
                "premium_percent": premium,
                "premium_change": premium_change,
                "threshold_magnitude": self._thresholds.get("premium_magnitude", 2.0),
                "threshold_change": self._thresholds.get("premium_change", 1.0),
            },
        ))

        # --- Family B: Volatility Stress ---
        volatility = evidence.get("volatility", 0.0)
        vol_stressed = volatility > self._thresholds.get("volatility", 1.5)
        families.append(EvidenceFamily(
            name="VOLATILITY_STRESS",
            stressed=vol_stressed,
            evidence={
                "volatility": volatility,
                "threshold": self._thresholds.get("volatility", 1.5),
            },
        ))

        # --- Family C: USD / Market Structure Stress ---
        usd_change = evidence.get("usd_change", 0.0)
        spread = evidence.get("platform_spread", 0.0)
        structure_stressed = (
            abs(usd_change) > self._thresholds.get("usd_change", 0.5)
            or spread > self._thresholds.get("platform_spread", 500000.0)
        )
        families.append(EvidenceFamily(
            name="STRUCTURE_STRESS",
            stressed=structure_stressed,
            evidence={
                "usd_change": usd_change,
                "platform_spread": spread,
                "threshold_usd_change": self._thresholds.get("usd_change", 0.5),
                "threshold_spread": self._thresholds.get("platform_spread", 500000.0),
            },
        ))

        # --- Family D: External Event Stress ---
        news_count = evidence.get("high_impact_news_count", 0)
        event_stressed = news_count >= self._thresholds.get("news_density", 3)
        families.append(EvidenceFamily(
            name="EVENT_STRESS",
            stressed=event_stressed,
            evidence={
                "high_impact_news_count": news_count,
                "threshold": self._thresholds.get("news_density", 3),
            },
        ))

        return families

    def _candidate_from_stress(
        self,
        stressed_count: int,
        evidence: Dict,
        families: List[EvidenceFamily],
    ) -> str:
        """Determine raw candidate regime from stress count and evidence."""
        # Check for relief first: previously elevated, now easing
        previous = evidence.get("previous_regime") or self._previous_state
        if previous in ("FEAR", "PANIC"):
            if stressed_count < 2 and self._is_easing(evidence):
                return "RELIEF"

        # Standard stress-based classification
        if stressed_count == 0:
            return "NORMAL"
        if stressed_count == 1:
            return "FEAR"
        if stressed_count >= 2:
            return "PANIC"

        return "UNKNOWN"

    def _is_easing(self, evidence: Dict) -> bool:
        """Check if market stress is materially easing."""
        premium_change = evidence.get("premium_change", 0.0)
        # Easing = premium change is small (toward stability)
        return abs(premium_change) < self._thresholds.get("premium_change", 1.0)

    def _apply_hysteresis(self, candidate: str) -> tuple:
        """Apply hysteresis to candidate regime.

        Returns:
            (final_state, hysteresis_active)
        """
        if not self._hysteresis_enabled:
            self._previous_state = candidate
            self._candidate_state = candidate
            self._confirmation_count = 0
            return candidate, False

        # No previous state — accept immediately
        if self._previous_state is None:
            self._previous_state = candidate
            self._candidate_state = candidate
            self._confirmation_count = 0
            return candidate, False

        # Same as current — no transition needed
        if candidate == self._previous_state:
            self._candidate_state = candidate
            self._confirmation_count = 0
            return candidate, False

        # Transition in progress
        if self._candidate_state == candidate:
            self._confirmation_count += 1
        else:
            self._candidate_state = candidate
            self._confirmation_count = 1

        if self._confirmation_count < self._confirmation_periods:
            # Not yet confirmed — hold previous state
            return self._previous_state, True

        # Confirmed — accept new state
        self._previous_state = candidate
        self._confirmation_count = 0
        return candidate, False


# ---------------------------------------------------------------------------
# Calibration — thresholds derived from the market's own recent distribution
# ---------------------------------------------------------------------------

def _percentile(values, percentile: int):
    """Value at a percentile of a sorted sample, by rank."""
    if not values:
        return None
    ordered = sorted(values)
    index = int(percentile / 100.0 * len(ordered))
    return ordered[max(0, min(len(ordered) - 1, index))]


def resolve_stress_thresholds(session, window_days: int = CALIBRATION_WINDOW_DAYS,
                              now: Optional[datetime] = None) -> Dict[str, float]:
    """Stress thresholds recalculated from recent history.

    Kept separate from RegimeClassifier so the classifier itself stays a pure,
    deterministic function of its inputs and the thresholds handed to it: the same
    evidence and the same thresholds must always produce the same regime, which is
    what makes it testable. This function is the only part that touches the database.

    Returns only the keys it can actually measure. Volatility and USD change are left
    to their defaults because nothing here has measured whether those two constants
    are wrong, and replacing a threshold on suspicion is how the fixed ones got here.

    An empty dict on any failure, so the classifier falls back to its defaults rather
    than the caller losing a regime reading altogether.
    """
    if session is None:
        return {}
    if now is None:
        now = datetime.utcnow()

    from database.models import MarketSnapshot, PlatformPrice

    try:
        rows = (
            session.query(MarketSnapshot.id, MarketSnapshot.premium_percent)
            .filter(
                MarketSnapshot.premium_percent.isnot(None),
                MarketSnapshot.timestamp >= now - timedelta(days=window_days),
                MarketSnapshot.timestamp <= now,
            )
            .order_by(MarketSnapshot.timestamp.asc())
            .all()
        )
        premiums = [float(p) for _, p in rows]
        if len(premiums) < MIN_CALIBRATION_OBSERVATIONS:
            return {}

        spreads = []
        prices = (
            session.query(PlatformPrice.snapshot_id, PlatformPrice.price_irr)
            .filter(
                PlatformPrice.snapshot_id.in_([r[0] for r in rows]),
                PlatformPrice.price_irr.isnot(None),
            )
            .all()
        )
        grouped: Dict[int, List[float]] = {}
        for snapshot_id, price in prices:
            grouped.setdefault(snapshot_id, []).append(float(price))
        for values in grouped.values():
            if len(values) >= 2:
                spreads.append(max(values) - min(values))
    except Exception as e:
        print(f"Regime threshold calibration failed: {e}")
        return {}

    magnitudes = [abs(p) for p in premiums]
    changes = [abs(premiums[i + 1] - premiums[i]) for i in range(len(premiums) - 1)]

    thresholds: Dict[str, float] = {}
    magnitude = _percentile(magnitudes, STRESS_PERCENTILE)
    if magnitude is not None:
        thresholds["premium_magnitude"] = round(magnitude, 4)
    change = _percentile(changes, STRESS_PERCENTILE)
    if change is not None:
        thresholds["premium_change"] = round(change, 4)
    spread = _percentile(spreads, STRESS_PERCENTILE)
    if spread is not None:
        thresholds["platform_spread"] = round(spread, 2)
    return thresholds
