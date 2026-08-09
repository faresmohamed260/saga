"""Reusable identity runtime backed by the active Modal xcore service."""

from .client import IdentityRuntimeClient, IdentityRuntimeConfig, IdentityRuntimeProfile
from .contracts import (
    IdentityAliasEvidence,
    IdentityCluster,
    IdentityGroundingReviewResult,
    IdentityQualityDiagnostic,
    IdentityRuntimeResult,
    ReviewedIdentityCluster,
)
from .review import review_identity_clusters

__all__ = [
    "IdentityCluster",
    "IdentityAliasEvidence",
    "IdentityGroundingReviewResult",
    "IdentityRuntimeClient",
    "IdentityRuntimeConfig",
    "IdentityRuntimeProfile",
    "IdentityQualityDiagnostic",
    "IdentityRuntimeResult",
    "ReviewedIdentityCluster",
    "review_identity_clusters",
]
