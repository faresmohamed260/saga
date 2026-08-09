"""Runtime token rotation and failover for the xcore-litbank provider."""

from __future__ import annotations

import os
import time
from typing import Any

import requests

from packages.modal_runtime import ModalEndpointPool

from .client import ModalXCoreLitbankClient
from .token_pool import (
    DEFAULT_STATE_PATH,
    DEFAULT_WARM_TTL_SECONDS,
    load_active_token_name,
    load_token_stats,
    load_start_index,
    mark_live_success,
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


class ModalXCoreRotationError(RuntimeError):
    pass


class _ModalXCoreRetryableError(RuntimeError):
    pass


class ModalXCorePoolManager(ModalEndpointPool):
    def __init__(
        self,
        *,
        app_name: str | None = None,
        tokens: list[Any] | None = None,
        state_path: str | None = DEFAULT_STATE_PATH,
        runtime_generation: int = 0,
        warm_ttl_seconds: int = DEFAULT_WARM_TTL_SECONDS,
        request_timeout_seconds: int = 300,
        max_failover_attempts: int = 3,
    ) -> None:
        super().__init__(
            app_name=str(app_name or os.environ.get("MODAL_XCORE_LITBANK_APP_NAME") or "saga-coref-runtime").strip(),
            tokens=tokens,
            state_path=state_path,
            runtime_generation=runtime_generation,
            warm_ttl_seconds=warm_ttl_seconds,
            request_timeout_seconds=request_timeout_seconds,
            max_failover_attempts=max_failover_attempts,
        )

    def analyze(self, **kwargs) -> dict[str, Any]:
        return self.execute(**kwargs)

    def analyze_via_endpoint(self, endpoint: dict[str, Any], **kwargs) -> dict[str, Any]:
        return self.execute_via_endpoint(endpoint, **kwargs)

    def _rotation_error(self, message: str) -> RuntimeError:
        return ModalXCoreRotationError(message)

    def _retryable_error_class(self):
        return _ModalXCoreRetryableError

    def _credit_failure_message(self, token_name: str) -> str:
        return f"xcore endpoint credit failure for token '{token_name}'."

    def _server_failure_message(self, token_name: str) -> str:
        return f"xcore endpoint server failure for token '{token_name}'."

    def _request_failure_message(self, token_name: str) -> str:
        return f"xcore endpoint request failure for token '{token_name}'."

    def _resolve_urls_for_token(self, token: Any) -> dict[str, str]:
        urls = ensure_urls(token, self.app_name)
        return {"api_url": urls.api_url, "health_url": urls.health_url}

    def _fetch_health(self, health_url: str) -> dict[str, Any]:
        response = requests.get(health_url, timeout=self.request_timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not payload.get("ready"):
            raise RuntimeError(f"xcore app did not confirm readiness: {payload!r}")
        return payload

    def _invoke_endpoint(self, endpoint: dict[str, Any], **kwargs) -> dict[str, Any]:
        client = ModalXCoreLitbankClient(str(endpoint.get("api_url") or "").strip(), timeout_seconds=self.request_timeout_seconds)
        payload = client.analyze(**kwargs)
        payload["token_name"] = str(endpoint.get("token_name") or "").strip()
        payload["api_url"] = str(endpoint.get("api_url") or "").strip()
        return payload

    def _mark_success(
        self,
        token_name: str,
        endpoint: dict[str, Any],
        *,
        live_payload: dict[str, Any],
        last_successful_request: dict[str, Any] | None = None,
    ) -> None:
        mark_live_success(
            token_name,
            api_url=str(endpoint.get("api_url") or "").strip(),
            health_url=str(endpoint.get("health_url") or "").strip(),
            app_name=self.app_name,
            live_payload=live_payload,
            state_path=self.state_path,
            warm_ttl_seconds=self.warm_ttl_seconds,
            runtime_generation=self.runtime_generation,
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
            live_ok=request_ok,
            warm_until=None,
            last_error=last_error,
            api_url=api_url,
            health_url=health_url,
            app_name=self.app_name,
            live_payload=live_payload,
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

    def _is_persisted_endpoint_warm(self, stats: dict[str, Any]) -> bool:
        return int(stats.get("warm_until", 0) or 0) > int(time.time())

    def _is_credit_failure(self, exc: requests.HTTPError) -> bool:
        response = exc.response
        body = ""
        if response is not None:
            body = f"{response.text}\n{response.reason}".lower()
            if response.status_code in {402, 429}:
                return True
        return any(pattern in body for pattern in CREDIT_PATTERNS)
