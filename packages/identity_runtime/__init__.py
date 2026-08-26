"""Reusable identity runtime backed by the active Modal xcore service."""

from .client import IdentityRuntimeClient, IdentityRuntimeConfig, IdentityRuntimeProfile
from .canonicalization_evaluation import IdentityCanonicalizationMetrics, evaluate_identity_canonicalization
from .contracts import (
    IdentityAliasEvidence,
    IdentityCluster,
    IdentityGroundingReviewResult,
    IdentityMergeEvidence,
    IdentityQualityDiagnostic,
    IdentityRuntimeResult,
    ReviewedIdentityCluster,
)
from .review import review_identity_clusters

__all__ = [
    "IdentityCluster",
    "IdentityCanonicalizationMetrics",
    "IdentityAliasEvidence",
    "IdentityGroundingReviewResult",
    "IdentityMergeEvidence",
    "IdentityRuntimeClient",
    "IdentityRuntimeConfig",
    "IdentityRuntimeProfile",
    "IdentityQualityDiagnostic",
    "IdentityRuntimeResult",
    "ReviewedIdentityCluster",
    "review_identity_clusters",
    "evaluate_identity_canonicalization",
]
