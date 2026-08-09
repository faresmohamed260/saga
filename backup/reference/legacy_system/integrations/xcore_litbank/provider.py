"""Coreference-provider adapter for the xcore-litbank Modal deployment."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from saga.providers.inference_provider import CoreferenceProvider

from .pool_manager import DEFAULT_STATE_PATH, ModalXCorePoolManager


class ModalXCoreLitbankProvider(CoreferenceProvider):
    def __init__(
        self,
        *,
        pool_manager: ModalXCorePoolManager | None = None,
        app_name: str | None = None,
        tokens: list[Any] | None = None,
        state_path: str | Path | None = None,
        runtime_generation: int = 0,
        request_timeout_seconds: int = 300,
        max_failover_attempts: int = 3,
    ) -> None:
        self.pool_manager = pool_manager or ModalXCorePoolManager(
            app_name=app_name,
            tokens=tokens,
            state_path=state_path or DEFAULT_STATE_PATH,
            runtime_generation=runtime_generation,
            request_timeout_seconds=request_timeout_seconds,
            max_failover_attempts=max_failover_attempts,
        )

    def ensure_live(self) -> dict:
        return self.pool_manager.ensure_live()

    def analyze_coref(self, **kwargs) -> dict:
        return self.pool_manager.analyze(**kwargs)
