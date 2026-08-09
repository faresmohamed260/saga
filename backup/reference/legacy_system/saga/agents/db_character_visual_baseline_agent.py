from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import logging
import re
import time
from typing import Any

from sqlalchemy import select

from packages.reasoning_runtime.contracts import ReasoningClient
from packages.web_search_runtime.tool_contracts import WebSearchTool
from saga.contracts.retrieval import BookRetrievalTool
from saga.providers.reasoning_runtime_adapter import MODE_GENERAL_COMPUTE, MODE_GPT_OSS, create_runtime_client
from saga.services.retrieval_service import RetrievalService
from saga.storage.models import Book, CharacterProfile, CharacterVisualBaseline, Entity, Event, Scene
from saga.storage.persistence import SagaSQLiteStore
from saga.services.wiki_character_reference_service import WikiCharacterReferenceService

from saga.agents.db_character_profile_agent import (
    CharacterEvidenceBundle,
    UNKNOWN_LIST_ITEM,
    UNKNOWN_TEXT,
)


LOGGER = logging.getLogger(__name__)


class DatabaseCharacterVisualBaselineAgent:
    VERSION = "db_character_visual_baseline_agent_v3_richer_rag"
    WEB_GAP_FILL_VERSION = "db_character_visual_web_gap_fill_v1"
    CONFIDENCE_VALUES = {"high", "medium", "low"}
    MAX_SCENES_PER_CHARACTER = 48
    MAX_EVENTS_PER_CHARACTER = 48
    MAX_SCENE_CHARS = 1100
    MAX_EVIDENCE_ROWS_PER_GROUP = 12
    VISUAL_FIELDS = [
        "gender_presentation",
        "species_or_race",
        "apparent_age_group",
        "height_impression",
        "build",
        "skin_tone_or_complexion",
        "hair_color",
        "hair_length_or_style",
        "eye_color",
        "facial_features",
        "distinguishing_marks",
        "default_clothing_style",
        "default_accessories",
        "default_footwear",
        "signature_items",
        "fantasy_features",
        "world_genre_cues",
    ]
    FIELD_GROUPS = [
        {
            "name": "identity_body",
            "fields": [
                "gender_presentation",
                "species_or_race",
                "apparent_age_group",
                "height_impression",
                "build",
                "skin_tone_or_complexion",
            ],
            "question": "What stable body-identity traits are explicitly supported for this character in the book?",
            "keywords": ["man", "woman", "boy", "girl", "wizard", "witch", "giant", "tall", "short", "thin", "broad", "pale", "dark", "young", "old", "adult", "child"],
        },
        {
            "name": "face_hair",
            "fields": [
                "hair_color",
                "hair_length_or_style",
                "eye_color",
                "facial_features",
                "distinguishing_marks",
            ],
            "question": "What stable face, hair, eye, or identifying features are explicitly supported for this character in the book?",
            "keywords": ["hair", "eyes", "face", "scar", "nose", "beard", "mustache", "glasses", "spectacles", "freckles", "bald", "black-haired", "red-haired", "blond", "blue eyes", "green eyes"],
        },
        {
            "name": "style_world",
            "fields": [
                "default_clothing_style",
                "default_accessories",
                "default_footwear",
                "signature_items",
                "fantasy_features",
                "world_genre_cues",
            ],
            "question": "What stable clothing, accessories, signature items, fantasy traits, or world-style cues are explicitly supported for this character in the book?",
            "keywords": ["robe", "robes", "cloak", "coat", "hat", "boots", "shoes", "wand", "umbrella", "sword", "ring", "cloak", "school", "magic", "fantasy", "uniform", "baggy clothes", "glasses"],
        },
    ]

    def __init__(
        self,
        *,
        llm_client: ReasoningClient | None = None,
        sqlite_store: SagaSQLiteStore | None = None,
        retrieval_tool: BookRetrievalTool | None = None,
        web_reference_policy: str = "when_sparse",
        web_reference_service: WikiCharacterReferenceService | None = None,
        web_search_tool: WebSearchTool | None = None,
        max_attempts: int = 3,
        retry_delay_seconds: float = 1.5,
    ) -> None:
        self.sqlite_store = sqlite_store or SagaSQLiteStore()
        self.llm = llm_client or create_runtime_client(mode=MODE_GPT_OSS, allow_account_rotation=True, allow_cross_provider_fallback=False)
        self.retrieval_tool = retrieval_tool or RetrievalService(sqlite_store=self.sqlite_store)
        self.web_reference_policy = str(web_reference_policy or "when_sparse").strip().lower()
        self.web_reference_service = web_reference_service
        self.web_search_tool = web_search_tool
        self.max_attempts = max(1, int(max_attempts))
        self.retry_delay_seconds = max(0.0, float(retry_delay_seconds))
        self.max_group_workers = min(3, len(self.FIELD_GROUPS))

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
            "DB character visual baseline agent start | book=%s roster=%s",
            book_id,
            len(roster),
        )
        self.retrieval_tool.ensure_book_index(book_id=book_id, source_types=("scene", "event"))
        results: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for row in roster:
            bundle = self._build_character_bundle(book_id=book_id, roster_row=row)
            if not bundle.scenes and not bundle.events and not bundle.entity_context:
                skipped.append({"character_name": bundle.character_name, "reason": "no_evidence"})
                continue
            external_reference = self._load_external_reference(bundle)
            setattr(bundle, "external_reference", external_reference)
            visual_profile = self._extract_visual_baseline(bundle)
            self._persist_visual_baseline(bundle=bundle, visual_profile=visual_profile)
            results.append(
                {
                    "character_name": bundle.character_name,
                    "confidence": visual_profile.get("confidence", ""),
                    "scene_count": len(bundle.scenes),
                    "event_count": len(bundle.events),
                }
            )
        LOGGER.info(
            "DB character visual baseline agent complete | book=%s persisted=%s skipped=%s",
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

    def backfill_web_reference_gaps(
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
            "DB character visual web gap fill start | book=%s roster=%s",
            book_id,
            len(roster),
        )
        updated: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for row in roster:
            bundle = self._build_character_bundle(book_id=book_id, roster_row=row)
            if not self._has_web_fillable_gaps(bundle):
                skipped.append({"character_name": bundle.character_name, "reason": "enough_local_coverage"})
                continue
            external_reference = self._load_external_reference(bundle)
            if not external_reference or not self._has_reference_traits(external_reference):
                skipped.append({"character_name": bundle.character_name, "reason": "no_reference_traits"})
                continue
            changed_fields = self._persist_web_gap_fill(bundle=bundle, external_reference=external_reference)
            updated.append(
                {
                    "character_name": bundle.character_name,
                    "changed_fields": changed_fields,
                    "reference_page": str(external_reference.get("page_title") or ""),
                }
            )
        LOGGER.info(
            "DB character visual web gap fill complete | book=%s updated=%s skipped=%s",
            book_id,
            len(updated),
            len(skipped),
        )
        return {
            "book_id": book_id,
            "updated_characters": len(updated),
            "updated": updated,
            "skipped": skipped,
            "agent_version": self.WEB_GAP_FILL_VERSION,
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
                profile = session.execute(
                    select(CharacterProfile).where(CharacterProfile.book_id == book_id, CharacterProfile.character_name == canonical_name)
                ).scalar_one_or_none()
                roster.append(
                    {
                        "entity_id": row.id,
                        "character_name": canonical_name,
                        "aliases": [str(item).strip() for item in metadata.get("aliases") or [] if str(item).strip()],
                        "entity_context": str(row.entity_context or "").strip(),
                        "existing_typed_attributes": dict(row.typed_attributes or {}) if isinstance(row.typed_attributes, dict) else {},
                        "existing_initial_physical_description": dict(row.initial_physical_description or {}) if isinstance(row.initial_physical_description, dict) else {},
                        "existing_first_appearance_profile": dict(row.first_appearance_profile or {}) if isinstance(row.first_appearance_profile, dict) else {},
                        "profile_payload": dict(profile.payload_json or {}) if profile and isinstance(profile.payload_json, dict) else {},
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
            bundle = CharacterEvidenceBundle(
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
            setattr(bundle, "profile_payload", dict(roster_row.get("profile_payload") or {}))
            setattr(bundle, "existing_typed_attributes", dict(roster_row.get("existing_typed_attributes") or {}))
            setattr(bundle, "existing_initial_physical_description", dict(roster_row.get("existing_initial_physical_description") or {}))
            setattr(bundle, "existing_first_appearance_profile", dict(roster_row.get("existing_first_appearance_profile") or {}))
            return bundle

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
        start = max(0, best_start - 280)
        end = min(len(source), best_start + best_len + 520)
        excerpt = source[start:end].strip()
        if len(excerpt) > self.MAX_SCENE_CHARS:
            excerpt = excerpt[: self.MAX_SCENE_CHARS].rstrip() + "..."
        return excerpt

    def _extract_visual_baseline(self, bundle: CharacterEvidenceBundle) -> dict[str, Any]:
        partial_results: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=self.max_group_workers) as executor:
            future_map = {
                executor.submit(self._extract_field_group, bundle=bundle, group=group): group
                for group in self.FIELD_GROUPS
            }
            for future in as_completed(future_map):
                partial_results.append(future.result())
        return self._merge_group_results(bundle=bundle, partial_results=partial_results)

    def _extract_field_group(self, *, bundle: CharacterEvidenceBundle, group: dict[str, Any]) -> dict[str, Any]:
        evidence_rows = self._retrieve_group_evidence(bundle=bundle, group=group)
        prompt = self._build_group_prompt(bundle=bundle, group=group, evidence_rows=evidence_rows)
        response = self._run_llm_with_retries(
            prompt=prompt,
            character_name=bundle.character_name,
            attempt_label=str(group.get("name") or "group"),
        )
        return self._normalize_group_response(group=group, response=response, evidence_rows=evidence_rows)

    def _build_group_prompt(self, *, bundle: CharacterEvidenceBundle, group: dict[str, Any], evidence_rows: list[dict[str, Any]]) -> str:
        profile_payload = getattr(bundle, "profile_payload", {}) or {}
        existing_typed_attributes = getattr(bundle, "existing_typed_attributes", {}) or {}
        existing_initial_physical_description = getattr(bundle, "existing_initial_physical_description", {}) or {}
        existing_first_appearance_profile = getattr(bundle, "existing_first_appearance_profile", {}) or {}
        schema_traits = {field: UNKNOWN_TEXT for field in group["fields"]}
        field_notes = self._field_guidance(group["fields"])
        return f"""
You are a book-wide character visual trait RAG extraction agent for a canon database.
Return only grounded JSON for one character and one field group using retrieved evidence from the whole book.

Mission:
- Answer only the requested field group.
- Focus on durable, persistent character-sheet traits.
- Ignore temporary scene-only state unless the book clearly presents it as a default look.

Hard rules:
- Stay strictly grounded in the retrieved evidence.
- If the text does not support a field, use exactly `{UNKNOWN_TEXT}`.
- Never leave any field blank.
- Do not convert scene action, temporary mood, or one-off staging into a persistent trait.
- Do not invent colors, facial details, or clothing specifics.
- Prefer explicit descriptive phrases over generic labels when the evidence supports them.
- Use the supporting context below only as a hint to what earlier extraction layers saw; it is not authoritative unless it agrees with retrieved book evidence.
- If an external web reference is provided, use it only as a gap-filling aid for unsupported slots.
- External web reference must never override explicit book evidence.
- If book evidence and web reference disagree, prefer the book evidence.
- `world_genre_cues` should describe the grounded world/style context in plain terms for the character's look, if supportable.
- `evidence_excerpt` must not be blank.

Return JSON only:
{{
  "character_name": "{bundle.character_name}",
  "visual_baseline": {json.dumps(schema_traits, ensure_ascii=False)},
  "evidence_excerpt": "{UNKNOWN_TEXT}",
  "confidence": "high|medium|low"
}}

Target field group:
{group["name"]}

Target question:
{group["question"]}

Target fields:
{json.dumps(group["fields"], ensure_ascii=False)}

Field guidance:
{json.dumps(field_notes, ensure_ascii=False)}

Book:
{bundle.book_title}

Character:
{bundle.character_name}

Aliases:
{json.dumps(bundle.aliases, ensure_ascii=False)}

Existing entity context:
{bundle.entity_context or UNKNOWN_TEXT}

Existing profile payload:
{json.dumps(profile_payload, ensure_ascii=False)}

Existing typed attributes:
{json.dumps(existing_typed_attributes, ensure_ascii=False)}

Existing initial physical description:
{json.dumps(existing_initial_physical_description, ensure_ascii=False)}

Existing first appearance profile:
{json.dumps(existing_first_appearance_profile, ensure_ascii=False)}

External web reference:
{json.dumps(getattr(bundle, "external_reference", {}) or {}, ensure_ascii=False)}

Retrieved evidence:
{json.dumps(evidence_rows, ensure_ascii=False)}
"""

    def _load_external_reference(self, bundle: CharacterEvidenceBundle) -> dict[str, Any]:
        if self.web_reference_policy == "off":
            return {}
        if self.web_reference_policy == "when_sparse" and not self._needs_web_gap_fill(bundle):
            return {}
        try:
            service = self.web_reference_service or WikiCharacterReferenceService(
                llm_client=self.llm,
                web_search_tool=self.web_search_tool,
                series_id=self._infer_reference_series_id(bundle),
            )
            local_context = {
                "persistent_visual_profile": {
                    **((getattr(bundle, "profile_payload", {}) or {}).get("persistent_traits") or {}),
                    **((getattr(bundle, "existing_first_appearance_profile", {}) or {}).get("persistent_traits") or {}),
                },
                "typed_attributes": getattr(bundle, "existing_typed_attributes", {}) or {},
                "entity_context": bundle.entity_context,
            }
            result = service.research_character(
                bundle.character_name,
                local_context=local_context,
                contract_title=bundle.book_title,
            )
            LOGGER.info(
                "DB character visual baseline web reference | character=%s used=%s series=%s confidence=%s",
                bundle.character_name,
                bool(result),
                self._infer_reference_series_id(bundle),
                str((result or {}).get("confidence") or ""),
            )
            return result if isinstance(result, dict) else {}
        except Exception as exc:
            LOGGER.warning(
                "DB character visual baseline web reference failed | character=%s error=%s",
                bundle.character_name,
                exc,
            )
            return {}

    def _has_reference_traits(self, reference: dict[str, Any]) -> bool:
        traits = dict(reference.get("structured_traits") or {}) if isinstance(reference.get("structured_traits"), dict) else {}
        notes = [self._clean(item) for item in (reference.get("canon_notes") or []) if self._clean(item)]
        return bool(traits or notes)

    def _needs_web_gap_fill(self, bundle: CharacterEvidenceBundle) -> bool:
        known = 0
        for source in (
            (getattr(bundle, "profile_payload", {}) or {}).get("persistent_traits") or {},
            (getattr(bundle, "existing_first_appearance_profile", {}) or {}).get("persistent_traits") or {},
            (getattr(bundle, "existing_initial_physical_description", {}) or {}).get("baseline_visual_fields") or {},
        ):
            if not isinstance(source, dict):
                continue
            for field in self.VISUAL_FIELDS:
                value = self._clean(source.get(field))
                if value and value != UNKNOWN_TEXT:
                    known += 1
        return known < 6

    def _has_web_fillable_gaps(self, bundle: CharacterEvidenceBundle) -> bool:
        existing_traits = {
            **((getattr(bundle, "existing_initial_physical_description", {}) or {}).get("baseline_visual_fields") or {}),
            **((getattr(bundle, "existing_first_appearance_profile", {}) or {}).get("persistent_traits") or {}),
        }
        fillable_fields = {
            "hair_color",
            "hair_length_or_style",
            "eye_color",
            "skin_tone_or_complexion",
            "build",
            "facial_features",
            "default_clothing_style",
            "default_accessories",
            "default_footwear",
            "world_genre_cues",
            "distinguishing_marks",
            "fantasy_features",
        }
        return any(self._fallback_text(existing_traits.get(field)) == UNKNOWN_TEXT for field in fillable_fields)

    def _infer_reference_series_id(self, bundle: CharacterEvidenceBundle) -> str:
        series = str(bundle.series_id or "").strip().lower()
        title = str(bundle.book_title or "").strip().lower()
        if "harry" in series or "potter" in series or "harry potter" in title:
            return "harry-potter"
        if "acotar" in series or "court of thorns" in title:
            return "acotar"
        return series or "acotar"

    def _persist_web_gap_fill(self, *, bundle: CharacterEvidenceBundle, external_reference: dict[str, Any]) -> list[str]:
        with self.sqlite_store.session_factory() as session:
            entity = session.get(Entity, bundle.entity_id) if bundle.entity_id else None
            if entity is None:
                return []
            ipd = dict(entity.initial_physical_description or {}) if isinstance(entity.initial_physical_description, dict) else {}
            fap = dict(entity.first_appearance_profile or {}) if isinstance(entity.first_appearance_profile, dict) else {}
            existing_traits = dict(ipd.get("baseline_visual_fields") or fap.get("persistent_traits") or {})
            merged_traits, changed_fields = self._merge_reference_traits(existing_traits, external_reference)
            if not changed_fields:
                return []
            evidence_excerpt = self._clean(ipd.get("evidence_excerpt")) or self._clean(fap.get("evidence_excerpt")) or self._clean(entity.entity_context)
            baseline_summary = self._reference_summary(external_reference, merged_traits)
            entity.initial_physical_description = {
                **ipd,
                "baseline_visual_fields": merged_traits,
                "evidence_excerpt": evidence_excerpt or self._clean(external_reference.get("appearance_excerpt")) or UNKNOWN_TEXT,
                "description": ipd.get("description") or baseline_summary,
                "status": ipd.get("status") or "captured",
            }
            entity.first_appearance_profile = {
                **fap,
                "persistent_traits": merged_traits,
                "baseline_description": fap.get("baseline_description") or baseline_summary,
                "confidence": fap.get("confidence") or str(external_reference.get("confidence") or "medium"),
                "status": fap.get("status") or "captured",
            }
            existing_typed = dict(entity.typed_attributes or {}) if isinstance(entity.typed_attributes, dict) else {}
            entity.typed_attributes = self._merge_reference_typed_attributes(existing_typed, external_reference)
            metadata = dict(entity.metadata_json or {})
            metadata["character_web_gap_fill"] = {
                "source": self.WEB_GAP_FILL_VERSION,
                "page_title": str(external_reference.get("page_title") or ""),
                "page_url": str(external_reference.get("page_url") or ""),
                "resolved_via": str(external_reference.get("resolved_via") or ""),
                "confidence": str(external_reference.get("confidence") or ""),
                "changed_fields": changed_fields,
            }
            entity.metadata_json = metadata
            baseline = session.execute(
                select(CharacterVisualBaseline).where(
                    CharacterVisualBaseline.book_id == bundle.book_id,
                    CharacterVisualBaseline.entity_id == bundle.entity_id,
                )
            ).scalar_one_or_none()
            if baseline is not None:
                for field in self.VISUAL_FIELDS:
                    value = merged_traits.get(field)
                    if self._clean(value):
                        setattr(baseline, field, value)
                if not self._clean(baseline.evidence_excerpt):
                    baseline.evidence_excerpt = self._clean(external_reference.get("appearance_excerpt")) or evidence_excerpt or None
            session.commit()
            return changed_fields

    def _merge_reference_traits(self, existing_traits: dict[str, Any], external_reference: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
        merged = {
            field: self._fallback_text(existing_traits.get(field))
            for field in self.VISUAL_FIELDS
        }
        structured = dict(external_reference.get("structured_traits") or {}) if isinstance(external_reference.get("structured_traits"), dict) else {}
        changed_fields: list[str] = []
        field_map = {
            "hair_color": structured.get("hair_description"),
            "hair_length_or_style": structured.get("hair_description"),
            "eye_color": structured.get("eye_description"),
            "skin_tone_or_complexion": structured.get("skin_description"),
            "build": structured.get("body_type"),
            "facial_features": structured.get("facial_structure"),
            "default_clothing_style": structured.get("clothing_description"),
            "default_footwear": structured.get("footwear_description"),
            "world_genre_cues": structured.get("world_aesthetic_cues"),
            "distinguishing_marks": structured.get("distinguishing_marks"),
            "fantasy_features": structured.get("fantasy_features"),
        }
        notes = [self._clean(item) for item in (external_reference.get("canon_notes") or []) if self._clean(item)]
        if merged["default_accessories"] == UNKNOWN_TEXT and notes:
            accessory_hint = self._extract_accessory_hint(notes)
            if accessory_hint:
                merged["default_accessories"] = accessory_hint
                changed_fields.append("default_accessories")
        for field, raw_value in field_map.items():
            if merged[field] != UNKNOWN_TEXT:
                continue
            value = self._clean(raw_value)
            if not value:
                continue
            merged[field] = value
            changed_fields.append(field)
        return merged, changed_fields

    def _reference_summary(self, reference: dict[str, Any], traits: dict[str, str]) -> str:
        parts = [
            traits.get("hair_length_or_style") if traits.get("hair_length_or_style") != UNKNOWN_TEXT else "",
            traits.get("eye_color") if traits.get("eye_color") != UNKNOWN_TEXT else "",
            traits.get("facial_features") if traits.get("facial_features") != UNKNOWN_TEXT else "",
            traits.get("default_clothing_style") if traits.get("default_clothing_style") != UNKNOWN_TEXT else "",
            traits.get("distinguishing_marks") if traits.get("distinguishing_marks") != UNKNOWN_TEXT else "",
        ]
        rows = [self._clean(item) for item in parts if self._clean(item)]
        if rows:
            return ", ".join(rows[:5])
        notes = [self._clean(item) for item in (reference.get("canon_notes") or []) if self._clean(item)]
        return " | ".join(notes[:3]) if notes else UNKNOWN_TEXT

    def _merge_reference_typed_attributes(self, existing_typed: dict[str, Any], reference: dict[str, Any]) -> dict[str, list[str]]:
        merged = dict(existing_typed)
        structured = dict(reference.get("structured_traits") or {}) if isinstance(reference.get("structured_traits"), dict) else {}
        appearance = [
            structured.get("hair_description"),
            structured.get("eye_description"),
            structured.get("skin_description"),
            structured.get("body_type"),
            structured.get("facial_structure"),
            structured.get("distinguishing_marks"),
            structured.get("fantasy_features"),
        ]
        outfit = [
            structured.get("clothing_description"),
            structured.get("footwear_description"),
        ]
        merged["appearance"] = self._merge_prefer_existing_lists(existing_typed.get("appearance"), appearance)
        merged["outfit"] = self._merge_prefer_existing_lists(existing_typed.get("outfit"), outfit)
        return merged

    def _extract_accessory_hint(self, notes: list[str]) -> str:
        accessory_terms = ("glasses", "spectacles", "wand", "cloak", "hat", "ring", "scarf")
        for note in notes:
            lowered = note.lower()
            if any(term in lowered for term in accessory_terms):
                return note
        return ""

    def _run_llm_with_retries(self, *, prompt: str, character_name: str, attempt_label: str) -> dict[str, Any]:
        last_error = ""
        for attempt in range(1, self.max_attempts + 1):
            LOGGER.info(
                "DB character visual baseline agent LLM attempt start | character=%s group=%s attempt=%s/%s",
                character_name,
                attempt_label,
                attempt,
                self.max_attempts,
            )
            response = self.llm.generate_json(prompt, strict=True, validator=self._validate_response)
            if isinstance(response, dict) and "error" not in response:
                LOGGER.info(
                    "DB character visual baseline agent LLM attempt complete | character=%s group=%s attempt=%s/%s",
                    character_name,
                    attempt_label,
                    attempt,
                    self.max_attempts,
                )
                return response
            last_error = str((response or {}).get("error") or "unknown_error")
            LOGGER.warning(
                "DB character visual baseline agent LLM attempt failed | character=%s group=%s attempt=%s/%s error=%s",
                character_name,
                attempt_label,
                attempt,
                self.max_attempts,
                last_error,
            )
            if attempt < self.max_attempts and self.retry_delay_seconds > 0:
                time.sleep(self.retry_delay_seconds)
        raise RuntimeError(
            f"DB character visual baseline agent failed after {self.max_attempts} attempts for {character_name} group {attempt_label}: {last_error}"
        )

    def _validate_response(self, response: dict[str, Any]) -> bool:
        if not isinstance(response, dict):
            return False
        baseline = response.get("visual_baseline") or {}
        if not isinstance(baseline, dict):
            return False
        confidence = str(response.get("confidence") or "").strip().lower()
        return confidence in self.CONFIDENCE_VALUES

    def _normalize_group_response(self, *, group: dict[str, Any], response: dict[str, Any], evidence_rows: list[dict[str, Any]]) -> dict[str, Any]:
        baseline = {
            field: self._fallback_text((response.get("visual_baseline") or {}).get(field))
            for field in group["fields"]
        }
        return {
            "group_name": group["name"],
            "visual_baseline": baseline,
            "evidence_excerpt": self._fallback_text(
                response.get("evidence_excerpt"),
                fallback=self._fallback_evidence_excerpt_from_rows(evidence_rows),
            ),
            "confidence": self._clean(response.get("confidence")).lower() or "low",
            "agent_version": self.VERSION,
            "evidence_rows": evidence_rows,
        }

    def _merge_group_results(self, *, bundle: CharacterEvidenceBundle, partial_results: list[dict[str, Any]]) -> dict[str, Any]:
        merged = {field: UNKNOWN_TEXT for field in self.VISUAL_FIELDS}
        evidence_rows: list[dict[str, Any]] = []
        confidences: list[str] = []
        evidence_excerpt = UNKNOWN_TEXT
        for result in partial_results:
            merged.update(result.get("visual_baseline") or {})
            confidences.append(str(result.get("confidence") or "low"))
            evidence_rows.extend(result.get("evidence_rows") or [])
            current_excerpt = self._clean(result.get("evidence_excerpt"))
            if evidence_excerpt == UNKNOWN_TEXT and current_excerpt:
                evidence_excerpt = current_excerpt
        if evidence_excerpt == UNKNOWN_TEXT:
            evidence_excerpt = self._fallback_evidence_excerpt(bundle)
        return {
            "character_name": bundle.character_name,
            "visual_baseline": merged,
            "evidence_excerpt": evidence_excerpt,
            "confidence": self._merge_confidence(confidences),
            "agent_version": self.VERSION,
            "source_scene_rows": evidence_rows[:20],
        }

    def _persist_visual_baseline(self, *, bundle: CharacterEvidenceBundle, visual_profile: dict[str, Any]) -> None:
        with self.sqlite_store.session_factory() as session:
            baseline = session.execute(
                select(CharacterVisualBaseline).where(
                    CharacterVisualBaseline.book_id == bundle.book_id,
                    CharacterVisualBaseline.entity_id == bundle.entity_id,
                )
            ).scalar_one_or_none()
            values = {
                **visual_profile["visual_baseline"],
                "evidence_excerpt": visual_profile["evidence_excerpt"],
                "source_scene_json": visual_profile.get("source_scene_rows") or bundle.scenes[:6],
            }
            if bundle.entity_id:
                if baseline is None:
                    session.add(
                        CharacterVisualBaseline(
                            book_id=bundle.book_id,
                            entity_id=bundle.entity_id,
                            **values,
                        )
                    )
                else:
                    for key, value in values.items():
                        setattr(baseline, key, value)

            profile = session.execute(
                select(CharacterProfile).where(
                    CharacterProfile.book_id == bundle.book_id,
                    CharacterProfile.character_name == bundle.character_name,
                )
            ).scalar_one_or_none()
            if profile is not None and isinstance(profile.payload_json, dict):
                payload = dict(profile.payload_json or {})
                payload["persistent_traits"] = dict(visual_profile["visual_baseline"])
                payload["visual_baseline_confidence"] = visual_profile["confidence"]
                payload["visual_baseline_agent_version"] = self.VERSION
                payload["evidence_excerpt"] = visual_profile["evidence_excerpt"]
                profile.payload_json = payload

            entity = session.get(Entity, bundle.entity_id) if bundle.entity_id else None
            if entity is not None:
                entity.first_appearance_profile = {
                    "persistent_traits": dict(visual_profile["visual_baseline"]),
                    "confidence": visual_profile["confidence"],
                    "agent_version": self.VERSION,
                }
                entity.initial_physical_description = {
                    "baseline_visual_fields": dict(visual_profile["visual_baseline"]),
                    "evidence_excerpt": visual_profile["evidence_excerpt"],
                }
                previous_typed = dict(entity.typed_attributes or {}) if isinstance(entity.typed_attributes, dict) else {}
                entity.typed_attributes = {
                    "appearance": self._merge_prefer_existing_lists(
                        previous_typed.get("appearance"),
                        [
                            visual_profile["visual_baseline"].get("height_impression", ""),
                            visual_profile["visual_baseline"].get("build", ""),
                            visual_profile["visual_baseline"].get("skin_tone_or_complexion", ""),
                            visual_profile["visual_baseline"].get("hair_color", ""),
                            visual_profile["visual_baseline"].get("hair_length_or_style", ""),
                            visual_profile["visual_baseline"].get("eye_color", ""),
                            visual_profile["visual_baseline"].get("facial_features", ""),
                            visual_profile["visual_baseline"].get("distinguishing_marks", ""),
                            visual_profile["visual_baseline"].get("fantasy_features", ""),
                            visual_profile["visual_baseline"].get("signature_items", ""),
                        ],
                    ),
                    "outfit": self._merge_prefer_existing_lists(
                        previous_typed.get("outfit"),
                        [
                            visual_profile["visual_baseline"].get("default_clothing_style", ""),
                            visual_profile["visual_baseline"].get("default_accessories", ""),
                            visual_profile["visual_baseline"].get("default_footwear", ""),
                        ],
                    ),
                    "titles_or_roles": self._merge_prefer_existing_lists(
                        previous_typed.get("titles_or_roles"),
                        ((getattr(bundle, "profile_payload", {}) or {}).get("titles_or_roles") or [UNKNOWN_LIST_ITEM]),
                    ),
                    "affiliations": self._merge_prefer_existing_lists(
                        previous_typed.get("affiliations"),
                        ((getattr(bundle, "profile_payload", {}) or {}).get("affiliations") or [UNKNOWN_LIST_ITEM]),
                    ),
                }
                metadata = dict(entity.metadata_json or {})
                metadata["character_visual_baseline_agent"] = {
                    "source": self.VERSION,
                    "evidence_scene_count": len(bundle.scenes),
                    "evidence_event_count": len(bundle.events),
                    "rag_group_count": len(self.FIELD_GROUPS),
                    "web_reference_used": bool(getattr(bundle, "external_reference", {}) or {}),
                    "web_reference_policy": self.web_reference_policy,
                }
                if getattr(bundle, "external_reference", {}) or {}:
                    metadata["character_visual_baseline_agent"]["web_reference"] = {
                        "page_title": str((getattr(bundle, "external_reference", {}) or {}).get("page_title") or ""),
                        "page_url": str((getattr(bundle, "external_reference", {}) or {}).get("page_url") or ""),
                        "resolved_via": str((getattr(bundle, "external_reference", {}) or {}).get("resolved_via") or ""),
                        "confidence": str((getattr(bundle, "external_reference", {}) or {}).get("confidence") or ""),
                    }
                entity.metadata_json = metadata
            session.commit()

    def _retrieve_group_evidence(self, *, bundle: CharacterEvidenceBundle, group: dict[str, Any]) -> list[dict[str, Any]]:
        query_text = self._build_group_query(bundle=bundle, group=group)
        semantic_rows = self._query_book_retrieval(
            book_id=bundle.book_id,
            query_text=query_text,
            top_k=self.MAX_EVIDENCE_ROWS_PER_GROUP,
            source_types=("scene", "event"),
            entity_bias=bundle.aliases,
        )
        normalized_semantic = [self._normalize_retrieved_row(row) for row in semantic_rows]
        if normalized_semantic:
            LOGGER.info(
                "DB character visual baseline semantic retrieval | character=%s group=%s hits=%s",
                bundle.character_name,
                group["name"],
                len(normalized_semantic),
            )
            return normalized_semantic

        keywords = [self._normalize_text(item) for item in group.get("keywords") or [] if self._normalize_text(item)]
        alias_keys = [self._normalize_text(alias) for alias in bundle.aliases if self._normalize_text(alias)]
        scored: list[tuple[int, dict[str, Any]]] = []
        for row in bundle.scenes:
            excerpt = self._clean(row.get("excerpt"))
            if not excerpt:
                continue
            score = self._score_evidence_text(text=excerpt, alias_keys=alias_keys, keywords=keywords)
            if score <= 0:
                continue
            scored.append(
                (
                    score,
                    {
                        "source_type": "scene",
                        "scene_id": row.get("scene_id"),
                        "chapter_index": row.get("chapter_index"),
                        "scene_index": row.get("scene_index"),
                        "summary": row.get("summary"),
                        "excerpt": excerpt,
                    },
                )
            )
        for row in bundle.events:
            event_text = " ".join(
                item
                for item in [
                    self._clean(row.get("description")),
                    self._clean(row.get("reason")),
                    self._clean(row.get("outcome")),
                ]
                if item
            )
            if not event_text:
                continue
            score = self._score_evidence_text(text=event_text, alias_keys=alias_keys, keywords=keywords)
            if score <= 0:
                continue
            scored.append(
                (
                    score,
                    {
                        "source_type": "event",
                        "chapter_index": row.get("chapter_index"),
                        "scene_index": row.get("scene_index"),
                        "event_type": row.get("event_type"),
                        "excerpt": event_text,
                    },
                )
            )
        scored.sort(key=lambda item: (-item[0], int(item[1].get("chapter_index") or 0), int(item[1].get("scene_index") or 0)))
        unique_rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for _, row in scored:
            key = json.dumps(row, sort_keys=True, ensure_ascii=False)
            if key in seen:
                continue
            seen.add(key)
            unique_rows.append(row)
            if len(unique_rows) >= self.MAX_EVIDENCE_ROWS_PER_GROUP:
                break
        if unique_rows:
            return unique_rows
        return (bundle.scenes[:2] or bundle.events[:2] or [{"source_type": "fallback", "excerpt": self._fallback_evidence_excerpt(bundle)}])

    def _build_group_query(self, *, bundle: CharacterEvidenceBundle, group: dict[str, Any]) -> str:
        return " ".join(
            item
            for item in [
                bundle.character_name,
                " / ".join(bundle.aliases[:4]),
                str(group.get("question") or "").strip(),
                "keywords: " + ", ".join(group.get("keywords") or []),
            ]
            if item
        )

    def _normalize_retrieved_row(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "source_type": str(row.get("source_type") or "").strip(),
            "scene_id": row.get("source_id"),
            "chapter_index": row.get("chapter_index"),
            "scene_index": row.get("scene_index"),
            "summary": str(row.get("summary") or "").strip(),
            "excerpt": self._clean(row.get("excerpt")),
            "score": row.get("score"),
            "metadata": row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
        }

    def _query_book_retrieval(self, **kwargs) -> list[dict[str, Any]]:
        return self.retrieval_tool.query_book(**kwargs)

    def _score_evidence_text(self, *, text: str, alias_keys: list[str], keywords: list[str]) -> int:
        normalized = self._normalize_text(text)
        if not normalized:
            return 0
        score = 0
        for alias in alias_keys:
            if alias and alias in normalized:
                score += 3
        for keyword in keywords:
            if keyword and keyword in normalized:
                score += 2
        return score

    def _fallback_evidence_excerpt_from_rows(self, rows: list[dict[str, Any]]) -> str:
        for row in rows:
            excerpt = self._clean(row.get("excerpt"))
            if excerpt:
                return excerpt
        return UNKNOWN_TEXT

    def _merge_confidence(self, values: list[str]) -> str:
        lowered = [self._clean(value).lower() for value in values if self._clean(value)]
        if not lowered:
            return "low"
        if all(value == "high" for value in lowered):
            return "high"
        if "medium" in lowered or "high" in lowered:
            return "medium"
        return "low"

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

    def _clean(self, value: Any) -> str:
        return " ".join(str(value or "").strip().split())

    def _fallback_text(self, value: Any, *, fallback: str = UNKNOWN_TEXT) -> str:
        cleaned = self._clean(value)
        return cleaned or fallback

    def _filled_list(self, values: list[Any]) -> list[str]:
        rows = []
        seen: set[str] = set()
        for value in values:
            cleaned = self._clean(value)
            lowered = cleaned.lower()
            if not cleaned or lowered in seen:
                continue
            seen.add(lowered)
            rows.append(cleaned)
        return rows or [UNKNOWN_LIST_ITEM]

    def _merge_prefer_existing_lists(self, existing: Any, generated: Any) -> list[str]:
        existing_rows = [item for item in (existing or []) if self._clean(item) and self._clean(item) != UNKNOWN_TEXT]
        generated_rows = [item for item in (generated or []) if self._clean(item) and self._clean(item) != UNKNOWN_TEXT]
        merged = self._filled_list([*existing_rows, *generated_rows])
        return merged

    def _field_guidance(self, fields: list[str]) -> dict[str, str]:
        guidance = {
            "gender_presentation": "Use only if explicitly signaled in the book text.",
            "species_or_race": "Prefer plain in-world type such as human, wizard, giant, witch, elf, goblin, etc.",
            "apparent_age_group": "Use child, teen, young adult, middle-aged, elderly only if the text supports it.",
            "height_impression": "Prefer phrases like tall, short, lanky, towering.",
            "build": "Prefer stable body build phrases like thin, broad-shouldered, heavyset, slight build.",
            "skin_tone_or_complexion": "Use explicit complexion phrases only when directly supported.",
            "hair_color": "Capture the explicit stable color only.",
            "hair_length_or_style": "Capture stable style such as cropped short hair, tight bun, long beard.",
            "eye_color": "Use explicit eye color only, not emotional gaze.",
            "facial_features": "Capture persistent face structure or repeated identifying face description, not temporary expression.",
            "distinguishing_marks": "Use scars, tattoos, glasses, missing teeth, unusual features, etc. only if persistent.",
            "default_clothing_style": "Prefer stable silhouette and garment style, not a one-scene action pose.",
            "default_accessories": "Use glasses, hats, jewelry, visible badges, belts, etc. if they read as recurring or first-appearance-defining.",
            "default_footwear": "Only fill when explicit.",
            "signature_items": "Use recurring held/worn items strongly associated with the character.",
            "fantasy_features": "Use magical anatomy or visible fantasy trait, not abstract powers.",
            "world_genre_cues": "Describe the look context in plain style terms such as wizarding academic attire or rustic fantasy traveler styling.",
        }
        return {field: guidance.get(field, "") for field in fields}

    def _normalize_text(self, value: str) -> str:
        cleaned = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
        return " ".join(cleaned.split())


