"""Manual trigger: fired by user via /run command."""

import logging
from typing import Any, Callable, Dict

logger = logging.getLogger(__name__)


class ManualTrigger:
    """Fires only when explicitly triggered by the user (via /run command)."""

    def __init__(self, config: Dict[str, Any], callback: Callable[[Dict[str, Any]], None]):
        self.callback = callback
        self.interval_minutes = 0

    def fire(self) -> None:
        logger.info("Manual trigger fired")
        self.callback({"data": "manual trigger", "source": "manual"})
