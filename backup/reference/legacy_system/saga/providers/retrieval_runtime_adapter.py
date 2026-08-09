from __future__ import annotations

from packages.retrieval_runtime.factory import create_retrieval_client
from packages.retrieval_runtime.models import RetrievalProfile, RetrievalRuntimeConfig


MODE_DOCUMENT_INDEX = "document_index"


def create_runtime_retrieval_client(
    *,
    mode: str = MODE_DOCUMENT_INDEX,
    base_dir: str = "analysis_outputs/vector_indices",
    embedding_model: str = "nomic-embed-text:latest",
    ollama_embed_url: str = "http://localhost:11434/api/embed",
    batch_size: int = 24,
    embedder=None,
):
    profile = RetrievalProfile(
        name=f"runtime_{mode}",
        mode=str(mode or MODE_DOCUMENT_INDEX).strip().lower() or MODE_DOCUMENT_INDEX,
        base_dir=base_dir,
        embedding_model=embedding_model,
        ollama_embed_url=ollama_embed_url,
        batch_size=max(1, int(batch_size)),
    )
    return create_retrieval_client(config=RetrievalRuntimeConfig(profile=profile), profile=profile, embedder=embedder)
