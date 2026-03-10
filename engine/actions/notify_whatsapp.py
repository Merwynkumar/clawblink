"""Notify WhatsApp action.

By default this sends a WhatsApp message via the local WhatsApp Web
bridge (see bridge/whatsapp/gateway.js), which exposes an HTTP endpoint
at http://127.0.0.1:8071/send.

Advanced users can still point this at a different endpoint by setting
CLAWBLINK_WHATSAPP_SEND_URL in the environment.
"""

import logging
import re
from typing import Any, Dict

import os
import requests

logger = logging.getLogger(__name__)


def _fill_template(template: str, variables: Dict[str, Any]) -> str:
    def replacer(match: re.Match) -> str:
        key = match.group(1)
        return str(variables.get(key, match.group(0)))

    return re.sub(r"\{(\w+)\}", replacer, template)


def execute(action: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
    """Send a WhatsApp message via the local WhatsApp Web bridge.

    Returns the variables dict unchanged.
    """
    send_url = os.environ.get(
        "CLAWBLINK_WHATSAPP_SEND_URL", "http://127.0.0.1:8071/send"
    )

    to_number = action.get("to") or variables.get("whatsapp_to", "")
    message_template = action.get("message", "{data}")
    message = _fill_template(message_template, variables)

    if not to_number:
        logger.warning("No 'to' number for WhatsApp notification, skipping")
        return variables

    payload = {"to": to_number, "text": message[:1600]}

    try:
        resp = requests.post(send_url, json=payload, timeout=10)
        if resp.ok:
            logger.info("WhatsApp notification sent to %s via bridge", to_number)
        else:
            logger.warning(
                "WhatsApp send failed via bridge (%s): %s",
                resp.status_code,
                resp.text[:200],
            )
    except Exception as e:
        logger.warning("WhatsApp send error via bridge: %s", e)

    return variables

