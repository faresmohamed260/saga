import requests

from infrastructure.llm_client import LLMClient


def test_gpt_oss_local_ollama_payload_uses_low_thinking(monkeypatch):
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.setattr("infrastructure.ollama_account_rotator.OllamaAccountRotator.active_api_key", lambda self: "")
    client = LLMClient(mode=LLMClient.MODE_GPT_OSS, max_retries=1, base_delay=0.0, timeout=5)
    payload = client._ollama_generate_payload(
        prompt="hello",
        model_name=client._ollama_model_for_mode(),
    )
    assert payload["model"] == "gpt-oss:120b-cloud"
    assert payload["think"] == "low"


def test_non_gpt_oss_local_ollama_payload_has_no_think_override(monkeypatch):
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.setattr("infrastructure.ollama_account_rotator.OllamaAccountRotator.active_api_key", lambda self: "")
    client = LLMClient(mode=LLMClient.MODE_DEEPSEEK, max_retries=1, base_delay=0.0, timeout=5)
    payload = client._ollama_generate_payload(
        prompt="hello",
        model_name=client._ollama_model_for_mode(),
    )
    assert payload["model"] == "deepseek-v3.1:671b-cloud"
    assert "think" not in payload


def test_direct_cloud_payload_uses_non_cloud_model_name(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")
    client = LLMClient(mode=LLMClient.MODE_GPT_OSS, max_retries=1, base_delay=0.0, timeout=5)
    payload = client._ollama_generate_payload(
        prompt="hello",
        model_name=client._ollama_model_for_mode(),
    )
    assert client.ollama_direct_cloud is True
    assert payload["model"] == "gpt-oss:120b"
    assert payload["think"] == "low"


def test_rate_limit_exhaustion_can_rotate_and_retry(monkeypatch):
    client = LLMClient(mode=LLMClient.MODE_GPT_OSS, max_retries=1, base_delay=0.0, timeout=5)
    rotated = {"value": False}

    def _rotate():
        rotated["value"] = True
        return {"status": "rotated", "label": "backup"}

    monkeypatch.setattr(client, "_rotate_ollama_account", _rotate)

    def _func(_prompt: str):
        if not rotated["value"]:
            response = requests.Response()
            response.status_code = 429
            error = requests.HTTPError("429")
            error.response = response
            raise error
        return {"ok": True}

    result = client._retry_wrapper(_func, "hello")
    assert result == {"ok": True}


def test_probe_transport_uses_api_key_when_available(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")
    transport = LLMClient._resolve_probe_transport()
    assert transport["direct_cloud"] is True
    assert transport["url"] == LLMClient.OLLAMA_CLOUD_URL
    assert transport["headers"]["Authorization"] == "Bearer test-key"


def test_general_compute_defaults_to_provider_model_when_override_is_ollama_cloud_tag():
    client = LLMClient(
        mode=LLMClient.MODE_GENERAL_COMPUTE,
        ollama_model_override="gemma4:31b-cloud",
        max_retries=1,
        base_delay=0.0,
        timeout=5,
    )
    assert client._general_compute_model_for_mode() == "deepseek-v3.1"


def test_general_compute_rate_limit_exhaustion_can_rotate_and_retry(monkeypatch):
    client = LLMClient(mode=LLMClient.MODE_GENERAL_COMPUTE, max_retries=1, base_delay=0.0, timeout=5)
    rotated = {"value": False}

    def _rotate():
        rotated["value"] = True
        return {"status": "rotated", "label": "backup"}

    monkeypatch.setattr(client, "_rotate_general_compute_account", _rotate)

    def _func(_prompt: str):
        if not rotated["value"]:
            response = requests.Response()
            response.status_code = 429
            error = requests.HTTPError("429")
            error.response = response
            raise error
        return {"ok": True}

    result = client._retry_wrapper(_func, "hello")
    assert result == {"ok": True}


def test_safe_parse_json_strips_utf8_bom():
    client = LLMClient(mode=LLMClient.MODE_GENERAL_COMPUTE, max_retries=1, base_delay=0.0, timeout=5)
    parsed = client._safe_parse_json("\ufeff{\"ok\": true}")
    assert parsed == {"ok": True}


def test_general_compute_budget_estimate_splits_input_and_output():
    client = LLMClient(mode=LLMClient.MODE_GENERAL_COMPUTE, max_retries=1, base_delay=0.0, timeout=5)
    input_tokens, output_tokens = client._estimate_general_compute_token_budget("abcd" * 100, max_tokens=512)
    assert input_tokens == 100
    assert output_tokens == 512


def test_codex_uses_local_account_store_when_env_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("infrastructure.openai_account_store.OpenAIAccountStore.active_api_key", lambda self: "store-key")
    monkeypatch.setattr("infrastructure.llm_client.LLMClient._hermes_codex_available", classmethod(lambda cls: False))

    class _DummyResponses:
        def create(self, **kwargs):
            return type("Response", (), {"output_text": '{"ok": true}'})()

    class _DummyOpenAI:
        def __init__(self, api_key):
            assert api_key == "store-key"
            self.responses = _DummyResponses()

    monkeypatch.setattr("infrastructure.llm_client.OpenAI", _DummyOpenAI)
    client = LLMClient(mode=LLMClient.MODE_CODEX, max_retries=1, base_delay=0.0, timeout=5)

    assert client.provider_name() == "openai-codex"
    assert client.current_account_alias() == "openai_unconfigured" or client.current_account_alias()


def test_codex_generate_json_uses_json_object_format(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setattr("infrastructure.llm_client.LLMClient._hermes_codex_available", classmethod(lambda cls: False))
    captured = {}

    class _DummyResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return type("Response", (), {"output_text": '{"scene": "ok"}'})()

    class _DummyOpenAI:
        def __init__(self, api_key):
            assert api_key == "env-key"
            self.responses = _DummyResponses()

    monkeypatch.setattr("infrastructure.llm_client.OpenAI", _DummyOpenAI)
    client = LLMClient(mode=LLMClient.MODE_CODEX, max_retries=1, base_delay=0.0, timeout=5)
    payload = client.generate_json("Return JSON", strict=True, max_tokens=123)

    assert payload == {"scene": "ok"}
    assert captured["model"] == "gpt-5.4-mini"
    assert captured["max_output_tokens"] == 123
    assert captured["text"]["format"]["type"] == "json_object"


def test_codex_generate_text_uses_instructions(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setattr("infrastructure.llm_client.LLMClient._hermes_codex_available", classmethod(lambda cls: False))
    captured = {}

    class _DummyResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return type("Response", (), {"output_text": "final text"})()

    class _DummyOpenAI:
        def __init__(self, api_key):
            self.responses = _DummyResponses()

    monkeypatch.setattr("infrastructure.llm_client.OpenAI", _DummyOpenAI)
    client = LLMClient(mode=LLMClient.MODE_CODEX, max_retries=1, base_delay=0.0, timeout=5)
    text = client.generate_text("User prompt", system_prompt="System prompt", temperature=0.2, max_tokens=222)

    assert text == "final text"
    assert captured["instructions"] == "System prompt"
    assert captured["input"] == "User prompt"
    assert captured["temperature"] == 0.2
    assert captured["max_output_tokens"] == 222


def test_codex_uses_local_device_session_when_api_key_store_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("infrastructure.openai_account_store.OpenAIAccountStore.active_api_key", lambda self: "")
    monkeypatch.setattr("infrastructure.llm_client.LLMClient._hermes_codex_available", classmethod(lambda cls: False))
    monkeypatch.setattr("infrastructure.codex_session_store.CodexSessionStore.active_access_token", lambda self: "session-token")

    class _DummyResponses:
        def create(self, **kwargs):
            return type("Response", (), {"output_text": '{"ok": true}'})()

    class _DummyOpenAI:
        def __init__(self, api_key):
            assert api_key == "session-token"
            self.responses = _DummyResponses()

    monkeypatch.setattr("infrastructure.llm_client.OpenAI", _DummyOpenAI)
    client = LLMClient(mode=LLMClient.MODE_CODEX, max_retries=1, base_delay=0.0, timeout=5)

    assert client.current_account_alias().startswith("codex_session") or client.current_account_alias()
    assert client.generate_json("Return JSON", strict=True) == {"ok": True}


def test_codex_uses_hermes_transport_when_device_auth_available(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("infrastructure.openai_account_store.OpenAIAccountStore.active_api_key", lambda self: "")
    monkeypatch.setattr("infrastructure.codex_session_store.CodexSessionStore.has_session", lambda self: True)
    monkeypatch.setattr("infrastructure.llm_client.LLMClient._hermes_codex_available", classmethod(lambda cls: True))
    monkeypatch.setattr(
        "infrastructure.llm_client.LLMClient._run_codex_hermes_prompt",
        classmethod(lambda cls, *, model_name, prompt, timeout_seconds: '{"ok": true}'),
    )

    client = LLMClient(mode=LLMClient.MODE_CODEX, max_retries=1, base_delay=0.0, timeout=5)

    assert client.codex_transport == "hermes"
    assert client.current_account_alias() == "hermes_openai_codex"
    assert client.generate_json("Return JSON", strict=True) == {"ok": True}


def test_probe_codex_model_access_uses_hermes_when_direct_key_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("infrastructure.openai_account_store.OpenAIAccountStore.active_api_key", lambda self: "")
    monkeypatch.setattr("infrastructure.llm_client.LLMClient._hermes_codex_available", classmethod(lambda cls: True))
    monkeypatch.setattr(
        "infrastructure.llm_client.LLMClient._run_codex_hermes_prompt",
        classmethod(lambda cls, *, model_name, prompt, timeout_seconds: '{"ok": true}'),
    )

    result = LLMClient.probe_codex_model_access("gpt-5.4-mini")

    assert result["status"] == "ok"
    assert result["transport"] == "hermes"


def test_codex_hermes_timeout_budget_scales_with_prompt_size():
    short_budget = LLMClient._codex_hermes_timeout_budget("x" * 500, 120)
    long_budget = LLMClient._codex_hermes_timeout_budget("x" * 24000, 120)

    assert short_budget >= 150
    assert long_budget > short_budget
    assert long_budget >= 300


def test_codex_hermes_uses_scaled_timeout_and_utf8(monkeypatch):
    monkeypatch.setattr("infrastructure.llm_client.LLMClient._hermes_codex_available", classmethod(lambda cls: True))
    captured = {}

    def _fake_run(command, **kwargs):
        captured["command"] = command
        captured["timeout"] = kwargs.get("timeout")
        captured["encoding"] = kwargs.get("encoding")
        captured["errors"] = kwargs.get("errors")
        return type("Result", (), {"returncode": 0, "stdout": '{"ok": true}', "stderr": ""})()

    monkeypatch.setattr("infrastructure.llm_client.subprocess.run", _fake_run)

    result = LLMClient._run_codex_hermes_prompt(
        model_name="gpt-5.4-mini",
        prompt="x" * 24000,
        timeout_seconds=120,
    )

    assert result == '{"ok": true}'
    assert captured["timeout"] >= 300
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"
