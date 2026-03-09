"""Notify Telegram action: sends a message to a Telegram chat."""

import logging
import os
import re
import requests
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _fill_template(template: str, variables: Dict[str, Any]) -> str:
    def replacer(match: re.Match) -> str:
        key = match.group(1)
        return str(variables.get(key, match.group(0)))
    return re.sub(r"\{(\w+)\}", replacer, template)


def execute(action: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
    """Send a Telegram message. Returns variables unchanged."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = action.get("chat_id") or variables.get("chat_id", "")
    message_template = action.get("message", "{data}")
    message = _fill_template(message_template, variables)

    if not token:
        logger.warning("No TELEGRAM_BOT_TOKEN set, skipping notification")
        return variables
    if not chat_id:
        logger.warning("No chat_id for Telegram notification, skipping")
        return variables

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(url, json={"chat_id": chat_id, "text": message[:4096]}, timeout=30)
        if resp.ok:
            logger.info("Telegram notification sent to %s", chat_id)
        else:
            logger.warning("Telegram send failed: %s", resp.text[:200])
    except Exception as e:
        logger.warning("Telegram send error: %s", e)

    return variables
