"""Relational canonical storage for SAGA analysis artifacts."""

from .database import get_database_url, get_engine, get_session_factory, initialize_database
from .persistence import SagaRelationalStore, SagaSQLiteStore
from .render_artifact_projection import (
    RenderArtifactProjection,
    build_entity_render_artifact_projection,
    build_render_artifact_projection,
    normalize_runtime_path,
    resolve_runtime_thumbnail,
)

__all__ = [
    "get_database_url",
    "get_engine",
    "get_session_factory",
    "initialize_database",
    "SagaRelationalStore",
    "SagaSQLiteStore",
    "RenderArtifactProjection",
    "build_entity_render_artifact_projection",
    "build_render_artifact_projection",
    "normalize_runtime_path",
    "resolve_runtime_thumbnail",
]
