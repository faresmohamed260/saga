from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from saga.providers.inference_registry import (
    COREF_CAPABILITY,
    IMAGE_CAPABILITY,
    SPEECH_CAPABILITY,
    read_inference_selection,
)
from saga.providers.status.shared import MODAL_POOL_PROVIDER
from saga.storage.persistence import SagaSQLiteStore


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _provider_status_map(store: SagaSQLiteStore) -> dict[str, Any]:
    return {
        "ollama": {"statuses": store.get_provider_statuses("ollama")},
        "general_compute": {"statuses": store.get_provider_statuses("general_compute")},
        "codex": {"statuses": store.get_provider_statuses("codex")},
        MODAL_POOL_PROVIDER: {"statuses": store.get_provider_statuses(MODAL_POOL_PROVIDER)},
    }


def read_latest_provider_status_payload(*, store: SagaSQLiteStore | None = None) -> dict[str, Any]:
    sqlite_store = store or SagaSQLiteStore()
    return {
        "providers": _provider_status_map(sqlite_store),
        "refreshed_at": _utc_now_iso(),
    }


def read_latest_inference_status_payload(*, store: SagaSQLiteStore | None = None) -> dict[str, Any]:
    sqlite_store = store or SagaSQLiteStore()
    return {
        "providers": _provider_status_map(sqlite_store),
        "selections": {
            SPEECH_CAPABILITY: read_inference_selection(SPEECH_CAPABILITY, store=sqlite_store),
            IMAGE_CAPABILITY: read_inference_selection(IMAGE_CAPABILITY, store=sqlite_store),
            COREF_CAPABILITY: read_inference_selection(COREF_CAPABILITY, store=sqlite_store),
        },
        "refreshed_at": _utc_now_iso(),
    }


def refresh_latest_provider_statuses(*, store: SagaSQLiteStore | None = None) -> dict[str, Any]:
    return read_latest_inference_status_payload(store=store)
