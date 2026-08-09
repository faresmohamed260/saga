"""Narrative generation runtime package."""

from .contracts import (
    ChapterDraftArtifact,
    ContinuityCheckArtifact,
    GeneratedStoryArtifact,
    ClaimSupportArtifact,
    NarrativeSupportDecisionArtifact,
    NarrativeSupportResult,
    NarrativeGenerationResult,
    RevisionRecordArtifact,
    SceneProseArtifact,
    SceneSupportAuditArtifact,
    SupportEvidenceArtifact,
)
from .pipeline import (
    ContinuityGuardAgent,
    NarrativeGenerationAgent,
    NarrativeGenerationRuntime,
    RewriteRevisionAgent,
    build_narrative_generation_graph,
)
from .quality import NarrativeGenerationQualityMetrics, evaluate_narrative_generation, require_narrative_semantic_acceptance
from .support_pipeline import (
    CanonEvidenceIndexAgent,
    NarrativeSupportRuntime,
    SemanticSupportAgent,
    SupportDecisionAgent,
    SupportRevisionAgent,
    build_narrative_support_graph,
)
from .support_service import (
    NarrativeSupportRunRequest,
    NarrativeSupportService,
    NarrativeSupportServiceConfig,
    load_narrative_support_service_config_from_env,
)
from .service import (
    NarrativeGenerationRunRequest,
    NarrativeGenerationService,
    NarrativeGenerationServiceConfig,
    load_narrative_generation_service_config_from_env,
)

__all__ = [
    "ChapterDraftArtifact",
    "ClaimSupportArtifact",
    "CanonEvidenceIndexAgent",
    "ContinuityCheckArtifact",
    "ContinuityGuardAgent",
    "GeneratedStoryArtifact",
    "NarrativeGenerationAgent",
    "NarrativeGenerationQualityMetrics",
    "NarrativeGenerationResult",
    "NarrativeGenerationRunRequest",
    "NarrativeGenerationRuntime",
    "NarrativeGenerationService",
    "NarrativeGenerationServiceConfig",
    "NarrativeSupportDecisionArtifact",
    "NarrativeSupportResult",
    "NarrativeSupportRunRequest",
    "NarrativeSupportRuntime",
    "NarrativeSupportService",
    "NarrativeSupportServiceConfig",
    "RevisionRecordArtifact",
    "RewriteRevisionAgent",
    "SceneProseArtifact",
    "SceneSupportAuditArtifact",
    "SemanticSupportAgent",
    "SupportDecisionAgent",
    "SupportEvidenceArtifact",
    "SupportRevisionAgent",
    "build_narrative_generation_graph",
    "build_narrative_support_graph",
    "evaluate_narrative_generation",
    "require_narrative_semantic_acceptance",
    "load_narrative_generation_service_config_from_env",
    "load_narrative_support_service_config_from_env",
]
