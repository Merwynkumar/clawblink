"""Gemini LLM provider. Free tier via Google AI Studio API."""

import logging
import os
import time
import requests
from typing import Optional

logger = logging.getLogger(__name__)


class GeminiProvider:
    """Google Gemini provider. Free API key from https://aistudio.google.com/apikey"""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required. Get one free at https://aistudio.google.com/apikey")

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        contents = []
        if system:
            contents.append({"role": "user", "parts": [{"text": f"[System instruction]: {system}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will follow those instructions."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {"contents": contents}
        resp = requests.post(
            url, params={"key": self.api_key}, json=payload, timeout=120,
        )
        if resp.status_code == 429:
            logger.warning("Gemini rate limited (429), waiting 10s then giving up")
            time.sleep(10)
            resp = requests.post(
                url, params={"key": self.api_key}, json=payload, timeout=120,
            )
            if resp.status_code == 429:
                raise RuntimeError("Gemini rate limited")

        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts).strip()
