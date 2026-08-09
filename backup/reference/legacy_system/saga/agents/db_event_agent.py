from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from saga.domain.canon_normalization import CanonicalEntityNormalizer
from saga.agents.identity_seed_sanitizer import sanitize_identity_seed
from packages.reasoning_runtime.contracts import ReasoningClient
from saga.providers.reasoning_runtime_adapter import MODE_GENERAL_COMPUTE, MODE_GPT_OSS, create_runtime_client
from saga.storage.models import Book, Entity, Event, IdentityCharacter, IdentitySeries, Scene
from saga.storage.persistence import SagaSQLiteStore


LOGGER = logging.getLogger(__name__)


@dataclass
class ChapterSceneBundle:
    book_id: str
    series_id: str
    chapter_index: int
    scene_id: str | None
    scene_index: int
    scene_text: str
    scene_summary: str
    location_name: str
    location_description: str
    known_entities: list[dict[str, Any]]
    known_characters: list[dict[str, Any]]
    alias_map: dict[str, list[str]]


class DatabaseEventAnalysisAgent:
    VALID_EVENT_TYPES = {"action", "interaction", "movement", "discovery"}
    VERSION = "db_event_agent_v1"
    UNSPECIFIED_REASON = "not_explicitly_stated"
    UNSPECIFIED_OUTCOME = "not_explicitly_stated"
    UNSPECIFIED_LOCATION = "unspecified_location"

    def __init__(
        self,
        *,
        llm_client: ReasoningClient | None = None,
        sqlite_store: SagaSQLiteStore | None = None,
        max_events_per_scene: int = 8,
        max_attempts: int = 3,
        retry_delay_seconds: float = 1.5,
    ) -> None:
        self.sqlite_store = sqlite_store or SagaSQLiteStore()
        self.llm = llm_client or create_runtime_client(mode=MODE_GPT_OSS, allow_account_rotation=True, allow_cross_provider_fallback=False)
        self.max_events_per_scene = max(1, int(max_events_per_scene))
        self.max_attempts = max(1, int(max_attempts))
        self.retry_delay_seconds = max(0.0, float(retry_delay_seconds))
        self.normalizer = CanonicalEntityNormalizer()

    def analyze_book_chapter(
        self,
        *,
        book_ref: str,
        chapter_index: int,
        replace_existing_agent_rows: bool = True,
    ) -> dict[str, Any]:
        book_id = self._resolve_book_id(book_ref)
        bundle = self._load_chapter_bundle(book_id=book_id, chapter_index=chapter_index)
        if bundle is None:
            raise ValueError(f"Could not load chapter {chapter_index} for {book_ref}")
        LOGGER.info(
            "DB event agent start | book=%s chapter=%s scene=%s known_entities=%s",
            bundle.book_id,
            bundle.chapter_index,
            bundle.scene_index,
            len(bundle.known_entities),
        )
        prompt = self._build_prompt(bundle)
        response = self._run_llm_with_retries(bundle=bundle, prompt=prompt)
        normalized = self._normalize_response(bundle=bundle, response=response)
        inserted = self._persist_events(
            bundle=bundle,
            normalized=normalized,
            replace_existing_agent_rows=replace_existing_agent_rows,
        )
        LOGGER.info(
            "DB event agent complete | book=%s chapter=%s inserted=%s unresolved=%s",
            bundle.book_id,
            bundle.chapter_index,
            inserted,
            len(normalized.get("unresolved_entities") or []),
        )
        return {
            "book_id": bundle.book_id,
            "series_id": bundle.series_id,
            "chapter_index": bundle.chapter_index,
            "scene_index": bundle.scene_index,
            "scene_summary": bundle.scene_summary,
            "location_name": bundle.location_name,
            "known_entity_count": len(bundle.known_entities),
            "inserted_event_count": inserted,
            "events": normalized.get("events") or [],
            "unresolved_entities": normalized.get("unresolved_entities") or [],
            "agent_version": self.VERSION,
        }

    def _run_llm_with_retries(self, *, bundle: ChapterSceneBundle, prompt: str) -> dict[str, Any]:
        last_error = ""
        for attempt in range(1, self.max_attempts + 1):
            LOGGER.info(
                "DB event agent LLM attempt start | book=%s chapter=%s attempt=%s/%s",
                bundle.book_id,
                bundle.chapter_index,
                attempt,
                self.max_attempts,
            )
            response = self.llm.generate_json(
                prompt,
                strict=True,
                validator=self._validate_response,
            )
            if isinstance(response, dict) and "error" not in response:
                LOGGER.info(
                    "DB event agent LLM attempt complete | book=%s chapter=%s attempt=%s/%s",
                    bundle.book_id,
                    bundle.chapter_index,
                    attempt,
                    self.max_attempts,
                )
                return response
            last_error = str((response or {}).get("error") or "unknown_error")
            LOGGER.warning(
                "DB event agent LLM attempt failed | book=%s chapter=%s attempt=%s/%s error=%s",
                bundle.book_id,
                bundle.chapter_index,
                attempt,
                self.max_attempts,
                last_error,
            )
            if attempt < self.max_attempts and self.retry_delay_seconds > 0:
                time.sleep(self.retry_delay_seconds)
        raise RuntimeError(
            f"DB event agent failed after {self.max_attempts} attempts "
            f"for book={bundle.book_id} chapter={bundle.chapter_index}: {last_error}"
        )

    def _resolve_book_id(self, book_ref: str) -> str:
        value = str(book_ref or "").strip()
        if value.startswith("db://book/"):
            return value.split("db://book/", 1)[-1].strip()
        return value

    def _load_chapter_bundle(self, *, book_id: str, chapter_index: int) -> ChapterSceneBundle | None:
        with self.sqlite_store.session_factory() as session:
            book = session.get(Book, book_id)
            if book is None:
                return None
            scenes = session.execute(
                select(Scene)
                .where(Scene.book_id == book.id, Scene.chapter_index == int(chapter_index))
                .order_by(Scene.scene_index.asc())
            ).scalars().all()
            if not scenes:
                return None
            primary_scene = scenes[0]
            scene_text = "\n\n".join(str(scene.text or "").strip() for scene in scenes if str(scene.text or "").strip())
            entity_rows = session.execute(
                select(Entity).where(Entity.book_id == book.id).order_by(Entity.canonical_name.asc())
            ).scalars().all()
            known_entities = [
                {
                    "name": str(row.canonical_name or "").strip(),
                    "entity_type": str(row.entity_type or "").strip().lower(),
                    "entity_context": str(row.entity_context or "").strip(),
                    "mention_count": int(row.mention_count or 0),
                }
                for row in entity_rows
                if str(row.canonical_name or "").strip()
            ]
            known_characters, alias_map = self._load_identity_seed(
                session=session,
                series_id=str(book.series_id or "").strip(),
                known_entities=known_entities,
            )
            return ChapterSceneBundle(
                book_id=book.id,
                series_id=str(book.series_id or "").strip(),
                chapter_index=int(chapter_index),
                scene_id=primary_scene.id,
                scene_index=int(primary_scene.scene_index or 1),
                scene_text=scene_text,
                scene_summary=str(primary_scene.summary or "").strip(),
                location_name=str(primary_scene.location_name or "").strip(),
                location_description=str(primary_scene.location_description or "").strip(),
                known_entities=known_entities,
                known_characters=known_characters,
                alias_map=alias_map,
            )

    def _load_identity_seed(
        self,
        *,
        session,
        series_id: str,
        known_entities: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
        if not series_id:
            return [], {}
        identity_series = session.execute(
            select(IdentitySeries).where(IdentitySeries.series_id == series_id)
        ).scalar_one_or_none()
        if identity_series is None:
            return [], {}
        rows = session.execute(
            select(IdentityCharacter).where(IdentityCharacter.identity_series_id == identity_series.id).order_by(IdentityCharacter.display_name.asc())
        ).scalars().all()
        payload = []
        for row in rows:
            item = dict(row.payload_json or {})
            payload.append(
                {
                    "id": str(row.character_id or "").strip(),
                    "display_name": str(row.display_name or "").strip(),
                    "aliases": [str(alias).strip() for alias in (item.get("aliases") or []) if str(alias).strip()],
                    "mention_count": int(row.mention_count or 0),
                    "risk_flags": list(row.risk_flags or item.get("risk_flags") or []),
                }
            )
        cleaned_rows, alias_map, diagnostics = sanitize_identity_seed(
            character_rows=payload,
            non_character_entities=known_entities,
            normalizer=self.normalizer,
        )
        LOGGER.info(
            "DB event agent identity seed sanitized | series=%s before=%s after=%s suppressed=%s merged=%s",
            series_id,
            diagnostics.get("character_count_before", len(payload)),
            diagnostics.get("character_count_after", len(cleaned_rows)),
            len(diagnostics.get("suppressed_rows") or []),
            len(diagnostics.get("merged_rows") or []),
        )
        return cleaned_rows, alias_map

    def _build_prompt(self, bundle: ChapterSceneBundle) -> str:
        compact_entities = [
            {
                "name": row["name"],
                "entity_type": row["entity_type"],
                "entity_context": row["entity_context"][:160],
            }
            for row in bundle.known_entities[:200]
        ]
        return f"""
Extract consequential story events from this chapter scene bundle.

Rules:
- Use only evidence from the provided scene text.
- Return at most {self.max_events_per_scene} events.
- Focus on concrete canon events, not mood, not worldbuilding notes by themselves.
- Every event must include:
  - description
  - type
  - event_location
  - characters
  - locations_involved
  - entities_involved
  - reason
  - outcome
- Entity class definitions:
  - character = a specific human or person-like individual with agency in the event.
  - creature = a non-human living being, beast, animal, monster, or magical creature.
  - object = a physical item, artifact, tool, weapon, vehicle, document, or carried thing.
  - location = a place, address, building, room, street, area, or physical setting.
  - organization = a named group, institution, household, faction, company, school-as-institution, or formal collective.
- Allowed event types only: action, interaction, movement, discovery
- "event_location" should be the most specific grounded place for the event.
- If the exact event location is not explicit but the scene location is known, use the scene location.
- Only use "{self.UNSPECIFIED_LOCATION}" when no grounded location can be recovered.
- "characters" should include only consequential character participants.
- "creatures_involved" is optional. Use it only when a non-human creature, animal, beast, monster, or magical creature is actually involved.
- "objects_involved" is optional. Use it only when a concrete object, tool, weapon, artifact, vehicle, letter, or similar item is actually used or affected.
- "locations_involved" should include the event location plus any other clearly involved places/settings.
- "organizations_involved" is optional. Use it only when a named group, institution, household, faction, company, staff, or formal collective is actually involved.
- "entities_involved" must be the union of the concrete participants you named across characters, objects, locations, creatures, and organizations.
- "reason" must be a short grounded explanation when stated or strongly implied. If not recoverable, use "{self.UNSPECIFIED_REASON}".
- "outcome" must be a short grounded consequence. If not recoverable, use "{self.UNSPECIFIED_OUTCOME}".
- Prefer canonical names from the known entity roster when possible.
- If an entity is not in the roster, still include it if grounded by the text.
- Do not invent details not directly supported by the text.
- Keep descriptions specific and short.

Return JSON only:
{{
  "events": [
    {{
      "description": "short concrete event description",
      "event_location": "specific location name or {self.UNSPECIFIED_LOCATION}",
      "characters": ["Canonical Character Name"],
      "creatures_involved": ["Creature Name"],
      "objects_involved": ["Object Name"],
      "locations_involved": ["Location Name"],
      "organizations_involved": ["Organization Name"],
      "entities_involved": ["Canonical Character Name", "Object or Place"],
      "reason": "why it happens if stated or strongly implied, else {self.UNSPECIFIED_REASON}",
      "outcome": "what changes because of it, else {self.UNSPECIFIED_OUTCOME}",
      "type": "action"
    }}
  ]
}}

Scene summary:
{bundle.scene_summary or "n/a"}

Scene location:
{json.dumps({"name": bundle.location_name, "description": bundle.location_description}, ensure_ascii=False)}

Known entity roster:
{json.dumps(compact_entities, ensure_ascii=False)}

Alias map:
{json.dumps(bundle.alias_map, ensure_ascii=False)}

Scene text:
{bundle.scene_text}
"""

    def _validate_response(self, response: dict[str, Any]) -> bool:
        events = response.get("events")
        if not isinstance(events, list):
            return False
        for row in events[: self.max_events_per_scene]:
            if not isinstance(row, dict):
                return False
            if not str(row.get("description") or "").strip():
                return False
            if not isinstance(str(row.get("event_location") or ""), str):
                return False
            if not isinstance(row.get("characters") or [], list):
                return False
            if row.get("creatures_involved") is not None and not isinstance(row.get("creatures_involved"), list):
                return False
            if row.get("objects_involved") is not None and not isinstance(row.get("objects_involved"), list):
                return False
            if row.get("locations_involved") is not None and not isinstance(row.get("locations_involved"), list):
                return False
            if row.get("organizations_involved") is not None and not isinstance(row.get("organizations_involved"), list):
                return False
            if not isinstance(row.get("entities_involved") or [], list):
                return False
        return True

    def _normalize_response(self, *, bundle: ChapterSceneBundle, response: dict[str, Any]) -> dict[str, Any]:
        context = self.normalizer.build_context(
            entity_registry=[
                {"name": row["name"], "entity_type": row["entity_type"]}
                for row in bundle.known_entities
            ],
            alias_map=bundle.alias_map,
        )
        known_names = {str(row["name"]).lower(): row for row in bundle.known_entities}
        canonical_character_names: dict[str, str] = {}
        for row in bundle.known_characters:
            best_name = self._best_seeded_character_name(row)
            surfaces = [str(row.get("display_name") or "").strip(), *(row.get("aliases") or [])]
            for surface in surfaces:
                key = self.normalizer.normalized_entity_key(surface)
                if key:
                    canonical_character_names[key] = best_name
        normalized_events: list[dict[str, Any]] = []
        unresolved_entities: list[str] = []
        for index, row in enumerate((response.get("events") or [])[: self.max_events_per_scene], start=1):
            description = str(row.get("description") or "").strip()
            if not description:
                continue
            event_type = str(row.get("type") or "").strip().lower()
            if event_type not in self.VALID_EVENT_TYPES:
                event_type = "action"
            event_reason = self._normalize_event_explanation(row.get("reason"), default=self.UNSPECIFIED_REASON)
            event_outcome = self._normalize_event_explanation(row.get("outcome"), default=self.UNSPECIFIED_OUTCOME)
            non_character_raw_keys = {
                self.normalizer.normalized_entity_key(str(item).strip())
                for item in [
                    row.get("event_location"),
                    *(row.get("creatures_involved") or []),
                    *(row.get("objects_involved") or []),
                    *(row.get("locations_involved") or []),
                    *(row.get("organizations_involved") or []),
                ]
                if self.normalizer.normalized_entity_key(str(item).strip())
            }
            raw_characters = [str(item).strip() for item in (row.get("characters") or []) if str(item).strip()]
            normalized_characters: list[str] = []
            for item in raw_characters:
                if self.normalizer.normalized_entity_key(item) in non_character_raw_keys:
                    continue
                resolved = self.normalizer.resolve_name(item, context=context, expect_character=True) or self.normalizer.canonicalize_candidate_name(item)
                resolved_key = self.normalizer.normalized_entity_key(resolved)
                if resolved_key in non_character_raw_keys:
                    continue
                if resolved.lower() in known_names and str(known_names[resolved.lower()].get("entity_type") or "").strip().lower() != "character":
                    continue
                if resolved_key in canonical_character_names:
                    resolved = canonical_character_names[resolved_key]
                if resolved and resolved not in normalized_characters:
                    normalized_characters.append(resolved)
            normalized_character_keys = self._expand_character_surface_keys(bundle=bundle, character_names=normalized_characters)
            event_location = str(row.get("event_location") or "").strip() or str(bundle.location_name or "").strip()
            normalized_event_location = (
                self.normalizer.resolve_name(event_location, context=context, expect_character=False)
                or self.normalizer.canonicalize_candidate_name(event_location)
                or event_location
            ).strip()
            if not normalized_event_location:
                normalized_event_location = self.UNSPECIFIED_LOCATION
            raw_creatures = [str(item).strip() for item in (row.get("creatures_involved") or []) if str(item).strip()]
            normalized_creatures: list[str] = []
            for item in raw_creatures:
                if self.normalizer.normalized_entity_key(item) in normalized_character_keys:
                    continue
                resolved = self.normalizer.resolve_name(item, context=context, expect_character=False) or self.normalizer.canonicalize_candidate_name(item) or item
                if not resolved:
                    continue
                if resolved.lower() not in known_names:
                    unresolved_entities.append(resolved)
                if resolved not in normalized_creatures:
                    normalized_creatures.append(resolved)
            raw_objects = [str(item).strip() for item in (row.get("objects_involved") or []) if str(item).strip()]
            normalized_objects: list[str] = []
            for item in raw_objects:
                if self.normalizer.normalized_entity_key(item) in normalized_character_keys:
                    continue
                resolved = self.normalizer.resolve_name(item, context=context, expect_character=False) or self.normalizer.canonicalize_candidate_name(item) or item
                if not resolved:
                    continue
                if resolved.lower() not in known_names:
                    unresolved_entities.append(resolved)
                if resolved not in normalized_objects:
                    normalized_objects.append(resolved)
            raw_locations = [str(item).strip() for item in (row.get("locations_involved") or []) if str(item).strip()]
            normalized_locations: list[str] = []
            for item in [normalized_event_location, *raw_locations]:
                cleaned = str(item or "").strip()
                if not cleaned or cleaned == self.UNSPECIFIED_LOCATION:
                    continue
                if self.normalizer.normalized_entity_key(cleaned) in normalized_character_keys:
                    continue
                resolved = self.normalizer.resolve_name(cleaned, context=context, expect_character=False) or self.normalizer.canonicalize_candidate_name(cleaned) or cleaned
                if not resolved:
                    continue
                if resolved.lower() not in known_names:
                    unresolved_entities.append(resolved)
                if resolved not in normalized_locations:
                    normalized_locations.append(resolved)
            raw_organizations = [str(item).strip() for item in (row.get("organizations_involved") or []) if str(item).strip()]
            normalized_organizations: list[str] = []
            for item in raw_organizations:
                if self.normalizer.normalized_entity_key(item) in normalized_character_keys:
                    continue
                resolved = self.normalizer.resolve_name(item, context=context, expect_character=False) or self.normalizer.canonicalize_candidate_name(item) or item
                if not resolved:
                    continue
                if resolved.lower() not in known_names:
                    unresolved_entities.append(resolved)
                if resolved not in normalized_organizations:
                    normalized_organizations.append(resolved)
            raw_entities = [str(item).strip() for item in (row.get("entities_involved") or []) if str(item).strip()]
            normalized_entities: list[str] = []
            for item in [*normalized_characters, *normalized_creatures, *normalized_objects, *normalized_locations, *normalized_organizations, *raw_entities]:
                resolved = self.normalizer.resolve_name(item, context=context, expect_character=False) or self.normalizer.canonicalize_candidate_name(item) or item
                if not resolved:
                    continue
                if resolved.lower() not in known_names:
                    unresolved_entities.append(resolved)
                if resolved not in normalized_entities:
                    normalized_entities.append(resolved)
            normalized_events.append(
                {
                    "event_id": f"{self.VERSION}_b1_c{bundle.chapter_index}_s{bundle.scene_index}_{index}",
                    "description": description,
                    "event_location": normalized_event_location,
                    "characters": normalized_characters,
                    "creatures_involved": normalized_creatures,
                    "objects_involved": normalized_objects,
                    "locations_involved": normalized_locations,
                    "organizations_involved": normalized_organizations,
                    "entities_involved": normalized_entities,
                    "reason": event_reason,
                    "outcome": event_outcome,
                    "type": event_type,
                    "chapter_index": bundle.chapter_index,
                    "scene_index": bundle.scene_index,
                }
            )
        return {
            "events": normalized_events,
            "unresolved_entities": sorted({item for item in unresolved_entities if item}),
        }

    def _normalize_event_explanation(self, value: Any, *, default: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            return default
        lowered = cleaned.lower()
        if lowered in {"n/a", "na", "none", "unknown", "not stated", "not specified", "unspecified"}:
            return default
        return cleaned

    def _expand_character_surface_keys(self, *, bundle: ChapterSceneBundle, character_names: list[str]) -> set[str]:
        target_keys = {self.normalizer.normalized_entity_key(name) for name in character_names if self.normalizer.normalized_entity_key(name)}
        protected: set[str] = set(target_keys)
        for row in bundle.known_characters:
            best_name = self._best_seeded_character_name(row)
            candidate_keys = {
                self.normalizer.normalized_entity_key(best_name),
                self.normalizer.normalized_entity_key(str(row.get("display_name") or "").strip()),
                *{
                    self.normalizer.normalized_entity_key(alias)
                    for alias in (row.get("aliases") or [])
                    if self.normalizer.normalized_entity_key(alias)
                },
            }
            if target_keys & {item for item in candidate_keys if item}:
                protected.update(item for item in candidate_keys if item)
        return protected

    def _best_seeded_character_name(self, row: dict[str, Any]) -> str:
        display_name = str(row.get("display_name") or "").strip()
        aliases = [str(item).strip() for item in (row.get("aliases") or []) if str(item).strip()]
        candidates = [display_name, *aliases]
        best = display_name
        best_score = self._seed_name_score(display_name)
        for candidate in candidates:
            score = self._seed_name_score(candidate)
            if score > best_score:
                best = candidate
                best_score = score
        return best or display_name

    def _seed_name_score(self, value: str) -> tuple[int, int, int, int]:
        cleaned = str(value or "").strip()
        token_count = len(cleaned.split())
        has_title_case = 1 if cleaned and cleaned[:1].isupper() else 0
        has_full_name = 1 if token_count >= 2 else 0
        has_noise = 1 if any(token.islower() for token in cleaned.split()[1:]) else 0
        return (has_full_name, token_count, has_title_case, -has_noise)

    def _normalize_search_text(self, value: str) -> str:
        cleaned = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
        return " ".join(cleaned.split())

    def _persist_events(
        self,
        *,
        bundle: ChapterSceneBundle,
        normalized: dict[str, Any],
        replace_existing_agent_rows: bool,
    ) -> int:
        inserted = 0
        with self.sqlite_store.session_factory() as session:
            if replace_existing_agent_rows:
                prior_rows = session.execute(
                    select(Event).where(
                        Event.book_id == bundle.book_id,
                        Event.chapter_index == bundle.chapter_index,
                    )
                ).scalars().all()
                for row in prior_rows:
                    payload = row.payload_json if isinstance(row.payload_json, dict) else {}
                    source = str(((payload.get("agent_metadata") or {}).get("source")) or "")
                    if source == self.VERSION:
                        session.delete(row)
            for row in normalized.get("events") or []:
                event = Event(
                    book_id=bundle.book_id,
                    scene_id=bundle.scene_id,
                    chapter_index=bundle.chapter_index,
                    scene_index=bundle.scene_index,
                    event_id_external=str(row.get("event_id") or "").strip() or None,
                    event_type=str(row.get("type") or "").strip() or None,
                    description=str(row.get("description") or "").strip() or None,
                    reason=str(row.get("reason") or "").strip() or None,
                    outcome=str(row.get("outcome") or "").strip() or None,
                    entities_involved=row.get("entities_involved") if isinstance(row.get("entities_involved"), list) else None,
                    payload_json={
                        **row,
                        "agent_metadata": {
                            "source": self.VERSION,
                            "chapter_index": bundle.chapter_index,
                            "scene_index": bundle.scene_index,
                            "known_entity_count": len(bundle.known_entities),
                        },
                    },
                )
                session.add(event)
                inserted += 1
            session.commit()
        return inserted


