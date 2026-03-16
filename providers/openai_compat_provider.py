"""OpenAI-compatible provider. Works with OpenAI, DeepSeek, Groq, Together, OpenRouter, etc."""

import os
import requests
from typing import Optional


class OpenAICompatProvider:
    """Any provider that supports the OpenAI chat completions API format.

    Set in .env:
        OPENAI_API_KEY=your-key
        OPENAI_BASE_URL=https://api.openai.com/v1  (or any compatible endpoint)
        OPENAI_MODEL=gpt-4o-mini

    Works with: OpenAI, DeepSeek, Groq, Together AI, OpenRouter, Mistral, etc.
    """

    KNOWN_PROVIDERS = {
        "openai": "https://api.openai.com/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "groq": "https://api.groq.com/openai/v1",
        "together": "https://api.together.xyz/v1",
        "openrouter": "https://openrouter.ai/api/v1",
        "mistral": "https://api.mistral.ai/v1",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required.")

    def generate(self, prompt: str, system: Optional[str] = None, timeout: Optional[int] = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        if timeout is None:
            timeout = 120

        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model, "messages": messages, "max_tokens": 2048},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            return ""
        return (choices[0].get("message", {}).get("content") or "").strip()
