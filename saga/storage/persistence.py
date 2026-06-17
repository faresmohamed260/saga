from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from saga.agents.scene_extractor import SceneExtractor
from .database import get_session_factory, initialize_database
from .models import (
    Book,
    DashboardJob,
    DashboardJobLog,
    CharacterVisualBaseline,
    CharacterVisualSceneState,
    Chapter,
    CharacterProfile,
    CreatureVisualBaseline,
    Entity,
    Event,
    GeneratedImage,
    GeneratedStory,
    GeneratedStoryChapter,
    IdentityAlias,
    IdentityBook,
    IdentityCharacter,
    IdentityNarrator,
    IdentityReferenceEntity,
    IdentitySeries,
    LocationSceneState,
    LocationVisualBaseline,
    ObjectSceneState,
    ObjectVisualBaseline,
    PipelineRun,
    PipelineRunBook,
    ProviderAccount,
    ProviderAccountStatus,
    ProviderConfig,
    Scene,
    Series,
    StableCharacterState,
    TimelineRow,
    UploadedSource,
    VisualPrompt,
)


class SagaSQLiteStore:
    """Canonical SQLite persistence for encoder and visual outputs."""

    def __init__(self, database_path: str | Path | None = None) -> None:
        initialize_database(database_path)
        self.session_factory = get_session_factory(database_path)

    def persist_contract(self, contract: dict[str, Any], *, contract_path: str | Path | None = None) -> dict[str, Any]:
        with self.session_factory() as session:
            return self._persist_contract(session, contract, contract_path=contract_path)

    def persist_render_manifest(self, manifest: dict[str, Any]) -> dict[str, Any]:
        contract_path = str(manifest.get("contract_path") or "").strip()
        if not contract_path:
            return {"stored_images": 0, "stored_prompts": 0}
        with self.session_factory() as session:
            book = self._find_book_by_contract_path(session, contract_path)
            if book is None:
                return {"stored_images": 0, "stored_prompts": 0}
            entity_map = self._entity_map(session, book.id)
            prompt_map = self._prompt_map(session, book.id)
            stored_images = 0
            stored_prompts = 0
            workflow_name = str(manifest.get("workflow_path") or manifest.get("workflow_mode") or "").strip()
            for row in (manifest.get("renders") or []):
                if not isinstance(row, dict):
                    continue
                entity_name = str(row.get("entity_name") or "").strip()
                entity_type = str(row.get("entity_type") or "").strip().lower()
                if not entity_name:
                    continue
                entity = entity_map.get((entity_name.lower(), entity_type))
                prompt_key = (entity_name.lower(), entity_type, str(row.get("prompt_type") or "").strip().lower())
                prompt = prompt_map.get(prompt_key)
                if prompt is None:
                    prompt = VisualPrompt(
                        book_id=book.id,
                        entity_id=entity.id if entity else None,
                        entity_name=entity_name,
                        entity_type=entity_type or None,
                        prompt_type=str(row.get("prompt_type") or "").strip() or None,
                        visual_bucket=str(row.get("visual_bucket") or "").strip() or None,
                        positive_prompt=str(row.get("positive_prompt") or "").strip() or None,
                        negative_prompt=str(row.get("negative_prompt") or "").strip() or None,
                        source_evidence=str(row.get("source_evidence") or "").strip() or None,
                        confidence=str(row.get("confidence") or "").strip() or None,
                        book_index=self._int_or_none(row.get("book_index")),
                        chapter_index=self._int_or_none(row.get("chapter_index")),
                        scene_index=self._int_or_none(row.get("scene_index")),
                        details_json=row.get("details") if isinstance(row.get("details"), (dict, list)) else None,
                        metadata_json={"origin": "render_manifest"},
                    )
                    session.add(prompt)
                    session.flush()
                    prompt_map[prompt_key] = prompt
                    stored_prompts += 1
                else:
                    prompt.entity_id = entity.id if entity else prompt.entity_id
                    prompt.visual_bucket = str(row.get("visual_bucket") or prompt.visual_bucket or "").strip() or prompt.visual_bucket
                    prompt.positive_prompt = str(row.get("positive_prompt") or prompt.positive_prompt or "").strip() or prompt.positive_prompt
                    prompt.negative_prompt = str(row.get("negative_prompt") or prompt.negative_prompt or "").strip() or prompt.negative_prompt
                    prompt.source_evidence = str(row.get("source_evidence") or prompt.source_evidence or "").strip() or prompt.source_evidence
                    prompt.confidence = str(row.get("confidence") or prompt.confidence or "").strip() or prompt.confidence
                    prompt.details_json = row.get("details") if isinstance(row.get("details"), (dict, list)) else prompt.details_json
                    prompt.metadata_json = {"origin": "render_manifest"}

                output_path = str(row.get("output_path") or "").strip()
                render_status = str(row.get("status") or row.get("render_status") or "").strip().lower()
                image_bytes = None
                if output_path:
                    try:
                        image_bytes = Path(output_path).read_bytes()
                    except OSError:
                        image_bytes = None
                should_store_image = bool(output_path and image_bytes is not None)
                generated = session.execute(
                    select(GeneratedImage).where(
                        GeneratedImage.book_id == book.id,
                        GeneratedImage.entity_name == entity_name,
                        GeneratedImage.output_path == (output_path or None),
                    )
                ).scalar_one_or_none()
                if generated is None and should_store_image:
                    generated = GeneratedImage(
                        book_id=book.id,
                        entity_id=entity.id if entity else None,
                        prompt_id=prompt.id,
                        entity_name=entity_name,
                        entity_type=entity_type or None,
                        output_path=output_path or None,
                        mime_type="image/png" if output_path.lower().endswith(".png") else None,
                        image_bytes=image_bytes,
                        render_status=render_status or None,
                        workflow_name=workflow_name or None,
                        manifest_json=row,
                    )
                    session.add(generated)
                    stored_images += 1
                elif generated is not None:
                    generated.entity_id = entity.id if entity else generated.entity_id
                    generated.prompt_id = prompt.id
                    generated.entity_type = entity_type or generated.entity_type
                    if output_path:
                        generated.output_path = output_path
                    if output_path.lower().endswith(".png"):
                        generated.mime_type = "image/png"
                    if image_bytes is not None:
                        generated.image_bytes = image_bytes
                    generated.render_status = render_status or generated.render_status
                    generated.workflow_name = workflow_name or generated.workflow_name
                    generated.manifest_json = row
                if entity:
                    if str(row.get("positive_prompt") or "").strip():
                        entity.baseline_visual_prompt = str(row.get("positive_prompt") or "").strip()
                    if should_store_image:
                        entity.generated_image_path = output_path
                    if image_bytes:
                        entity.generated_image_bytes = image_bytes
            session.commit()
            return {"stored_images": stored_images, "stored_prompts": stored_prompts}

    def persist_identity_bundle(
        self,
        *,
        series_id: str,
        source_path: str | Path,
        series_payload: dict[str, Any],
        book_summaries: list[dict[str, Any]],
    ) -> dict[str, Any]:
        with self.session_factory() as session:
            return self._persist_identity_bundle(
                session,
                series_id=series_id,
                source_path=source_path,
                series_payload=series_payload,
                book_summaries=book_summaries,
            )

    def resplit_book_scenes(
        self,
        *,
        book_ref: str,
        target_words: int = 700,
        allow_cross_chapter: bool = False,
        clear_dependent_rows: bool = True,
    ) -> dict[str, Any]:
        with self.session_factory() as session:
            return self._resplit_book_scenes(
                session,
                book_ref=book_ref,
                target_words=target_words,
                allow_cross_chapter=allow_cross_chapter,
                clear_dependent_rows=clear_dependent_rows,
            )

    def upsert_pipeline_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.session_factory() as session:
            row = self._upsert_pipeline_run(session, payload)
            session.commit()
            return {"id": row.id, "series_id": row.series_id, "run_id": row.run_id, "status": row.status}

    def get_pipeline_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            rows = session.execute(select(PipelineRun).order_by(PipelineRun.updated_at.desc())).scalars().all()
            return [self._pipeline_run_dict(session, row) for row in rows[:limit]]

    def get_latest_pipeline_run(self, *, series_id: str) -> dict[str, Any] | None:
        with self.session_factory() as session:
            rows = session.execute(
                select(PipelineRun)
                .where(PipelineRun.series_id == str(series_id))
                .order_by(PipelineRun.updated_at.desc())
            ).scalars().all()
            preferred = next(
                (
                    item for item in rows
                    if str(item.status_source or "").strip().lower() == "saga_tools_status"
                    and not str(item.run_dir or "").startswith("db://job/")
                ),
                None,
            )
            row = preferred or (rows[0] if rows else None)
            if row is None:
                return None
            return self._pipeline_run_dict(session, row)

    def get_series_books(self, series_id: str) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            rows = session.execute(
                select(Book)
                .where(Book.series_id == str(series_id))
                .order_by(Book.book_index.asc(), Book.updated_at.desc())
            ).scalars().all()
            payload: list[dict[str, Any]] = []
            for row in rows:
                payload.append(
                    {
                        "book_id": row.id,
                        "series_id": row.series_id,
                        "book_index": row.book_index,
                        "title": row.title,
                        "source_path": row.source_path or "",
                        "run_status": row.run_status or "",
                        "identity_provider": row.identity_provider or "",
                        "scene_analysis_quality": row.scene_analysis_quality if isinstance(row.scene_analysis_quality, dict) else {},
                        "metadata": row.metadata_json if isinstance(row.metadata_json, dict) else {},
                    }
                )
            return payload

    def upsert_dashboard_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.session_factory() as session:
            row = self._upsert_dashboard_job(session, payload)
            session.commit()
            return {"id": row.id, "status": row.status}

    def get_dashboard_jobs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            rows = session.execute(select(DashboardJob).order_by(DashboardJob.updated_at.desc())).scalars().all()
            return [self._dashboard_job_dict(row) for row in rows[:limit]]

    def get_dashboard_job(self, job_id: str) -> dict[str, Any] | None:
        with self.session_factory() as session:
            row = session.get(DashboardJob, job_id)
            return self._dashboard_job_dict(row) if row else None

    def upsert_provider_config(self, provider_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.session_factory() as session:
            row = self._upsert_provider_config(session, provider_name=provider_name, payload=payload)
            session.commit()
            return self._provider_config_dict(session, row)

    def get_provider_config(self, provider_name: str) -> dict[str, Any] | None:
        with self.session_factory() as session:
            row = session.execute(select(ProviderConfig).where(ProviderConfig.provider_name == str(provider_name))).scalar_one_or_none()
            return self._provider_config_dict(session, row) if row else None

    def get_provider_configs(self) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            rows = session.execute(select(ProviderConfig).order_by(ProviderConfig.provider_name.asc())).scalars().all()
            return [self._provider_config_dict(session, row) for row in rows]

    def upsert_provider_status(self, provider_name: str, label: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.session_factory() as session:
            row = self._upsert_provider_status(session, provider_name=provider_name, label=label, payload=payload)
            session.commit()
            return self._provider_status_dict(row)

    def get_provider_statuses(self, provider_name: str | None = None) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            query = select(ProviderAccountStatus)
            if provider_name:
                query = query.where(ProviderAccountStatus.provider_name == str(provider_name))
            rows = session.execute(query.order_by(ProviderAccountStatus.provider_name.asc(), ProviderAccountStatus.label.asc())).scalars().all()
            return [self._provider_status_dict(row) for row in rows]

    def delete_series_run(self, *, series_id: str, run_id: str | None = None) -> dict[str, Any]:
        with self.session_factory() as session:
            run_query = select(PipelineRun).where(PipelineRun.series_id == str(series_id))
            if run_id:
                run_query = run_query.where(PipelineRun.run_id == str(run_id))
            runs = session.execute(run_query).scalars().all()
            run_ids = [row.id for row in runs]
            if run_ids:
                session.execute(delete(PipelineRunBook).where(PipelineRunBook.pipeline_run_id.in_(run_ids)))
                session.execute(delete(PipelineRun).where(PipelineRun.id.in_(run_ids)))
            session.commit()
            return {"deleted_runs": len(runs)}

    def delete_dashboard_job(self, job_id: str) -> bool:
        with self.session_factory() as session:
            row = session.get(DashboardJob, job_id)
            if row is None:
                return False
            session.execute(delete(DashboardJobLog).where(DashboardJobLog.job_id == row.id))
            session.delete(row)
            session.commit()
            return True

    def append_dashboard_job_log(self, job_id: str, text: str, *, level: str | None = None) -> None:
        raw = str(text or "")
        if not raw:
            return
        with self.session_factory() as session:
            last_index = session.execute(
                select(DashboardJobLog.line_index)
                .where(DashboardJobLog.job_id == str(job_id))
                .order_by(DashboardJobLog.line_index.desc())
            ).scalars().first()
            next_index = int(last_index or 0)
            rows = [chunk for chunk in raw.splitlines() if str(chunk).strip()]
            for line in rows:
                next_index += 1
                session.add(
                    DashboardJobLog(
                        job_id=str(job_id),
                        line_index=next_index,
                        level=str(level or "").strip() or None,
                        line_text=str(line),
                    )
                )
            session.commit()

    def get_dashboard_job_log_tail(self, job_id: str, limit: int = 120) -> list[str]:
        with self.session_factory() as session:
            rows = session.execute(
                select(DashboardJobLog)
                .where(DashboardJobLog.job_id == str(job_id))
                .order_by(DashboardJobLog.line_index.desc())
            ).scalars().all()
            ordered = list(reversed(rows[: max(0, int(limit))]))
            return [str(row.line_text or "") for row in ordered]

    def register_uploaded_source(
        self,
        *,
        original_name: str,
        stored_path: str,
        size_bytes: int | None = None,
        mime_type: str | None = None,
        sha256: str | None = None,
        source_kind: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self.session_factory() as session:
            row = session.execute(
                select(UploadedSource).where(UploadedSource.stored_path == str(stored_path))
            ).scalar_one_or_none()
            if row is None:
                row = UploadedSource(stored_path=str(stored_path))
                session.add(row)
                session.flush()
            row.original_name = str(original_name or "").strip() or None
            row.size_bytes = self._int_or_none(size_bytes)
            row.mime_type = str(mime_type or "").strip() or None
            row.sha256 = str(sha256 or "").strip() or None
            row.source_kind = str(source_kind or "").strip() or None
            row.metadata_json = metadata if isinstance(metadata, dict) else {}
            session.commit()
            return {
                "id": row.id,
                "original_name": row.original_name or "",
                "stored_path": row.stored_path,
                "size_bytes": row.size_bytes or 0,
                "mime_type": row.mime_type or "",
                "sha256": row.sha256 or "",
                "source_kind": row.source_kind or "",
            }

    def get_uploaded_sources(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            rows = session.execute(
                select(UploadedSource).order_by(UploadedSource.created_at.desc())
            ).scalars().all()
            payload: list[dict[str, Any]] = []
            for row in rows[: max(0, int(limit))]:
                payload.append(
                    {
                        "id": row.id,
                        "original_name": row.original_name or "",
                        "stored_path": row.stored_path,
                        "size_bytes": row.size_bytes or 0,
                        "mime_type": row.mime_type or "",
                        "sha256": row.sha256 or "",
                        "source_kind": row.source_kind or "",
                        "metadata": row.metadata_json if isinstance(row.metadata_json, dict) else {},
                        "created_at": row.created_at.isoformat() if row.created_at else "",
                        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
                    }
                )
            return payload

    def store_generated_story(
        self,
        *,
        book_id: str,
        story_mode: str,
        title: str,
        user_prompt: str,
        canon_position: str,
        primary_pov_character: str,
        llm_provider: str,
        llm_model: str,
        status: str,
        output_text: str,
        blueprint: dict[str, Any] | None,
        progress: dict[str, Any] | None,
        verification: dict[str, Any] | None,
        metadata: dict[str, Any] | None,
        chapters: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        with self.session_factory() as session:
            row = GeneratedStory(
                book_id=str(book_id),
                story_mode=str(story_mode or "").strip() or None,
                title=str(title or "").strip() or None,
                user_prompt=str(user_prompt or "").strip() or None,
                canon_position=str(canon_position or "").strip() or None,
                primary_pov_character=str(primary_pov_character or "").strip() or None,
                llm_provider=str(llm_provider or "").strip() or None,
                llm_model=str(llm_model or "").strip() or None,
                status=str(status or "").strip() or None,
                output_text=str(output_text or "").strip() or None,
                blueprint_json=blueprint if isinstance(blueprint, (dict, list)) else None,
                progress_json=progress if isinstance(progress, (dict, list)) else None,
                verification_json=verification if isinstance(verification, (dict, list)) else None,
                metadata_json=metadata if isinstance(metadata, dict) else {},
            )
            session.add(row)
            session.flush()
            for chapter in chapters or []:
                if not isinstance(chapter, dict):
                    continue
                session.add(
                    GeneratedStoryChapter(
                        story_id=row.id,
                        chapter_number=self._int_or_none(chapter.get("chapter_number")) or 0,
                        chapter_title=str(chapter.get("chapter_title") or "").strip() or None,
                        outline_json=chapter.get("outline") if isinstance(chapter.get("outline"), (dict, list)) else None,
                        prose_text=str(chapter.get("prose_text") or "").strip() or None,
                        metadata_json=chapter.get("metadata") if isinstance(chapter.get("metadata"), dict) else {},
                    )
                )
            session.commit()
            return {
                "story_id": row.id,
                "book_id": row.book_id,
                "story_mode": row.story_mode or "",
                "title": row.title or "",
                "status": row.status or "",
            }

    def get_generated_stories(self, *, book_id: str | None = None) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            query = select(GeneratedStory).order_by(GeneratedStory.created_at.desc())
            if book_id:
                query = query.where(GeneratedStory.book_id == str(book_id))
            rows = session.execute(query).scalars().all()
            payload: list[dict[str, Any]] = []
            for row in rows:
                chapters = session.execute(
                    select(GeneratedStoryChapter)
                    .where(GeneratedStoryChapter.story_id == row.id)
                    .order_by(GeneratedStoryChapter.chapter_number.asc())
                ).scalars().all()
                payload.append(
                    {
                        "id": row.id,
                        "book_id": row.book_id,
                        "story_mode": row.story_mode or "",
                        "title": row.title or "",
                        "user_prompt": row.user_prompt or "",
                        "canon_position": row.canon_position or "",
                        "primary_pov_character": row.primary_pov_character or "",
                        "llm_provider": row.llm_provider or "",
                        "llm_model": row.llm_model or "",
                        "status": row.status or "",
                        "output_text": row.output_text or "",
                        "blueprint": row.blueprint_json if isinstance(row.blueprint_json, dict) else {},
                        "progress": row.progress_json if isinstance(row.progress_json, dict) else {},
                        "verification": row.verification_json if isinstance(row.verification_json, dict) else {},
                        "metadata": row.metadata_json if isinstance(row.metadata_json, dict) else {},
                        "chapters": [
                            {
                                "chapter_number": chapter.chapter_number,
                                "chapter_title": chapter.chapter_title or "",
                                "outline": chapter.outline_json if isinstance(chapter.outline_json, dict) else {},
                                "prose_text": chapter.prose_text or "",
                                "metadata": chapter.metadata_json if isinstance(chapter.metadata_json, dict) else {},
                            }
                            for chapter in chapters
                        ],
                    }
                )
            return payload

    def get_generated_story(self, story_id: str) -> dict[str, Any] | None:
        rows = self.get_generated_stories()
        return next((row for row in rows if str(row.get("id") or "") == str(story_id)), None)

    def get_generated_stories_for_series(self, series_id: str) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            books = session.execute(
                select(Book.id).where(Book.series_id == str(series_id))
            ).all()
        book_ids = {str(row[0]) for row in books}
        if not book_ids:
            return []
        return [row for row in self.get_generated_stories() if str(row.get("book_id") or "") in book_ids]

    def get_identity_series_payload(self, series_id: str) -> dict[str, Any] | None:
        with self.session_factory() as session:
            series = session.execute(select(IdentitySeries).where(IdentitySeries.series_id == str(series_id))).scalar_one_or_none()
            if series is None:
                return None
            books = session.execute(select(IdentityBook).where(IdentityBook.identity_series_id == series.id).order_by(IdentityBook.book_index.asc())).scalars().all()
            characters = session.execute(select(IdentityCharacter).where(IdentityCharacter.identity_series_id == series.id)).scalars().all()
            aliases = session.execute(select(IdentityAlias).where(IdentityAlias.identity_series_id == series.id)).scalars().all()
            refs = session.execute(select(IdentityReferenceEntity).where(IdentityReferenceEntity.identity_series_id == series.id)).scalars().all()
            narrators = session.execute(select(IdentityNarrator).where(IdentityNarrator.identity_series_id == series.id).order_by(IdentityNarrator.book_index.asc())).scalars().all()
            book_identity_paths = {
                str(book.book_slug or ""): str(book.pipeline_identity_path or "")
                for book in books
                if str(book.book_slug or "").strip() and str(book.pipeline_identity_path or "").strip()
            }
            return {
                "series_id": series.series_id,
                "provider": series.provider or "booknlp_clean",
                "source_path": series.source_path or "",
                "characters": [dict(row.payload_json or {}) for row in characters if isinstance(row.payload_json, dict)],
                "alias_index": {str(row.alias_key): str(row.target_character_id or "") for row in aliases if str(row.alias_key or "").strip()},
                "reference_entities": [dict(row.payload_json or {}) for row in refs if isinstance(row.payload_json, dict)],
                "narrators": [dict(row.payload_json or {}) for row in narrators if isinstance(row.payload_json, dict)],
                "book_identity_paths": book_identity_paths,
                "diagnostics": dict(series.metadata_json or {}),
            }

    def _persist_contract(self, session: Session, contract: dict[str, Any], *, contract_path: str | Path | None = None) -> dict[str, Any]:
        inputs = contract.get("inputs") or {}
        outputs = contract.get("outputs") or {}
        metadata = contract.get("metadata") or {}
        config = contract.get("configuration") or {}
        books = inputs.get("books") or []
        series_meta = inputs.get("series") or {}
        primary_book = books[0] if books else {}
        series = self._upsert_series(session, series_meta)
        book = self._upsert_book(session, series, primary_book, metadata, config, contract_path)
        self._clear_book_children(session, book.id)
        chapter_map = self._persist_chapters(session, book.id, outputs.get("chapters") or [])
        scene_map = self._persist_scenes(session, book.id, outputs, chapter_map)
        entity_map = self._persist_entities(session, book.id, outputs.get("entity_registry") or [])
        scene_map_by_ref = scene_map
        self._persist_entity_visual_details(session, book.id, entity_map, scene_map_by_ref)
        self._persist_character_profiles(session, book.id, outputs.get("character_profiles") or [], entity_map)
        self._persist_stable_states(session, book.id, outputs.get("stable_character_states") or [], entity_map)
        event_map = self._persist_events(session, book.id, outputs.get("event_ledger") or [], scene_map)
        self._persist_timeline(session, book.id, outputs.get("timeline") or [], event_map)
        self._persist_visual_prompts(session, book.id, outputs.get("visual_prompt_sets") or {}, entity_map)
        session.commit()
        return {
            "series_id": book.series_id,
            "book_id": book.id,
            "book_title": book.title,
            "scene_count": len(scene_map),
            "entity_count": len(entity_map),
            "event_count": len(event_map),
        }

    def _persist_identity_bundle(
        self,
        session: Session,
        *,
        series_id: str,
        source_path: str | Path,
        series_payload: dict[str, Any],
        book_summaries: list[dict[str, Any]],
    ) -> dict[str, Any]:
        existing = session.execute(select(IdentitySeries).where(IdentitySeries.series_id == str(series_id))).scalar_one_or_none()
        if existing is None:
            existing = IdentitySeries(series_id=str(series_id))
            session.add(existing)
            session.flush()
        existing.provider = str(series_payload.get("provider") or "booknlp_clean").strip() or "booknlp_clean"
        existing.source_path = str(source_path)
        existing.character_count = len(series_payload.get("characters") or [])
        existing.alias_count = len(series_payload.get("alias_index") or {})
        existing.reference_entity_count = len(series_payload.get("reference_entities") or [])
        existing.narrator_count = len(series_payload.get("narrators") or [])
        existing.metadata_json = series_payload.get("diagnostics") if isinstance(series_payload.get("diagnostics"), (dict, list)) else {"diagnostics": {}}

        for model in [IdentityBook, IdentityAlias, IdentityCharacter, IdentityNarrator, IdentityReferenceEntity]:
            session.execute(delete(model).where(model.identity_series_id == existing.id))

        for summary in book_summaries:
            output_dir = Path(str(summary.get("output_dir") or ""))
            session.add(
                IdentityBook(
                    identity_series_id=existing.id,
                    book_index=self._int_or_none(summary.get("book_index")),
                    book_slug=str(summary.get("book_slug") or "").strip() or None,
                    title=str(summary.get("title") or "").strip() or None,
                    output_dir=str(output_dir) if str(output_dir) else None,
                    pipeline_identity_path=str(summary.get("pipeline_identity_path") or "").strip() or None,
                    raw_identity_path=str(output_dir / "booknlp_small_identity_result.json") if str(output_dir) else None,
                    clean_identity_path=str(output_dir / "booknlp_small_clean_identity_result.json") if str(output_dir) else None,
                    cleanup_report_path=str(output_dir / "booknlp_cleanup_report.md") if str(output_dir) else None,
                    character_count=self._int_or_none(summary.get("character_count")),
                    alias_count=self._int_or_none(summary.get("alias_count")),
                    reference_entity_count=self._int_or_none(summary.get("reference_entity_count")),
                    suppressed_cluster_count=self._int_or_none(summary.get("suppressed_cluster_count")),
                    narrator_json=summary.get("narrator") if isinstance(summary.get("narrator"), (dict, list)) else None,
                    diagnostics_json={k: v for k, v in summary.items() if k not in {"narrator"}},
                )
            )

        for row in series_payload.get("characters") or []:
            book_sources = row.get("book_sources") or []
            session.add(
                IdentityCharacter(
                    identity_series_id=existing.id,
                    character_id=str(row.get("id") or "").strip(),
                    display_name=str(row.get("display_name") or "").strip() or None,
                    mention_count=sum(int(src.get("mention_count", 0) or 0) for src in book_sources),
                    quote_count=sum(int(src.get("quote_count", 0) or 0) for src in book_sources),
                    risk_flags=row.get("risk_flags") if isinstance(row.get("risk_flags"), (dict, list)) else None,
                    book_sources=book_sources if isinstance(book_sources, (dict, list)) else None,
                    payload_json=row,
                )
            )
        for alias_key, target_character_id in (series_payload.get("alias_index") or {}).items():
            session.add(
                IdentityAlias(
                    identity_series_id=existing.id,
                    alias_key=str(alias_key),
                    target_character_id=str(target_character_id or "").strip() or None,
                )
            )
        for row in series_payload.get("reference_entities") or []:
            session.add(
                IdentityReferenceEntity(
                    identity_series_id=existing.id,
                    reference_id=str(row.get("id") or "").strip() or None,
                    display_name=str(row.get("display_name") or "").strip() or None,
                    category=str(row.get("category") or "").strip() or None,
                    aliases=row.get("aliases") if isinstance(row.get("aliases"), (dict, list)) else None,
                    risk_flags=row.get("risk_flags") if isinstance(row.get("risk_flags"), (dict, list)) else None,
                    book_sources=row.get("book_sources") if isinstance(row.get("book_sources"), (dict, list)) else None,
                    payload_json=row,
                )
            )
        for row in series_payload.get("narrators") or []:
            session.add(
                IdentityNarrator(
                    identity_series_id=existing.id,
                    book_index=self._int_or_none(row.get("book_index")),
                    book_slug=str(row.get("book_slug") or "").strip() or None,
                    narrator_name=str(row.get("name") or row.get("display_name") or row.get("narrator_name") or "").strip() or None,
                    payload_json=row,
                )
            )
        session.commit()
        return {
            "series_id": existing.series_id,
            "character_count": existing.character_count or 0,
            "alias_count": existing.alias_count or 0,
            "reference_entity_count": existing.reference_entity_count or 0,
            "book_count": len(book_summaries),
        }

    def _upsert_pipeline_run(self, session: Session, payload: dict[str, Any]) -> PipelineRun:
        series_id = str(payload.get("series_id") or "").strip()
        run_id = str(payload.get("run_id") or "").strip()
        existing = session.execute(
            select(PipelineRun).where(PipelineRun.series_id == series_id, PipelineRun.run_id == run_id)
        ).scalar_one_or_none()
        if existing is None:
            existing = PipelineRun(series_id=series_id, run_id=run_id)
            session.add(existing)
            session.flush()
        existing.series_title = str(payload.get("series_title") or "").strip() or existing.series_title
        existing.run_dir = str(payload.get("run_dir") or "").strip() or existing.run_dir
        existing.log_path = str(payload.get("log_path") or "").strip() or existing.log_path
        existing.status = str(payload.get("status") or "").strip() or existing.status
        existing.status_reason = str(payload.get("status_reason") or "").strip() or existing.status_reason
        existing.status_source = str(payload.get("status_source") or "").strip() or existing.status_source
        existing.command_mode = str(payload.get("command_mode") or "").strip() or existing.command_mode
        existing.worker_pid = self._int_or_none(payload.get("worker_pid"))
        existing.started_at_utc = str(payload.get("started_at_utc") or "").strip() or existing.started_at_utc
        existing.finished_at_utc = str(payload.get("finished_at_utc") or "").strip() or existing.finished_at_utc
        existing.latest_progress_json = payload.get("latest_progress_json") if isinstance(payload.get("latest_progress_json"), (dict, list)) else existing.latest_progress_json
        existing.status_payload_json = payload if isinstance(payload, dict) else existing.status_payload_json

        session.execute(delete(PipelineRunBook).where(PipelineRunBook.pipeline_run_id == existing.id))
        for row in payload.get("books") or []:
            if not isinstance(row, dict):
                continue
            session.add(
                PipelineRunBook(
                    pipeline_run_id=existing.id,
                    series_id=series_id,
                    run_id=run_id,
                    book_index=self._int_or_none(row.get("book_index")),
                    title=str(row.get("title") or "").strip() or None,
                    source_path=str(row.get("path") or "").strip() or None,
                    status=str(row.get("status") or "").strip() or None,
                    phase=str(row.get("phase") or "").strip() or None,
                    status_reason=str(row.get("error") or "").strip() or None,
                    scenes_processed=self._int_or_none(row.get("scenes_processed")),
                    total_scenes=self._int_or_none(row.get("total_scenes")),
                    failed_scenes=self._int_or_none(row.get("failed_scenes")),
                    successful_scenes=self._int_or_none(row.get("successful_scenes")),
                    checkpoint_path=str(row.get("checkpoint_path") or "").strip() or None,
                    contract_path=str(row.get("contract_path") or "").strip() or None,
                    started_at_utc=str(row.get("started_at_utc") or "").strip() or None,
                    finished_at_utc=str(row.get("finished_at_utc") or "").strip() or None,
                    elapsed_seconds=self._float_or_none(row.get("elapsed_seconds")),
                    last_progress_json=row.get("last_progress") if isinstance(row.get("last_progress"), (dict, list)) else None,
                    raw_payload_json=row,
                )
            )
        session.flush()
        return existing

    def _pipeline_run_dict(self, session: Session, row: PipelineRun) -> dict[str, Any]:
        books = session.execute(
            select(PipelineRunBook)
            .where(PipelineRunBook.pipeline_run_id == row.id)
            .order_by(PipelineRunBook.book_index.asc(), PipelineRunBook.created_at.asc())
        ).scalars().all()
        book_rows = []
        total_scenes = 0
        failed_books = 0
        progress = row.latest_progress_json if isinstance(row.latest_progress_json, dict) else None
        for book in books:
            total_scenes += int(book.total_scenes or book.scenes_processed or 0)
            if str(book.status or "").strip().lower() in {"failed", "partial", "paused", "blocked_rate_limit"}:
                failed_books += 1
            book_rows.append(
                {
                    "path": book.contract_path or book.source_path or "",
                    "name": book.title or "",
                    "run_status": book.status or "unknown",
                    "status_reason": book.status_reason or "",
                    "scenes": int(book.total_scenes or book.scenes_processed or 0),
                    "scenes_processed": int(book.scenes_processed or 0),
                    "total_scenes": int(book.total_scenes or 0),
                    "failed_scenes": self._int_or_none(book.failed_scenes),
                    "successful_scenes": self._int_or_none(book.successful_scenes),
                }
            )
        log_tail: list[str] = []
        log_path = str(row.log_path or "").strip()
        if log_path:
            try:
                log_tail = Path(log_path).read_text(encoding="utf-8", errors="replace").splitlines()[-120:]
            except Exception:
                log_tail = []
        return {
            "path": row.run_dir or "",
            "series_id": row.series_id,
            "run_id": row.run_id,
            "mtime": row.updated_at.timestamp() if row.updated_at else 0.0,
            "status": row.status or "unknown",
            "status_reason": row.status_reason or "",
            "status_source": row.status_source or "",
            "books": len(books),
            "contracts": sum(1 for book in books if str(book.contract_path or "").strip()),
            "failed_books": failed_books,
            "total_scenes": total_scenes,
            "book_rows": book_rows,
            "worker_pid": row.worker_pid,
            "status_update_age_seconds": None,
            "progress": progress,
            "log_tail": log_tail,
            "command": row.command_mode or "",
            "started_at": row.started_at_utc or "",
            "finished_at": row.finished_at_utc or "",
        }

    def _upsert_dashboard_job(self, session: Session, payload: dict[str, Any]) -> DashboardJob:
        job_id = str(payload.get("id") or "").strip()
        existing = session.get(DashboardJob, job_id)
        if existing is None:
            existing = DashboardJob(id=job_id)
            session.add(existing)
            session.flush()
        existing.job_type = str(payload.get("type") or existing.job_type or "").strip() or existing.job_type
        existing.status = str(payload.get("status") or existing.status or "").strip() or existing.status
        existing.status_reason = str(payload.get("status_reason") or existing.status_reason or "").strip() or existing.status_reason
        existing.command = str(payload.get("command") or existing.command or "").strip() or existing.command
        existing.pid = self._int_or_none(payload.get("pid"))
        existing.return_code = self._int_or_none(payload.get("return_code"))
        existing.started_at_utc = str(payload.get("started_at") or payload.get("started_at_utc") or existing.started_at_utc or "").strip() or existing.started_at_utc
        existing.finished_at_utc = str(payload.get("finished_at") or payload.get("finished_at_utc") or existing.finished_at_utc or "").strip() or existing.finished_at_utc
        existing.progress_json = payload.get("progress") if isinstance(payload.get("progress"), (dict, list)) else existing.progress_json
        existing.request_json = payload.get("request") if isinstance(payload.get("request"), (dict, list)) else existing.request_json
        existing.artifacts_json = payload.get("artifacts") if isinstance(payload.get("artifacts"), (dict, list)) else existing.artifacts_json
        existing.error = str(payload.get("error") or existing.error or "").strip() or existing.error
        existing.log_path = str(payload.get("log_path") or existing.log_path or "").strip() or existing.log_path
        existing.metadata_json = payload
        session.flush()
        return existing

    def _dashboard_job_dict(self, row: DashboardJob) -> dict[str, Any]:
        return {
            "id": row.id,
            "type": row.job_type or "",
            "status": row.status or "unknown",
            "status_reason": row.status_reason or "",
            "command": row.command or "",
            "pid": row.pid,
            "return_code": row.return_code,
            "started_at": row.started_at_utc or "",
            "finished_at": row.finished_at_utc or "",
            "progress": row.progress_json if isinstance(row.progress_json, dict) else None,
            "request": row.request_json if isinstance(row.request_json, dict) else {},
            "artifacts": row.artifacts_json if isinstance(row.artifacts_json, dict) else {},
            "error": row.error or "",
            "log_path": row.log_path or "",
            "log_tail": self.get_dashboard_job_log_tail(row.id, limit=120),
        }

    def _upsert_provider_config(self, session: Session, *, provider_name: str, payload: dict[str, Any]) -> ProviderConfig:
        provider_key = str(provider_name or "").strip().lower()
        existing = session.execute(select(ProviderConfig).where(ProviderConfig.provider_name == provider_key)).scalar_one_or_none()
        if existing is None:
            existing = ProviderConfig(provider_name=provider_key)
            session.add(existing)
            session.flush()
        existing.active_index = self._int_or_none(payload.get("active_index"))
        existing.transport = str(payload.get("transport") or existing.transport or "").strip() or existing.transport
        existing.metadata_json = payload

        session.execute(delete(ProviderAccount).where(ProviderAccount.provider_name == provider_key))
        for index, row in enumerate(payload.get("accounts") or []):
            if not isinstance(row, dict):
                continue
            session.add(
                ProviderAccount(
                    provider_name=provider_key,
                    label=str(row.get("label") or f"account-{index + 1}").strip(),
                    account_index=self._int_or_none(row.get("index", index)),
                    email=str(row.get("email") or "").strip() or None,
                    auth_mode=str(row.get("auth_mode") or "").strip() or None,
                    api_key=str(row.get("api_key") or "").strip() or None,
                    password=str(row.get("password") or "").strip() or None,
                    account_id=str(row.get("account_id") or "").strip() or None,
                    is_active=bool(row.get("active")),
                    metadata_json=row,
                )
            )
        session.flush()
        return existing

    def _provider_config_dict(self, session: Session, row: ProviderConfig) -> dict[str, Any]:
        accounts = session.execute(
            select(ProviderAccount)
            .where(ProviderAccount.provider_name == row.provider_name)
            .order_by(ProviderAccount.account_index.asc(), ProviderAccount.created_at.asc())
        ).scalars().all()
        return {
            "provider_name": row.provider_name,
            "active_index": int(row.active_index or 0),
            "transport": row.transport or "",
            "accounts": [
                {
                    "index": int(account.account_index or idx),
                    "label": account.label,
                    "email": account.email or "",
                    "auth_mode": account.auth_mode or "",
                    "api_key": account.api_key or "",
                    "password": account.password or "",
                    "account_id": account.account_id or "",
                    "active": bool(account.is_active),
                    "has_api_key": bool(str(account.api_key or "").strip()),
                    "has_password": bool(str(account.password or "").strip()),
                    "metadata": account.metadata_json if isinstance(account.metadata_json, dict) else {},
                }
                for idx, account in enumerate(accounts)
            ],
            "metadata": row.metadata_json if isinstance(row.metadata_json, dict) else {},
        }

    def _upsert_provider_status(self, session: Session, *, provider_name: str, label: str, payload: dict[str, Any]) -> ProviderAccountStatus:
        provider_key = str(provider_name or "").strip().lower()
        label_key = str(label or "").strip()
        existing = session.execute(
            select(ProviderAccountStatus).where(
                ProviderAccountStatus.provider_name == provider_key,
                ProviderAccountStatus.label == label_key,
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = ProviderAccountStatus(provider_name=provider_key, label=label_key)
            session.add(existing)
            session.flush()
        existing.probe_status = str(payload.get("probe_status") or payload.get("status") or existing.probe_status or "").strip() or existing.probe_status
        existing.transport = str(payload.get("transport") or existing.transport or "").strip() or existing.transport
        existing.resolved_model = str(payload.get("resolved_model") or payload.get("model") or existing.resolved_model or "").strip() or existing.resolved_model
        existing.quota_source = str(payload.get("quota_source") or existing.quota_source or "").strip() or existing.quota_source
        existing.remaining_requests_minute = self._int_or_none(payload.get("remaining_requests_minute"))
        existing.remaining_input_tokens_minute = self._int_or_none(payload.get("remaining_input_tokens_minute"))
        existing.remaining_output_tokens_minute = self._int_or_none(payload.get("remaining_output_tokens_minute"))
        existing.remaining_requests_day = self._int_or_none(payload.get("remaining_requests_day"))
        existing.remaining_tokens_day = self._int_or_none(payload.get("remaining_tokens_day"))
        existing.credits_remaining = str(payload.get("credits_remaining") or existing.credits_remaining or "").strip() or existing.credits_remaining
        existing.last_checked_at_utc = str(payload.get("last_checked_at_utc") or "").strip() or existing.last_checked_at_utc
        existing.detail = str(payload.get("detail") or existing.detail or "").strip() or existing.detail
        existing.payload_json = payload
        session.flush()
        return existing

    def _provider_status_dict(self, row: ProviderAccountStatus) -> dict[str, Any]:
        return {
            "provider_name": row.provider_name,
            "label": row.label,
            "probe_status": row.probe_status or "unknown",
            "transport": row.transport or "",
            "resolved_model": row.resolved_model or "",
            "quota_source": row.quota_source or "",
            "remaining_requests_minute": row.remaining_requests_minute,
            "remaining_input_tokens_minute": row.remaining_input_tokens_minute,
            "remaining_output_tokens_minute": row.remaining_output_tokens_minute,
            "remaining_requests_day": row.remaining_requests_day,
            "remaining_tokens_day": row.remaining_tokens_day,
            "credits_remaining": row.credits_remaining or "",
            "last_checked_at_utc": row.last_checked_at_utc or "",
            "detail": row.detail or "",
            "payload": row.payload_json if isinstance(row.payload_json, dict) else {},
        }

    def _upsert_series(self, session: Session, series_meta: dict[str, Any]) -> Series | None:
        series_id = str(series_meta.get("series_id") or "").strip()
        if not series_id:
            return None
        existing = session.execute(select(Series).where(Series.series_id == series_id)).scalar_one_or_none()
        if existing is None:
            existing = Series(series_id=series_id, title=str(series_meta.get("series_title") or series_id), metadata_json=series_meta)
            session.add(existing)
            session.flush()
        else:
            existing.title = str(series_meta.get("series_title") or existing.title or series_id)
            existing.metadata_json = series_meta
        return existing

    def _upsert_book(
        self,
        session: Session,
        series: Series | None,
        primary_book: dict[str, Any],
        metadata: dict[str, Any],
        config: dict[str, Any],
        contract_path: str | Path | None,
    ) -> Book:
        series_id = series.series_id if series else str(((metadata.get("series") or {}).get("series_id")) or "").strip() or None
        book_index = self._int_or_none(primary_book.get("book_index"))
        title = str(primary_book.get("title") or metadata.get("book_title") or "Unknown Book").strip()
        stmt = select(Book).where(Book.series_id == series_id, Book.book_index == book_index) if series_id is not None and book_index is not None else select(Book).where(Book.title == title)
        existing = session.execute(stmt).scalar_one_or_none()
        contract_path_str = str(contract_path) if contract_path else None
        if existing is None:
            existing = Book(
                series_fk=series.id if series else None,
                series_id=series_id,
                book_index=book_index,
                title=title,
            )
            session.add(existing)
            session.flush()
        existing.series_fk = series.id if series else None
        existing.series_id = series_id
        existing.book_index = book_index
        existing.title = title
        existing.source_path = str(primary_book.get("path") or "").strip() or None
        existing.source_hash_sha256 = str(primary_book.get("source_hash_sha256") or "").strip() or None
        existing.source_type = str(primary_book.get("type") or "").strip() or None
        existing.contract_path = contract_path_str
        existing.run_status = str(metadata.get("run_status") or contract_path and "success" or "").strip() or None
        existing.analysis_model = str(config.get("analysis_model_resolved") or config.get("analysis_model") or "").strip() or None
        existing.analysis_provider_mode = str(config.get("analysis_provider_mode") or "").strip() or None
        existing.identity_provider = str(config.get("identity_provider") or "").strip() or None
        existing.scene_failure_policy = str(config.get("scene_failure_policy") or "").strip() or None
        existing.scene_analysis_quality = metadata.get("scene_analysis_quality") if isinstance(metadata.get("scene_analysis_quality"), (dict, list)) else None
        existing.metadata_json = {"metadata": metadata, "configuration": config, "inputs": primary_book}
        session.flush()
        return existing

    def _clear_book_children(self, session: Session, book_id: str) -> None:
        for model in [
            GeneratedImage,
            VisualPrompt,
            CharacterVisualSceneState,
            CharacterVisualBaseline,
            CreatureVisualBaseline,
            ObjectSceneState,
            ObjectVisualBaseline,
            LocationSceneState,
            LocationVisualBaseline,
            TimelineRow,
            Event,
            StableCharacterState,
            CharacterProfile,
            Entity,
            Scene,
            Chapter,
        ]:
            session.execute(delete(model).where(model.book_id == book_id))
        session.flush()

    def _clear_book_analysis_rows(self, session: Session, book_id: str) -> None:
        for model in [
            GeneratedImage,
            VisualPrompt,
            CharacterVisualSceneState,
            CharacterVisualBaseline,
            CreatureVisualBaseline,
            ObjectSceneState,
            ObjectVisualBaseline,
            LocationSceneState,
            LocationVisualBaseline,
            TimelineRow,
            Event,
            StableCharacterState,
            CharacterProfile,
            Entity,
            Scene,
        ]:
            session.execute(delete(model).where(model.book_id == book_id))
        session.flush()

    def _resplit_book_scenes(
        self,
        session: Session,
        *,
        book_ref: str,
        target_words: int = 700,
        allow_cross_chapter: bool = False,
        clear_dependent_rows: bool = True,
    ) -> dict[str, Any]:
        value = str(book_ref or "").strip()
        book_id = value.split("db://book/", 1)[-1].strip() if value.startswith("db://book/") else value
        book = session.get(Book, book_id)
        if book is None:
            raise FileNotFoundError(f"Book not found in SQLite: {book_ref}")
        chapter_rows = session.execute(
            select(Chapter).where(Chapter.book_id == book.id).order_by(Chapter.chapter_index.asc())
        ).scalars().all()
        if not chapter_rows:
            raise ValueError(f"No chapters stored for book: {book_ref}")

        chapters: list[dict[str, Any]] = []
        for row in chapter_rows:
            metadata = dict(row.metadata_json or {})
            chapters.append(
                {
                    "book_index": int(book.book_index or 1),
                    "chapter_index": int(row.chapter_index),
                    "chapter_title": str(row.title or metadata.get("title") or metadata.get("chapter_title") or "").strip(),
                    "content": str(row.text or metadata.get("text") or metadata.get("content") or "").strip(),
                    "source_file": str(book.source_path or "").strip(),
                }
            )

        extractor = SceneExtractor.from_target_words(int(target_words or 700))
        scene_rows = extractor.extract_many(chapters, allow_cross_chapter=bool(allow_cross_chapter))
        if clear_dependent_rows:
            self._clear_book_analysis_rows(session, book.id)
        else:
            session.execute(delete(Scene).where(Scene.book_id == book.id))
            session.flush()

        chapter_map = {row.chapter_index: row for row in chapter_rows}
        scene_map: dict[tuple[int, int], Scene] = {}
        for row in scene_rows:
            chapter_index = self._int_or_none(row.get("chapter_index"))
            scene_index = self._int_or_none(row.get("scene_index"))
            if chapter_index is None or scene_index is None:
                continue
            chapter = chapter_map.get(chapter_index)
            payload = {
                "book_index": int(book.book_index or 1),
                "chapter_index": chapter_index,
                "scene_index": scene_index,
                "text": str(row.get("text") or "").strip(),
                "length": self._word_count(row.get("text")),
                "scene_summary": "",
                "events": [],
                "entities_present": [],
                "entity_descriptions": [],
                "state_changes": [],
                "relationship_changes": [],
                "location": {},
                "source_chapter_indices": list(row.get("source_chapter_indices") or [chapter_index]),
                "end_chapter_index": self._int_or_none(row.get("end_chapter_index")) or chapter_index,
                "source_files": list(row.get("source_files") or []),
                "split_origin": {
                    "method": "scene_extractor",
                    "target_words": int(target_words or 700),
                    "allow_cross_chapter": bool(allow_cross_chapter),
                },
                "final_status": "pending_analysis",
            }
            scene = Scene(
                book_id=book.id,
                chapter_id=chapter.id if chapter else None,
                book_index=int(book.book_index or 1),
                chapter_index=chapter_index,
                scene_index=scene_index,
                summary=None,
                text=payload["text"],
                location_name=None,
                location_description=None,
                final_status="pending_analysis",
                error_category=None,
                last_error=None,
                provider=None,
                model=None,
                provider_account_alias=None,
                rotation_used=None,
                rotation_attempt_count=None,
                analysis_duration_seconds=None,
                payload_json=payload,
            )
            session.add(scene)
            session.flush()
            scene_map[(chapter_index, scene_index)] = scene

        book.run_status = "split_ready"
        book.scene_analysis_quality = {
            "total_scenes": len(scene_map),
            "successful_scenes": 0,
            "failed_scenes": 0,
            "scene_split_only": True,
            "target_words": int(target_words or 700),
            "allow_cross_chapter": bool(allow_cross_chapter),
        }
        metadata = dict(book.metadata_json or {})
        metadata["scene_splitter"] = {
            "target_words": int(target_words or 700),
            "allow_cross_chapter": bool(allow_cross_chapter),
            "scene_count": len(scene_map),
        }
        book.metadata_json = metadata
        session.commit()
        return {
            "book_id": book.id,
            "series_id": book.series_id or "",
            "book_title": book.title,
            "chapter_count": len(chapter_rows),
            "scene_count": len(scene_map),
            "target_words": int(target_words or 700),
            "allow_cross_chapter": bool(allow_cross_chapter),
            "cleared_dependents": bool(clear_dependent_rows),
        }

    def _persist_chapters(self, session: Session, book_id: str, chapters: list[dict[str, Any]]) -> dict[int, Chapter]:
        chapter_map: dict[int, Chapter] = {}
        for row in chapters:
            if not isinstance(row, dict):
                continue
            chapter_index = self._int_or_none(row.get("chapter_index"))
            if chapter_index is None:
                continue
            chapter_title = str(row.get("title") or row.get("chapter_title") or "").strip()
            chapter_text = str(row.get("text") or row.get("content") or "").strip()
            chapter = Chapter(
                book_id=book_id,
                chapter_index=chapter_index,
                title=chapter_title or None,
                text=chapter_text or None,
                word_count=self._word_count(chapter_text),
                metadata_json=row,
            )
            session.add(chapter)
            session.flush()
            chapter_map[chapter_index] = chapter
        return chapter_map

    def _persist_scenes(self, session: Session, book_id: str, outputs: dict[str, Any], chapter_map: dict[int, Chapter]) -> dict[tuple[int, int], Scene]:
        scene_rows = outputs.get("resolved_scene_analyses") or outputs.get("scene_analyses") or []
        scene_map: dict[tuple[int, int], Scene] = {}
        for row in scene_rows:
            if not isinstance(row, dict):
                continue
            chapter_index = self._int_or_none(row.get("chapter_index"))
            scene_index = self._int_or_none(row.get("scene_index"))
            if chapter_index is None or scene_index is None:
                continue
            chapter = chapter_map.get(chapter_index)
            location = row.get("location") or {}
            scene = Scene(
                book_id=book_id,
                chapter_id=chapter.id if chapter else None,
                book_index=self._int_or_none(row.get("book_index")),
                chapter_index=chapter_index,
                scene_index=scene_index,
                summary=str(row.get("scene_summary") or "").strip() or None,
                text=str(row.get("text") or "").strip() or None,
                location_name=str(location.get("name") or "").strip() or None,
                location_description=str(location.get("description") or "").strip() or None,
                final_status=str(row.get("final_status") or "").strip() or None,
                error_category=str(row.get("error_category") or "").strip() or None,
                last_error=str(row.get("last_error") or row.get("error") or "").strip() or None,
                provider=str(row.get("provider") or "").strip() or None,
                model=str(row.get("resolved_model") or row.get("model") or "").strip() or None,
                provider_account_alias=str(row.get("provider_account_alias") or "").strip() or None,
                rotation_used=self._bool_or_none(row.get("rotation_used")),
                rotation_attempt_count=self._int_or_none(row.get("rotation_attempt_count")),
                analysis_duration_seconds=self._float_or_none(row.get("analysis_duration_seconds")),
                payload_json=row,
            )
            session.add(scene)
            session.flush()
            scene_map[(chapter_index, scene_index)] = scene
        return scene_map

    def _persist_entities(self, session: Session, book_id: str, entity_rows: list[dict[str, Any]]) -> dict[tuple[str, str], Entity]:
        entity_map: dict[tuple[str, str], Entity] = {}
        for row in entity_rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "").strip()
            entity_type = str(row.get("entity_type") or "").strip().lower()
            if not name or not entity_type:
                continue
            first_seen = row.get("first_seen") or {}
            entity = Entity(
                book_id=book_id,
                canonical_name=name,
                entity_type=entity_type,
                mention_count=self._int_or_none(row.get("mention_count")),
                first_seen_book_index=self._int_or_none(first_seen.get("book_index")),
                first_seen_chapter_index=self._int_or_none(first_seen.get("chapter_index")),
                first_seen_scene_index=self._int_or_none(first_seen.get("scene_index")),
                entity_context=str(row.get("entity_context") or "").strip() or None,
                initial_physical_description=row.get("initial_physical_description") if isinstance(row.get("initial_physical_description"), (dict, list)) else None,
                first_appearance_profile=row.get("first_appearance_profile") if isinstance(row.get("first_appearance_profile"), (dict, list)) else None,
                typed_attributes=row.get("typed_attributes") if isinstance(row.get("typed_attributes"), (dict, list)) else None,
                latest_world_state=row.get("latest_world_state") if isinstance(row.get("latest_world_state"), (dict, list)) else None,
                narrative_roles=row.get("narrative_roles") if isinstance(row.get("narrative_roles"), (dict, list)) else None,
                descriptions=row.get("descriptions") if isinstance(row.get("descriptions"), (dict, list)) else None,
                state_changes=row.get("state_changes") if isinstance(row.get("state_changes"), (dict, list)) else None,
                event_links=row.get("event_links") if isinstance(row.get("event_links"), (dict, list)) else None,
                visual_change_log=row.get("visual_change_log") if isinstance(row.get("visual_change_log"), (dict, list)) else None,
                analysis_quality_flags=row.get("analysis_quality_flags") if isinstance(row.get("analysis_quality_flags"), (dict, list)) else None,
                baseline_visual_prompt=None,
                generated_image_path=None,
                generated_image_bytes=None,
                metadata_json=row,
            )
            session.add(entity)
            session.flush()
            entity_map[(name.lower(), entity_type)] = entity
        return entity_map

    def _persist_character_profiles(self, session: Session, book_id: str, profiles: list[dict[str, Any]], entity_map: dict[tuple[str, str], Entity]) -> None:
        for row in profiles:
            if not isinstance(row, dict):
                continue
            name = str(row.get("character_name") or row.get("name") or "").strip()
            if not name:
                continue
            entity = entity_map.get((name.lower(), "character"))
            session.add(CharacterProfile(
                book_id=book_id,
                entity_id=entity.id if entity else None,
                character_name=name,
                payload_json=row,
            ))

    def _persist_entity_visual_details(
        self,
        session: Session,
        book_id: str,
        entity_map: dict[tuple[str, str], Entity],
        scene_map: dict[tuple[int, int], Scene],
    ) -> None:
        for (_, entity_type), entity in entity_map.items():
            persistent_traits = (entity.first_appearance_profile or {}).get("persistent_traits") or (entity.latest_world_state or {}).get("persistent_traits") or {}
            evidence_excerpt = str(((entity.initial_physical_description or {}).get("description")) or entity.entity_context or "").strip() or None
            source_scene_json = (entity.first_appearance_profile or {}).get("source") or {}
            if entity_type == "character":
                session.add(CharacterVisualBaseline(
                    book_id=book_id,
                    entity_id=entity.id,
                    gender_presentation=self._text(persistent_traits.get("gender_presentation")),
                    species_or_race=self._text(persistent_traits.get("species_or_race")),
                    apparent_age_group=self._text(persistent_traits.get("apparent_age_group")),
                    height_impression=self._text(persistent_traits.get("height_impression")),
                    build=self._text(persistent_traits.get("build")),
                    skin_tone_or_complexion=self._text(persistent_traits.get("skin_tone_or_complexion")),
                    hair_color=self._text(persistent_traits.get("hair_color")),
                    hair_length_or_style=self._text(persistent_traits.get("hair_length_or_style")),
                    eye_color=self._text(persistent_traits.get("eye_color")),
                    facial_features=self._text(persistent_traits.get("facial_features")),
                    distinguishing_marks=self._text(persistent_traits.get("distinguishing_marks")),
                    default_clothing_style=self._text(persistent_traits.get("default_clothing_style")),
                    default_accessories=self._text(persistent_traits.get("default_accessories")),
                    default_footwear=self._text(persistent_traits.get("default_footwear")),
                    signature_items=self._text(persistent_traits.get("signature_items")),
                    fantasy_features=self._text(persistent_traits.get("fantasy_features")),
                    world_genre_cues=self._text(persistent_traits.get("world_genre_cues")),
                    evidence_excerpt=evidence_excerpt,
                    source_scene_json=source_scene_json if isinstance(source_scene_json, (dict, list)) else None,
                ))
                for row in entity.metadata_json.get("scene_visual_states", []) if isinstance(entity.metadata_json, dict) else []:
                    state = row.get("state") or {}
                    scene = scene_map.get((self._int_or_none(row.get("chapter_index")), self._int_or_none(row.get("scene_index"))))
                    session.add(CharacterVisualSceneState(
                        book_id=book_id,
                        entity_id=entity.id,
                        scene_id=scene.id if scene else None,
                        chapter_index=self._int_or_none(row.get("chapter_index")),
                        scene_index=self._int_or_none(row.get("scene_index")),
                        scene_outfit=self._text(state.get("scene_outfit")),
                        scene_accessories=self._text(state.get("scene_accessories")),
                        scene_footwear=self._text(state.get("scene_footwear")),
                        visible_condition=self._text(state.get("visible_condition")),
                        injuries=self._text(state.get("injuries")),
                        dirt_blood_markings=self._text(state.get("dirt_blood_markings")),
                        body_language=self._text(state.get("body_language")),
                        expression=self._text(state.get("expression")),
                        carried_items=self._text(state.get("carried_items")),
                        temporary_effects=self._text(state.get("temporary_effects")),
                        source_scene_json=row,
                    ))
            elif entity_type == "creature":
                session.add(CreatureVisualBaseline(
                    book_id=book_id,
                    entity_id=entity.id,
                    species_kind=self._text(persistent_traits.get("species_kind")),
                    size_class=self._text(persistent_traits.get("size_class")),
                    body_plan=self._text(persistent_traits.get("body_plan")),
                    surface_covering=self._text(persistent_traits.get("surface_covering")),
                    coloration=self._text(persistent_traits.get("coloration")),
                    head_features=self._text(persistent_traits.get("head_features")),
                    eyes=self._text(persistent_traits.get("eyes")),
                    limbs_appendages=self._text(persistent_traits.get("limbs_appendages")),
                    natural_weapons=self._text(persistent_traits.get("natural_weapons")),
                    wings=self._text(persistent_traits.get("wings")),
                    tail=self._text(persistent_traits.get("tail")),
                    magical_features=self._text(persistent_traits.get("magical_features")),
                    world_genre_cues=self._text(persistent_traits.get("world_genre_cues")),
                    evidence_excerpt=evidence_excerpt,
                    source_scene_json=source_scene_json if isinstance(source_scene_json, (dict, list)) else None,
                ))
            elif entity_type == "object":
                session.add(ObjectVisualBaseline(
                    book_id=book_id,
                    entity_id=entity.id,
                    object_class=self._text(persistent_traits.get("object_class")),
                    function=self._text(persistent_traits.get("function")),
                    size_scale=self._text(persistent_traits.get("size_scale")),
                    shape_form=self._text(persistent_traits.get("shape_form")),
                    primary_material=self._text(persistent_traits.get("primary_material")),
                    secondary_materials=self._text(persistent_traits.get("secondary_materials")),
                    color_finish=self._text(persistent_traits.get("color_finish")),
                    surface_texture=self._text(persistent_traits.get("surface_texture")),
                    condition_default=self._text(persistent_traits.get("condition_default")),
                    symbolic_markings=self._text(persistent_traits.get("symbolic_markings")),
                    magical_properties=self._text(persistent_traits.get("magical_properties")),
                    world_genre_cues=self._text(persistent_traits.get("world_genre_cues")),
                    evidence_excerpt=evidence_excerpt,
                    source_scene_json=source_scene_json if isinstance(source_scene_json, (dict, list)) else None,
                ))
                for row in entity.metadata_json.get("scene_visual_states", []) if isinstance(entity.metadata_json, dict) else []:
                    state = row.get("state") or {}
                    scene = scene_map.get((self._int_or_none(row.get("chapter_index")), self._int_or_none(row.get("scene_index"))))
                    session.add(ObjectSceneState(
                        book_id=book_id,
                        entity_id=entity.id,
                        scene_id=scene.id if scene else None,
                        chapter_index=self._int_or_none(row.get("chapter_index")),
                        scene_index=self._int_or_none(row.get("scene_index")),
                        owner_or_holder=self._text(state.get("owner_or_holder")),
                        activation_state=self._text(state.get("activation_state")),
                        damage_state=self._text(state.get("damage_state")),
                        location_context=self._text(state.get("location_context")),
                        contained_contents=self._text(state.get("contained_contents")),
                        temporary_effects=self._text(state.get("temporary_effects")),
                        source_scene_json=row,
                    ))
            elif entity_type == "location":
                session.add(LocationVisualBaseline(
                    book_id=book_id,
                    entity_id=entity.id,
                    location_class=self._text(persistent_traits.get("location_class")),
                    indoor_outdoor=self._text(persistent_traits.get("indoor_outdoor")),
                    environment_type=self._text(persistent_traits.get("environment_type")),
                    region_or_domain=self._text(persistent_traits.get("region_or_domain")),
                    architecture_or_terrain_style=self._text(persistent_traits.get("architecture_or_terrain_style")),
                    dominant_materials=self._text(persistent_traits.get("dominant_materials")),
                    lighting_default=self._text(persistent_traits.get("lighting_default")),
                    weather_exposure=self._text(persistent_traits.get("weather_exposure")),
                    ambient_mood=self._text(persistent_traits.get("ambient_mood")),
                    notable_features=self._text(persistent_traits.get("notable_features")),
                    magic_or_tech_presence=self._text(persistent_traits.get("magic_or_tech_presence")),
                    world_genre_cues=self._text(persistent_traits.get("world_genre_cues")),
                    evidence_excerpt=evidence_excerpt,
                    source_scene_json=source_scene_json if isinstance(source_scene_json, (dict, list)) else None,
                ))
                for row in entity.metadata_json.get("scene_visual_states", []) if isinstance(entity.metadata_json, dict) else []:
                    state = row.get("state") or {}
                    scene = scene_map.get((self._int_or_none(row.get("chapter_index")), self._int_or_none(row.get("scene_index"))))
                    session.add(LocationSceneState(
                        book_id=book_id,
                        entity_id=entity.id,
                        scene_id=scene.id if scene else None,
                        chapter_index=self._int_or_none(row.get("chapter_index")),
                        scene_index=self._int_or_none(row.get("scene_index")),
                        lighting_current=self._text(state.get("lighting_current")),
                        weather_current=self._text(state.get("weather_current")),
                        occupancy_state=self._text(state.get("occupancy_state")),
                        damage_state=self._text(state.get("damage_state")),
                        temporary_setup=self._text(state.get("temporary_setup")),
                        atmosphere_shift=self._text(state.get("atmosphere_shift")),
                        active_effects=self._text(state.get("active_effects")),
                        source_scene_json=row,
                    ))

    def _persist_stable_states(self, session: Session, book_id: str, states: list[dict[str, Any]], entity_map: dict[tuple[str, str], Entity]) -> None:
        for row in states:
            if not isinstance(row, dict):
                continue
            name = str(row.get("character_name") or row.get("name") or "").strip()
            if not name:
                continue
            entity = entity_map.get((name.lower(), "character"))
            session.add(StableCharacterState(
                book_id=book_id,
                entity_id=entity.id if entity else None,
                character_name=name,
                payload_json=row,
            ))

    def _persist_events(self, session: Session, book_id: str, events: list[dict[str, Any]], scene_map: dict[tuple[int, int], Scene]) -> dict[str, Event]:
        event_map: dict[str, Event] = {}
        for idx, row in enumerate(events, start=1):
            if not isinstance(row, dict):
                continue
            chapter_index = self._int_or_none(row.get("chapter_index"))
            scene_index = self._int_or_none(row.get("scene_index"))
            scene = scene_map.get((chapter_index, scene_index)) if chapter_index is not None and scene_index is not None else None
            external_id = str(row.get("event_id") or f"event_{idx}").strip()
            event = Event(
                book_id=book_id,
                scene_id=scene.id if scene else None,
                chapter_index=chapter_index,
                scene_index=scene_index,
                event_id_external=external_id,
                event_type=str(row.get("event_type") or row.get("type") or "").strip() or None,
                description=str(row.get("description") or row.get("event") or "").strip() or None,
                reason=str(row.get("reason") or row.get("cause") or "").strip() or None,
                outcome=str(row.get("outcome") or "").strip() or None,
                entities_involved=row.get("entities_involved") if isinstance(row.get("entities_involved"), (list, dict)) else None,
                payload_json=row,
            )
            session.add(event)
            session.flush()
            event_map[external_id] = event
        return event_map

    def _persist_timeline(self, session: Session, book_id: str, rows: list[dict[str, Any]], event_map: dict[str, Event]) -> None:
        for idx, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                continue
            external_id = str(row.get("event_id") or "").strip()
            event = event_map.get(external_id)
            session.add(TimelineRow(
                book_id=book_id,
                event_id=event.id if event else None,
                row_index=idx,
                payload_json=row,
            ))

    def _persist_visual_prompts(self, session: Session, book_id: str, prompt_sets: dict[str, Any], entity_map: dict[tuple[str, str], Entity]) -> None:
        if not isinstance(prompt_sets, dict):
            return
        for bucket, rows in prompt_sets.items():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                entity_name = str(row.get("entity_name") or "").strip()
                entity_type = str(row.get("entity_type") or "").strip().lower()
                entity = entity_map.get((entity_name.lower(), entity_type)) if entity_name and entity_type else None
                session.add(VisualPrompt(
                    book_id=book_id,
                    entity_id=entity.id if entity else None,
                    entity_name=entity_name or None,
                    entity_type=entity_type or None,
                    prompt_type=str(row.get("prompt_type") or "").strip() or None,
                    visual_bucket=str(bucket).strip() or None,
                    positive_prompt=str(row.get("positive_prompt") or "").strip() or None,
                    negative_prompt=str(row.get("negative_prompt") or "").strip() or None,
                    source_evidence=str(row.get("source_evidence") or "").strip() or None,
                    confidence=str(row.get("confidence") or "").strip() or None,
                    book_index=self._int_or_none(row.get("book_index")),
                    chapter_index=self._int_or_none(row.get("chapter_index")),
                    scene_index=self._int_or_none(row.get("scene_index")),
                    details_json=row.get("details") if isinstance(row.get("details"), (dict, list)) else None,
                    metadata_json=row,
                ))
                if entity and str(row.get("positive_prompt") or "").strip():
                    entity.baseline_visual_prompt = str(row.get("positive_prompt") or "").strip()

    def _find_book_by_contract_path(self, session: Session, contract_path: str) -> Book | None:
        if str(contract_path).startswith("db://book/"):
            book_id = str(contract_path).split("db://book/", 1)[-1].strip()
            return session.get(Book, book_id) if book_id else None
        normalized = str(Path(contract_path).resolve())
        books = session.execute(select(Book)).scalars().all()
        for book in books:
            if not book.contract_path:
                continue
            try:
                if str(Path(book.contract_path).resolve()) == normalized:
                    return book
            except OSError:
                if book.contract_path == contract_path:
                    return book
        return None

    def _entity_map(self, session: Session, book_id: str) -> dict[tuple[str, str], Entity]:
        rows = session.execute(select(Entity).where(Entity.book_id == book_id)).scalars().all()
        return {(row.canonical_name.lower(), row.entity_type.lower()): row for row in rows}

    def _prompt_map(self, session: Session, book_id: str) -> dict[tuple[str, str, str], VisualPrompt]:
        rows = session.execute(select(VisualPrompt).where(VisualPrompt.book_id == book_id)).scalars().all()
        return {
            (
                str(row.entity_name or "").lower(),
                str(row.entity_type or "").lower(),
                str(row.prompt_type or "").lower(),
            ): row
            for row in rows
        }

    def _word_count(self, text: Any) -> int | None:
        value = str(text or "").strip()
        return len(value.split()) if value else None

    def _int_or_none(self, value: Any) -> int | None:
        try:
            return None if value in (None, "") else int(value)
        except (TypeError, ValueError):
            return None

    def _float_or_none(self, value: Any) -> float | None:
        try:
            return None if value in (None, "") else float(value)
        except (TypeError, ValueError):
            return None

    def _bool_or_none(self, value: Any) -> bool | None:
        if value in (None, ""):
            return None
        return bool(value)

    def _text(self, value: Any) -> str | None:
        cleaned = str(value or "").strip()
        return cleaned or None
