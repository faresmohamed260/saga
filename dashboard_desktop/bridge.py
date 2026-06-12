from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dashboard_api.app import (
    BuildContextRequest,
    CharacterStateSnapshotRequest,
    ConfigPresetSaveRequest,
    ExportJsonRequest,
    GenerateBlueprintRequest,
    GenerateOutlineRequest,
    GenerateProseRequest,
    GenerateSceneRequest,
    GenerationContextRequest,
    Neo4jDeleteConfirmRequest,
    Neo4jDeleteDryRunRequest,
    Neo4jIngestRequest,
    PromptPackRequest,
    ValidateContractRequest,
    VisualWorldStateRequest,
    _apply_identity_provider_override,
    _args_namespace,
    _artifact_collection,
    _artifact_listing,
    _artifact_snapshot,
    _build_context_payload,
    _compare_snapshots,
    _context_scores,
    _context_status,
    _decoder_from_model_request,
    _default_output_path,
    _delete_confirmation_required,
    _dependency_rows,
    _focus_character_rows,
    _generation_controls_payload,
    _graph_summary,
    _identity_summary,
    _inject_target_snapshot_context,
    _json_safe,
    _list_neo4j_books,
    _list_neo4j_series,
    _load_config_presets,
    _neo4j_delete_dry_run,
    _neo4j_probe_payload,
    _neo4j_service,
    _noise_diagnostics,
    _now_utc,
    _rebuild_outputs_for_validation,
    _relevant_documents,
    _relationship_rows_for_focus,
    _render_encoder_validation_markdown,
    _resolved_identity_json,
    _resolve_many_paths,
    _resolve_path_input,
    _safe_neo4j_query,
    _save_config_presets,
    _scene_schema_summary,
    _unresolved_thread_rows,
    _with_id,
    _write_comfyui_prompt_pack_report,
    _write_json_file,
    _write_snapshot_report,
    _write_visual_world_state_report,
    DEFAULT_PRODUCTION_IDENTITY_PROVIDER,
)
from infrastructure.llm_client import LLMClient
from infrastructure.neo4j_ingestion_service import Neo4jIngestionService
from query.comfyui_prompt_pack_service import ComfyUIPromptPackService
from query.narrative_context_service import NarrativeContextService
from query.target_character_state_service import TargetCharacterStateService
from query.visual_world_state_service import VisualWorldStateService
from saga_tools import (
    _artifact_snapshot as _saga_artifact_snapshot,
    _compare_snapshots as _saga_compare_snapshots,
    _context_scores as _saga_context_scores,
    _context_status as _saga_context_status,
    _dependency_rows as _saga_dependency_rows,
    _focus_character_rows as _saga_focus_character_rows,
    _identity_summary as _saga_identity_summary,
    _inject_target_snapshot_context as _saga_inject_target_snapshot_context,
    _load_contracts_with_identity,
    _noise_diagnostics as _saga_noise_diagnostics,
    _relevant_documents as _saga_relevant_documents,
    _relationship_rows_for_focus as _saga_relationship_rows_for_focus,
    _resolved_identity_json as _saga_resolved_identity_json,
    _scene_schema_summary as _saga_scene_schema_summary,
    _unresolved_thread_rows as _saga_unresolved_thread_rows,
)
from services.dashboard_artifact_service import (
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


class DashboardBridge:
    def getHealth(self) -> dict[str, Any]:
        return {"status": "ok"}

    def getOverview(self) -> dict[str, Any]:
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

        return _json_safe(
            {
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
        )

    def getRuns(self) -> dict[str, Any]:
        return _artifact_collection(discover_encode_runs())

    def getContracts(self) -> dict[str, Any]:
        items = []
        for record in discover_contract_files():
            item = _with_id(record)
            try:
                contract = read_json_file(record["path"])
                item["summary"] = build_contract_summary(contract)
            except Exception as exc:
                item["error"] = repr(exc)
            items.append(item)
        return _json_safe({"items": items})

    def getContract(self, contractId: str) -> dict[str, Any]:
        path = _resolve_path_input(contractId, None)
        contract = read_json_file(path)
        return _json_safe(
            {
                "id": contractId,
                "display_path": str(path.relative_to(path.parents[2])),
                "summary": build_contract_summary(contract),
                "payload": contract,
            }
        )

    def getReports(self) -> dict[str, Any]:
        return _artifact_collection(discover_report_files())

    def getReport(self, reportId: str) -> dict[str, Any]:
        path = _resolve_path_input(reportId, None)
        if path.suffix.lower() == ".json":
            content: Any = read_json_file(path)
            content_type = "json"
        else:
            content = read_text_file(path)
            content_type = "text"
        return _json_safe(
            {
                "id": reportId,
                "display_path": str(path.relative_to(path.parents[2])),
                "content_type": content_type,
                "content": content,
            }
        )

    def getPresets(self) -> dict[str, Any]:
        return {"items": _load_config_presets()}

    def savePreset(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = ConfigPresetSaveRequest(**payload)
        items = [item for item in _load_config_presets() if item.get("name") != request.name]
        items.append({"name": request.name, **request.values})
        _save_config_presets(items)
        return {"status": "ok", "items": items}

    def getIdentities(self) -> dict[str, Any]:
        return _artifact_collection(discover_identity_files())

    def getStateSnapshots(self) -> dict[str, Any]:
        return _artifact_collection(discover_state_snapshot_files())

    def getVisualWorldStates(self) -> dict[str, Any]:
        return _artifact_collection(discover_visual_world_state_files())

    def getPromptPacks(self) -> dict[str, Any]:
        return _artifact_collection(discover_prompt_pack_files())

    def getRetrievalContexts(self) -> dict[str, Any]:
        return _artifact_collection(discover_retrieval_context_files())

    def exportJson(self, payload: Any, fileName: str) -> dict[str, Any]:
        request = ExportJsonRequest(payload=payload, file_name=fileName)
        content = json.dumps(request.payload, ensure_ascii=False, indent=2)
        return {"file_name": request.file_name, "content": content}

    def validateContract(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = ValidateContractRequest(**payload)
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
        artifact_snapshot = _saga_artifact_snapshot(rebuilt_outputs)
        scene_schema = _saga_scene_schema_summary(rebuilt_outputs.get("resolved_scene_analyses") or [])
        identity_summary = _saga_identity_summary(rebuilt_outputs)
        dependency_rows = _saga_dependency_rows(rebuilt_outputs, scene_schema)
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
            comparison_snapshot = _saga_compare_snapshots(_saga_artifact_snapshot(compare_outputs), artifact_snapshot)
        response_payload = {
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
        _write_json_file(out_path, response_payload)
        report_path.write_text(_render_encoder_validation_markdown(response_payload), encoding="utf-8")
        return _json_safe({"status": "ok", "output_path": str(out_path), "report_path": str(report_path), "payload": response_payload})

    def buildCharacterStateSnapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = CharacterStateSnapshotRequest(**payload)
        contract_paths = _resolve_many_paths(request.contract_ids, request.contract_paths)
        service = TargetCharacterStateService()
        response_payload = service.build_character_state_snapshot(
            contract_paths=contract_paths,
            target_point=request.target_point.model_dump(),
            identity_json_path=request.identity_json or None,
            character_ids=list(request.focus_characters or []),
            include_reference_entities=request.include_reference_entities,
        )
        out_path = Path(request.out) if request.out else _default_output_path("character_state_snapshot", ".json")
        report_path = Path(request.report_md) if request.report_md else out_path.with_suffix(".md")
        _write_json_file(out_path, response_payload)
        _write_snapshot_report(report_path, response_payload)
        return _json_safe({"status": "ok", "output_path": str(out_path), "report_path": str(report_path), "payload": response_payload})

    def buildVisualWorldState(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = VisualWorldStateRequest(**payload)
        contract_paths = _resolve_many_paths(request.contract_ids, request.contract_paths)
        service = VisualWorldStateService()
        response_payload = service.build_visual_world_state(
            contract_paths=contract_paths,
            target_point=request.target_point.model_dump(),
            identity_json_path=request.identity_json or None,
        )
        out_path = Path(request.out) if request.out else _default_output_path("visual_world_state", ".json")
        report_path = Path(request.report_md) if request.report_md else out_path.with_suffix(".md")
        _write_json_file(out_path, response_payload)
        _write_visual_world_state_report(report_path, response_payload)
        return _json_safe({"status": "ok", "output_path": str(out_path), "report_path": str(report_path), "payload": response_payload})

    def buildComfyuiPromptPack(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = PromptPackRequest(**payload)
        visual_state_path = _resolve_path_input(None, request.visual_state_path)
        contract_path = _resolve_path_input(None, request.contract_path).resolve() if request.contract_path else None
        service = ComfyUIPromptPackService()
        response_payload = service.build_from_json_path(
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
        _write_json_file(out_path, response_payload)
        _write_comfyui_prompt_pack_report(report_path, response_payload)
        return _json_safe({"status": "ok", "output_path": str(out_path), "report_path": str(report_path), "payload": response_payload})

    def validateGenerationContext(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = GenerationContextRequest(**payload)
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
            identity_json_path=_saga_resolved_identity_json(args) or None,
            contract_paths=args.contract,
        )
        target_snapshot = (
            read_json_file(_resolve_path_input(None, request.target_states_path))
            if request.target_states_path
            else TargetCharacterStateService().build_character_state_snapshot(
                contract_paths=args.contract,
                target_point=request.target_point.model_dump(),
                identity_json_path=_saga_resolved_identity_json(args) or None,
            )
        )
        target_context = _saga_inject_target_snapshot_context(
            context_service=context_service,
            context=default_context,
            snapshot_payload=target_snapshot,
            top_characters=50,
        )
        default_scores = _saga_context_scores(default_context)
        target_scores = _saga_context_scores(target_context)
        response_payload = {
            "contracts_used": list(args.contract),
            "identity_file_used": _saga_resolved_identity_json(args) or "",
            "target_states_used": str(request.target_states_path or ""),
            "prompt": request.prompt,
            "default_context": {
                "stats": default_context.get("stats") or {},
                "meta": default_context.get("meta") or {},
                "scores": default_scores,
                "status": _saga_context_status(default_scores),
            },
            "target_context": {
                "stats": target_context.get("stats") or {},
                "meta": target_context.get("meta") or {},
                "scores": target_scores,
                "status": _saga_context_status(target_scores),
            },
            "focus_character_coverage": _saga_focus_character_rows(target_context),
            "relationship_coverage": _saga_relationship_rows_for_focus(target_context),
            "unresolved_plot_threads": _saga_unresolved_thread_rows(target_context),
            "noise_diagnostics": _saga_noise_diagnostics(target_context),
            "relevant_documents": _saga_relevant_documents(target_context, limit=20),
            "target_context_payload": target_context,
        }
        out_path = Path(request.out) if request.out else _default_output_path("generation_context_validation", ".json")
        report_path = Path(request.report_md) if request.report_md else out_path.with_suffix(".md")
        _write_json_file(out_path, response_payload)
        report_lines = [
            "# Generation Context Validation",
            "",
            f"- Contracts used: `{len(args.contract)}`",
            f"- Identity file used: `{response_payload['identity_file_used']}`",
            f"- Target states used: `{response_payload['target_states_used']}`",
            f"- Default status: `{response_payload['default_context']['status']}`",
            f"- Target-aware status: `{response_payload['target_context']['status']}`",
            "",
            "## Focus Character Coverage",
            "",
            "| focus_name | present | resolved_name | confidence |",
            "|---|---|---|---|",
        ]
        for row in response_payload["focus_character_coverage"]:
            report_lines.append(f"| {row['focus_name']} | {row['present']} | {row['resolved_name']} | {row['confidence']} |")
        report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
        return _json_safe({"status": "ok", "output_path": str(out_path), "report_path": str(report_path), "payload": response_payload})

    def buildContext(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = BuildContextRequest(**payload)
        contract_paths, context = _build_context_payload(request)
        out_path = Path(request.out) if request.out else _default_output_path("build_context", ".json")
        _write_json_file(out_path, context)
        return _json_safe({"status": "ok", "output_path": str(out_path), "contract_paths": contract_paths, "payload": context})

    def generateBlueprint(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = GenerateBlueprintRequest(**payload)
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
        response_payload = {"retrieval_context": retrieval_context, "compiled_context": compiled, "blueprint": blueprint}
        _write_json_file(out_path, response_payload)
        return _json_safe({"status": "ok", "output_path": str(out_path), "contract_paths": contract_paths, "payload": response_payload})

    def generateOutline(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = GenerateOutlineRequest(**payload)
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
        response_payload = {"compiled_context": compiled, "blueprint": blueprint, "chapter_outline": outline}
        _write_json_file(out_path, response_payload)
        return _json_safe({"status": "ok", "output_path": str(out_path), "contract_paths": contract_paths, "payload": response_payload})

    def generateScene(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = GenerateSceneRequest(**payload)
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
        response_payload = {
            "compiled_context": compiled,
            "chapter_outline": request.chapter_outline,
            "scene_outline": request.scene_outline,
            "prose": prose,
        }
        _write_json_file(out_path, response_payload)
        return _json_safe({"status": "ok", "output_path": str(out_path), "contract_paths": contract_paths, "payload": response_payload})

    def generateProse(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.generateScene(payload)

    def getNeo4jStatus(self) -> dict[str, Any]:
        return _safe_neo4j_query(lambda: {"implemented": True, "connected": True, **_neo4j_service().probe_connection()})

    def getNeo4jSeries(self) -> dict[str, Any]:
        return _safe_neo4j_query(lambda: _list_neo4j_series(_neo4j_service()))

    def getNeo4jBooks(self, seriesId: str = "") -> dict[str, Any]:
        return _safe_neo4j_query(lambda: _list_neo4j_books(_neo4j_service(), series_id=seriesId or None))

    def getNeo4jSummary(self, seriesId: str = "", bookTitle: str = "") -> dict[str, Any]:
        return _safe_neo4j_query(lambda: _graph_summary(_neo4j_service(), series_id=seriesId or None, book_title=bookTitle or None))

    def neo4jDeleteDryRun(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = Neo4jDeleteDryRunRequest(**payload)
        return _safe_neo4j_query(lambda: _neo4j_delete_dry_run(_neo4j_service(), request))

    def neo4jIngest(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = Neo4jIngestRequest(**payload)
        contract_path = _resolve_path_input(request.contract_id, request.contract_path)
        contract_payload = read_json_file(contract_path)

        def _ingest() -> dict[str, Any]:
            service = _neo4j_service()
            try:
                preflight = service.probe_connection()
                result = service.ingest_contract(contract_payload, replace_existing=request.replace_existing)
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

    def neo4jDeleteConfirm(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = Neo4jDeleteConfirmRequest(**payload)
        required = _delete_confirmation_required(request)
        if request.confirm_text.strip() != required:
            raise ValueError(f"Confirmation text mismatch. Type exactly: {required}")

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
