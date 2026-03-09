"""Validate agent config structure before running."""

from typing import Any, Dict, List

VALID_TRIGGER_TYPES = {"scheduled", "polling", "manual"}
VALID_ACTION_TYPES = {"llm_analyze", "notify_telegram", "notify_whatsapp", "http_request"}
REQUIRED_TOP_LEVEL = {"name", "trigger", "actions"}


def validate(config: Dict[str, Any]) -> List[str]:
    """Return list of error strings. Empty list means config is valid."""
    errors: List[str] = []

    if not isinstance(config, dict):
        return ["Config must be a YAML mapping (dictionary)."]

    for field in REQUIRED_TOP_LEVEL:
        if field not in config:
            errors.append(f"Missing required field: '{field}'")

    if errors:
        return errors

    name = config.get("name", "")
    if not isinstance(name, str) or not name.strip():
        errors.append("'name' must be a non-empty string.")

    trigger = config.get("trigger", {})
    if not isinstance(trigger, dict):
        errors.append("'trigger' must be a mapping.")
    else:
        t_type = trigger.get("type", "")
        if t_type not in VALID_TRIGGER_TYPES:
            errors.append(f"Unknown trigger type '{t_type}'. Must be one of: {VALID_TRIGGER_TYPES}")
        if t_type == "polling":
            source = trigger.get("source", "")
            if source == "github_issues" and not trigger.get("repo"):
                errors.append("Polling trigger with source 'github_issues' requires 'repo' field.")
            if source == "url_check" and not trigger.get("url"):
                errors.append("Polling trigger with source 'url_check' requires 'url' field.")

    actions = config.get("actions", [])
    if not isinstance(actions, list) or len(actions) == 0:
        errors.append("'actions' must be a non-empty list.")
    else:
        for i, action in enumerate(actions):
            if not isinstance(action, dict):
                errors.append(f"Action {i} must be a mapping.")
                continue
            a_type = action.get("type", "")
            if a_type not in VALID_ACTION_TYPES:
                errors.append(f"Action {i}: unknown type '{a_type}'. Must be one of: {VALID_ACTION_TYPES}")
            if a_type == "llm_analyze" and not action.get("prompt"):
                errors.append(f"Action {i}: 'llm_analyze' requires a 'prompt' field.")
            if a_type == "notify_telegram" and not action.get("message"):
                errors.append(f"Action {i}: 'notify_telegram' requires a 'message' field.")
            if a_type == "notify_whatsapp" and not action.get("message"):
                errors.append(f"Action {i}: 'notify_whatsapp' requires a 'message' field.")
            if a_type == "http_request" and not action.get("url"):
                errors.append(f"Action {i}: 'http_request' requires a 'url' field.")

        # Check: scheduled/manual trigger + llm_analyze but no http_request = LLM has no data
        action_types = [a.get("type", "") for a in actions if isinstance(a, dict)]
        trigger_type = trigger.get("type", "") if isinstance(trigger, dict) else ""
        if trigger_type in ("scheduled", "manual"):
            if "llm_analyze" in action_types and "http_request" not in action_types:
                errors.append(
                    "Agent needs data from the internet but has no 'http_request' action. "
                    "Add an http_request before llm_analyze to fetch data first."
                )

    return errors
