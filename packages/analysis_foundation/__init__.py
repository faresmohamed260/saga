"""Analysis foundation for ingesting books, segmenting scenes, and resolving identity."""

from .contracts import (
    AnalysisFoundationResult,
    BookArtifact,
    CanonicalCharacter,
    CanonicalIdentityBundle,
    ChapterArtifact,
    NarrativeEvidenceSpan,
    NarratorReferenceData,
    SceneArtifact,
    SceneNarrativeGrounding,
    SourceDocumentArtifact,
)
from .pipeline import (
    AnalysisFoundationRuntime,
    IngestionAgent,
    IdentityAgent,
    NarrativeGroundingAgent,
    SceneSegmentationAgent,
    build_analysis_foundation_graph,
)
from .service import (
    AnalysisFoundationRunRequest,
    AnalysisFoundationService,
    AnalysisFoundationServiceConfig,
    load_analysis_foundation_service_config_from_env,
)

__all__ = [
    "AnalysisFoundationResult",
    "AnalysisFoundationRuntime",
    "AnalysisFoundationRunRequest",
    "AnalysisFoundationService",
    "AnalysisFoundationServiceConfig",
    "BookArtifact",
    "CanonicalCharacter",
    "CanonicalIdentityBundle",
    "ChapterArtifact",
    "IdentityAgent",
    "IngestionAgent",
    "NarrativeEvidenceSpan",
    "NarrativeGroundingAgent",
    "NarratorReferenceData",
    "SceneArtifact",
    "SceneNarrativeGrounding",
    "SceneSegmentationAgent",
    "SourceDocumentArtifact",
    "build_analysis_foundation_graph",
    "load_analysis_foundation_service_config_from_env",
]
