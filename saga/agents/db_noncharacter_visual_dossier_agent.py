from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import logging
import re
import time
from typing import Any

from sqlalchemy import select

from saga.domain.trait_taxonomy import TYPED_ATTRIBUTE_KEYS, practical_persistent_fields
from saga.providers.llm_client import LLMClient
from saga.storage.models import Book, Entity, Event, Scene
from saga.storage.persistence import SagaSQLiteStore
from saga.storage.semantic_retrieval import SQLiteSemanticRetrievalService

from saga.agents.db_character_profile_agent import UNKNOWN_LIST_ITEM, UNKNOWN_TEXT


LOGGER = logging.getLogger(__name__)


NONCHARACTER_TYPED_KEYS = {
    key: value
    for key, value in TYPED_ATTRIBUTE_KEYS.items()
    if key in {"creature", "object", "location"}
}


class DatabaseNonCharacterVisualDossierAgent:
    VERSION = "db_noncharacter_visual_dossier_agent_v1"
    CONFIDENCE_VALUES = {"high", "medium", "low"}
    SUPPORTED_ENTITY_TYPES = {"creature", "object", "location"}
    MAX_SCENES_PER_ENTITY = 12
    MAX_EVENTS_PER_ENTITY = 12
    MAX_SCENE_CHARS = 1100

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
            "DB non-character visual dossier agent start | book=%s roster=%s types=%s",
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
            "DB non-character visual dossier agent complete | book=%s persisted=%s skipped=%s",
            book_id,
            len(results),
            len(skipped),
        )
        return {
            "book_id": book_id,
            "persisted_dossiers": len(results),
            "results": sorted(results, key=lambda item: (str(item.get("entity_type") or ""), str(item.get("entity_name") or "").lower())),
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
        dossier = self._extract_dossier(bundle=bundle)
        self._persist_dossier(bundle=bundle, dossier=dossier)
        return {
            "result": {
                "entity_name": bundle["entity_name"],
                "entity_type": bundle["entity_type"],
                "confidence": dossier.get("confidence", ""),
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
                        "initial_physical_description": dict(row.initial_physical_description or {}) if isinstance(row.initial_physical_description, dict) else {},
                        "first_appearance_profile": dict(row.first_appearance_profile or {}) if isinstance(row.first_appearance_profile, dict) else {},
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
                    *[str(item).strip() for item in payload.get("locations_involved") or [] if str(item).strip()],
                    str(payload.get("event_location") or "").strip(),
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
                "book_title": str(book.title or "").strip() if book else "",
                "entity_id": str(roster_row.get("entity_id") or "").strip() or None,
                "entity_name": entity_name,
                "entity_type": str(roster_row.get("entity_type") or "").strip().lower(),
                "aliases": [alias for alias in aliases if alias],
                "entity_context": str(roster_row.get("entity_context") or "").strip(),
                "typed_attributes": dict(roster_row.get("typed_attributes") or {}),
                "initial_physical_description": dict(roster_row.get("initial_physical_description") or {}),
                "first_appearance_profile": dict(roster_row.get("first_appearance_profile") or {}),
                "scenes": scenes,
                "events": events,
            }

    def _extract_dossier(self, *, bundle: dict[str, Any]) -> dict[str, Any]:
        bundle["retrieved_evidence"] = self._retrieve_semantic_evidence(bundle=bundle)
        prompt = self._build_prompt(bundle=bundle)
        response = self._run_llm_with_retries(
            prompt=prompt,
            entity_name=bundle["entity_name"],
            entity_type=bundle["entity_type"],
        )
        return self._normalize_response(bundle=bundle, response=response)

    def _build_prompt(self, *, bundle: dict[str, Any]) -> str:
        typed_schema = {
            key: [UNKNOWN_LIST_ITEM]
            for key in NONCHARACTER_TYPED_KEYS.get(bundle["entity_type"], [])
        }
        field_schema = {field: UNKNOWN_TEXT for field in practical_persistent_fields(bundle["entity_type"])}
        return f"""
You are the non-character visual dossier agent for a canon database.
Return grounded JSON for one entity using whole-book evidence.

Mission:
- Build a richer descriptive visual dossier for prompt construction.
- Keep it grounded in the book text.
- Do not replace strict structured baseline facts with guesses.

Hard rules:
- `baseline_description` should be a compact but vivid prose description of the entity's stable visual saga.identity.
- `prompt_ready_description` should be a cleaner prompt-facing description using only grounded facts.
- `typed_attributes` should group supported details into the provided buckets.
- `persistent_traits` must fill every structured field with either a grounded value or `{UNKNOWN_TEXT}`.
- If a typed attribute bucket has no support, return `["{UNKNOWN_LIST_ITEM}"]`.
- Never leave fields blank.
- Do not invent materials, colors, magical properties, scale, atmosphere, or anatomy.
- Use existing structured context only as a weak hint, not as authority when unsupported by evidence.

Return JSON only:
{{
  "entity_name": "{bundle["entity_name"]}",
  "entity_type": "{bundle["entity_type"]}",
  "baseline_description": "{UNKNOWN_TEXT}",
  "prompt_ready_description": "{UNKNOWN_TEXT}",
  "typed_attributes": {json.dumps(typed_schema, ensure_ascii=False)},
  "persistent_traits": {json.dumps(field_schema, ensure_ascii=False)},
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

Existing initial physical description:
{json.dumps(bundle["initial_physical_description"], ensure_ascii=False)}

Existing first appearance profile:
{json.dumps(bundle["first_appearance_profile"], ensure_ascii=False)}

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
                "DB non-character visual dossier agent LLM attempt start | entity=%s type=%s attempt=%s/%s",
                entity_name,
                entity_type,
                attempt,
                self.max_attempts,
            )
            response = self.llm.generate_json(prompt, strict=True, validator=self._validate_response)
            if isinstance(response, dict) and "error" not in response:
                LOGGER.info(
                    "DB non-character visual dossier agent LLM attempt complete | entity=%s type=%s attempt=%s/%s",
                    entity_name,
                    entity_type,
                    attempt,
                    self.max_attempts,
                )
                return response
            last_error = str((response or {}).get("error") or "unknown_error")
            LOGGER.warning(
                "DB non-character visual dossier agent LLM attempt failed | entity=%s type=%s attempt=%s/%s error=%s",
                entity_name,
                entity_type,
                attempt,
                self.max_attempts,
                last_error,
            )
            if attempt < self.max_attempts and self.retry_delay_seconds > 0:
                time.sleep(self.retry_delay_seconds)
        raise RuntimeError(
            f"DB non-character visual dossier agent failed after {self.max_attempts} attempts for {entity_type} {entity_name}: {last_error}"
        )

    def _validate_response(self, response: dict[str, Any]) -> bool:
        if not isinstance(response, dict):
            return False
        if not isinstance(response.get("typed_attributes") or {}, dict):
            return False
        if not isinstance(response.get("persistent_traits") or {}, dict):
            return False
        confidence = str(response.get("confidence") or "").strip().lower()
        return confidence in self.CONFIDENCE_VALUES

    def _normalize_response(self, *, bundle: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
        typed_keys = NONCHARACTER_TYPED_KEYS.get(bundle["entity_type"], [])
        normalized_typed = {
            key: self._clean_list((response.get("typed_attributes") or {}).get(key) or [], fallback=UNKNOWN_LIST_ITEM)
            for key in typed_keys
        }
        normalized_traits = {
            field: self._fallback_text((response.get("persistent_traits") or {}).get(field))
            for field in practical_persistent_fields(bundle["entity_type"])
        }
        return {
            "entity_name": bundle["entity_name"],
            "entity_type": bundle["entity_type"],
            "baseline_description": self._fallback_text(response.get("baseline_description"), fallback=self._fallback_evidence_excerpt(bundle)),
            "prompt_ready_description": self._fallback_text(response.get("prompt_ready_description"), fallback=self._fallback_evidence_excerpt(bundle)),
            "typed_attributes": normalized_typed,
            "persistent_traits": normalized_traits,
            "evidence_excerpt": self._fallback_text(response.get("evidence_excerpt"), fallback=self._fallback_evidence_excerpt(bundle)),
            "confidence": self._clean(response.get("confidence")).lower() or "low",
            "agent_version": self.VERSION,
        }

    def _retrieve_semantic_evidence(self, *, bundle: dict[str, Any]) -> list[dict[str, Any]]:
        typed_keys = NONCHARACTER_TYPED_KEYS.get(bundle["entity_type"], [])
        query_text = " ".join(
            item
            for item in [
                bundle["entity_name"],
                " / ".join(bundle["aliases"][:4]),
                f"visual dossier for {bundle['entity_type']}",
                "typed groups: " + ", ".join(typed_keys),
                "persistent fields: " + ", ".join(practical_persistent_fields(bundle["entity_type"])),
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
                "DB non-character visual dossier semantic retrieval | entity=%s type=%s hits=%s",
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

    def _persist_dossier(self, *, bundle: dict[str, Any], dossier: dict[str, Any]) -> None:
        with self.sqlite_store.session_factory() as session:
            entity = session.get(Entity, bundle["entity_id"]) if bundle.get("entity_id") else None
            if entity is None:
                return
            existing_initial = dict(entity.initial_physical_description or {}) if isinstance(entity.initial_physical_description, dict) else {}
            existing_first = dict(entity.first_appearance_profile or {}) if isinstance(entity.first_appearance_profile, dict) else {}
            existing_typed = dict(entity.typed_attributes or {}) if isinstance(entity.typed_attributes, dict) else {}
            merged_typed = dict(existing_typed)
            for key, values in (dossier.get("typed_attributes") or {}).items():
                merged_typed[key] = self._merge_lists(existing_typed.get(key), values)
            entity.typed_attributes = merged_typed
            entity.initial_physical_description = {
                **existing_initial,
                "status": "captured",
                "description": dossier["baseline_description"],
                "description_type": "visual_dossier",
                "prompt_ready_description": dossier["prompt_ready_description"],
                "evidence_excerpt": dossier["evidence_excerpt"],
                "persistent_traits": dossier["persistent_traits"],
                "source": self.VERSION,
            }
            entity.first_appearance_profile = {
                **existing_first,
                "status": "captured",
                "baseline_description": dossier["baseline_description"],
                "prompt_ready_description": dossier["prompt_ready_description"],
                "typed_attributes": merged_typed,
                "persistent_traits": dossier["persistent_traits"],
                "confidence": dossier["confidence"],
                "agent_version": self.VERSION,
            }
            metadata = dict(entity.metadata_json or {})
            metadata["visual_dossier"] = {
                "baseline_description": dossier["baseline_description"],
                "prompt_ready_description": dossier["prompt_ready_description"],
                "typed_attributes": dossier["typed_attributes"],
                "persistent_traits": dossier["persistent_traits"],
                "evidence_excerpt": dossier["evidence_excerpt"],
                "confidence": dossier["confidence"],
                "source": self.VERSION,
            }
            entity.metadata_json = metadata
            session.commit()

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
        end = min(len(source), best_start + best_len + 560)
        excerpt = source[start:end].strip()
        if len(excerpt) > self.MAX_SCENE_CHARS:
            excerpt = excerpt[: self.MAX_SCENE_CHARS].rstrip() + "..."
        return excerpt

    def _clean(self, value: Any) -> str:
        return " ".join(str(value or "").strip().split())

    def _fallback_text(self, value: Any, *, fallback: str = UNKNOWN_TEXT) -> str:
        cleaned = self._clean(value)
        return cleaned or fallback

    def _clean_list(self, values: list[Any], *, fallback: str = UNKNOWN_LIST_ITEM) -> list[str]:
        rows: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = self._clean(value)
            lowered = cleaned.lower()
            if not cleaned or lowered in seen:
                continue
            seen.add(lowered)
            rows.append(cleaned)
        return rows or [fallback]

    def _merge_lists(self, left: Any, right: Any) -> list[str]:
        rows: list[str] = []
        seen: set[str] = set()
        for value in [*(left or []), *(right or [])]:
            cleaned = self._clean(value)
            lowered = cleaned.lower()
            if not cleaned or lowered == UNKNOWN_TEXT or lowered == UNKNOWN_LIST_ITEM:
                continue
            if lowered in seen:
                continue
            seen.add(lowered)
            rows.append(cleaned)
        return rows or [UNKNOWN_LIST_ITEM]

    def _normalize_text(self, value: str) -> str:
        cleaned = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
        return " ".join(cleaned.split())
