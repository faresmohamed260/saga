from saga.providers import llm_provider_smoke


class _FakeOllamaRuntime:
    def __init__(self, *, store=None):
        del store

    def generate_json(self, *, prompt, model_name, timeout_seconds):
        del prompt, model_name, timeout_seconds
        return {"response": '{"ok": true}'}

    def resolve_transport(self):
        return type("Transport", (), {"direct_cloud": False})()


class _FakeGeneralComputeRuntime:
    def __init__(self, *, store=None):
        del store

    def generate_json(self, *, payload, timeout_seconds, estimated_input_tokens, estimated_output_tokens):
        del payload, timeout_seconds, estimated_input_tokens, estimated_output_tokens
        return {"choices": [{"message": {"content": '{"ok": true}'}}]}

    def record_usage(self, payload):
        del payload


def test_run_llm_provider_smoke_writes_ollama_artifacts(monkeypatch, tmp_path):
    monkeypatch.setattr(llm_provider_smoke, "OllamaProviderRuntime", _FakeOllamaRuntime)

    payload = llm_provider_smoke.run_llm_provider_smoke(
        "ollama",
        model_name="gpt-oss:120b-cloud",
        output_root=tmp_path / "smoke",
    )

    assert payload["provider_name"] == "ollama"
    assert "summary_path" in payload


def test_run_llm_provider_smoke_writes_general_compute_artifacts(monkeypatch, tmp_path):
    monkeypatch.setattr(llm_provider_smoke, "GeneralComputeProviderRuntime", _FakeGeneralComputeRuntime)

    payload = llm_provider_smoke.run_llm_provider_smoke(
        "general_compute",
        model_name="deepseek-v3.1",
        output_root=tmp_path / "smoke",
    )

    assert payload["provider_name"] == "general_compute"
    assert "summary_path" in payload
