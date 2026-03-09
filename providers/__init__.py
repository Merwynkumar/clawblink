"""LLM providers for ClawBlink.

Priority order:
1. OpenAI-compatible (if OPENAI_API_KEY is set) -- works with OpenAI, DeepSeek, Groq, etc.
2. Gemini (if GEMINI_API_KEY is set) -- free tier from Google
3. Ollama (default) -- local, free, no API key needed
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class SmartProvider:
    """Uses the best available LLM. Ollama is default. Falls back between providers on error."""

    def __init__(self):
        self.primary = None
        self.fallback = None
        self.primary_name = ""
        self.fallback_name = ""

        # Try to set up providers in priority order
        if os.environ.get("OPENAI_API_KEY"):
            try:
                from providers.openai_compat_provider import OpenAICompatProvider
                self.primary = OpenAICompatProvider()
                self.primary_name = f"OpenAI-compat ({self.primary.model})"
            except Exception as e:
                logger.warning("OpenAI-compat provider failed: %s", e)

        if os.environ.get("GEMINI_API_KEY"):
            try:
                from providers.gemini_provider import GeminiProvider
                if self.primary is None:
                    self.primary = GeminiProvider()
                    self.primary_name = "Gemini"
                else:
                    self.fallback = GeminiProvider()
                    self.fallback_name = "Gemini"
            except Exception as e:
                logger.warning("Gemini provider failed: %s", e)

        # Ollama is always available as default or fallback
        try:
            from providers.ollama_provider import OllamaProvider
            ollama = OllamaProvider()
            if self.primary is None:
                self.primary = ollama
                self.primary_name = f"Ollama ({ollama.model})"
            elif self.fallback is None:
                self.fallback = ollama
                self.fallback_name = f"Ollama ({ollama.model})"
        except Exception as e:
            logger.warning("Ollama provider failed: %s", e)

        if self.primary is None:
            raise ValueError(
                "No LLM provider available.\n\n"
                "Option 1 (easiest): Install Ollama from https://ollama.ai then run:\n"
                "  ollama pull qwen2.5-coder:7b\n\n"
                "Option 2: Set GEMINI_API_KEY in .env (free: https://aistudio.google.com/apikey)\n\n"
                "Option 3: Set OPENAI_API_KEY in .env (works with OpenAI, DeepSeek, Groq, etc.)\n"
                "  Also set OPENAI_BASE_URL and OPENAI_MODEL if not using OpenAI directly."
            )

        logger.info("LLM: primary=%s, fallback=%s", self.primary_name, self.fallback_name or "none")

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        try:
            return self.primary.generate(prompt, system=system)
        except Exception as e:
            if self.fallback:
                logger.warning("%s failed (%s), falling back to %s", self.primary_name, e, self.fallback_name)
                return self.fallback.generate(prompt, system=system)
            raise


def get_provider() -> SmartProvider:
    """Return a smart provider that picks the best available LLM."""
    return SmartProvider()
