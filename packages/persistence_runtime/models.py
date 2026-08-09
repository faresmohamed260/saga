"""Portable configuration models for the persistence runtime."""

from __future__ import annotations

from dataclasses import dataclass

_ALLOWED_PERSISTENCE_MODES = {"supabase_postgres", "test_harness"}


@dataclass(frozen=True)
class PersistenceProfile:
    name: str
    provider: str = "supabase"
    mode: str = "supabase_postgres"
    database_url: str = ""
    schema_name: str = "public"
    connect_timeout_seconds: int = 15
    pool_size: int = 5
    max_overflow: int = 10
    application_name: str = "saga-persistence-runtime"
    vector_table_name: str = "vector_documents"
    vector_metric: str = "cosine"
    local_storage_root_dir: str = "analysis_outputs/unified_storage"

    def __post_init__(self) -> None:
        if not str(self.name or "").strip():
            raise ValueError("PersistenceProfile.name is required.")
        if not str(self.provider or "").strip():
            raise ValueError("PersistenceProfile.provider is required.")
        normalized_mode = str(self.mode or "").strip().lower()
        if not normalized_mode:
            raise ValueError("PersistenceProfile.mode is required.")
        if normalized_mode not in _ALLOWED_PERSISTENCE_MODES:
            raise ValueError(
                "PersistenceProfile.mode must be one of: "
                + ", ".join(sorted(_ALLOWED_PERSISTENCE_MODES))
                + "."
            )
        if int(self.connect_timeout_seconds) <= 0:
            raise ValueError("PersistenceProfile.connect_timeout_seconds must be positive.")
        if int(self.pool_size) < 1:
            raise ValueError("PersistenceProfile.pool_size must be at least 1.")
        if int(self.max_overflow) < 0:
            raise ValueError("PersistenceProfile.max_overflow cannot be negative.")
        if not str(self.vector_table_name or "").strip():
            raise ValueError("PersistenceProfile.vector_table_name is required.")
        if not str(self.vector_metric or "").strip():
            raise ValueError("PersistenceProfile.vector_metric is required.")


@dataclass
class PersistenceRuntimeConfig:
    profile: PersistenceProfile
    supabase_url: str = ""
    supabase_api_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    def __post_init__(self) -> None:
        if self.profile is None:
            raise ValueError("PersistenceRuntimeConfig.profile is required.")
