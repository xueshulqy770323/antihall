# -*- coding: utf-8 -*-
"""LLM client abstraction — works with any OpenAI-compatible API.

Supports:
- OpenAI (GPT-4o, GPT-4o-mini, ...)
- DeepSeek, Qwen, Moonshot, Zhipu, etc. (any OpenAI-compatible endpoint)
- Custom local servers (vLLM, Ollama with OpenAI compatibility layer)

Usage:
    client = LLMClient(
        api_key="sk-xxx",
        base_url="https://api.deepseek.com/v1",  # optional
        model="deepseek-chat",
    )
    response = client.chat("Extract financial claims from: ...")
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """Configuration for the LLM client."""
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    temperature: float = 0.0       # deterministic for extraction
    max_tokens: int = 4096
    timeout: int = 60


class LLMClient:
    """Thin wrapper around any OpenAI-compatible Chat Completions API.

    If the `openai` package is not installed, falls back to raw HTTP
    via `urllib` so the library works even without the SDK.
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self._client = None
        self._init_sdk()

    def _init_sdk(self):
        """Try to use the openai SDK; fall back to urllib."""
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
            logger.debug("openai SDK loaded")
        except ImportError:
            logger.debug("openai SDK not installed, will use urllib fallback")
            self._client = None

    def chat(self, prompt: str, system: str = "") -> str:
        """Send a single-turn chat and return the text response.

        Args:
            prompt: User message.
            system: Optional system message.

        Returns:
            The assistant's text response.
        """
        if self._client:
            return self._chat_sdk(prompt, system)
        return self._chat_urllib(prompt, system)

    def chat_json(self, prompt: str, system: str = "") -> list[dict] | dict:
        """Like chat(), but parses the response as JSON.

        Returns:
            Parsed JSON (list or dict). On parse failure returns {"error": raw_text}.
        """
        raw = self.chat(prompt, system)

        # Try to extract JSON from markdown code blocks or raw text
        text = raw.strip()

        # Strip markdown ```json ... ``` wrapper
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            text = text[start:end].strip()

        # Remove leading/trailing brackets if wrapped
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try adding brackets if it looks like a list
            text_stripped = text.strip()
            if text_stripped.startswith("[") or text_stripped.startswith("{"):
                try:
                    return json.loads(text_stripped)
                except json.JSONDecodeError:
                    pass
            logger.warning(f"Failed to parse JSON from LLM response: {raw[:200]}")
            return {"error": "json_parse_failed", "raw": raw}

    def _chat_sdk(self, prompt: str, system: str) -> str:
        """Chat via openai SDK."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        return response.choices[0].message.content or ""

    def _chat_urllib(self, prompt: str, system: str) -> str:
        """Fallback chat via raw HTTP (no openai SDK needed)."""
        import urllib.request
        import urllib.error

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = json.dumps({
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }).encode("utf-8")

        url = self.config.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return body["choices"][0]["message"]["content"] or ""
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            logger.error(f"LLM API error {e.code}: {error_body[:500]}")
            return f"[API_ERROR {e.code}]"

    @property
    def is_available(self) -> bool:
        """Check if the client has an API key configured."""
        return bool(self.config.api_key)
