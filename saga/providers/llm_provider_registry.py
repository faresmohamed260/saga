from __future__ import annotations

from typing import Any

from saga.storage.persistence import SagaSQLiteStore


OLLAMA_PROVIDER = "ollama"
GENERAL_COMPUTE_PROVIDER = "general_compute"


def _base_payload(provider_name: str, stored: dict[str, Any] | None) -> dict[str, Any]:
    payload = stored if isinstance(stored, dict) else {}
    return {
        "provider_name": str(payload.get("provider_name") or provider_name).strip().lower(),
        "active_index": int(payload.get("active_index", 0) or 0),
        "accounts": list(payload.get("accounts") or []),
        "metadata": dict(payload.get("metadata") or {}) if isinstance(payload.get("metadata"), dict) else {},
    }


def read_llm_provider_config(
    provider_name: str,
    *,
    store: SagaSQLiteStore | None = None,
    mask: bool = True,
) -> dict[str, Any]:
    provider_key = str(provider_name or "").strip().lower()
    sqlite_store = store or SagaSQLiteStore()
    payload = _base_payload(provider_key, sqlite_store.get_provider_config(provider_key))
    if not mask:
        return payload

    masked_accounts: list[dict[str, Any]] = []
    for item in payload["accounts"]:
        if not isinstance(item, dict):
            continue
        masked = dict(item)
        for key in ("api_key", "password"):
            if masked.get(key):
                masked[key] = "***"
        masked_accounts.append(masked)
    payload["accounts"] = masked_accounts
    return payload


def save_llm_provider_config(
    provider_name: str,
    payload: dict[str, Any],
    *,
    store: SagaSQLiteStore | None = None,
) -> dict[str, Any]:
    provider_key = str(provider_name or "").strip().lower()
    sqlite_store = store or SagaSQLiteStore()
    normalized = _base_payload(provider_key, payload)
    sqlite_store.upsert_provider_config(provider_key, normalized)
    return read_llm_provider_config(provider_key, store=sqlite_store, mask=True)
