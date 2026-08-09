"""Factory helpers for the persistence runtime."""

from __future__ import annotations

from packages.persistence_runtime.client import PersistenceRuntimeClient
from packages.persistence_runtime.models import PersistenceProfile, PersistenceRuntimeConfig
from packages.persistence_runtime.providers import create_provider


def create_persistence_client(
    *,
    config: PersistenceRuntimeConfig,
    profile: PersistenceProfile | None = None,
) -> PersistenceRuntimeClient:
    resolved_profile = profile or config.profile
    return PersistenceRuntimeClient(profile=resolved_profile, config=config)


def create_persistence_provider(
    *,
    config: PersistenceRuntimeConfig,
    profile: PersistenceProfile | None = None,
):
    resolved_profile = profile or config.profile
    return create_provider(profile=resolved_profile, config=config)
