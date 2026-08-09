"""Image-provider adapter that exposes ComfyUI through generic contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from saga.providers.inference_provider import ImageRenderProvider

from .pool_manager import DEFAULT_STATE_PATH, ModalComfyUIPoolManager


class ModalComfyUIRenderProvider(ImageRenderProvider):
    def __init__(
        self,
        *,
        pool_manager: ModalComfyUIPoolManager | None = None,
        app_name: str | None = None,
        hf_token: str = "",
        tokens: list[Any] | None = None,
        state_path: str | Path | None = None,
        runtime_generation: int = 0,
        request_timeout_seconds: int = 600,
        max_failover_attempts: int = 3,
    ) -> None:
        self.pool_manager = pool_manager or ModalComfyUIPoolManager(
            app_name=app_name,
            hf_token=hf_token,
            tokens=tokens,
            state_path=state_path or DEFAULT_STATE_PATH,
            runtime_generation=runtime_generation,
            request_timeout_seconds=request_timeout_seconds,
            max_failover_attempts=max_failover_attempts,
        )

    def ensure_live(self) -> dict:
        return self.pool_manager.ensure_live()

    def render_image(self, **kwargs) -> dict:
        return self.pool_manager.render(**kwargs)
