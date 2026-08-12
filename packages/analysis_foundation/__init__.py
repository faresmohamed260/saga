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
from .addressee_evaluation import (
    AddresseeEvaluation,
    AddresseeGoldCase,
    evaluate_addressees,
)
from .narrative_grounding_evaluation import (
    NarrativeGroundingEvaluation,
    NarrativeGroundingGoldCase,
    evaluate_narrative_grounding,
)
from .service import (
    AnalysisFoundationRunRequest,
    AnalysisFoundationService,
    AnalysisFoundationServiceConfig,
    load_analysis_foundation_service_config_from_env,
)

__all__ = [
    "AddresseeEvaluation",
    "AddresseeGoldCase",
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
    "NarrativeGroundingEvaluation",
    "NarrativeGroundingGoldCase",
    "NarratorReferenceData",
    "SceneArtifact",
    "SceneNarrativeGrounding",
    "SceneSegmentationAgent",
    "SourceDocumentArtifact",
    "build_analysis_foundation_graph",
    "evaluate_addressees",
    "evaluate_narrative_grounding",
    "load_analysis_foundation_service_config_from_env",
]
