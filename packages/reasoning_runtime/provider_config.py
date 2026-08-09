from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from packages.persistence_runtime import PersistenceRuntimeClient
from packages.reasoning_runtime.models import GeneralComputeAccount, OllamaAccount, ReasoningRuntimeConfig


OLLAMA_PROVIDER_NAME = "ollama"
GENERAL_COMPUTE_PROVIDER_NAME = "general_compute"


def apply_persistence_provider_configs(
    config: ReasoningRuntimeConfig,
    *,
    persistence_client: PersistenceRuntimeClient,
) -> ReasoningRuntimeConfig:
    ollama_row = persistence_client.provider_configs.get_provider_config(OLLAMA_PROVIDER_NAME)
    ollama_payload = dict((ollama_row or {}).get("payload") or {})
    general_row = persistence_client.provider_configs.get_provider_config(GENERAL_COMPUTE_PROVIDER_NAME)
    general_payload = dict((general_row or {}).get("payload") or {})
    return ReasoningRuntimeConfig(
        profiles=dict(config.profiles or {}),
        ollama_accounts=_parse_ollama_accounts(ollama_payload.get("accounts")),
        general_compute_accounts=_parse_general_compute_accounts(general_payload.get("accounts")),
        ollama_active_index=max(0, int(ollama_payload.get("active_index") or 0)),
        general_compute_active_index=max(0, int(general_payload.get("active_index") or 0)),
        general_compute_last_request_index=max(-1, int(general_payload.get("last_request_index") or -1)),
        ollama_local_url=config.ollama_local_url,
        ollama_cloud_url=config.ollama_cloud_url,
        general_compute_chat_url=config.general_compute_chat_url,
        mistral_api_key=config.mistral_api_key,
        gemini_api_key=config.gemini_api_key,
    )


def import_ollama_accounts_from_file(
    persistence_client: PersistenceRuntimeClient,
    *,
    file_path: str | Path,
) -> dict[str, Any]:
    path = Path(file_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    accounts = _parse_ollama_accounts(payload.get("accounts") if isinstance(payload, dict) else None)
    active_index = max(0, int((payload.get("active_index") if isinstance(payload, dict) else 0) or 0))
    persistence_client.provider_configs.upsert_provider_config(
        OLLAMA_PROVIDER_NAME,
        {
            "active_index": active_index,
            "accounts": [account.__dict__ for account in accounts],
            "source": "local_file_import",
            "source_path": str(path),
        },
    )
    return {"provider_name": OLLAMA_PROVIDER_NAME, "accounts_imported": len(accounts), "active_index": active_index}


def import_general_compute_accounts_from_file(
    persistence_client: PersistenceRuntimeClient,
    *,
    file_path: str | Path,
) -> dict[str, Any]:
    path = Path(file_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    accounts = _parse_general_compute_accounts(payload.get("accounts") if isinstance(payload, dict) else None)
    active_index = max(0, int((payload.get("active_index") if isinstance(payload, dict) else 0) or 0))
    last_request_index = max(-1, int((payload.get("last_request_index") if isinstance(payload, dict) else -1) or -1))
    persistence_client.provider_configs.upsert_provider_config(
        GENERAL_COMPUTE_PROVIDER_NAME,
        {
            "active_index": active_index,
            "last_request_index": last_request_index,
            "accounts": [account.__dict__ for account in accounts],
            "source": "local_file_import",
            "source_path": str(path),
        },
    )
    return {
        "provider_name": GENERAL_COMPUTE_PROVIDER_NAME,
        "accounts_imported": len(accounts),
        "active_index": active_index,
        "last_request_index": last_request_index,
    }


def summarize_reasoning_provider_configs(persistence_client: PersistenceRuntimeClient) -> dict[str, Any]:
    ollama_row = persistence_client.provider_configs.get_provider_config(OLLAMA_PROVIDER_NAME)
    ollama_payload = dict((ollama_row or {}).get("payload") or {})
    general_row = persistence_client.provider_configs.get_provider_config(GENERAL_COMPUTE_PROVIDER_NAME)
    general_payload = dict((general_row or {}).get("payload") or {})
    return {
        "ollama": {
            "configured": bool(ollama_payload),
            "accounts": _summarize_accounts(ollama_payload.get("accounts")),
            "active_index": max(0, int(ollama_payload.get("active_index") or 0)),
        },
        "general_compute": {
            "configured": bool(general_payload),
            "accounts": _summarize_accounts(general_payload.get("accounts")),
            "active_index": max(0, int(general_payload.get("active_index") or 0)),
            "last_request_index": max(-1, int(general_payload.get("last_request_index") or -1)),
            "has_env_api_key": bool(str(os.getenv("GENERAL_COMPUTE_API_KEY") or "").strip()),
        },
        "mistral": {"has_env_api_key": bool(str(os.getenv("MISTRAL_API_KEY") or "").strip())},
        "gemini": {"has_env_api_key": bool(str(os.getenv("GEMINI_API_KEY") or "").strip())},
    }


def _parse_ollama_accounts(value: Any) -> list[OllamaAccount]:
    results: list[OllamaAccount] = []
    for item in value or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        results.append(
            OllamaAccount(
                label=label,
                api_key=str(item.get("api_key") or "").strip(),
                email=str(item.get("email") or "").strip(),
                password=str(item.get("password") or "").strip(),
                metadata=dict(item.get("metadata") or {}),
            )
        )
    return results


def _parse_general_compute_accounts(value: Any) -> list[GeneralComputeAccount]:
    results: list[GeneralComputeAccount] = []
    for item in value or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        api_key = str(item.get("api_key") or "").strip()
        if not label or not api_key:
            continue
        results.append(
            GeneralComputeAccount(
                label=label,
                api_key=api_key,
                limits=dict(item.get("limits") or {}),
                usage=dict(item.get("usage") or {}),
                metadata=dict(item.get("metadata") or {}),
            )
        )
    return results


def _summarize_accounts(value: Any) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in value or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        results.append(
            {
                "label": label,
                "has_api_key": bool(str(item.get("api_key") or "").strip()),
            }
        )
    return results
