from __future__ import annotations

import json
from pathlib import Path

from saga.providers import inference_smoke
from saga.providers.inference_registry import MODAL_COMFYUI_PROVIDER, MODAL_KOKORO_PROVIDER, MODAL_XCORE_PROVIDER
from saga.storage.persistence import SagaSQLiteStore


class _FakeSpeechProvider:
    def ensure_live(self):
        return {"token_name": "member-01", "api_url": "https://tts.example/api", "health_url": "https://tts.example/health"}

    def synthesize_speech(self, **kwargs):
        return {"audio_bytes": b"flac", "voice": "af_bella", "lang_code": "a", "sample_rate": 24000, "audio_format": "flac"}


class _FakeImageProvider:
    def ensure_live(self):
        return {"token_name": "member-02", "api_url": "https://image.example/api", "health_url": "https://image.example/health"}

    def render_image(self, **kwargs):
        return {"image_bytes": b"png", "workflow_mode": kwargs.get("workflow_mode")}


class _FakeCorefProvider:
    def ensure_live(self):
        return {"token_name": "member-03", "api_url": "https://coref.example/api", "health_url": "https://coref.example/health"}

    def analyze_coref(self, **kwargs):
        return {"system": "xcore_litbank", "clusters": [], "text": kwargs["text"]}


def test_run_provider_smoke_writes_speech_artifacts(monkeypatch, tmp_path):
    store = SagaSQLiteStore(tmp_path / "saga.sqlite")
    monkeypatch.setattr(inference_smoke, "resolve_provider", lambda provider_name=None, store=None: _FakeSpeechProvider())

    payload = inference_smoke.run_provider_smoke(
        capability="speech",
        provider_name=MODAL_KOKORO_PROVIDER,
        store=store,
        output_root=tmp_path / "smoke",
    )

    assert Path(payload["artifacts"]["audio_path"]).exists()
    assert Path(payload["artifacts"]["audio_path"]).suffix == ".flac"
    assert Path(payload["artifacts"]["summary_path"]).exists()


def test_run_provider_smoke_writes_image_artifacts(monkeypatch, tmp_path):
    store = SagaSQLiteStore(tmp_path / "saga.sqlite")
    monkeypatch.setattr(inference_smoke, "resolve_provider", lambda provider_name=None, store=None: _FakeImageProvider())

    payload = inference_smoke.run_provider_smoke(
        capability="image",
        provider_name=MODAL_COMFYUI_PROVIDER,
        store=store,
        output_root=tmp_path / "smoke",
    )

    assert Path(payload["artifacts"]["image_path"]).exists()


def test_run_provider_smoke_writes_manifest_driven_image_artifacts(monkeypatch, tmp_path):
    store = SagaSQLiteStore(tmp_path / "saga.sqlite")
    monkeypatch.setattr(inference_smoke, "resolve_provider", lambda provider_name=None, store=None: _FakeImageProvider())

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "width": 512,
                "height": 512,
                "steps": 4,
                "cfg": 1.0,
                "renders": [
                    {
                        "entity_name": "Harry Potter",
                        "entity_type": "character",
                        "positive_prompt": "character prompt",
                        "negative_prompt": "character negative",
                        "workflow_mode": "character_sheet",
                    },
                    {
                        "entity_name": "Hogwarts",
                        "entity_type": "location",
                        "positive_prompt": "location prompt",
                        "negative_prompt": "location negative",
                        "workflow_mode": "entity_generation",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = inference_smoke.run_provider_smoke(
        capability="image",
        provider_name=MODAL_COMFYUI_PROVIDER,
        store=store,
        output_root=tmp_path / "smoke",
        image_manifest_path=manifest_path,
    )

    renders = payload["artifacts"]["renders"]
    assert len(renders) == 2
    assert Path(renders[0]["image_path"]).exists()
    assert Path(renders[1]["image_path"]).exists()


def test_run_provider_smoke_can_use_deploy_first_image_provider(monkeypatch, tmp_path):
    store = SagaSQLiteStore(tmp_path / "saga.sqlite")
    monkeypatch.setattr(
        inference_smoke,
        "_deploy_modal_comfyui_smoke_provider",
        lambda provider_payload, account_label=None: (
            _FakeImageProvider(),
            {
                "account_label": account_label or "member-01",
                "api_url": "https://image.example/api",
                "health_url": "https://image.example/health",
                "ui_url": "https://image.example/ui",
                "deploy_log": "deployed",
            },
        ),
    )

    payload = inference_smoke.run_provider_smoke(
        capability="image",
        provider_name=MODAL_COMFYUI_PROVIDER,
        store=store,
        output_root=tmp_path / "smoke",
        deploy_first=True,
        account_label="member-09",
    )

    assert payload["deploy"]["account_label"] == "member-09"
    assert Path(payload["artifacts"]["image_path"]).exists()


def test_run_provider_smoke_writes_coref_artifacts(monkeypatch, tmp_path):
    store = SagaSQLiteStore(tmp_path / "saga.sqlite")
    monkeypatch.setattr(inference_smoke, "resolve_provider", lambda provider_name=None, store=None: _FakeCorefProvider())

    payload = inference_smoke.run_provider_smoke(
        capability="coref",
        provider_name=MODAL_XCORE_PROVIDER,
        store=store,
        output_root=tmp_path / "smoke",
    )

    summary = json.loads(Path(payload["artifacts"]["summary_path"]).read_text(encoding="utf-8"))
    assert summary["provider_name"] == MODAL_XCORE_PROVIDER
