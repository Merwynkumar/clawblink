"""LLM Analyze action: sends data + prompt to LLM and stores the result."""

import logging
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _fill_template(template: str, variables: Dict[str, Any]) -> str:
    """Replace {variable} placeholders with values from the variables dict."""
    def replacer(match: re.Match) -> str:
        key = match.group(1)
        return str(variables.get(key, match.group(0)))
    return re.sub(r"\{(\w+)\}", replacer, template)


def execute(
    action: Dict[str, Any],
    variables: Dict[str, Any],
    llm,
) -> Dict[str, Any]:
    """Run llm_analyze action. Returns updated variables dict."""
    prompt_template = action.get("prompt", "Analyze this: {data}")
    prompt = _fill_template(prompt_template, variables)

    _ERROR_SIGNALS = [
        "(HTTP error:",
        "500 internal", '"error":', '"error_message":', '"error_code":',
        "Unauthorized", "Forbidden", "Invalid API Key",
        "access key", "invalid_access_key",
    ]
    prompt_lower = prompt.lower()
    # Skip LLM when upstream is clearly an error (HTTP 4xx/5xx or short error-like content).
    is_short = len(prompt) < 800
    looks_like_error = any(sig.lower() in prompt_lower for sig in _ERROR_SIGNALS)
    if is_short and looks_like_error:
        logger.warning("Skipping LLM call -- upstream data looks like an error")
        output_key = action.get("output", "analysis")
        variables[output_key] = (
            "The source URL returned an error or no data (e.g. 404). "
            "You can check /config for the agent URL or try /run again later."
        )
        return variables

    system = (
        "You are a data analysis assistant. The user's message contains REAL DATA that was "
        "already fetched for you. Analyze ONLY the data in the message. "
        "NEVER say you cannot access anything. The data is RIGHT THERE. "
        "Be concise and useful."
    )

    try:
        result = llm.generate(prompt, system=system)
    except Exception as e:
        logger.warning("LLM analyze failed: %s", e)
        result = f"(LLM error: {e})"

    output_key = action.get("output", "analysis")
    variables[output_key] = result
    return variables
