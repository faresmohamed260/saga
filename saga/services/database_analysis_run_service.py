from __future__ import annotations

import json
import re
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select

from saga.agents.db_character_profile_agent import DatabaseCharacterProfileAgent
from saga.agents.db_character_visual_baseline_agent import DatabaseCharacterVisualBaselineAgent
from saga.agents.db_character_visual_scene_state_agent import DatabaseCharacterVisualSceneStateAgent
from saga.agents.db_entity_agent import DatabaseEntityDiscoveryAgent
from saga.agents.db_event_agent import DatabaseEventAnalysisAgent
from saga.agents.db_noncharacter_scene_state_agent import DatabaseNonCharacterSceneStateAgent
from saga.agents.db_noncharacter_visual_baseline_agent import DatabaseNonCharacterVisualBaselineAgent
from saga.agents.db_relationship_agent import DatabaseRelationshipAgent
from saga.agents.db_stable_character_state_agent import DatabaseStableCharacterStateAgent
from saga.agents.db_timeline_agent import DatabaseTimelineAgent
from saga.agents.db_world_state_consolidation_agent import DatabaseWorldStateConsolidationAgent
from saga.agents.scene_extractor import SceneExtractor
from saga.identity.series_identity_provider import build_series_pipeline_identity, generate_book_identity_bundle
from saga.providers.llm_client import LLMClient
from saga.services.entity_visual_prompt_service import EntityVisualPromptService
from saga.services.epub_processor import EPUBProcessor
from saga.storage import models as sql_models
from saga.storage.models import Book as SqlBook
from saga.storage.models import Chapter as SqlChapter
from saga.storage.models import Series as SqlSeries
from saga.storage.models import UploadedSource as SqlUploadedSource
from saga.storage.persistence import SagaSQLiteStore


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return text or "untitled"


def _word_count(text: Any) -> int:
    return len(str(text or "").split())


def _progress_payload(
    *,
    stage: str,
    current: int,
    total: int,
    label: str,
    status: str = "running",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    total = max(1, int(total or 1))
    current = max(0, min(int(current or 0), total))
    return {
        "stage": stage,
        "phase": stage,
        "current": current,
        "total": total,
        "percent": round((current / total) * 100, 2),
        "label": label,
        "status": status,
        "details": details or {},
        "updated_at": _utc_now(),
    }


@dataclass(slots=True)
class StageResult:
    stage: str
    payload: dict[str, Any]


@dataclass(slots=True)
class StageGroup:
    name: str
    stages: list[str]
    parallel: bool = False


class DatabaseAnalysisRunService:
    """Application service for dashboard-started database-native analysis runs.

    The FastAPI runtime owns HTTP transport. This service owns the actual import
    plan validation, source ingestion, chapter/scene persistence, optional
    production DB-agent orchestration, and cooperative job control boundaries.
    """

    DEFAULT_AGENT_STAGES = [
        "events",
        "entities",
        "character_profiles",
        "character_visual_baselines",
        "noncharacter_visual_baselines",
        "character_visual_scene_states",
        "noncharacter_scene_states",
        "relationships",
        "timeline",
        "stable_states",
        "world_state",
        "visual_prompts",
    ]
    DEFAULT_STAGE_GROUPS = [
        StageGroup(name="events", stages=["events"]),
        StageGroup(name="entities", stages=["entities"]),
        StageGroup(
            name="canon_synthesis",
            stages=[
                "character_profiles",
                "noncharacter_visual_baselines",
                "relationships",
                "timeline",
                "noncharacter_scene_states",
            ],
            parallel=True,
        ),
        StageGroup(
            name="character_visuals",
            stages=[
                "character_visual_baselines",
                "character_visual_scene_states",
            ],
            parallel=True,
        ),
        StageGroup(name="stable_states", stages=["stable_states"]),
        StageGroup(name="world_state", stages=["world_state"]),
        StageGroup(name="visual_prompts", stages=["visual_prompts"]),
    ]

    def __init__(self, sqlite_store: SagaSQLiteStore | None = None) -> None:
        self.sqlite_store = sqlite_store or SagaSQLiteStore()

    def validate_import_plan_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        books = payload.get("books") if isinstance(payload.get("books"), list) else []
        if not books:
            errors.append("No selected books are present in the import plan.")
        seen_indexes: set[int] = set()
        seen_hashes: set[str] = set()
        with self.sqlite_store.session_factory() as session:
            for item in books:
                source_id = str((item or {}).get("source_id") or "").strip()
                source = session.get(SqlUploadedSource, source_id) if source_id else None
                if source is None:
                    errors.append(f"Missing uploaded source: {source_id or 'blank source id'}")
                    continue
                if not Path(source.stored_path).exists():
                    errors.append(f"Uploaded file is no longer present on disk: {source.original_name or source.id}")
                book_index = int((item or {}).get("book_index") or 0)
                if book_index in seen_indexes:
                    errors.append(f"Duplicate book index in plan: {book_index}")
                seen_indexes.add(book_index)
                if source.sha256:
                    if source.sha256 in seen_hashes:
                        warnings.append(f"Duplicate staged file hash detected: {source.original_name or source.id}")
                    seen_hashes.add(source.sha256)
                    existing = session.execute(select(SqlBook).where(SqlBook.source_hash_sha256 == source.sha256)).scalars().first()
                    if existing:
                        warnings.append(f"Source already exists in library: {source.original_name or source.id} -> {existing.title}")
        can_start = not errors
        return {
            "status": "ready" if can_start else "blocked",
            "can_start": can_start,
            "errors": errors,
            "warnings": warnings,
            "summary": f"{len(books)} selected book(s), {len(errors)} blocking issue(s), {len(warnings)} warning(s).",
        }

    def run_import_plan_job(self, job_id: str, request_payload: dict[str, Any]) -> None:
        start = time.time()
        books = request_payload.get("books") if isinstance(request_payload.get("books"), list) else []
        shared_config = request_payload.get("shared_config") if isinstance(request_payload.get("shared_config"), dict) else {}
        run_agents = bool(shared_config.get("run_agents", True))
        resume_snapshot = self._load_resume_snapshot(request_payload=request_payload, books=books, shared_config=shared_config)
        total_units = self._estimate_total_units(books=books, shared_config=shared_config, run_agents=run_agents)
        artifacts = {
            "book_results": [],
            "stage_results": [],
            "import_mode": "db_native",
            "contracts_generated": False,
            "run_agents": run_agents,
        }
        if resume_snapshot:
            artifacts["resumed_from"] = resume_snapshot["retry_of"]
        self._set_job(
            job_id,
            status="running",
            started_at=_utc_now(),
            progress=_progress_payload(
                stage="analysis",
                current=int(resume_snapshot.get("completed_units") or 0) if resume_snapshot else 0,
                total=total_units,
                label="Resuming database-native analysis" if resume_snapshot else "Starting database-native analysis",
            ),
            artifacts=artifacts,
        )
        self._log(
            job_id,
            "INFO",
            "analysis_job_started",
            books=len(books),
            series_id=request_payload.get("series_id"),
            run_agents=run_agents,
            resumed_from=resume_snapshot["retry_of"] if resume_snapshot else None,
        )
        completed_units = int(resume_snapshot.get("completed_units") or 0) if resume_snapshot else 0
        try:
            series_id = str(request_payload.get("series_id") or "").strip()
            series_title = str(request_payload.get("series_title") or "").strip()
            source_snapshots: dict[str, dict[str, Any]] = {}
            for book_index, book_item in enumerate(books, start=1):
                source_id = str(book_item.get("source_id") or "").strip()
                with self.sqlite_store.session_factory() as session:
                    source = session.get(SqlUploadedSource, source_id)
                    if source is None:
                        raise ValueError(f"Missing uploaded source for plan book {book_index}: {source_id}")
                    source_snapshots[source_id] = {
                        "id": source.id,
                        "original_name": source.original_name,
                        "stored_path": source.stored_path,
                        "sha256": source.sha256,
                    }

            identity_provider = str(shared_config.get("identity_provider") or "booknlp_clean").strip().lower()
            if identity_provider == "booknlp_clean" and books and run_agents:
                if resume_snapshot and resume_snapshot.get("identity_payload"):
                    identity_payload = dict(resume_snapshot["identity_payload"])
                    self._log(
                        job_id,
                        "INFO",
                        "identity_bundle_reused",
                        series_id=series_id,
                        character_count=len(identity_payload.get("characters") or []),
                        alias_count=len(identity_payload.get("alias_index") or {}),
                        reference_entity_count=len(identity_payload.get("reference_entities") or []),
                    )
                else:
                    identity_payload, completed_units = self._build_booknlp_identity_bundle(
                        job_id=job_id,
                        series_id=series_id,
                        series_title=series_title,
                        books=books,
                        source_snapshots=source_snapshots,
                        shared_config=shared_config,
                        completed_units=completed_units,
                        total_units=total_units,
                    )
                artifacts["identity_bundle"] = {
                    "provider": "booknlp_clean",
                    "series_id": series_id,
                    "character_count": len(identity_payload.get("characters") or []),
                    "alias_count": len(identity_payload.get("alias_index") or {}),
                    "reference_entity_count": len(identity_payload.get("reference_entities") or []),
                    "db_ref": f"db://identity-series/{series_id}",
                }
                self._set_job(job_id, artifacts=artifacts)

            for book_index, book_item in enumerate(books, start=1):
                self._raise_if_cancelled(job_id, completed_units, total_units)
                source_id = str(book_item.get("source_id") or "").strip()
                source_snapshot = source_snapshots.get(source_id)
                if source_snapshot is None:
                    raise ValueError(f"Missing uploaded source snapshot for plan book {book_index}: {source_id}")
                resume_book = (resume_snapshot.get("books") or {}).get(int(book_item.get("book_index") or book_index)) if resume_snapshot else None
                if resume_book and resume_book.get("book_result"):
                    result = dict(resume_book["book_result"])
                    self._log(
                        job_id,
                        "INFO",
                        "book_ingest_reused",
                        book_index=book_item.get("book_index"),
                        source=source_snapshot["original_name"],
                        book_id=result.get("book_id"),
                    )
                else:
                    self._set_job(
                        job_id,
                        progress=_progress_payload(
                            stage="ingest_split",
                            current=completed_units,
                            total=total_units,
                            label=f"Extracting {source_snapshot['original_name'] or source_id}",
                            details={"book_index": book_item.get("book_index"), "source_id": source_id},
                        ),
                    )
                    self._log(job_id, "INFO", "book_ingest_started", book_index=book_item.get("book_index"), source=source_snapshot["original_name"])
                    result = self._upsert_analysis_book(
                        source=source_snapshot,
                        series_id=series_id,
                        series_title=series_title,
                        book_item=book_item,
                        shared_config=shared_config,
                    )
                    completed_units += 1
                artifacts["book_results"].append(result)
                self._set_job(
                    job_id,
                    artifacts=artifacts,
                    progress=_progress_payload(
                        stage="ingest_split",
                        current=completed_units,
                        total=total_units,
                        label=f"Stored {result['title']}: {result['chapters']} chapters, {result['scenes']} scenes",
                        details=result,
                    ),
                )
                self._log(job_id, "INFO", "book_ingest_completed", **result)
                if run_agents:
                    stage_results, completed_units = self._run_agent_stages(
                        job_id=job_id,
                        book_result=result,
                        shared_config=shared_config,
                        completed_units=completed_units,
                        total_units=total_units,
                        resume_book=resume_book,
                    )
                    artifacts["stage_results"].extend(stage_results)
                    self._set_job(job_id, artifacts=artifacts)
            elapsed = round(time.time() - start, 3)
            self._set_job(
                job_id,
                status="completed",
                finished_at=_utc_now(),
                status_reason="Database-native run completed.",
                artifacts=artifacts,
                progress=_progress_payload(
                    stage="complete",
                    current=total_units,
                    total=total_units,
                    label="Database-native analysis complete",
                    status="completed",
                    details={"elapsed_seconds": elapsed},
                ),
            )
            self._log(job_id, "INFO", "analysis_job_completed", elapsed_seconds=elapsed, books=len(books))
        except CancelledError as exc:
            self._set_job(
                job_id,
                status="cancelled",
                finished_at=_utc_now(),
                status_reason=str(exc),
                progress=_progress_payload(stage="cancelled", current=completed_units, total=total_units, label=str(exc), status="cancelled"),
            )
            self._log(job_id, "WARNING", "analysis_job_cancelled", completed_units=completed_units, total_units=total_units)
        except Exception as exc:
            elapsed = round(time.time() - start, 3)
            self._set_job(
                job_id,
                status="failed",
                finished_at=_utc_now(),
                status_reason=str(exc),
                error=traceback.format_exc(),
                artifacts=artifacts,
                progress=_progress_payload(
                    stage="failed",
                    current=completed_units,
                    total=total_units,
                    label="Analysis failed",
                    status="failed",
                    details={"elapsed_seconds": elapsed, "error_type": type(exc).__name__},
                ),
            )
            self._log(job_id, "ERROR", "analysis_job_failed", elapsed_seconds=elapsed, error=repr(exc))

    def _estimate_total_units(self, *, books: list[dict[str, Any]], shared_config: dict[str, Any], run_agents: bool) -> int:
        book_count = len(books)
        identity_provider = str(shared_config.get("identity_provider") or "booknlp_clean").strip().lower()
        units = max(1, book_count)
        if identity_provider == "booknlp_clean" and book_count:
            units += book_count + 1
        if run_agents:
            units += book_count * len(self._agent_stage_names(shared_config))
        return max(1, units)

    def _load_resume_snapshot(
        self,
        *,
        request_payload: dict[str, Any],
        books: list[dict[str, Any]],
        shared_config: dict[str, Any],
    ) -> dict[str, Any] | None:
        resume = request_payload.get("resume") if isinstance(request_payload.get("resume"), dict) else {}
        retry_of = str(resume.get("retry_of") or "").strip()
        if not retry_of:
            return None
        previous_job = self.sqlite_store.get_dashboard_job(retry_of)
        if previous_job is None:
            return None
        series_id = str(request_payload.get("series_id") or "").strip()
        identity_provider = str(shared_config.get("identity_provider") or "booknlp_clean").strip().lower()
        identity_payload = self.sqlite_store.get_identity_series_payload(series_id) if series_id and identity_provider == "booknlp_clean" else None
        snapshot: dict[str, Any] = {
            "retry_of": retry_of,
            "identity_payload": identity_payload,
            "books": {},
            "completed_units": 0,
        }
        if identity_payload and books and bool(shared_config.get("run_agents", True)):
            snapshot["completed_units"] += len(books) + 1
        for ordinal, book_item in enumerate(books, start=1):
            book_index = int(book_item.get("book_index") or ordinal)
            existing = self._existing_analysis_book_result(series_id=series_id, book_index=book_index)
            if existing is None:
                continue
            completed_stages = self._completed_stage_names_for_book(job_id=retry_of, book_id=str(existing["book_id"]))
            snapshot["books"][book_index] = {
                "book_result": existing,
                "completed_stages": completed_stages,
            }
            snapshot["completed_units"] += 1 + len(completed_stages)
        return snapshot

    def _existing_analysis_book_result(self, *, series_id: str, book_index: int) -> dict[str, Any] | None:
        with self.sqlite_store.session_factory() as session:
            book = session.execute(
                select(SqlBook).where(SqlBook.series_id == str(series_id), SqlBook.book_index == int(book_index))
            ).scalar_one_or_none()
            if book is None:
                return None
            chapter_ids = session.execute(select(SqlChapter.id).where(SqlChapter.book_id == book.id)).all()
            scene_ids = session.execute(select(sql_models.Scene.id).where(sql_models.Scene.book_id == book.id)).all()
            if not chapter_ids or not scene_ids:
                return None
            return {
                "book_id": book.id,
                "book_ref": f"db://book/{book.id}",
                "title": str(book.title or f"Book {book_index}"),
                "chapters": len(chapter_ids),
                "scenes": len(scene_ids),
            }

    def _completed_stage_names_for_book(self, *, job_id: str, book_id: str) -> set[str]:
        completed: set[str] = set()
        for line in self.sqlite_store.get_dashboard_job_log_tail(job_id, limit=5000):
            payload = self._parse_structured_log_payload(line)
            if not payload:
                continue
            if str(payload.get("book_id") or "") != str(book_id):
                continue
            if str(payload.get("event") or "") != "agent_stage_completed":
                continue
            stage_name = str(payload.get("stage") or "").strip()
            if stage_name:
                completed.add(stage_name)
        return completed

    def _parse_structured_log_payload(self, line: str) -> dict[str, Any] | None:
        raw = str(line or "")
        brace_index = raw.find("{")
        if brace_index < 0:
            return None
        try:
            payload = json.loads(raw[brace_index:])
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def _agent_stage_names(self, shared_config: dict[str, Any]) -> list[str]:
        configured = shared_config.get("agent_stages")
        if isinstance(configured, list) and configured:
            names = [str(item).strip() for item in configured if str(item).strip()]
            return [name for name in names if name in self.DEFAULT_AGENT_STAGES]
        return list(self.DEFAULT_AGENT_STAGES)

    def _agent_stage_groups(self, shared_config: dict[str, Any]) -> list[StageGroup]:
        requested = set(self._agent_stage_names(shared_config))
        groups: list[StageGroup] = []
        for group in self.DEFAULT_STAGE_GROUPS:
            selected = [stage for stage in group.stages if stage in requested]
            if not selected:
                continue
            groups.append(StageGroup(name=group.name, stages=selected, parallel=group.parallel and len(selected) > 1))
        covered = {stage for group in groups for stage in group.stages}
        for stage in self._agent_stage_names(shared_config):
            if stage not in covered:
                groups.append(StageGroup(name=stage, stages=[stage], parallel=False))
        return groups

    def _run_agent_stages(
        self,
        *,
        job_id: str,
        book_result: dict[str, Any],
        shared_config: dict[str, Any],
        completed_units: int,
        total_units: int,
        resume_book: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        book_ref = str(book_result["book_ref"])
        chapter_indices = self._chapter_indices(book_result["book_id"])
        stage_results: list[dict[str, Any]] = []
        completed_stage_names = {
            str(stage).strip()
            for stage in (resume_book or {}).get("completed_stages", set())
            if str(stage).strip()
        }
        for group in self._agent_stage_groups(shared_config):
            pending_stages = [stage for stage in group.stages if stage not in completed_stage_names]
            if not pending_stages:
                self._log(
                    job_id,
                    "INFO",
                    "agent_stage_group_reused",
                    book_id=book_result["book_id"],
                    stage_group=group.name,
                    stages=list(group.stages),
                )
                continue
            self._raise_if_cancelled(job_id, completed_units, total_units)
            self._set_job(
                job_id,
                progress=_progress_payload(
                    stage=group.name,
                    current=completed_units,
                    total=total_units,
                    label=f"{book_result['title']}: running {group.name}",
                    details={
                        "book_id": book_result["book_id"],
                        "stage_group": group.name,
                        "stages": list(pending_stages),
                        "parallel": group.parallel and len(pending_stages) > 1,
                        "resumed": bool(resume_book),
                    },
                ),
            )
            self._log(
                job_id,
                "INFO",
                "agent_stage_group_started",
                book_id=book_result["book_id"],
                stage_group=group.name,
                stages=list(pending_stages),
                parallel=group.parallel and len(pending_stages) > 1,
            )
            group_results = self._run_stage_group(
                group=StageGroup(name=group.name, stages=list(pending_stages), parallel=group.parallel and len(pending_stages) > 1),
                job_id=job_id,
                book_result=book_result,
                book_ref=book_ref,
                chapter_indices=chapter_indices,
                shared_config=shared_config,
                completed_units=completed_units,
                total_units=total_units,
            )
            completed_units += len(group_results)
            stage_results.extend(group_results)
            self._set_job(
                job_id,
                progress=_progress_payload(
                    stage=group.name,
                    current=completed_units,
                    total=total_units,
                    label=f"{book_result['title']}: {group.name} complete",
                    details={
                        "book_id": book_result["book_id"],
                        "stage_group": group.name,
                        "completed_stages": [row["stage"] for row in group_results],
                    },
                ),
            )
            self._log(
                job_id,
                "INFO",
                "agent_stage_group_completed",
                book_id=book_result["book_id"],
                stage_group=group.name,
                stages=[row["stage"] for row in group_results],
            )
        return stage_results, completed_units

    def _run_stage_group(
        self,
        *,
        group: StageGroup,
        job_id: str,
        book_result: dict[str, Any],
        book_ref: str,
        chapter_indices: list[int],
        shared_config: dict[str, Any],
        completed_units: int,
        total_units: int,
    ) -> list[dict[str, Any]]:
        if not group.parallel:
            results: list[dict[str, Any]] = []
            for stage in group.stages:
                result = self._execute_stage(
                    stage=stage,
                    book_ref=book_ref,
                    chapter_indices=chapter_indices,
                    shared_config=shared_config,
                    job_id=job_id,
                    book_result=book_result,
                    completed_units=completed_units + len(results),
                    total_units=total_units,
                )
                results.append({"book_id": book_result["book_id"], "stage": stage, "result": result})
            return results

        max_parallel = max(2, min(int(shared_config.get("max_parallel_agent_stages") or 3), len(group.stages)))
        futures = {}
        results_by_stage: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=max_parallel, thread_name_prefix=f"saga-{_slugify(group.name)}") as executor:
            for stage in group.stages:
                futures[
                    executor.submit(
                        self._execute_stage,
                        stage=stage,
                        book_ref=book_ref,
                        chapter_indices=chapter_indices,
                        shared_config=shared_config,
                        job_id=job_id,
                        book_result=book_result,
                        completed_units=completed_units,
                        total_units=total_units,
                    )
                ] = stage
            for future in as_completed(futures):
                stage = futures[future]
                results_by_stage[stage] = future.result()
        return [{"book_id": book_result["book_id"], "stage": stage, "result": results_by_stage[stage]} for stage in group.stages]

    def _execute_stage(
        self,
        *,
        stage: str,
        book_ref: str,
        chapter_indices: list[int],
        shared_config: dict[str, Any],
        job_id: str,
        book_result: dict[str, Any],
        completed_units: int,
        total_units: int,
    ) -> dict[str, Any]:
        self._raise_if_cancelled(job_id, completed_units, total_units)
        self._log(job_id, "INFO", "agent_stage_started", book_id=book_result["book_id"], stage=stage)
        started = time.time()
        try:
            result = self._run_one_stage(
                stage=stage,
                book_ref=book_ref,
                chapter_indices=chapter_indices,
                shared_config=shared_config,
                llm_client=None,
                job_id=job_id,
                book_result=book_result,
                completed_units=completed_units,
                total_units=total_units,
            )
            self._enforce_stage_gate(stage=stage, result=result)
        except Exception as exc:
            self._log(
                job_id,
                "ERROR",
                "agent_stage_failed",
                book_id=book_result["book_id"],
                stage=stage,
                elapsed_seconds=round(time.time() - started, 3),
                error=repr(exc),
            )
            raise
        self._log(
            job_id,
            "INFO",
            "agent_stage_completed",
            book_id=book_result["book_id"],
            stage=stage,
            elapsed_seconds=round(time.time() - started, 3),
            details=self._compact_stage_details(result),
        )
        return result

    def _enforce_stage_gate(self, *, stage: str, result: dict[str, Any]) -> None:
        if stage == "events":
            inserted = int(result.get("inserted_event_count") or 0)
            if inserted <= 0:
                raise ValueError("Events stage produced zero events; downstream stages are blocked.")
        if stage == "entities":
            written = int(
                result.get("entities_written")
                or result.get("persisted_entity_count")
                or result.get("inserted_count")
                or 0
            )
            if written <= 0:
                written = int(result.get("updated_count") or 0)
            if written <= 0:
                written = int(len(result.get("entities") or []))
            if written <= 0:
                raise ValueError("Entities stage produced zero entities; downstream stages are blocked.")

    def _run_one_stage(
        self,
        *,
        stage: str,
        book_ref: str,
        chapter_indices: list[int],
        shared_config: dict[str, Any],
        llm_client: LLMClient | None,
        job_id: str,
        book_result: dict[str, Any],
        completed_units: int,
        total_units: int,
    ) -> dict[str, Any]:
        if llm_client is None and stage in {
            "events",
            "entities",
            "character_profiles",
            "character_visual_baselines",
            "noncharacter_visual_baselines",
            "character_visual_scene_states",
        }:
            llm_client = self._llm_client(shared_config)
        if stage == "events":
            rows = []
            agent = DatabaseEventAnalysisAgent(
                llm_client=llm_client,
                sqlite_store=self.sqlite_store,
                max_attempts=self._agent_max_attempts(shared_config),
                retry_delay_seconds=self._agent_retry_delay_seconds(shared_config),
            )
            for ordinal, chapter_index in enumerate(chapter_indices, start=1):
                self._raise_if_cancelled(job_id, completed_units, total_units)
                self._set_chapter_progress(
                    job_id=job_id,
                    stage=stage,
                    book_result=book_result,
                    chapter_index=chapter_index,
                    chapter_ordinal=ordinal,
                    chapter_total=len(chapter_indices),
                    completed_units=completed_units,
                    total_units=total_units,
                )
                self._log(
                    job_id,
                    "INFO",
                    "agent_chapter_started",
                    book_id=book_result["book_id"],
                    stage=stage,
                    chapter_index=chapter_index,
                    chapter_ordinal=ordinal,
                    chapter_total=len(chapter_indices),
                )
                started = time.time()
                try:
                    row = self._run_with_timeout(
                        lambda chapter_index=chapter_index: agent.analyze_book_chapter(
                            book_ref=book_ref,
                            chapter_index=chapter_index,
                            replace_existing_agent_rows=True,
                        ),
                        timeout_seconds=self._agent_chapter_timeout_seconds(shared_config),
                        label=f"{stage} chapter {chapter_index}",
                    )
                except Exception as exc:
                    self._log(
                        job_id,
                        "ERROR",
                        "agent_chapter_failed",
                        book_id=book_result["book_id"],
                        stage=stage,
                        chapter_index=chapter_index,
                        elapsed_seconds=round(time.time() - started, 3),
                        error=repr(exc),
                    )
                    raise
                rows.append(row)
                self._log(
                    job_id,
                    "INFO",
                    "agent_chapter_completed",
                    book_id=book_result["book_id"],
                    stage=stage,
                    chapter_index=chapter_index,
                    elapsed_seconds=round(time.time() - started, 3),
                    details=self._compact_stage_details(row),
                )
            return {"chapters": len(rows), "inserted_event_count": sum(int(row.get("inserted_event_count") or 0) for row in rows)}
        if stage == "entities":
            rows = []
            agent = DatabaseEntityDiscoveryAgent(
                llm_client=llm_client,
                sqlite_store=self.sqlite_store,
                max_attempts=self._agent_max_attempts(shared_config),
                retry_delay_seconds=self._agent_retry_delay_seconds(shared_config),
            )
            for ordinal, chapter_index in enumerate(chapter_indices, start=1):
                self._raise_if_cancelled(job_id, completed_units, total_units)
                self._set_chapter_progress(
                    job_id=job_id,
                    stage=stage,
                    book_result=book_result,
                    chapter_index=chapter_index,
                    chapter_ordinal=ordinal,
                    chapter_total=len(chapter_indices),
                    completed_units=completed_units,
                    total_units=total_units,
                )
                self._log(
                    job_id,
                    "INFO",
                    "agent_chapter_started",
                    book_id=book_result["book_id"],
                    stage=stage,
                    chapter_index=chapter_index,
                    chapter_ordinal=ordinal,
                    chapter_total=len(chapter_indices),
                )
                started = time.time()
                try:
                    row = self._run_with_timeout(
                        lambda chapter_index=chapter_index: agent.analyze_book_chapter(
                            book_ref=book_ref,
                            chapter_index=chapter_index,
                        ),
                        timeout_seconds=self._agent_chapter_timeout_seconds(shared_config),
                        label=f"{stage} chapter {chapter_index}",
                    )
                except Exception as exc:
                    self._log(
                        job_id,
                        "ERROR",
                        "agent_chapter_failed",
                        book_id=book_result["book_id"],
                        stage=stage,
                        chapter_index=chapter_index,
                        elapsed_seconds=round(time.time() - started, 3),
                        error=repr(exc),
                    )
                    raise
                rows.append(row)
                self._log(
                    job_id,
                    "INFO",
                    "agent_chapter_completed",
                    book_id=book_result["book_id"],
                    stage=stage,
                    chapter_index=chapter_index,
                    elapsed_seconds=round(time.time() - started, 3),
                    details=self._compact_stage_details(row),
                )
            inserted_count = sum(int(row.get("inserted_count") or 0) for row in rows)
            updated_count = sum(int(row.get("updated_count") or 0) for row in rows)
            persisted_entity_count = sum(
                int(row.get("entities_written") or row.get("persisted_entity_count") or 0) for row in rows
            )
            if persisted_entity_count <= 0:
                persisted_entity_count = inserted_count + updated_count
            return {
                "chapters": len(rows),
                "inserted_count": inserted_count,
                "updated_count": updated_count,
                "persisted_entity_count": persisted_entity_count,
                "entities_written": persisted_entity_count,
            }
        if stage == "character_profiles":
            return DatabaseCharacterProfileAgent(llm_client=llm_client, sqlite_store=self.sqlite_store).analyze_book(
                book_ref=book_ref,
                limit_characters=self._optional_int(shared_config.get("limit_characters")),
            )
        if stage == "character_visual_baselines":
            return DatabaseCharacterVisualBaselineAgent(llm_client=llm_client, sqlite_store=self.sqlite_store).analyze_book(
                book_ref=book_ref,
                limit_characters=self._optional_int(shared_config.get("limit_characters")),
            )
        if stage == "noncharacter_visual_baselines":
            def _noncharacter_visual_progress(event: dict[str, Any]) -> None:
                total_entities = max(1, int(event.get("total_entities") or 1))
                completed_entities = max(0, int(event.get("completed_entities") or 0))
                current_entity_name = str(event.get("current_entity_name") or "").strip()
                current_entity_type = str(event.get("current_entity_type") or "").strip()
                persisted_visual_baselines = int(event.get("persisted_visual_baselines") or 0)
                skipped_entities = int(event.get("skipped_entities") or 0)
                if completed_entities >= total_entities:
                    label = f"{book_result['title']}: {stage} complete"
                elif current_entity_name:
                    label = (
                        f"{book_result['title']}: {stage} "
                        f"{completed_entities}/{total_entities} "
                        f"({current_entity_type or 'entity'} {current_entity_name})"
                    )
                else:
                    label = f"{book_result['title']}: {stage} {completed_entities}/{total_entities}"
                self._set_job(
                    job_id,
                    progress=_progress_payload(
                        stage=stage,
                        current=completed_units,
                        total=total_units,
                        label=label,
                        details={
                            "book_id": book_result["book_id"],
                            "stage": stage,
                            "entity_current": completed_entities,
                            "entity_total": total_entities,
                            "persisted_visual_baselines": persisted_visual_baselines,
                            "skipped_entities": skipped_entities,
                            "current_entity_name": current_entity_name,
                            "current_entity_type": current_entity_type,
                        },
                    ),
                )
                if event.get("event") == "entity_completed":
                    self._log(
                        job_id,
                        "INFO",
                        "agent_entity_completed",
                        book_id=book_result["book_id"],
                        stage=stage,
                        entity_current=completed_entities,
                        entity_total=total_entities,
                        entity_name=current_entity_name,
                        entity_type=current_entity_type,
                        skipped=bool(event.get("skipped")),
                        persisted_visual_baselines=persisted_visual_baselines,
                        skipped_entities=skipped_entities,
                    )

            return DatabaseNonCharacterVisualBaselineAgent(llm_client=llm_client, sqlite_store=self.sqlite_store).analyze_book(
                book_ref=book_ref,
                limit_entities=self._optional_int(shared_config.get("limit_entities")),
                progress_callback=_noncharacter_visual_progress,
            )
        if stage == "character_visual_scene_states":
            return DatabaseCharacterVisualSceneStateAgent(llm_client=llm_client, sqlite_store=self.sqlite_store).analyze_book(
                book_ref=book_ref,
                max_scenes=self._optional_int(shared_config.get("limit_scene_states")),
            )
        if stage == "noncharacter_scene_states":
            return DatabaseNonCharacterSceneStateAgent(sqlite_store=self.sqlite_store).analyze_book(book_ref=book_ref)
        if stage == "relationships":
            return DatabaseRelationshipAgent(sqlite_store=self.sqlite_store).analyze_book(book_ref=book_ref)
        if stage == "timeline":
            return DatabaseTimelineAgent(sqlite_store=self.sqlite_store).analyze_book(book_ref=book_ref)
        if stage == "stable_states":
            return DatabaseStableCharacterStateAgent(sqlite_store=self.sqlite_store).analyze_book(book_ref=book_ref)
        if stage == "world_state":
            return DatabaseWorldStateConsolidationAgent(sqlite_store=self.sqlite_store).analyze_book(book_ref=book_ref)
        if stage == "visual_prompts":
            result = EntityVisualPromptService(self.sqlite_store).build_book_prompts(book_ref, overwrite=True)
            return {
                "total_entities": result.total_entities,
                "prompts_written": result.prompts_written,
                "prompts_updated": result.prompts_updated,
                "prompts_total": result.prompts_total,
            }
        raise ValueError(f"Unsupported database analysis stage: {stage}")

    def _llm_client(self, shared_config: dict[str, Any]) -> LLMClient:
        provider_mode = str(shared_config.get("analysis_provider_mode") or "same_provider_rotating")
        model_mode = str(shared_config.get("analysis_model") or LLMClient.MODE_GPT_OSS)
        return LLMClient(
            mode=model_mode,
            max_retries=self._llm_max_retries(shared_config),
            timeout=self._llm_timeout_seconds(shared_config),
            allow_account_rotation=(provider_mode == "same_provider_rotating"),
            allow_cross_provider_fallback=(provider_mode == "cross_provider_fallback"),
        )

    def _set_chapter_progress(
        self,
        *,
        job_id: str,
        stage: str,
        book_result: dict[str, Any],
        chapter_index: int,
        chapter_ordinal: int,
        chapter_total: int,
        completed_units: int,
        total_units: int,
    ) -> None:
        self._set_job(
            job_id,
            progress=_progress_payload(
                stage=stage,
                current=completed_units,
                total=total_units,
                label=f"{book_result['title']}: {stage} chapter {chapter_ordinal}/{chapter_total}",
                details={
                    "book_id": book_result["book_id"],
                    "stage": stage,
                    "chapter_index": chapter_index,
                    "chapter_ordinal": chapter_ordinal,
                    "chapter_total": chapter_total,
                },
            ),
        )

    def _run_with_timeout(self, func, *, timeout_seconds: int, label: str) -> Any:
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"saga-{_slugify(label)}")
        future = executor.submit(func)
        try:
            return future.result(timeout=max(1, int(timeout_seconds)))
        except FutureTimeoutError as exc:
            future.cancel()
            raise TimeoutError(f"{label} exceeded {timeout_seconds}s timeout") from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _llm_timeout_seconds(self, shared_config: dict[str, Any]) -> int:
        return max(30, int(shared_config.get("llm_timeout_seconds") or shared_config.get("analysis_timeout_seconds") or 120))

    def _llm_max_retries(self, shared_config: dict[str, Any]) -> int:
        return max(1, int(shared_config.get("llm_max_retries") or shared_config.get("analysis_max_retries") or 2))

    def _agent_max_attempts(self, shared_config: dict[str, Any]) -> int:
        return max(1, int(shared_config.get("agent_max_attempts") or 2))

    def _agent_retry_delay_seconds(self, shared_config: dict[str, Any]) -> float:
        return max(0.0, float(shared_config.get("agent_retry_delay_seconds") or 1.0))

    def _agent_chapter_timeout_seconds(self, shared_config: dict[str, Any]) -> int:
        configured = shared_config.get("agent_chapter_timeout_seconds")
        if configured not in (None, ""):
            return max(60, int(configured))
        return max(180, self._llm_timeout_seconds(shared_config) * self._agent_max_attempts(shared_config) + 60)

    def _compact_stage_details(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        compact: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                compact[key] = value
            elif isinstance(value, list):
                compact[f"{key}_count"] = len(value)
            elif isinstance(value, dict):
                compact[f"{key}_keys"] = len(value)
        return compact

    def _chapter_indices(self, book_id: str) -> list[int]:
        with self.sqlite_store.session_factory() as session:
            rows = session.execute(
                select(SqlChapter.chapter_index).where(SqlChapter.book_id == book_id).order_by(SqlChapter.chapter_index.asc())
            ).all()
        return [int(row[0]) for row in rows]

    def _upsert_analysis_book(
        self,
        *,
        source: dict[str, Any],
        series_id: str,
        series_title: str,
        book_item: dict[str, Any],
        shared_config: dict[str, Any],
    ) -> dict[str, Any]:
        source_path = Path(str(source.get("stored_path") or ""))
        chapters = self._extract_source_chapters(source_path)
        if not chapters:
            raise ValueError(f"No narrative chapters could be extracted from {source.get('original_name') or source_path.name}")
        book_index = int(book_item.get("book_index") or 1)
        title = str(book_item.get("title") or book_item.get("target_title") or source.get("original_name") or source_path.stem).strip()
        scene_target_words = int(shared_config.get("scene_target_words") or shared_config.get("target_scene_words") or 700)
        with self.sqlite_store.session_factory() as session:
            series = session.execute(select(SqlSeries).where(SqlSeries.series_id == series_id)).scalar_one_or_none()
            if series is None:
                series = SqlSeries(series_id=series_id, title=series_title, metadata_json={"origin": "dashboard_import_plan"})
                session.add(series)
                session.flush()
            else:
                series.title = series_title or series.title
            book = session.execute(select(SqlBook).where(SqlBook.series_id == series_id, SqlBook.book_index == book_index)).scalar_one_or_none()
            if book is None:
                book = SqlBook(series_id=series_id, book_index=book_index, title=title)
                session.add(book)
                session.flush()
            book.series_fk = series.id
            book.title = title
            book.source_path = str(source_path)
            book.source_hash_sha256 = str(source.get("sha256") or "")
            book.source_type = source_path.suffix.lower().lstrip(".") or "text"
            book.contract_path = None
            book.run_status = "extracting"
            book.analysis_model = str(shared_config.get("analysis_model") or "")
            book.analysis_provider_mode = str(shared_config.get("analysis_provider_mode") or "")
            book.identity_provider = str(shared_config.get("identity_provider") or "booknlp_clean")
            book.scene_failure_policy = str(shared_config.get("scene_failure_policy") or "fail_fast")
            book.metadata_json = {
                "origin": "dashboard_db_native_analysis",
                "source_id": source.get("id"),
                "scene_target_words": scene_target_words,
                "contracts_generated": False,
            }
            self._clear_book_rows(session=session, book_id=book.id)
            chapter_rows = []
            for chapter_index, chapter in enumerate(chapters, start=1):
                chapter_row = SqlChapter(
                    book_id=book.id,
                    chapter_index=chapter_index,
                    title=str(chapter.get("chapter_title") or f"Chapter {chapter_index}").strip(),
                    text=str(chapter.get("content") or "").strip(),
                    word_count=_word_count(chapter.get("content")),
                    metadata_json={"source_id": source.get("id"), "source_name": source.get("original_name")},
                )
                session.add(chapter_row)
                chapter_rows.append(chapter_row)
            session.flush()
            scene_inputs = [
                {
                    "book_index": book_index,
                    "chapter_index": int(row.chapter_index),
                    "chapter_title": row.title or f"Chapter {row.chapter_index}",
                    "content": row.text or "",
                    "source_file": str(source_path),
                }
                for row in chapter_rows
            ]
            scene_rows = SceneExtractor.from_target_words(scene_target_words).extract_many(scene_inputs, allow_cross_chapter=False)
            chapter_map = {row.chapter_index: row for row in chapter_rows}
            for scene in scene_rows:
                chapter_index = int(scene.get("chapter_index") or 1)
                text = str(scene.get("text") or "").strip()
                chapter = chapter_map.get(chapter_index)
                session.add(
                    sql_models.Scene(
                        book_id=book.id,
                        chapter_id=getattr(chapter, "id", None),
                        book_index=book_index,
                        chapter_index=chapter_index,
                        scene_index=int(scene.get("scene_index") or 1),
                        summary=str(scene.get("chapter_title") or getattr(chapter, "title", "") or "").strip(),
                        text=text,
                        final_status="split_ready",
                        payload_json={
                            "source": "dashboard_db_native_scene_splitter",
                            "word_count": _word_count(text),
                            "target_words": scene_target_words,
                            "source_chapter_indices": scene.get("source_chapter_indices") or [chapter_index],
                        },
                    )
                )
            book.run_status = "split_ready"
            book.scene_analysis_quality = {
                "total_scenes": len(scene_rows),
                "successful_scenes": len(scene_rows),
                "failed_scenes": 0,
                "source": "db_native_import_split",
            }
            session.commit()
            return {
                "book_id": book.id,
                "book_ref": f"db://book/{book.id}",
                "title": title,
                "chapters": len(chapter_rows),
                "scenes": len(scene_rows),
            }

    def _identity_output_root(self, series_id: str) -> Path:
        return Path("analysis_outputs") / "identity_series" / _slugify(series_id)

    def _build_booknlp_identity_bundle(
        self,
        *,
        job_id: str,
        series_id: str,
        series_title: str,
        books: list[dict[str, Any]],
        source_snapshots: dict[str, dict[str, Any]],
        shared_config: dict[str, Any],
        completed_units: int,
        total_units: int,
    ) -> tuple[dict[str, Any], int]:
        output_root = self._identity_output_root(series_id)
        output_root.mkdir(parents=True, exist_ok=True)
        llm_review_mode = str(shared_config.get("identity_llm_review_mode") or "").strip()
        enable_external_research = bool(shared_config.get("identity_enable_external_research", False))
        max_review_candidates = int(shared_config.get("identity_max_review_candidates") or 24)
        total_steps = max(1, len(books) + 1)
        summaries: list[dict[str, Any]] = []

        def _set_identity_progress(*, current_step: int, label: str, details: dict[str, Any] | None = None, status: str = "running") -> None:
            self._set_job(
                job_id,
                progress=_progress_payload(
                    stage="identity_bundle",
                    current=min(total_units, completed_units + current_step),
                    total=total_units,
                    label=label,
                    status=status,
                    details=details or {},
                ),
            )

        for idx, book_item in enumerate(books, start=1):
            source_id = str(book_item.get("source_id") or "").strip()
            source = source_snapshots.get(source_id)
            if source is None:
                raise ValueError(f"Missing source snapshot for BookNLP bundle: {source_id}")
            title = str(book_item.get("title") or book_item.get("target_title") or source.get("original_name") or "").strip()
            book_payload = {
                "path": str(source.get("stored_path") or ""),
                "title": title,
            }

            def _bundle_progress(stage_name: str, payload: dict[str, Any]) -> None:
                payload = payload if isinstance(payload, dict) else {}
                detail_payload = {
                    "book_index": int(book_item.get("book_index") or idx),
                    "book_position": idx,
                    "book_total": len(books),
                    "book_title": title,
                    "substage": stage_name,
                    **payload,
                }
                _set_identity_progress(
                    current_step=idx - 1,
                    label=f"{title}: BookNLP {stage_name}",
                    details=detail_payload,
                )
                self._log(
                    job_id,
                    "INFO",
                    "identity_bundle_progress",
                    book_title=title,
                    stage=stage_name,
                    **payload,
                )

            self._log(
                job_id,
                "INFO",
                "identity_bundle_started",
                book_title=title,
                book_index=int(book_item.get("book_index") or idx),
                output_root=str(output_root),
                series_id=series_id,
            )
            _set_identity_progress(
                current_step=idx - 1,
                label=f"{title}: preparing BookNLP identity bundle",
                details={
                    "book_index": int(book_item.get("book_index") or idx),
                    "book_position": idx,
                    "book_total": len(books),
                    "book_title": title,
                    "output_root": str(output_root),
                    "substage": "starting",
                },
            )
            summary = generate_book_identity_bundle(
                book=book_payload,
                book_index=int(book_item.get("book_index") or idx),
                output_root=output_root,
                reuse_book1_seed=False,
                llm_review_mode=llm_review_mode,
                enable_external_research=enable_external_research,
                max_review_candidates=max_review_candidates,
                progress_callback=_bundle_progress,
            )
            summaries.append(summary)
            _set_identity_progress(
                current_step=idx,
                label=f"{title}: BookNLP identity ready",
                details={
                    "book_index": int(book_item.get("book_index") or idx),
                    "book_position": idx,
                    "book_total": len(books),
                    "book_title": title,
                    "character_count": summary.get("character_count", 0),
                    "alias_count": summary.get("alias_count", 0),
                    "reference_entity_count": summary.get("reference_entity_count", 0),
                    "pipeline_identity_path": str(summary.get("pipeline_identity_path") or ""),
                    "substage": "book_complete",
                },
            )
            self._log(
                job_id,
                "INFO",
                "identity_bundle_completed",
                book_title=title,
                book_index=int(book_item.get("book_index") or idx),
                character_count=summary.get("character_count", 0),
                alias_count=summary.get("alias_count", 0),
                reference_entity_count=summary.get("reference_entity_count", 0),
                pipeline_identity_path=str(summary.get("pipeline_identity_path") or ""),
            )

        series_identity_path = output_root / f"{_slugify(series_id)}_series_pipeline_identity.json"
        _set_identity_progress(
            current_step=len(books),
            label=f"{series_title}: building series identity map",
            details={
                "series_id": series_id,
                "series_title": series_title,
                "output_path": str(series_identity_path),
                "substage": "series_merge",
            },
        )
        self._log(
            job_id,
            "INFO",
            "identity_series_merge_started",
            series_id=series_id,
            series_title=series_title,
            output_path=str(series_identity_path),
            books=len(summaries),
        )
        payload = build_series_pipeline_identity(book_summaries=summaries, output_json=series_identity_path)
        payload["series_id"] = series_id
        payload.setdefault("provider", "booknlp_clean")
        persisted = self.sqlite_store.persist_identity_bundle(
            series_id=series_id,
            source_path=f"db://identity-series/{series_id}",
            series_payload=payload,
            book_summaries=summaries,
        )
        _set_identity_progress(
            current_step=total_steps,
            label=f"{series_title}: BookNLP identity persisted",
            details={
                "series_id": series_id,
                "series_title": series_title,
                "book_count": len(summaries),
                "character_count": len(payload.get("characters") or []),
                "alias_count": len(payload.get("alias_index") or {}),
                "reference_entity_count": len(payload.get("reference_entities") or []),
                "identity_series_ref": f"db://identity-series/{series_id}",
                "output_path": str(series_identity_path),
                "substage": "complete",
            },
        )
        self._log(
            job_id,
            "INFO",
            "identity_series_merge_completed",
            series_id=series_id,
            series_title=series_title,
            book_count=len(summaries),
            character_count=len(payload.get("characters") or []),
            alias_count=len(payload.get("alias_index") or {}),
            reference_entity_count=len(payload.get("reference_entities") or []),
            identity_series_ref=f"db://identity-series/{series_id}",
            persisted_books=persisted.get("book_count", 0),
        )
        return payload, completed_units + total_steps

    def _clear_book_rows(self, *, session: Any, book_id: str) -> None:
        for model in [
            sql_models.GeneratedImage,
            sql_models.VisualPrompt,
            sql_models.CharacterVisualSceneState,
            sql_models.CharacterVisualBaseline,
            sql_models.CreatureVisualBaseline,
            sql_models.ObjectSceneState,
            sql_models.ObjectVisualBaseline,
            sql_models.LocationSceneState,
            sql_models.LocationVisualBaseline,
            sql_models.TimelineRow,
            sql_models.Event,
            sql_models.StableCharacterState,
            sql_models.CharacterProfile,
            sql_models.Entity,
            sql_models.Scene,
            sql_models.Chapter,
        ]:
            session.execute(delete(model).where(model.book_id == book_id))
        session.flush()

    def _extract_source_chapters(self, path: Path) -> list[dict[str, str]]:
        suffix = path.suffix.lower()
        if suffix == ".epub":
            return EPUBProcessor().process(str(path))
        if suffix in {".txt", ".md"}:
            return self._plain_text_chapters(path)
        raise ValueError(f"Unsupported staged source type for database analysis: {path.suffix or path.name}")

    def _plain_text_chapters(self, path: Path) -> list[dict[str, str]]:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        pieces = re.split(r"(?im)^\s*(chapter\s+[\wivxlcdm\d .:-]+|prologue|epilogue)\s*$", text)
        chapters: list[dict[str, str]] = []
        if len(pieces) >= 3:
            prefix = pieces[0].strip()
            for idx in range(1, len(pieces), 2):
                title = pieces[idx].strip()
                content = pieces[idx + 1].strip() if idx + 1 < len(pieces) else ""
                if len(content.split()) >= 20:
                    chapters.append({"chapter_title": title, "content": content})
            if prefix and chapters:
                chapters[0]["content"] = f"{prefix}\n\n{chapters[0]['content']}".strip()
        if not chapters and text.strip():
            chapters = [{"chapter_title": path.stem, "content": text.strip()}]
        return chapters

    def _raise_if_cancelled(self, job_id: str, completed_units: int, total_units: int) -> None:
        payload = self.sqlite_store.get_dashboard_job(job_id) or {}
        artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
        if str(artifacts.get("control_requested") or "").strip().lower() == "cancel":
            self._set_job(
                job_id,
                progress=_progress_payload(stage="cancelled", current=completed_units, total=total_units, label="Cancellation acknowledged", status="cancelled"),
            )
            raise CancelledError("Cancelled at a safe stage boundary.")

    def _set_job(self, job_id: str, **updates: Any) -> dict[str, Any]:
        payload = self.sqlite_store.get_dashboard_job(job_id) or {"id": job_id}
        payload.update(updates)
        self.sqlite_store.upsert_dashboard_job(payload)
        return self.sqlite_store.get_dashboard_job(job_id) or payload

    def _log(self, job_id: str, level: str, event: str, **fields: Any) -> None:
        payload = {"event": event, **fields}
        self.sqlite_store.append_dashboard_job_log(
            job_id,
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} {level.upper()} {json.dumps(payload, ensure_ascii=False, sort_keys=True)}",
            level=level.upper(),
        )

    def _optional_int(self, value: Any) -> int | None:
        if value in (None, "", 0, "0"):
            return None
        return int(value)


class CancelledError(RuntimeError):
    pass
