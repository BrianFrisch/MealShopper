from datetime import datetime, timezone, timedelta
from typing import List

def get_circular_cycle_key(target_date: datetime | None = None) -> str:
    """
    Returns a deterministic cycle key (e.g. '2026-W39') anchored to Thursday 00:00 UTC.
    Wednesday is weekday index 2; Thursday is weekday index 3.
    """
    dt = target_date or datetime.now(timezone.utc)
    # Align to previous or current Thursday
    # weekday(): Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4, Saturday=5, Sunday=6
    days_since_thursday = (dt.weekday() - 3) % 7
    cycle_start = (dt - timedelta(days=days_since_thursday)).date()
    
    # ISO calendar week number of the cycle start
    iso_year, iso_week, _ = cycle_start.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def get_spanning_cycle_keys(valid_from: datetime, valid_to: datetime) -> List[str]:
    """
    Generates all distinct cycle keys covered between valid_from and valid_to.
    """
    cycles: set[str] = set()
    current = valid_from
    while current <= valid_to:
        cycles.add(get_circular_cycle_key(current))
        current += timedelta(days=3)  # Step by 3 days to safely sample each weekly window
    cycles.add(get_circular_cycle_key(valid_to))
    return sorted(cycles)