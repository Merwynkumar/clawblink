"""HTTP Request action: makes a GET/POST request and stores the response."""

import logging
import re
import requests as http_lib
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _fill_template(template: str, variables: Dict[str, Any]) -> str:
    def replacer(match: re.Match) -> str:
        key = match.group(1)
        return str(variables.get(key, match.group(0)))
    return re.sub(r"\{(\w+)\}", replacer, template)


def _html_to_text(html: str) -> str:
    """Strip HTML tags and extract readable text."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&#\d+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def execute(action: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
    """Make an HTTP request. Stores response text in output variable."""
    url = _fill_template(action.get("url", ""), variables)
    method = action.get("method", "GET").upper()
    headers = dict(action.get("headers", {}))
    if "User-Agent" not in headers:
        headers["User-Agent"] = DEFAULT_USER_AGENT
    output_key = action.get("output", "data")

    if not url:
        logger.warning("http_request: no URL provided")
        return variables

    try:
        if method == "POST":
            body = action.get("body", {})
            resp = http_lib.post(url, json=body, headers=headers, timeout=30)
        else:
            resp = http_lib.get(url, headers=headers, timeout=30)

        if resp.status_code >= 400:
            variables[output_key] = f"(HTTP error: {resp.status_code} {resp.reason})"
            logger.warning("HTTP %s %s -> %d %s", method, url[:60], resp.status_code, resp.reason)
            return variables

        content = resp.text
        content_type = resp.headers.get("content-type", "")
        if "html" in content_type.lower() or content.strip().startswith("<"):
            content = _html_to_text(content)

        variables[output_key] = content[:5000]
        logger.info("HTTP %s %s -> %d", method, url[:60], resp.status_code)
    except Exception as e:
        logger.warning("HTTP request failed: %s", e)
        variables[output_key] = f"(HTTP error: {e})"

    return variables
