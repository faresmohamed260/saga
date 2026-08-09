from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from saga.persistence.provider_config_store import ProviderConfigStore
from saga.providers.inference_registry import (
    COREF_CAPABILITY,
    IMAGE_CAPABILITY,
    SPEECH_CAPABILITY,
    read_inference_selection,
)
from saga.providers.status.shared import MODAL_POOL_PROVIDER
from saga.storage.persistence import SagaRelationalStore


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _provider_status_map(store: ProviderConfigStore) -> dict[str, Any]:
    return {
        "ollama": {"statuses": store.get_provider_statuses("ollama")},
        "general_compute": {"statuses": store.get_provider_statuses("general_compute")},
        "codex": {"statuses": store.get_provider_statuses("codex")},
        MODAL_POOL_PROVIDER: {"statuses": store.get_provider_statuses(MODAL_POOL_PROVIDER)},
    }


def read_latest_provider_status_payload(*, store: SagaRelationalStore | ProviderConfigStore | None = None) -> dict[str, Any]:
    provider_store = _provider_store(store)
    return {
        "providers": _provider_status_map(provider_store),
        "refreshed_at": _utc_now_iso(),
    }


def read_latest_inference_status_payload(*, store: SagaRelationalStore | ProviderConfigStore | None = None) -> dict[str, Any]:
    provider_store = _provider_store(store)
    return {
        "providers": _provider_status_map(provider_store),
        "selections": {
            SPEECH_CAPABILITY: read_inference_selection(SPEECH_CAPABILITY, store=provider_store),
            IMAGE_CAPABILITY: read_inference_selection(IMAGE_CAPABILITY, store=provider_store),
            COREF_CAPABILITY: read_inference_selection(COREF_CAPABILITY, store=provider_store),
        },
        "refreshed_at": _utc_now_iso(),
    }


def refresh_latest_provider_statuses(*, store: SagaRelationalStore | ProviderConfigStore | None = None) -> dict[str, Any]:
    return read_latest_inference_status_payload(store=store)


def _provider_store(store: SagaRelationalStore | ProviderConfigStore | None) -> ProviderConfigStore:
    if isinstance(store, ProviderConfigStore):
        return store
    return ProviderConfigStore(store or SagaRelationalStore())
