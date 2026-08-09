from __future__ import annotations

import json
import requests

from integrations.kokoro_tts.pool_manager import ModalTTSPoolManager
from integrations.kokoro_tts.token_pool import ModalToken


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)
        self.reason = "OK" if status_code < 400 else "ERROR"

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            error = requests.HTTPError(self.text)
            error.response = self  # type: ignore[assignment]
            raise error

    def json(self):
        return self._payload


def test_pool_manager_ensure_live_records_ready_payload(monkeypatch, tmp_path):
    state_path = tmp_path / "state.json"
    tokens = [ModalToken(name="member-01", token_id="id", token_secret="secret")]

    monkeypatch.setattr(
        "integrations.kokoro_tts.pool_manager.ensure_urls",
        lambda token, app_name: type("Urls", (), {"api_url": "https://api.example", "health_url": "https://health.example"})(),
    )
    monkeypatch.setattr(
        ModalTTSPoolManager,
        "_fetch_health",
        lambda self, health_url: {"ready": True, "provider": "kokoro_tts", "app_name": "saga-tts-runtime"},
    )

    manager = ModalTTSPoolManager(tokens=tokens, state_path=state_path)
    payload = manager.ensure_live()

    assert payload["token_name"] == "member-01"
    assert payload["api_url"] == "https://api.example"
    assert payload["live_payload"]["ready"] is True
    stored = json.loads(state_path.read_text(encoding="utf-8"))
    assert stored["active_api_url"] == "https://api.example"
    assert stored["active_token_name"] == "member-01"


def test_pool_manager_rotates_after_credit_failure(monkeypatch, tmp_path):
    state_path = tmp_path / "state.json"
    tokens = [
        ModalToken(name="member-01", token_id="id-1", token_secret="secret-1"),
        ModalToken(name="member-02", token_id="id-2", token_secret="secret-2"),
    ]

    monkeypatch.setattr(
        ModalTTSPoolManager,
        "_resolve_next_live_endpoint",
        lambda self, exclude_token_names=None: (
            None
            if {"member-01", "member-02"}.issubset(set(exclude_token_names or set()))
            else (
                {"token_name": "member-02", "api_url": "https://api-2.example", "health_url": "https://health-2.example", "live_payload": {"ready": True}}
                if "member-01" in set(exclude_token_names or set())
                else {"token_name": "member-01", "api_url": "https://api-1.example", "health_url": "https://health-1.example", "live_payload": {"ready": True}}
            )
        ),
    )

    def fake_synthesize(self, **kwargs):
        if self.api_url.endswith("1.example"):
            response = requests.Response()
            response.status_code = 402
            response._content = b"insufficient credits"
            error = requests.HTTPError("insufficient credits")
            error.response = response
            raise error
        return {
            "audio_bytes": b"ok",
            "media_type": "audio/wav",
            "voice": kwargs.get("voice", "af_bella"),
            "lang_code": kwargs.get("lang_code", "a"),
            "sample_rate": kwargs.get("sample_rate", 24000),
            "audio_format": kwargs.get("audio_format", "wav"),
            "duration_seconds": 1.0,
        }

    monkeypatch.setattr("integrations.kokoro_tts.pool_manager.ModalKokoroTTSClient.synthesize", fake_synthesize)

    manager = ModalTTSPoolManager(tokens=tokens, state_path=state_path)
    payload = manager.synthesize(text="rotation test")

    assert payload["token_name"] == "member-02"
    assert payload["api_url"] == "https://api-2.example"


def test_pool_manager_exhausts_each_live_tts_endpoint_once(monkeypatch, tmp_path):
    state_path = tmp_path / "state.json"
    tokens = [
        ModalToken(name="member-01", token_id="id-1", token_secret="secret-1"),
        ModalToken(name="member-02", token_id="id-2", token_secret="secret-2"),
    ]

    monkeypatch.setattr(
        ModalTTSPoolManager,
        "_resolve_next_live_endpoint",
        lambda self, exclude_token_names=None: (
            None
            if {"member-01", "member-02"}.issubset(set(exclude_token_names or set()))
            else (
                {"token_name": "member-02", "api_url": "https://api-2.example", "health_url": "https://health-2.example", "live_payload": {"ready": True}}
                if "member-01" in set(exclude_token_names or set())
                else {"token_name": "member-01", "api_url": "https://api-1.example", "health_url": "https://health-1.example", "live_payload": {"ready": True}}
            )
        ),
    )

    seen = []

    def fake_synthesize(self, **kwargs):
        seen.append(self.api_url)
        raise requests.RequestException("tts down")

    monkeypatch.setattr("integrations.kokoro_tts.pool_manager.ModalKokoroTTSClient.synthesize", fake_synthesize)

    manager = ModalTTSPoolManager(tokens=tokens, state_path=state_path)

    try:
        manager.synthesize(text="rotation test")
        assert False, "Expected ModalTTSRotationError"
    except Exception as exc:
        assert "pool exhausted" in str(exc).lower()

    assert seen == ["https://api-1.example", "https://api-2.example"]
