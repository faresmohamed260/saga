"""Factory helpers for portable retrieval clients."""

from __future__ import annotations

from packages.retrieval_runtime.client import RetrievalRuntimeClient
from packages.retrieval_runtime.models import RetrievalProfile, RetrievalRuntimeConfig


def create_retrieval_client(
    *,
    config: RetrievalRuntimeConfig,
    profile: RetrievalProfile | None = None,
    embedder=None,
    persistence_client=None,
) -> RetrievalRuntimeClient:
    resolved_profile = profile or config.profile
    return RetrievalRuntimeClient(
        profile=resolved_profile,
        config=config,
        embedder=embedder,
        persistence_client=persistence_client,
    )
