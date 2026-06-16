from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import logging
import re
import time
from typing import Any

from sqlalchemy import select

from core.trait_taxonomy import practical_persistent_fields
from infrastructure.llm_client import LLMClient
from sql_store.models import (
    Book,
    CreatureVisualBaseline,
    Entity,
    Event,
    LocationVisualBaseline,
    ObjectVisualBaseline,
    Scene,
)
from sql_store.persistence import SagaSQLiteStore
from sql_store.semantic_retrieval import SQLiteSemanticRetrievalService

from analysis.db_character_profile_agent import UNKNOWN_LIST_ITEM, UNKNOWN_TEXT


LOGGER = logging.getLogger(__name__)


class DatabaseNonCharacterVisualBaselineAgent:
    VERSION = "db_noncharacter_visual_baseline_agent_v2_parallel"
    CONFIDENCE_VALUES = {"high", "medium", "low"}
    SUPPORTED_ENTITY_TYPES = {"creature", "object", "location"}
    MAX_SCENES_PER_ENTITY = 12
    MAX_EVENTS_PER_ENTITY = 12
    MAX_SCENE_CHARS = 1000

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        sqlite_store: SagaSQLiteStore | None = None,
        semantic_retrieval: SQLiteSemanticRetrievalService | None = None,
        max_attempts: int = 3,
        retry_delay_seconds: float = 1.5,
        max_entity_workers: int = 4,
    ) -> None:
        self.sqlite_store = sqlite_store or SagaSQLiteStore()
        self.llm = llm_client or LLMClient(
            mode=LLMClient.MODE_GPT_OSS,
            allow_account_rotation=True,
            allow_cross_provider_fallback=False,
        )
        self.semantic_retrieval = semantic_retrieval or SQLiteSemanticRetrievalService(sqlite_store=self.sqlite_store)
        self.max_attempts = max(1, int(max_attempts))
        self.retry_delay_seconds = max(0.0, float(retry_delay_seconds))
        self.max_entity_workers = max(1, int(max_entity_workers))

    def analyze_book(
        self,
        *,
        book_ref: str,
        entity_types: list[str] | None = None,
        entity_names: list[str] | None = None,
        limit_entities: int | None = None,
    ) -> dict[str, Any]:
        book_id = self._resolve_book_id(book_ref)
        requested_types = {
            str(value).strip().lower()
            for value in (entity_types or self.SUPPORTED_ENTITY_TYPES)
            if str(value).strip().lower() in self.SUPPORTED_ENTITY_TYPES
        }
        requested_names = {
            str(value).strip().lower()
            for value in (entity_names or [])
            if str(value).strip()
        }
        roster = self._load_entity_roster(
            book_id=book_id,
            requested_types=requested_types,
            requested_names=requested_names,
        )
        if limit_entities is not None:
            roster = roster[: max(0, int(limit_entities))]
        LOGGER.info(
            "DB non-character visual baseline agent start | book=%s roster=%s types=%s",
            book_id,
            len(roster),
            sorted(requested_types),
        )
        self.semantic_retrieval.ensure_book_index(book_id=book_id, source_types=("scene", "event"))
        results: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=self.max_entity_workers) as executor:
            future_map = {
                executor.submit(self._process_entity, book_id=book_id, roster_row=row): row
                for row in roster
            }
            for future in as_completed(future_map):
                outcome = future.result()
                if outcome.get("skipped"):
                    skipped.append(outcome["skipped"])
                    continue
                results.append(outcome["result"])
        LOGGER.info(
            "DB non-character visual baseline agent complete | book=%s persisted=%s skipped=%s",
            book_id,
            len(results),
            len(skipped),
        )
        return {
            "book_id": book_id,
            "persisted_visual_baselines": len(results),
            "results": results,
            "skipped": skipped,
            "agent_version": self.VERSION,
        }

    def _process_entity(self, *, book_id: str, roster_row: dict[str, Any]) -> dict[str, Any]:
        bundle = self._build_entity_bundle(book_id=book_id, roster_row=roster_row)
        if not bundle["scenes"] and not bundle["events"] and not bundle["entity_context"]:
            return {
                "skipped": {
                    "entity_name": bundle["entity_name"],
                    "entity_type": bundle["entity_type"],
                    "reason": "no_evidence",
                }
            }
        visual_profile = self._extract_visual_baseline(bundle=bundle)
        self._persist_visual_baseline(bundle=bundle, visual_profile=visual_profile)
        return {
            "result": {
                "entity_name": bundle["entity_name"],
                "entity_type": bundle["entity_type"],
                "confidence": visual_profile.get("confidence", ""),
                "scene_count": len(bundle["scenes"]),
                "event_count": len(bundle["events"]),
            }
        }

    def _resolve_book_id(self, book_ref: str) -> str:
        value = str(book_ref or "").strip()
        if value.startswith("db://book/"):
            return value.split("db://book/", 1)[-1].strip()
        return value

    def _load_entity_roster(
        self,
        *,
        book_id: str,
        requested_types: set[str],
        requested_names: set[str],
    ) -> list[dict[str, Any]]:
        with self.sqlite_store.session_factory() as session:
            rows = session.execute(
                select(Entity)
                .where(Entity.book_id == book_id, Entity.entity_type.in_(sorted(requested_types)))
                .order_by(Entity.entity_type.asc(), Entity.mention_count.desc(), Entity.canonical_name.asc())
            ).scalars().all()
            roster: list[dict[str, Any]] = []
            for row in rows:
                canonical_name = str(row.canonical_name or "").strip()
                entity_type = str(row.entity_type or "").strip().lower()
                if not canonical_name or entity_type not in requested_types:
                    continue
                if requested_names and canonical_name.lower() not in requested_names:
                    continue
                metadata = dict(row.metadata_json or {})
                roster.append(
                    {
                        "entity_id": row.id,
                        "entity_name": canonical_name,
                        "entity_type": entity_type,
                        "aliases": [str(item).strip() for item in metadata.get("aliases") or [] if str(item).strip()],
                        "entity_context": str(row.entity_context or "").strip(),
                        "typed_attributes": dict(row.typed_attributes or {}) if isinstance(row.typed_attributes, dict) else {},
                    }
                )
            return roster

    def _build_entity_bundle(self, *, book_id: str, roster_row: dict[str, Any]) -> dict[str, Any]:
        with self.sqlite_store.session_factory() as session:
            book = session.get(Book, book_id)
            entity_name = str(roster_row.get("entity_name") or "").strip()
            aliases = [entity_name, *[str(item).strip() for item in roster_row.get("aliases") or [] if str(item).strip()]]
            alias_keys = {self._normalize_text(item) for item in aliases if self._normalize_text(item)}
            scenes: list[dict[str, Any]] = []
            for scene in session.execute(
                select(Scene).where(Scene.book_id == book_id).order_by(Scene.chapter_index.asc(), Scene.scene_index.asc())
            ).scalars():
                excerpt = self._excerpt_for_aliases(str(scene.text or ""), aliases)
                if excerpt:
                    scenes.append(
                        {
                            "scene_id": scene.id,
                            "chapter_index": scene.chapter_index,
                            "scene_index": scene.scene_index,
                            "summary": str(scene.summary or "").strip(),
                            "location_name": str(scene.location_name or "").strip(),
                            "excerpt": excerpt,
                        }
                    )
                if len(scenes) >= self.MAX_SCENES_PER_ENTITY:
                    break
            events: list[dict[str, Any]] = []
            for event in session.execute(
                select(Event).where(Event.book_id == book_id).order_by(Event.chapter_index.asc(), Event.scene_index.asc(), Event.created_at.asc())
            ).scalars():
                payload = dict(event.payload_json or {})
                raw_names = [
                    *[str(item).strip() for item in (event.entities_involved or []) if str(item).strip()],
                    *[str(item).strip() for item in payload.get("objects_involved") or [] if str(item).strip()],
                    *[str(item).strip() for item in payload.get("creatures_involved") or [] if str(item).strip()],
                    str(payload.get("location_name") or "").strip(),
                ]
                raw_keys = {self._normalize_text(item) for item in raw_names if self._normalize_text(item)}
                if not alias_keys & raw_keys:
                    description = " ".join(
                        piece
                        for piece in [
                            str(event.description or "").strip(),
                            str(event.reason or "").strip(),
                            str(event.outcome or "").strip(),
                        ]
                        if piece
                    )
                    if not self._contains_alias(description, aliases):
                        continue
                events.append(
                    {
                        "chapter_index": event.chapter_index,
                        "scene_index": event.scene_index,
                        "event_type": event.event_type,
                        "description": str(event.description or "").strip(),
                        "reason": str(event.reason or "").strip(),
                        "outcome": str(event.outcome or "").strip(),
                    }
                )
                if len(events) >= self.MAX_EVENTS_PER_ENTITY:
                    break
            return {
                "book_id": book_id,
                "series_id": str(book.series_id or "").strip() if book else "",
                "book_title": str(book.title or "").strip() if book else "",
                "entity_id": str(roster_row.get("entity_id") or "").strip() or None,
                "entity_name": entity_name,
                "entity_type": str(roster_row.get("entity_type") or "").strip().lower(),
                "aliases": [alias for alias in aliases if alias],
                "entity_context": str(roster_row.get("entity_context") or "").strip(),
                "typed_attributes": dict(roster_row.get("typed_attributes") or {}),
                "scenes": scenes,
                "events": events,
            }

    def _extract_visual_baseline(self, *, bundle: dict[str, Any]) -> dict[str, Any]:
        bundle["retrieved_evidence"] = self._retrieve_semantic_evidence(bundle=bundle)
        prompt = self._build_prompt(bundle=bundle)
        response = self._run_llm_with_retries(
            prompt=prompt,
            entity_name=bundle["entity_name"],
            entity_type=bundle["entity_type"],
        )
        return self._normalize_response(bundle=bundle, response=response)

    def _build_prompt(self, *, bundle: dict[str, Any]) -> str:
        fields = practical_persistent_fields(bundle["entity_type"])
        schema = {field: UNKNOWN_TEXT for field in fields}
        return f"""
You are the non-character visual baseline extraction agent for a canon database.
Return only grounded JSON for one {bundle["entity_type"]} using whole-book evidence.

Mission:
- Extract durable visual/world description only.
- Focus on physical or visual identity that can later support image generation.
- Stay grounded in the book text.

Hard rules:
- Use exactly `{UNKNOWN_TEXT}` for unsupported fields.
- Never leave any field blank.
- Do not invent colors, materials, powers, scale, atmosphere, or magical properties.
- `evidence_excerpt` must not be blank.
- For locations, capture indoor/outdoor, environment, architecture/terrain, mood, notable features, and magic/tech presence only when supported.
- For objects, capture material, shape, condition, markings, function, and magical properties only when supported.
- For creatures, capture body plan, covering, coloration, anatomy, natural weapons, and magical features only when supported.

Return JSON only:
{{
  "entity_name": "{bundle["entity_name"]}",
  "entity_type": "{bundle["entity_type"]}",
  "visual_baseline": {json.dumps(schema, ensure_ascii=False)},
  "evidence_excerpt": "{UNKNOWN_TEXT}",
  "confidence": "high|medium|low"
}}

Book:
{bundle["book_title"]}

Entity:
{bundle["entity_name"]}

Aliases:
{json.dumps(bundle["aliases"], ensure_ascii=False)}

Existing entity context:
{bundle["entity_context"] or UNKNOWN_TEXT}

Existing typed attributes:
{json.dumps(bundle["typed_attributes"], ensure_ascii=False)}

Semantic retrieved evidence:
{json.dumps(bundle.get("retrieved_evidence") or [], ensure_ascii=False)}

Scene evidence:
{json.dumps(bundle["scenes"], ensure_ascii=False)}

Event evidence:
{json.dumps(bundle["events"], ensure_ascii=False)}
"""

    def _run_llm_with_retries(self, *, prompt: str, entity_name: str, entity_type: str) -> dict[str, Any]:
        last_error = ""
        for attempt in range(1, self.max_attempts + 1):
            LOGGER.info(
                "DB non-character visual baseline agent LLM attempt start | entity=%s type=%s attempt=%s/%s",
                entity_name,
                entity_type,
                attempt,
                self.max_attempts,
            )
            response = self.llm.generate_json(prompt, strict=True, validator=self._validate_response)
            if isinstance(response, dict) and "error" not in response:
                LOGGER.info(
                    "DB non-character visual baseline agent LLM attempt complete | entity=%s type=%s attempt=%s/%s",
                    entity_name,
                    entity_type,
                    attempt,
                    self.max_attempts,
                )
                return response
            last_error = str((response or {}).get("error") or "unknown_error")
            LOGGER.warning(
                "DB non-character visual baseline agent LLM attempt failed | entity=%s type=%s attempt=%s/%s error=%s",
                entity_name,
                entity_type,
                attempt,
                self.max_attempts,
                last_error,
            )
            if attempt < self.max_attempts and self.retry_delay_seconds > 0:
                time.sleep(self.retry_delay_seconds)
        raise RuntimeError(
            f"DB non-character visual baseline agent failed after {self.max_attempts} attempts for {entity_type} {entity_name}: {last_error}"
        )

    def _validate_response(self, response: dict[str, Any]) -> bool:
        if not isinstance(response, dict):
            return False
        baseline = response.get("visual_baseline") or {}
        if not isinstance(baseline, dict):
            return False
        confidence = str(response.get("confidence") or "").strip().lower()
        return confidence in self.CONFIDENCE_VALUES

    def _normalize_response(self, *, bundle: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
        fields = practical_persistent_fields(bundle["entity_type"])
        baseline = {
            field: self._fallback_text((response.get("visual_baseline") or {}).get(field))
            for field in fields
        }
        return {
            "entity_name": bundle["entity_name"],
            "entity_type": bundle["entity_type"],
            "visual_baseline": baseline,
            "evidence_excerpt": self._fallback_text(
                response.get("evidence_excerpt"),
                fallback=self._fallback_evidence_excerpt(bundle),
            ),
            "confidence": self._clean(response.get("confidence")).lower() or "low",
            "agent_version": self.VERSION,
        }

    def _retrieve_semantic_evidence(self, *, bundle: dict[str, Any]) -> list[dict[str, Any]]:
        field_names = practical_persistent_fields(bundle["entity_type"])
        query_text = " ".join(
            item
            for item in [
                bundle["entity_name"],
                " / ".join(bundle["aliases"][:4]),
                f"persistent visual traits for {bundle['entity_type']}",
                "fields: " + ", ".join(field_names),
            ]
            if item
        )
        rows = self.semantic_retrieval.query(
            book_id=bundle["book_id"],
            query_text=query_text,
            top_k=8,
            source_types=("scene", "event"),
            entity_bias=bundle["aliases"],
        )
        if rows:
            LOGGER.info(
                "DB non-character visual baseline semantic retrieval | entity=%s type=%s hits=%s",
                bundle["entity_name"],
                bundle["entity_type"],
                len(rows),
            )
        return [
            {
                "source_type": str(row.get("source_type") or "").strip(),
                "source_id": row.get("source_id"),
                "chapter_index": row.get("chapter_index"),
                "scene_index": row.get("scene_index"),
                "summary": str(row.get("summary") or "").strip(),
                "excerpt": self._clean(row.get("excerpt")),
                "score": row.get("score"),
                "metadata": row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
            }
            for row in rows
        ]

    def _persist_visual_baseline(self, *, bundle: dict[str, Any], visual_profile: dict[str, Any]) -> None:
        with self.sqlite_store.session_factory() as session:
            entity = session.get(Entity, bundle["entity_id"]) if bundle.get("entity_id") else None
            values = {
                **visual_profile["visual_baseline"],
                "evidence_excerpt": visual_profile["evidence_excerpt"],
                "source_scene_json": bundle["scenes"][:8],
            }
            entity_type = bundle["entity_type"]
            if entity_type == "creature" and bundle.get("entity_id"):
                row = session.execute(
                    select(CreatureVisualBaseline).where(
                        CreatureVisualBaseline.book_id == bundle["book_id"],
                        CreatureVisualBaseline.entity_id == bundle["entity_id"],
                    )
                ).scalar_one_or_none()
                self._upsert_baseline_row(session=session, row=row, model=CreatureVisualBaseline, values=values, bundle=bundle)
            elif entity_type == "object" and bundle.get("entity_id"):
                row = session.execute(
                    select(ObjectVisualBaseline).where(
                        ObjectVisualBaseline.book_id == bundle["book_id"],
                        ObjectVisualBaseline.entity_id == bundle["entity_id"],
                    )
                ).scalar_one_or_none()
                self._upsert_baseline_row(session=session, row=row, model=ObjectVisualBaseline, values=values, bundle=bundle)
            elif entity_type == "location" and bundle.get("entity_id"):
                row = session.execute(
                    select(LocationVisualBaseline).where(
                        LocationVisualBaseline.book_id == bundle["book_id"],
                        LocationVisualBaseline.entity_id == bundle["entity_id"],
                    )
                ).scalar_one_or_none()
                self._upsert_baseline_row(session=session, row=row, model=LocationVisualBaseline, values=values, bundle=bundle)

            if entity is not None:
                entity.initial_physical_description = {
                    "baseline_visual_fields": dict(visual_profile["visual_baseline"]),
                    "evidence_excerpt": visual_profile["evidence_excerpt"],
                }
                entity.first_appearance_profile = {
                    "persistent_traits": dict(visual_profile["visual_baseline"]),
                    "confidence": visual_profile["confidence"],
                    "agent_version": self.VERSION,
                }
                metadata = dict(entity.metadata_json or {})
                metadata["noncharacter_visual_baseline_agent"] = {
                    "source": self.VERSION,
                    "evidence_scene_count": len(bundle["scenes"]),
                    "evidence_event_count": len(bundle["events"]),
                }
                entity.metadata_json = metadata
            session.commit()

    def _upsert_baseline_row(self, *, session, row, model, values: dict[str, Any], bundle: dict[str, Any]) -> None:
        if row is None:
            session.add(
                model(
                    book_id=bundle["book_id"],
                    entity_id=bundle["entity_id"],
                    **values,
                )
            )
            return
        for key, value in values.items():
            setattr(row, key, value)

    def _fallback_evidence_excerpt(self, bundle: dict[str, Any]) -> str:
        for row in bundle["scenes"]:
            excerpt = self._clean(row.get("excerpt"))
            if excerpt:
                return excerpt
        for row in bundle["events"]:
            description = self._clean(row.get("description"))
            if description:
                return description
        return self._fallback_text(bundle.get("entity_context"))

    def _contains_alias(self, text: str, aliases: list[str]) -> bool:
        normalized_text = self._normalize_text(text)
        for alias in aliases:
            alias_key = self._normalize_text(alias)
            if alias_key and alias_key in normalized_text:
                return True
        return False

    def _excerpt_for_aliases(self, text: str, aliases: list[str]) -> str:
        source = str(text or "").strip()
        if not source:
            return ""
        normalized_source = source.lower()
        best_start = -1
        best_len = 0
        for alias in aliases:
            alias_value = str(alias or "").strip()
            if not alias_value:
                continue
            found = normalized_source.find(alias_value.lower())
            if found >= 0 and (best_start < 0 or found < best_start):
                best_start = found
                best_len = len(alias_value)
        if best_start < 0:
            return ""
        start = max(0, best_start - 240)
        end = min(len(source), best_start + best_len + 520)
        excerpt = source[start:end].strip()
        if len(excerpt) > self.MAX_SCENE_CHARS:
            excerpt = excerpt[: self.MAX_SCENE_CHARS].rstrip() + "..."
        return excerpt

    def _clean(self, value: Any) -> str:
        return " ".join(str(value or "").strip().split())

    def _fallback_text(self, value: Any, *, fallback: str = UNKNOWN_TEXT) -> str:
        cleaned = self._clean(value)
        return cleaned or fallback

    def _normalize_text(self, value: str) -> str:
        cleaned = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
        return " ".join(cleaned.split())
