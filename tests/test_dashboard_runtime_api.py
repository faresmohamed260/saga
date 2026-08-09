from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from apps.dashboard_api.app import app
from packages.agent_runtime.graph import AgentGraphRuntime
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.reasoning_runtime.contracts import ReasoningClient
from packages.observability_runtime import CostRate, UsageGovernanceRuntime
from packages.runtime_common import ProviderUsage, UsageAttribution


class StubArtifactPlanner(ReasoningClient):
    mode = "stub_artifact_planner"

    def __init__(self) -> None:
        self.calls = 0

    def generate_json(
        self,
        prompt: str,
        strict: bool = False,
        validator=None,
        max_tokens: int = 4096,
        response_format=None,
        tools=None,
        tool_choice=None,
    ) -> dict:
        self.calls += 1
        if self.calls == 1:
            return {
                "action": "tool",
                "rationale": "Persist the runtime report artifact first.",
                "response": "",
                "tool_name": "persistence_store_text_artifact",
                "tool_input": {
                    "artifact_type": "runtime_report",
                    "filename": "report.txt",
                    "text": "agent-produced runtime artifact",
                    "provider_name": "modal_comfyui",
                    "report_kind": "integration-test",
                    "metadata": {"source": "langgraph-runtime-e2e"},
                },
            }
        return {
            "action": "respond",
            "rationale": "The artifact is stored and can now be served over HTTP.",
            "response": "Runtime artifact stored successfully.",
            "tool_name": "",
            "tool_input": {},
        }

    def generate_text(self, prompt: str, *, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 4096) -> str:
        return "unused"

    def provider_name(self) -> str:
        return "stub-artifact-planner"

    def resolved_model_name(self) -> str:
        return "stub-artifact-planner-model"

    def last_request_metadata(self) -> dict:
        return {}


def test_runtime_state_reports_active_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("SAGA_RUNTIME_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'runtime-state.sqlite3'}")
    monkeypatch.setenv("SAGA_RUNTIME_DB_MODE", "test_harness")
    monkeypatch.setenv("SAGA_RUNTIME_LOCAL_STORAGE_ROOT", str(tmp_path / "runtime-storage"))

    client = TestClient(app)
    response = client.get("/runtime/state")

    assert response.status_code == 200
    payload = response.json()
    assert payload["runtime"]["provider"] == "test_harness"
    assert payload["runtime"]["database"]["configured"] is True
    assert "database_url" not in payload["runtime"]
    assert payload["artifacts"]["buckets"]["generated_images"] == "generated-images"


def test_runtime_artifact_object_serves_unified_runtime_objects(monkeypatch, tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'runtime-objects.sqlite3'}"
    local_storage_root = tmp_path / "runtime-storage"
    monkeypatch.setenv("SAGA_RUNTIME_DB_URL", database_url)
    monkeypatch.setenv("SAGA_RUNTIME_DB_MODE", "test_harness")
    monkeypatch.setenv("SAGA_RUNTIME_LOCAL_STORAGE_ROOT", str(local_storage_root))

    profile = PersistenceProfile(
        name="test-runtime-api",
        provider="supabase",
        mode="test_harness",
        database_url=database_url,
        local_storage_root_dir=str(local_storage_root),
    )
    persistence = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=profile),
        profile=profile,
    )
    persistence.initialize()
    persistence.objects.ensure_bucket("generated-images")
    persistence.objects.upload_text(
        "generated-images",
        "series/test/assets/hero/image.txt",
        "artifact bytes",
        content_type="text/custom-runtime",
    )

    client = TestClient(app)
    response = client.get(
        "/runtime/artifacts/object",
        params={"bucket_name": "generated-images", "object_path": "series/test/assets/hero/image.txt"},
    )

    assert response.status_code == 200
    assert response.text == "artifact bytes"
    assert response.headers["content-type"].startswith("text/custom-runtime")


def test_runtime_provider_state_exposes_config_and_statuses(monkeypatch, tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'runtime-provider.sqlite3'}"
    local_storage_root = tmp_path / "runtime-storage"
    monkeypatch.setenv("SAGA_RUNTIME_DB_URL", database_url)
    monkeypatch.setenv("SAGA_RUNTIME_DB_MODE", "test_harness")
    monkeypatch.setenv("SAGA_RUNTIME_LOCAL_STORAGE_ROOT", str(local_storage_root))

    profile = PersistenceProfile(
        name="test-runtime-provider-api",
        provider="supabase",
        mode="test_harness",
        database_url=database_url,
        local_storage_root_dir=str(local_storage_root),
    )
    persistence = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=profile),
        profile=profile,
    )
    persistence.initialize()
    persistence.provider_configs.upsert_provider_config("modal_comfyui", {"runtime_state": {"active_token_name": "member-01"}})
    persistence.provider_configs.upsert_provider_status(
        "modal_comfyui",
        "member-01",
        {"last_health_ok": True, "api_url": "https://image.example/api"},
    )

    client = TestClient(app)
    response = client.get("/runtime/providers/modal_comfyui")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider_name"] == "modal_comfyui"
    assert payload["found"] is True
    assert payload["runtime_state"]["active_label"] == "member-01"
    assert payload["status_count"] == 1
    assert payload["statuses"][0]["label"] == "member-01"
    assert payload["healthy_labels"] == ["member-01"]


def test_runtime_artifact_object_serves_langgraph_persisted_artifact(monkeypatch, tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'runtime-agent-artifact.sqlite3'}"
    local_storage_root = tmp_path / "runtime-storage"
    monkeypatch.setenv("SAGA_RUNTIME_DB_URL", database_url)
    monkeypatch.setenv("SAGA_RUNTIME_DB_MODE", "test_harness")
    monkeypatch.setenv("SAGA_RUNTIME_LOCAL_STORAGE_ROOT", str(local_storage_root))

    profile = PersistenceProfile(
        name="test-runtime-agent-artifact",
        provider="supabase",
        mode="test_harness",
        database_url=database_url,
        local_storage_root_dir=str(local_storage_root),
    )
    persistence = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=profile),
        profile=profile,
    )
    persistence.initialize()

    runtime = AgentGraphRuntime(
        reasoning_client=StubArtifactPlanner(),
        tools=persistence.as_langgraph_tools(),
        system_prompt="You are a test orchestration agent.",
        checkpoint_engine=persistence.engine,
    )
    result = runtime.invoke(
        user_input="Persist a runtime artifact and finish.",
        max_steps=4,
        thread_id="artifact-http-e2e",
    )

    assert result.final_output == "Runtime artifact stored successfully."
    assert len(result.tool_history) == 1
    assert result.tool_history[0].tool_name == "persistence_store_text_artifact"
    assert result.tool_history[0].tool_output.ok is True
    assert result.tool_history[0].trace.run_id == "artifact-http-e2e"

    artifact = result.tool_history[0].tool_output.data
    assert artifact["artifact_type"] == "runtime_report"
    assert artifact["request_metadata"]["operation"] == "store_text_artifact"
    assert artifact["provider"] == "test_harness"

    client = TestClient(app)
    response = client.get(
        "/runtime/artifacts/object",
        params={
            "bucket_name": artifact["bucket_name"],
            "object_path": artifact["object_path"],
        },
    )

    assert response.status_code == 200
    assert response.text == "agent-produced runtime artifact"
    assert response.headers["content-type"].startswith("text/plain")


def test_runtime_artifact_object_serves_persisted_agent_execution_report(monkeypatch, tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'runtime-agent-report.sqlite3'}"
    local_storage_root = tmp_path / "runtime-storage"
    monkeypatch.setenv("SAGA_RUNTIME_DB_URL", database_url)
    monkeypatch.setenv("SAGA_RUNTIME_DB_MODE", "test_harness")
    monkeypatch.setenv("SAGA_RUNTIME_LOCAL_STORAGE_ROOT", str(local_storage_root))

    profile = PersistenceProfile(
        name="test-runtime-agent-report",
        provider="supabase",
        mode="test_harness",
        database_url=database_url,
        local_storage_root_dir=str(local_storage_root),
    )
    persistence = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=profile),
        profile=profile,
    )
    persistence.initialize()

    runtime = AgentGraphRuntime(
        reasoning_client=StubArtifactPlanner(),
        tools=persistence.as_langgraph_tools(),
        system_prompt="You are a test orchestration agent.",
        checkpoint_engine=persistence.engine,
    )
    result = runtime.invoke(
        user_input="Persist a runtime artifact and finish.",
        max_steps=4,
        thread_id="artifact-report-e2e",
    )
    report_payload = result.to_report_payload()
    artifact = persistence.artifacts.store_json(
        artifact_type="runtime_report",
        filename="agent-execution-report.json",
        payload=report_payload,
        provider_name="agent_runtime",
        report_kind="execution-report",
        metadata={"run_id": result.summary.run_id},
    )

    client = TestClient(app)
    response = client.get(
        "/runtime/artifacts/object",
        params={
            "bucket_name": artifact["bucket_name"],
            "object_path": artifact["object_path"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["report_type"] == "agent_execution_report"
    assert payload["summary"]["run_id"] == "artifact-report-e2e"
    assert payload["summary"]["status"] == "ok"
    assert payload["tool_history"][0]["tool_name"] == "persistence_store_text_artifact"


def test_runtime_inference_provider_saves_and_redacts_modal_secrets(monkeypatch, tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'runtime-provider-secrets.sqlite3'}"
    local_storage_root = tmp_path / "runtime-storage"
    monkeypatch.setenv("SAGA_RUNTIME_DB_URL", database_url)
    monkeypatch.setenv("SAGA_RUNTIME_DB_MODE", "test_harness")
    monkeypatch.setenv("SAGA_RUNTIME_LOCAL_STORAGE_ROOT", str(local_storage_root))
    monkeypatch.setenv("SAGA_MODAL_STATE_DB_URL", database_url)
    monkeypatch.setenv("SAGA_MODAL_STATE_DB_MODE", "test_harness")

    profile = PersistenceProfile(
        name="test-runtime-provider-secrets",
        provider="supabase",
        mode="test_harness",
        database_url=database_url,
        local_storage_root_dir=str(local_storage_root),
    )
    persistence = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=profile),
        profile=profile,
    )
    persistence.initialize()

    client = TestClient(app)
    save_response = client.post(
        "/runtime/inference/providers/modal_comfyui",
        json={
            "app_name": "saga-image-runtime",
            "hf_token": "hf-secret-value",
            "request_timeout_seconds": 600,
            "accounts": [
                {
                    "label": "member-01",
                    "token_id": "modal-id",
                    "token_secret": "modal-secret",
                    "app_name_override": "saga-image-runtime",
                }
            ],
        },
    )

    assert save_response.status_code == 200
    save_payload = save_response.json()["provider"]
    assert save_payload["has_hf_token"] is True
    assert save_payload["accounts"][0]["has_token_id"] is True
    assert save_payload["accounts"][0]["has_token_secret"] is True
    assert "hf_token" not in save_payload
    assert "hf-secret-value" not in str(save_payload)
    assert "modal-secret" not in str(save_payload)

    get_response = client.get("/runtime/inference/providers/modal_comfyui")
    assert get_response.status_code == 200
    get_payload = get_response.json()["provider"]
    assert get_payload["has_hf_token"] is True
    assert get_payload["accounts"][0]["has_token_id"] is True
    assert get_payload["accounts"][0]["has_token_secret"] is True
    assert "hf_token" not in get_payload

    stored = persistence.provider_configs.get_provider_config("modal_comfyui")
    assert stored is not None
    assert stored["payload"]["hf_token"] == "hf-secret-value"
    assert stored["payload"]["accounts"][0]["token_secret"] == "modal-secret"


def test_runtime_provider_statuses_include_modal_and_reasoning_summaries(monkeypatch, tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'runtime-provider-statuses.sqlite3'}"
    local_storage_root = tmp_path / "runtime-storage"
    monkeypatch.setenv("SAGA_RUNTIME_DB_URL", database_url)
    monkeypatch.setenv("SAGA_RUNTIME_DB_MODE", "test_harness")
    monkeypatch.setenv("SAGA_RUNTIME_LOCAL_STORAGE_ROOT", str(local_storage_root))
    monkeypatch.setenv("SAGA_MODAL_STATE_DB_URL", database_url)
    monkeypatch.setenv("SAGA_MODAL_STATE_DB_MODE", "test_harness")
    monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral-key")

    profile = PersistenceProfile(
        name="test-runtime-provider-statuses",
        provider="supabase",
        mode="test_harness",
        database_url=database_url,
        local_storage_root_dir=str(local_storage_root),
    )
    persistence = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=profile),
        profile=profile,
    )
    persistence.initialize()
    persistence.provider_configs.upsert_provider_config(
        "ollama",
        {"active_index": 0, "accounts": [{"label": "api-1", "api_key": "ollama-key"}]},
    )
    persistence.provider_configs.upsert_provider_config(
        "modal_comfyui",
        {"accounts": [{"label": "member-01", "token_id": "token-id", "token_secret": "token-secret"}]},
    )
    persistence.provider_configs.upsert_provider_status(
        "modal_comfyui",
        "member-01",
        {"last_health_ok": True, "last_request_ok": True, "api_url": "https://image.example/api"},
    )

    client = TestClient(app)
    response = client.get("/runtime/providers/status")

    assert response.status_code == 200
    payload = response.json()["providers"]
    assert payload["modal_comfyui"]["config"]["accounts"][0]["has_token_secret"] is True
    assert payload["modal_comfyui"]["statuses"][0]["probe_status"] == "ok"
    assert payload["ollama"]["config"]["accounts"][0]["has_api_key"] is True
    assert payload["mistral"]["statuses"][0]["probe_status"] == "configured"


def test_runtime_usage_summary_and_budget_policy_surface(monkeypatch, tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'runtime-usage.sqlite3'}"
    storage_root = tmp_path / "objects"
    monkeypatch.setenv("SAGA_RUNTIME_DB_URL", database_url)
    monkeypatch.setenv("SAGA_RUNTIME_DB_MODE", "test_harness")
    monkeypatch.setenv("SAGA_RUNTIME_LOCAL_STORAGE_ROOT", str(storage_root))
    profile = PersistenceProfile(
        name="test-runtime-usage", provider="supabase", mode="test_harness",
        database_url=database_url, local_storage_root_dir=str(storage_root),
    )
    persistence = create_persistence_client(profile=profile, config=PersistenceRuntimeConfig(profile=profile))
    persistence.initialize()
    governor = UsageGovernanceRuntime(store=persistence.usage, cost_rates=(CostRate(
        provider="mistral", model="model-a", input_per_million=2, output_per_million=6, pricing_version="test-rate",
    ),))
    attribution = UsageAttribution(run_id="run-usage", stage="canon", provider="mistral", model="model-a")
    reservation = governor.reserve(attribution, ProviderUsage(input_tokens=20, output_tokens=10, source="declared"))
    governor.settle(reservation, ProviderUsage(input_tokens=12, output_tokens=4, evidence_id="request-1"))

    client = TestClient(app)
    saved = client.post("/runtime/usage/budgets/run-cap", json={
        "scope_type": "run", "limits": {"cost_usd": 1}, "hard_limit": True,
    })
    response = client.get("/runtime/usage/summary", params={"run_id": "run-usage"})

    assert saved.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["charge_count"] == 1
    assert payload["summary"]["unpriced_charge_count"] == 0
    assert payload["by_provider"][0]["provider"] == "mistral"
    assert payload["by_account"][0]["account_alias"] == "unattributed"
    assert payload["by_model"][0]["model"] == "model-a"
    assert payload["policies"][0]["policy_id"] == "run-cap"
