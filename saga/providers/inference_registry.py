from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from saga.providers.status.shared import MODAL_POOL_PROVIDER
from saga.storage.persistence import SagaSQLiteStore


SPEECH_CAPABILITY = "speech"
IMAGE_CAPABILITY = "image"
COREF_CAPABILITY = "coref"

MODAL_KOKORO_PROVIDER = "modal_kokoro"
MODAL_COMFYUI_PROVIDER = "modal_comfyui"
MODAL_XCORE_PROVIDER = "modal_xcore"


def _base_payload(provider_name: str, stored: dict[str, Any] | None) -> dict[str, Any]:
    payload = stored if isinstance(stored, dict) else {}
    return {
        "provider_name": str(payload.get("provider_name") or provider_name).strip().lower(),
        "app_name": str(payload.get("app_name") or "").strip(),
        "api_url": str(payload.get("api_url") or "").strip(),
        "health_url": str(payload.get("health_url") or "").strip(),
        "ui_url": str(payload.get("ui_url") or "").strip(),
        "request_timeout_seconds": int(payload.get("request_timeout_seconds", payload.get("timeout_seconds", 300)) or 300),
        "default_voice": str(payload.get("default_voice") or "af_bella").strip(),
        "default_lang_code": str(payload.get("default_lang_code") or "a").strip(),
        "default_sample_rate": int(payload.get("default_sample_rate", 24000) or 24000),
        "default_audio_format": str(payload.get("default_audio_format") or "wav").strip().lower(),
        "default_normalize_audio": bool(payload.get("default_normalize_audio", True)),
        "default_trim_silence": bool(payload.get("default_trim_silence", False)),
        "default_sentence_pause_ms": int(payload.get("default_sentence_pause_ms", 0) or 0),
        "model_name": str(payload.get("model_name") or "").strip(),
        "accounts": list(payload.get("accounts") or []),
        "metadata": dict(payload.get("metadata") or {}) if isinstance(payload.get("metadata"), dict) else {},
        "capability": capability_for_provider(provider_name),
        "transport": str(payload.get("transport") or "modal_api").strip() or "modal_api",
    }


def capability_for_provider(provider_name: str) -> str:
    provider_key = str(provider_name or "").strip().lower()
    if provider_key == MODAL_KOKORO_PROVIDER:
        return SPEECH_CAPABILITY
    if provider_key == MODAL_COMFYUI_PROVIDER:
        return IMAGE_CAPABILITY
    if provider_key == MODAL_XCORE_PROVIDER:
        return COREF_CAPABILITY
    return ""


def provider_capability(provider_name: str) -> str:
    return capability_for_provider(provider_name)


def read_inference_provider_config(
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
        for key in ("token_secret",):
            if masked.get(key):
                masked[key] = "***"
        masked_accounts.append(masked)
    payload["accounts"] = masked_accounts
    return payload


def save_inference_provider_config(
    provider_name: str,
    payload: dict[str, Any],
    *,
    store: SagaSQLiteStore | None = None,
) -> dict[str, Any]:
    provider_key = str(provider_name or "").strip().lower()
    sqlite_store = store or SagaSQLiteStore()
    normalized = _base_payload(provider_key, payload)
    sqlite_store.upsert_provider_config(provider_key, normalized)
    return read_inference_provider_config(provider_key, store=sqlite_store, mask=True)


def read_inference_selection(capability: str, *, store: SagaSQLiteStore | None = None) -> dict[str, Any]:
    sqlite_store = store or SagaSQLiteStore()
    provider_name = active_provider_name_for_capability(capability, store=sqlite_store)
    return {
        "capability": str(capability or "").strip().lower(),
        "provider_name": provider_name,
    }


def save_inference_selection(capability: str, provider_name: str, *, store: SagaSQLiteStore | None = None) -> dict[str, Any]:
    sqlite_store = store or SagaSQLiteStore()
    capability_key = str(capability or "").strip().lower()
    selection_provider = str(provider_name or "").strip().lower()
    selection_key = f"inference_selection:{capability_key}"
    sqlite_store.upsert_provider_config(
        selection_key,
        {
            "provider_name": selection_key,
            "metadata": {
                "capability": capability_key,
                "selected_provider_name": selection_provider,
            },
        },
    )
    return read_inference_selection(capability_key, store=sqlite_store)


def active_provider_name_for_capability(capability: str, *, store: SagaSQLiteStore | None = None) -> str:
    sqlite_store = store or SagaSQLiteStore()
    capability_key = str(capability or "").strip().lower()
    selection_key = f"inference_selection:{capability_key}"
    stored = sqlite_store.get_provider_config(selection_key) or {}
    metadata = stored.get("metadata") if isinstance(stored.get("metadata"), dict) else {}
    selected = str(metadata.get("selected_provider_name") or "").strip().lower()
    if selected:
        return selected
    if capability_key == SPEECH_CAPABILITY:
        return MODAL_KOKORO_PROVIDER
    if capability_key == IMAGE_CAPABILITY:
        return MODAL_COMFYUI_PROVIDER
    if capability_key == COREF_CAPABILITY:
        return MODAL_XCORE_PROVIDER
    return ""


@dataclass
class ResolvedInferenceProvider:
    provider_name: str
    payload: dict[str, Any]

    def ensure_live(self) -> dict[str, Any]:
        api_url = str(self.payload.get("api_url") or "").strip()
        app_name = str(self.payload.get("app_name") or "").strip()
        accounts = list(self.payload.get("accounts") or [])
        token_name = str((accounts[0] or {}).get("label") or "").strip() if accounts else ""
        return {
            "provider_name": self.provider_name,
            "api_url": api_url,
            "app_name": app_name,
            "token_name": token_name,
            "health_url": str(self.payload.get("health_url") or "").strip(),
            "ui_url": str(self.payload.get("ui_url") or "").strip(),
            "pool_provider_name": MODAL_POOL_PROVIDER,
        }


def resolve_provider(provider_name: str, *, store: SagaSQLiteStore | None = None) -> ResolvedInferenceProvider:
    sqlite_store = store or SagaSQLiteStore()
    payload = read_inference_provider_config(provider_name, store=sqlite_store, mask=False)
    return ResolvedInferenceProvider(provider_name=str(provider_name or "").strip().lower(), payload=payload)
