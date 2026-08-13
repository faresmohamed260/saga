import requests
import pytest
from types import SimpleNamespace

from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.reasoning_runtime.client import ReasoningRuntimeClient
from packages.reasoning_runtime.client import _mistral_usage, _wav_duration_seconds
from packages.reasoning_runtime.factory import create_reasoning_client
from packages.reasoning_runtime.models import (
    GeneralComputeAccount,
    OllamaAccount,
    ReasoningProfile,
    ReasoningRuntimeConfig,
)
from packages.reasoning_runtime.provider_config import apply_persistence_provider_configs, summarize_reasoning_provider_configs
from packages.runtime_common import RuntimeCancelledError


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


def test_ollama_local_profile_is_explicit_and_cannot_use_cloud_accounts():
    client = create_reasoning_client(
        profile_name="local",
        config=ReasoningRuntimeConfig(
            profiles={
                "local": ReasoningProfile(
                    name="local", mode="ollama_local", ollama_model="qwen2.5:14b",
                    ollama_gpu_layers=32, ollama_threads=8,
                )
            },
            ollama_accounts=[OllamaAccount(label="cloud", api_key="secret")],
        ),
    )

    assert client.provider_name() == "ollama_local"
    assert client.resolved_model_name() == "qwen2.5:14b"
    assert client._ollama_transport() == (
        "http://localhost:11434/api/generate", {}, False,
    )
    assert client._ollama_payload(
        prompt="probe", model_name=client.resolved_model_name(), direct_cloud=False,
    )["options"] == {"temperature": 0.0, "num_predict": 4096, "num_ctx": 8192, "num_gpu": 32, "num_thread": 8}
    assert client._rotate_account() is False


def test_ollama_local_profile_rejects_non_loopback_transport():
    with pytest.raises(ValueError, match="loopback-only"):
        create_reasoning_client(
            profile_name="local",
            config=ReasoningRuntimeConfig(
                profiles={
                    "local": ReasoningProfile(
                        name="local", mode="ollama_local", ollama_model="qwen2.5:14b",
                    )
                },
                ollama_local_url="https://ollama.com/api/generate",
            ),
        )


def test_ollama_local_tool_use_calls_native_chat_endpoint(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "message": {"tool_calls": [{"function": {
                    "name": "lookup_book",
                    "arguments": {"book_id": "book-1"},
                }}]},
                "prompt_eval_count": 12,
                "eval_count": 8,
                "eval_duration": 1_000_000_000,
            }

    def post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return Response()

    monkeypatch.setattr(requests, "post", post)
    client = create_reasoning_client(
        profile_name="local",
        config=ReasoningRuntimeConfig(profiles={
            "local": ReasoningProfile(
                name="local", mode="ollama_local", ollama_model="qwen2.5:14b",
                max_retries=1,
            )
        }),
    )
    tools = [{"type": "function", "function": {
        "name": "lookup_book",
        "description": "Load one book.",
        "parameters": {
            "type": "object",
            "properties": {"book_id": {"type": "string"}},
            "required": ["book_id"],
        },
    }}]

    result = client.generate_json("Load book-1.", tools=tools, max_tokens=64)

    assert result == {"tool_calls": [{"tool": "lookup_book", "arguments": {"book_id": "book-1"}}]}
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["json"]["tools"] == tools
    assert captured["json"]["keep_alive"] == "5m"
    assert client.last_request_metadata()["tool_mode"] == "tool_calling"


def test_ollama_provider_metrics_preserve_native_load_and_decode_timings():
    client = create_reasoning_client(
        profile_name="local",
        config=ReasoningRuntimeConfig(profiles={
            "local": ReasoningProfile(
                name="local", mode="ollama_local", ollama_model="qwen2.5:14b",
            )
        }),
    )
    response = SimpleNamespace(json=lambda: {
        "total_duration": 2_000_000_000,
        "load_duration": 500_000_000,
        "prompt_eval_duration": 250_000_000,
        "eval_duration": 1_000_000_000,
        "eval_count": 25,
    })

    client._capture_ollama_metrics(response)

    assert client._provider_metrics == {
        "total_duration_seconds": 2.0,
        "load_duration_seconds": 0.5,
        "prompt_eval_duration_seconds": 0.25,
        "eval_duration_seconds": 1.0,
        "tokens_per_second": 25.0,
    }


def test_mistral_native_usage_extraction_is_exact_and_mock_safe():
    usage = _mistral_usage(SimpleNamespace(
        id="request-1",
        usage=SimpleNamespace(prompt_tokens=41, completion_tokens=11, cached_tokens=7),
    ))
    assert usage.input_tokens == 41
    assert usage.output_tokens == 11
    assert usage.cached_input_tokens == 7
    assert usage.evidence_id == "request-1"

    assert _mistral_usage(SimpleNamespace()).model_dump(exclude={"source"}) == {
        "request_count": 1.0, "input_tokens": 0.0, "output_tokens": 0.0,
        "cached_input_tokens": 0.0, "compute_seconds": 0.0, "image_count": 0.0,
        "audio_seconds": 0.0, "native_cost_usd": None, "evidence_id": "",
    }


def test_mistral_json_generation_forwards_schema_and_output_limit():
    config = ReasoningRuntimeConfig(
        profiles={"default": ReasoningProfile(name="default", mode="mistral", max_retries=1)},
        mistral_api_key="test-key",
    )
    client = create_reasoning_client(profile_name="default", config=config)
    captured = {}

    def complete(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            id="request-1",
            usage=SimpleNamespace(prompt_tokens=7, completion_tokens=3, cached_tokens=0),
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"answer":"ready"}'))],
        )

    client._mistral_client = SimpleNamespace(chat=SimpleNamespace(complete=complete))
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "answer",
            "schema": {
                "type": "object",
                "properties": {"answer": {"type": "string"}},
                "required": ["answer"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }

    result = client.generate_json(
        "Return an answer.",
        strict=True,
        max_tokens=321,
        response_format=response_format,
    )

    assert result == {"answer": "ready"}
    assert captured["max_tokens"] == 321
    assert captured["response_format"] == response_format
    assert client.last_request_metadata()["response_format_type"] == "json_schema"


def test_wav_duration_is_available_for_per_minute_transcription_pricing():
    import io
    import wave

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(b"\x00\x00" * 32000)

    audio = buffer.getvalue()
    assert _wav_duration_seconds(audio) == 2.0

    client = create_reasoning_client(
        profile_name="transcription",
        config=ReasoningRuntimeConfig(
            profiles={
                "transcription": ReasoningProfile(
                    name="transcription",
                    mode="mistral",
                    model_override="voxtral-mini-latest",
                )
            }
        ),
    )
    complete = SimpleNamespace(
        text="spoken words",
        language="en",
        model="voxtral-mini-latest",
        usage=SimpleNamespace(prompt_tokens=0, completion_tokens=0),
    )
    client._mistral_client = SimpleNamespace(
        audio=SimpleNamespace(
            transcriptions=SimpleNamespace(complete=lambda **_: complete)
        )
    )

    client.transcribe_audio(audio_bytes=audio)

    assert client.last_request_metadata()["usage"]["audio_seconds"] == 2.0


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


def test_database_owned_sdk_provider_keys_override_process_composition_without_leaking():
    rows = {
        "mistral": {"payload": {"api_key": "db-mistral-secret"}},
        "gemini": {"payload": {"api_key": "db-gemini-secret"}},
    }

    class ProviderConfigs:
        def get_provider_config(self, provider_name):
            return rows.get(provider_name)

    persistence = type("Persistence", (), {"provider_configs": ProviderConfigs()})()
    config = ReasoningRuntimeConfig(
        profiles={"default": ReasoningProfile(name="default")},
        mistral_api_key="process-mistral-secret",
        gemini_api_key="process-gemini-secret",
    )

    resolved = apply_persistence_provider_configs(config, persistence_client=persistence)
    summary = summarize_reasoning_provider_configs(persistence)

    assert resolved.mistral_api_key == "db-mistral-secret"
    assert resolved.gemini_api_key == "db-gemini-secret"
    assert summary["mistral"]["configured"] is True
    assert summary["gemini"]["configured"] is True
    assert "secret" not in str(summary)


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


def test_retry_json_stops_before_another_provider_attempt_after_cancellation(monkeypatch):
    config = ReasoningRuntimeConfig(
        profiles={"default": ReasoningProfile(name="default", mode="gpt_oss", max_retries=4)},
        ollama_accounts=[OllamaAccount(label="a1", api_key="test-key")],
    )
    client = create_reasoning_client(profile_name="default", config=config)
    monkeypatch.setattr("packages.reasoning_runtime.client.time.sleep", lambda _seconds: None)
    state = {"calls": 0, "cancelled": False}

    def operation():
        state["calls"] += 1
        state["cancelled"] = True
        return {"error": "parse_failed", "raw_output": "truncated"}

    with pytest.raises(RuntimeCancelledError):
        client._retry_json_request(operation, cancellation_checker=lambda: state["cancelled"])

    assert state["calls"] == 1


def test_retry_json_discards_a_response_completed_after_cancellation():
    config = ReasoningRuntimeConfig(
        profiles={"default": ReasoningProfile(name="default", mode="gpt_oss", max_retries=2)},
        ollama_accounts=[OllamaAccount(label="a1", api_key="test-key")],
    )
    client = create_reasoning_client(profile_name="default", config=config)
    state = {"cancelled": False}

    def operation():
        state["cancelled"] = True
        return {"ok": True}

    with pytest.raises(RuntimeCancelledError):
        client._retry_json_request(operation, cancellation_checker=lambda: state["cancelled"])


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
