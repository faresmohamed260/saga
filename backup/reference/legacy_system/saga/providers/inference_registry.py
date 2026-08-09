from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from saga.persistence.provider_config_store import ProviderConfigStore
from saga.providers.status.shared import MODAL_POOL_PROVIDER
from saga.storage.persistence import SagaRelationalStore


SPEECH_CAPABILITY = "speech"
IMAGE_CAPABILITY = "image"
COREF_CAPABILITY = "coref"

MODAL_KOKORO_PROVIDER = "modal_kokoro"
MODAL_COMFYUI_PROVIDER = "modal_comfyui"
MODAL_XCORE_PROVIDER = "modal_xcore"


def _base_payload(provider_name: str, stored: dict[str, Any] | None) -> dict[str, Any]:
    payload = stored if isinstance(stored, dict) else {}
    normalized_accounts = [_normalized_modal_account_payload(item, fallback_index=index) for index, item in enumerate(payload.get("accounts") or []) if isinstance(item, dict)]
    hf_token = _coalesce_secret(str(payload.get("hf_token") or "").strip(), "")
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
        "accounts": normalized_accounts,
        "hf_token": hf_token,
        "has_hf_token": bool(hf_token),
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
    store: SagaRelationalStore | ProviderConfigStore | None = None,
    mask: bool = True,
) -> dict[str, Any]:
    provider_key = str(provider_name or "").strip().lower()
    provider_store = _provider_store(store)
    payload = _base_payload(provider_key, provider_store.get_provider_config(provider_key))
    if not mask:
        return payload

    masked_accounts: list[dict[str, Any]] = []
    for item in payload["accounts"]:
        if not isinstance(item, dict):
            continue
        masked = dict(item)
        if masked.get("token_secret"):
            masked["token_secret"] = ""
        masked_accounts.append(masked)
    payload["accounts"] = masked_accounts
    if payload.get("hf_token"):
        payload["hf_token"] = _mask_hf_token(str(payload.get("hf_token") or ""))
    return payload


def save_inference_provider_config(
    provider_name: str,
    payload: dict[str, Any],
    *,
    store: SagaRelationalStore | ProviderConfigStore | None = None,
) -> dict[str, Any]:
    provider_key = str(provider_name or "").strip().lower()
    provider_store = _provider_store(store)
    existing = provider_store.get_provider_config(provider_key) or {}
    normalized = _normalized_provider_payload(provider_key, payload, existing=existing)
    provider_store.upsert_provider_config(provider_key, normalized)
    return read_inference_provider_config(provider_key, store=provider_store, mask=True)


def read_inference_selection(capability: str, *, store: SagaRelationalStore | ProviderConfigStore | None = None) -> dict[str, Any]:
    provider_store = _provider_store(store)
    provider_name = active_provider_name_for_capability(capability, store=provider_store)
    return {
        "capability": str(capability or "").strip().lower(),
        "provider_name": provider_name,
        "active_provider": provider_name,
    }


def save_inference_selection(
    capability: str,
    provider_name: str,
    *,
    store: SagaRelationalStore | ProviderConfigStore | None = None,
) -> dict[str, Any]:
    provider_store = _provider_store(store)
    capability_key = str(capability or "").strip().lower()
    selection_provider = str(provider_name or "").strip().lower()
    selection_key = f"inference_selection:{capability_key}"
    provider_store.upsert_provider_config(
        selection_key,
        {
            "provider_name": selection_key,
            "metadata": {
                "capability": capability_key,
                "selected_provider_name": selection_provider,
            },
        },
    )
    return read_inference_selection(capability_key, store=provider_store)


def active_provider_name_for_capability(
    capability: str,
    *,
    store: SagaRelationalStore | ProviderConfigStore | None = None,
) -> str:
    provider_store = _provider_store(store)
    capability_key = str(capability or "").strip().lower()
    selection_key = f"inference_selection:{capability_key}"
    stored = provider_store.get_provider_config(selection_key) or {}
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


def resolve_provider(
    provider_name: str,
    *,
    store: SagaRelationalStore | ProviderConfigStore | None = None,
) -> ResolvedInferenceProvider:
    provider_store = _provider_store(store)
    payload = read_inference_provider_config(provider_name, store=provider_store, mask=False)
    return ResolvedInferenceProvider(provider_name=str(provider_name or "").strip().lower(), payload=payload)


def _provider_store(store: SagaRelationalStore | ProviderConfigStore | None) -> ProviderConfigStore:
    if isinstance(store, ProviderConfigStore):
        return store
    return ProviderConfigStore(store or SagaRelationalStore())


def _normalized_provider_payload(provider_name: str, payload: dict[str, Any], *, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    provider_key = str(provider_name or "").strip().lower()
    current = existing if isinstance(existing, dict) else {}
    current_accounts = [item for item in (current.get("accounts") or []) if isinstance(item, dict)]
    incoming_accounts = [item for item in (payload.get("accounts") or []) if isinstance(item, dict)]
    existing_by_label = {
        str(item.get("label") or f"account-{index + 1}").strip(): item
        for index, item in enumerate(current_accounts)
    }
    normalized_accounts: list[dict[str, Any]] = []
    for index, item in enumerate(incoming_accounts):
        label = str(item.get("label") or f"member-{index + 1:02d}").strip()
        prior = existing_by_label.get(label, {})
        token_id = _coalesce_secret(str(item.get("token_id") or "").strip(), str(prior.get("api_key") or "").strip())
        token_secret = _coalesce_secret(str(item.get("token_secret") or "").strip(), str(prior.get("password") or "").strip())
        normalized_accounts.append(
            {
                "label": label,
                "index": index,
                "active": bool(item.get("active", index == int(payload.get("active_index", current.get("active_index", 0)) or 0))),
                "api_key": token_id,
                "password": token_secret,
                "email": str(item.get("email") or prior.get("email") or "").strip(),
                "auth_mode": str(item.get("auth_mode") or prior.get("auth_mode") or "").strip(),
                "account_id": str(item.get("account_id") or prior.get("account_id") or "").strip(),
                "app_name_override": str(item.get("app_name_override") or ((prior.get("metadata") or {}).get("app_name_override") if isinstance(prior.get("metadata"), dict) else "") or "").strip(),
                "metadata": {
                    **(dict(prior.get("metadata") or {}) if isinstance(prior.get("metadata"), dict) else {}),
                    **(dict(item.get("metadata") or {}) if isinstance(item.get("metadata"), dict) else {}),
                },
            }
        )
    if not normalized_accounts and current_accounts:
        normalized_accounts = current_accounts

    incoming_hf_token = str(payload.get("hf_token") or "").strip()
    existing_hf_token = str(current.get("hf_token") or "").strip()
    normalized_hf_token = _coalesce_secret(incoming_hf_token, existing_hf_token)
    return {
        **_base_payload(provider_key, current),
        "provider_name": provider_key,
        "app_name": str(payload.get("app_name") or current.get("app_name") or "").strip(),
        "api_url": str(payload.get("api_url") or current.get("api_url") or "").strip(),
        "health_url": str(payload.get("health_url") or current.get("health_url") or "").strip(),
        "ui_url": str(payload.get("ui_url") or current.get("ui_url") or "").strip(),
        "request_timeout_seconds": int(payload.get("request_timeout_seconds", current.get("request_timeout_seconds", 300)) or 300),
        "default_voice": str(payload.get("default_voice") or current.get("default_voice") or "af_bella").strip(),
        "default_lang_code": str(payload.get("default_lang_code") or current.get("default_lang_code") or "a").strip(),
        "default_sample_rate": int(payload.get("default_sample_rate", current.get("default_sample_rate", 24000)) or 24000),
        "default_audio_format": str(payload.get("default_audio_format") or current.get("default_audio_format") or "wav").strip().lower(),
        "default_normalize_audio": bool(payload.get("default_normalize_audio", current.get("default_normalize_audio", True))),
        "default_trim_silence": bool(payload.get("default_trim_silence", current.get("default_trim_silence", False))),
        "default_sentence_pause_ms": int(payload.get("default_sentence_pause_ms", current.get("default_sentence_pause_ms", 0)) or 0),
        "model_name": str(payload.get("model_name") or current.get("model_name") or "").strip(),
        "active_index": int(payload.get("active_index", current.get("active_index", 0)) or 0),
        "accounts": normalized_accounts,
        "hf_token": normalized_hf_token,
        "has_hf_token": bool(normalized_hf_token),
        "metadata": {
            **(dict(current.get("metadata") or {}) if isinstance(current.get("metadata"), dict) else {}),
            **(dict(payload.get("metadata") or {}) if isinstance(payload.get("metadata"), dict) else {}),
        },
        "capability": capability_for_provider(provider_key),
        "transport": str(payload.get("transport") or current.get("transport") or "modal_api").strip() or "modal_api",
    }


def _normalized_modal_account_payload(item: dict[str, Any], *, fallback_index: int) -> dict[str, Any]:
    metadata = dict(item.get("metadata") or {}) if isinstance(item.get("metadata"), dict) else {}
    token_id = str(item.get("token_id") or item.get("api_key") or "").strip()
    token_secret = str(item.get("token_secret") or item.get("password") or "").strip()
    app_name_override = str(item.get("app_name_override") or metadata.get("app_name_override") or "").strip()
    return {
        "label": str(item.get("label") or f"member-{fallback_index + 1:02d}").strip(),
        "token_id": token_id,
        "token_secret": token_secret,
        "has_token_id": bool(token_id),
        "has_token_secret": bool(token_secret),
        "app_name_override": app_name_override,
        "active": bool(item.get("active")),
        "index": int(item.get("index", fallback_index) or fallback_index),
        "email": str(item.get("email") or "").strip(),
        "auth_mode": str(item.get("auth_mode") or "").strip(),
        "account_id": str(item.get("account_id") or "").strip(),
        "metadata": metadata,
    }


def modal_tokens_from_provider_payload(payload: dict[str, Any], token_cls) -> list[Any]:
    tokens: list[Any] = []
    for index, item in enumerate(payload.get("accounts") or [], start=1):
        if not isinstance(item, dict):
            continue
        token_id = str(item.get("token_id") or item.get("api_key") or "").strip()
        token_secret = str(item.get("token_secret") or item.get("password") or "").strip()
        if not token_id or not token_secret:
            continue
        kwargs = {
            "name": str(item.get("label") or item.get("name") or f"member-{index:02d}").strip(),
            "token_id": token_id,
            "token_secret": token_secret,
        }
        app_name_override = str(item.get("app_name_override") or "").strip()
        if app_name_override:
            try:
                tokens.append(token_cls(app_name_override=app_name_override, **kwargs))
                continue
            except TypeError:
                pass
        tokens.append(token_cls(**kwargs))
    return tokens


def _mask_hf_token(value: str) -> str:
    token = str(value or "").strip()
    if len(token) <= 4:
        return "*" * len(token)
    return token[:4] + "*" * max(4, len(token) - 4)


def _coalesce_secret(incoming: str, existing: str) -> str:
    value = str(incoming or "").strip()
    if value:
        return value
    return str(existing or "").strip()
