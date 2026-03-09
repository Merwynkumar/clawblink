"""Notify WhatsApp action: sends a WhatsApp message via Twilio API."""

import logging
import os
import re
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)


def _fill_template(template: str, variables: Dict[str, Any]) -> str:
    def replacer(match: re.Match) -> str:
        key = match.group(1)
        return str(variables.get(key, match.group(0)))

    return re.sub(r"\{(\w+)\}", replacer, template)


def execute(action: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
    """Send a WhatsApp message using Twilio. Returns variables unchanged."""
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    from_number = os.environ.get("TWILIO_WHATSAPP_FROM", "")

    to_number = action.get("to") or variables.get("whatsapp_to", "")
    message_template = action.get("message", "{data}")
    message = _fill_template(message_template, variables)

    if not account_sid or not auth_token or not from_number:
        logger.warning("Twilio WhatsApp env vars not set, skipping WhatsApp notification")
        return variables

    if not to_number:
        logger.warning("No 'to' number for WhatsApp notification, skipping")
        return variables

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    data = {
        "From": from_number,
        "To": to_number,
        "Body": message[:1600],
    }

    try:
        resp = requests.post(url, data=data, auth=(account_sid, auth_token), timeout=30)
        if resp.ok:
            logger.info("WhatsApp notification sent to %s", to_number)
        else:
            logger.warning("WhatsApp send failed: %s", resp.text[:200])
    except Exception as e:
        logger.warning("WhatsApp send error: %s", e)

    return variables

