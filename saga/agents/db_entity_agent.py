from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from saga.domain.canon_normalization import CanonicalEntityNormalizer
from saga.agents.identity_seed_sanitizer import sanitize_identity_seed
from saga.providers.llm_client import LLMClient
from saga.storage.models import Book, Entity, Event, IdentityCharacter, IdentitySeries, Scene
from saga.storage.persistence import SagaSQLiteStore


LOGGER = logging.getLogger(__name__)


@dataclass
class ChapterEntityBundle:
    book_id: str
    series_id: str
    chapter_index: int
    scene_count: int
    scene_text: str
    scene_map: dict[int, dict[str, Any]]
    scene_refs: list[dict[str, Any]]
    chapter_events: list[dict[str, Any]]
    known_characters: list[dict[str, Any]]
    existing_entities: list[dict[str, Any]]
    alias_map: dict[str, list[str]]


@dataclass
class MentionCandidate:
    surface: str
    mention_type: str
    expected_type: str
    evidence_rows: list[dict[str, Any]]
    scene_indices: list[int]


class DatabaseEntityDiscoveryAgent:
    VALID_ENTITY_TYPES = {"character", "creature", "object", "location", "organization", "other"}
    VERSION = "db_entity_discovery_agent_v1"
    LOCATION_FORCE_TOKENS = {"drive", "street", "road", "lane", "avenue", "way"}
    LOCATION_FORCE_NAMES = {
        "hogwarts",
        "privetdrive",
        "littlewhinging",
        "surrey",
        "gringotts",
        "diagonalley",
        "platform934",
    }
    ORGANIZATION_HINT_TOKENS = {"school", "ministry", "family", "household", "staff", "team", "order", "guild"}
    GENERIC_NON_ENTITY_TOKENS = {"street", "road", "lane", "avenue", "way", "people", "person"}
    CHARACTER_FIELD_TYPES = {"event_character"}
    LOCATION_FIELD_TYPES = {"event_location", "event_location_involved"}
    OBJECT_FIELD_TYPES = {"event_object"}
    CREATURE_FIELD_TYPES = {"event_creature"}
    ORGANIZATION_FIELD_TYPES = {"event_organization"}

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        sqlite_store: SagaSQLiteStore | None = None,
        max_entities_per_chapter: int = 40,
        max_attempts: int = 3,
        retry_delay_seconds: float = 1.5,
    ) -> None:
        self.sqlite_store = sqlite_store or SagaSQLiteStore()
        self.llm = llm_client or LLMClient(
            mode=LLMClient.MODE_GPT_OSS,
            allow_account_rotation=True,
            allow_cross_provider_fallback=False,
        )
        self.max_entities_per_chapter = max(1, int(max_entities_per_chapter))
        self.max_attempts = max(1, int(max_attempts))
        self.retry_delay_seconds = max(0.0, float(retry_delay_seconds))
        self.normalizer = CanonicalEntityNormalizer()

    def analyze_book_chapter(
        self,
        *,
        book_ref: str,
        chapter_index: int,
    ) -> dict[str, Any]:
        book_id = self._resolve_book_id(book_ref)
        bundle = self._load_chapter_bundle(book_id=book_id, chapter_index=chapter_index)
        if bundle is None:
            raise ValueError(f"Could not load chapter {chapter_index} for {book_ref}")
        LOGGER.info(
            "DB entity agent start | book=%s chapter=%s scenes=%s known_characters=%s existing_entities=%s",
            bundle.book_id,
            bundle.chapter_index,
            bundle.scene_count,
            len(bundle.known_characters),
            len(bundle.existing_entities),
        )
        mentions = self._harvest_event_mentions(bundle)
        LOGGER.info(
            "DB entity agent mention harvest | book=%s chapter=%s mentions=%s events=%s",
            bundle.book_id,
            bundle.chapter_index,
            len(mentions),
            len(bundle.chapter_events),
        )
        normalized = self._resolve_mentions(bundle=bundle, mentions=mentions)
        persisted = self._persist_entities(bundle=bundle, normalized=normalized)
        LOGGER.info(
            "DB entity agent complete | book=%s chapter=%s inserted=%s updated=%s unresolved=%s",
            bundle.book_id,
            bundle.chapter_index,
            persisted["inserted_count"],
            persisted["updated_count"],
            len(normalized.get("unresolved_entities") or []),
        )
        return {
            "book_id": bundle.book_id,
            "series_id": bundle.series_id,
            "chapter_index": bundle.chapter_index,
            "scene_count": bundle.scene_count,
            "inserted_count": persisted["inserted_count"],
            "updated_count": persisted["updated_count"],
            "entities": normalized.get("entities") or [],
            "unresolved_entities": normalized.get("unresolved_entities") or [],
            "agent_version": self.VERSION,
        }

    def _resolve_book_id(self, book_ref: str) -> str:
        value = str(book_ref or "").strip()
        if value.startswith("db://book/"):
            return value.split("db://book/", 1)[-1].strip()
        return value

    def _load_chapter_bundle(self, *, book_id: str, chapter_index: int) -> ChapterEntityBundle | None:
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
            scene_text = "\n\n".join(str(scene.text or "").strip() for scene in scenes if str(scene.text or "").strip())
            scene_map = {
                int(scene.scene_index or 1): {
                    "scene_id": scene.id,
                    "scene_index": int(scene.scene_index or 1),
                    "summary": str(scene.summary or "").strip(),
                    "text": str(scene.text or "").strip(),
                    "final_status": str(scene.final_status or "").strip(),
                }
                for scene in scenes
            }
            scene_refs = [
                {
                    "scene_id": scene.id,
                    "scene_index": int(scene.scene_index or 1),
                    "summary": str(scene.summary or "").strip(),
                    "final_status": str(scene.final_status or "").strip(),
                }
                for scene in scenes
            ]
            chapter_events = [
                dict(row.payload_json or {})
                for row in session.execute(
                    select(Event)
                    .where(Event.book_id == book.id, Event.chapter_index == int(chapter_index))
                    .order_by(Event.scene_index.asc(), Event.created_at.asc())
                ).scalars().all()
            ]
            existing_entities = [
                {
                    "name": str(row.canonical_name or "").strip(),
                    "entity_type": str(row.entity_type or "").strip().lower(),
                    "aliases": list((row.metadata_json or {}).get("aliases") or []),
                }
                for row in session.execute(
                    select(Entity).where(Entity.book_id == book.id).order_by(Entity.entity_type.asc(), Entity.canonical_name.asc())
                ).scalars().all()
            ]
            known_characters, alias_map = self._load_identity_seed(
                session=session,
                series_id=str(book.series_id or "").strip(),
                existing_entities=existing_entities,
            )
            return ChapterEntityBundle(
                book_id=book.id,
                series_id=str(book.series_id or "").strip(),
                chapter_index=int(chapter_index),
                scene_count=len(scenes),
                scene_text=scene_text,
                scene_map=scene_map,
                scene_refs=scene_refs,
                chapter_events=chapter_events,
                known_characters=known_characters,
                existing_entities=existing_entities,
                alias_map=alias_map,
            )

    def _harvest_event_mentions(self, bundle: ChapterEntityBundle) -> list[MentionCandidate]:
        collected: dict[tuple[str, str], MentionCandidate] = {}
        for event in bundle.chapter_events:
            if not isinstance(event, dict):
                continue
            evidence = {
                "description": str(event.get("description") or "").strip(),
                "reason": str(event.get("reason") or "").strip(),
                "outcome": str(event.get("outcome") or "").strip(),
                "scene_index": event.get("scene_index"),
                "event_type": str(event.get("type") or event.get("event_type") or "").strip(),
            }
            for name in event.get("characters") or []:
                surface = str(name or "").strip()
                if not surface:
                    continue
                key = (surface.lower(), "character")
                row = collected.setdefault(
                    key,
                    MentionCandidate(surface=surface, mention_type="event_character", expected_type="character", evidence_rows=[], scene_indices=[]),
                )
                row.evidence_rows.append(evidence)
                scene_index = event.get("scene_index")
                if isinstance(scene_index, int) and scene_index not in row.scene_indices:
                    row.scene_indices.append(scene_index)
            event_location = str(event.get("event_location") or "").strip()
            if event_location and event_location.lower() != "unspecified_location":
                key = (event_location.lower(), "location")
                row = collected.setdefault(
                    key,
                    MentionCandidate(surface=event_location, mention_type="event_location", expected_type="location", evidence_rows=[], scene_indices=[]),
                )
                row.evidence_rows.append(evidence)
                scene_index = event.get("scene_index")
                if isinstance(scene_index, int) and scene_index not in row.scene_indices:
                    row.scene_indices.append(scene_index)
            for name in event.get("objects_involved") or []:
                surface = str(name or "").strip()
                if not surface:
                    continue
                key = (surface.lower(), "object")
                row = collected.setdefault(
                    key,
                    MentionCandidate(surface=surface, mention_type="event_object", expected_type="object", evidence_rows=[], scene_indices=[]),
                )
                row.evidence_rows.append(evidence)
                scene_index = event.get("scene_index")
                if isinstance(scene_index, int) and scene_index not in row.scene_indices:
                    row.scene_indices.append(scene_index)
            for name in event.get("creatures_involved") or []:
                surface = str(name or "").strip()
                if not surface:
                    continue
                key = (surface.lower(), "creature")
                row = collected.setdefault(
                    key,
                    MentionCandidate(surface=surface, mention_type="event_creature", expected_type="creature", evidence_rows=[], scene_indices=[]),
                )
                row.evidence_rows.append(evidence)
                scene_index = event.get("scene_index")
                if isinstance(scene_index, int) and scene_index not in row.scene_indices:
                    row.scene_indices.append(scene_index)
            for name in event.get("locations_involved") or []:
                surface = str(name or "").strip()
                if not surface or surface.lower() == "unspecified_location":
                    continue
                key = (surface.lower(), "location")
                row = collected.setdefault(
                    key,
                    MentionCandidate(surface=surface, mention_type="event_location_involved", expected_type="location", evidence_rows=[], scene_indices=[]),
                )
                row.evidence_rows.append(evidence)
                scene_index = event.get("scene_index")
                if isinstance(scene_index, int) and scene_index not in row.scene_indices:
                    row.scene_indices.append(scene_index)
            for name in event.get("organizations_involved") or []:
                surface = str(name or "").strip()
                if not surface:
                    continue
                key = (surface.lower(), "organization")
                row = collected.setdefault(
                    key,
                    MentionCandidate(surface=surface, mention_type="event_organization", expected_type="organization", evidence_rows=[], scene_indices=[]),
                )
                row.evidence_rows.append(evidence)
                scene_index = event.get("scene_index")
                if isinstance(scene_index, int) and scene_index not in row.scene_indices:
                    row.scene_indices.append(scene_index)
            for name in event.get("entities_involved") or []:
                surface = str(name or "").strip()
                if not surface:
                    continue
                if (surface.lower(), "creature") in collected:
                    continue
                if (surface.lower(), "object") in collected:
                    continue
                if (surface.lower(), "location") in collected:
                    continue
                if (surface.lower(), "organization") in collected:
                    continue
                key = (surface.lower(), "entity")
                row = collected.setdefault(
                    key,
                    MentionCandidate(surface=surface, mention_type="event_entity", expected_type="", evidence_rows=[], scene_indices=[]),
                )
                row.evidence_rows.append(evidence)
                scene_index = event.get("scene_index")
                if isinstance(scene_index, int) and scene_index not in row.scene_indices:
                    row.scene_indices.append(scene_index)
        return sorted(collected.values(), key=lambda item: (item.surface.lower(), self._mention_type_priority(item.mention_type)))

    def _mention_type_priority(self, mention_type: str) -> int:
        order = {
            "event_location": 0,
            "event_location_involved": 1,
            "event_object": 2,
            "event_creature": 3,
            "event_organization": 4,
            "event_entity": 5,
            "event_character": 6,
        }
        return order.get(str(mention_type or "").strip(), 99)

    def _load_identity_seed(
        self,
        *,
        session,
        series_id: str,
        existing_entities: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
        if not series_id:
            return [], {}
        identity_series = session.execute(select(IdentitySeries).where(IdentitySeries.series_id == series_id)).scalar_one_or_none()
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
                    "aliases": list(item.get("aliases") or []),
                    "mention_count": int(row.mention_count or 0),
                    "risk_flags": list(item.get("risk_flags") or []),
                }
            )
        cleaned_rows, alias_map, diagnostics = sanitize_identity_seed(
            character_rows=payload,
            non_character_entities=existing_entities,
            normalizer=self.normalizer,
        )
        LOGGER.info(
            "DB entity agent identity seed sanitized | series=%s before=%s after=%s suppressed=%s merged=%s",
            series_id,
            diagnostics.get("character_count_before", len(payload)),
            diagnostics.get("character_count_after", len(cleaned_rows)),
            len(diagnostics.get("suppressed_rows") or []),
            len(diagnostics.get("merged_rows") or []),
        )
        return cleaned_rows, alias_map

    def _validate_classification_response(self, response: dict[str, Any]) -> bool:
        if not isinstance(response, dict):
            return False
        if not isinstance(response.get("should_create"), bool):
            return False
        if response.get("should_create") is False:
            return True
        if not str(response.get("canonical_name") or "").strip():
            return False
        if str(response.get("entity_type") or "").strip().lower() not in self.VALID_ENTITY_TYPES:
            return False
        if not isinstance(response.get("aliases") or [], list):
            return False
        return True

    def _validate_character_resolution_response(self, response: dict[str, Any]) -> bool:
        if not isinstance(response, dict):
            return False
        choice = str(response.get("selected_display_name") or "").strip()
        if choice and not isinstance(response.get("aliases") or [], list):
            return False
        return True

    def _run_llm_with_retries(self, *, bundle: ChapterEntityBundle, prompt: str, validator) -> dict[str, Any]:
        last_error = ""
        for attempt in range(1, self.max_attempts + 1):
            LOGGER.info(
                "DB entity agent LLM attempt start | book=%s chapter=%s attempt=%s/%s",
                bundle.book_id,
                bundle.chapter_index,
                attempt,
                self.max_attempts,
            )
            response = self.llm.generate_json(
                prompt,
                strict=True,
                validator=validator,
            )
            if isinstance(response, dict) and "error" not in response:
                LOGGER.info(
                    "DB entity agent LLM attempt complete | book=%s chapter=%s attempt=%s/%s",
                    bundle.book_id,
                    bundle.chapter_index,
                    attempt,
                    self.max_attempts,
                )
                return response
            last_error = str((response or {}).get("error") or "unknown_error")
            LOGGER.warning(
                "DB entity agent LLM attempt failed | book=%s chapter=%s attempt=%s/%s error=%s",
                bundle.book_id,
                bundle.chapter_index,
                attempt,
                self.max_attempts,
                last_error,
            )
            if attempt < self.max_attempts and self.retry_delay_seconds > 0:
                time.sleep(self.retry_delay_seconds)
        raise RuntimeError(
            f"DB entity agent failed after {self.max_attempts} attempts "
            f"for book={bundle.book_id} chapter={bundle.chapter_index}: {last_error}"
        )

    def _normalize_response(self, *, bundle: ChapterEntityBundle, mention: MentionCandidate, payload: dict[str, Any]) -> dict[str, Any]:
        context = self.normalizer.build_context(
            entity_registry=bundle.existing_entities + [{"name": row["display_name"], "entity_type": "character"} for row in bundle.known_characters],
            alias_map=bundle.alias_map,
        )
        canonical_character_names: dict[str, str] = {}
        for row in bundle.known_characters:
            best_name = self._best_seeded_character_name(row)
            surfaces = [str(row.get("display_name") or "").strip(), *(row.get("aliases") or [])]
            for surface in surfaces:
                key = self.normalizer.normalized_entity_key(surface)
                if key:
                    canonical_character_names[key] = best_name
        raw_name = str(payload.get("canonical_name") or payload.get("name") or mention.surface).strip()
        raw_type = str(payload.get("entity_type") or mention.expected_type or "other").strip().lower()
        resolved_name = self.normalizer.resolve_name(
            raw_name,
            context=context,
            expect_character=(raw_type == "character"),
        ) or raw_name
        resolved_type = raw_type if raw_type in self.VALID_ENTITY_TYPES else "other"
        aliases = []
        for item in payload.get("aliases") or []:
            alias = str(item).strip()
            if alias and alias.lower() != resolved_name.lower() and alias not in aliases:
                aliases.append(alias)
        entity_context = str(payload.get("entity_context") or "").strip()
        evidence = str(payload.get("evidence") or "").strip()
        character_key = self.normalizer.normalized_entity_key(resolved_name)
        allow_character_promotion = (
            raw_type == "character"
            or str(mention.expected_type or "").strip().lower() == "character"
            or mention.mention_type in self.CHARACTER_FIELD_TYPES
        )
        if allow_character_promotion and character_key in canonical_character_names:
            resolved_name = canonical_character_names[character_key]
            resolved_type = "character"
        else:
            lowered_name_tokens = {token.lower() for token in resolved_name.split()}
            if lowered_name_tokens & self.LOCATION_FORCE_TOKENS:
                resolved_type = "location"
            elif resolved_type in {"location", "object", "organization", "creature"}:
                resolved_type = resolved_type
            else:
                inferred_type = self.normalizer.infer_entity_type(
                    resolved_name,
                    existing_type=resolved_type,
                    descriptions=[entity_context, evidence],
                )
                if inferred_type in self.VALID_ENTITY_TYPES and inferred_type != "unknown":
                    resolved_type = inferred_type
        return {
            "name": resolved_name,
            "entity_type": resolved_type,
            "aliases": aliases,
            "entity_context": entity_context,
            "evidence": evidence,
            "chapter_index": bundle.chapter_index,
            "scene_index": 1,
            "source_scene_count": bundle.scene_count,
        }

    def _resolve_mentions(self, *, bundle: ChapterEntityBundle, mentions: list[MentionCandidate]) -> dict[str, Any]:
        normalized_entities_by_surface: dict[str, tuple[int, dict[str, Any]]] = {}
        unresolved_entities: list[str] = []
        seen: set[tuple[str, str]] = set()
        non_character_surface_hints: dict[str, set[str]] = {}
        for mention in mentions:
            key = self.normalizer.normalized_entity_key(mention.surface)
            expected_type = str(mention.expected_type or "").strip().lower()
            if not key or expected_type not in {"location", "object", "creature", "organization"}:
                continue
            non_character_surface_hints.setdefault(key, set()).add(expected_type)
        for mention in mentions[: self.max_entities_per_chapter]:
            mention_key = self.normalizer.normalized_entity_key(mention.surface)
            if (
                mention_key
                and mention.mention_type in self.CHARACTER_FIELD_TYPES
                and mention_key in non_character_surface_hints
            ):
                continue
            resolved = (
                self._resolve_against_identity(bundle, mention)
                or self._resolve_deterministic_typed_mention(bundle, mention)
                or self._resolve_against_existing_entities(bundle, mention)
                or self._classify_unresolved_mention(bundle, mention)
            )
            if not resolved:
                unresolved_entities.append(mention.surface)
                continue
            normalized = self._normalize_response(bundle=bundle, mention=mention, payload=resolved)
            key = (str(normalized["name"]).lower(), str(normalized["entity_type"]).lower())
            if key in seen:
                continue
            surface_key = self.normalizer.normalized_entity_key(mention.surface) or str(normalized["name"]).lower()
            rank = self._mention_resolution_rank(mention, normalized)
            current = normalized_entities_by_surface.get(surface_key)
            if current is not None and current[0] >= rank:
                continue
            if current is not None:
                previous = current[1]
                seen.discard((str(previous["name"]).lower(), str(previous["entity_type"]).lower()))
            seen.add(key)
            normalized_entities_by_surface[surface_key] = (rank, normalized)
        normalized_entities = [item[1] for item in normalized_entities_by_surface.values()]
        normalized_entities.sort(key=lambda row: (str(row["entity_type"]), str(row["name"]).lower()))
        return {"entities": normalized_entities, "unresolved_entities": sorted(set(unresolved_entities))}

    def _mention_resolution_rank(self, mention: MentionCandidate, normalized: dict[str, Any]) -> int:
        entity_type = str(normalized.get("entity_type") or "").strip().lower()
        expected_type = str(mention.expected_type or "").strip().lower()
        if expected_type and entity_type == expected_type:
            return 4
        if mention.mention_type == "event_entity" and entity_type in {"location", "object", "creature", "organization"}:
            return 5
        if mention.mention_type in self.LOCATION_FIELD_TYPES and entity_type == "location":
            return 4
        if mention.mention_type in self.OBJECT_FIELD_TYPES and entity_type == "object":
            return 4
        if mention.mention_type in self.CREATURE_FIELD_TYPES and entity_type == "creature":
            return 4
        if mention.mention_type in self.ORGANIZATION_FIELD_TYPES and entity_type == "organization":
            return 4
        if mention.mention_type in self.CHARACTER_FIELD_TYPES and entity_type == "character":
            return 4
        if self._forced_entity_type(mention.surface) == entity_type and entity_type:
            return 3
        if entity_type in {"location", "object", "organization", "creature"}:
            return 2
        return 1

    def _resolve_deterministic_typed_mention(self, bundle: ChapterEntityBundle, mention: MentionCandidate) -> dict[str, Any] | None:
        forced_type = self._forced_entity_type(mention.surface)
        expected_type = str(mention.expected_type or "").strip().lower()
        if mention.mention_type in self.LOCATION_FIELD_TYPES:
            return {
                "canonical_name": self._clean_non_character_name(mention.surface),
                "entity_type": forced_type or expected_type or "location",
                "aliases": [],
                "entity_context": self._mention_evidence_summary(mention),
                "evidence": self._mention_evidence_summary(mention),
            }
        if mention.mention_type in self.OBJECT_FIELD_TYPES:
            return {
                "canonical_name": self._clean_non_character_name(mention.surface),
                "entity_type": "object",
                "aliases": [],
                "entity_context": self._mention_evidence_summary(mention),
                "evidence": self._mention_evidence_summary(mention),
            }
        if mention.mention_type in self.CREATURE_FIELD_TYPES:
            return {
                "canonical_name": self._clean_non_character_name(mention.surface),
                "entity_type": "creature",
                "aliases": [],
                "entity_context": self._mention_evidence_summary(mention),
                "evidence": self._mention_evidence_summary(mention),
            }
        if mention.mention_type in self.ORGANIZATION_FIELD_TYPES:
            return {
                "canonical_name": self._clean_non_character_name(mention.surface),
                "entity_type": "organization",
                "aliases": [],
                "entity_context": self._mention_evidence_summary(mention),
                "evidence": self._mention_evidence_summary(mention),
            }
        if forced_type and forced_type != "character":
            return {
                "canonical_name": self._clean_non_character_name(mention.surface),
                "entity_type": forced_type,
                "aliases": [],
                "entity_context": self._mention_evidence_summary(mention),
                "evidence": self._mention_evidence_summary(mention),
            }
        return None

    def _resolve_against_identity(self, bundle: ChapterEntityBundle, mention: MentionCandidate) -> dict[str, Any] | None:
        surface_key = self.normalizer.normalized_entity_key(mention.surface)
        if not surface_key:
            return None
        if self._should_force_non_character(mention.surface):
            return None
        if mention.expected_type and mention.expected_type != "character":
            return None
        exact_matches: list[dict[str, Any]] = []
        surname_matches: list[dict[str, Any]] = []
        for row in bundle.known_characters:
            display_name = str(row["display_name"]).strip()
            surfaces = [display_name, *(row.get("aliases") or [])]
            normalized_surfaces = {self.normalizer.normalized_entity_key(item) for item in surfaces if str(item).strip()}
            if surface_key in normalized_surfaces:
                exact_matches.append(row)
                continue
            last_token = self.normalizer.normalized_entity_key(display_name.split()[-1]) if display_name.split() else ""
            if last_token and surface_key == last_token:
                surname_matches.append(row)
        if len(exact_matches) == 1:
            row = exact_matches[0]
            canonical_name = self._best_seeded_character_name(row)
            return {
                "canonical_name": canonical_name,
                "entity_type": "character",
                "aliases": [mention.surface],
                "entity_context": "",
                "evidence": self._mention_evidence_summary(mention),
            }
        if len(surname_matches) == 1:
            row = surname_matches[0]
            canonical_name = self._best_seeded_character_name(row)
            return {
                "canonical_name": canonical_name,
                "entity_type": "character",
                "aliases": [mention.surface],
                "entity_context": "",
                "evidence": self._mention_evidence_summary(mention),
            }
        candidates = exact_matches or surname_matches
        if not candidates:
            return None
        choice = self._resolve_ambiguous_character_candidate(bundle=bundle, mention=mention, candidates=candidates)
        if not choice:
            return None
        return {
            "canonical_name": choice["selected_display_name"],
            "entity_type": "character",
            "aliases": [mention.surface, *(choice.get("aliases") or [])],
            "entity_context": "",
            "evidence": self._mention_evidence_summary(mention),
        }

    def _resolve_against_existing_entities(self, bundle: ChapterEntityBundle, mention: MentionCandidate) -> dict[str, Any] | None:
        surface_key = self.normalizer.normalized_entity_key(mention.surface)
        if not surface_key:
            return None
        for row in bundle.existing_entities:
            name = str(row.get("name") or "").strip()
            entity_type = str(row.get("entity_type") or "other").strip().lower() or "other"
            if mention.expected_type and entity_type != mention.expected_type:
                continue
            surfaces = [name, *(row.get("aliases") or [])]
            normalized_surfaces = {self.normalizer.normalized_entity_key(item) for item in surfaces if str(item).strip()}
            if surface_key in normalized_surfaces:
                return {
                    "canonical_name": name,
                    "entity_type": entity_type,
                    "aliases": [mention.surface] if mention.surface.lower() != name.lower() else [],
                    "entity_context": "",
                    "evidence": self._mention_evidence_summary(mention),
                }
        return None

    def _resolve_ambiguous_character_candidate(
        self,
        *,
        bundle: ChapterEntityBundle,
        mention: MentionCandidate,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        prompt = f"""
Resolve this character mention to one seeded identity character if the evidence supports a specific match.

Mention:
{mention.surface}

Evidence:
{json.dumps(mention.evidence_rows[:8], ensure_ascii=False)}

Origin scene context:
{json.dumps(self._mention_scene_context(bundle, mention), ensure_ascii=False)}

Candidates:
{json.dumps([{'display_name': row['display_name'], 'aliases': list(row.get('aliases') or [])} for row in candidates], ensure_ascii=False)}

Return JSON only:
{{
  "selected_display_name": "exact candidate display name or empty string if not resolvable",
  "aliases": ["grounded alias forms used in this chapter"]
}}
"""
        response = self._run_llm_with_retries(bundle=bundle, prompt=prompt, validator=self._validate_character_resolution_response)
        selected = str(response.get("selected_display_name") or "").strip()
        if not selected:
            return None
        return {"selected_display_name": selected, "aliases": list(response.get("aliases") or [])}

    def _classify_unresolved_mention(self, bundle: ChapterEntityBundle, mention: MentionCandidate) -> dict[str, Any] | None:
        forced_type = self._forced_entity_type(mention.surface)
        if forced_type:
            return {
                "should_create": True,
                "canonical_name": self._clean_non_character_name(mention.surface),
                "entity_type": forced_type,
                "aliases": [],
                "entity_context": self._mention_evidence_summary(mention),
                "evidence": self._mention_evidence_summary(mention),
            }
        if self._should_drop_generic_fragment(mention.surface):
            return None
        prompt = f"""
Classify this unresolved narrative entity mention using origin-chapter evidence.

Rules:
- character = a specific human or person-like individual with agency in the story.
- creature = a non-human living being, monster, beast, magical animal, or sentient non-human being.
- location = a place, address, building, room, street, area, region, settlement, or named physical setting.
- object = a physical thing, artifact, tool, weapon, document, vehicle, or carried item.
- organization = a named group, institution, household, faction, school as institution, or formal collective body.
- other = only use if none of the above fit clearly.
- Prefer location/object/organization/creature when appropriate.
- Do not classify as character unless the evidence clearly indicates a specific person or person-like individual.
- Address-like names, streets, buildings, rooms, schools, and settlements are locations, not characters.
- Household names, staff groups, teams, and institutions are organizations, not characters.
- If the mention is only a surname or partial family label and cannot be safely mapped to a specific seeded character, do not invent a new character.
- If the mention is just noise or a fragment, set should_create to false.
- If creating an entity, choose the clean canonical name.
- Use the origin event evidence first.
- Use the origin scene context second.
- Use chapter fallback only if the event and scene are not enough.

Mention:
{mention.surface}

Expected type hint:
{mention.expected_type or "none"}

Evidence:
{json.dumps(mention.evidence_rows[:8], ensure_ascii=False)}

Origin scene context:
{json.dumps(self._mention_scene_context(bundle, mention), ensure_ascii=False)}

Chapter fallback excerpt:
{self._chapter_fallback_excerpt(bundle, mention)}

Return JSON only:
{{
  "should_create": true,
  "canonical_name": "clean canonical entity name",
  "entity_type": "location",
  "aliases": ["grounded alternate forms"],
  "entity_context": "short concrete description",
  "evidence": "short evidence summary"
}}
"""
        response = self._run_llm_with_retries(bundle=bundle, prompt=prompt, validator=self._validate_classification_response)
        if not bool(response.get("should_create")):
            return None
        return response

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

    def _forced_entity_type(self, surface: str) -> str:
        lowered = self.normalizer.normalized_entity_key(surface)
        if not lowered:
            return ""
        if lowered in self.LOCATION_FORCE_NAMES:
            return "location"
        raw_tokens = {token.strip(" ,.;:!?()[]{}\"'").lower() for token in str(surface or "").split() if token.strip(" ,.;:!?()[]{}\"'")}
        tokens = raw_tokens or set(lowered.split())
        if tokens & self.LOCATION_FORCE_TOKENS:
            return "location"
        if tokens & self.ORGANIZATION_HINT_TOKENS:
            return "organization"
        return ""

    def _should_force_non_character(self, surface: str) -> bool:
        return bool(self._forced_entity_type(surface))

    def _should_drop_generic_fragment(self, surface: str) -> bool:
        lowered = self.normalizer.normalized_entity_key(surface)
        if not lowered:
            return True
        if lowered in self.GENERIC_NON_ENTITY_TOKENS:
            return True
        raw_tokens = [token.strip(" ,.;:!?()[]{}\"'").lower() for token in str(surface or "").split() if token.strip(" ,.;:!?()[]{}\"'")]
        return len(raw_tokens) == 1 and raw_tokens[0] in self.LOCATION_FORCE_TOKENS

    def _clean_non_character_name(self, surface: str) -> str:
        value = " ".join(str(surface or "").strip().split())
        if not value:
            return ""
        return " ".join(token[:1].upper() + token[1:] if token else token for token in value.split())

    def _mention_evidence_summary(self, mention: MentionCandidate) -> str:
        parts = []
        for row in mention.evidence_rows[:4]:
            for key in ("description", "reason", "outcome"):
                value = str(row.get(key) or "").strip()
                if value and value not in parts:
                    parts.append(value)
        return " | ".join(parts[:3])

    def _mention_scene_context(self, bundle: ChapterEntityBundle, mention: MentionCandidate) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for scene_index in mention.scene_indices[:3]:
            scene = bundle.scene_map.get(int(scene_index))
            if not scene:
                continue
            payload.append(
                {
                    "scene_index": scene_index,
                    "summary": str(scene.get("summary") or "").strip(),
                    "text_excerpt": self._trim_text(str(scene.get("text") or "").strip(), max_chars=900),
                }
            )
        return payload

    def _chapter_fallback_excerpt(self, bundle: ChapterEntityBundle, mention: MentionCandidate) -> str:
        text = str(bundle.scene_text or "").strip()
        if not text:
            return ""
        surface = str(mention.surface or "").strip()
        lowered_text = text.lower()
        lowered_surface = surface.lower()
        position = lowered_text.find(lowered_surface) if lowered_surface else -1
        if position < 0:
            return self._trim_text(text, max_chars=700)
        start = max(0, position - 250)
        end = min(len(text), position + len(surface) + 450)
        return self._trim_text(text[start:end].strip(), max_chars=700)

    def _trim_text(self, text: str, *, max_chars: int) -> str:
        value = str(text or "").strip()
        if len(value) <= max_chars:
            return value
        return value[: max_chars - 3].rstrip() + "..."

    def _persist_entities(self, *, bundle: ChapterEntityBundle, normalized: dict[str, Any]) -> dict[str, int]:
        inserted_count = 0
        updated_count = 0
        with self.sqlite_store.session_factory() as session:
            for row in normalized.get("entities") or []:
                existing = session.execute(
                    select(Entity).where(
                        Entity.book_id == bundle.book_id,
                        Entity.canonical_name == str(row["name"]),
                        Entity.entity_type == str(row["entity_type"]),
                    )
                ).scalar_one_or_none()
                if existing is None:
                    existing = Entity(
                        book_id=bundle.book_id,
                        canonical_name=str(row["name"]),
                        entity_type=str(row["entity_type"]),
                        mention_count=1,
                        first_seen_book_index=1,
                        first_seen_chapter_index=bundle.chapter_index,
                        first_seen_scene_index=1,
                        entity_context=str(row.get("entity_context") or "").strip() or None,
                        metadata_json={
                            "aliases": list(row.get("aliases") or []),
                            "evidence": str(row.get("evidence") or "").strip(),
                            "source_scene_count": bundle.scene_count,
                            "agent_metadata": {"source": self.VERSION},
                        },
                    )
                    session.add(existing)
                    inserted_count += 1
                    continue
                existing.mention_count = int(existing.mention_count or 0) + 1
                if not str(existing.entity_context or "").strip():
                    existing.entity_context = str(row.get("entity_context") or "").strip() or existing.entity_context
                metadata = dict(existing.metadata_json or {})
                merged_aliases = list(metadata.get("aliases") or [])
                for alias in row.get("aliases") or []:
                    if alias not in merged_aliases:
                        merged_aliases.append(alias)
                metadata["aliases"] = merged_aliases
                if str(row.get("evidence") or "").strip():
                    evidence_rows = list(metadata.get("evidence_rows") or [])
                    evidence_rows.append(
                        {
                            "chapter_index": bundle.chapter_index,
                            "evidence": str(row.get("evidence") or "").strip(),
                        }
                    )
                    metadata["evidence_rows"] = evidence_rows[:20]
                    metadata["evidence"] = evidence_rows[-1]["evidence"]
                metadata["source_scene_count"] = bundle.scene_count
                metadata["agent_metadata"] = {"source": self.VERSION}
                existing.metadata_json = metadata
                updated_count += 1
            session.commit()
            self._suppress_cross_typed_character_conflicts(session=session, book_id=bundle.book_id)
            self._reconcile_chapter_event_characters(session=session, bundle=bundle)
            session.commit()
        return {"inserted_count": inserted_count, "updated_count": updated_count}

    def _suppress_cross_typed_character_conflicts(self, *, session, book_id: str) -> None:
        rows = session.execute(
            select(Entity).where(Entity.book_id == book_id).order_by(Entity.canonical_name.asc(), Entity.entity_type.asc())
        ).scalars().all()
        character_alias_keys: dict[str, set[str]] = {}
        for row in rows:
            if str(row.entity_type or "").strip().lower() != "character":
                continue
            canonical_name = str(row.canonical_name or "").strip()
            if not canonical_name:
                continue
            keys: set[str] = set()
            for surface in [canonical_name, *(dict(row.metadata_json or {}).get("aliases") or [])]:
                key = self.normalizer.normalized_entity_key(str(surface or "").strip())
                if key:
                    keys.add(key)
            if keys:
                character_alias_keys[canonical_name] = keys
        for row in rows:
            if str(row.entity_type or "").strip().lower() == "character":
                continue
            row_keys: set[str] = set()
            for surface in [str(row.canonical_name or "").strip(), *(dict(row.metadata_json or {}).get("aliases") or [])]:
                key = self.normalizer.normalized_entity_key(str(surface or "").strip())
                if key:
                    row_keys.add(key)
            if not row_keys:
                continue
            for keys in character_alias_keys.values():
                if row_keys & keys:
                    session.delete(row)
                    break

    def _reconcile_chapter_event_characters(self, *, session, bundle: ChapterEntityBundle) -> None:
        entity_rows = session.execute(
            select(Entity).where(Entity.book_id == bundle.book_id).order_by(Entity.entity_type.asc(), Entity.canonical_name.asc())
        ).scalars().all()
        existing_entities = [
            {
                "name": str(row.canonical_name or "").strip(),
                "entity_type": str(row.entity_type or "").strip().lower(),
                "aliases": list((row.metadata_json or {}).get("aliases") or []),
            }
            for row in entity_rows
            if str(row.canonical_name or "").strip()
        ]
        known_characters, alias_map = self._load_identity_seed(
            session=session,
            series_id=bundle.series_id,
            existing_entities=existing_entities,
        )
        context = self.normalizer.build_context(
            entity_registry=existing_entities,
            alias_map=alias_map,
        )
        canonical_character_names: dict[str, str] = {}
        for row in known_characters:
            best_name = self._best_seeded_character_name(row)
            surfaces = [str(row.get("display_name") or "").strip(), *(row.get("aliases") or [])]
            for surface in surfaces:
                key = self.normalizer.normalized_entity_key(surface)
                if key:
                    canonical_character_names[key] = best_name
        known_names = {str(row["name"]).lower(): row for row in existing_entities}
        identity_rows_by_name = {self._best_seeded_character_name(row): row for row in known_characters}
        canonical_character_by_alias: dict[str, str] = {}
        for canonical_name, seed_row in identity_rows_by_name.items():
            for surface in [canonical_name, str(seed_row.get("display_name") or "").strip(), *(seed_row.get("aliases") or [])]:
                key = self.normalizer.normalized_entity_key(surface)
                if key:
                    canonical_character_by_alias[key] = canonical_name
        non_character_keys = {
            self.normalizer.normalized_entity_key(str(row["name"]))
            for row in existing_entities
            if str(row.get("entity_type") or "").strip().lower() != "character"
        }
        rows = session.execute(
            select(Event).where(Event.book_id == bundle.book_id, Event.chapter_index == bundle.chapter_index).order_by(Event.scene_index.asc(), Event.created_at.asc())
        ).scalars().all()
        for row in rows:
            payload = dict(row.payload_json or {})
            description = str(payload.get("description") or row.description or "").strip()
            reason = str(payload.get("reason") or row.reason or "").strip()
            outcome = str(payload.get("outcome") or row.outcome or "").strip()
            deterministic_characters = self._extract_seeded_characters_from_event_text(
                known_characters=known_characters,
                text_parts=[description, reason, outcome],
            )
            raw_characters = [str(item).strip() for item in (payload.get("characters") or []) if str(item).strip()]
            normalized_characters: list[str] = []
            for item in [*deterministic_characters, *raw_characters]:
                item_key = self.normalizer.normalized_entity_key(item)
                canonical_seed_name = canonical_character_by_alias.get(item_key or "")
                if item_key in non_character_keys and not canonical_seed_name:
                    continue
                if canonical_seed_name:
                    resolved = canonical_seed_name
                    resolved_key = self.normalizer.normalized_entity_key(resolved)
                    is_seeded_character = True
                    is_existing_character = (
                        resolved.lower() in known_names
                        and str(known_names[resolved.lower()].get("entity_type") or "").strip().lower() == "character"
                    )
                else:
                    resolved = self.normalizer.resolve_name(item, context=context, expect_character=True) or self.normalizer.canonicalize_candidate_name(item) or item
                    resolved_key = self.normalizer.normalized_entity_key(resolved)
                    is_seeded_character = resolved_key in canonical_character_names
                    is_existing_character = (
                        resolved.lower() in known_names
                        and str(known_names[resolved.lower()].get("entity_type") or "").strip().lower() == "character"
                    )
                if resolved_key in non_character_keys and not is_seeded_character:
                    continue
                if is_seeded_character:
                    resolved = canonical_character_names[resolved_key]
                if (
                    resolved.lower() in known_names
                    and str(known_names[resolved.lower()].get("entity_type") or "").strip().lower() != "character"
                    and not is_seeded_character
                ):
                    continue
                if not is_seeded_character and not is_existing_character:
                    continue
                if resolved and resolved not in normalized_characters:
                    normalized_characters.append(resolved)
            payload["characters"] = normalized_characters
            self._upsert_reconciled_character_entities(
                session=session,
                book_id=bundle.book_id,
                chapter_index=bundle.chapter_index,
                character_names=normalized_characters,
                identity_rows_by_name=identity_rows_by_name,
            )
            rebuilt_entities: list[str] = []
            for field in (
                payload.get("characters") or [],
                payload.get("creatures_involved") or [],
                payload.get("objects_involved") or [],
                payload.get("locations_involved") or [],
                payload.get("organizations_involved") or [],
                payload.get("entities_involved") or [],
            ):
                for item in field:
                    value = str(item or "").strip()
                    if value and value not in rebuilt_entities:
                        rebuilt_entities.append(value)
            payload["entities_involved"] = rebuilt_entities
            row.entities_involved = rebuilt_entities
            row.payload_json = payload
        session.commit()

    def _upsert_reconciled_character_entities(
        self,
        *,
        session,
        book_id: str,
        chapter_index: int,
        character_names: list[str],
        identity_rows_by_name: dict[str, dict[str, Any]],
    ) -> None:
        if not character_names:
            return
        deduped_character_names: list[str] = []
        seen_character_names: set[str] = set()
        for value in character_names:
            key = str(value or "").strip().lower()
            if not key or key in seen_character_names:
                continue
            seen_character_names.add(key)
            deduped_character_names.append(str(value).strip())
        existing_rows = session.execute(
            select(Entity).where(Entity.book_id == book_id).order_by(Entity.entity_type.asc(), Entity.canonical_name.asc())
        ).scalars().all()
        existing_by_name = {str(row.canonical_name or "").strip().lower(): row for row in existing_rows}
        alias_to_character: dict[str, str] = {}
        for canonical_name, seed_row in identity_rows_by_name.items():
            surfaces = [canonical_name, str(seed_row.get("display_name") or "").strip(), *(seed_row.get("aliases") or [])]
            for surface in surfaces:
                key = self.normalizer.normalized_entity_key(surface)
                if key:
                    alias_to_character[key] = canonical_name
        for canonical_name in deduped_character_names:
            existing = existing_by_name.get(canonical_name.lower())
            seed_row = identity_rows_by_name.get(canonical_name, {})
            aliases = []
            for alias in [str(seed_row.get("display_name") or "").strip(), *(seed_row.get("aliases") or [])]:
                value = str(alias or "").strip()
                if value and value.lower() != canonical_name.lower() and value not in aliases:
                    aliases.append(value)
            if existing is None:
                existing = Entity(
                    book_id=book_id,
                    canonical_name=canonical_name,
                    entity_type="character",
                    mention_count=1,
                    first_seen_book_index=1,
                    first_seen_chapter_index=chapter_index,
                    first_seen_scene_index=1,
                    entity_context=None,
                    metadata_json={
                        "aliases": aliases,
                        "agent_metadata": {"source": f"{self.VERSION}:reconciled_character_backfill"},
                    },
                )
                session.add(existing)
                existing_by_name[canonical_name.lower()] = existing
                session.flush()
                continue
            if str(existing.entity_type or "").strip().lower() != "character":
                existing.entity_type = "character"
            metadata = dict(existing.metadata_json or {})
            merged_aliases = list(metadata.get("aliases") or [])
            for alias in aliases:
                if alias not in merged_aliases:
                    merged_aliases.append(alias)
            metadata["aliases"] = merged_aliases
            metadata["agent_metadata"] = {"source": f"{self.VERSION}:reconciled_character_backfill"}
            existing.metadata_json = metadata
        refreshed_rows = session.execute(
            select(Entity).where(Entity.book_id == book_id).order_by(Entity.entity_type.asc(), Entity.canonical_name.asc())
        ).scalars().all()
        selected_alias_keys: dict[str, set[str]] = {}
        for canonical_name in deduped_character_names:
            seed_row = identity_rows_by_name.get(canonical_name, {})
            keys: set[str] = set()
            for surface in [canonical_name, str(seed_row.get("display_name") or "").strip(), *(seed_row.get("aliases") or [])]:
                key = self.normalizer.normalized_entity_key(str(surface or "").strip())
                if key:
                    keys.add(key)
            if keys:
                selected_alias_keys[canonical_name] = keys
        for row in refreshed_rows:
            entity_type = str(row.entity_type or "").strip().lower()
            if entity_type == "character":
                continue
            row_keys: set[str] = set()
            for surface in [str(row.canonical_name or "").strip(), *(dict(row.metadata_json or {}).get("aliases") or [])]:
                key = self.normalizer.normalized_entity_key(str(surface or "").strip())
                if key:
                    row_keys.add(key)
            if not row_keys or self._should_force_non_character(str(row.canonical_name or "").strip()):
                continue
            for canonical_character, keys in selected_alias_keys.items():
                if canonical_character in deduped_character_names and row_keys & keys:
                    session.delete(row)
                    break

    def _extract_seeded_characters_from_event_text(self, *, known_characters: list[dict[str, Any]], text_parts: list[str]) -> list[str]:
        combined_text = " ".join(str(part or "").strip() for part in text_parts if str(part or "").strip())
        normalized_text = self._normalize_search_text(combined_text)
        if not normalized_text:
            return []
        padded_text = f" {normalized_text} "
        matches: list[tuple[int, str]] = []
        for row in known_characters:
            canonical_name = self._best_seeded_character_name(row)
            candidate_surfaces = [canonical_name, str(row.get("display_name") or "").strip(), *(row.get("aliases") or [])]
            surface_forms = sorted({self._normalize_search_text(item) for item in candidate_surfaces if self._normalize_search_text(item)}, key=len, reverse=True)
            for surface in surface_forms:
                if f" {surface} " in padded_text:
                    matches.append((len(surface), canonical_name))
                    break
        deduped: list[str] = []
        seen: set[str] = set()
        for _, canonical_name in sorted(matches, key=lambda item: (-item[0], item[1].lower())):
            key = canonical_name.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(canonical_name)
        return deduped

    def _normalize_search_text(self, value: str) -> str:
        import re
        cleaned = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
        return " ".join(cleaned.split())
