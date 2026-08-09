from __future__ import annotations

from types import SimpleNamespace

from packages.identity_runtime import client as identity_client_module
from packages.identity_runtime.client import IdentityRuntimeClient, IdentityRuntimeConfig, IdentityRuntimeProfile


class _StubPool:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = []

    def analyze(self, **kwargs):
        self.calls.append(dict(kwargs))
        return dict(self.payload)


def test_identity_runtime_unwraps_modal_execution_envelope(monkeypatch):
    monkeypatch.setattr(identity_client_module, "load_modal_provider_secret_config", lambda provider_name: SimpleNamespace(app_name="saga-coref-runtime"))
    monkeypatch.setattr(identity_client_module, "load_tokens", lambda: [{"name": "member-01"}])
    profile = IdentityRuntimeProfile(name="identity-runtime-test")
    client = IdentityRuntimeClient(profile=profile, config=IdentityRuntimeConfig(profile=profile))
    client._pool = _StubPool(
        {
            "token_name": "member-01",
            "app_name": "saga-coref-runtime",
            "response": {
                "app_name": "saga-coref-runtime",
                "model_name": "sapienzanlp/xcore-litbank",
                "runtime_seconds": 0.82,
                "chunk_count": 1,
                "input_stats": {"chapter_count": 1},
                "clusters": [
                    {
                        "cluster_id": 1,
                        "display_name": "Kareem",
                        "aliases": [],
                        "mentions": ["Kareem"],
                        "mention_count": 1,
                        "proper_mentions": ["Kareem"],
                        "pronoun_mentions": [],
                    }
                ],
            },
            "metadata": {"status": "ok"},
        }
    )

    result = client.analyze_chapters(
        chapters=[{"book_index": 1, "chapter_index": 1, "chapter_title": "Chapter 1", "content": "Kareem replied."}],
        use_chunking=False,
    )

    assert result.app_name == "saga-coref-runtime"
    assert result.model_name == "sapienzanlp/xcore-litbank"
    assert result.runtime_seconds == 0.82
    assert [row.display_name for row in result.clusters] == ["Kareem"]


def test_identity_runtime_avoids_chunking_for_tiny_single_chapter(monkeypatch):
    monkeypatch.setattr(identity_client_module, "load_modal_provider_secret_config", lambda provider_name: SimpleNamespace(app_name="saga-coref-runtime"))
    monkeypatch.setattr(identity_client_module, "load_tokens", lambda: [{"name": "member-01"}])
    profile = IdentityRuntimeProfile(name="identity-runtime-test")
    client = IdentityRuntimeClient(profile=profile, config=IdentityRuntimeConfig(profile=profile))
    stub = _StubPool({"response": {"clusters": []}})
    client._pool = stub

    client.analyze_chapters(
        chapters=[{"book_index": 1, "chapter_index": 1, "chapter_title": "Chapter 1", "content": "Fares greeted Kareem."}],
        use_chunking=None,
    )

    assert stub.calls
    assert stub.calls[0]["use_chunking"] is False
