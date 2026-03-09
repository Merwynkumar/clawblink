"""Turn a plain-English user message into a YAML agent config using an LLM."""

import logging
import re
import yaml
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are ClawBlink, an AI that creates automation agent configs.

Given a user's request, generate a YAML config for an automated agent.

CRITICAL RULE: If the agent needs ANY data from the internet (prices, news, weather, API data, website content),
you MUST include an http_request action BEFORE the llm_analyze action. The LLM CANNOT access the internet.
The http_request fetches the data, stores it in a variable, and llm_analyze reads that variable.

CORRECT pattern (http_request FIRST, then llm_analyze):
  actions:
    - type: http_request
      method: GET
      url: "https://some-real-api.com/data"
      output: fetched_data
    - type: llm_analyze
      prompt: "Here is data from an API: {fetched_data}. Summarize it."
      output: summary
    - type: notify_telegram
      message: "{summary}"

WRONG pattern (NEVER do this -- llm_analyze cannot fetch data):
  actions:
    - type: llm_analyze
      prompt: "What is the current gold price?"

RULES:
1. Output ONLY valid YAML. No explanation, no markdown fences, no commentary.
2. Use this structure:

name: short-kebab-case-name
description: One sentence describing what the agent does

trigger:
  type: scheduled OR polling
  interval_minutes: 5
  source: github_issues OR url_check OR generic
  repo: "owner/repo"

actions:
  - type: http_request
    method: GET
    url: "https://real-api-url.com/endpoint"
    output: raw_data
  - type: llm_analyze
    prompt: "Here is real data: {raw_data}. Analyze it."
    output: analysis
  - type: notify_telegram
    message: "{analysis}"

3. Trigger types:
   - "scheduled": runs on interval (set interval_minutes)
   - "polling": checks a source for changes (github_issues needs repo, url_check needs url)

4. Action types (in this order):
   - "http_request": FIRST - fetch data from URL, store in output variable
   - "llm_analyze": SECOND - analyze the fetched data using {variable_name}
   - "notify_telegram": LAST - send result to user

5. Use {variable_name} to pass data between actions.
   For polling triggers: {data}, {title}, {body}, {url}, {repo} are available.
   For scheduled triggers: you MUST use http_request to get data.

6. Use REAL API URLs that work WITHOUT API keys. Examples of free APIs:
   - Bitcoin price: https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd
   - Gold price: https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1d&range=1d
   - Silver price: https://query1.finance.yahoo.com/v8/finance/chart/SI=F?interval=1d&range=1d
   - Any stock: https://query1.finance.yahoo.com/v8/finance/chart/AAPL?interval=1d&range=1d (replace AAPL with ticker)
   - Crypto prices: https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd,inr
   - Weather: https://wttr.in/London?format=j1 (replace London with city)
   - News (CNN): https://lite.cnn.com
   - GitHub issues: https://api.github.com/repos/owner/repo/issues
   NEVER use APIs that need API keys or "demo" keys -- they will fail.

7. ONLY output the YAML. Nothing else."""


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
                f"Your previous output was not valid YAML. Try again.\n\nUser request: {user_message}",
                system=SYSTEM_PROMPT,
            )
            yaml_text = _extract_yaml(raw_retry)
            try:
                config = yaml.safe_load(yaml_text)
            except yaml.YAMLError:
                raise ValueError("Could not generate a valid agent config. Try rephrasing your request.")

        if not isinstance(config, dict):
            raise ValueError("Generated config is not a valid YAML mapping.")

        if chat_id:
            for action in config.get("actions", []):
                if action.get("type") == "notify_telegram" and "chat_id" not in action:
                    action["chat_id"] = chat_id

        return config
