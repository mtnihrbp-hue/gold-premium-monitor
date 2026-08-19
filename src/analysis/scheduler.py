"""Analysis Wing scheduler contract.

PRE-SP-C.2: configurable scheduling logic for system-triggered analysis.
Does NOT implement production cron — defines the architecture contract only.

Default schedule:
    timezone: Asia/Tehran
    interval: 30 minutes
    daily window: 08:00 (inclusive) → 21:00 (exclusive)
    active days: configurable per weekday
"""

from datetime import datetime, timedelta, time
from typing import Optional, List

DEFAULT_TIMEZONE = "Asia/Tehran"
DEFAULT_INTERVAL_MINUTES = 30
DEFAULT_START_TIME = time(8, 0)
DEFAULT_END_TIME = time(21, 0)
DEFAULT_ACTIVE_DAYS = [0, 1, 2, 3, 4, 5, 6]  # Monday=0 through Sunday=6


def generate_source_run_id(
    analysis_timestamp: datetime,
    prefix: str = "analysis",
) -> str:
    """Generate a deterministic source run ID for idempotency.

    Format: analysis_YYYYMMDD_HHMM

    Args:
        analysis_timestamp: the scheduled analysis timestamp
        prefix: run ID prefix

    Returns:
        deterministic string suitable for UNIQUE constraint
    """
    return f"{prefix}_{analysis_timestamp.strftime('%Y%m%d_%H%M')}"


def is_analysis_window(
    dt: datetime,
    start_time: time = DEFAULT_START_TIME,
    end_time: time = DEFAULT_END_TIME,
    active_days: Optional[List[int]] = None,
) -> bool:
    """Check if a datetime falls within the configured analysis window.

    Args:
        dt: datetime to check
        start_time: inclusive start of daily window
        end_time: exclusive end of daily window
        active_days: list of weekday integers (0=Monday); None = all days

    Returns:
        True if dt is within the analysis window
    """
    if active_days is None:
        active_days = DEFAULT_ACTIVE_DAYS

    if dt.weekday() not in active_days:
        return False

    current_time = dt.time()
    if current_time < start_time:
        return False
    if current_time >= end_time:
        return False

    return True


def get_next_analysis_windows(
    from_time: Optional[datetime] = None,
    count: int = 5,
    interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
    start_time: time = DEFAULT_START_TIME,
    end_time: time = DEFAULT_END_TIME,
    active_days: Optional[List[int]] = None,
) -> List[datetime]:
    """Generate the next N analysis window datetimes from a reference time.

    The reference time itself is never returned. If the reference lands
    exactly on a schedule boundary, the next boundary is returned.

    Args:
        from_time: reference time (default: now)
        count: number of windows to generate
        interval_minutes: minutes between analysis windows
        start_time: inclusive daily start
        end_time: exclusive daily end
        active_days: list of weekday integers; None = all days

    Returns:
        List of datetimes representing upcoming analysis windows
    """
    if from_time is None:
        from_time = datetime.now()

    if active_days is None:
        active_days = DEFAULT_ACTIVE_DAYS

    windows = []
    candidate = from_time.replace(second=0, microsecond=0)

    remainder = candidate.minute % interval_minutes
    if remainder != 0:
        candidate = candidate + timedelta(minutes=interval_minutes - remainder)
    else:
        candidate = candidate + timedelta(minutes=interval_minutes)

    while len(windows) < count:
        if candidate.weekday() not in active_days:
            candidate = candidate + timedelta(days=1)
            candidate = candidate.replace(hour=start_time.hour, minute=start_time.minute)
            continue

        if candidate.time() < start_time:
            candidate = candidate.replace(hour=start_time.hour, minute=start_time.minute)
            continue

        if candidate.time() >= end_time:
            candidate = candidate + timedelta(days=1)
            candidate = candidate.replace(hour=start_time.hour, minute=start_time.minute)
            continue

        windows.append(candidate)
        candidate = candidate + timedelta(minutes=interval_minutes)

    return windows


def should_run_analysis(
    dt: Optional[datetime] = None,
    config: Optional[dict] = None,
) -> bool:
    """Determine whether analysis should run at the given time.

    Args:
        dt: datetime to evaluate (default: now)
        config: scheduler configuration dict

    Returns:
        True if analysis should proceed
    """
    if dt is None:
        dt = datetime.now()

    if config is None:
        config = {}

    scheduler_cfg = config.get("scheduler", {})
    start = _parse_time(scheduler_cfg.get("start_time", "08:00"))
    end = _parse_time(scheduler_cfg.get("end_time", "21:00"))
    active = scheduler_cfg.get("active_days", DEFAULT_ACTIVE_DAYS)

    if not is_analysis_window(dt, start, end, active):
        return False

    return True


def _parse_time(time_str: str) -> time:
    """Parse HH:MM string into time object."""
    parts = time_str.split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    return time(hour, minute)
