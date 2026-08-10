"""Stage input projections and lineage helpers for production orchestration."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from packages.lineage_runtime import LineageVersions, StageLineageSpec, sanitize
from packages.production_orchestration.contracts import OrchestrationRequest, StageName, StageOutcomeArtifact
from packages.production_orchestration.policy import STAGE_DEPENDENCIES


STAGE_CONTRACT_VERSIONS: dict[str, dict[str, str]] = {
    "analysis_foundation": {"runtime": "analysis-foundation-v1", "schema_version": "analysis-v1", "quality_policy": "analysis-quality-v1"},
    "canon_extraction": {"runtime": "canon-extraction-v1", "schema_version": "canon-v1", "quality_policy": "canon-quality-v1"},
    "character_world_modeling": {"runtime": "character-world-v1", "schema_version": "character-world-v1", "quality_policy": "character-world-quality-v1"},
    "generation_planning": {"runtime": "generation-planning-v1", "schema_version": "blueprint-v1", "quality_policy": "planning-quality-v1"},
    "narrative_generation": {"runtime": "narrative-generation-v2", "schema_version": "story-v1", "quality_policy": "narrative-quality-v2"},
    "narrative_support": {"runtime": "narrative-support-v2", "schema_version": "support-v1", "quality_policy": "semantic-support-v2"},
    "visual_generation": {"runtime": "visual-generation-v1", "schema_version": "visual-v1", "quality_policy": "visual-quality-v2"},
    "audiobook_generation": {"runtime": "audiobook-generation-v1", "schema_version": "audiobook-v1", "quality_policy": "audio-quality-v1"},
    "artifact_packaging": {"runtime": "production-packaging-v1", "schema_version": "deliverable-manifest-v1", "quality_policy": "package-quality-v2"},
}


class PersistenceArtifactVersionStore:
    """Persist immutable output snapshots through the storage runtime."""

    def __init__(self, artifacts: Any) -> None:
        self.artifacts = artifacts

    def put(
        self, *, execution_id: str, run_id: str, series_id: str, stage: str,
        output_fingerprint: str, output_payload: Any,
    ) -> dict[str, Any]:
        stored = self.artifacts.store_json(
            artifact_type="runtime_report",
            filename=f"{execution_id}.json",
            payload={
                "execution_id": execution_id,
                "run_id": run_id,
                "series_id": series_id,
                "stage": stage,
                "output_fingerprint": output_fingerprint,
                "output": sanitize(output_payload),
            },
            series_id=series_id,
            run_id=run_id,
            provider_name="lineage-runtime",
            report_kind=stage,
            metadata={"execution_id": execution_id, "output_fingerprint": output_fingerprint},
            upsert=False,
            record_type="lineage_artifact_version",
        )
        return {
            "record_id": str(stored.get("record_id") or ""),
            "bucket_name": str(stored.get("bucket_name") or ""),
            "object_path": str(stored.get("object_path") or ""),
            "output_fingerprint": output_fingerprint,
        }

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MODELS = {
    "deepseek": "deepseek-v3.1:671b-cloud",
    "gpt_oss": "gpt-oss:120b-cloud",
    "general_compute": "deepseek-v3.1",
    "mistral": "mistral-large-2512",
    "gemini": "gemini-2.0-flash",
}


def active_stage_version_overrides(explicit: dict[str, dict[str, Any]] | None = None) -> dict[str, dict[str, str]]:
    """Resolve non-secret deployment identities used for deterministic invalidation."""
    stage_files = {
        "canon_extraction": "packages/canon_extraction/pipeline.py",
        "character_world_modeling": "packages/character_world_modeling/pipeline.py",
        "generation_planning": "packages/generation_planning/pipeline.py",
        "narrative_generation": "packages/narrative_generation/pipeline.py",
        "narrative_support": "packages/narrative_generation/support_pipeline.py",
        "visual_generation": "packages/visual_generation/pipeline.py",
        "audiobook_generation": "packages/audiobook_generation/pipeline.py",
    }
    modes = {
        "canon_extraction": _env("SAGA_CANON_EXTRACTION_REASONING_MODE", "gpt_oss"),
        "character_world_modeling": _env("SAGA_CHARACTER_WORLD_MODELING_REASONING_MODE", "gpt_oss"),
        "generation_planning": _env("SAGA_GENERATION_PLANNING_REASONING_MODE", "gpt_oss"),
        "narrative_generation": _env("SAGA_NARRATIVE_GENERATION_REASONING_MODE", "gpt_oss"),
        "narrative_support": _env("SAGA_NARRATIVE_SUPPORT_REASONING_MODE", "mistral"),
    }
    resolved: dict[str, dict[str, str]] = {
        "analysis_foundation": {
            "model": _env("SAGA_ANALYSIS_IDENTITY_MODEL", "sapienzanlp/xcore-litbank"),
            "provider_config": _env("SAGA_ANALYSIS_IDENTITY_PROVIDER", "modal-coreference"),
        },
        "visual_generation": {
            "prompt": _file_digest(stage_files["visual_generation"]),
            "workflow": _combined_digest([
                "integrations/comfyui/workflows/character_sheet_workflow.json",
                "integrations/comfyui/workflows/entity_generation_workflow.json",
            ]),
            "model": "|".join(filter(None, [
                _env("SAGA_VISUAL_PLANNING_MODEL", _DEFAULT_MODELS.get(_env("SAGA_VISUAL_PLANNING_MODE", "mistral"), "")),
                _env("SAGA_VISUAL_QUALITY_MODEL", "mistral-small-2603"),
                _env("SAGA_VISUAL_HARD_CONSTRAINT_MODEL", "mistral-medium-2604"),
            ])),
            "provider_config": "planning=" + _env("SAGA_VISUAL_PLANNING_MODE", "mistral") + ";vision=" + _env("SAGA_VISUAL_QUALITY_MODE", "mistral") + ";hard_constraints=" + _env("SAGA_VISUAL_HARD_CONSTRAINT_MODE", "mistral") + ";render=modal-comfyui",
        },
        "audiobook_generation": {
            "prompt": _file_digest(stage_files["audiobook_generation"]),
            "model": _env("SAGA_AUDIOBOOK_TRANSCRIPTION_MODEL", "voxtral-mini-latest"),
            "provider_config": "transcription=mistral;tts=modal-kokoro",
        },
        "artifact_packaging": {
            "workflow": _file_digest("packages/production_orchestration/packaging.py"),
            "provider_config": "artifact-storage-runtime",
        },
    }
    for stage, mode in modes.items():
        resolved[stage] = {
            "prompt": _file_digest(stage_files[stage]),
            "model": _DEFAULT_MODELS.get(mode, mode),
            "provider_config": mode,
        }
    for stage, values in (explicit or {}).items():
        resolved.setdefault(stage, {}).update({str(key): str(value) for key, value in values.items()})
    return resolved


def build_stage_spec(
    stage: StageName,
    request: OrchestrationRequest,
    *,
    version_overrides: dict[str, dict[str, Any]] | None = None,
) -> StageLineageSpec:
    versions = {**STAGE_CONTRACT_VERSIONS[stage], **dict((version_overrides or {}).get(stage) or {})}
    return StageLineageSpec(
        stage=stage,
        input_payload=_stage_request_payload(stage, request),
        versions=LineageVersions.model_validate(versions),
    )


def parent_fingerprints(
    stage: StageName,
    request: OrchestrationRequest,
    planned: list[str],
    outcomes: dict[str, StageOutcomeArtifact],
) -> dict[str, str]:
    parents = list(STAGE_DEPENDENCIES[stage])
    if stage == "artifact_packaging":
        if request.include_visuals and "visual_generation" in planned:
            parents.append("visual_generation")
        if request.include_audiobook and "audiobook_generation" in planned:
            parents.append("audiobook_generation")
    result: dict[str, str] = {}
    for parent in parents:
        lineage = dict((outcomes.get(parent).metadata if outcomes.get(parent) else {}).get("lineage") or {})
        value = str(lineage.get("lineage_fingerprint") or "")
        if value:
            result[parent] = value
    return result


def normalized_outcome_payload(outcome: StageOutcomeArtifact) -> dict[str, Any]:
    payload = outcome.model_dump(exclude={"attempt", "reused", "started_at", "completed_at", "elapsed_seconds"})
    metadata = dict(payload.get("metadata") or {})
    metadata.pop("lineage", None)
    payload["metadata"] = metadata
    return sanitize(payload)


def _stage_request_payload(stage: StageName, request: OrchestrationRequest) -> dict[str, Any]:
    limits = request.execution_limits
    common = {"series_id": request.series_id}
    if stage == "analysis_foundation":
        return {**common, "sources": [_source_identity(path) for path in request.source_paths]}
    if stage in {"canon_extraction", "character_world_modeling"}:
        return common
    if stage == "generation_planning":
        return {
            **common,
            "premise": request.premise,
            "target_audience": request.target_audience,
            "tone": request.tone,
            "desired_chapter_count": request.desired_chapter_count,
        }
    if stage == "narrative_generation":
        return {
            **common,
            "story_id": request.story_id,
            "blueprint_id": request.blueprint_id,
            "target_words_per_scene": limits.target_words_per_scene,
        }
    if stage == "narrative_support":
        return {**common, "story_id": request.story_id}
    if stage == "visual_generation":
        return {
            **common,
            "story_id": request.story_id,
            "include_types": limits.visual_include_types,
            "max_renders_per_type": limits.max_visual_renders_per_type,
            "max_attempts": request.max_attempts,
        }
    if stage == "audiobook_generation":
        return {
            **common,
            "story_id": request.story_id,
            "audiobook_run_id": request.audiobook_run_id,
            "max_chapters": limits.audiobook_max_chapters,
            "max_segment_chars": limits.audiobook_max_segment_chars,
            "max_attempts": request.max_attempts,
        }
    return {
        **common,
        "story_id": request.story_id,
        "include_visuals": request.include_visuals,
        "include_audiobook": request.include_audiobook,
    }


def _source_identity(value: str) -> dict[str, Any]:
    path = Path(value)
    if not path.is_file():
        return {"path": str(path), "available": False}
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(path.resolve()), "available": True, "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def _env(name: str, default: str) -> str:
    return str(os.getenv(name) or default).strip()


def _file_digest(relative_path: str) -> str:
    path = _REPO_ROOT / relative_path
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "missing"


def _combined_digest(relative_paths: list[str]) -> str:
    digest = hashlib.sha256()
    for relative_path in sorted(relative_paths):
        digest.update(relative_path.encode("utf-8"))
        digest.update(_file_digest(relative_path).encode("ascii"))
    return digest.hexdigest()
