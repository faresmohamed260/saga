"""Speech-provider adapter that exposes Kokoro through generic contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from saga.providers.inference_provider import SpeechSynthesisProvider

from .pool_manager import DEFAULT_STATE_PATH, ModalTTSPoolManager


class ModalKokoroTTSProvider(SpeechSynthesisProvider):
    def __init__(
        self,
        *,
        pool_manager: ModalTTSPoolManager | None = None,
        app_name: str | None = None,
        tokens: list[Any] | None = None,
        state_path: str | Path | None = None,
        runtime_generation: int = 0,
        request_timeout_seconds: int = 300,
        max_failover_attempts: int = 3,
    ) -> None:
        self.pool_manager = pool_manager or ModalTTSPoolManager(
            app_name=app_name,
            tokens=tokens,
            state_path=state_path or DEFAULT_STATE_PATH,
            runtime_generation=runtime_generation,
            request_timeout_seconds=request_timeout_seconds,
            max_failover_attempts=max_failover_attempts,
        )

    def ensure_live(self) -> dict:
        return self.pool_manager.ensure_live()

    def list_live_endpoints(self, *, max_endpoints: int | None = None) -> list[dict]:
        return self.pool_manager.get_live_endpoints(max_endpoints=max_endpoints)

    def synthesize_speech_via_endpoint(self, endpoint: dict, **kwargs) -> dict:
        return self.pool_manager.synthesize_via_endpoint(endpoint, **kwargs)

    def synthesize_speech(self, **kwargs) -> dict:
        return self.pool_manager.synthesize(**kwargs)


def build_modal_kokoro_provider(
    *,
    app_name: str | None = None,
    tokens: list[Any] | None = None,
    state_path: str | Path | None = None,
    runtime_generation: int = 0,
    request_timeout_seconds: int = 300,
    max_failover_attempts: int = 3,
) -> ModalKokoroTTSProvider:
    return ModalKokoroTTSProvider(
        app_name=app_name,
        tokens=tokens,
        state_path=state_path,
        runtime_generation=runtime_generation,
        request_timeout_seconds=request_timeout_seconds,
        max_failover_attempts=max_failover_attempts,
    )
