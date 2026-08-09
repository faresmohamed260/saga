from __future__ import annotations

from typing import Any

from saga.storage.persistence import SagaRelationalStore


class ProviderConfigStore:
    """Provider config/status persistence adapter over the canonical relational store."""

    def __init__(self, relational_store: SagaRelationalStore | None = None) -> None:
        self.relational_store = relational_store or SagaRelationalStore()
        self.session_factory = self.relational_store.session_factory

    def upsert_provider_config(self, provider_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.relational_store.upsert_provider_config(provider_name, payload)

    def get_provider_config(self, provider_name: str) -> dict[str, Any] | None:
        return self.relational_store.get_provider_config(provider_name)

    def get_provider_configs(self) -> list[dict[str, Any]]:
        return self.relational_store.get_provider_configs()

    def upsert_provider_status(self, provider_name: str, label: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.relational_store.upsert_provider_status(provider_name, label, payload)

    def replace_provider_statuses(self, provider_name: str, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self.relational_store.replace_provider_statuses(provider_name, payloads)

    def get_provider_statuses(self, provider_name: str | None = None) -> list[dict[str, Any]]:
        return self.relational_store.get_provider_statuses(provider_name)


# Backward-compatible alias for older call sites that still use the SQLite-era name.
SQLiteProviderConfigStore = ProviderConfigStore
