"""Ollama LLM provider. Default for local use without paid APIs."""

import os
import requests
from typing import Optional


class OllamaProvider:
    """Ollama provider. Requires Ollama running locally (e.g. ollama run llama3.2)."""

    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None):
        self.model = model or os.environ.get("OLLAMA_MODEL", "llama3.2")
        # Use 127.0.0.1 on Windows to avoid localhost resolving to IPv6 (::1) when Ollama listens on IPv4
        default = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        self.base_url = (base_url or default).rstrip("/")

    def generate(self, prompt: str, system: Optional[str] = None, timeout: Optional[int] = None) -> str:
        full = f"{system}\n\n{prompt}" if system else prompt
        if timeout is None:
            timeout = int(os.environ.get("OLLAMA_TIMEOUT", "180"))
        resp = requests.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": full, "stream": False},
            timeout=timeout,
        )
        resp.raise_for_status()
        return (resp.json().get("response") or "").strip()
