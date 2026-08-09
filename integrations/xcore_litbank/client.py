"""Thin HTTP client for the deployed xcore-litbank Modal service."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests


class ModalXCoreLitbankClient:
    def __init__(self, api_url: str, *, timeout_seconds: int = 300) -> None:
        self.api_url = str(api_url or "").strip()
        self.timeout_seconds = max(1, int(timeout_seconds))
        if not self.api_url:
            raise ValueError("api_url is required")

    def analyze(
        self,
        *,
        text: str = "",
        chapters: list[dict[str, Any]] | None = None,
        use_chunking: bool | None = None,
        allow_cross_chapter: bool = True,
        chunk_target_words: int = 900,
        chunk_min_words: int = 650,
        chunk_max_words: int = 1200,
        chunk_min_scene_words: int = 350,
    ) -> dict[str, Any]:
        resolved_text = str(text or "")
        resolved_chapters = list(chapters or [])
        resolved_use_chunking = self._resolve_use_chunking(
            text=resolved_text,
            chapters=resolved_chapters,
            use_chunking=use_chunking,
            chunk_min_words=chunk_min_words,
        )
        payload = {
            "text": resolved_text,
            "chapters": resolved_chapters,
            "use_chunking": resolved_use_chunking,
            "allow_cross_chapter": bool(allow_cross_chapter),
            "chunk_target_words": int(chunk_target_words or 0),
            "chunk_min_words": int(chunk_min_words or 0),
            "chunk_max_words": int(chunk_max_words or 0),
            "chunk_min_scene_words": int(chunk_min_scene_words or 0),
        }
        response = requests.post(self.api_url, json=payload, timeout=self.timeout_seconds)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise RuntimeError(f"Unexpected Modal xcore response: {type(body).__name__}")
        return body

    def _resolve_use_chunking(
        self,
        *,
        text: str,
        chapters: list[dict[str, Any]],
        use_chunking: bool | None,
        chunk_min_words: int,
    ) -> bool:
        if use_chunking is not None:
            return bool(use_chunking)
        if chapters:
            return True
        word_count = len(str(text or "").split())
        return word_count > max(1, int(chunk_min_words or 650))
