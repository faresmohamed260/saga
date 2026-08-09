from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from packages.modal_runtime.models import ModalRuntimeState, ModalTokenStatus
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client


def load_runtime_state(
    state_path: Path | None = None,
    *,
    expected_app_name: str = "",
    expected_generation: int = 0,
    provider_name: str = "",
) -> dict:
    del state_path
    if not str(provider_name or "").strip():
        return _fresh_state(app_name=expected_app_name, runtime_generation=expected_generation)
    state = _load_persisted_runtime_state(provider_name)
    actual_app_name = state.app_name
    actual_generation = int(state.runtime_generation or 0)
    if expected_app_name and actual_app_name and actual_app_name != expected_app_name:
        return _fresh_state(app_name=expected_app_name, runtime_generation=expected_generation)
    if expected_generation and actual_generation and actual_generation != expected_generation:
        return _fresh_state(app_name=expected_app_name or actual_app_name, runtime_generation=expected_generation)
    if expected_app_name:
        state.app_name = str(expected_app_name).strip()
    if expected_generation:
        state.runtime_generation = int(expected_generation)
    return state.to_runtime_payload()


def save_runtime_state(
    payload: dict,
    state_path: Path | None = None,
    *,
    provider_name: str = "",
    app_name: str = "",
    runtime_generation: int = 0,
) -> None:
    del state_path
    normalized_provider = str(provider_name or "").strip()
    if not normalized_provider:
        return
    state = _coerce_state(payload, app_name=app_name, runtime_generation=runtime_generation)
    _persist_runtime_state(normalized_provider, state)


def stamp_runtime_metadata(payload: dict, *, app_name: str = "", runtime_generation: int = 0) -> dict:
    return _coerce_state(payload, app_name=app_name, runtime_generation=runtime_generation).to_runtime_payload()


def clear_runtime_state_cache() -> None:
    _persistence_client.cache_clear()


@lru_cache(maxsize=1)
def _persistence_client():
    database_url = str(os.getenv("SAGA_MODAL_STATE_DB_URL") or os.getenv("SAGA_RUNTIME_DB_URL") or "").strip()
    database_mode = str(os.getenv("SAGA_MODAL_STATE_DB_MODE") or os.getenv("SAGA_RUNTIME_DB_MODE") or "supabase_postgres").strip() or "supabase_postgres"
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
        name="modal-provider-state",
        provider="supabase",
        mode=database_mode,
        database_url=database_url,
        application_name="saga-modal-runtime-state",
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


def _coerce_state(payload: dict | None, *, app_name: str = "", runtime_generation: int = 0) -> ModalRuntimeState:
    state = ModalRuntimeState.from_payload(payload or {})
    if app_name:
        state.app_name = str(app_name).strip()
    if runtime_generation:
        state.runtime_generation = int(runtime_generation)
    state.next_index = max(0, int(state.next_index or 0))
    return state


def _fresh_state(*, app_name: str = "", runtime_generation: int = 0) -> dict:
    return ModalRuntimeState(app_name=str(app_name or "").strip(), runtime_generation=max(0, int(runtime_generation or 0))).to_runtime_payload()


def _load_persisted_runtime_state(provider_name: str) -> ModalRuntimeState:
    client = _persistence_client()
    config_row = client.provider_configs.get_provider_config(provider_name)
    config_payload = dict((config_row or {}).get("payload") or {})
    state = ModalRuntimeState.from_payload(config_payload.get("runtime_state") if isinstance(config_payload.get("runtime_state"), dict) else {})
    for row in client.provider_configs.list_provider_statuses(provider_name):
        label = str(row.get("label") or "").strip()
        if not label:
            continue
        state.token_stats[label] = ModalTokenStatus.from_status_row(label, dict(row.get("payload") or {}))
    return state


def _persist_runtime_state(provider_name: str, state: ModalRuntimeState) -> None:
    client = _persistence_client()
    config_row = client.provider_configs.get_provider_config(provider_name)
    config_payload = dict((config_row or {}).get("payload") or {})
    runtime_payload = state.to_runtime_payload()
    token_stats = dict(runtime_payload.pop("token_stats", {}) or {})
    config_payload["runtime_state"] = runtime_payload
    client.provider_configs.upsert_provider_config(provider_name, config_payload)

    status_payloads = []
    for token_name, payload in token_stats.items():
        status_payloads.append({"label": token_name, **dict(payload or {})})
    client.provider_configs.replace_provider_statuses(provider_name, status_payloads)
