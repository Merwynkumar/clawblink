"""Scheduled trigger: runs an agent at fixed intervals."""

import logging
from typing import Any, Callable, Dict

logger = logging.getLogger(__name__)


class ScheduledTrigger:
    """Fires a callback on a fixed interval (in minutes)."""

    def __init__(self, config: Dict[str, Any], callback: Callable[[Dict[str, Any]], None]):
        self.interval_minutes = max(1, int(config.get("interval_minutes", 5)))
        self.callback = callback
        self._running = False

    def fire(self) -> None:
        """Called by the runner's scheduler loop."""
        logger.info("Scheduled trigger firing")
        self.callback({"data": "scheduled tick", "source": "scheduled"})
