"""Turn a plain-English user message into a YAML agent config using an LLM."""

import logging
import re
import yaml
import requests
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Short prompt = fewer tokens = faster generation and less timeout risk.
SYSTEM_PROMPT = """You create YAML agent configs. Output ONLY valid YAML, no markdown or commentary.

Structure:
name: kebab-case-name
description: one sentence
trigger:
  type: scheduled
  interval_minutes: 5
actions:
  - type: http_request
    method: GET
    url: "https://..."
    output: raw_data
  - type: llm_analyze
    prompt: "Turn into short chat message, bullet points, no HTML. Content: {raw_data}"
    output: summary
  - type: notify_telegram
    message: "{summary}"

Rules:
- Data from internet MUST come from http_request first (LLM cannot fetch). Then llm_analyze to make it chat-readable, then notify.
- When the user asks to explain, teach, learn, or get tips/lessons on a topic (programming, language, skill), the llm_analyze prompt MUST ask for one clear takeaway or concept plus a short example when relevant (e.g. code for programming), not a full-page summary. E.g. "Pick one concept from the content, explain briefly, add a short example if relevant. Chat-friendly. Content: {raw_data}"
- Scheduled: "every X minutes" -> interval_minutes: X. "every morning" -> time_local: "08:00", interval_minutes: 1440. "hourly" -> 60. "daily" -> 1440.
- For news/sports/weather use scheduled + http_request. No github_issues unless user asked for GitHub. No API keys.
- Match user source: BBC -> bbc.com/news, CNN -> lite.cnn.com. Sports -> bbc.com/sport/football/scores-fixtures. Prices: coingecko, yahoo finance. Weather: wttr.in/City?format=j1.
- Keep YAML minimal. Use real, working URLs (they are validated after generation)."""


def _extract_yaml(raw: str) -> str:
    """Extract YAML from LLM output, stripping markdown fences and prose."""
    text = raw.strip()
    match = re.search(r"```(?:ya?ml)?\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    lines = text.split("\n")
    yaml_lines = []
    started = False
    for line in lines:
        if not started and (line.startswith("name:") or line.startswith("---")):
            started = True
        if started:
            yaml_lines.append(line)
    return "\n".join(yaml_lines).strip() if yaml_lines else text


# Known-good URLs by intent. Used to set correct URL at creation time (generic for any agent).
# Extend this map to cover more use cases; validation + LLM suggestion still run for anything not matched.
_FALLBACK_URLS: Dict[str, str] = {
    "news": "https://www.bbc.com/news",
    "bbc": "https://www.bbc.com/news",
    "cnn": "https://lite.cnn.com",
    "sports": "https://www.bbc.com/sport/football/scores-fixtures",
    "football": "https://www.bbc.com/sport/football/scores-fixtures",
}

_EDUCATIONAL_URLS: Dict[str, str] = {
    "python": "https://docs.python.org/3/tutorial/",
    "javascript": "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide",
    "java": "https://docs.oracle.com/javase/tutorial/",
    "sql": "https://www.w3schools.com/sql/",
    "programming": "https://docs.python.org/3/tutorial/",
}

# Other common intents (prices, weather, etc.) so more use cases get correct URL at creation.
_OTHER_KNOWN_URLS: Dict[str, str] = {
    "weather": "https://wttr.in/London?format=j1",
    "gold": "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1d&range=1d",
    "silver": "https://query1.finance.yahoo.com/v8/finance/chart/SI=F?interval=1d&range=1d",
    "bitcoin": "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
    "crypto": "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd",
}

# Timeout and max size for URL validation.
_URL_CHECK_TIMEOUT = 10
_URL_CHECK_MAX_BODY = 8192  # bytes to read for content check


def _content_looks_like_error_page(text: str) -> bool:
    """True if the content looks like a generic error/not-found page, not real data."""
    if not text or len(text) < 50:
        return True
    t = text[: _URL_CHECK_MAX_BODY].lower()
    # One strong signal: explicit 404 or "not found" style.
    has_404 = "404" in t
    has_not_found = "not found" in t or "file not found" in t or "page not found" in t
    has_error_language = any(
        x in t
        for x in (
            "error",
            "couldn't find",
            "could not find",
            "broken link",
            "does not exist",
            "doesn't exist",
            "we couldn't find what you were looking for",
            "what you were looking for",
            "look into it shortly",
        )
    )
    if has_404 and (has_not_found or has_error_language or "file" in t):
        return True
    if has_not_found and has_error_language:
        return True
    if "500" in t and "internal server error" in t:
        return True
    return False


def _validate_url(url: str) -> bool:
    """Return True if the URL returns 2xx and body looks like real content, not an error page."""
    if not url or not url.strip().startswith(("http://", "https://")):
        return False
    try:
        r = requests.get(
            url,
            timeout=_URL_CHECK_TIMEOUT,
            stream=True,
            headers={"User-Agent": "ClawBlink-URL-Check/1.0"},
        )
        if r.status_code < 200 or r.status_code >= 300:
            logger.warning("URL validation failed: %s -> %s", url[:80], r.status_code)
            return False
        # Check that the body has relevant data, not an error page (e.g. 200 but "404 File not found" inside).
        try:
            chunk = b""
            for b in r.iter_content(chunk_size=1024):
                chunk += b
                if len(chunk) >= _URL_CHECK_MAX_BODY:
                    break
            text = chunk.decode("utf-8", errors="replace")
        except Exception:
            text = ""
        if _content_looks_like_error_page(text):
            logger.warning("URL content looks like error page: %s", url[:80])
            return False
        return True
    except Exception as e:
        logger.warning("URL validation error for %s: %s", url[:80], e)
        return False


def _pick_fallback_url(user_message: str) -> Optional[str]:
    """If we have a known-good URL for this request, return it; else None. No HTTP check.
    Check specific intents first (bbc, cnn, python, …) then generic (news, sports)."""
    m = user_message.lower()
    # Specific sources first (so "bbc news" -> bbc URL, not generic news).
    if "bbc" in m:
        return _FALLBACK_URLS["bbc"]
    if "cnn" in m:
        return _FALLBACK_URLS["cnn"]
    if "news" in m:
        return _FALLBACK_URLS["news"]
    if any(x in m for x in ("sport", "football", "league", "score", "fixture")):
        return _FALLBACK_URLS["football"]
    # Prices, weather, etc.
    if "weather" in m:
        return _OTHER_KNOWN_URLS["weather"]
    if "gold" in m:
        return _OTHER_KNOWN_URLS["gold"]
    if "silver" in m:
        return _OTHER_KNOWN_URLS["silver"]
    if "bitcoin" in m or "btc" in m:
        return _OTHER_KNOWN_URLS["bitcoin"]
    if any(x in m for x in ("crypto", "ethereum", "cryptocurrency")):
        return _OTHER_KNOWN_URLS["crypto"]
    # Educational / topic-specific.
    if "python" in m:
        return _EDUCATIONAL_URLS["python"]
    if "javascript" in m or "js " in m:
        return _EDUCATIONAL_URLS["javascript"]
    if "java " in m:
        return _EDUCATIONAL_URLS["java"]
    if "sql" in m:
        return _EDUCATIONAL_URLS["sql"]
    if any(x in m for x in ("code", "programming", "coding", "concept", "tutorial")):
        return _EDUCATIONAL_URLS["programming"]
    return None


def _set_url_from_user_intent(config: Dict[str, Any], user_message: str) -> None:
    """Set the first http_request URL from user intent so the YAML has the correct URL at creation time.
    Generic: whenever we can infer topic/source from the message, use our known-good URL and ignore LLM output."""
    actions = config.get("actions") or []
    first_http = None
    for a in actions:
        if isinstance(a, dict) and a.get("type") == "http_request":
            first_http = a
            break
    if not first_http:
        return
    url = _pick_fallback_url(user_message)
    if url:
        first_http["url"] = url
        logger.info("Set http_request URL from user intent (known-good URL for this request)")


def _ensure_valid_urls(config: Dict[str, Any], user_message: str, llm: Any) -> None:
    """Ensure every http_request URL in config returns 2xx. Replace or ask LLM for one URL if invalid."""
    actions = config.get("actions") or []
    for action in actions:
        if not isinstance(action, dict) or action.get("type") != "http_request":
            continue
        url = action.get("url")
        if not url:
            continue
        url = str(url).strip()
        if _validate_url(url):
            continue
        # Try known fallback first (no extra LLM call).
        replacement = _pick_fallback_url(user_message)
        if replacement and _validate_url(replacement):
            action["url"] = replacement
            logger.info("Replaced invalid URL with fallback: %s", replacement[:60])
            continue
        # Ask LLM for one working URL only (minimal prompt, fast).
        try:
            prompt = (
                f"This URL returned an error or no data: {url}\n"
                f"User request: {user_message}\n"
                "Reply with exactly one working, public URL that fits the request. No API keys. One line, URL only."
            )
            raw = llm.generate(prompt, system=None)
            raw = (raw or "").strip()
            # Extract first URL from response (may be in markdown or plain text).
            found = re.search(r"https?://[^\s\]>\"]+", raw)
            new_url = found.group(0).rstrip(".,;)\]>\"'") if found else None
            if new_url and _validate_url(new_url):
                action["url"] = new_url
                logger.info("Replaced invalid URL with LLM suggestion: %s", new_url[:60])
            else:
                raise ValueError(
                    "Could not find a working URL for your request. Try naming a specific site (e.g. BBC, Python docs)."
                )
        except ValueError:
            raise
        except Exception as e:
            logger.warning("LLM URL suggestion failed: %s", e)
            raise ValueError(
                "The generated URL did not work and we could not fix it. Try rephrasing (e.g. name a specific website)."
            ) from e


def _fix_http_request_actions(config: Dict[str, Any], user_message: str) -> None:
    """Patch config in-place: remove API-key URLs/headers and fix wrong source. No LLM call."""
    msg_lower = user_message.lower()
    actions: List[Dict[str, Any]] = config.get("actions") or []
    for action in actions:
        if not isinstance(action, dict) or action.get("type") != "http_request":
            continue
        url = str(action.get("url", "")).lower()
        headers = action.get("headers")
        if isinstance(headers, dict):
            # Strip any auth headers so we don't require API keys.
            for k in list(headers.keys()):
                if any(x in k.lower() for x in ("auth", "token", "api-key", "x-api-key")):
                    del headers[k]
        # Replace known API-key domains with a no-key fallback.
        if "api.football-data.org" in url or "newsapi.org" in url or "rapidapi.com" in url:
            if "football" in msg_lower or "sport" in msg_lower or "league" in msg_lower:
                action["url"] = _FALLBACK_URLS["football"]
            else:
                action["url"] = _FALLBACK_URLS["news"]
            logger.info("Replaced API-key URL with fallback %s", action["url"])
        # Fix wrong source: user said BBC/CNN but URL is for a different source.
        for source, fallback_url in _FALLBACK_URLS.items():
            if source in ("news", "sports", "football"):
                continue
            if source in msg_lower and source not in url:
                action["url"] = fallback_url
                logger.info("Fixed source: user said %s, set url to %s", source, fallback_url)
                break


def _is_educational_intent(user_message: str) -> bool:
    """True if the user wants to learn/explain/teach/tips rather than e.g. news or prices."""
    m = user_message.lower()
    # Clearly not educational: main ask is news, weather, sports, prices.
    if any(x in m for x in ("news", "weather", "sport", "score", "fixture", "price", "stock", "gold", "silver", "bitcoin", "headline")):
        if not any(x in m for x in ("explain", "teach", "learn", "concept", "tutorial", "lesson", "tip")):
            return False
    # Educational: teach, learn, tutorial, lesson, tip, concept, or "explain [topic]".
    if any(x in m for x in ("teach", "learn", "tutorial", "lesson", "concept", "tip", "how to ")):
        return True
    if "explain" in m and any(x in m for x in ("python", "java", "javascript", "sql", "code", "programming", "coding")):
        return True
    if any(x in m for x in ("with example", "with simple example", "with a sample")):
        return True
    return False


def _fix_educational_prompt(config: Dict[str, Any], user_message: str) -> None:
    """For educational/learning requests, set llm_analyze to one takeaway + example and use known-good URL."""
    if not _is_educational_intent(user_message):
        return
    msg_lower = user_message.lower()
    actions = config.get("actions") or []
    out_var = "raw_data"
    first_http = None
    for a in actions:
        if isinstance(a, dict) and a.get("type") == "http_request":
            out_var = a.get("output", "raw_data")
            first_http = a
            break
    # Programming/code topics: one concept + code example, and set a known-good URL.
    topic_key = None
    if any(x in msg_lower for x in ("python", "java", "javascript", "sql", "code", "programming", "coding")):
        if "python" in msg_lower:
            topic_key = "python"
            topic = "Python"
        elif "javascript" in msg_lower or "js " in msg_lower:
            topic_key = "javascript"
            topic = "JavaScript"
        elif "java " in msg_lower:
            topic_key = "java"
            topic = "Java"
        elif "sql" in msg_lower:
            topic_key = "sql"
            topic = "SQL"
        else:
            topic_key = "programming"
            topic = "programming"
        if first_http and topic_key in _EDUCATIONAL_URLS:
            first_http["url"] = _EDUCATIONAL_URLS[topic_key]
            logger.info("Set http_request URL to known-good educational URL for %s", topic_key)
        prompt = (
            f"Pick one {topic} concept (e.g. variables, loops, functions). "
            "Explain it in 2-3 sentences, then give a short code example. Chat-friendly. "
            f"Content: {{{out_var}}}"
        )
    else:
        # Other learning (language, skill, etc.): one takeaway + short example if relevant.
        prompt = (
            "From the content below, pick one clear concept or takeaway and explain it briefly. "
            "Add a short example if relevant. Chat-friendly. "
            f"Content: {{{out_var}}}"
        )
    for action in actions:
        if isinstance(action, dict) and action.get("type") == "llm_analyze":
            action["prompt"] = prompt
            logger.info("Set llm_analyze to educational (one takeaway + example) for user request")
            break


def _fix_github_issues_trigger(config: Dict[str, Any], user_message: str) -> None:
    """If trigger is github_issues but user didn't ask for GitHub, switch to scheduled + generic. No LLM call."""
    trigger = config.get("trigger") or {}
    if not isinstance(trigger, dict) or trigger.get("source") != "github_issues":
        return
    msg_lower = user_message.lower()
    if any(kw in msg_lower for kw in ("github", "issue", "repo", "repository")):
        return
    trigger["type"] = "scheduled"
    trigger["source"] = "generic"
    trigger.pop("repo", None)
    if "interval_minutes" not in trigger:
        trigger["interval_minutes"] = 60
    logger.info("Switched github_issues to scheduled (user did not ask for GitHub)")


class ConfigBuilder:
    """Uses an LLM to convert a user message into a validated YAML agent config."""

    def __init__(self, provider):
        self.llm = provider

    def build(self, user_message: str, chat_id: Optional[str] = None) -> Dict[str, Any]:
        """Convert a user message to a parsed agent config dict. Raises ValueError on failure."""
        raw = self.llm.generate(user_message, system=SYSTEM_PROMPT)
        yaml_text = _extract_yaml(raw)

        try:
            config = yaml.safe_load(yaml_text)
        except yaml.YAMLError as e:
            logger.warning("LLM produced invalid YAML: %s", e)
            raw_retry = self.llm.generate(
                f"Output was not valid YAML. Try again. User request: {user_message}",
                system=SYSTEM_PROMPT,
            )
            yaml_text = _extract_yaml(raw_retry)
            try:
                config = yaml.safe_load(yaml_text)
            except yaml.YAMLError:
                raise ValueError("Could not generate a valid agent config. Try rephrasing your request.")

        if not isinstance(config, dict):
            raise ValueError("Generated config is not a valid YAML mapping.")

        # Fix config in-code: API-key URLs, wrong source, educational prompt.
        _fix_http_request_actions(config, user_message)
        _fix_github_issues_trigger(config, user_message)
        _fix_educational_prompt(config, user_message)

        # Generic: set first http_request URL from user intent so YAML has correct URL at creation time.
        _set_url_from_user_intent(config, user_message)

        # Ensure every http_request URL is valid and returns data (generic for any agent).
        _ensure_valid_urls(config, user_message, self.llm)

        # Force "every X minutes" from user text so interval is correct.
        msg_lower = user_message.lower()
        tr = config.get("trigger") or {}
        if isinstance(tr, dict) and tr.get("type") == "scheduled":
            every_n_min = re.search(r"every\s+(\d+)\s*minutes?", msg_lower)
            if every_n_min:
                n = int(every_n_min.group(1))
                if 1 <= n <= 10080:
                    tr["interval_minutes"] = n
                    logger.info("User said 'every %s minutes'; set interval_minutes to %s", n, n)
            if not every_n_min and any(phrase in msg_lower for phrase in ("every morning", "daily morning", "each morning", "in the morning")):
                tr["time_local"] = "08:00"
                tr["interval_minutes"] = 1440
                logger.info("User asked for morning; set time_local to 08:00")
            elif not every_n_min and any(phrase in msg_lower for phrase in ("every day", "once a day", "each day", "daily")) and "time_local" not in tr:
                tr["interval_minutes"] = 1440
                logger.info("User asked for daily; set interval_minutes to 1440")

        if chat_id:
            for action in config.get("actions", []):
                if action.get("type") == "notify_telegram" and "chat_id" not in action:
                    action["chat_id"] = chat_id

        return config
