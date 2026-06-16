from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from core.canon_normalization import CanonicalEntityNormalizer
from core.trait_taxonomy import practical_persistent_fields
from infrastructure.llm_client import LLMClient
from sql_store.models import Book, CharacterProfile, CharacterVisualBaseline, Entity, Event, Scene
from sql_store.persistence import SagaSQLiteStore


LOGGER = logging.getLogger(__name__)

UNKNOWN_TEXT = "not_explicitly_stated_in_text"
UNKNOWN_LIST_ITEM = "not_explicitly_stated_in_text"


@dataclass
class CharacterEvidenceBundle:
    book_id: str
    series_id: str
    book_title: str
    entity_id: str | None
    character_name: str
    aliases: list[str]
    entity_context: str
    scenes: list[dict[str, Any]]
    events: list[dict[str, Any]]


class DatabaseCharacterProfileAgent:
    VERSION = "db_character_profile_agent_v1"
    CONFIDENCE_VALUES = {"high", "medium", "low"}
    MAX_SCENES_PER_CHARACTER = 8
    MAX_EVENTS_PER_CHARACTER = 12
    MAX_SCENE_CHARS = 900

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        sqlite_store: SagaSQLiteStore | None = None,
        max_attempts: int = 3,
        retry_delay_seconds: float = 1.5,
    ) -> None:
        self.sqlite_store = sqlite_store or SagaSQLiteStore()
        self.llm = llm_client or LLMClient(
            mode=LLMClient.MODE_GPT_OSS,
            allow_account_rotation=True,
            allow_cross_provider_fallback=False,
        )
        self.max_attempts = max(1, int(max_attempts))
        self.retry_delay_seconds = max(0.0, float(retry_delay_seconds))
        self.normalizer = CanonicalEntityNormalizer()
        self.character_trait_fields = practical_persistent_fields("character")

    def analyze_book(
        self,
        *,
        book_ref: str,
        limit_characters: int | None = None,
        character_names: list[str] | None = None,
    ) -> dict[str, Any]:
        book_id = self._resolve_book_id(book_ref)
        roster = self._load_character_roster(book_id=book_id, character_names=character_names)
        if limit_characters is not None:
            roster = roster[: max(0, int(limit_characters))]
        LOGGER.info(
            "DB character profile agent start | book=%s roster=%s",
            book_id,
            len(roster),
        )
        results: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for row in roster:
            bundle = self._build_character_bundle(book_id=book_id, roster_row=row)
            if not bundle.scenes and not bundle.events and not bundle.entity_context:
                skipped.append({"character_name": bundle.character_name, "reason": "no_evidence"})
                continue
            profile = self._profile_character(bundle)
            self._persist_character_profile(bundle=bundle, profile=profile)
            results.append(
                {
                    "character_name": bundle.character_name,
                    "confidence": profile.get("confidence", ""),
                    "scene_count": len(bundle.scenes),
                    "event_count": len(bundle.events),
                }
            )
        LOGGER.info(
            "DB character profile agent complete | book=%s persisted=%s skipped=%s",
            book_id,
            len(results),
            len(skipped),
        )
        return {
            "book_id": book_id,
            "persisted_profiles": len(results),
            "results": results,
            "skipped": skipped,
            "agent_version": self.VERSION,
        }

    def _resolve_book_id(self, book_ref: str) -> str:
        value = str(book_ref or "").strip()
        if value.startswith("db://book/"):
            return value.split("db://book/", 1)[-1].strip()
        return value

    def _load_character_roster(self, *, book_id: str, character_names: list[str] | None) -> list[dict[str, Any]]:
        requested = {str(name).strip().lower() for name in (character_names or []) if str(name).strip()}
        with self.sqlite_store.session_factory() as session:
            rows = session.execute(
                select(Entity).where(Entity.book_id == book_id, Entity.entity_type == "character").order_by(Entity.mention_count.desc(), Entity.canonical_name.asc())
            ).scalars().all()
            roster: list[dict[str, Any]] = []
            for row in rows:
                canonical_name = str(row.canonical_name or "").strip()
                if not canonical_name:
                    continue
                if requested and canonical_name.lower() not in requested:
                    continue
                metadata = dict(row.metadata_json or {})
                aliases = [str(item).strip() for item in metadata.get("aliases") or [] if str(item).strip()]
                roster.append(
                    {
                        "entity_id": row.id,
                        "character_name": canonical_name,
                        "aliases": aliases,
                        "entity_context": str(row.entity_context or "").strip(),
                    }
                )
            return roster

    def _build_character_bundle(self, *, book_id: str, roster_row: dict[str, Any]) -> CharacterEvidenceBundle:
        with self.sqlite_store.session_factory() as session:
            book = session.get(Book, book_id)
            character_name = str(roster_row.get("character_name") or "").strip()
            aliases = [character_name, *[str(item).strip() for item in roster_row.get("aliases") or [] if str(item).strip()]]
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
                            "excerpt": excerpt,
                        }
                    )
                if len(scenes) >= self.MAX_SCENES_PER_CHARACTER:
                    break
            events: list[dict[str, Any]] = []
            for event in session.execute(
                select(Event).where(Event.book_id == book_id).order_by(Event.chapter_index.asc(), Event.scene_index.asc(), Event.created_at.asc())
            ).scalars():
                payload = dict(event.payload_json or {})
                raw_names = [
                    *[str(item).strip() for item in payload.get("characters") or [] if str(item).strip()],
                    *[str(item).strip() for item in (event.entities_involved or []) if str(item).strip()],
                ]
                raw_keys = {self._normalize_text(item) for item in raw_names if self._normalize_text(item)}
                if not alias_keys & raw_keys:
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
                if len(events) >= self.MAX_EVENTS_PER_CHARACTER:
                    break
            return CharacterEvidenceBundle(
                book_id=book_id,
                series_id=str(book.series_id or "").strip() if book else "",
                book_title=str(book.title or "").strip() if book else "",
                entity_id=str(roster_row.get("entity_id") or "").strip() or None,
                character_name=character_name,
                aliases=[alias for alias in aliases if alias],
                entity_context=str(roster_row.get("entity_context") or "").strip(),
                scenes=scenes,
                events=events,
            )

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
        start = max(0, best_start - 220)
        end = min(len(source), best_start + best_len + 420)
        excerpt = source[start:end].strip()
        if len(excerpt) > self.MAX_SCENE_CHARS:
            excerpt = excerpt[: self.MAX_SCENE_CHARS].rstrip() + "..."
        return excerpt

    def _profile_character(self, bundle: CharacterEvidenceBundle) -> dict[str, Any]:
        prompt = self._build_prompt(bundle)
        response = self._run_llm_with_retries(prompt=prompt, character_name=bundle.character_name)
        return self._normalize_profile_response(bundle=bundle, response=response)

    def _build_prompt(self, bundle: CharacterEvidenceBundle) -> str:
        schema_traits = {field: UNKNOWN_TEXT for field in self.character_trait_fields}
        return f"""
You are the character profile extraction agent for a canon database.
Return only grounded JSON for one character using the provided book evidence.

Hard rules:
- Stay strictly grounded in the supplied evidence.
- Prefer durable whole-book character facts, not one-scene mood or staging.
- Use plain language.
- Do not invent physical traits if the evidence does not support them.
- Persistent traits should be usable later for visual prompting, but remain book-grounded.
- Temporary injuries, fear, dirt, crying, or battle state do not belong in persistent traits.
- If a field is unsupported, use exactly `{UNKNOWN_TEXT}`.
- `titles_or_roles`, `affiliations`, and `core_traits` should be short lists of concise phrases. If unsupported, return `["{UNKNOWN_LIST_ITEM}"]`.
- `profile_summary` and `personality_summary` must never be blank. If evidence is too thin, return a cautious grounded summary instead of an empty field.
- `evidence_excerpt` must never be blank.

Return JSON only:
{{
  "character_name": "{bundle.character_name}",
  "profile_summary": "{UNKNOWN_TEXT}",
  "personality_summary": "{UNKNOWN_TEXT}",
  "titles_or_roles": ["{UNKNOWN_LIST_ITEM}"],
  "affiliations": ["{UNKNOWN_LIST_ITEM}"],
  "core_traits": ["{UNKNOWN_LIST_ITEM}"],
  "persistent_traits": {json.dumps(schema_traits, ensure_ascii=False)},
  "evidence_excerpt": "{UNKNOWN_TEXT}",
  "confidence": "high|medium|low"
}}

Book:
{bundle.book_title}

Character:
{bundle.character_name}

Aliases:
{json.dumps(bundle.aliases, ensure_ascii=False)}

Existing entity context:
{bundle.entity_context or "None"}

Scene evidence:
{json.dumps(bundle.scenes, ensure_ascii=False)}

Event evidence:
{json.dumps(bundle.events, ensure_ascii=False)}
"""

    def _run_llm_with_retries(self, *, prompt: str, character_name: str) -> dict[str, Any]:
        last_error = ""
        for attempt in range(1, self.max_attempts + 1):
            LOGGER.info(
                "DB character profile agent LLM attempt start | character=%s attempt=%s/%s",
                character_name,
                attempt,
                self.max_attempts,
            )
            response = self.llm.generate_json(prompt, strict=True, validator=self._validate_response)
            if isinstance(response, dict) and "error" not in response:
                LOGGER.info(
                    "DB character profile agent LLM attempt complete | character=%s attempt=%s/%s",
                    character_name,
                    attempt,
                    self.max_attempts,
                )
                return response
            last_error = str((response or {}).get("error") or "unknown_error")
            LOGGER.warning(
                "DB character profile agent LLM attempt failed | character=%s attempt=%s/%s error=%s",
                character_name,
                attempt,
                self.max_attempts,
                last_error,
            )
            if attempt < self.max_attempts and self.retry_delay_seconds > 0:
                time.sleep(self.retry_delay_seconds)
        raise RuntimeError(
            f"DB character profile agent failed after {self.max_attempts} attempts for {character_name}: {last_error}"
        )

    def _validate_response(self, response: dict[str, Any]) -> bool:
        if not isinstance(response, dict):
            return False
        if not isinstance(response.get("titles_or_roles") or [], list):
            return False
        if not isinstance(response.get("affiliations") or [], list):
            return False
        if not isinstance(response.get("core_traits") or [], list):
            return False
        persistent_traits = response.get("persistent_traits") or {}
        if not isinstance(persistent_traits, dict):
            return False
        confidence = str(response.get("confidence") or "").strip().lower()
        return confidence in self.CONFIDENCE_VALUES

    def _normalize_profile_response(self, *, bundle: CharacterEvidenceBundle, response: dict[str, Any]) -> dict[str, Any]:
        persistent_traits = {
            field: self._fallback_text(response.get("persistent_traits", {}).get(field))
            for field in self.character_trait_fields
        }
        return {
            "character_name": bundle.character_name,
            "profile_summary": self._fallback_text(response.get("profile_summary"), fallback=self._fallback_profile_summary(bundle)),
            "personality_summary": self._fallback_text(response.get("personality_summary"), fallback=self._fallback_personality_summary(bundle)),
            "titles_or_roles": self._clean_list(response.get("titles_or_roles") or [], fallback=UNKNOWN_LIST_ITEM),
            "affiliations": self._clean_list(response.get("affiliations") or [], fallback=UNKNOWN_LIST_ITEM),
            "core_traits": self._clean_list(response.get("core_traits") or [], fallback=UNKNOWN_LIST_ITEM),
            "persistent_traits": persistent_traits,
            "evidence_excerpt": self._fallback_text(response.get("evidence_excerpt"), fallback=self._fallback_evidence_excerpt(bundle)),
            "confidence": self._clean(response.get("confidence")).lower() or "low",
            "agent_version": self.VERSION,
        }

    def _persist_character_profile(self, *, bundle: CharacterEvidenceBundle, profile: dict[str, Any]) -> None:
        with self.sqlite_store.session_factory() as session:
            existing_profile = session.execute(
                select(CharacterProfile).where(
                    CharacterProfile.book_id == bundle.book_id,
                    CharacterProfile.character_name == bundle.character_name,
                )
            ).scalar_one_or_none()
            payload = {
                "profile_summary": profile["profile_summary"],
                "personality_summary": profile["personality_summary"],
                "titles_or_roles": profile["titles_or_roles"],
                "affiliations": profile["affiliations"],
                "core_traits": profile["core_traits"],
                "persistent_traits": profile["persistent_traits"],
                "evidence_excerpt": profile["evidence_excerpt"],
                "confidence": profile["confidence"],
                "agent_version": self.VERSION,
            }
            if existing_profile is None:
                session.add(
                    CharacterProfile(
                        book_id=bundle.book_id,
                        entity_id=bundle.entity_id,
                        character_name=bundle.character_name,
                        payload_json=payload,
                    )
                )
            else:
                existing_profile.entity_id = bundle.entity_id
                existing_profile.payload_json = payload

            entity = session.get(Entity, bundle.entity_id) if bundle.entity_id else None
            if entity is not None:
                entity.initial_physical_description = {
                    "profile_summary": profile["profile_summary"],
                    "personality_summary": profile["personality_summary"],
                    "evidence_excerpt": profile["evidence_excerpt"],
                }
                entity.first_appearance_profile = {
                    "persistent_traits": profile["persistent_traits"],
                    "confidence": profile["confidence"],
                }
                entity.typed_attributes = {
                    "appearance": self._filled_list([
                        profile["persistent_traits"].get("height_impression", ""),
                        profile["persistent_traits"].get("build", ""),
                        profile["persistent_traits"].get("skin_tone_or_complexion", ""),
                        profile["persistent_traits"].get("hair_color", ""),
                        profile["persistent_traits"].get("hair_length_or_style", ""),
                        profile["persistent_traits"].get("eye_color", ""),
                        profile["persistent_traits"].get("facial_features", ""),
                        profile["persistent_traits"].get("distinguishing_marks", ""),
                        profile["persistent_traits"].get("fantasy_features", ""),
                    ]),
                    "outfit": self._filled_list([
                        profile["persistent_traits"].get("default_clothing_style", ""),
                        profile["persistent_traits"].get("default_accessories", ""),
                        profile["persistent_traits"].get("default_footwear", ""),
                    ]),
                    "titles_or_roles": self._filled_list(profile["titles_or_roles"]),
                    "affiliations": self._filled_list(profile["affiliations"]),
                }
                entity.narrative_roles = profile["titles_or_roles"]
                metadata = dict(entity.metadata_json or {})
                metadata["character_profile_agent"] = {
                    "source": self.VERSION,
                    "evidence_scene_count": len(bundle.scenes),
                    "evidence_event_count": len(bundle.events),
                }
                entity.metadata_json = metadata

            if bundle.entity_id:
                baseline = session.execute(
                    select(CharacterVisualBaseline).where(
                        CharacterVisualBaseline.book_id == bundle.book_id,
                        CharacterVisualBaseline.entity_id == bundle.entity_id,
                    )
                ).scalar_one_or_none()
                baseline_values = {
                    "gender_presentation": self._fallback_text(profile["persistent_traits"].get("gender_presentation", "")),
                    "species_or_race": self._fallback_text(profile["persistent_traits"].get("species_or_race", "")),
                    "apparent_age_group": self._fallback_text(profile["persistent_traits"].get("apparent_age_group", "")),
                    "height_impression": self._fallback_text(profile["persistent_traits"].get("height_impression", "")),
                    "build": self._fallback_text(profile["persistent_traits"].get("build", "")),
                    "skin_tone_or_complexion": self._fallback_text(profile["persistent_traits"].get("skin_tone_or_complexion", "")),
                    "hair_color": self._fallback_text(profile["persistent_traits"].get("hair_color", "")),
                    "hair_length_or_style": self._fallback_text(profile["persistent_traits"].get("hair_length_or_style", "")),
                    "eye_color": self._fallback_text(profile["persistent_traits"].get("eye_color", "")),
                    "facial_features": self._fallback_text(profile["persistent_traits"].get("facial_features", "")),
                    "distinguishing_marks": self._fallback_text(profile["persistent_traits"].get("distinguishing_marks", "")),
                    "default_clothing_style": self._fallback_text(profile["persistent_traits"].get("default_clothing_style", "")),
                    "default_accessories": self._fallback_text(profile["persistent_traits"].get("default_accessories", "")),
                    "default_footwear": self._fallback_text(profile["persistent_traits"].get("default_footwear", "")),
                    "signature_items": self._fallback_text(profile["persistent_traits"].get("signature_items", "")),
                    "fantasy_features": self._fallback_text(profile["persistent_traits"].get("fantasy_features", "")),
                    "world_genre_cues": self._fallback_text(profile["persistent_traits"].get("world_genre_cues", "")),
                    "evidence_excerpt": profile["evidence_excerpt"],
                    "source_scene_json": bundle.scenes[:4],
                }
                if baseline is None:
                    session.add(
                        CharacterVisualBaseline(
                            book_id=bundle.book_id,
                            entity_id=bundle.entity_id,
                            **baseline_values,
                        )
                    )
                else:
                    for key, value in baseline_values.items():
                        setattr(baseline, key, value)

            session.commit()

    def _fallback_evidence_excerpt(self, bundle: CharacterEvidenceBundle) -> str:
        for row in bundle.scenes:
            excerpt = self._clean(row.get("excerpt"))
            if excerpt:
                return excerpt
        for row in bundle.events:
            description = self._clean(row.get("description"))
            if description:
                return description
        return self._fallback_text(bundle.entity_context)

    def _fallback_profile_summary(self, bundle: CharacterEvidenceBundle) -> str:
        if bundle.entity_context:
            return self._clean(bundle.entity_context)
        if bundle.events:
            return self._clean(bundle.events[0].get("description"))
        if bundle.scenes:
            return f"{bundle.character_name} appears in the book with grounded but limited profile evidence."
        return UNKNOWN_TEXT

    def _fallback_personality_summary(self, bundle: CharacterEvidenceBundle) -> str:
        if bundle.events:
            bits = []
            for event in bundle.events[:3]:
                description = self._clean(event.get("description"))
                if description:
                    bits.append(description)
            if bits:
                return f"Grounded from book events: {' | '.join(bits[:2])}"
        return UNKNOWN_TEXT

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

    def _filled_list(self, values: list[Any]) -> list[str]:
        rows = [self._clean(value) for value in values if self._clean(value)]
        return rows or [UNKNOWN_LIST_ITEM]

    def _normalize_text(self, value: str) -> str:
        cleaned = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
        return " ".join(cleaned.split())
