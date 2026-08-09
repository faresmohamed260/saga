from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from saga.domain.canon_normalization import CanonicalEntityNormalizer
from packages.reasoning_runtime.contracts import ReasoningClient
from saga.providers.reasoning_runtime_adapter import MODE_GENERAL_COMPUTE, MODE_GPT_OSS, create_runtime_client
from saga.storage.models import Book, Entity, Event, Scene
from saga.storage.persistence import SagaSQLiteStore


LOGGER = logging.getLogger(__name__)


@dataclass
class SceneEnrichmentBundle:
    book_id: str
    book_title: str
    scene_id: str
    chapter_index: int
    scene_index: int
    scene_text: str
    existing_summary: str
    existing_location_name: str
    existing_location_description: str
    events: list[dict[str, Any]]
    entity_roster: list[dict[str, Any]]


class DatabaseSceneEnrichmentAgent:
    VERSION = "db_scene_enrichment_agent_v1"
    VALID_ENTITY_TYPES = {"character", "creature", "object", "location", "organization", "other"}
    VALID_CHANGE_TYPES = {"physical_state", "status", "possession", "location", "condition", "relationship", "knowledge"}

    def __init__(
        self,
        *,
        llm_client: ReasoningClient | None = None,
        sqlite_store: SagaSQLiteStore | None = None,
        max_attempts: int = 3,
        retry_delay_seconds: float = 1.5,
    ) -> None:
        self.sqlite_store = sqlite_store or SagaSQLiteStore()
        self.llm = llm_client or create_runtime_client(mode=MODE_GPT_OSS, allow_account_rotation=True, allow_cross_provider_fallback=False)
        self.max_attempts = max(1, int(max_attempts))
        self.retry_delay_seconds = max(0.0, float(retry_delay_seconds))
        self.normalizer = CanonicalEntityNormalizer()

    def analyze_book(
        self,
        *,
        book_ref: str,
        chapter_limit: int | None = None,
        chapter_indices: list[int] | None = None,
    ) -> dict[str, Any]:
        book_id = self._resolve_book_id(book_ref)
        bundles = self._load_scene_bundles(book_id=book_id, chapter_limit=chapter_limit, chapter_indices=chapter_indices)
        LOGGER.info("DB scene enrichment agent start | book=%s scenes=%s", book_id, len(bundles))
        results: list[dict[str, Any]] = []
        for bundle in bundles:
            payload = self._run_scene(bundle)
            self._persist_scene(bundle=bundle, payload=payload)
            results.append(
                {
                    "scene_id": bundle.scene_id,
                    "chapter_index": bundle.chapter_index,
                    "scene_index": bundle.scene_index,
                    "scene_title": payload.get("scene_title") or "",
                    "entity_count": len(payload.get("entities_present") or []),
                    "state_change_count": len(payload.get("state_changes") or []),
                    "relationship_change_count": len(payload.get("relationship_changes") or []),
                }
            )
        LOGGER.info("DB scene enrichment agent complete | book=%s scenes=%s", book_id, len(results))
        return {
            "book_id": book_id,
            "processed_scenes": len(results),
            "results": results,
            "agent_version": self.VERSION,
        }

    def _resolve_book_id(self, book_ref: str) -> str:
        value = str(book_ref or "").strip()
        if value.startswith("db://book/"):
            return value.split("db://book/", 1)[-1].strip()
        return value

    def _load_scene_bundles(
        self,
        *,
        book_id: str,
        chapter_limit: int | None,
        chapter_indices: list[int] | None,
    ) -> list[SceneEnrichmentBundle]:
        selected_indices = {int(value) for value in (chapter_indices or [])}
        with self.sqlite_store.session_factory() as session:
            book = session.get(Book, book_id)
            if book is None:
                return []
            scene_rows = session.execute(
                select(Scene).where(Scene.book_id == book_id).order_by(Scene.chapter_index.asc(), Scene.scene_index.asc())
            ).scalars().all()
            entity_rows = session.execute(
                select(Entity).where(Entity.book_id == book_id).order_by(Entity.entity_type.asc(), Entity.canonical_name.asc())
            ).scalars().all()
            event_rows = session.execute(
                select(Event).where(Event.book_id == book_id).order_by(Event.chapter_index.asc(), Event.scene_index.asc(), Event.created_at.asc())
            ).scalars().all()
            event_map: dict[tuple[int, int], list[dict[str, Any]]] = {}
            for event in event_rows:
                key = (int(event.chapter_index or 0), int(event.scene_index or 0))
                event_map.setdefault(key, []).append(
                    {
                        "event_id": str(event.event_id_external or "").strip(),
                        "description": str(event.description or "").strip(),
                        "type": str(event.event_type or "").strip(),
                        "reason": str(event.reason or "").strip(),
                        "outcome": str(event.outcome or "").strip(),
                        "entities_involved": list(event.entities_involved or []),
                        "payload": dict(event.payload_json or {}) if isinstance(event.payload_json, dict) else {},
                    }
                )
            roster = [
                {
                    "name": str(row.canonical_name or "").strip(),
                    "entity_type": str(row.entity_type or "").strip().lower(),
                    "aliases": list((row.metadata_json or {}).get("aliases") or []),
                }
                for row in entity_rows
                if str(row.canonical_name or "").strip()
            ]
            bundles: list[SceneEnrichmentBundle] = []
            for row in scene_rows:
                chapter_index = int(row.chapter_index or 0)
                if chapter_limit is not None and chapter_index > int(chapter_limit):
                    continue
                if selected_indices and chapter_index not in selected_indices:
                    continue
                scene_index = int(row.scene_index or 0)
                bundles.append(
                    SceneEnrichmentBundle(
                        book_id=book_id,
                        book_title=str(book.title or "").strip(),
                        scene_id=row.id,
                        chapter_index=chapter_index,
                        scene_index=scene_index,
                        scene_text=str(row.text or "").strip(),
                        existing_summary=str(row.summary or "").strip(),
                        existing_location_name=str(row.location_name or "").strip(),
                        existing_location_description=str(row.location_description or "").strip(),
                        events=event_map.get((chapter_index, scene_index), []),
                        entity_roster=roster,
                    )
                )
            return bundles

    def _run_scene(self, bundle: SceneEnrichmentBundle) -> dict[str, Any]:
        prompt = self._build_prompt(bundle)
        response = self._run_llm_with_retries(bundle=bundle, prompt=prompt)
        return self._normalize_response(bundle=bundle, response=response)

    def _build_prompt(self, bundle: SceneEnrichmentBundle) -> str:
        compact_roster = [
            {
                "name": row["name"],
                "entity_type": row["entity_type"],
                "aliases": row["aliases"][:5],
            }
            for row in bundle.entity_roster[:300]
        ]
        return f"""
You are the scene enrichment agent for a canon analysis database.

Task:
- Analyze exactly one stored scene.
- Use the scene text and the pre-extracted events.
- Return a scene title, concise summary, entities present, location context, state changes, relationship changes, and scene world-state notes.

Hard rules:
- Stay strictly grounded in the supplied text and events.
- Do not leave required fields blank.
- Prefer canonical names from the roster when possible.
- `scene_title` should be short and descriptive.
- `scene_summary` should be 1-3 sentences.
- `entities_present` should include named entities materially present or directly active in the scene.
- `relationship_changes` should only include meaningful shifts, not simple co-presence.
- `state_changes` should only include states that become true in this scene.
- `location.name` should be the most grounded place name available.
- If no specific location description is available, keep `location.description` short and cautious.
- `entity_world_state.entities` should include only entities with a visible/world-state note worth preserving.
- Allowed entity types: character, creature, object, location, organization, other
- Allowed state change types: physical_state, status, possession, location, condition, relationship, knowledge

Return JSON only:
{{
  "scene_title": "",
  "scene_summary": "",
  "location": {{
    "name": "",
    "description": "",
    "atmosphere": ""
  }},
  "entities_present": [
    {{
      "name": "",
      "entity_type": "character",
      "role_in_scene": "",
      "evidence": ""
    }}
  ],
  "state_changes": [
    {{
      "entity_name": "",
      "entity_type": "character",
      "attribute": "",
      "previous_state": "",
      "new_state": "",
      "change_type": "condition",
      "evidence": ""
    }}
  ],
  "relationship_changes": [
    {{
      "source_entity": "",
      "target_entity": "",
      "relationship": "",
      "change": "",
      "evidence": ""
    }}
  ],
  "entity_world_state": {{
    "entities": [
      {{
        "entity_name": "",
        "entity_type": "object",
        "description": "",
        "current_state": "",
        "state_changes": []
      }}
    ],
    "diagnostics": {{}}
  }}
}}

Book:
{bundle.book_title}

Scene ref:
chapter={bundle.chapter_index}, scene={bundle.scene_index}

Existing summary:
{bundle.existing_summary or "n/a"}

Existing location:
{json.dumps({"name": bundle.existing_location_name, "description": bundle.existing_location_description}, ensure_ascii=False)}

Pre-extracted events:
{json.dumps(bundle.events, ensure_ascii=False)}

Entity roster:
{json.dumps(compact_roster, ensure_ascii=False)}

Scene text:
{bundle.scene_text}
"""

    def _run_llm_with_retries(self, *, bundle: SceneEnrichmentBundle, prompt: str) -> dict[str, Any]:
        last_error = ""
        for attempt in range(1, self.max_attempts + 1):
            LOGGER.info(
                "DB scene enrichment LLM attempt start | book=%s chapter=%s scene=%s attempt=%s/%s",
                bundle.book_id,
                bundle.chapter_index,
                bundle.scene_index,
                attempt,
                self.max_attempts,
            )
            response = self.llm.generate_json(prompt, strict=True, validator=self._validate_response)
            if isinstance(response, dict) and "error" not in response:
                LOGGER.info(
                    "DB scene enrichment LLM attempt complete | book=%s chapter=%s scene=%s attempt=%s/%s",
                    bundle.book_id,
                    bundle.chapter_index,
                    bundle.scene_index,
                    attempt,
                    self.max_attempts,
                )
                return response
            last_error = str((response or {}).get("error") or "unknown_error")
            LOGGER.warning(
                "DB scene enrichment LLM attempt failed | book=%s chapter=%s scene=%s attempt=%s/%s error=%s",
                bundle.book_id,
                bundle.chapter_index,
                bundle.scene_index,
                attempt,
                self.max_attempts,
                last_error,
            )
            if attempt < self.max_attempts and self.retry_delay_seconds > 0:
                time.sleep(self.retry_delay_seconds)
        raise RuntimeError(
            f"DB scene enrichment failed after {self.max_attempts} attempts for "
            f"book={bundle.book_id} chapter={bundle.chapter_index} scene={bundle.scene_index}: {last_error}"
        )

    def _validate_response(self, response: dict[str, Any]) -> bool:
        if not isinstance(response, dict):
            return False
        if not str(response.get("scene_title") or "").strip():
            return False
        if not str(response.get("scene_summary") or "").strip():
            return False
        if not isinstance(response.get("entities_present") or [], list):
            return False
        if not isinstance(response.get("state_changes") or [], list):
            return False
        if not isinstance(response.get("relationship_changes") or [], list):
            return False
        if not isinstance(response.get("entity_world_state") or {}, dict):
            return False
        return True

    def _normalize_response(self, *, bundle: SceneEnrichmentBundle, response: dict[str, Any]) -> dict[str, Any]:
        roster_context = self.normalizer.build_context(
            entity_registry=[{"name": row["name"], "entity_type": row["entity_type"]} for row in bundle.entity_roster],
            alias_map=self._alias_map_from_roster(bundle.entity_roster),
        )
        roster_by_key = {
            self.normalizer.normalized_entity_key(row["name"]): row
            for row in bundle.entity_roster
            if self.normalizer.normalized_entity_key(row["name"])
        }
        entities_present: list[dict[str, Any]] = []
        seen_entities: set[tuple[str, str]] = set()
        for row in response.get("entities_present") or []:
            if not isinstance(row, dict):
                continue
            name, entity_type = self._resolve_entity(
                str(row.get("name") or "").strip(),
                str(row.get("entity_type") or "").strip().lower(),
                roster_context=roster_context,
                roster_by_key=roster_by_key,
            )
            if not name or entity_type not in self.VALID_ENTITY_TYPES:
                continue
            key = (name.lower(), entity_type)
            if key in seen_entities:
                continue
            seen_entities.add(key)
            entities_present.append(
                {
                    "name": name,
                    "entity_type": entity_type,
                    "role_in_scene": self._clean_text(row.get("role_in_scene")),
                    "evidence": self._clean_text(row.get("evidence")),
                }
            )

        state_changes: list[dict[str, Any]] = []
        seen_state: set[tuple[str, str, str, str]] = set()
        for row in response.get("state_changes") or []:
            if not isinstance(row, dict):
                continue
            name, entity_type = self._resolve_entity(
                str(row.get("entity_name") or "").strip(),
                str(row.get("entity_type") or "").strip().lower(),
                roster_context=roster_context,
                roster_by_key=roster_by_key,
            )
            attribute = self._clean_text(row.get("attribute"))
            new_state = self._clean_text(row.get("new_state"))
            evidence = self._clean_text(row.get("evidence"))
            change_type = self._clean_text(row.get("change_type")).lower() or "condition"
            if not name or entity_type not in self.VALID_ENTITY_TYPES or not attribute or not new_state or not evidence:
                continue
            if change_type not in self.VALID_CHANGE_TYPES:
                change_type = "condition"
            key = (name.lower(), attribute.lower(), new_state.lower(), change_type)
            if key in seen_state:
                continue
            seen_state.add(key)
            state_changes.append(
                {
                    "entity_name": name,
                    "entity_type": entity_type,
                    "attribute": attribute,
                    "previous_state": self._clean_text(row.get("previous_state")),
                    "new_state": new_state,
                    "change_type": change_type,
                    "evidence": evidence,
                }
            )

        relationship_changes: list[dict[str, Any]] = []
        seen_rel: set[tuple[str, str, str, str]] = set()
        for row in response.get("relationship_changes") or []:
            if not isinstance(row, dict):
                continue
            source_name, _ = self._resolve_entity(
                str(row.get("source_entity") or "").strip(),
                "character",
                roster_context=roster_context,
                roster_by_key=roster_by_key,
            )
            target_name, _ = self._resolve_entity(
                str(row.get("target_entity") or "").strip(),
                "character",
                roster_context=roster_context,
                roster_by_key=roster_by_key,
            )
            relationship = self._clean_text(row.get("relationship"))
            change = self._clean_text(row.get("change"))
            evidence = self._clean_text(row.get("evidence"))
            if not source_name or not target_name or not relationship or not change or not evidence:
                continue
            key = (source_name.lower(), target_name.lower(), relationship.lower(), change.lower())
            if key in seen_rel:
                continue
            seen_rel.add(key)
            relationship_changes.append(
                {
                    "source_entity": source_name,
                    "target_entity": target_name,
                    "relationship": relationship,
                    "change": change,
                    "evidence": evidence,
                }
            )

        world_state_entities: list[dict[str, Any]] = []
        seen_world: set[tuple[str, str]] = set()
        world_payload = response.get("entity_world_state") or {}
        for row in world_payload.get("entities") or []:
            if not isinstance(row, dict):
                continue
            name, entity_type = self._resolve_entity(
                str(row.get("entity_name") or row.get("name") or "").strip(),
                str(row.get("entity_type") or "").strip().lower(),
                roster_context=roster_context,
                roster_by_key=roster_by_key,
            )
            description = self._clean_text(row.get("description"))
            current_state = self._clean_text(row.get("current_state"))
            if not name or entity_type not in self.VALID_ENTITY_TYPES:
                continue
            if not description and not current_state:
                continue
            key = (name.lower(), entity_type)
            if key in seen_world:
                continue
            seen_world.add(key)
            world_state_entities.append(
                {
                    "entity_name": name,
                    "entity_type": entity_type,
                    "description": description,
                    "current_state": current_state,
                    "state_changes": list(row.get("state_changes") or []),
                }
            )

        location_payload = response.get("location") or {}
        scene_title = self._clean_text(response.get("scene_title")) or f"Scene {bundle.chapter_index}.{bundle.scene_index}"
        scene_summary = self._clean_text(response.get("scene_summary")) or bundle.existing_summary or scene_title
        location_name = self._clean_text(location_payload.get("name")) or bundle.existing_location_name
        return {
            "book_index": 1,
            "chapter_index": bundle.chapter_index,
            "scene_index": bundle.scene_index,
            "scene_title": scene_title,
            "scene_summary": scene_summary,
            "location": {
                "name": location_name,
                "description": self._clean_text(location_payload.get("description")) or bundle.existing_location_description,
                "atmosphere": self._clean_text(location_payload.get("atmosphere")),
            },
            "entities_present": entities_present,
            "events": [
                {
                    "event_id": row.get("event_id"),
                    "description": row.get("description"),
                    "type": row.get("type"),
                    "characters": list((row.get("payload") or {}).get("characters") or []),
                    "entities_involved": list(row.get("entities_involved") or []),
                    "reason": row.get("reason"),
                    "outcome": row.get("outcome"),
                }
                for row in bundle.events
            ],
            "state_changes": state_changes,
            "relationship_changes": relationship_changes,
            "entity_world_state": {
                "entities": world_state_entities,
                "diagnostics": {
                    "source": self.VERSION,
                    "scene_ref": {"chapter_index": bundle.chapter_index, "scene_index": bundle.scene_index},
                },
            },
            "text": bundle.scene_text,
            "analysis_metadata": {"source": self.VERSION},
        }

    def _persist_scene(self, *, bundle: SceneEnrichmentBundle, payload: dict[str, Any]) -> None:
        with self.sqlite_store.session_factory() as session:
            row = session.get(Scene, bundle.scene_id)
            if row is None:
                return
            merged = dict(row.payload_json or {}) if isinstance(row.payload_json, dict) else {}
            merged.update(payload)
            row.summary = str(payload.get("scene_summary") or "").strip() or row.summary
            row.location_name = str(((payload.get("location") or {}).get("name")) or row.location_name or "").strip() or row.location_name
            row.location_description = str(((payload.get("location") or {}).get("description")) or row.location_description or "").strip() or row.location_description
            row.payload_json = merged
            session.commit()

    def _alias_map_from_roster(self, roster: list[dict[str, Any]]) -> dict[str, list[str]]:
        return {
            str(row["name"]): [str(alias).strip() for alias in row.get("aliases") or [] if str(alias).strip()]
            for row in roster
            if str(row.get("name") or "").strip()
        }

    def _resolve_entity(
        self,
        raw_name: str,
        raw_type: str,
        *,
        roster_context: dict[str, Any],
        roster_by_key: dict[str, dict[str, Any]],
    ) -> tuple[str, str]:
        name = str(raw_name or "").strip()
        entity_type = str(raw_type or "").strip().lower()
        if not name:
            return "", entity_type
        resolved = self.normalizer.resolve_name(name, context=roster_context, expect_character=(entity_type == "character"))
        candidate = resolved or self.normalizer.canonicalize_candidate_name(name) or name
        key = self.normalizer.normalized_entity_key(candidate)
        roster_row = roster_by_key.get(key or "")
        if roster_row:
            return str(roster_row["name"]), str(roster_row["entity_type"])
        return candidate, entity_type

    def _clean_text(self, value: Any) -> str:
        return " ".join(str(value or "").strip().split())


