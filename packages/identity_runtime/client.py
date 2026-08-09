"""Reusable client for the active Modal-backed identity runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packages.modal_runtime import load_modal_provider_secret_config

from integrations.xcore_litbank.pool_manager import ModalXCorePoolManager
from integrations.xcore_litbank.token_pool import load_tokens

from .contracts import IdentityRuntimeResult


@dataclass(frozen=True)
class IdentityRuntimeProfile:
    name: str
    provider_name: str = "modal_xcore_litbank"
    request_timeout_seconds: int = 300
    allow_cross_chapter: bool = True
    chunk_target_words: int = 900
    chunk_min_words: int = 650
    chunk_max_words: int = 1200
    chunk_min_scene_words: int = 350


@dataclass(frozen=True)
class IdentityRuntimeConfig:
    profile: IdentityRuntimeProfile


class IdentityRuntimeClient:
    def __init__(self, *, profile: IdentityRuntimeProfile, config: IdentityRuntimeConfig) -> None:
        self.profile = profile
        self.config = config
        provider_config = load_modal_provider_secret_config(self.provider_name())
        tokens = load_tokens()
        self._pool = ModalXCorePoolManager(
            app_name=str(provider_config.app_name or "").strip() or "saga-coref-runtime",
            tokens=tokens,
            request_timeout_seconds=max(30, int(profile.request_timeout_seconds)),
        )

    def provider_name(self) -> str:
        return str(self.profile.provider_name or "modal_xcore_litbank").strip()

    def analyze_chapters(
        self,
        *,
        chapters: list[dict[str, Any]],
        use_chunking: bool | None = None,
    ) -> IdentityRuntimeResult:
        resolved_chapters = list(chapters or [])
        resolved_use_chunking = self._resolve_use_chunking(
            chapters=resolved_chapters,
            use_chunking=use_chunking,
        )
        payload = self._pool.analyze(
            chapters=resolved_chapters,
            use_chunking=resolved_use_chunking,
            allow_cross_chapter=bool(self.profile.allow_cross_chapter),
            chunk_target_words=int(self.profile.chunk_target_words),
            chunk_min_words=int(self.profile.chunk_min_words),
            chunk_max_words=int(self.profile.chunk_max_words),
            chunk_min_scene_words=int(self.profile.chunk_min_scene_words),
        )
        response = dict(payload.get("response") or {})
        return IdentityRuntimeResult.model_validate(
            {
                "provider_name": self.provider_name(),
                "app_name": str(response.get("app_name") or payload.get("app_name") or "").strip(),
                "model_name": str(response.get("model_name") or "").strip(),
                "runtime_seconds": float(response.get("runtime_seconds") or 0.0),
                "chunk_count": int(response.get("chunk_count") or 0),
                "input_stats": dict(response.get("input_stats") or {}),
                "clusters": list(response.get("clusters") or []),
                "raw_payload": dict(payload or {}),
            }
        )

    def _resolve_use_chunking(
        self,
        *,
        chapters: list[dict[str, Any]],
        use_chunking: bool | None,
    ) -> bool:
        if use_chunking is not None:
            return bool(use_chunking)
        if len(chapters) > 1:
            return True
        if not chapters:
            return False
        content = str((chapters[0] or {}).get("content") or "").strip()
        return len(content.split()) > max(1, int(self.profile.chunk_min_words or 650))
