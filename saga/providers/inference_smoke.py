from __future__ import annotations

from datetime import datetime, timezone

from saga.providers.inference_registry import read_inference_provider_config
from saga.storage.persistence import SagaSQLiteStore


def run_provider_smoke(*, capability: str, provider_name: str, store: SagaSQLiteStore | None = None) -> dict:
    sqlite_store = store or SagaSQLiteStore()
    payload = read_inference_provider_config(provider_name, store=sqlite_store, mask=True)
    api_url = str(payload.get("api_url") or "").strip()
    accounts = list(payload.get("accounts") or [])
    status = "ok" if api_url or accounts else "unconfigured"
    detail = "Provider configuration is present." if status == "ok" else "No provider API URL or accounts are configured."
    return {
        "capability": str(capability or "").strip().lower(),
        "provider_name": str(provider_name or "").strip().lower(),
        "status": status,
        "detail": detail,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
