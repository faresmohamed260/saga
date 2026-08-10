from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import requests

from integrations.comfyui.pool_manager import ModalComfyUIPoolManager
from integrations.comfyui.token_pool import load_tokens
from packages.modal_runtime import ModalEndpointPool
from packages.modal_runtime.pool import _modal_usage
from packages.modal_runtime.profiling import ModalTimingCollector, collect_modal_timings, record_modal_timing
from packages.modal_runtime.provider_config import (
    clear_modal_provider_config_cache,
    load_modal_provider_secret_config,
    save_modal_provider_secret_config,
)
from packages.modal_runtime.models import ModalEndpointDescriptor, ModalEndpointUrls, ModalExecutionResult, ModalRuntimeState
from packages.modal_runtime.state import clear_runtime_state_cache, load_runtime_state, save_runtime_state
from packages.runtime_common import trace_scope


@dataclass(frozen=True)
class _Token:
    name: str


class _StubModalPool(ModalEndpointPool):
    def __init__(self, *, tokens, state, failure_plan=None):
        self.state = state
        self.failure_plan = dict(failure_plan or {})
        self.status_updates = []
        self.success_updates = []
        super().__init__(
            app_name="stub-modal-runtime",
            tokens=tokens,
            state_path=None,
            runtime_generation=3,
            warm_ttl_seconds=120,
            request_timeout_seconds=5,
            max_failover_attempts=3,
        )

    def _resolve_urls_for_token(self, token):
        return {
            "api_url": f"https://{token.name}.example/api",
            "ui_url": f"https://{token.name}.example/ui",
            "health_url": f"https://{token.name}.example/health",
        }

    def _fetch_health(self, health_url: str) -> dict[str, str]:
        return {"ready": True, "health_url": health_url}

    def _invoke_endpoint(self, endpoint: dict[str, str], **kwargs) -> dict[str, str]:
        token_name = str(endpoint.get("token_name") or "")
        planned = self.failure_plan.get(token_name)
        if planned:
            status_code = int(planned.pop(0))
            response = requests.Response()
            response.status_code = status_code
            response._content = b"planned failure"
            error = requests.HTTPError(f"HTTP {status_code}")
            error.response = response
            raise error
        return {
            "ok": True,
            "token_name": token_name,
            "request_id": kwargs.get("request_id", ""),
            "trace_id": f"upstream-{token_name}",
        }

    def _mark_success(self, token_name: str, endpoint: dict, *, live_payload: dict, last_successful_request: dict | None = None) -> None:
        self.success_updates.append((token_name, dict(endpoint), dict(last_successful_request or {})))
        stats = self.state.setdefault("token_stats", {}).setdefault(token_name, {})
        stats.update(
            {
                "api_url": endpoint.get("api_url", ""),
                "health_url": endpoint.get("health_url", ""),
                "ui_url": endpoint.get("ui_url", ""),
                "warm_until": 9999999999,
                "last_request_ok": True,
                "last_successful_request": dict(last_successful_request or {}),
            }
        )
        self.state["active_token_name"] = token_name

    def _update_status(self, token_name: str, **kwargs) -> None:
        self.status_updates.append((token_name, dict(kwargs)))
        stats = self.state.setdefault("token_stats", {}).setdefault(token_name, {})
        stats.update({key: value for key, value in kwargs.items() if value is not None})

    def _load_active_token_name(self) -> str:
        return str(self.state.get("active_token_name") or "")

    def _load_token_stats(self) -> dict[str, dict]:
        return dict(self.state.get("token_stats") or {})

    def _load_start_index(self) -> int:
        return int(self.state.get("next_index") or 0)

    def _save_next_index(self, next_index: int) -> None:
        self.state["next_index"] = int(next_index)

    def _rotate_prefer_warm(self, tokens, start_index: int):
        token_list = list(tokens)
        if not token_list:
            return []
        offset = start_index % len(token_list)
        return [
            ((offset + step) % len(token_list), token_list[(offset + step) % len(token_list)])
            for step in range(len(token_list))
        ]


class _StubModalPoolWithoutUpstreamTrace(_StubModalPool):
    def _invoke_endpoint(self, endpoint: dict[str, str], **kwargs) -> dict[str, str]:
        token_name = str(endpoint.get("token_name") or "")
        return {"ok": True, "token_name": token_name, "request_id": kwargs.get("request_id", "")}


def test_modal_image_usage_reads_http_request_elapsed_time():
    usage = _modal_usage(
        "saga-image-runtime",
        {"request_metrics": {"total_elapsed_seconds": 12.75}},
    )

    assert usage.compute_seconds == 12.75
    assert usage.image_count == 1


def test_modal_runtime_state_normalizes_legacy_request_keys(tmp_path: Path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'modal-state.sqlite3'}"
    monkeypatch.setenv("SAGA_MODAL_STATE_DB_URL", database_url)
    monkeypatch.setenv("SAGA_MODAL_STATE_DB_MODE", "test_harness")
    clear_runtime_state_cache()

    save_runtime_state(
        {
            "app_name": "runtime-a",
            "runtime_generation": 1,
            "next_index": 2,
            "token_stats": {
                "member-01": {
                    "last_render_ok": True,
                    "last_render_checked_at": 111,
                    "last_successful_request": {"operation": "render", "response_keys": ["image_url"]},
                }
            },
        },
        provider_name="modal_comfyui",
    )

    payload = load_runtime_state(expected_app_name="runtime-a", expected_generation=1, provider_name="modal_comfyui")
    state = ModalRuntimeState.from_payload(payload)

    assert state.next_index == 2
    assert state.token_stats["member-01"].last_request_ok is True
    assert state.token_stats["member-01"].last_successful_request is not None
    assert state.token_stats["member-01"].last_successful_request.operation == "render"

    clear_runtime_state_cache()


def test_modal_endpoint_pool_fails_over_and_updates_operational_state() -> None:
    pool = _StubModalPool(
        tokens=[_Token(name="member-01"), _Token(name="member-02")],
        state={"next_index": 0, "token_stats": {}},
        failure_plan={"member-01": [500]},
    )

    with trace_scope(run_id="modal-run-1"):
        result = pool.execute(request_id="req-123")

    execution = ModalExecutionResult.model_validate(result)

    assert execution.response["ok"] is True
    assert execution.token_name == "member-02"
    assert pool.state["active_token_name"] == "member-02"
    assert pool.state["next_index"] == 2
    assert pool.state["token_stats"]["member-01"]["last_error"].startswith("server_failure:")
    assert pool.state["token_stats"]["member-02"]["last_request_ok"] is True
    assert pool.success_updates[0][2]["response_keys"] == ["ok", "request_id", "token_name", "trace_id"]
    assert pool.success_updates[0][2]["trace_id"]
    assert pool.success_updates[0][2]["run_id"] == "modal-run-1"
    assert pool.success_updates[0][2]["upstream_trace_id"] == "upstream-member-02"
    assert execution.metadata.component == "modal_runtime"
    assert execution.metadata.provider == "modal"
    assert execution.metadata.usage["request_count"] == 1
    assert execution.metadata.trace_id
    assert execution.metadata.run_id == "modal-run-1"
    assert execution.metadata.upstream_trace_id == "upstream-member-02"


def test_modal_endpoint_models_normalize_payloads() -> None:
    urls = ModalEndpointUrls.model_validate({"api_url": "https://a/api", "health_url": "https://a/health"})
    endpoint = ModalEndpointDescriptor.model_validate(
        {
            "token_name": "member-01",
            "api_url": urls.api_url,
            "health_url": urls.health_url,
            "live_payload": {"ready": True},
        }
    )

    assert urls.api_url == "https://a/api"
    assert endpoint.token_name == "member-01"
    assert endpoint.live_payload["ready"] is True


def test_modal_endpoint_pool_generates_runtime_trace_without_upstream_trace_id() -> None:
    pool = _StubModalPoolWithoutUpstreamTrace(
        tokens=[_Token(name="member-01")],
        state={"next_index": 0, "token_stats": {}},
    )

    with trace_scope(run_id="modal-run-2"):
        result = pool.execute(request_id="req-456")

    execution = ModalExecutionResult.model_validate(result)

    assert execution.metadata.trace_id
    assert execution.metadata.run_id == "modal-run-2"
    assert execution.metadata.upstream_trace_id == ""
    assert execution.response["request_id"] == "req-456"
    assert pool.success_updates[0][2]["trace_id"] == execution.metadata.trace_id
    assert pool.success_updates[0][2]["upstream_trace_id"] == ""


def test_modal_provider_secret_config_partial_update_preserves_existing_accounts(tmp_path: Path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'modal-provider-config.sqlite3'}"
    monkeypatch.setenv("SAGA_RUNTIME_DB_URL", database_url)
    monkeypatch.setenv("SAGA_RUNTIME_DB_MODE", "test_harness")
    monkeypatch.setenv("SAGA_MODAL_STATE_DB_URL", database_url)
    monkeypatch.setenv("SAGA_MODAL_STATE_DB_MODE", "test_harness")
    monkeypatch.setenv("SAGA_RUNTIME_LOCAL_STORAGE_ROOT", str(tmp_path / "runtime-storage"))
    clear_modal_provider_config_cache()

    save_modal_provider_secret_config(
        "modal_comfyui",
        {
            "accounts": [
                {
                    "label": "member-01",
                    "token_id": "modal-id",
                    "token_secret": "modal-secret",
                }
            ]
        },
    )
    save_modal_provider_secret_config("modal_comfyui", {"hf_token": "hf-secret"})

    config = load_modal_provider_secret_config("modal_comfyui")
    assert config.hf_token == "hf-secret"
    assert len(config.accounts) == 1
    assert config.accounts[0].label == "member-01"
    assert config.accounts[0].token_id == "modal-id"
    assert config.accounts[0].token_secret == "modal-secret"


def test_modal_comfyui_pool_manager_defaults_to_persisted_provider_config(tmp_path: Path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'modal-provider-defaults.sqlite3'}"
    monkeypatch.setenv("SAGA_RUNTIME_DB_URL", database_url)
    monkeypatch.setenv("SAGA_RUNTIME_DB_MODE", "test_harness")
    monkeypatch.setenv("SAGA_MODAL_STATE_DB_URL", database_url)
    monkeypatch.setenv("SAGA_MODAL_STATE_DB_MODE", "test_harness")
    monkeypatch.setenv("SAGA_RUNTIME_LOCAL_STORAGE_ROOT", str(tmp_path / "runtime-storage"))
    monkeypatch.setenv("MODAL_COMFYUI_APP_NAME", "env-app-name")
    clear_modal_provider_config_cache()

    save_modal_provider_secret_config(
        "modal_comfyui",
        {
            "app_name": "persisted-app-name",
            "hf_token": "hf-persisted-token",
            "accounts": [
                {
                    "label": "member-01",
                    "token_id": "modal-id",
                    "token_secret": "modal-secret",
                }
            ],
        },
    )

    manager = ModalComfyUIPoolManager(tokens=[_Token(name="member-01")], request_timeout_seconds=5)

    assert manager.app_name == "persisted-app-name"
    assert manager.hf_token == "hf-persisted-token"


def test_modal_comfyui_pool_manager_explicit_config_skips_persistence_lookup(monkeypatch) -> None:
    monkeypatch.delenv("SAGA_RUNTIME_DB_URL", raising=False)
    monkeypatch.delenv("SAGA_MODAL_STATE_DB_URL", raising=False)

    manager = ModalComfyUIPoolManager(
        app_name="explicit-app-name",
        hf_token="hf-explicit-token",
        tokens=[_Token(name="member-01")],
        request_timeout_seconds=5,
    )

    assert manager.app_name == "explicit-app-name"
    assert manager.hf_token == "hf-explicit-token"


def test_modal_comfyui_token_pool_prefers_persisted_accounts_over_env_fallback(tmp_path: Path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'modal-provider-precedence.sqlite3'}"
    monkeypatch.setenv("SAGA_RUNTIME_DB_URL", database_url)
    monkeypatch.setenv("SAGA_RUNTIME_DB_MODE", "test_harness")
    monkeypatch.setenv("SAGA_MODAL_STATE_DB_URL", database_url)
    monkeypatch.setenv("SAGA_MODAL_STATE_DB_MODE", "test_harness")
    monkeypatch.setenv("SAGA_RUNTIME_LOCAL_STORAGE_ROOT", str(tmp_path / "runtime-storage"))
    monkeypatch.setenv("SAGA_MODAL_ALLOW_ENV_FALLBACK", "1")
    monkeypatch.setenv("MODAL_TOKEN_ID", "env-token-id")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "env-token-secret")
    clear_modal_provider_config_cache()

    save_modal_provider_secret_config(
        "modal_comfyui",
        {
            "accounts": [
                {
                    "label": "member-01",
                    "token_id": "persisted-token-id",
                    "token_secret": "persisted-token-secret",
                }
            ]
        },
    )

    tokens = load_tokens()

    assert len(tokens) == 1
    assert tokens[0].name == "member-01"
    assert tokens[0].token_id == "persisted-token-id"
    assert tokens[0].token_secret == "persisted-token-secret"


def test_modal_timing_collector_aggregates_phase_totals() -> None:
    collector = ModalTimingCollector()
    collector.record("modal_phase", 0.25, token_name="member-01")
    collector.record("modal_phase", 0.5, token_name="member-02")

    summary = collector.summary()

    assert summary["modal_phase"]["count"] == 2
    assert summary["modal_phase"]["total_seconds"] == 0.75
    assert summary["modal_phase"]["max_seconds"] == 0.5
    assert summary["modal_phase"]["last_metadata"]["token_name"] == "member-02"


def test_modal_timing_collection_context_records_events() -> None:
    with collect_modal_timings() as collector:
        record_modal_timing("modal_health_check", 0.125, ready=True)

    assert len(collector.events) == 1
    assert collector.events[0].phase == "modal_health_check"
    assert collector.events[0].metadata["ready"] is True
