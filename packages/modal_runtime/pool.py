from __future__ import annotations

import time
from typing import Any

import requests

from packages.modal_runtime.models import (
    ModalEndpointDescriptor,
    ModalEndpointRequestMetadata,
    ModalEndpointUrls,
    ModalExecutionRequestMetadata,
    ModalExecutionResult,
    ModalLastSuccessfulRequest,
)
from packages.modal_runtime.profiling import record_modal_timing
from packages.runtime_common import ProviderUsage, create_trace, finalize_trace, reserve_usage, settle_usage


class ModalEndpointPool:
    """Shared Modal account rotation and live-endpoint orchestration."""

    def __init__(
        self,
        *,
        app_name: str,
        tokens: list[Any] | None,
        state_path: str | None,
        runtime_generation: int,
        warm_ttl_seconds: int,
        request_timeout_seconds: int,
        max_failover_attempts: int,
    ) -> None:
        self.app_name = str(app_name or "").strip()
        self._tokens = list(tokens or [])
        self.state_path = str(state_path or "").strip() or None
        self.runtime_generation = max(0, int(runtime_generation or 0))
        self.warm_ttl_seconds = max(1, int(warm_ttl_seconds or 1))
        self.request_timeout_seconds = max(1, int(request_timeout_seconds or 300))
        self.max_failover_attempts = max(1, int(max_failover_attempts or 1))
        self._sticky_token_name = ""
        self._sticky_api_url = ""
        self._sticky_ui_url = ""
        self._sticky_health_url = ""
        self._sticky_live_payload: dict[str, Any] | None = None

    def get_live_endpoints(self, *, max_endpoints: int | None = None) -> list[dict[str, Any]]:
        started_at = time.perf_counter()
        limit = max(1, int(max_endpoints or 1))
        cached = self._cached_candidate_endpoints(max_endpoints=limit)
        if cached:
            record_modal_timing(
                "modal_get_live_endpoints",
                time.perf_counter() - started_at,
                app_name=self.app_name,
                max_endpoints=limit,
                source="cached",
                count=len(cached),
            )
            return cached
        endpoints: list[dict[str, Any]] = []
        seen: set[str] = set()
        while len(endpoints) < limit:
            live = self._resolve_next_live_endpoint(exclude_token_names=seen)
            if live is None:
                break
            endpoints.append(live)
            seen.add(str(live["token_name"]))
        if not endpoints:
            raise self._rotation_error("Unable to find any live Modal endpoints.")
        record_modal_timing(
            "modal_get_live_endpoints",
            time.perf_counter() - started_at,
            app_name=self.app_name,
            max_endpoints=limit,
            source="resolved",
            count=len(endpoints),
        )
        return endpoints

    def ensure_live(self) -> dict[str, Any]:
        return self.get_live_endpoints(max_endpoints=1)[0]

    def execute(self, **kwargs) -> dict[str, Any]:
        attempted: set[str] = set()
        errors: list[str] = []
        for endpoint in self._cached_candidate_endpoints(max_endpoints=self._max_failover_attempts(), exclude_token_names=attempted):
            try:
                return self.execute_via_endpoint(endpoint, **kwargs)
            except self._retryable_error_class() as exc:
                errors.append(str(exc))
                attempted.add(str(endpoint.get("token_name") or "").strip())
                continue
        for _ in range(self._max_failover_attempts()):
            endpoint = self._resolve_next_live_endpoint(exclude_token_names=attempted)
            if endpoint is None:
                break
            try:
                return self.execute_via_endpoint(endpoint, **kwargs)
            except self._retryable_error_class() as exc:
                errors.append(str(exc))
                attempted.add(str(endpoint.get("token_name") or "").strip())
                continue
        detail = "; ".join(errors) if errors else "No live Modal endpoints were available."
        raise self._rotation_error(f"Modal pool exhausted without a successful request. {detail}")

    def execute_via_endpoint(self, endpoint: dict[str, Any] | ModalEndpointDescriptor, **kwargs) -> dict[str, Any]:
        normalized_endpoint = self._normalize_endpoint(endpoint)
        token_name = normalized_endpoint.token_name
        started_at_ms = int(time.time() * 1000)
        try:
            payload, usage = self._metered_invoke(normalized_endpoint, kwargs)
            wrapped_payload = self._build_execution_result(
                endpoint=normalized_endpoint,
                response_payload=payload,
                started_at_ms=started_at_ms,
                status="ok",
                usage=usage,
            )
            live_payload = dict(normalized_endpoint.live_payload or {})
            self._mark_success(
                token_name,
                normalized_endpoint.model_dump(),
                live_payload=live_payload,
                last_successful_request=self._build_last_successful_request_metadata(wrapped_payload),
            )
            self._remember_sticky_live(
                token_name=token_name,
                api_url=normalized_endpoint.api_url,
                ui_url=normalized_endpoint.ui_url,
                health_url=normalized_endpoint.health_url,
                live_payload=live_payload,
            )
            return wrapped_payload
        except requests.HTTPError as exc:
            if self._is_stale_endpoint_failure(exc):
                refreshed = self._refresh_endpoint_for_token(token_name)
                if refreshed is not None:
                    refreshed_endpoint = self._normalize_endpoint(refreshed)
                    refreshed_payload, usage = self._metered_invoke(refreshed_endpoint, kwargs)
                    wrapped_payload = self._build_execution_result(
                        endpoint=refreshed_endpoint,
                        response_payload=refreshed_payload,
                        started_at_ms=started_at_ms,
                        status="ok",
                        usage=usage,
                    )
                    live_payload = dict(refreshed_endpoint.live_payload or {})
                    self._mark_success(
                        token_name,
                        refreshed_endpoint.model_dump(),
                        live_payload=live_payload,
                        last_successful_request=self._build_last_successful_request_metadata(wrapped_payload),
                    )
                    self._remember_sticky_live(
                        token_name=token_name,
                        api_url=refreshed_endpoint.api_url,
                        ui_url=refreshed_endpoint.ui_url,
                        health_url=refreshed_endpoint.health_url,
                        live_payload=live_payload,
                    )
                    return wrapped_payload
            if self._is_credit_failure(exc):
                self._update_failure_status(token_name, normalized_endpoint.model_dump(), kind="credit_failure", exc=exc)
                self._advance_past_current_token(token_name)
                self._clear_sticky_live(token_name)
                raise self._retryable_error_class()(self._credit_failure_message(token_name)) from exc
            if self._is_server_failure(exc):
                self._update_failure_status(token_name, normalized_endpoint.model_dump(), kind="server_failure", exc=exc)
                self._advance_past_current_token(token_name)
                self._clear_sticky_live(token_name)
                raise self._retryable_error_class()(self._server_failure_message(token_name)) from exc
            raise
        except requests.RequestException as exc:
            self._update_failure_status(token_name, normalized_endpoint.model_dump(), kind="request_failure", exc=exc)
            self._clear_sticky_live(token_name)
            raise self._retryable_error_class()(self._request_failure_message(token_name)) from exc

    def _cached_candidate_endpoints(
        self,
        *,
        max_endpoints: int,
        exclude_token_names: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        excluded = {str(name or "").strip() for name in (exclude_token_names or set()) if str(name or "").strip()}
        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()
        token_by_name = {token.name: token for token in self._load_tokens()}

        sticky = self._sticky_endpoint()
        if sticky:
            token_name = str(sticky.get("token_name") or "").strip()
            if token_name and token_name not in excluded:
                candidates.append(sticky)
                seen.add(token_name)

        for endpoint in self._persisted_candidate_endpoints(token_by_name):
            token_name = str(endpoint.get("token_name") or "").strip()
            if not token_name or token_name in excluded or token_name in seen:
                continue
            candidates.append(endpoint)
            seen.add(token_name)
            if len(candidates) >= max_endpoints:
                break
        return candidates[:max_endpoints]

    def _resolve_next_live_endpoint(self, *, exclude_token_names: set[str] | None = None) -> dict[str, Any] | None:
        started_at = time.perf_counter()
        excluded = {str(name or "").strip() for name in (exclude_token_names or set()) if str(name or "").strip()}
        tokens = self._load_tokens()
        token_by_name = {token.name: token for token in tokens}

        sticky_live = self._try_sticky_live(token_by_name)
        if sticky_live and str(sticky_live["token_name"]) not in excluded:
            record_modal_timing(
                "modal_resolve_next_live_endpoint",
                time.perf_counter() - started_at,
                app_name=self.app_name,
                source="sticky",
                token_name=str(sticky_live.get("token_name") or "").strip(),
            )
            return sticky_live

        persisted_live = self._try_persisted_live(token_by_name, excluded)
        if persisted_live:
            record_modal_timing(
                "modal_resolve_next_live_endpoint",
                time.perf_counter() - started_at,
                app_name=self.app_name,
                source="persisted",
                token_name=str(persisted_live.get("token_name") or "").strip(),
            )
            return persisted_live

        for index, token in self._ordered_tokens(tokens):
            if token.name in excluded:
                continue
            try:
                per_token_started_at = time.perf_counter()
                urls = self._normalize_urls(self._resolve_urls_for_token(token))
                health = self._fetch_health(str(urls.health_url or "").strip())
                live = ModalEndpointDescriptor(
                    token_name=token.name,
                    api_url=urls.api_url,
                    ui_url=urls.ui_url,
                    health_url=urls.health_url,
                    live_payload=health,
                )
                if not self._sticky_token_name:
                    self._remember_sticky_live(
                        token_name=token.name,
                        api_url=live.api_url,
                        ui_url=live.ui_url,
                        health_url=live.health_url,
                        live_payload=health,
                    )
                self._save_next_index(index + 1)
                self._record_discovery_success(token.name, live.model_dump(), health)
                record_modal_timing(
                    "modal_discovery_candidate",
                    time.perf_counter() - per_token_started_at,
                    app_name=self.app_name,
                    token_name=token.name,
                    discovered=True,
                )
                record_modal_timing(
                    "modal_resolve_next_live_endpoint",
                    time.perf_counter() - started_at,
                    app_name=self.app_name,
                    source="discovered",
                    token_name=token.name,
                )
                return live.model_dump()
            except Exception as exc:  # noqa: BLE001
                self._record_discovery_failure(token.name, exc)
                record_modal_timing(
                    "modal_discovery_candidate",
                    time.perf_counter() - per_token_started_at,
                    app_name=self.app_name,
                    token_name=token.name,
                    discovered=False,
                    error_type=type(exc).__name__,
                )
                continue
        record_modal_timing(
            "modal_resolve_next_live_endpoint",
            time.perf_counter() - started_at,
            app_name=self.app_name,
            source="exhausted",
        )
        return None

    def _try_sticky_live(self, token_by_name: dict[str, Any]) -> dict[str, Any] | None:
        token_name = str(self._sticky_token_name or "").strip()
        if not token_name:
            return None
        token = token_by_name.get(token_name)
        if token is None:
            self._clear_sticky_live()
            return None
        try:
            api_url = self._sticky_api_url
            ui_url = self._sticky_ui_url
            health_url = self._sticky_health_url
            live_payload = self._sticky_live_payload
            if not api_url or not health_url:
                urls = self._normalize_urls(self._resolve_urls_for_token(token))
                api_url = str(urls.api_url or "").strip()
                ui_url = str(urls.ui_url or "").strip()
                health_url = str(urls.health_url or "").strip()
                live_payload = self._fetch_health(health_url)
            else:
                live_payload = self._fetch_health(health_url)
            self._remember_sticky_live(
                token_name=token_name,
                api_url=api_url,
                ui_url=ui_url,
                health_url=health_url,
                live_payload=live_payload if isinstance(live_payload, dict) else {},
            )
            return ModalEndpointDescriptor(
                token_name=token_name,
                api_url=api_url,
                ui_url=ui_url,
                health_url=health_url,
                live_payload=live_payload if isinstance(live_payload, dict) else {},
            ).model_dump()
        except Exception:
            self._clear_sticky_live(token_name)
            return None

    def _sticky_endpoint(self) -> dict[str, Any] | None:
        token_name = str(self._sticky_token_name or "").strip()
        api_url = str(self._sticky_api_url or "").strip()
        health_url = str(self._sticky_health_url or "").strip()
        if not token_name or not api_url or not health_url:
            return None
        return ModalEndpointDescriptor(
            token_name=token_name,
            api_url=api_url,
            ui_url=str(self._sticky_ui_url or "").strip(),
            health_url=health_url,
            live_payload=self._sticky_live_payload if isinstance(self._sticky_live_payload, dict) else {},
        ).model_dump()

    def _try_persisted_live(self, token_by_name: dict[str, Any], excluded: set[str]) -> dict[str, Any] | None:
        for endpoint in self._persisted_candidate_endpoints(token_by_name):
            token_name = str(endpoint.get("token_name") or "").strip()
            if not token_name or token_name in excluded:
                continue
            if self._should_healthcheck_persisted_endpoint():
                try:
                    live_payload = self._fetch_health(str(endpoint.get("health_url") or "").strip())
                except Exception:
                    self._clear_sticky_live(token_name)
                    continue
                endpoint = {**endpoint, "live_payload": live_payload if isinstance(live_payload, dict) else {}}
            self._remember_sticky_live(
                token_name=token_name,
                api_url=str(endpoint.get("api_url") or "").strip(),
                ui_url=str(endpoint.get("ui_url") or "").strip(),
                health_url=str(endpoint.get("health_url") or "").strip(),
                live_payload=endpoint.get("live_payload") if isinstance(endpoint.get("live_payload"), dict) else {},
            )
            return endpoint
        return None

    def _persisted_candidate_endpoints(self, token_by_name: dict[str, Any]) -> list[dict[str, Any]]:
        preferred_names: list[str] = []
        active_token_name = self._load_active_token_name()
        if active_token_name:
            preferred_names.append(active_token_name)
        stats_by_name = self._load_token_stats()
        preferred_names.extend(self._preferred_warm_token_names(stats_by_name, preferred_names))

        endpoints: list[dict[str, Any]] = []
        for token_name in preferred_names:
            normalized = str(token_name or "").strip()
            if not normalized or normalized not in token_by_name:
                continue
            stats = stats_by_name.get(normalized) or {}
            api_url = str(stats.get("api_url") or "").strip()
            health_url = str(stats.get("health_url") or "").strip()
            if not api_url or not health_url:
                continue
            endpoints.append(
                ModalEndpointDescriptor(
                    token_name=normalized,
                    api_url=api_url,
                    ui_url=str(stats.get("ui_url") or "").strip(),
                    health_url=health_url,
                    live_payload=stats.get("live_payload") if isinstance(stats.get("live_payload"), dict) else {},
                ).model_dump()
            )
        return endpoints

    def _preferred_warm_token_names(self, stats_by_name: dict[str, dict[str, Any]], preferred_names: list[str]) -> list[str]:
        return [
            token_name
            for token_name, stats in stats_by_name.items()
            if token_name not in preferred_names and self._is_persisted_endpoint_warm(stats)
        ]

    def _is_persisted_endpoint_warm(self, stats: dict[str, Any]) -> bool:
        return bool(stats.get("warm_until"))

    def _should_healthcheck_persisted_endpoint(self) -> bool:
        return True

    def _remember_sticky_live(
        self,
        *,
        token_name: str,
        api_url: str,
        ui_url: str,
        health_url: str,
        live_payload: dict[str, Any],
    ) -> None:
        self._sticky_token_name = str(token_name or "").strip()
        self._sticky_api_url = str(api_url or "").strip()
        self._sticky_ui_url = str(ui_url or "").strip()
        self._sticky_health_url = str(health_url or "").strip()
        self._sticky_live_payload = live_payload if isinstance(live_payload, dict) else {}

    def _clear_sticky_live(self, token_name: str | None = None) -> None:
        if token_name and str(token_name).strip() and str(token_name).strip() != str(self._sticky_token_name or "").strip():
            return
        self._sticky_token_name = ""
        self._sticky_api_url = ""
        self._sticky_ui_url = ""
        self._sticky_health_url = ""
        self._sticky_live_payload = None

    def _advance_past_current_token(self, token_name: str) -> None:
        for index, token in enumerate(self._load_tokens()):
            if token.name == token_name:
                self._save_next_index(index + 1)
                return

    def _max_failover_attempts(self) -> int:
        return min(self.max_failover_attempts, max(1, len(self._load_tokens())))

    def _ordered_tokens(self, tokens: list[Any]) -> list[tuple[int, Any]]:
        start_index = self._load_start_index()
        ordered = self._rotate_prefer_warm(tokens, start_index)
        active_token_name = self._load_active_token_name()
        if active_token_name:
            ordered = sorted(ordered, key=lambda item: 0 if item[1].name == active_token_name else 1)
        return ordered

    def _load_tokens(self) -> list[Any]:
        if self._tokens:
            return list(self._tokens)
        raise self._rotation_error("No Modal accounts are configured.")

    def _record_discovery_success(self, token_name: str, endpoint: dict[str, Any], live_payload: dict[str, Any]) -> None:
        self._update_status(
            token_name,
            health_ok=True,
            request_ok=self._success_request_flag(),
            last_error="",
            api_url=str(endpoint.get("api_url") or "").strip(),
            ui_url=str(endpoint.get("ui_url") or "").strip(),
            health_url=str(endpoint.get("health_url") or "").strip(),
            live_payload=live_payload,
        )

    def _record_discovery_failure(self, token_name: str, exc: Exception) -> None:
        self._update_status(
            token_name,
            health_ok=False,
            request_ok=self._failure_request_flag(),
            last_error=f"{type(exc).__name__}: {exc}",
        )

    def _update_failure_status(self, token_name: str, endpoint: dict[str, Any], *, kind: str, exc: Exception) -> None:
        self._update_status(
            token_name,
            health_ok=False,
            request_ok=False,
            last_error=f"{kind}:{exc}",
            api_url=str(endpoint.get("api_url") or "").strip() or None,
            ui_url=str(endpoint.get("ui_url") or "").strip() or None,
            health_url=str(endpoint.get("health_url") or "").strip() or None,
        )

    def _success_request_flag(self) -> bool:
        return True

    def _failure_request_flag(self) -> bool:
        return False

    def _build_last_successful_request_metadata(self, payload: dict[str, Any]) -> dict[str, Any]:
        execution = ModalExecutionResult.model_validate(payload or {})
        return ModalLastSuccessfulRequest(
            trace_id=execution.metadata.trace_id,
            run_id=execution.metadata.run_id,
            parent_trace_id=execution.metadata.parent_trace_id,
            component=execution.metadata.component,
            operation=execution.metadata.operation,
            provider=execution.metadata.provider,
            started_at_ms=execution.metadata.started_at_ms,
            completed_at_ms=execution.metadata.completed_at_ms,
            latency_ms=execution.metadata.latency_ms,
            status=execution.metadata.status,
            error_code=execution.metadata.error_code,
            observed_at=int(execution.metadata.completed_at_ms or time.time() * 1000),
            response_keys=list(execution.metadata.response_keys or []),
            token_name=execution.metadata.token_name,
            app_name=execution.metadata.app_name,
            api_url=execution.metadata.api_url,
            ui_url=execution.metadata.ui_url,
            health_url=execution.metadata.health_url,
            upstream_trace_id=execution.metadata.upstream_trace_id,
        ).model_dump(exclude_none=True)

    def _build_execution_result(
        self,
        *,
        endpoint: ModalEndpointDescriptor,
        response_payload: dict[str, Any],
        started_at_ms: int,
        status: str,
        usage: ProviderUsage | None = None,
    ) -> dict[str, Any]:
        completed_at_ms = int(time.time() * 1000)
        response = dict(response_payload or {})
        upstream_trace_id = str(response.get("trace_id") or "").strip()
        trace = finalize_trace(
            create_trace(
                component="modal_runtime",
                operation=str(response.get("operation") or "execute_endpoint"),
                provider="modal",
                metadata={
                    "token_name": endpoint.token_name,
                    "app_name": self.app_name,
                    "api_url": endpoint.api_url,
                    "ui_url": endpoint.ui_url,
                    "health_url": endpoint.health_url,
                    "upstream_trace_id": upstream_trace_id,
                    "response_keys": sorted(response.keys()),
                    "usage": (usage or ProviderUsage(request_count=0)).model_dump(),
                },
            ),
            status=str(status or "ok"),
        )
        trace.started_at_ms = started_at_ms
        trace.completed_at_ms = completed_at_ms
        trace.latency_ms = max(0, completed_at_ms - started_at_ms)
        return ModalExecutionResult(
            token_name=endpoint.token_name,
            app_name=self.app_name,
            api_url=endpoint.api_url,
            ui_url=endpoint.ui_url,
            health_url=endpoint.health_url,
            live_payload=dict(endpoint.live_payload or {}),
            response=response,
            metadata=ModalExecutionRequestMetadata(
                trace_id=trace.trace_id,
                run_id=trace.run_id,
                parent_trace_id=trace.parent_trace_id,
                component=trace.component,
                operation=trace.operation,
                provider=trace.provider,
                started_at_ms=trace.started_at_ms,
                completed_at_ms=trace.completed_at_ms,
                latency_ms=trace.latency_ms,
                status=trace.status,
                error_code=str((trace.error.code if trace.error else "") or ""),
                token_name=endpoint.token_name,
                app_name=self.app_name,
                api_url=endpoint.api_url,
                ui_url=endpoint.ui_url,
                health_url=endpoint.health_url,
                response_keys=sorted(response.keys()),
                upstream_trace_id=upstream_trace_id,
                usage=(usage or ProviderUsage(request_count=0)).model_dump(),
            ),
        ).model_dump()

    def _metered_invoke(self, endpoint: ModalEndpointDescriptor, kwargs: dict[str, Any]) -> tuple[dict[str, Any], ProviderUsage]:
        projected = ProviderUsage(
            request_count=1,
            image_count=1 if "comfy" in self.app_name.casefold() or "image" in self.app_name.casefold() else 0,
            source="declared",
        )
        reservation = reserve_usage(
            projected=projected, component="modal_runtime", provider="modal", account_alias=endpoint.token_name,
            model=self.app_name, operation=str(kwargs.get("operation") or "execute_endpoint"),
        )
        try:
            payload = self._invoke_endpoint(endpoint.model_dump(), **kwargs)
        except Exception as exc:
            actual = ProviderUsage(request_count=1, source="measured")
            settle_usage(reservation, actual, evidence={"status": "error", "exception_type": type(exc).__name__})
            raise
        usage = _modal_usage(self.app_name, payload)
        settle_usage(reservation, usage, evidence={
            "status": "ok", "upstream_trace_id": str(payload.get("trace_id") or ""),
            "usage_source": usage.source,
        })
        return payload, usage

    @staticmethod
    def _normalize_urls(urls: dict[str, str] | ModalEndpointUrls) -> ModalEndpointUrls:
        if isinstance(urls, ModalEndpointUrls):
            return urls
        return ModalEndpointUrls.model_validate(urls)

    @staticmethod
    def _normalize_endpoint(endpoint: dict[str, Any] | ModalEndpointDescriptor) -> ModalEndpointDescriptor:
        if isinstance(endpoint, ModalEndpointDescriptor):
            return endpoint
        return ModalEndpointDescriptor.model_validate(endpoint)

    def _rotation_error(self, message: str) -> RuntimeError:
        return RuntimeError(message)
    def _retryable_error_class(self):
        return RuntimeError

    def _credit_failure_message(self, token_name: str) -> str:
        return f"Modal endpoint credit failure for token '{token_name}'."

    def _server_failure_message(self, token_name: str) -> str:
        return f"Modal endpoint server failure for token '{token_name}'."

    def _request_failure_message(self, token_name: str) -> str:
        return f"Modal endpoint request failure for token '{token_name}'."

    def _is_credit_failure(self, exc: requests.HTTPError) -> bool:
        return False

    def _is_server_failure(self, exc: requests.HTTPError) -> bool:
        response = exc.response
        return bool(response is not None and int(response.status_code or 0) >= 500)

    def _is_stale_endpoint_failure(self, exc: requests.HTTPError) -> bool:
        return False

    def _refresh_endpoint_for_token(self, token_name: str) -> dict[str, Any] | None:
        return None

    def _resolve_urls_for_token(self, token: Any) -> dict[str, str]:
        raise NotImplementedError

    def _fetch_health(self, health_url: str) -> dict[str, Any]:
        raise NotImplementedError

    def _invoke_endpoint(self, endpoint: dict[str, Any], **kwargs) -> dict[str, Any]:
        raise NotImplementedError

    def _mark_success(
        self,
        token_name: str,
        endpoint: dict[str, Any],
        *,
        live_payload: dict[str, Any],
        last_successful_request: dict[str, Any] | None = None,
    ) -> None:
        raise NotImplementedError

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
        raise NotImplementedError

    def _load_active_token_name(self) -> str:
        raise NotImplementedError

    def _load_token_stats(self) -> dict[str, dict[str, Any]]:
        raise NotImplementedError

    def _load_start_index(self) -> int:
        raise NotImplementedError

    def _save_next_index(self, next_index: int) -> None:
        raise NotImplementedError

    def _rotate_prefer_warm(self, tokens: list[Any], start_index: int) -> list[tuple[int, Any]]:
        raise NotImplementedError


def _modal_usage(app_name: str, payload: dict[str, Any]) -> ProviderUsage:
    response = dict(payload or {})
    technical = dict(response.get("technical_metrics") or {})
    request_metrics = dict(response.get("request_metrics") or {})
    telemetry = dict(response.get("telemetry") or technical.get("telemetry") or {})
    compute_seconds = _first_number(
        response.get("runtime_seconds"), response.get("elapsed_seconds"),
        telemetry.get("total_elapsed_seconds"), technical.get("total_elapsed_seconds"),
        request_metrics.get("total_elapsed_seconds"),
    )
    audio_seconds = _first_number(response.get("duration_seconds"), technical.get("duration_seconds"))
    normalized_app = str(app_name or "").casefold()
    return ProviderUsage(
        request_count=1,
        compute_seconds=compute_seconds,
        image_count=1 if "comfy" in normalized_app or "image" in normalized_app else 0,
        audio_seconds=audio_seconds if "tts" in normalized_app or "kokoro" in normalized_app else 0,
        source="measured",
        evidence_id=str(response.get("request_id") or response.get("trace_id") or ""),
    )


def _first_number(*values: Any) -> float:
    for value in values:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return max(0.0, float(value))
    return 0.0
