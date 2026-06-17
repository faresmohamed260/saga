from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select

from saga.identity.identity_provider import resolve_identity_provider_input
from saga.storage.models import (
    Book as SqlBook,
    Chapter as SqlChapter,
    CharacterProfile as SqlCharacterProfile,
    Entity as SqlEntity,
    Event as SqlEvent,
    GeneratedImage as SqlGeneratedImage,
    Scene as SqlScene,
    StableCharacterState as SqlStableCharacterState,
    TimelineRow as SqlTimelineRow,
    VisualPrompt as SqlVisualPrompt,
)
from saga.storage.persistence import SagaSQLiteStore


SQLITE_STORE = SagaSQLiteStore()


def is_db_book_ref(value: str | None) -> bool:
    return str(value or "").strip().startswith("db://book/")


def extract_book_id(value: str) -> str:
    return str(value).split("db://book/", 1)[-1].strip()


def load_contract_like(ref: str) -> dict[str, Any]:
    if not is_db_book_ref(ref):
        raise ValueError(f"Unsupported SQLite contract ref: {ref}")
    book_id = extract_book_id(ref)
    with SQLITE_STORE.session_factory() as session:
        book = session.get(SqlBook, book_id)
        if book is None:
            raise FileNotFoundError(f"Book not found in SQLite: {ref}")

        chapters = session.execute(
            select(SqlChapter).where(SqlChapter.book_id == book.id).order_by(SqlChapter.chapter_index.asc())
        ).scalars().all()
        scenes = session.execute(
            select(SqlScene).where(SqlScene.book_id == book.id).order_by(SqlScene.chapter_index.asc(), SqlScene.scene_index.asc())
        ).scalars().all()
        entities = session.execute(
            select(SqlEntity).where(SqlEntity.book_id == book.id).order_by(SqlEntity.entity_type.asc(), SqlEntity.canonical_name.asc())
        ).scalars().all()
        profiles = session.execute(
            select(SqlCharacterProfile).where(SqlCharacterProfile.book_id == book.id).order_by(SqlCharacterProfile.character_name.asc())
        ).scalars().all()
        stable_states = session.execute(
            select(SqlStableCharacterState).where(SqlStableCharacterState.book_id == book.id).order_by(SqlStableCharacterState.character_name.asc())
        ).scalars().all()
        events = session.execute(
            select(SqlEvent).where(SqlEvent.book_id == book.id).order_by(SqlEvent.chapter_index.asc(), SqlEvent.scene_index.asc(), SqlEvent.created_at.asc())
        ).scalars().all()
        timeline_rows = session.execute(
            select(SqlTimelineRow).where(SqlTimelineRow.book_id == book.id).order_by(SqlTimelineRow.row_index.asc(), SqlTimelineRow.created_at.asc())
        ).scalars().all()
        prompt_rows = session.execute(
            select(SqlVisualPrompt).where(SqlVisualPrompt.book_id == book.id).order_by(SqlVisualPrompt.entity_type.asc(), SqlVisualPrompt.entity_name.asc())
        ).scalars().all()
        image_rows = session.execute(
            select(SqlGeneratedImage).where(SqlGeneratedImage.book_id == book.id).order_by(SqlGeneratedImage.entity_type.asc(), SqlGeneratedImage.entity_name.asc())
        ).scalars().all()

        metadata = dict((book.metadata_json or {}).get("metadata") or {})
        configuration = dict((book.metadata_json or {}).get("configuration") or {})
        primary_book = dict((book.metadata_json or {}).get("inputs") or {})
        inputs = {
            "series": {
                "series_id": book.series_id or "",
                "series_title": str((book.metadata_json or {}).get("series_title") or metadata.get("series_title") or ""),
            },
            "books": [
                {
                    "book_index": book.book_index,
                    "title": book.title,
                    "path": book.source_path or "",
                    "type": book.source_type or "",
                    **primary_book,
                }
            ],
        }

        prompt_sets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in prompt_rows:
            payload = dict(row.metadata_json or {})
            if not payload:
                payload = {
                    "entity_name": row.entity_name or "",
                    "entity_type": row.entity_type or "",
                    "prompt_type": row.prompt_type or "",
                    "positive_prompt": row.positive_prompt or "",
                    "negative_prompt": row.negative_prompt or "",
                    "source_evidence": row.source_evidence or "",
                    "confidence": row.confidence or "",
                    "book_index": row.book_index,
                    "chapter_index": row.chapter_index,
                    "scene_index": row.scene_index,
                    "details": row.details_json or {},
                }
            prompt_sets[str(row.visual_bucket or "ungrouped")].append(payload)

        generated_images = []
        for row in image_rows:
            generated_images.append(
                {
                    "entity_name": row.entity_name or "",
                    "entity_type": row.entity_type or "",
                    "output_path": row.output_path or "",
                    "mime_type": row.mime_type or "",
                    "render_status": row.render_status or "",
                    "workflow_name": row.workflow_name or "",
                    "manifest": row.manifest_json or {},
                    "has_image_bytes": bool(row.image_bytes),
                }
            )

        identity_result: dict[str, Any] = {"alias_map": {}, "decisions": [], "reference_entities": [], "narrator": {}}
        pipeline_identity: dict[str, Any] = {}
        if book.series_id and str(book.identity_provider or "").strip().lower() == "booknlp_clean":
            identity_ref = f"db://identity-series/{book.series_id}"
            try:
                provider = resolve_identity_provider_input(
                    provider_mode="booknlp_clean",
                    input_json=identity_ref,
                    book_inputs=inputs["books"],
                )
                try:
                    identity_result = provider.build_identity_result_compat(book_inputs=inputs["books"])
                    pipeline_identity = provider.build_pipeline_identity(book_inputs=inputs["books"])
                except TypeError:
                    identity_result = provider.build_identity_result_compat()
                    pipeline_identity = provider.build_pipeline_identity()
            except Exception:
                identity_result = {"alias_map": {}, "decisions": [], "reference_entities": [], "narrator": {}}
                pipeline_identity = {}

        outputs = {
            "chapters": [dict(row.metadata_json or {}) for row in chapters],
            "scene_analyses": [dict(row.payload_json or {}) for row in scenes],
            "resolved_scene_analyses": [dict(row.payload_json or {}) for row in scenes],
            "entity_registry": [dict(row.metadata_json or {}) for row in entities],
            "character_profiles": [dict(row.payload_json or {}) for row in profiles],
            "stable_character_states": [dict(row.payload_json or {}) for row in stable_states],
            "event_ledger": [dict(row.payload_json or {}) for row in events],
            "timeline": [dict(row.payload_json or {}) for row in timeline_rows],
            "visual_prompt_sets": dict(prompt_sets),
            "generated_images": generated_images,
            "identity_result": identity_result,
            "pipeline_identity": pipeline_identity,
            "causal_graph_result": {"graph": {"events": [], "critical_path": [], "flexible_events": [], "causal_chains": [], "divergence_points": []}},
            "state_result": {"transitions": [], "latest_state": []},
            "character_timelines": [],
        }
        return {
            "contract_version": "sqlite-adapter",
            "inputs": inputs,
            "outputs": outputs,
            "metadata": metadata,
            "configuration": configuration,
        }

