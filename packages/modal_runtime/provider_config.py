from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, Field, field_validator

from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client


class ModalAccountSecret(BaseModel):
    label: str = Field(min_length=1)
    token_id: str = ""
    token_secret: str = ""
    app_name_override: str = ""

    @field_validator("label", "token_id", "token_secret", "app_name_override", mode="before")
    @classmethod
    def _coerce_string(cls, value: Any) -> str:
        return str(value or "").strip()


class ModalProviderSecretConfig(BaseModel):
    provider_name: str = Field(min_length=1)
    app_name: str = ""
    api_url: str = ""
    health_url: str = ""
    ui_url: str = ""
    hf_token: str = ""
    request_timeout_seconds: int = 600
    accounts: list[ModalAccountSecret] = Field(default_factory=list)

    @field_validator("provider_name", "app_name", "api_url", "health_url", "ui_url", "hf_token", mode="before")
    @classmethod
    def _coerce_provider_strings(cls, value: Any) -> str:
        return str(value or "").strip()


def load_modal_provider_secret_config(provider_name: str) -> ModalProviderSecretConfig:
    client = _persistence_client()
    row = client.provider_configs.get_provider_config(provider_name)
    payload = dict((row or {}).get("payload") or {})
    accounts: list[ModalAccountSecret] = []
    for item in payload.get("accounts") or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("name") or "").strip()
        if not label:
            continue
        accounts.append(
            ModalAccountSecret(
                label=label,
                token_id=str(item.get("token_id") or "").strip(),
                token_secret=str(item.get("token_secret") or "").strip(),
                app_name_override=str(item.get("app_name_override") or "").strip(),
            )
        )
    return ModalProviderSecretConfig(
        provider_name=provider_name,
        app_name=str(payload.get("app_name") or "").strip(),
        api_url=str(payload.get("api_url") or "").strip(),
        health_url=str(payload.get("health_url") or "").strip(),
        ui_url=str(payload.get("ui_url") or "").strip(),
        hf_token=str(payload.get("hf_token") or "").strip(),
        request_timeout_seconds=max(30, int(payload.get("request_timeout_seconds") or 600)),
        accounts=accounts,
    )


def save_modal_provider_secret_config(provider_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized_provider = str(provider_name or "").strip()
    if not normalized_provider:
        raise ValueError("provider_name is required.")
    client = _persistence_client()
    existing = load_modal_provider_secret_config(normalized_provider)
    merged_accounts: list[ModalAccountSecret]
    if "accounts" not in payload:
        merged_accounts = list(existing.accounts)
    else:
        raw_accounts = list(payload.get("accounts") or [])
        merged_accounts = []
        existing_by_label = {item.label: item for item in existing.accounts}
        for index, item in enumerate(raw_accounts, start=1):
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "").strip()
            if not label:
                label = f"member-{index:02d}"
            existing_account = existing_by_label.get(label)
            token_id = str(item.get("token_id") or "").strip() or (existing_account.token_id if existing_account else "")
            token_secret = str(item.get("token_secret") or "").strip() or (existing_account.token_secret if existing_account else "")
            merged_accounts.append(
                ModalAccountSecret(
                    label=label,
                    token_id=token_id,
                    token_secret=token_secret,
                    app_name_override=str(item.get("app_name_override") or "").strip() or (existing_account.app_name_override if existing_account else ""),
                )
            )
    normalized = ModalProviderSecretConfig(
        provider_name=normalized_provider,
        app_name=str(payload.get("app_name") or "").strip() or existing.app_name,
        api_url=str(payload.get("api_url") or "").strip() or existing.api_url,
        health_url=str(payload.get("health_url") or "").strip() or existing.health_url,
        ui_url=str(payload.get("ui_url") or "").strip() or existing.ui_url,
        hf_token=str(payload.get("hf_token") or "").strip() or existing.hf_token,
        request_timeout_seconds=max(30, int(payload.get("request_timeout_seconds") or existing.request_timeout_seconds or 600)),
        accounts=merged_accounts,
    )
    client.provider_configs.upsert_provider_config(
        normalized_provider,
        {
            "app_name": normalized.app_name,
            "api_url": normalized.api_url,
            "health_url": normalized.health_url,
            "ui_url": normalized.ui_url,
            "hf_token": normalized.hf_token,
            "request_timeout_seconds": normalized.request_timeout_seconds,
            "accounts": [account.model_dump() for account in normalized.accounts],
        },
    )
    return summarize_modal_provider_secret_config(normalized)


def summarize_modal_provider_secret_config(config: ModalProviderSecretConfig) -> dict[str, Any]:
    return {
        "provider_name": config.provider_name,
        "app_name": config.app_name,
        "api_url": config.api_url,
        "health_url": config.health_url,
        "ui_url": config.ui_url,
        "request_timeout_seconds": config.request_timeout_seconds,
        "has_hf_token": bool(config.hf_token),
        "accounts": [
            {
                "label": account.label,
                "app_name_override": account.app_name_override,
                "has_token_id": bool(account.token_id),
                "has_token_secret": bool(account.token_secret),
            }
            for account in config.accounts
        ],
    }


def load_modal_account_secrets(provider_name: str) -> list[dict[str, str]]:
    config = load_modal_provider_secret_config(provider_name)
    results: list[dict[str, str]] = []
    for account in config.accounts:
        if not account.token_id or not account.token_secret:
            continue
        results.append(
            {
                "label": account.label,
                "token_id": account.token_id,
                "token_secret": account.token_secret,
                "app_name_override": account.app_name_override,
            }
        )
    return results


def load_modal_hf_token(provider_name: str) -> str:
    return load_modal_provider_secret_config(provider_name).hf_token


def clear_modal_provider_config_cache() -> None:
    _persistence_client.cache_clear()


@lru_cache(maxsize=1)
def _persistence_client():
    database_url = str(os.getenv("SAGA_MODAL_STATE_DB_URL") or os.getenv("SAGA_RUNTIME_DB_URL") or "").strip()
    database_mode = (
        str(os.getenv("SAGA_MODAL_STATE_DB_MODE") or os.getenv("SAGA_RUNTIME_DB_MODE") or "supabase_postgres").strip()
        or "supabase_postgres"
    )
    local_storage_root_dir = str(os.getenv("SAGA_RUNTIME_LOCAL_STORAGE_ROOT") or "").strip() or "analysis_outputs/unified_storage"
    supabase_api_url = str(
        os.getenv("SAGA_SUPABASE_STORAGE_API_URL")
        or os.getenv("SUPABASE_STORAGE_API_URL")
        or os.getenv("SAGA_SUPABASE_API_URL")
        or os.getenv("SUPABASE_API_URL")
        or os.getenv("SAGA_SUPABASE_URL")
        or os.getenv("SUPABASE_URL")
        or ""
    ).strip()
    supabase_service_role_key = str(
        os.getenv("SAGA_SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or ""
    ).strip()
    profile = PersistenceProfile(
        name="modal-provider-config",
        provider="supabase",
        mode=database_mode,
        database_url=database_url,
        application_name="saga-modal-provider-config",
        local_storage_root_dir=local_storage_root_dir,
    )
    client = create_persistence_client(
        config=PersistenceRuntimeConfig(
            profile=profile,
            supabase_api_url=supabase_api_url,
            supabase_service_role_key=supabase_service_role_key,
        ),
        profile=profile,
    )
    client.initialize()
    return client
