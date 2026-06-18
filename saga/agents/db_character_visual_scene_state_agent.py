from __future__ import annotations

import ast
import json
import logging
import re
import time
from typing import Any

from sqlalchemy import select

from saga.agents.db_character_profile_agent import UNKNOWN_TEXT
from saga.providers.llm_client import LLMClient
from saga.storage.models import Book, CharacterVisualSceneState, Entity, Event, Scene
from saga.storage.persistence import SagaSQLiteStore


LOGGER = logging.getLogger(__name__)


class DatabaseCharacterVisualSceneStateAgent:
    VERSION = "db_character_visual_scene_state_agent_v2_scene_batch"
    CONFIDENCE_VALUES = {"high", "medium", "low"}
    STATE_FIELDS = [
        "scene_outfit",
        "scene_accessories",
        "scene_footwear",
        "visible_condition",
        "injuries",
        "dirt_blood_markings",
        "body_language",
        "expression",
        "carried_items",
        "temporary_effects",
    ]
    MAX_SCENE_CHARS = 2400
    MAX_EVENTS_PER_SCENE = 12
    MAX_CHARACTERS_PER_SCENE = 12
    VISUAL_CUE_KEYWORDS = [
        "wear", "wearing", "wore", "dressed", "dress", "robes", "cloak", "coat", "hat", "boots", "shoes",
        "glasses", "spectacles", "pocket", "carried", "holding", "held", "gripped", "grasped", "pulled out",
        "looked", "face", "eyes", "hair", "nose", "beard", "smile", "smiled", "grin", "grinned", "frown", "frowned",
        "tearful", "crying", "laughing", "chuckled", "angry", "afraid", "nervous", "trembling", "trembled",
        "pink", "pale", "dirty", "blood", "mud", "wound", "cut", "scar", "bruised", "awake", "asleep", "sleepy",
        "stretched", "hunched", "leaned", "collapsed", "stood", "sitting", "sat", "thumbs up", "crinkled",
    ]

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

    def analyze_book(
        self,
        *,
        book_ref: str,
        chapter_indices: list[int] | None = None,
        character_names: list[str] | None = None,
        max_scenes: int | None = None,
    ) -> dict[str, Any]:
        book_id = self._resolve_book_id(book_ref)
        requested_chapters = {int(value) for value in (chapter_indices or [])}
        requested_characters = {
            str(value).strip().lower()
            for value in (character_names or [])
            if str(value).strip()
        }
        roster = self._load_character_roster(book_id=book_id, requested_characters=requested_characters)
        scenes = self._load_scenes(book_id=book_id, requested_chapters=requested_chapters)
        if max_scenes is not None:
            scenes = scenes[: max(0, int(max_scenes))]
        LOGGER.info(
            "DB character visual scene-state agent start | book=%s roster=%s scenes=%s",
            book_id,
            len(roster),
            len(scenes),
        )
        results: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        persisted_count = 0
        for scene_row in scenes:
            scene_bundle = self._build_scene_bundle(roster=roster, scene_row=scene_row)
            if not scene_bundle["characters"]:
                skipped.append(
                    {
                        "chapter_index": scene_row["chapter_index"],
                        "scene_index": scene_row["scene_index"],
                        "reason": "no_character_matches",
                    }
                )
                continue
            scene_states = self._extract_scene_states(scene_bundle=scene_bundle)
            persisted = self._persist_scene_states(book_id=book_id, scene_bundle=scene_bundle, scene_states=scene_states)
            persisted_count += persisted
            results.append(
                {
                    "chapter_index": scene_row["chapter_index"],
                    "scene_index": scene_row["scene_index"],
                    "character_count": len(scene_states),
                    "persisted_count": persisted,
                }
            )
        LOGGER.info(
            "DB character visual scene-state agent complete | book=%s persisted=%s skipped=%s scenes=%s",
            book_id,
            persisted_count,
            len(skipped),
            len(results),
        )
        return {
            "book_id": book_id,
            "persisted_scene_states": persisted_count,
            "scene_results": results,
            "skipped": skipped,
            "agent_version": self.VERSION,
        }

    def _resolve_book_id(self, book_ref: str) -> str:
        value = str(book_ref or "").strip()
        if value.startswith("db://book/"):
            return value.split("db://book/", 1)[-1].strip()
        return value

    def _load_character_roster(self, *, book_id: str, requested_characters: set[str]) -> list[dict[str, Any]]:
        with self.sqlite_store.session_factory() as session:
            rows = session.execute(
                select(Entity)
                .where(Entity.book_id == book_id, Entity.entity_type == "character")
                .order_by(Entity.mention_count.desc(), Entity.canonical_name.asc())
            ).scalars().all()
            roster: list[dict[str, Any]] = []
            for row in rows:
                name = str(row.canonical_name or "").strip()
                if not name:
                    continue
                if requested_characters and name.lower() not in requested_characters:
                    continue
                metadata = dict(row.metadata_json or {})
                aliases = [name]
                aliases.extend(str(item).strip() for item in metadata.get("aliases") or [] if str(item).strip())
                roster.append(
                    {
                        "entity_id": row.id,
                        "character_name": name,
                        "aliases": aliases,
                        "entity_context": str(row.entity_context or "").strip(),
                    }
                )
            return roster

    def _load_scenes(self, *, book_id: str, requested_chapters: set[int]) -> list[dict[str, Any]]:
        with self.sqlite_store.session_factory() as session:
            rows = session.execute(
                select(Scene).where(Scene.book_id == book_id).order_by(Scene.chapter_index.asc(), Scene.scene_index.asc())
            ).scalars().all()
            scenes: list[dict[str, Any]] = []
            for row in rows:
                chapter_index = int(row.chapter_index or 0)
                if requested_chapters and chapter_index not in requested_chapters:
                    continue
                scenes.append(
                    {
                        "book_id": book_id,
                        "scene_id": row.id,
                        "chapter_index": chapter_index,
                        "scene_index": int(row.scene_index or 0),
                        "summary": str(row.summary or "").strip(),
                        "text": str(row.text or "").strip(),
                        "location_name": str(row.location_name or "").strip(),
                        "location_description": str(row.location_description or "").strip(),
                    }
                )
            return scenes

    def _build_scene_bundle(self, *, roster: list[dict[str, Any]], scene_row: dict[str, Any]) -> dict[str, Any]:
        scene_text = str(scene_row.get("text") or "").strip()
        candidates: list[dict[str, Any]] = []
        for roster_row in roster:
            excerpt = self._excerpt_for_aliases(scene_text, roster_row["aliases"])
            if not excerpt or not self._excerpt_has_visual_cues(excerpt):
                continue
            previous_state = self._load_previous_scene_state(
                entity_id=roster_row["entity_id"],
                chapter_index=int(scene_row["chapter_index"]),
                scene_index=int(scene_row["scene_index"]),
            )
            candidates.append(
                {
                    "entity_id": roster_row["entity_id"],
                    "character_name": roster_row["character_name"],
                    "aliases": roster_row["aliases"],
                    "entity_context": roster_row["entity_context"],
                    "excerpt": excerpt,
                    "previous_scene_state": previous_state,
                }
            )
            if len(candidates) >= self.MAX_CHARACTERS_PER_SCENE:
                break
        event_rows = self._load_scene_events(scene_row=scene_row)
        return {
            "scene": {
                "scene_id": scene_row["scene_id"],
                "chapter_index": scene_row["chapter_index"],
                "scene_index": scene_row["scene_index"],
                "summary": scene_row["summary"],
                "location_name": scene_row["location_name"],
                "location_description": scene_row["location_description"],
                "text_excerpt": self._trim_scene_text(scene_text),
            },
            "characters": candidates,
            "events": event_rows,
        }

    def _load_scene_events(self, *, scene_row: dict[str, Any]) -> list[dict[str, Any]]:
        with self.sqlite_store.session_factory() as session:
            rows = session.execute(
                select(Event)
                .where(
                    Event.book_id == scene_row["book_id"],
                    Event.chapter_index == int(scene_row["chapter_index"]),
                    Event.scene_index == int(scene_row["scene_index"]),
                )
                .order_by(Event.created_at.asc())
            ).scalars().all()
            events: list[dict[str, Any]] = []
            for row in rows:
                payload = dict(row.payload_json or {})
                events.append(
                    {
                        "event_type": str(row.event_type or "").strip(),
                        "description": str(row.description or "").strip(),
                        "reason": str(row.reason or "").strip(),
                        "outcome": str(row.outcome or "").strip(),
                        "characters": payload.get("characters") or [],
                        "objects_involved": payload.get("objects_involved") or [],
                        "creatures_involved": payload.get("creatures_involved") or [],
                    }
                )
                if len(events) >= self.MAX_EVENTS_PER_SCENE:
                    break
            return events

    def _extract_scene_states(self, *, scene_bundle: dict[str, Any]) -> list[dict[str, Any]]:
        prompt = self._build_prompt(scene_bundle=scene_bundle)
        response = self._run_llm_with_retries(prompt=prompt, scene=scene_bundle["scene"])
        return self._normalize_response(response=response, scene_bundle=scene_bundle)

    def _build_prompt(self, *, scene_bundle: dict[str, Any]) -> str:
        schema = {field: UNKNOWN_TEXT for field in self.STATE_FIELDS}
        return f"""
You are the character visual scene-state extraction agent for a canon database.
Return only grounded JSON for the relevant characters in one scene.

Mission:
- For each listed character, extract temporary scene-specific visual state only.
- Do not repeat persistent baseline traits unless they are visibly active in this scene.
- Treat this as a focused character-state pass similar to narrative analysis: capture the character's current presentation in this scene and any explicit changes from their previously known state.
- Richer results are good, but only when grounded in the scene text.
- Use exact sentinel `{UNKNOWN_TEXT}` for any unsupported field.
- Never leave any field blank.
- Do not invent injuries, props, clothing, expressions, or effects.
- Only return characters for whom the scene text itself provides direct visual evidence.
- Event rows are supplementary context only. They must not be used as the sole basis for returning a character.
- `evidence_excerpt` must quote or paraphrase a scene-text span, not an event summary.
- If the scene shows a current outfit, condition, posture, expression, carried item, magical effect, mud, blood, tears, fatigue, or other visible presentation detail, capture it.
- If the scene clearly changes the character from the previous known state, reflect the new current state in the fields.

Return JSON only:
{{
  "scene_states": [
    {{
      "character_name": "name from candidate list",
      "scene_state": {json.dumps(schema, ensure_ascii=False)},
      "evidence_excerpt": "{UNKNOWN_TEXT}",
      "confidence": "high|medium|low"
    }}
  ]
}}

Scene:
{json.dumps(scene_bundle["scene"], ensure_ascii=False)}

Candidate characters:
{json.dumps(scene_bundle["characters"], ensure_ascii=False)}

Scene events:
{json.dumps(scene_bundle["events"], ensure_ascii=False)}
"""

    def _run_llm_with_retries(self, *, prompt: str, scene: dict[str, Any]) -> dict[str, Any]:
        last_error = ""
        for attempt in range(1, self.max_attempts + 1):
            LOGGER.info(
                "DB character visual scene-state LLM attempt start | chapter=%s scene=%s attempt=%s/%s candidates=%s",
                scene.get("chapter_index"),
                scene.get("scene_index"),
                attempt,
                self.max_attempts,
                len(scene.get("characters") or []) if isinstance(scene, dict) else 0,
            )
            response = self.llm.generate_json(prompt, strict=True, validator=self._validate_response)
            if isinstance(response, dict) and "error" not in response:
                LOGGER.info(
                    "DB character visual scene-state LLM attempt complete | chapter=%s scene=%s attempt=%s/%s",
                    scene.get("chapter_index"),
                    scene.get("scene_index"),
                    attempt,
                    self.max_attempts,
                )
                return response
            last_error = str((response or {}).get("error") or "unknown_error")
            LOGGER.warning(
                "DB character visual scene-state LLM attempt failed | chapter=%s scene=%s attempt=%s/%s error=%s",
                scene.get("chapter_index"),
                scene.get("scene_index"),
                attempt,
                self.max_attempts,
                last_error,
            )
            if attempt < self.max_attempts and self.retry_delay_seconds > 0:
                time.sleep(self.retry_delay_seconds)
        raise RuntimeError(
            f"DB character visual scene-state agent failed after {self.max_attempts} attempts "
            f"for scene {scene.get('chapter_index')}:{scene.get('scene_index')}: {last_error}"
        )

    def _validate_response(self, response: dict[str, Any]) -> bool:
        if not isinstance(response, dict):
            return False
        rows = response.get("scene_states") or []
        if not isinstance(rows, list):
            return False
        for row in rows:
            if not isinstance(row, dict):
                return False
            state = row.get("scene_state") or {}
            if not isinstance(state, dict):
                return False
            confidence = str(row.get("confidence") or "").strip().lower()
            if confidence not in self.CONFIDENCE_VALUES:
                return False
        return True

    def _normalize_response(self, *, response: dict[str, Any], scene_bundle: dict[str, Any]) -> list[dict[str, Any]]:
        candidate_map = {
            str(row["character_name"]).strip().lower(): row
            for row in scene_bundle["characters"]
        }
        scene_text = self._clean(scene_bundle["scene"].get("text_excerpt"))
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in response.get("scene_states") or []:
            name = self._clean(row.get("character_name"))
            lowered = name.lower()
            if not name or lowered not in candidate_map or lowered in seen:
                continue
            seen.add(lowered)
            raw_state = row.get("scene_state") or {}
            state = {
                field: self._normalize_state_value(raw_state.get(field))
                for field in self.STATE_FIELDS
            }
            evidence_excerpt = self._fallback_text(
                row.get("evidence_excerpt"),
                fallback=candidate_map[lowered]["excerpt"],
            )
            if not self._is_scene_grounded_excerpt(evidence_excerpt=evidence_excerpt, candidate_excerpt=candidate_map[lowered]["excerpt"], scene_text=scene_text):
                continue
            if self._all_state_fields_unknown(state):
                continue
            normalized.append(
                {
                    "entity_id": candidate_map[lowered]["entity_id"],
                    "character_name": candidate_map[lowered]["character_name"],
                    "scene_state": state,
                    "evidence_excerpt": evidence_excerpt,
                    "confidence": self._clean(row.get("confidence")).lower() or "low",
                }
            )
        return normalized

    def _persist_scene_states(self, *, book_id: str, scene_bundle: dict[str, Any], scene_states: list[dict[str, Any]]) -> int:
        scene = scene_bundle["scene"]
        with self.sqlite_store.session_factory() as session:
            for row in scene_states:
                existing = session.execute(
                    select(CharacterVisualSceneState).where(
                        CharacterVisualSceneState.book_id == book_id,
                        CharacterVisualSceneState.entity_id == row["entity_id"],
                        CharacterVisualSceneState.scene_id == scene["scene_id"],
                    )
                ).scalar_one_or_none()
                payload = dict(row["scene_state"])
                source_scene_json = {
                    "scene_id": scene["scene_id"],
                    "chapter_index": scene["chapter_index"],
                    "scene_index": scene["scene_index"],
                    "summary": scene.get("summary"),
                    "location_name": scene.get("location_name"),
                    "excerpt": row["evidence_excerpt"],
                    "confidence": row["confidence"],
                    "agent_version": self.VERSION,
                }
                if existing is None:
                    session.add(
                        CharacterVisualSceneState(
                            book_id=book_id,
                            entity_id=row["entity_id"],
                            scene_id=scene["scene_id"],
                            chapter_index=scene["chapter_index"],
                            scene_index=scene["scene_index"],
                            scene_outfit=payload["scene_outfit"],
                            scene_accessories=payload["scene_accessories"],
                            scene_footwear=payload["scene_footwear"],
                            visible_condition=payload["visible_condition"],
                            injuries=payload["injuries"],
                            dirt_blood_markings=payload["dirt_blood_markings"],
                            body_language=payload["body_language"],
                            expression=payload["expression"],
                            carried_items=payload["carried_items"],
                            temporary_effects=payload["temporary_effects"],
                            source_scene_json=source_scene_json,
                        )
                    )
                else:
                    existing.chapter_index = scene["chapter_index"]
                    existing.scene_index = scene["scene_index"]
                    existing.scene_outfit = payload["scene_outfit"]
                    existing.scene_accessories = payload["scene_accessories"]
                    existing.scene_footwear = payload["scene_footwear"]
                    existing.visible_condition = payload["visible_condition"]
                    existing.injuries = payload["injuries"]
                    existing.dirt_blood_markings = payload["dirt_blood_markings"]
                    existing.body_language = payload["body_language"]
                    existing.expression = payload["expression"]
                    existing.carried_items = payload["carried_items"]
                    existing.temporary_effects = payload["temporary_effects"]
                    existing.source_scene_json = source_scene_json

                entity = session.get(Entity, row["entity_id"])
                if entity is not None:
                    change_log = list(entity.visual_change_log or [])
                    new_entry = {
                        "chapter_index": scene["chapter_index"],
                        "scene_index": scene["scene_index"],
                        "scene_id": scene["scene_id"],
                        **payload,
                        "confidence": row["confidence"],
                        "agent_version": self.VERSION,
                    }
                    change_log = [
                        entry
                        for entry in change_log
                        if not (
                            isinstance(entry, dict)
                            and int(entry.get("chapter_index") or -1) == scene["chapter_index"]
                            and int(entry.get("scene_index") or -1) == scene["scene_index"]
                        )
                    ]
                    change_log.append(new_entry)
                    change_log.sort(key=lambda item: (int(item.get("chapter_index") or 0), int(item.get("scene_index") or 0)))
                    entity.visual_change_log = change_log
                    metadata = dict(entity.metadata_json or {})
                    metadata["character_visual_scene_state_agent"] = {
                        "source": self.VERSION,
                        "last_scene_id": scene["scene_id"],
                    }
                    entity.metadata_json = metadata
            session.commit()
        return len(scene_states)

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
        start = max(0, best_start - 260)
        end = min(len(source), best_start + best_len + 560)
        excerpt = source[start:end].strip()
        if len(excerpt) > self.MAX_SCENE_CHARS:
            excerpt = excerpt[: self.MAX_SCENE_CHARS].rstrip() + "..."
        return excerpt

    def _trim_scene_text(self, text: str) -> str:
        source = str(text or "").strip()
        if len(source) <= self.MAX_SCENE_CHARS:
            return source
        return source[: self.MAX_SCENE_CHARS].rstrip() + "..."

    def _clean(self, value: Any) -> str:
        return str(value or "").strip()

    def _fallback_text(self, value: Any, *, fallback: str = UNKNOWN_TEXT) -> str:
        cleaned = self._clean(value)
        return cleaned or fallback

    def _normalize_state_value(self, value: Any) -> str:
        if isinstance(value, list):
            cleaned_items = [self._clean(item) for item in value if self._clean(item)]
            return ", ".join(cleaned_items) if cleaned_items else UNKNOWN_TEXT
        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("[") and raw.endswith("]"):
                try:
                    parsed = ast.literal_eval(raw)
                except (SyntaxError, ValueError):
                    parsed = None
                if isinstance(parsed, list):
                    cleaned_items = [self._clean(item) for item in parsed if self._clean(item)]
                    return ", ".join(cleaned_items) if cleaned_items else UNKNOWN_TEXT
        return self._fallback_text(value)

    def _excerpt_has_visual_cues(self, excerpt: str) -> bool:
        normalized = self._normalize_text(excerpt)
        if not normalized:
            return False
        return any(keyword in normalized for keyword in self.VISUAL_CUE_KEYWORDS)

    def _load_previous_scene_state(self, *, entity_id: str, chapter_index: int, scene_index: int) -> dict[str, Any]:
        with self.sqlite_store.session_factory() as session:
            row = session.execute(
                select(CharacterVisualSceneState)
                .where(CharacterVisualSceneState.entity_id == entity_id)
                .order_by(CharacterVisualSceneState.chapter_index.desc(), CharacterVisualSceneState.scene_index.desc())
            ).scalars().all()
            for candidate in row:
                c_chapter = int(candidate.chapter_index or 0)
                c_scene = int(candidate.scene_index or 0)
                if (c_chapter, c_scene) < (chapter_index, scene_index):
                    return {
                        "chapter_index": c_chapter,
                        "scene_index": c_scene,
                        "scene_outfit": candidate.scene_outfit or UNKNOWN_TEXT,
                        "scene_accessories": candidate.scene_accessories or UNKNOWN_TEXT,
                        "scene_footwear": candidate.scene_footwear or UNKNOWN_TEXT,
                        "visible_condition": candidate.visible_condition or UNKNOWN_TEXT,
                        "injuries": candidate.injuries or UNKNOWN_TEXT,
                        "dirt_blood_markings": candidate.dirt_blood_markings or UNKNOWN_TEXT,
                        "body_language": candidate.body_language or UNKNOWN_TEXT,
                        "expression": candidate.expression or UNKNOWN_TEXT,
                        "carried_items": candidate.carried_items or UNKNOWN_TEXT,
                        "temporary_effects": candidate.temporary_effects or UNKNOWN_TEXT,
                    }
            return {}

    def _is_scene_grounded_excerpt(self, *, evidence_excerpt: str, candidate_excerpt: str, scene_text: str) -> bool:
        evidence = self._normalize_text(evidence_excerpt)
        candidate = self._normalize_text(candidate_excerpt)
        scene = self._normalize_text(scene_text)
        if not evidence:
            return False
        if evidence in scene or evidence in candidate:
            return True
        evidence_tokens = set(evidence.split())
        if not evidence_tokens:
            return False
        candidate_tokens = set(candidate.split())
        overlap = evidence_tokens & candidate_tokens
        return len(overlap) >= min(5, max(3, len(evidence_tokens) // 3))

    def _all_state_fields_unknown(self, state: dict[str, str]) -> bool:
        for field in self.STATE_FIELDS:
            if self._clean(state.get(field)) and self._clean(state.get(field)) != UNKNOWN_TEXT:
                return False
        return True

    def _normalize_text(self, value: str) -> str:
        cleaned = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
        return " ".join(cleaned.split())
