"""Small local-model client for bounded semantic micro-tasks.

This client is intentionally separate from the main LLM client because its job
is different: many small local Ollama calls with tightly scoped prompts and
deterministic JSON outputs. The default model is the empirically preferred
local worker, ``mistral:7b``.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Callable, Optional

import requests


class LocalSemanticClient:
    """JSON-first client for small local Ollama semantic tasks."""

    def __init__(
        self,
        model: str = "mistral:7b",
        ollama_url: str = "http://localhost:11434/api/generate",
        timeout: int = 45,
    ) -> None:
        self.model = model
        self.ollama_url = ollama_url
        self.timeout = timeout

    def generate_json(self, prompt: str, validator: Optional[Callable[[dict], bool]] = None) -> dict:
        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "prompt": self._strict_prompt(prompt),
                    "stream": False,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            content = (response.json() or {}).get("response", "").strip()
            result = self._safe_parse_json(content)
        except Exception as exc:  # pragma: no cover - network/runtime path
            return {"error": "local_semantic_failed", "last_error": str(exc)}

        if validator and "error" not in result and not validator(result):
            return {"error": "validation_failed", "raw_output": result}
        return result

    def _strict_prompt(self, prompt: str) -> str:
        return (
            "Return ONLY valid JSON.\n"
            "NO markdown.\n"
            "NO explanations.\n"
            "NO extra text.\n\n"
            f"{prompt}"
        )

    def _safe_parse_json(self, content: str) -> dict:
        if not content:
            return {"error": "empty_response"}
        try:
            return json.loads(content)
        except Exception:
            pass

        cleaned = content.replace("```json", "").replace("```", "").strip()
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        logging.warning("Local semantic JSON parse failed")
        return {"error": "parse_failed", "raw_output": content}
