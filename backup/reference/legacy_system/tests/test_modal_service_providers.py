from __future__ import annotations

from integrations.comfyui.provider import ModalComfyUIRenderProvider
from integrations.kokoro_tts.provider import ModalKokoroTTSProvider, build_modal_kokoro_provider
from integrations.xcore_litbank.provider import ModalXCoreLitbankProvider


class _FakeComfyPool:
    def ensure_live(self):
        return {"api_url": "https://comfy.example/api", "token_name": "member-01"}

    def render(self, **kwargs):
        return {"image_bytes": b"png", "params": kwargs}


class _FakeTtsPool:
    def ensure_live(self):
        return {"api_url": "https://tts.example/api", "token_name": "member-01"}

    def get_live_endpoints(self, *, max_endpoints=None):
        return [{"api_url": "https://tts.example/api", "token_name": "member-01", "limit": max_endpoints}]

    def synthesize_via_endpoint(self, endpoint, **kwargs):
        return {"audio_bytes": b"wav", "endpoint": endpoint, "kwargs": kwargs}

    def synthesize(self, **kwargs):
        return {"audio_bytes": b"wav", "kwargs": kwargs}


class _FakeXCorePool:
    def ensure_live(self):
        return {"api_url": "https://xcore.example/api", "token_name": "member-01"}

    def analyze(self, **kwargs):
        return {"system": "xcore_litbank", "kwargs": kwargs}


def test_comfy_provider_wraps_pool_manager():
    provider = ModalComfyUIRenderProvider(pool_manager=_FakeComfyPool())
    assert provider.ensure_live()["api_url"] == "https://comfy.example/api"
    assert provider.render_image(prompt="hero")["params"]["prompt"] == "hero"


def test_tts_provider_wraps_pool_manager():
    provider = ModalKokoroTTSProvider(pool_manager=_FakeTtsPool())
    assert provider.ensure_live()["api_url"] == "https://tts.example/api"
    assert provider.list_live_endpoints(max_endpoints=2)[0]["limit"] == 2
    assert provider.synthesize_speech(text="hello")["kwargs"]["text"] == "hello"
    assert provider.synthesize_speech_via_endpoint({"token_name": "member-01"}, text="hello")["kwargs"]["text"] == "hello"


def test_build_modal_kokoro_provider_returns_provider_instance():
    provider = build_modal_kokoro_provider(app_name="saga-tts-runtime", tokens=[])
    assert isinstance(provider, ModalKokoroTTSProvider)


def test_xcore_provider_wraps_pool_manager():
    provider = ModalXCoreLitbankProvider(pool_manager=_FakeXCorePool())
    assert provider.ensure_live()["api_url"] == "https://xcore.example/api"
    assert provider.analyze_coref(text="hello")["kwargs"]["text"] == "hello"
