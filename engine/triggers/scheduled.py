"""Scheduled trigger: runs an agent at fixed intervals or at a fixed time daily."""

import logging
import re
from datetime import date, datetime, time as dt_time
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


def _parse_time_local(s: str) -> Optional[tuple[int, int]]:
    """Parse 'HH:MM' or 'H:MM' to (hour, minute). Returns None if invalid."""
    if not s or not isinstance(s, str):
        return None
    m = re.match(r"^(\d{1,2}):(\d{2})$", s.strip())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if 0 <= h <= 23 and 0 <= mi <= 59:
        return (h, mi)
    return None


class ScheduledTrigger:
    """Fires a callback on a fixed interval (in minutes) or once daily at a fixed local time."""

    def __init__(self, config: Dict[str, Any], callback: Callable[[Dict[str, Any]], None]):
        self.callback = callback
        self._running = False
        time_local = config.get("time_local") or config.get("time_local_utc")
        parsed = _parse_time_local(str(time_local)) if time_local else None
        if parsed:
            self.time_local = f"{parsed[0]:02d}:{parsed[1]:02d}"
            self._hour, self._minute = parsed
            self.interval_minutes = 1440
        else:
            self.time_local = None
            self._hour, self._minute = None, None
            self.interval_minutes = max(1, int(config.get("interval_minutes", 5)))

    def should_fire_now(self, last_run_timestamp: Optional[float]) -> bool:
        """True if we should fire now: it's at or past time_local today and we haven't run today yet."""
        if not self.time_local or self._hour is None:
            return False
        now = datetime.now()
        today = now.date()
        run_at = datetime.combine(today, dt_time(self._hour, self._minute, 0))
        if now < run_at:
            return False
        if last_run_timestamp is None:
            return True
        last_date = datetime.fromtimestamp(last_run_timestamp).date()
        return last_date < today

    def fire(self) -> None:
        """Called by the runner's scheduler loop."""
        logger.info("Scheduled trigger firing")
        today = date.today().isoformat()
        self.callback({
            "data": "scheduled tick",
            "source": "scheduled",
            "start_date": today,
            "end_date": today,
        })
