"""Deep-discount push: when to interrupt the reader, and when to stay quiet.

A push exists for one reason. The deep zone typically closes inside five hours, and
half its episodes last under two, so a reader who only looks when they remember to
look will miss most of them. Everything else the system knows can wait for /Analyze.

This is not a BUY alert and must never read as one. `skills/telegram-product.md`
holds that external BUY/SELL alerts are driven only by the deterministic
`final_decision`; this reports that a measured level was reached and recommends
nothing. `CHEAP != BUY` applies here as everywhere else.

--------------------------------------------------------------------------------
The thermostat
--------------------------------------------------------------------------------

Firing whenever the discount crosses a line does not work. The discount jitters
across any fixed level, so one episode produces a burst of alerts. Measured over 44
days of production data at the 85th percentile: 23 crossings, median duration twelve
minutes, and on 8-9 August four alerts inside 41 hours for a single episode that
never went anywhere.

So there are two levels, like a thermostat that heats at 20C and will not switch on
again until the room has actually fallen to 18. Fire at the high level; re-arm only
after the discount has returned below the low one. Same data, same 85th percentile:
9 alerts instead of 23, never less than 23 hours apart, 14 flickers suppressed.

--------------------------------------------------------------------------------
Why the band is a width and not a second percentile
--------------------------------------------------------------------------------

The obvious design is "fire at p85, re-arm at p50". Measured across the observation
period, the distance between those two percentiles ranged from 0.24 to 0.84
percentage points, while the typical reading-to-reading change is 0.14 pp and its
90th percentile is 0.46 pp. At the narrow end the band would have been half the
noise it exists to filter, and flicker would have survived.

A percentile pair has a width that drifts independently of the thing it is filtering.
So the re-arm level is the fire level minus a width tied to the noise directly.
Sweeping that width against the same data, the alert count stops falling at roughly
1.5x the 90th-percentile step and below that begins merging genuinely separate
episodes.

--------------------------------------------------------------------------------
Both levels move
--------------------------------------------------------------------------------

The 85th percentile of the discount moved 0.81 pp over six weeks: 4.49% on 13 August,
3.70% on 21 September. A fixed level set at either date would be wrong at the other,
which is the failure that produced valuation CHEAP on every reading and regime PANIC
on every snapshot. Both levels are recomputed from completed days only, so they hold
still within a day and step at the boundary.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from analysis.analyze_report import _percentile, _settled_series
from analysis.bubble_position import DEFAULT_WINDOW_DAYS, MIN_OBSERVATIONS

# Rank at which the discount is deep enough to interrupt someone. Measured: this is
# also median + 1 standard deviation to within 0.02 pp, the distribution having become
# near-symmetric once the trimmed basis removed the outlier tail. Expressed as a rank
# because that is the ruler the rest of the system uses and because it survives the
# distribution skewing again.
FIRE_PERCENTILE = 85

# Band width as a multiple of the 90th-percentile reading-to-reading change. The
# elbow in the measured sweep; below it flicker survives, above it separate episodes
# merge.
REARM_NOISE_MULTIPLE = 1.5

# Floor on the band. If the market goes very quiet the noise measure collapses and a
# proportional band would collapse with it, reinstating the flicker.
MIN_REARM_BAND_PP = 0.25


@dataclass
class PushThresholds:
    fire_at: Optional[float] = None
    rearm_at: Optional[float] = None
    band_pp: Optional[float] = None
    noise_pp: Optional[float] = None
    sample_size: int = 0
    status: str = "INSUFFICIENT_DATA"


@dataclass
class PushDecision:
    should_fire: bool = False
    armed_after: bool = True
    reason: str = "NO_DATA"
    gap: Optional[float] = None
    fire_at: Optional[float] = None
    rearm_at: Optional[float] = None


def resolve_push_thresholds(
    session,
    now: Optional[datetime] = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> PushThresholds:
    """Fire and re-arm levels, recomputed from completed days."""
    result = PushThresholds()
    if session is None:
        return result
    if now is None:
        now = datetime.utcnow()

    try:
        series = _settled_series(session, now, window_days)
    except Exception as e:
        print(f"Push threshold query failed: {e}")
        return result

    result.sample_size = len(series)
    if len(series) < MIN_OBSERVATIONS:
        return result

    sizes = sorted(abs(item[2]) for item in series)
    fire_at = _percentile(sizes, FIRE_PERCENTILE)
    if fire_at is None:
        return result

    steps = []
    for index in range(1, len(series)):
        hours = (series[index][0] - series[index - 1][0]).total_seconds() / 3600.0
        if 0 < hours <= 2.0:
            steps.append(abs(abs(series[index][2]) - abs(series[index - 1][2])))
    noise = _percentile(sorted(steps), 90) if steps else None
    band = max(MIN_REARM_BAND_PP,
               (noise or 0) * REARM_NOISE_MULTIPLE)

    result.fire_at = round(fire_at, 4)
    result.noise_pp = round(noise, 4) if noise is not None else None
    result.band_pp = round(band, 4)
    result.rearm_at = round(max(0.0, fire_at - band), 4)
    result.status = "OK"
    return result


def evaluate_push(
    current_gap: Optional[float],
    thresholds: PushThresholds,
    armed: Optional[bool],
) -> PushDecision:
    """Decide whether to interrupt, and what the armed state becomes.

    Pure: no clock, no database, no configuration. Every branch is reachable from a
    test, which is the point -- this project has produced four suppression rules that
    were documented as temporary and shipped as permanent.

    `armed=None` means the persisted state could not be read, and is deliberately
    treated as armed. The state lives in state.json, carried between runs by the
    Actions cache -- the same cache whose loss latched `last_alert` into a permanent
    WAIT and suppressed 100 consecutive BUY candidates. A lost cache must cost a
    duplicate message, which is noise. The opposite costs silence, which is the
    failure this project has already paid for once and which nothing alerts on.
    """
    decision = PushDecision(gap=current_gap)
    if thresholds.status != "OK" or current_gap is None:
        decision.reason = "NO_DATA"
        decision.armed_after = True if armed is None else armed
        return decision

    size = abs(current_gap)
    decision.fire_at = thresholds.fire_at
    decision.rearm_at = thresholds.rearm_at
    is_armed = True if armed is None else bool(armed)

    if is_armed and size >= thresholds.fire_at:
        decision.should_fire = True
        decision.armed_after = False
        decision.reason = "FIRED" if armed is not None else "FIRED_STATE_UNKNOWN"
        return decision

    if not is_armed and size < thresholds.rearm_at:
        decision.armed_after = True
        decision.reason = "REARMED"
        return decision

    decision.armed_after = is_armed
    decision.reason = "BELOW_FIRE" if is_armed else "HELD_BY_BAND"
    return decision
