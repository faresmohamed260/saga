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
