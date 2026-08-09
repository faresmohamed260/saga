import requests

from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.reasoning_runtime.client import ReasoningRuntimeClient
from packages.reasoning_runtime.factory import create_reasoning_client
from packages.reasoning_runtime.models import (
    GeneralComputeAccount,
    OllamaAccount,
    ReasoningProfile,
    ReasoningRuntimeConfig,
)


def test_ollama_cloud_payload_drops_cloud_suffix():
    config = ReasoningRuntimeConfig(
        profiles={"default": ReasoningProfile(name="default", mode="gpt_oss")},
        ollama_accounts=[OllamaAccount(label="a1", api_key="test-key")],
    )
    client = create_reasoning_client(profile_name="default", config=config)
    payload = client._ollama_payload(
        prompt="hello", model_name=client.resolved_model_name(), direct_cloud=True,
        temperature=0.25, max_tokens=17,
    )
    assert payload["model"] == "gpt-oss:120b"
    assert payload["think"] == "low"
    assert payload["options"] == {"temperature": 0.25, "num_predict": 17}


def test_ollama_json_payload_enables_native_json_mode():
    config = ReasoningRuntimeConfig(
        profiles={"default": ReasoningProfile(name="default", mode="gpt_oss")},
        ollama_accounts=[OllamaAccount(label="a1", api_key="test-key")],
    )
    client = create_reasoning_client(profile_name="default", config=config)
    payload = client._ollama_payload(
        prompt="hello",
        model_name=client.resolved_model_name(),
        direct_cloud=True,
        json_mode=True,
    )
    assert payload["format"] == "json"


def test_ollama_clones_share_round_robin_account_allocation():
    config = ReasoningRuntimeConfig(
        profiles={"default": ReasoningProfile(name="default", mode="gpt_oss")},
        ollama_accounts=[OllamaAccount(label=f"api-{index}", api_key=f"key-{index}") for index in range(1, 5)],
    )
    client = create_reasoning_client(profile_name="default", config=config)
    clones = [client.clone() for _ in range(4)]

    for clone in clones:
        clone._ollama_transport()

    assert [clone._request_account_alias for clone in clones] == ["api-1", "api-2", "api-3", "api-4"]
    assert all(clone._ollama_pool is client._ollama_pool for clone in clones)


def test_general_compute_rotation_advances_active_index():
    config = ReasoningRuntimeConfig(
        profiles={"default": ReasoningProfile(name="default", mode="general_compute")},
        general_compute_accounts=[
            GeneralComputeAccount(label="gc1", api_key="key-1"),
            GeneralComputeAccount(label="gc2", api_key="key-2"),
        ],
    )
    client = create_reasoning_client(profile_name="default", config=config)
    assert client._rotate_account() is True
    assert client.config.general_compute_active_index == 1


def test_retry_json_rotates_on_rate_limit():
    config = ReasoningRuntimeConfig(
        profiles={"default": ReasoningProfile(name="default", mode="general_compute", max_retries=1)},
        general_compute_accounts=[
            GeneralComputeAccount(label="gc1", api_key="key-1"),
            GeneralComputeAccount(label="gc2", api_key="key-2"),
        ],
    )
    client = create_reasoning_client(profile_name="default", config=config)
    rotated = {"count": 0}

    def _func():
        if rotated["count"] == 0:
            response = requests.Response()
            response.status_code = 429
            error = requests.HTTPError("429")
            error.response = response
            raise error
        return {"ok": True}

    original_rotate = client._rotate_account

    def _rotate():
        rotated["count"] += 1
        return original_rotate()

    client._rotate_account = _rotate
    assert client._retry_json_request(_func) == {"ok": True}


def test_retry_json_backs_off_on_sdk_rate_limit(monkeypatch):
    config = ReasoningRuntimeConfig(
        profiles={"default": ReasoningProfile(name="default", mode="mistral", max_retries=2)},
        mistral_api_key="test-key",
    )
    client = create_reasoning_client(profile_name="default", config=config)
    calls = {"count": 0}
    sleeps: list[float] = []
    monkeypatch.setattr("packages.reasoning_runtime.client.time.sleep", lambda seconds: sleeps.append(seconds))

    def _func():
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("API error occurred: Status 429. Body: rate limit exceeded")
        return {"ok": True}

    assert client._retry_json_request(_func) == {"ok": True}
    assert calls["count"] == 2
    assert sleeps == [8]


def test_retry_json_retries_transient_structured_output_failures(monkeypatch):
    config = ReasoningRuntimeConfig(
        profiles={"default": ReasoningProfile(name="default", mode="gpt_oss", max_retries=3)},
        ollama_accounts=[OllamaAccount(label="a1", api_key="test-key")],
    )
    client = create_reasoning_client(profile_name="default", config=config)
    monkeypatch.setattr("packages.reasoning_runtime.client.time.sleep", lambda _seconds: None)
    responses = iter([
        {"error": "parse_failed", "raw_output": "not-json"},
        {"error": "empty_response"},
        {"ok": True},
    ])

    assert client._retry_json_request(lambda: next(responses)) == {"ok": True}


def test_safe_parse_json_extracts_object_from_fence():
    assert ReasoningRuntimeClient._safe_parse_json("```json\n{\"ok\": true}\n```") == {"ok": True}


def test_reasoning_tool_returns_standard_envelope():
    profile = ReasoningProfile(name="default", mode="gpt_oss")
    client = create_reasoning_client(
        profile_name="default",
        config=ReasoningRuntimeConfig(profiles={"default": profile}),
    )

    client.generate_text = lambda *args, **kwargs: "contract ready"  # type: ignore[method-assign]
    client.last_request_metadata = lambda: {"provider": "stubbed"}  # type: ignore[method-assign]

    tools = {tool.name: tool for tool in client.as_langgraph_tools()}
    result = tools["reasoning_generate_text"].invoke({"prompt": "hello"})

    assert result["ok"] is True
    assert result["data"]["text"] == "contract ready"
    assert "request_metadata" in result["data"]
    assert result["trace"]["component"] == "reasoning_runtime"
    assert result["trace"]["events"][0]["event_type"] == "runtime_tool.started"
    assert result["trace"]["events"][-1]["event_type"] == "runtime_tool.succeeded"
    assert result["trace"]["events"][-1]["details"]["tool_name"] == "reasoning_generate_text"


def test_reasoning_json_tool_returns_payload_diagnostics_and_validates_expected_keys():
    profile = ReasoningProfile(name="default", mode="gpt_oss")
    client = create_reasoning_client(
        profile_name="default",
        config=ReasoningRuntimeConfig(profiles={"default": profile}),
    )

    client.generate_json = lambda *args, **kwargs: {"answer": "Victor Frankenstein", "confidence": 0.92}  # type: ignore[method-assign]
    client.last_request_metadata = lambda: {"provider": "stubbed", "operation": "generate_json"}  # type: ignore[method-assign]

    tools = {tool.name: tool for tool in client.as_langgraph_tools()}
    result = tools["reasoning_generate_json"].invoke(
        {"prompt": "Return answer JSON.", "expected_keys": ["answer", "confidence"]}
    )

    assert result["ok"] is True
    assert result["data"]["payload_kind"] == "object"
    assert result["data"]["payload_keys"] == ["answer", "confidence"]
    assert result["data"]["field_count"] == 2
    assert result["data"]["payload"]["answer"] == "Victor Frankenstein"
    assert result["data"]["request_metadata"]["operation"] == "generate_json"


def test_reasoning_json_tool_rejects_missing_expected_keys():
    profile = ReasoningProfile(name="default", mode="gpt_oss")
    client = create_reasoning_client(
        profile_name="default",
        config=ReasoningRuntimeConfig(profiles={"default": profile}),
    )

    client.generate_json = lambda *args, **kwargs: {"answer": "Victor Frankenstein"}  # type: ignore[method-assign]
    client.last_request_metadata = lambda: {"provider": "stubbed", "operation": "generate_json"}  # type: ignore[method-assign]

    tools = {tool.name: tool for tool in client.as_langgraph_tools()}
    result = tools["reasoning_generate_json"].invoke(
        {"prompt": "Return answer JSON.", "expected_keys": ["answer", "confidence"]}
    )

    assert result["ok"] is False
    assert result["error"]["category"] == "validation"
    assert "missing required keys" in result["error"]["message"]
    assert result["trace"]["events"][0]["event_type"] == "runtime_tool.started"
    assert result["trace"]["events"][-1]["event_type"] == "runtime_tool.failed"
    assert result["trace"]["events"][-1]["details"]["error_category"] == "validation"


def test_reasoning_request_metadata_tracks_runtime_fields():
    profile = ReasoningProfile(name="default", mode="gpt_oss")
    client = create_reasoning_client(
        profile_name="default",
        config=ReasoningRuntimeConfig(profiles={"default": profile}),
    )

    client._begin_request_tracking()
    client._finalize_request_tracking()
    metadata = client.last_request_metadata()

    assert metadata["trace_id"]
    assert metadata["component"] == "reasoning_runtime"
    assert metadata["operation"] == "reasoning_request"
    assert metadata["request_kind"] == ""
    assert metadata["provider_family"] == "ollama"
    assert metadata["resolved_model"]
    assert metadata["latency_ms"] >= 0


def test_reasoning_json_request_metadata_tracks_json_mode():
    profile = ReasoningProfile(name="default", mode="gpt_oss")
    client = create_reasoning_client(
        profile_name="default",
        config=ReasoningRuntimeConfig(profiles={"default": profile}),
    )

    client._pending_request_kind = "json"
    client._pending_json_mode = "strict_prompt"
    client._pending_response_format_type = "json_schema"
    client._pending_tool_mode = "tool_calling"
    client._begin_request_tracking()
    client._finalize_request_tracking()
    metadata = client.last_request_metadata()

    assert metadata["request_kind"] == "json"
    assert metadata["json_mode"] == "strict_prompt"
    assert metadata["response_format_type"] == "json_schema"
    assert metadata["tool_mode"] == "tool_calling"
    assert metadata["status"] == "ok"


def test_reasoning_profile_rejects_invalid_runtime_values():
    try:
        ReasoningProfile(name="", mode="gpt_oss")
    except ValueError as exc:
        assert "name is required" in str(exc)
    else:
        raise AssertionError("Expected invalid reasoning profile to be rejected.")

    try:
        ReasoningRuntimeConfig(
            profiles={"default": ReasoningProfile(name="default", mode="gpt_oss")},
            ollama_local_url="localhost-only",
        )
    except ValueError as exc:
        assert "ollama_local_url" in str(exc)
    else:
        raise AssertionError("Expected invalid reasoning runtime config URL to be rejected.")


def test_reasoning_factory_loads_ollama_accounts_from_persistence(tmp_path):
    persistence_profile = PersistenceProfile(
        name="reasoning-provider-config",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'reasoning-provider-config.sqlite3'}",
    )
    persistence_client = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=persistence_profile),
        profile=persistence_profile,
    )
    persistence_client.initialize()
    persistence_client.provider_configs.upsert_provider_config(
        "ollama",
        {
            "active_index": 1,
            "accounts": [
                {"label": "api-1", "api_key": "key-1"},
                {"label": "api-2", "api_key": "key-2"},
            ],
        },
    )
    config = ReasoningRuntimeConfig(profiles={"default": ReasoningProfile(name="default", mode="gpt_oss")})

    client = create_reasoning_client(
        profile_name="default",
        config=config,
        persistence_client=persistence_client,
    )

    assert len(client.config.ollama_accounts) == 2
    assert client.config.ollama_active_index == 1
    assert client._ollama_pool.current_label() == "api-2"
