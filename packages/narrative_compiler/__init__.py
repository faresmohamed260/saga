"""S.A.G.A. v3 narrative compiler foundation.

This package is intentionally model-light. Heavy model adapters live behind the
contracts exported here and must remain optional so normal CI never downloads
model weights.
"""

from .fingerprint import artifact_fingerprint, config_fingerprint, stable_id
from .ir import (
    AcceptanceState,
    Entity,
    EntityType,
    EvidenceRef,
    Mention,
    ModelDescriptor,
    SourceSpan,
    StageRunDescriptor,
)
from .source import NormalizedSection, NormalizedSource

__all__ = [
    "AcceptanceState",
    "Entity",
    "EntityType",
    "EvidenceRef",
    "Mention",
    "ModelDescriptor",
    "NormalizedSection",
    "NormalizedSource",
    "SourceSpan",
    "StageRunDescriptor",
    "artifact_fingerprint",
    "config_fingerprint",
    "stable_id",
]
