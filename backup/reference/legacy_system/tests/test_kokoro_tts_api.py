from __future__ import annotations

import numpy as np

from integrations.kokoro_tts.client import ModalKokoroTTSClient
from integrations.kokoro_tts.modal_app import (
    SynthesizeRequest,
    _apply_normalization,
    _apply_trim,
    _encode_audio,
)


class _FakeResponse:
    def __init__(self, *, content: bytes, headers: dict[str, str], status_code: int = 200) -> None:
        self.content = content
        self.headers = headers
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_synthesize_request_defaults():
    payload = SynthesizeRequest(text="Hello world").model_dump()
    assert payload["voice"] == "af_bella"
    assert payload["lang_code"] == "a"
    assert payload["sample_rate"] == 24000
    assert payload["audio_format"] == "flac"
    assert payload["normalize_audio"] is True
    assert payload["trim_silence"] is False
    assert payload["sentence_pause_ms"] == 0


def test_modal_tts_client_posts_default_flac_payload(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse(
            content=b"flac-bytes",
            headers={
                "content-type": "audio/flac",
                "X-Kokoro-Voice": "af_bella",
                "X-Kokoro-Lang-Code": "a",
                "X-Kokoro-Sample-Rate": "24000",
                "X-Kokoro-Audio-Format": "flac",
                "X-Kokoro-Duration-Seconds": "1.25",
            },
        )

    monkeypatch.setattr("integrations.kokoro_tts.client.requests.post", fake_post)
    client = ModalKokoroTTSClient("https://tts.example/api", timeout_seconds=90)

    response = client.synthesize(text="Narrate this scene.")

    assert captured["url"] == "https://tts.example/api"
    assert captured["timeout"] == 90
    assert captured["json"]["voice"] == "af_bella"
    assert captured["json"]["audio_format"] == "flac"
    assert response["media_type"] == "audio/flac"
    assert response["sample_rate"] == 24000
    assert response["duration_seconds"] == 1.25


def test_modal_tts_client_posts_custom_flac_payload(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured["json"] = json
        return _FakeResponse(
            content=b"flac-bytes",
            headers={
                "content-type": "audio/flac",
                "X-Kokoro-Voice": "af_bella",
                "X-Kokoro-Lang-Code": "b",
                "X-Kokoro-Sample-Rate": "32000",
                "X-Kokoro-Audio-Format": "flac",
                "X-Kokoro-Duration-Seconds": "2.5",
            },
        )

    monkeypatch.setattr("integrations.kokoro_tts.client.requests.post", fake_post)
    client = ModalKokoroTTSClient("https://tts.example/api")

    response = client.synthesize(
        text="Narrate an entire chapter.",
        voice="af_bella",
        lang_code="b",
        sample_rate=32000,
        audio_format="flac",
        normalize_audio=False,
        trim_silence=True,
        sentence_pause_ms=200,
    )

    assert captured["json"]["lang_code"] == "b"
    assert captured["json"]["sample_rate"] == 32000
    assert captured["json"]["audio_format"] == "flac"
    assert captured["json"]["normalize_audio"] is False
    assert captured["json"]["trim_silence"] is True
    assert captured["json"]["sentence_pause_ms"] == 200
    assert response["media_type"] == "audio/flac"
    assert response["audio_format"] == "flac"


def test_normalization_and_trim_helpers():
    audio = np.array([0.0, 0.0, 0.2, -0.5, 0.0], dtype=np.float32)
    trimmed = _apply_trim(audio, threshold=0.05)
    assert trimmed.tolist() == [0.20000000298023224, -0.5]

    normalized = _apply_normalization(trimmed)
    assert np.max(np.abs(normalized)) <= 0.97 + 1e-6
    assert normalized.dtype == np.float32


def test_encode_audio_supports_wav_and_flac():
    audio = np.array([0.0, 0.1, -0.1, 0.0], dtype=np.float32)

    wav_bytes, wav_type = _encode_audio(audio, sample_rate=24000, audio_format="wav")
    flac_bytes, flac_type = _encode_audio(audio, sample_rate=24000, audio_format="flac")

    assert wav_type == "audio/wav"
    assert flac_type == "audio/flac"
    assert len(wav_bytes) > 0
    assert len(flac_bytes) > 0
