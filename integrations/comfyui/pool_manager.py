"""Runtime token rotation and failover for the ComfyUI image provider."""

from __future__ import annotations

import os
import time
from typing import Any

import requests

from packages.modal_runtime import ModalEndpointPool, load_modal_provider_secret_config
from packages.modal_runtime.profiling import record_modal_timing

from .client import ModalComfyUIClient
from .token_pool import (
    DEFAULT_STATE_PATH,
    DEFAULT_WARM_TTL_SECONDS,
    load_active_token_name,
    load_token_stats,
    load_start_index,
    mark_render_success,
    rotate_prefer_warm,
    save_next_index,
    update_token_stat,
)
from .workspace_client import ensure_urls


CREDIT_PATTERNS = (
    "credit",
    "credits",
    "quota",
    "budget",
    "billing",
    "payment",
    "insufficient",
    "limit exceeded",
    "exceeded your spending",
    "workspace budget",
)


class ModalComfyUIRotationError(RuntimeError):
    pass


class _ModalComfyUIRetryableError(RuntimeError):
    pass


class ModalComfyUIPoolManager(ModalEndpointPool):
    def __init__(
        self,
        *,
        app_name: str | None = None,
        hf_token: str = "",
        tokens: list[Any] | None = None,
        state_path: str | None = DEFAULT_STATE_PATH,
        runtime_generation: int = 0,
        warm_ttl_seconds: int = DEFAULT_WARM_TTL_SECONDS,
        request_timeout_seconds: int = 600,
        max_failover_attempts: int = 3,
    ) -> None:
        started_at = time.perf_counter()
        provider_config = None
        resolved_hf_token = str(hf_token or "").strip()
        resolved_app_name = str(app_name or "").strip()
        if not resolved_hf_token or not resolved_app_name:
            provider_config = load_modal_provider_secret_config("modal_comfyui")
        self.hf_token = resolved_hf_token or (provider_config.hf_token if provider_config else "")
        super().__init__(
            app_name=resolved_app_name or (provider_config.app_name if provider_config else "") or str(os.environ.get("MODAL_COMFYUI_APP_NAME") or "saga-image-runtime").strip(),
            tokens=tokens,
            state_path=state_path,
            runtime_generation=runtime_generation,
            warm_ttl_seconds=warm_ttl_seconds,
            request_timeout_seconds=request_timeout_seconds,
            max_failover_attempts=max_failover_attempts,
        )
        record_modal_timing(
            "modal_pool_manager_init",
            time.perf_counter() - started_at,
            app_name=self.app_name,
            token_count=len(tokens or []),
            loaded_provider_config=provider_config is not None,
            has_hf_token=bool(self.hf_token),
        )

    def render(self, **kwargs) -> dict[str, Any]:
        return self.execute(**kwargs)

    def render_via_endpoint(self, endpoint: dict[str, Any], **kwargs) -> dict[str, Any]:
        return self.execute_via_endpoint(endpoint, **kwargs)

    def _rotation_error(self, message: str) -> RuntimeError:
        return ModalComfyUIRotationError(message)

    def _retryable_error_class(self):
        return _ModalComfyUIRetryableError

    def _credit_failure_message(self, token_name: str) -> str:
        return f"ComfyUI endpoint credit failure for token '{token_name}'."

    def _server_failure_message(self, token_name: str) -> str:
        return f"ComfyUI endpoint server failure for token '{token_name}'."

    def _request_failure_message(self, token_name: str) -> str:
        return f"ComfyUI endpoint request failure for token '{token_name}'."

    def _resolve_urls_for_token(self, token: Any) -> dict[str, str]:
        urls = ensure_urls(token, self._app_name_for_token(token), hf_token=self.hf_token)
        return {"api_url": urls.api_url, "ui_url": urls.ui_url, "health_url": urls.health_url}

    def _fetch_health(self, health_url: str) -> dict[str, Any]:
        started_at = time.perf_counter()
        response = requests.get(health_url, timeout=self.request_timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not payload.get("ready"):
            raise RuntimeError(f"ComfyUI app did not confirm readiness: {payload!r}")
        record_modal_timing(
            "modal_health_check",
            time.perf_counter() - started_at,
            app_name=self.app_name,
            health_url=health_url,
            status_code=response.status_code,
            ready=True,
        )
        return payload

    def _invoke_endpoint(self, endpoint: dict[str, Any], **kwargs) -> dict[str, Any]:
        started_at = time.perf_counter()
        client = ModalComfyUIClient(str(endpoint.get("api_url") or "").strip(), timeout_seconds=self.request_timeout_seconds)
        payload = client.render(**kwargs)
        payload["token_name"] = str(endpoint.get("token_name") or "").strip()
        payload["api_url"] = str(endpoint.get("api_url") or "").strip()
        payload["ui_url"] = str(endpoint.get("ui_url") or "").strip()
        payload["health_url"] = str(endpoint.get("health_url") or "").strip()
        request_metrics = dict(payload.get("request_metrics") or {})
        record_modal_timing(
            "modal_render_invoke",
            time.perf_counter() - started_at,
            app_name=self.app_name,
            token_name=payload["token_name"],
            workflow_mode=str((request_metrics.get("workflow_mode") or kwargs.get("workflow_mode") or "")).strip(),
            total_elapsed_seconds=request_metrics.get("total_elapsed_seconds"),
        )
        return payload

    def _mark_success(
        self,
        token_name: str,
        endpoint: dict[str, Any],
        *,
        live_payload: dict[str, Any],
        last_successful_request: dict[str, Any] | None = None,
    ) -> None:
        mark_render_success(
            token_name,
            state_path=self.state_path,
            warm_ttl_seconds=self.warm_ttl_seconds,
            app_name=self.app_name,
            runtime_generation=self.runtime_generation,
            api_url=str(endpoint.get("api_url") or "").strip(),
            ui_url=str(endpoint.get("ui_url") or "").strip(),
            health_url=str(endpoint.get("health_url") or "").strip(),
            live_payload=live_payload,
            last_successful_request=last_successful_request,
        )

    def _record_discovery_success(self, token_name: str, endpoint: dict[str, Any], live_payload: dict[str, Any]) -> None:
        self._mark_success(token_name, endpoint, live_payload=live_payload)
        super()._record_discovery_success(token_name, endpoint, live_payload)

    def _update_status(
        self,
        token_name: str,
        *,
        health_ok: bool | None = None,
        request_ok: bool | None = None,
        last_error: str | None = None,
        api_url: str | None = None,
        ui_url: str | None = None,
        health_url: str | None = None,
        live_payload: dict[str, Any] | None = None,
    ) -> None:
        update_token_stat(
            token_name,
            state_path=self.state_path,
            health_ok=health_ok,
            render_ok=request_ok,
            warm_until=None,
            last_error=last_error,
            api_url=api_url,
            ui_url=ui_url,
            health_url=health_url,
            live_payload=live_payload,
            app_name=self.app_name,
            runtime_generation=self.runtime_generation,
        )

    def _load_active_token_name(self) -> str:
        return load_active_token_name(self.state_path, expected_app_name=self.app_name, expected_generation=self.runtime_generation)

    def _load_token_stats(self) -> dict[str, dict[str, Any]]:
        return load_token_stats(self.state_path, expected_app_name=self.app_name, expected_generation=self.runtime_generation)

    def _load_start_index(self) -> int:
        return load_start_index(self.state_path, expected_app_name=self.app_name, expected_generation=self.runtime_generation)

    def _save_next_index(self, next_index: int) -> None:
        save_next_index(next_index, self.state_path, app_name=self.app_name, runtime_generation=self.runtime_generation)

    def _rotate_prefer_warm(self, tokens: list[Any], start_index: int) -> list[tuple[int, Any]]:
        return rotate_prefer_warm(tokens, start_index, state_path=self.state_path, expected_app_name=self.app_name, expected_generation=self.runtime_generation)

    def _is_credit_failure(self, exc: requests.HTTPError) -> bool:
        response = exc.response
        body = ""
        if response is not None:
            body = f"{response.text}\n{response.reason}".lower()
            if response.status_code in {402, 429}:
                return True
        return any(pattern in body for pattern in CREDIT_PATTERNS)

    def _is_stale_endpoint_failure(self, exc: requests.HTTPError) -> bool:
        response = exc.response
        return bool(response is not None and int(response.status_code or 0) in {404, 410})

    def _refresh_endpoint_for_token(self, token_name: str) -> dict[str, Any] | None:
        normalized = str(token_name or "").strip()
        token = next((item for item in self._load_tokens() if item.name == normalized), None)
        if token is None:
            return None
        urls = self._resolve_urls_for_token(token)
        live_payload = self._fetch_health(str(urls.get("health_url") or "").strip())
        endpoint = {
            "token_name": normalized,
            "api_url": str(urls.get("api_url") or "").strip(),
            "ui_url": str(urls.get("ui_url") or "").strip(),
            "health_url": str(urls.get("health_url") or "").strip(),
            "live_payload": live_payload if isinstance(live_payload, dict) else {},
        }
        self._remember_sticky_live(
            token_name=normalized,
            api_url=endpoint["api_url"],
            ui_url=endpoint["ui_url"],
            health_url=endpoint["health_url"],
            live_payload=endpoint["live_payload"],
        )
        return endpoint

    def _should_healthcheck_persisted_endpoint(self) -> bool:
        return False

    def _app_name_for_token(self, token: Any) -> str:
        override = str(getattr(token, "app_name_override", "") or "").strip()
        return override or self.app_name
