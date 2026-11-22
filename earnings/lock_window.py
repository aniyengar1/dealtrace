"""Owner operating policy, separate from frozen baseline/historical horizons."""
from datetime import timedelta,timezone
from zoneinfo import ZoneInfo
VERSION='live-entry-17-calendar-days-v1'
DAYS=17

def opening(deadline,zone):
    """Subtract local calendar days; preserve release-zone clock through DST."""
    return (deadline.astimezone(ZoneInfo(zone))-timedelta(days=DAYS)).astimezone(timezone.utc)
