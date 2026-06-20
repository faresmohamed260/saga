from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

from .client import ModalKokoroTTSClient
from .token_pool import (
    DEFAULT_STATE_PATH,
    DEFAULT_TOKENS_PATH,
    DEFAULT_WARM_TTL_SECONDS,
    load_active_token_name,
    load_start_index,
    load_tokens,
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


class ModalTTSRotationError(RuntimeError):
    pass


class ModalTTSPoolManager:
    def __init__(
        self,
        *,
        app_name: str | None = None,
        tokens_path: str | Path = DEFAULT_TOKENS_PATH,
        state_path: str | Path = DEFAULT_STATE_PATH,
        warm_ttl_seconds: int = DEFAULT_WARM_TTL_SECONDS,
        request_timeout_seconds: int = 300,
    ) -> None:
        self.app_name = str(app_name or os.environ.get("MODAL_KOKORO_APP_NAME") or "graduation-kokoro-tts").strip()
        self.tokens_path = Path(tokens_path)
        self.state_path = Path(state_path)
        self.warm_ttl_seconds = max(1, int(warm_ttl_seconds or DEFAULT_WARM_TTL_SECONDS))
        self.request_timeout_seconds = max(1, int(request_timeout_seconds or 300))
        self._sticky_token_name = ""
        self._sticky_api_url = ""
        self._sticky_health_url = ""
        self._sticky_live_payload: dict[str, Any] | None = None

    def get_live_endpoints(self, *, max_endpoints: int | None = None) -> list[dict[str, Any]]:
        limit = max(1, int(max_endpoints or 1))
        tokens = load_tokens(self.tokens_path)
        token_by_name = {token.name: token for token in tokens}
        endpoints: list[dict[str, Any]] = []
        seen: set[str] = set()

        sticky_live = self._try_sticky_live(token_by_name)
        if sticky_live:
            endpoints.append(sticky_live)
            seen.add(str(sticky_live["token_name"]))
            if len(endpoints) >= limit:
                return endpoints

        start_index = load_start_index(self.state_path)
        ordered_tokens = rotate_prefer_warm(tokens, start_index, state_path=self.state_path)
        active_token_name = load_active_token_name(self.state_path)
        if active_token_name:
            ordered_tokens = sorted(
                ordered_tokens,
                key=lambda item: 0 if item[1].name == active_token_name else 1,
            )

        for index, token in ordered_tokens:
            if token.name in seen:
                continue
            try:
                urls = ensure_urls(token, self.app_name)
                health = self._fetch_health(urls.health_url)
                mark_live_success(
                    token.name,
                    api_url=urls.api_url,
                    health_url=urls.health_url,
                    app_name=self.app_name,
                    live_payload=health,
                    state_path=self.state_path,
                    warm_ttl_seconds=self.warm_ttl_seconds,
                )
                live = {
                    "token_name": token.name,
                    "api_url": urls.api_url,
                    "health_url": urls.health_url,
                    "live_payload": health,
                }
                if not self._sticky_token_name:
                    self._remember_sticky_live(
                        token_name=token.name,
                        api_url=urls.api_url,
                        health_url=urls.health_url,
                        live_payload=health,
                    )
                endpoints.append(live)
                seen.add(token.name)
                save_next_index(index + 1, self.state_path)
                if len(endpoints) >= limit:
                    break
            except Exception as exc:  # noqa: BLE001
                update_token_stat(
                    token.name,
                    state_path=self.state_path,
                    health_ok=False,
                    live_ok=False,
                    last_error=f"{type(exc).__name__}: {exc}",
                    app_name=self.app_name,
                )
                continue
        if not endpoints:
            raise ModalTTSRotationError("Unable to find any live TTS Modal endpoints.")
        return endpoints

    def ensure_live(self) -> dict[str, Any]:
        return self.get_live_endpoints(max_endpoints=1)[0]

    def synthesize_via_endpoint(self, endpoint: dict[str, Any], **kwargs) -> dict[str, Any]:
        token_name = str(endpoint.get("token_name") or "").strip()
        api_url = str(endpoint.get("api_url") or "").strip()
        health_url = str(endpoint.get("health_url") or "").strip()
        live_payload = endpoint.get("live_payload") if isinstance(endpoint.get("live_payload"), dict) else {}
        try:
            client = ModalKokoroTTSClient(api_url, timeout_seconds=self.request_timeout_seconds)
            payload = client.synthesize(**kwargs)
            mark_live_success(
                token_name,
                api_url=api_url,
                health_url=health_url,
                app_name=self.app_name,
                live_payload=live_payload,
                state_path=self.state_path,
                warm_ttl_seconds=self.warm_ttl_seconds,
            )
            payload["token_name"] = token_name
            payload["api_url"] = api_url
            return payload
        except requests.HTTPError as exc:
            if self._is_credit_failure(exc):
                update_token_stat(
                    token_name,
                    state_path=self.state_path,
                    health_ok=False,
                    live_ok=False,
                    last_error=f"credit_failure:{exc}",
                    api_url=api_url,
                    health_url=health_url,
                    app_name=self.app_name,
                )
                self._advance_past_current_token(token_name)
                self._clear_sticky_live(token_name)
                return self.synthesize(**kwargs)
            raise
        except requests.RequestException as exc:
            update_token_stat(
                token_name,
                state_path=self.state_path,
                health_ok=False,
                live_ok=False,
                last_error=f"request_failure:{type(exc).__name__}: {exc}",
                api_url=api_url,
                health_url=health_url,
                app_name=self.app_name,
            )
            self._clear_sticky_live(token_name)
            return self.synthesize(**kwargs)

    def synthesize(self, **kwargs) -> dict[str, Any]:
        live = self.ensure_live()
        try:
            return self.synthesize_via_endpoint(live, **kwargs)
        except RuntimeError as exc:
            raise RuntimeError(str(exc)) from exc

    def _try_sticky_live(self, token_by_name: dict[str, Any]) -> dict[str, Any] | None:
        token_name = str(self._sticky_token_name or "").strip()
        if not token_name:
            return None
        token = token_by_name.get(token_name)
        if token is None:
            self._clear_sticky_live()
            return None
        try:
            health_url = self._sticky_health_url
            api_url = self._sticky_api_url
            live_payload = self._sticky_live_payload
            if not health_url or not api_url:
                urls = ensure_urls(token, self.app_name)
                api_url = urls.api_url
                health_url = urls.health_url
                live_payload = self._fetch_health(health_url)
            else:
                live_payload = self._fetch_health(health_url)
            self._remember_sticky_live(
                token_name=token_name,
                api_url=api_url,
                health_url=health_url,
                live_payload=live_payload if isinstance(live_payload, dict) else {},
            )
            return {
                "token_name": token_name,
                "api_url": api_url,
                "health_url": health_url,
                "live_payload": live_payload if isinstance(live_payload, dict) else {},
            }
        except Exception:
            self._clear_sticky_live(token_name)
            return None

    def _remember_sticky_live(self, *, token_name: str, api_url: str, health_url: str, live_payload: dict[str, Any]) -> None:
        self._sticky_token_name = str(token_name or "").strip()
        self._sticky_api_url = str(api_url or "").strip()
        self._sticky_health_url = str(health_url or "").strip()
        self._sticky_live_payload = live_payload if isinstance(live_payload, dict) else {}

    def _clear_sticky_live(self, token_name: str | None = None) -> None:
        if token_name and str(token_name).strip() and str(token_name).strip() != str(self._sticky_token_name or "").strip():
            return
        self._sticky_token_name = ""
        self._sticky_api_url = ""
        self._sticky_health_url = ""
        self._sticky_live_payload = None

    def _fetch_health(self, health_url: str) -> dict[str, Any]:
        response = requests.get(health_url, timeout=self.request_timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not payload.get("ready"):
            raise RuntimeError(f"TTS app did not confirm readiness: {payload!r}")
        return payload

    def _advance_past_current_token(self, token_name: str) -> None:
        tokens = load_tokens(self.tokens_path)
        for index, token in enumerate(tokens):
            if token.name == token_name:
                save_next_index(index + 1, self.state_path)
                return

    def _is_credit_failure(self, exc: requests.HTTPError) -> bool:
        response = exc.response
        body = ""
        if response is not None:
            body = f"{response.text}\n{response.reason}".lower()
            if response.status_code in {402, 429}:
                return True
        return any(pattern in body for pattern in CREDIT_PATTERNS)
