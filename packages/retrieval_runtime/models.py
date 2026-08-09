"""Portable configuration models for the retrieval runtime."""

from __future__ import annotations

from dataclasses import dataclass

from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig


@dataclass(frozen=True)
class RetrievalProfile:
    name: str
    mode: str = "document_index"
    embedding_model: str = "nomic-embed-text:latest"
    ollama_embed_url: str = "http://localhost:11434/api/embed"
    batch_size: int = 24
    vector_namespace_prefix: str = "retrieval"

    def __post_init__(self) -> None:
        if not str(self.name or "").strip():
            raise ValueError("RetrievalProfile.name is required.")
        if not str(self.mode or "").strip():
            raise ValueError("RetrievalProfile.mode is required.")
        if not str(self.embedding_model or "").strip():
            raise ValueError("RetrievalProfile.embedding_model is required.")
        if not str(self.ollama_embed_url or "").strip().startswith(("http://", "https://")):
            raise ValueError("RetrievalProfile.ollama_embed_url must be an HTTP(S) URL.")
        if int(self.batch_size) < 1:
            raise ValueError("RetrievalProfile.batch_size must be at least 1.")
        if not str(self.vector_namespace_prefix or "").strip():
            raise ValueError("RetrievalProfile.vector_namespace_prefix is required.")


@dataclass
class RetrievalRuntimeConfig:
    profile: RetrievalProfile
    persistence_profile: PersistenceProfile | None = None
    persistence_config: PersistenceRuntimeConfig | None = None

    def __post_init__(self) -> None:
        if self.profile is None:
            raise ValueError("RetrievalRuntimeConfig.profile is required.")
