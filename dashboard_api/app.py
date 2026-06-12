"""FastAPI backend for the local S.A.G.A. debug dashboard."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from services.dashboard_artifact_service import (
    ANALYSIS_OUTPUTS_DIR,
    build_contract_summary,
    discover_contract_files,
    discover_encode_runs,
    discover_identity_files,
    discover_prompt_pack_files,
    discover_report_files,
    discover_retrieval_context_files,
    discover_state_snapshot_files,
    discover_visual_world_state_files,
    read_json_file,
    read_text_file,
)
from infrastructure.neo4j_ingestion_service import Neo4jIngestionError, Neo4jIngestionService
from query.comfyui_prompt_pack_service import ComfyUIPromptPackService
from query.narrative_context_service import NarrativeContextService
from query.target_character_state_service import TargetCharacterStateService
from query.visual_world_state_service import VisualWorldStateService
from saga_tools import (
    DEFAULT_PRODUCTION_IDENTITY_PROVIDER,
    _apply_identity_provider_override,
    _artifact_snapshot,
    _compare_snapshots,
    _context_scores,
    _context_status,
    _dependency_rows,
    _focus_character_rows,
    _identity_summary,
    _inject_target_snapshot_context,
    _load_contracts_with_identity,
    _noise_diagnostics,
    _now_utc,
    _rebuild_outputs_for_validation,
    _relevant_documents,
    _relationship_rows_for_focus,
    _render_encoder_validation_markdown,
    _resolved_identity_json,
    _scene_schema_summary,
    _unresolved_thread_rows,
    _write_comfyui_curated_preview,
    _write_comfyui_prompt_pack_report,
    _write_comfyui_text_exports,
    _write_snapshot_report,
    _write_visual_world_state_report,
)
from services.narrative_generation_service import NarrativeGenerationService
from infrastructure.llm_client import LLMClient


def _encode_artifact_id(display_path: str) -> str:
    return base64.urlsafe_b64encode(display_path.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_artifact_id(artifact_id: str) -> str:
    padding = "=" * (-len(artifact_id) % 4)
    try:
        return base64.urlsafe_b64decode((artifact_id + padding).encode("ascii")).decode("utf-8")
    except Exception as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=400, detail=f"Invalid artifact id: {artifact_id}") from exc


def _safe_path_from_display(display_path: str) -> Path:
    candidate = (ANALYSIS_OUTPUTS_DIR.parent / display_path).resolve()
    root = ANALYSIS_OUTPUTS_DIR.parent.resolve()
    if root not in candidate.parents and candidate != root:
        raise HTTPException(status_code=400, detail="Artifact path escapes the project root.")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail=f"Artifact not found: {display_path}")
    return candidate


def _with_id(record: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(record)
    enriched["id"] = _encode_artifact_id(str(record["display_path"]))
    if isinstance(enriched.get("path"), Path):
        enriched["path"] = str(enriched["path"])
    if isinstance(enriched.get("status_path"), Path):
        enriched["status_path"] = str(enriched["status_path"])
    if isinstance(enriched.get("log_path"), Path):
        enriched["log_path"] = str(enriched["log_path"])
    for key in ("contract_paths", "report_paths"):
        if key in enriched:
            enriched[key] = [str(item) for item in enriched[key]]
    for key in ("started_at", "updated_at"):
        if key in enriched and enriched[key] is None:
            enriched[key] = ""
    if "modified_at" in enriched and hasattr(enriched["modified_at"], "isoformat"):
        enriched["modified_at"] = enriched["modified_at"].isoformat()
    return enriched


def _artifact_listing(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_with_id(record) for record in records]


def _write_json_file(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    if hasattr(value, "items"):
        try:
            return {str(key): _json_safe(item) for key, item in value.items()}
        except Exception:
            pass
    return str(value)


def _placeholder_response(name: str) -> dict[str, Any]:
    return {
        "implemented": False,
        "status": "not_implemented",
        "operation": name,
        "message": f"{name} is reserved for a later dashboard milestone.",
    }


class ExportJsonRequest(BaseModel):
    payload: Any
    file_name: str = Field(default="export.json", min_length=1)


class ValidateContractRequest(BaseModel):
    contract_id: str | None = None
    contract_path: str | None = None
    identity_provider: str = DEFAULT_PRODUCTION_IDENTITY_PROVIDER
    identity_json: str | None = None
    compare_contract_path: str | None = None
    out: str | None = None
    report_md: str | None = None


class TargetPointRequest(BaseModel):
    mode: str
    book_index: int | None = None
    chapter: int | None = None
    scene_id: str | None = None
    after_book_index: int | None = None
    include_future_facts: bool = False


class CharacterStateSnapshotRequest(BaseModel):
    contract_ids: list[str] = Field(default_factory=list)
    contract_paths: list[str] = Field(default_factory=list)
    target_point: TargetPointRequest
    identity_json: str | None = None
    focus_characters: list[str] = Field(default_factory=list)
    include_reference_entities: bool = False
    out: str | None = None
    report_md: str | None = None


class VisualWorldStateRequest(BaseModel):
    contract_ids: list[str] = Field(default_factory=list)
    contract_paths: list[str] = Field(default_factory=list)
    target_point: TargetPointRequest
    identity_json: str | None = None
    out: str | None = None
    report_md: str | None = None


class PromptPackRequest(BaseModel):
    visual_state_path: str
    contract_path: str | None = None
    mode: str = "full_prompt_pack"
    focus_characters: list[str] = Field(default_factory=list)
    focus_locations: list[str] = Field(default_factory=list)
    focus_entities: list[str] = Field(default_factory=list)
    scene_id: str = ""
    chapter: int = 0
    include_low_confidence: bool = False
    out: str | None = None
    report_md: str | None = None


class GenerationContextRequest(BaseModel):
    contract_ids: list[str] = Field(default_factory=list)
    contract_paths: list[str] = Field(default_factory=list)
    identity_json: str | None = None
    target_states_path: str | None = None
    target_point: TargetPointRequest
    prompt: str
    out: str | None = None
    report_md: str | None = None


class ConfigPresetSaveRequest(BaseModel):
    name: str
    values: dict[str, Any]


class BuildContextRequest(BaseModel):
    contract_ids: list[str] = Field(default_factory=list)
    contract_paths: list[str] = Field(default_factory=list)
    identity_json: str | None = None
    target_states_path: str | None = None
    target_point: TargetPointRequest | None = None
    include_visual_world_state: bool = False
    visual_world_state_path: str | None = None
    prompt: str = ""
    out: str | None = None


class GenerationControlsRequest(BaseModel):
    chapter_count: int | None = None
    canon_position: str | None = None
    primary_pov_character: str | None = None
    new_plot: str | None = None
    continuity_anchor: str | None = None
    anchor_after: str | None = None
    anchor_before: str | None = None
    divergence_anchor: str | None = None
    preserve_event_labels: list[str] = Field(default_factory=list)
    relationship_directions: list[str] = Field(default_factory=list)


class GenerateBlueprintRequest(BaseModel):
    contract_ids: list[str] = Field(default_factory=list)
    contract_paths: list[str] = Field(default_factory=list)
    identity_json: str | None = None
    prompt: str
    model_mode: str = LLMClient.MODE_GPT_OSS
    planner_model_mode: str | None = None
    prose_model_mode: str | None = None
    ollama_model: str | None = None
    planner_model: str | None = None
    prose_model: str | None = None
    prefer_exported_context: bool = True
    prefer_exported_blueprint: bool = True
    generation_controls: GenerationControlsRequest | None = None
    out: str | None = None


class GenerateOutlineRequest(GenerateBlueprintRequest):
    blueprint: dict[str, Any] | None = None
    chapter_number: int = 1


class GenerateSceneRequest(GenerateBlueprintRequest):
    chapter_outline: dict[str, Any]
    scene_outline: dict[str, Any]
    previous_scene_ending: str = ""
    scene_memory: dict[str, Any] | None = None


class GenerateProseRequest(GenerateSceneRequest):
    pass


class Neo4jSummaryRequest(BaseModel):
    series_id: str | None = None
    book_title: str | None = None


class Neo4jDeleteDryRunRequest(BaseModel):
    delete_type: str = Field(pattern="^(book|series)$")
    series_id: str
    book_title: str | None = None


class Neo4jDeleteConfirmRequest(Neo4jDeleteDryRunRequest):
    confirm_text: str


class Neo4jIngestRequest(BaseModel):
    contract_id: str | None = None
    contract_path: str | None = None
    replace_existing: bool = False


def _resolve_path_input(path_id: str | None, path_text: str | None) -> Path:
    if path_id:
        display_path = _decode_artifact_id(path_id)
        return _safe_path_from_display(display_path)
    if path_text:
        return _safe_path_from_display(path_text)
    raise HTTPException(status_code=400, detail="A contract or artifact id/path is required.")


def _resolve_many_paths(ids: list[str], paths: list[str]) -> list[Path]:
    resolved: list[Path] = []
    for path_id in ids or []:
        resolved.append(_resolve_path_input(path_id, None))
    for path_text in paths or []:
        resolved.append(_resolve_path_input(None, path_text))
    deduped: list[Path] = []
    seen: set[Path] = set()
    for item in resolved:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    if not deduped:
        raise HTTPException(status_code=400, detail="At least one contract path is required.")
    return deduped


def _operation_output_dir(name: str) -> Path:
    root = ANALYSIS_OUTPUTS_DIR / "dashboard" / "api_ops" / name
    root.mkdir(parents=True, exist_ok=True)
    return root


def _default_output_path(name: str, suffix: str) -> Path:
    timestamp = _now_utc().replace(":", "").replace("-", "")
    timestamp = timestamp.replace("+0000", "Z").replace("+00:00", "Z")
    return _operation_output_dir(name) / f"{name}_{timestamp}{suffix}"


def _args_namespace(**values: Any) -> SimpleNamespace:
    return SimpleNamespace(**values)


CONFIG_PRESETS_PATH = ANALYSIS_OUTPUTS_DIR / "dashboard" / "config_presets.json"


def _load_config_presets() -> list[dict[str, Any]]:
    if not CONFIG_PRESETS_PATH.exists():
        return [
            {
                "name": "ACOTAR Full BookNLP Clean",
                "analysis_model": "gpt_oss",
                "identity_model": "gpt_oss",
                "analysis_provider_mode": "same_provider_rotating",
                "identity_provider": "booknlp_clean",
                "scene_failure_policy": "fail_fast",
                "skip_ingest": True,
            },
            {
                "name": "Bounded Smoke Validation",
                "analysis_model": "gpt_oss",
                "identity_model": "gpt_oss",
                "analysis_provider_mode": "single_provider",
                "identity_provider": "booknlp_clean",
                "scene_failure_policy": "fail_fast",
                "skip_ingest": True,
            },
        ]
    return read_json_file(CONFIG_PRESETS_PATH)


def _save_config_presets(items: list[dict[str, Any]]) -> Path:
    return _write_json_file(CONFIG_PRESETS_PATH, items)


def _artifact_collection(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {"items": _artifact_listing(records)}


def _decoder_from_model_request(request: GenerateBlueprintRequest | GenerateOutlineRequest | GenerateSceneRequest) -> NarrativeGenerationService:
    base_mode = request.model_mode or LLMClient.MODE_GPT_OSS
    base_model = request.ollama_model or ""
    planner_mode = request.planner_model_mode or base_mode
    planner_model = request.planner_model or base_model
    prose_mode = request.prose_model_mode or base_mode
    prose_model = request.prose_model or base_model
    planner_llm = LLMClient(mode=planner_mode, ollama_model_override=planner_model)
    prose_llm = planner_llm if (planner_mode == prose_mode and planner_model == prose_model) else LLMClient(
        mode=prose_mode,
        ollama_model_override=prose_model,
    )
    try:
        return NarrativeGenerationService(
            llm_client=planner_llm,
            planner_llm_client=planner_llm,
            prose_llm_client=prose_llm,
        )
    except TypeError:
        return NarrativeGenerationService(llm_client=planner_llm)


def _generation_controls_payload(request_controls: GenerationControlsRequest | None, prompt: str) -> dict[str, Any]:
    controls = request_controls.model_dump() if request_controls else {}
    return {
        "chapter_count": controls.get("chapter_count"),
        "canon_position": controls.get("canon_position"),
        "primary_pov_character": controls.get("primary_pov_character"),
        "new_plot": controls.get("new_plot"),
        "continuity_anchor": controls.get("continuity_anchor"),
        "anchor_after": controls.get("anchor_after"),
        "anchor_before": controls.get("anchor_before"),
        "divergence_anchor": controls.get("divergence_anchor"),
        "canon_elements_to_preserve": controls.get("preserve_event_labels") or [],
        "relationship_directions": controls.get("relationship_directions") or [],
        "user_prompt": prompt,
    }


def _build_context_payload(request: BuildContextRequest | GenerateBlueprintRequest | GenerateOutlineRequest | GenerateSceneRequest) -> tuple[list[str], dict[str, Any]]:
    contract_paths = _resolve_many_paths(
        getattr(request, "contract_ids", []) or [],
        getattr(request, "contract_paths", []) or [],
    )
    args = _args_namespace(
        contract=[str(path) for path in contract_paths],
        identity_provider=DEFAULT_PRODUCTION_IDENTITY_PROVIDER,
        identity_json=getattr(request, "identity_json", "") or "",
        series_identity_json="",
    )
    contracts = _load_contracts_with_identity(args)
    context_service = NarrativeContextService()
    context = context_service.build_from_contracts(
        contracts,
        top_characters=50,
        top_threads=12,
        top_flexible_events=8,
        top_character_trajectories=12,
        identity_json_path=_resolved_identity_json(args) or None,
        contract_paths=args.contract,
    )
    target_states_path = getattr(request, "target_states_path", "") or ""
    if target_states_path:
        target_snapshot = read_json_file(_resolve_path_input(None, target_states_path))
        context = _inject_target_snapshot_context(
            context_service=context_service,
            context=context,
            snapshot_payload=target_snapshot,
            top_characters=50,
        )
    elif getattr(request, "target_point", None):
        target_snapshot = TargetCharacterStateService().build_character_state_snapshot(
            contract_paths=args.contract,
            target_point=request.target_point.model_dump(),
            identity_json_path=_resolved_identity_json(args) or None,
        )
        context = _inject_target_snapshot_context(
            context_service=context_service,
            context=context,
            snapshot_payload=target_snapshot,
            top_characters=50,
        )
    if getattr(request, "include_visual_world_state", False):
        visual_path = getattr(request, "visual_world_state_path", "") or ""
        if visual_path:
            context["visual_world_state"] = read_json_file(_resolve_path_input(None, visual_path))
    return args.contract, context


def _neo4j_service() -> Neo4jIngestionService:
    return Neo4jIngestionService()


def _neo4j_unavailable_payload(exc: Exception) -> dict[str, Any]:
    return {
        "implemented": True,
        "connected": False,
        "status": "unavailable",
        "message": str(exc),
    }


def _safe_neo4j_query(fn):
    try:
        return _json_safe(fn())
    except (Neo4jIngestionError, ValueError) as exc:
        return _neo4j_unavailable_payload(exc)


def _neo4j_probe_payload() -> dict[str, Any]:
    service = _neo4j_service()
    try:
        payload = service.probe_connection()
        return {"implemented": True, "connected": True, **payload}
    finally:
        service.close()


def _graph_summary(service: Neo4jIngestionService, *, series_id: str | None = None, book_title: str | None = None) -> dict[str, Any]:
    service.probe_connection()
    driver = service._ensure_driver()
    session_kwargs = {"database": service.database} if service.database else {}
    with driver.session(**session_kwargs) as session:
        filters = []
        params: dict[str, Any] = {}
        if series_id:
            filters.append("n.series_id = $series_id")
            params["series_id"] = series_id
        if book_title:
            filters.append("n.title = $book_title")
            params["book_title"] = book_title
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        counts = {}
        for label in ["Series", "Book", "Chapter", "Scene", "Entity", "Event", "StateTransition"]:
            row = session.run(
                f"MATCH (n:{label}) {where} RETURN count(n) AS count",
                **params,
            ).single()
            counts[label] = int((row.data() if row else {}).get("count") or 0)
        relationship_count = session.run(
            "MATCH ()-[r]->() RETURN count(r) AS count"
        ).single()
        counts["Relationships"] = int((relationship_count.data() if relationship_count else {}).get("count") or 0)
        return {
            "implemented": True,
            "connected": True,
            "status": "ok",
            "database": service.database,
            "uri": service.uri,
            "scope": {"series_id": series_id or "", "book_title": book_title or ""},
            "counts": counts,
        }


def _list_neo4j_series(service: Neo4jIngestionService) -> dict[str, Any]:
    service.probe_connection()
    driver = service._ensure_driver()
    session_kwargs = {"database": service.database} if service.database else {}
    with driver.session(**session_kwargs) as session:
        rows = [
            row.data()
            for row in session.run(
                """
                MATCH (s:Series)
                OPTIONAL MATCH (s)-[:HAS_BOOK]->(b:Book)
                RETURN s.series_id AS series_id,
                       s.title AS title,
                       count(DISTINCT b) AS book_count,
                       s.updated_at AS updated_at
                ORDER BY s.series_id ASC
                """
            )
        ]
    return {"implemented": True, "connected": True, "status": "ok", "items": rows}


def _list_neo4j_books(service: Neo4jIngestionService, *, series_id: str | None = None) -> dict[str, Any]:
    service.probe_connection()
    driver = service._ensure_driver()
    session_kwargs = {"database": service.database} if service.database else {}
    with driver.session(**session_kwargs) as session:
        query = """
            MATCH (b:Book)
            {where}
            RETURN b.series_id AS series_id,
                   b.book_index AS book_index,
                   b.title AS title,
                   b.ingested_at AS ingested_at,
                   b.analysis_model AS analysis_model,
                   b.identity_model AS identity_model
            ORDER BY b.series_id ASC, b.book_index ASC
        """
        params = {}
        where = ""
        if series_id:
            where = "WHERE b.series_id = $series_id"
            params["series_id"] = series_id
        rows = [row.data() for row in session.run(query.format(where=where), **params)]
    return {"implemented": True, "connected": True, "status": "ok", "items": rows}


def _delete_confirmation_required(payload: Neo4jDeleteConfirmRequest) -> str:
    if payload.delete_type == "series":
        return payload.series_id
    return f"{payload.series_id}:{payload.book_title or ''}"


def _neo4j_delete_dry_run(service: Neo4jIngestionService, payload: Neo4jDeleteDryRunRequest) -> dict[str, Any]:
    service.probe_connection()
    driver = service._ensure_driver()
    session_kwargs = {"database": service.database} if service.database else {}
    with driver.session(**session_kwargs) as session:
        if payload.delete_type == "series":
            counts = {
                "Series": session.run("MATCH (s:Series {series_id: $series_id}) RETURN count(s) AS count", series_id=payload.series_id).single().data()["count"],
                "Books": session.run("MATCH (b:Book {series_id: $series_id}) RETURN count(b) AS count", series_id=payload.series_id).single().data()["count"],
                "Chapters": session.run("MATCH (n:Chapter {series_id: $series_id}) RETURN count(n) AS count", series_id=payload.series_id).single().data()["count"],
                "Scenes": session.run("MATCH (n:Scene {series_id: $series_id}) RETURN count(n) AS count", series_id=payload.series_id).single().data()["count"],
                "Entities": session.run("MATCH (n:Entity {series_id: $series_id}) RETURN count(n) AS count", series_id=payload.series_id).single().data()["count"],
                "Events": session.run("MATCH (n:Event {series_id: $series_id}) RETURN count(n) AS count", series_id=payload.series_id).single().data()["count"],
                "StateTransitions": session.run("MATCH (n:StateTransition {series_id: $series_id}) RETURN count(n) AS count", series_id=payload.series_id).single().data()["count"],
            }
        else:
            if not payload.book_title:
                raise ValueError("book_title is required for book deletion.")
            book = service.lookup_book(payload.series_id, payload.book_title, session=session)
            if not book:
                raise ValueError(f"Book '{payload.book_title}' was not found in series '{payload.series_id}'.")
            book_index = book["book_index"]
            counts = {
                "Book": session.run("MATCH (b:Book {series_id: $series_id, title: $book_title}) RETURN count(b) AS count", series_id=payload.series_id, book_title=payload.book_title).single().data()["count"],
                "Chapters": session.run("MATCH (b:Book {series_id: $series_id, title: $book_title})-[:HAS_CHAPTER]->(n:Chapter) RETURN count(n) AS count", series_id=payload.series_id, book_title=payload.book_title).single().data()["count"],
                "Scenes": session.run("MATCH (b:Book {series_id: $series_id, title: $book_title})-[:HAS_CHAPTER]->(:Chapter)-[:HAS_SCENE]->(n:Scene) RETURN count(n) AS count", series_id=payload.series_id, book_title=payload.book_title).single().data()["count"],
                "Events": session.run("MATCH (b:Book {series_id: $series_id, title: $book_title})-[:HAS_EVENT]->(n:Event) RETURN count(n) AS count", series_id=payload.series_id, book_title=payload.book_title).single().data()["count"],
                "StateTransitions": session.run("MATCH (n:StateTransition {series_id: $series_id, book_index: $book_index}) RETURN count(n) AS count", series_id=payload.series_id, book_index=book_index).single().data()["count"],
            }
    return {
        "implemented": True,
        "connected": True,
        "status": "ok",
        "delete_type": payload.delete_type,
        "series_id": payload.series_id,
        "book_title": payload.book_title or "",
        "confirmation_required": _delete_confirmation_required(
            Neo4jDeleteConfirmRequest(**payload.model_dump(), confirm_text="")
        ),
        "dry_run": True,
        "would_delete": counts,
        "local_contracts_affected": False,
    }


def create_app() -> FastAPI:
    app = FastAPI(title="S.A.G.A. Debug Dashboard API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok"}

    @app.get("/api/overview")
    def overview() -> dict[str, Any]:
        runs = discover_encode_runs()
        contracts = discover_contract_files()
        reports = discover_report_files()
        identities = discover_identity_files()
        state_snapshots = discover_state_snapshot_files()
        visual_states = discover_visual_world_state_files()
        prompt_packs = discover_prompt_pack_files()
        retrieval_contexts = discover_retrieval_context_files()
        latest_run = _with_id(runs[0]) if runs else None
        total_scenes = 0
        failed_scenes = 0
        for contract_record in contracts:
            try:
                contract = read_json_file(contract_record["path"])
            except Exception:
                continue
            outputs = contract.get("outputs") or {}
            scene_rows = outputs.get("scene_analyses") or outputs.get("resolved_scene_analyses") or []
            total_scenes += len(scene_rows)
            failed_scenes += sum(1 for scene in scene_rows if scene.get("error") or scene.get("final_status") == "failed")

        return {
            "latest_run": latest_run,
            "run_count": len(runs),
            "contract_count": len(contracts),
            "report_count": len(reports),
            "identity_file_count": len(identities),
            "state_snapshot_count": len(state_snapshots),
            "visual_world_state_count": len(visual_states),
            "prompt_pack_count": len(prompt_packs),
            "retrieval_context_count": len(retrieval_contexts),
            "total_scenes": total_scenes,
            "failed_scenes": failed_scenes,
            "identity_provider_status": "booknlp_clean",
            "neo4j_status": _safe_neo4j_query(_neo4j_probe_payload),
        }

    @app.get("/api/runs")
    def list_runs() -> dict[str, Any]:
        return {"items": _artifact_listing(discover_encode_runs())}

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        target_display = _decode_artifact_id(run_id)
        for record in discover_encode_runs():
            if str(record["display_path"]) == target_display:
                return _with_id(record)
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    @app.get("/api/contracts")
    def list_contracts() -> dict[str, Any]:
        items = []
        for record in discover_contract_files():
            item = _with_id(record)
            try:
                contract = read_json_file(record["path"])
                item["summary"] = build_contract_summary(contract)
            except Exception as exc:
                item["error"] = repr(exc)
            items.append(item)
        return {"items": items}

    @app.get("/api/contracts/{contract_id}")
    def get_contract(contract_id: str) -> dict[str, Any]:
        display_path = _decode_artifact_id(contract_id)
        path = _safe_path_from_display(display_path)
        contract = read_json_file(path)
        return {
            "id": contract_id,
            "display_path": display_path,
            "summary": build_contract_summary(contract),
            "payload": contract,
        }

    @app.get("/api/reports")
    def list_reports() -> dict[str, Any]:
        return {"items": _artifact_listing(discover_report_files())}

    @app.get("/api/reports/{report_id}")
    def get_report(report_id: str) -> dict[str, Any]:
        display_path = _decode_artifact_id(report_id)
        path = _safe_path_from_display(display_path)
        if path.suffix.lower() == ".json":
            content: Any = read_json_file(path)
            content_type = "json"
        else:
            content = read_text_file(path)
            content_type = "text"
        return {
            "id": report_id,
            "display_path": display_path,
            "content_type": content_type,
            "content": content,
        }

    @app.get("/api/identities")
    def list_identities() -> dict[str, Any]:
        return _artifact_collection(discover_identity_files())

    @app.get("/api/state-snapshots")
    def list_state_snapshots() -> dict[str, Any]:
        return _artifact_collection(discover_state_snapshot_files())

    @app.get("/api/visual-world-states")
    def list_visual_world_states() -> dict[str, Any]:
        return _artifact_collection(discover_visual_world_state_files())

    @app.get("/api/prompt-packs")
    def list_prompt_packs() -> dict[str, Any]:
        return _artifact_collection(discover_prompt_pack_files())

    @app.get("/api/retrieval-contexts")
    def list_retrieval_contexts() -> dict[str, Any]:
        return _artifact_collection(discover_retrieval_context_files())

    @app.post("/api/export/json")
    def export_json(request: ExportJsonRequest) -> dict[str, Any]:
        content = json.dumps(request.payload, ensure_ascii=False, indent=2)
        return {"file_name": request.file_name, "content": content}

    @app.post("/api/validate-contract")
    def validate_contract(request: ValidateContractRequest) -> dict[str, Any]:
        contract_path = _resolve_path_input(request.contract_id, request.contract_path)
        contract = read_json_file(contract_path)
        working_contract = contract
        validation_mode = "contract_only"
        args = _args_namespace(
            identity_provider=request.identity_provider,
            identity_json=request.identity_json or "",
            series_identity_json="",
        )
        if request.identity_provider == DEFAULT_PRODUCTION_IDENTITY_PROVIDER:
            working_contract = _apply_identity_provider_override(dict(contract), args)
            validation_mode = "provider_override_rebuild"
        rebuilt_outputs = _rebuild_outputs_for_validation(working_contract)
        artifact_snapshot = _artifact_snapshot(rebuilt_outputs)
        scene_schema = _scene_schema_summary(rebuilt_outputs.get("resolved_scene_analyses") or [])
        identity_summary = _identity_summary(rebuilt_outputs)
        dependency_rows = _dependency_rows(rebuilt_outputs, scene_schema)
        root_cause = {"classification": "", "reason": "", "minimum_fix": ""}
        dominant_error = scene_schema.get("dominant_error") or ""
        error_scene_count = int(scene_schema.get("error_scene_count") or 0)
        scene_count = int(scene_schema.get("scene_count") or 0)
        error_ratio = (error_scene_count / scene_count) if scene_count else 0.0
        if dominant_error and error_ratio >= 0.25:
            if "max_retries_exceeded" in dominant_error or "rate" in dominant_error.lower():
                root_cause = {
                    "classification": "model output quality issue",
                    "reason": f"Scene analyses degraded into error shells because the analyzer hit provider exhaustion: {dominant_error}",
                    "minimum_fix": "Resume later with the same provider/model budget before any broader series pass.",
                }
            else:
                root_cause = {
                    "classification": "scene analyzer missing fields",
                    "reason": f"Resolved scenes contain dominant analyzer errors instead of structured content: {dominant_error}",
                    "minimum_fix": "Fix analyzer reliability so scenes emit usable structured fields.",
                }
        elif int((artifact_snapshot.get("timeline") or {}).get("count") or 0) == 0:
            root_cause = {
                "classification": "scene analyzer missing fields",
                "reason": "Scenes exist, but they do not carry events, so timeline/event ledger/profile builders have no material to work with.",
                "minimum_fix": "Fix scene analysis event extraction before scaling the encoder.",
            }
        elif int((artifact_snapshot.get("stable_character_states") or {}).get("count") or 0) <= 1:
            root_cause = {
                "classification": "builder filtering too aggressively",
                "reason": "Stable character states are much thinner than profiles because the stable-state builder remains conservative.",
                "minimum_fix": "Audit whether target-aware state snapshots are sufficient or improve stable-state promotion later.",
            }
        comparison_snapshot = None
        if request.compare_contract_path:
            compare_contract = read_json_file(_resolve_path_input(None, request.compare_contract_path))
            compare_outputs = _rebuild_outputs_for_validation(compare_contract)
            comparison_snapshot = _compare_snapshots(_artifact_snapshot(compare_outputs), artifact_snapshot)
        payload = {
            "generated_at_utc": _now_utc(),
            "contract_path": str(contract_path),
            "validation_mode": validation_mode,
            "identity_provider": request.identity_provider,
            "artifact_snapshot": artifact_snapshot,
            "scene_schema": scene_schema,
            "identity_summary": identity_summary,
            "dependency_rows": dependency_rows,
            "comparison_snapshot": comparison_snapshot,
            "root_cause": root_cause,
        }
        out_path = Path(request.out) if request.out else _default_output_path("validate_contract", ".json")
        report_path = Path(request.report_md) if request.report_md else out_path.with_suffix(".md")
        _write_json_file(out_path, payload)
        report_path.write_text(_render_encoder_validation_markdown(payload), encoding="utf-8")
        return {"status": "ok", "output_path": str(out_path), "report_path": str(report_path), "payload": payload}

    @app.post("/api/build-character-state-snapshot")
    def build_character_state_snapshot(request: CharacterStateSnapshotRequest) -> dict[str, Any]:
        contract_paths = _resolve_many_paths(request.contract_ids, request.contract_paths)
        service = TargetCharacterStateService()
        payload = service.build_character_state_snapshot(
            contract_paths=contract_paths,
            target_point=request.target_point.model_dump(),
            identity_json_path=request.identity_json or None,
            character_ids=list(request.focus_characters or []),
            include_reference_entities=request.include_reference_entities,
        )
        out_path = Path(request.out) if request.out else _default_output_path("character_state_snapshot", ".json")
        report_path = Path(request.report_md) if request.report_md else out_path.with_suffix(".md")
        _write_json_file(out_path, payload)
        _write_snapshot_report(report_path, payload)
        return {"status": "ok", "output_path": str(out_path), "report_path": str(report_path), "payload": payload}

    @app.post("/api/build-visual-world-state")
    def build_visual_world_state(request: VisualWorldStateRequest) -> dict[str, Any]:
        contract_paths = _resolve_many_paths(request.contract_ids, request.contract_paths)
        service = VisualWorldStateService()
        payload = service.build_visual_world_state(
            contract_paths=contract_paths,
            target_point=request.target_point.model_dump(),
            identity_json_path=request.identity_json or None,
        )
        out_path = Path(request.out) if request.out else _default_output_path("visual_world_state", ".json")
        report_path = Path(request.report_md) if request.report_md else out_path.with_suffix(".md")
        _write_json_file(out_path, payload)
        _write_visual_world_state_report(report_path, payload)
        return {"status": "ok", "output_path": str(out_path), "report_path": str(report_path), "payload": payload}

    @app.post("/api/build-comfyui-prompt-pack")
    def build_comfyui_prompt_pack(request: PromptPackRequest) -> dict[str, Any]:
        visual_state_path = _resolve_path_input(None, request.visual_state_path)
        contract_path = _resolve_path_input(None, request.contract_path).resolve() if request.contract_path else None
        service = ComfyUIPromptPackService()
        payload = service.build_from_json_path(
            visual_state_path=visual_state_path,
            contract_path=str(contract_path) if contract_path else None,
            mode=request.mode,
            focus_characters=list(request.focus_characters or []),
            focus_locations=list(request.focus_locations or []),
            focus_entities=list(request.focus_entities or []),
            scene_id=request.scene_id,
            chapter=request.chapter,
            include_low_confidence=request.include_low_confidence,
        )
        out_path = Path(request.out) if request.out else _default_output_path("comfyui_prompt_pack", ".json")
        report_path = Path(request.report_md) if request.report_md else out_path.with_suffix(".md")
        _write_json_file(out_path, payload)
        _write_comfyui_prompt_pack_report(report_path, payload)
        return {"status": "ok", "output_path": str(out_path), "report_path": str(report_path), "payload": payload}

    @app.post("/api/validate-generation-context")
    def validate_generation_context(request: GenerationContextRequest) -> dict[str, Any]:
        contract_paths = _resolve_many_paths(request.contract_ids, request.contract_paths)
        args = _args_namespace(
            contract=[str(path) for path in contract_paths],
            identity_provider=DEFAULT_PRODUCTION_IDENTITY_PROVIDER,
            identity_json=request.identity_json or "",
            series_identity_json="",
        )
        contracts = _load_contracts_with_identity(args)
        context_service = NarrativeContextService()
        default_context = context_service.build_from_contracts(
            contracts,
            top_characters=50,
            top_threads=12,
            top_flexible_events=8,
            top_character_trajectories=12,
            identity_json_path=_resolved_identity_json(args) or None,
            contract_paths=args.contract,
        )
        target_snapshot = (
            read_json_file(_resolve_path_input(None, request.target_states_path))
            if request.target_states_path
            else TargetCharacterStateService().build_character_state_snapshot(
                contract_paths=args.contract,
                target_point=request.target_point.model_dump(),
                identity_json_path=_resolved_identity_json(args) or None,
            )
        )
        target_context = _inject_target_snapshot_context(
            context_service=context_service,
            context=default_context,
            snapshot_payload=target_snapshot,
            top_characters=50,
        )
        default_scores = _context_scores(default_context)
        target_scores = _context_scores(target_context)
        payload = {
            "contracts_used": list(args.contract),
            "identity_file_used": _resolved_identity_json(args) or "",
            "target_states_used": str(request.target_states_path or ""),
            "prompt": request.prompt,
            "default_context": {
                "stats": default_context.get("stats") or {},
                "meta": default_context.get("meta") or {},
                "scores": default_scores,
                "status": _context_status(default_scores),
            },
            "target_context": {
                "stats": target_context.get("stats") or {},
                "meta": target_context.get("meta") or {},
                "scores": target_scores,
                "status": _context_status(target_scores),
            },
            "focus_character_coverage": _focus_character_rows(target_context),
            "relationship_coverage": _relationship_rows_for_focus(target_context),
            "unresolved_plot_threads": _unresolved_thread_rows(target_context),
            "noise_diagnostics": _noise_diagnostics(target_context),
            "relevant_documents": _relevant_documents(target_context, limit=20),
            "target_context_payload": target_context,
        }
        out_path = Path(request.out) if request.out else _default_output_path("generation_context_validation", ".json")
        report_path = Path(request.report_md) if request.report_md else out_path.with_suffix(".md")
        _write_json_file(out_path, payload)
        report_lines = [
            "# Generation Context Validation",
            "",
            f"- Contracts used: `{len(args.contract)}`",
            f"- Identity file used: `{payload['identity_file_used']}`",
            f"- Target states used: `{payload['target_states_used']}`",
            f"- Default status: `{payload['default_context']['status']}`",
            f"- Target-aware status: `{payload['target_context']['status']}`",
            "",
            "## Focus Character Coverage",
            "",
            "| focus_name | present | resolved_name | confidence |",
            "|---|---|---|---|",
        ]
        for row in payload["focus_character_coverage"]:
            report_lines.append(
                f"| {row['focus_name']} | {row['present']} | {row['resolved_name']} | {row['confidence']} |"
            )
        report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
        return {"status": "ok", "output_path": str(out_path), "report_path": str(report_path), "payload": payload}

    @app.get("/api/config/presets")
    def config_presets() -> dict[str, Any]:
        return {"items": _load_config_presets()}

    @app.post("/api/config/presets")
    def save_config_preset(request: ConfigPresetSaveRequest) -> dict[str, Any]:
        items = [item for item in _load_config_presets() if item.get("name") != request.name]
        items.append({"name": request.name, **request.values})
        _save_config_presets(items)
        return {"status": "ok", "items": items}

    @app.post("/api/build-context")
    def build_context(request: BuildContextRequest) -> dict[str, Any]:
        contract_paths, context = _build_context_payload(request)
        out_path = Path(request.out) if request.out else _default_output_path("build_context", ".json")
        _write_json_file(out_path, context)
        return {"status": "ok", "output_path": str(out_path), "contract_paths": contract_paths, "payload": context}

    @app.post("/api/generate-blueprint")
    def generate_blueprint(request: GenerateBlueprintRequest) -> dict[str, Any]:
        contract_paths, retrieval_context = _build_context_payload(
            BuildContextRequest(
                contract_ids=request.contract_ids,
                contract_paths=request.contract_paths,
                identity_json=request.identity_json,
                prompt=request.prompt,
            )
        )
        decoder = _decoder_from_model_request(request)
        controls = _generation_controls_payload(request.generation_controls, request.prompt)
        compiled = decoder.compile_context(retrieval_context, request.prompt, generation_controls=controls)
        blueprint = decoder.generate_blueprint(compiled)
        out_path = Path(request.out) if request.out else _default_output_path("blueprint", ".json")
        payload = {"retrieval_context": retrieval_context, "compiled_context": compiled, "blueprint": blueprint}
        _write_json_file(out_path, payload)
        return {"status": "ok", "output_path": str(out_path), "contract_paths": contract_paths, "payload": payload}

    @app.post("/api/generate-outline")
    def generate_outline(request: GenerateOutlineRequest) -> dict[str, Any]:
        contract_paths, retrieval_context = _build_context_payload(
            BuildContextRequest(
                contract_ids=request.contract_ids,
                contract_paths=request.contract_paths,
                identity_json=request.identity_json,
                prompt=request.prompt,
            )
        )
        decoder = _decoder_from_model_request(request)
        controls = _generation_controls_payload(request.generation_controls, request.prompt)
        compiled = decoder.compile_context(retrieval_context, request.prompt, generation_controls=controls)
        blueprint = request.blueprint or decoder.generate_blueprint(compiled)
        world_state = decoder.initialise_world_state(compiled)
        outline = decoder.generate_chapter_outline(
            blueprint=blueprint,
            compiled_context=compiled,
            world_state=world_state,
            previous_summaries=[],
            chapter_number=request.chapter_number,
        )
        out_path = Path(request.out) if request.out else _default_output_path("outline", ".json")
        payload = {"compiled_context": compiled, "blueprint": blueprint, "chapter_outline": outline}
        _write_json_file(out_path, payload)
        return {"status": "ok", "output_path": str(out_path), "contract_paths": contract_paths, "payload": payload}

    @app.post("/api/generate-scene")
    def generate_scene(request: GenerateSceneRequest) -> dict[str, Any]:
        contract_paths, retrieval_context = _build_context_payload(
            BuildContextRequest(
                contract_ids=request.contract_ids,
                contract_paths=request.contract_paths,
                identity_json=request.identity_json,
                prompt=request.prompt,
            )
        )
        decoder = _decoder_from_model_request(request)
        controls = _generation_controls_payload(request.generation_controls, request.prompt)
        compiled = decoder.compile_context(retrieval_context, request.prompt, generation_controls=controls)
        world_state = decoder.initialise_world_state(compiled)
        prose = decoder.generate_scene_prose(
            scene_outline=request.scene_outline,
            chapter_outline=request.chapter_outline,
            world_state=world_state,
            previous_scene_ending=request.previous_scene_ending,
            book_title=compiled.get("book_title", "Unknown"),
            scene_memory=request.scene_memory or {},
            generation_controls=controls,
        )
        out_path = Path(request.out) if request.out else _default_output_path("scene", ".json")
        payload = {
            "compiled_context": compiled,
            "chapter_outline": request.chapter_outline,
            "scene_outline": request.scene_outline,
            "prose": prose,
        }
        _write_json_file(out_path, payload)
        return {"status": "ok", "output_path": str(out_path), "contract_paths": contract_paths, "payload": payload}

    @app.post("/api/generate-prose")
    def generate_prose(request: GenerateProseRequest) -> dict[str, Any]:
        return generate_scene(request)

    @app.get("/api/neo4j/status")
    def neo4j_status() -> dict[str, Any]:
        return _safe_neo4j_query(lambda: {"implemented": True, "connected": True, **_neo4j_service().probe_connection()})

    @app.get("/api/neo4j/series")
    def neo4j_series() -> dict[str, Any]:
        return _safe_neo4j_query(lambda: _list_neo4j_series(_neo4j_service()))

    @app.get("/api/neo4j/books")
    def neo4j_books(series_id: str | None = None) -> dict[str, Any]:
        return _safe_neo4j_query(lambda: _list_neo4j_books(_neo4j_service(), series_id=series_id))

    @app.get("/api/neo4j/summary")
    def neo4j_summary(series_id: str | None = None, book_title: str | None = None) -> dict[str, Any]:
        return _safe_neo4j_query(lambda: _graph_summary(_neo4j_service(), series_id=series_id, book_title=book_title))

    @app.post("/api/neo4j/delete/dry-run")
    def neo4j_delete_dry_run(request: Neo4jDeleteDryRunRequest) -> dict[str, Any]:
        return _safe_neo4j_query(lambda: _neo4j_delete_dry_run(_neo4j_service(), request))

    @app.post("/api/neo4j/ingest")
    def neo4j_ingest(request: Neo4jIngestRequest) -> dict[str, Any]:
        contract_path = _resolve_path_input(request.contract_id, request.contract_path)
        payload = read_json_file(contract_path)

        def _ingest() -> dict[str, Any]:
            service = _neo4j_service()
            try:
                preflight = service.probe_connection()
                result = service.ingest_contract(payload, replace_existing=request.replace_existing)
            finally:
                service.close()
            return {
                "implemented": True,
                "connected": True,
                "status": "ok",
                "contract_path": str(contract_path),
                "neo4j_preflight": preflight,
                "result": result,
            }

        return _safe_neo4j_query(_ingest)

    @app.post("/api/neo4j/delete/confirm")
    def neo4j_delete_confirm(request: Neo4jDeleteConfirmRequest) -> dict[str, Any]:
        required = _delete_confirmation_required(request)
        if request.confirm_text.strip() != required:
            raise HTTPException(
                status_code=400,
                detail=f"Confirmation text mismatch. Type exactly: {required}",
            )

        def _confirm() -> dict[str, Any]:
            service = _neo4j_service()
            dry_run = _neo4j_delete_dry_run(service, request)
            if request.delete_type == "series":
                service.purge_series_residue(request.series_id)
                driver = service._ensure_driver()
                session_kwargs = {"database": service.database} if service.database else {}
                with driver.session(**session_kwargs) as session:
                    session.run("MATCH (s:Series {series_id: $series_id}) DETACH DELETE s", series_id=request.series_id)
            else:
                service.remove_book(request.series_id, request.book_title or "")
            return {
                "implemented": True,
                "connected": True,
                "status": "ok",
                "delete_type": request.delete_type,
                "series_id": request.series_id,
                "book_title": request.book_title or "",
                "confirmed": True,
                "deleted": dry_run["would_delete"],
                "local_contracts_affected": False,
            }

        return _safe_neo4j_query(_confirm)

    stub_posts = [
        "/api/analysis/run",
        "/api/decoder/run",
    ]
    for route_path in stub_posts:
        route_name = route_path.replace("/api/", "")

        @app.post(route_path)
        def _stub_post(name: str = route_name) -> dict[str, Any]:
            return _placeholder_response(name)

    stub_gets = {
    }
    for route_path, route_name in stub_gets.items():
        @app.get(route_path)
        def _stub_get(name: str = route_name) -> dict[str, Any]:
            return _placeholder_response(name)

    return app


app = create_app()
