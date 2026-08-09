"""Provider implementations for the persistence runtime."""

from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from packages.persistence_runtime.database_url import build_database_url_from_env
from packages.persistence_runtime.contracts import PersistenceProvider
from packages.persistence_runtime.models import PersistenceProfile, PersistenceRuntimeConfig
from packages.persistence_runtime.schema import Base
from packages.persistence_runtime.schema_validation import validate_production_schema
from packages.persistence_runtime.storage_url import build_storage_api_url_from_env, resolve_supabase_service_role_key
from packages.persistence_runtime.stores import (
    AudiobookStore,
    DeploymentStore,
    ExecutionQueueStore,
    IdentityStore,
    JobStore,
    LineageStore,
    ObservabilityStore,
    UsageLedgerStore,
    LibraryStore,
    LocalObjectStorageStore,
    ProviderConfigStore,
    StoryStore,
    SupabaseObjectStorageStore,
    VectorDocumentStore,
)


def create_sqlalchemy_engine(database_url: str, *, profile: PersistenceProfile | None = None) -> Engine:
    normalized_database_url = str(database_url or "").strip()
    if not normalized_database_url:
        raise ValueError("database_url is required.")
    kwargs: dict[str, Any] = {
        "future": True,
        "pool_pre_ping": True,
    }
    if normalized_database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        resolved_profile = profile or PersistenceProfile(name="sqlalchemy-engine-helper")
        kwargs["pool_size"] = max(1, int(resolved_profile.pool_size))
        kwargs["max_overflow"] = max(0, int(resolved_profile.max_overflow))
        kwargs["connect_args"] = {
            "connect_timeout": max(1, int(resolved_profile.connect_timeout_seconds)),
            "application_name": resolved_profile.application_name,
        }
        if normalized_database_url.startswith(("postgresql+psycopg://", "postgresql://")):
            # Supavisor transaction pooling can reuse server connections across
            # clients, so psycopg prepared statement names may collide.
            kwargs["connect_args"]["prepare_threshold"] = None
    return create_engine(normalized_database_url, **kwargs)


class SupabasePersistenceProvider:
    def __init__(self, *, profile: PersistenceProfile, config: PersistenceRuntimeConfig) -> None:
        self.profile = profile
        self.config = config
        self.is_test_harness = str(profile.mode or "").strip().lower() == "test_harness"
        self.database_url = self._resolve_database_url(profile, config)
        self.engine = self._create_engine()
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False, future=True)
        self.provider_configs = ProviderConfigStore(self.session_factory)
        self.library = LibraryStore(self.session_factory)
        self.identity = IdentityStore(self.session_factory)
        self.jobs = JobStore(self.session_factory)
        self.execution_queue = ExecutionQueueStore(self.session_factory)
        self.lineage = LineageStore(self.session_factory)
        self.observability = ObservabilityStore(self.session_factory)
        self.usage = UsageLedgerStore(self.session_factory)
        self.deployments = DeploymentStore(self.session_factory)
        self.stories = StoryStore(self.session_factory)
        self.audiobooks = AudiobookStore(self.session_factory)
        self.vectors = VectorDocumentStore(
            self.engine,
            table_name=str(profile.vector_table_name or "vector_documents").strip() or "vector_documents",
            metric=str(profile.vector_metric or "cosine").strip() or "cosine",
            provider_label="test_harness" if self.is_test_harness else "supabase",
        )
        if self.engine.dialect.name == "postgresql":
            storage_api_url = self._resolve_storage_api_url(config)
            if storage_api_url:
                self.objects = SupabaseObjectStorageStore(
                    base_url=storage_api_url,
                    service_role_key=resolve_supabase_service_role_key(explicit=config.supabase_service_role_key),
                    timeout_seconds=max(15, int(profile.connect_timeout_seconds) * 4),
                )
            else:
                local_root = str(profile.local_storage_root_dir or "").strip()
                if not local_root:
                    raise ValueError(
                        "PostgreSQL-backed persistence requires either a Supabase storage API URL or "
                        "PersistenceProfile.local_storage_root_dir for local artifact storage."
                    )
                self.objects = LocalObjectStorageStore(local_root)
        elif self.is_test_harness:
            self.objects = LocalObjectStorageStore(profile.local_storage_root_dir)
        else:
            raise ValueError(
                "PersistenceProfile.mode='supabase_postgres' requires a PostgreSQL database URL. "
                "Use PersistenceProfile.mode='test_harness' only for explicit local contract tests."
            )

    def provider_name(self) -> str:
        if self.is_test_harness:
            return "test_harness"
        return str(self.profile.provider or "supabase").strip().lower() or "supabase"

    def initialize(self) -> None:
        if self.is_test_harness:
            Base.metadata.create_all(self.engine)
            self.vectors.initialize()
            return
        validate_production_schema(self.engine, vector_table_name=self.profile.vector_table_name)

    def close(self) -> None:
        self.engine.dispose()

    def _create_engine(self) -> Engine:
        return create_sqlalchemy_engine(self.database_url, profile=self.profile)

    @staticmethod
    def _resolve_database_url(profile: PersistenceProfile, config: PersistenceRuntimeConfig) -> str:
        candidates = [
            profile.database_url,
            config.supabase_url,
        ]
        for candidate in candidates:
            value = str(candidate or "").strip()
            if value:
                return value
        built_url = build_database_url_from_env()
        if built_url:
            return built_url
        raise ValueError(
            "Database URL is required. Set PersistenceProfile.database_url, "
            "PersistenceRuntimeConfig.supabase_url, SAGA_SUPABASE_DB_URL, SUPABASE_DB_URL, "
            "DATABASE_URL, or the self-hosted Supabase component env vars."
        )

    @staticmethod
    def _resolve_storage_api_url(config: PersistenceRuntimeConfig) -> str:
        explicit = str(config.supabase_api_url or "").strip().rstrip("/")
        if explicit:
            if explicit.endswith("/storage/v1"):
                return explicit
            return f"{explicit}/storage/v1"
        resolved = build_storage_api_url_from_env()
        if resolved:
            return resolved
        return ""


def create_provider(*, profile: PersistenceProfile, config: PersistenceRuntimeConfig) -> PersistenceProvider:
    provider_name = str(profile.provider or "supabase").strip().lower() or "supabase"
    if provider_name == "supabase":
        return SupabasePersistenceProvider(profile=profile, config=config)
    raise ValueError(f"Unsupported persistence provider '{provider_name}'.")
