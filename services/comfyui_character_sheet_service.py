from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from sqlalchemy import select

from analysis.visual_prompt_schema import (
    compile_entity_concept_prompt,
    compile_location_concept_prompt,
    compile_character_turnaround_prompt,
    normalize_persistent_profile,
    profile_specificity_score,
    promote_persistent_profile_from_visual_changes,
)
from core.canon_normalization import CanonicalEntityNormalizer
from services.entity_visual_prompt_service import EntityVisualPromptService
from sql_store.persistence import SagaSQLiteStore
from sql_store.models import Book as SqlBook
from sql_store.models import Entity as SqlEntity
from sql_store.models import GeneratedImage as SqlGeneratedImage
from sql_store.models import VisualPrompt as SqlVisualPrompt

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_OUTPUTS = ROOT / "analysis_outputs"
RENDER_ROOT = ANALYSIS_OUTPUTS / "visual_state" / "character_sheet_renders"
RENDER_CLIENT = ROOT / "modal_comfyui" / "render_client.py"
POSE_IMAGE = ROOT / "modal_comfyui" / "assets" / "pose-sheet.png"

DEFAULT_NEGATIVE_PROMPT = (
    "illustration, painterly style, anime, CGI, 3D render, game character, plastic or overly smooth skin, "
    "no toon shading, no cel shading, exaggerated proportions, cinematic lighting, dramatic shadows, fantasy glow, "
    "magical effects, environment or scenery, extra characters or duplicates, modern clothing, denim, t-shirt, hoodie, "
    "sneakers, zipper, plastic accessories, modern jewelry, futuristic materials, contemporary streetwear."
)


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())
    return cleaned.strip("-") or "unnamed"


def render_output_dir_for_contract(contract_path: str | Path) -> Path:
    contract_str = str(contract_path)
    if contract_str.startswith("db://book/"):
        book_id = contract_str.split("db://book/", 1)[-1].strip() or "book"
        return RENDER_ROOT / "sqlite" / _slugify(book_id)
    contract = Path(contract_str)
    contract_name = contract.name.replace(".contract.json", "")
    parent_run = contract.parent.parent.name if contract.parent.name == "contracts" else contract.parent.name
    series_name = contract.parent.parent.parent.name if contract.parent.name == "contracts" and contract.parent.parent.parent else "series"
    return RENDER_ROOT / _slugify(series_name) / _slugify(parent_run) / _slugify(contract_name)


def render_manifest_path_for_contract(contract_path: str | Path) -> Path:
    return render_output_dir_for_contract(contract_path) / "manifest.json"


class ComfyUICharacterSheetService:
    CREATURE_MARKERS = {
        "attor", "creature", "monster", "beast", "animal", "wolf", "kelpie", "naga", "suriel", "bogge",
        "fangs", "talons", "claws", "clawed", "snout", "muzzle", "scaled", "scales", "fur", "hide", "bat-like",
        "leathery", "predatory", "skeletal", "centaur", "goblin", "ghost", "poltergeist", "spirit", "dog",
        "boarhound", "owl", "horse body", "cat", "hound",
    }
    HUMANOID_MARKERS = {
        "human", "humanoid", "woman", "man", "male", "female", "person", "warrior", "lord", "lady",
        "noble", "priestess", "servant", "attendant", "hunter", "fighter", "soldier", "high fae", "fae",
        "wizard", "witch", "student", "boy", "girl", "professor", "mr", "mrs", "ms", "uncle", "aunt",
    }
    OBJECT_MARKERS = {
        "coin", "coins", "knut", "knuts", "galleon", "galleons", "sickle", "hat", "sorting hat", "wand", "broom",
        "arrow", "knife", "sword", "book", "newspaper", "prophet", "portrait", "package", "crate", "cart", "door",
        "train", "stone", "snitch", "quaffle", "put-outer", "cloak", "glasses", "spectacles", "bag", "ticket",
        "flames", "fire", "mirror", "trapdoor", "clock", "harness", "boat",
    }
    LOCATION_MARKERS = {
        "forest", "castle", "tower", "hall", "room", "house", "cottage", "court", "city", "village", "street",
        "drive", "lake", "mountain", "bedroom", "kitchen", "office", "dormitory", "classroom", "vault", "station",
        "platform", "cabinet", "shop", "bank", "pub", "inn", "library", "hut",
    }
    GENERIC_LABEL_SUPPRESSIONS = {
        "giant", "goblin", "ghost", "dog", "cat", "wolf", "owl", "centaur", "spirit", "poltergeist",
        "dragon", "snake", "spider", "troll",
    }
    TITLE_LIKE_PREFIXES = {
        "mr", "mrs", "ms", "miss", "professor", "prof", "uncle", "aunt", "sir", "lord", "lady",
    }

    def __init__(self) -> None:
        self.normalizer = CanonicalEntityNormalizer()
        self.sqlite_store = SagaSQLiteStore()
        self.entity_visual_prompt_service = EntityVisualPromptService(self.sqlite_store)

    def load_contract(self, contract_path: str | Path) -> dict[str, Any]:
        if str(contract_path).startswith("db://book/"):
            raise FileNotFoundError("DB-backed render source should use SQLite prompt collection, not file loading.")
        return json.loads(Path(contract_path).read_text(encoding="utf-8-sig"))

    def collect_entity_visual_prompts(self, contract_path: str | Path, *, limit: int = 0) -> list[dict[str, Any]]:
        if str(contract_path).startswith("db://book/"):
            return self._collect_entity_visual_prompts_from_db(str(contract_path), limit=limit)
        payload = self.load_contract(contract_path)
        outputs = payload.get("outputs") or {}
        prompt_sets = outputs.get("visual_prompt_sets") or {}
        entity_registry = outputs.get("entity_registry") or []
        alias_map = ((outputs.get("identity_result") or {}).get("alias_map") or {})
        context = self.normalizer.build_context(entity_registry=entity_registry, alias_map=alias_map)

        prompt_maps = self._build_prompt_maps(
            prompt_sets=prompt_sets,
            entity_registry=entity_registry,
            context=context,
        )
        rows: list[dict[str, Any]] = []
        for entry in entity_registry:
            if not isinstance(entry, dict):
                continue
            entity_name = str(entry.get("name") or "").strip()
            entity_type = self._effective_registry_entity_type(entry)
            if not entity_name or entity_type not in {"character", "creature", "object", "location"}:
                continue
            typed_entry = dict(entry)
            typed_entry["entity_type"] = entity_type
            mapped_row = prompt_maps.get((entity_name.lower(), entity_type))
            if mapped_row and entity_type != "character" and (
                str(mapped_row.get("visual_bucket") or "").strip().lower() == "initial_characters"
                or str(mapped_row.get("prompt_type") or "").strip().lower() == "initial_character_description"
            ):
                mapped_row = None
            baseline_row = self._build_registry_baseline_prompt_payload(typed_entry)
            if mapped_row and entity_type == "character":
                chosen = self._merge_registry_character_payload(mapped_row, entry)
            else:
                chosen = mapped_row or baseline_row
            if not chosen:
                continue
            render_row = dict(chosen)
            render_row["entity_name"] = entity_name
            render_row["entity_type"] = entity_type
            render_row.setdefault("book_index", (entry.get("first_seen") or {}).get("book_index"))
            render_row.setdefault("chapter_index", (entry.get("first_seen") or {}).get("chapter_index"))
            render_row.setdefault("scene_index", (entry.get("first_seen") or {}).get("scene_index"))
            render_row["details"] = dict(render_row.get("details") or {})
            render_row["details"]["canonical_entity_name"] = entity_name
            render_row["details"]["entity_context"] = str(entry.get("entity_context") or "")
            render_row["details"]["registry_entity_type"] = entity_type
            render_row["workflow_mode"] = "character_sheet" if entity_type == "character" else "default"
            if entity_type == "character":
                render_row.setdefault("width", 1504)
                render_row.setdefault("height", 1024)
            elif entity_type == "location":
                render_row.setdefault("width", 1344)
                render_row.setdefault("height", 768)
            else:
                render_row.setdefault("width", 1024)
                render_row.setdefault("height", 1024)
            rows.append(render_row)
        rows = sorted(rows, key=lambda row: (str(row.get("entity_type") or ""), str(row.get("entity_name") or "").lower()))
        if limit and limit > 0:
            rows = rows[:limit]
        return rows

    def _collect_entity_visual_prompts_from_db(self, book_ref: str, *, limit: int = 0) -> list[dict[str, Any]]:
        book_id = str(book_ref).split("db://book/", 1)[-1].strip()
        rows: list[dict[str, Any]] = []
        self.entity_visual_prompt_service.build_book_prompts(book_ref, overwrite=False)
        with self.sqlite_store.session_factory() as session:
            book = session.get(SqlBook, book_id)
            if book is None:
                return rows
            entities = session.execute(
                select(SqlEntity).where(SqlEntity.book_id == book.id).order_by(SqlEntity.entity_type.asc(), SqlEntity.canonical_name.asc())
            ).scalars().all()
            prompts = session.execute(select(SqlVisualPrompt).where(SqlVisualPrompt.book_id == book.id)).scalars().all()
            images = session.execute(select(SqlGeneratedImage).where(SqlGeneratedImage.book_id == book.id)).scalars().all()
            prompt_map = {(str(row.entity_name or "").lower(), str(row.entity_type or "").lower()): row for row in prompts}
            image_map = {(str(row.entity_name or "").lower(), str(row.entity_type or "").lower()): row for row in images}
            for entity in entities:
                registry_entry = self._sql_entity_to_registry_entry(entity)
                entity_type = str(entity.entity_type or "").strip().lower() or self._effective_registry_entity_type(registry_entry)
                if entity_type not in {"character", "creature", "object", "location", "organization", "other"}:
                    continue
                registry_entry["entity_type"] = entity_type
                key = (str(entity.canonical_name or "").lower(), entity_type)
                prompt = prompt_map.get(key)
                prompt_valid = bool(prompt and str(prompt.positive_prompt or "").strip())
                if prompt_valid and entity_type != "character":
                    prompt_kind = str(prompt.prompt_type or "").strip().lower()
                    prompt_bucket = str(prompt.visual_bucket or "").strip().lower()
                    if prompt_kind == "initial_character_description" or prompt_bucket == "initial_characters":
                        prompt_valid = False
                image = image_map.get(key)
                baseline_row = self._build_registry_baseline_prompt_payload(registry_entry)
                merged_row: dict[str, Any] | None = None
                if prompt_valid:
                    prompt_row = {
                        "entity_name": entity.canonical_name,
                        "entity_type": entity_type,
                        "book_index": entity.first_seen_book_index,
                        "chapter_index": entity.first_seen_chapter_index,
                        "scene_index": entity.first_seen_scene_index,
                        "positive_prompt": str(prompt.positive_prompt or "").strip(),
                        "negative_prompt": str(prompt.negative_prompt or "").strip(),
                        "confidence": str(prompt.confidence or "").strip() or "medium",
                        "prompt_type": str(prompt.prompt_type or "").strip() or f"initial_{entity_type}_description",
                        "visual_bucket": str(prompt.visual_bucket or "").strip() or ("initial_characters" if entity_type == "character" else entity_type),
                        "source_evidence": str(prompt.source_evidence or "").strip(),
                        "details": dict(prompt.details_json or {}),
                    }
                    merged_row = (
                        self._merge_registry_character_payload(prompt_row, registry_entry)
                        if entity_type == "character"
                        else prompt_row
                    )
                chosen = merged_row or baseline_row
                if not chosen or not str(chosen.get("positive_prompt") or "").strip():
                    continue
                chosen["generated_image_path"] = entity.generated_image_path or str(getattr(image, "output_path", "") or "")
                chosen["render_status"] = str(getattr(image, "render_status", "") or "")
                chosen["mention_count"] = entity.mention_count or 0
                chosen["entity_context"] = entity.entity_context or ""
                chosen["initial_physical_description"] = entity.initial_physical_description or {}
                chosen["first_appearance_profile"] = entity.first_appearance_profile or {}
                chosen["typed_attributes"] = entity.typed_attributes or {}
                chosen["analysis_quality_flags"] = entity.analysis_quality_flags or []
                chosen["workflow_mode"] = "character_sheet" if entity_type == "character" else "default"
                chosen["width"] = 1504 if entity_type == "character" else (1344 if entity_type == "location" else 1024)
                chosen["height"] = 1024 if entity_type != "location" else 768
                rows.append(chosen)
        rows = sorted(rows, key=lambda row: (str(row.get("entity_type") or ""), str(row.get("entity_name") or "").lower()))
        if limit and limit > 0:
            rows = rows[:limit]
        return rows

    def collect_character_prompts(self, contract_path: str | Path, *, limit: int = 0) -> list[dict[str, Any]]:
        rows = [
            row
            for row in self.collect_entity_visual_prompts(contract_path, limit=limit)
            if str(row.get("entity_type") or "").lower() == "character"
        ]
        if limit and limit > 0:
            rows = rows[:limit]
        return rows

    def _build_prompt_maps(self, *, prompt_sets: dict[str, Any], entity_registry: list[dict[str, Any]], context) -> dict[tuple[str, str], dict[str, Any]]:
        registry_by_name = {
            str(item.get("name") or "").strip().lower(): item
            for item in entity_registry
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        }
        mapped: dict[tuple[str, str], dict[str, Any]] = {}
        seen_names: list[str] = []

        def _store(row: dict[str, Any], bucket: str, default_type: str) -> None:
            name = str(row.get("entity_name") or "").strip()
            if not name:
                return
            canonical_name = self._resolve_render_name(name, context=context, seen_names=seen_names)
            registry_entry = registry_by_name.get(canonical_name.lower()) or registry_by_name.get(name.lower()) or {}
            entity_type = default_type
            if bucket == "initial_characters":
                entity_type = self._classify_render_entity_type(row, registry_entry=registry_entry)
            else:
                entity_type = str(row.get("entity_type") or default_type).strip().lower() or default_type
            key = (canonical_name.lower(), entity_type)
            current = mapped.get(key)
            candidate = dict(row)
            candidate["entity_name"] = canonical_name
            candidate.setdefault("visual_bucket", bucket)
            if entity_type == "character":
                candidate.setdefault("prompt_type", "initial_character_description")
                candidate = self._corrected_character_row(candidate)
            if current:
                mapped[key] = self._prefer_prompt_row(current, candidate, entity_type=entity_type)
            else:
                mapped[key] = candidate
            seen_names.append(name)

        for row in prompt_sets.get("initial_characters") or []:
            if isinstance(row, dict):
                _store(row, "initial_characters", "character")
        for row in prompt_sets.get("objects_creatures") or []:
            if isinstance(row, dict):
                default_type = str(row.get("entity_type") or "object").strip().lower() or "object"
                _store(row, "objects_creatures", default_type)
        for row in prompt_sets.get("locations") or []:
            if isinstance(row, dict):
                _store(row, "locations", "location")
        return mapped

    def _effective_registry_entity_type(self, entry: dict[str, Any]) -> str:
        raw_type = str(entry.get("entity_type") or "").strip().lower()
        name_lower = str(entry.get("name") or "").strip().lower()
        descriptions = " ".join(
            str(item.get("description") or "")
            for item in (entry.get("descriptions") or [])
            if isinstance(item, dict)
        )
        initial_description = str(((entry.get("initial_physical_description") or {}).get("description")) or "")
        typed_attributes = entry.get("typed_attributes") or {}
        first_appearance = entry.get("first_appearance_profile") or {}
        haystack = " ".join(
            [
                str(entry.get("name") or ""),
                descriptions,
                initial_description,
                str(first_appearance.get("baseline_description") or ""),
                " ".join(str(value) for values in typed_attributes.values() for value in (values or [])) if isinstance(typed_attributes, dict) else "",
            ]
        ).lower()
        has_humanoid = self._contains_marker(haystack, self.HUMANOID_MARKERS)
        if raw_type in {"object", "location", "creature", "organization", "other"}:
            return raw_type
        if raw_type == "character" and self._contains_marker(haystack, self.CREATURE_MARKERS) and not has_humanoid:
            return "creature"
        if raw_type == "character" and self._contains_marker(name_lower, self.LOCATION_MARKERS) and not has_humanoid:
            return "location"
        if raw_type == "character" and self._contains_marker(name_lower, self.OBJECT_MARKERS) and not has_humanoid:
            return "object"
        if self._contains_marker(name_lower, self.OBJECT_MARKERS) and not has_humanoid:
            return "object"
        if self._contains_marker(name_lower, self.LOCATION_MARKERS) and not has_humanoid:
            return "location"
        if self._contains_marker(haystack, self.OBJECT_MARKERS) and not has_humanoid:
            return "object"
        if self._contains_marker(haystack, self.LOCATION_MARKERS) and not has_humanoid:
            return "location"
        inferred = self.normalizer.infer_entity_type(
            str(entry.get("name") or ""),
            existing_type=raw_type,
            descriptions=[descriptions, initial_description, str(first_appearance.get("baseline_description") or "")],
        )
        if inferred in {"character", "creature", "object", "location"}:
            if inferred == "character":
                return "character"
            if inferred != "character" and not has_humanoid:
                return inferred
        if self.normalizer.looks_like_character_name(str(entry.get("name") or "")) or has_humanoid:
            return "character"
        if self._contains_marker(haystack, self.CREATURE_MARKERS) and not has_humanoid:
            return "creature"
        return "character"

    def _contains_marker(self, haystack: str, markers: set[str]) -> bool:
        text = str(haystack or "").lower()
        if not text:
            return False
        for marker in markers:
            pattern = r"(?<![a-z0-9])" + re.escape(str(marker).lower()).replace(r"\ ", r"\s+") + r"(?![a-z0-9])"
            if re.search(pattern, text):
                return True
        return False

    def _sql_entity_to_registry_entry(self, entity: SqlEntity) -> dict[str, Any]:
        return {
            "name": entity.canonical_name,
            "entity_type": entity.entity_type,
            "mention_count": entity.mention_count or 0,
            "first_seen": {
                "book_index": entity.first_seen_book_index,
                "chapter_index": entity.first_seen_chapter_index,
                "scene_index": entity.first_seen_scene_index,
            },
            "entity_context": entity.entity_context or "",
            "initial_physical_description": entity.initial_physical_description or {},
            "first_appearance_profile": entity.first_appearance_profile or {},
            "typed_attributes": entity.typed_attributes or {},
            "latest_world_state": entity.latest_world_state or {},
            "narrative_roles": entity.narrative_roles or [],
            "descriptions": entity.descriptions or [],
            "state_changes": entity.state_changes or [],
            "event_links": entity.event_links or [],
            "visual_change_log": entity.visual_change_log or [],
            "analysis_quality_flags": entity.analysis_quality_flags or [],
            "metadata_json": entity.metadata_json or {},
        }

    def _corrected_character_row(self, row: dict[str, Any]) -> dict[str, Any]:
        details = row.get("details") or {}
        profile = normalize_persistent_profile((details.get("persistent_visual_profile") or {}))
        if profile_specificity_score(profile) <= 2:
            profile = promote_persistent_profile_from_visual_changes(profile, details.get("dynamic_visual_changes") or [])
        rebuilt_prompt = compile_character_turnaround_prompt(profile, display_name=str(row.get("entity_name") or ""))
        corrected = dict(row)
        corrected["entity_type"] = "character"
        if rebuilt_prompt:
            corrected["positive_prompt"] = rebuilt_prompt
        corrected["details"] = dict(details)
        corrected["details"]["persistent_visual_profile"] = profile
        return corrected

    def _classify_render_entity_type(self, row: dict[str, Any], *, registry_entry: dict[str, Any]) -> str:
        details = row.get("details") or {}
        profile = details.get("persistent_visual_profile") or {}
        profile_species = str(profile.get("species_or_race") or "").strip().lower()
        profile_role = str(profile.get("role_or_archetype") or "").strip().lower()
        model_safe_identity = str(profile.get("model_safe_identity") or "").strip().lower()
        if self._contains_marker(profile_species, self.CREATURE_MARKERS):
            return "creature"
        if self._contains_marker(profile_role, self.CREATURE_MARKERS):
            return "creature"
        if self._contains_marker(model_safe_identity, self.CREATURE_MARKERS):
            return "creature"
        descriptions = " ".join(
            str(item.get("description") or "")
            for item in (registry_entry.get("descriptions") or [])
            if isinstance(item, dict)
        )
        haystack = " ".join(
            str(value or "")
            for value in [
                row.get("entity_name"),
                row.get("source_evidence"),
                profile_species,
                profile_role,
                model_safe_identity,
                profile.get("fantasy_features"),
                details.get("physical_description"),
                details.get("visible_condition"),
                profile.get("facial_structure"),
                profile.get("distinguishing_marks"),
                details.get("body_language"),
                descriptions,
            ]
        ).lower()
        has_creature = self._contains_marker(haystack, self.CREATURE_MARKERS)
        has_humanoid = self._contains_marker(haystack, self.HUMANOID_MARKERS)
        if has_creature and not has_humanoid:
            return "creature"
        return "character"

    def _resolve_render_name(self, name: str, *, context, seen_names: list[str]) -> str:
        resolved = self.normalizer.resolve_name(name, context=context, expect_character=False) or name
        if resolved == name and len(name.split()) == 1:
            expanded = self.normalizer.expand_short_character_name(name, seen_names)
            if expanded:
                return expanded
        return resolved

    def _should_suppress_generic_label(self, raw_name: str, *, canonical_name: str, registry_entry: dict[str, Any]) -> bool:
        lowered = _slugify(raw_name).replace("-", " ")
        if lowered in self.GENERIC_LABEL_SUPPRESSIONS and raw_name == canonical_name:
            return True
        descriptions = " ".join(
            str(item.get("description") or "")
            for item in (registry_entry.get("descriptions") or [])
            if isinstance(item, dict)
        ).lower()
        if lowered in self.GENERIC_LABEL_SUPPRESSIONS and any(marker in descriptions for marker in self.CREATURE_MARKERS):
            return True
        return False

    def _best_row_for_group(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {}

        def _score(row: dict[str, Any]) -> tuple[int, int, int]:
            details = row.get("details") or {}
            profile = normalize_persistent_profile((details.get("persistent_visual_profile") or {}))
            confidence = {"high": 3, "medium": 2, "low": 1}.get(str(row.get("confidence") or "").lower(), 0)
            prompt_len = len(str(row.get("positive_prompt") or ""))
            return (profile_specificity_score(profile), confidence, prompt_len)

        return sorted(rows, key=_score, reverse=True)[0]

    def _prefer_prompt_row(self, current: dict[str, Any], candidate: dict[str, Any], *, entity_type: str) -> dict[str, Any]:
        if entity_type == "character":
            return self._best_row_for_group([current, candidate])

        def _score(row: dict[str, Any]) -> tuple[int, int]:
            confidence = {"high": 3, "medium": 2, "low": 1}.get(str(row.get("confidence") or "").lower(), 0)
            prompt_len = len(str(row.get("positive_prompt") or "").strip())
            return (confidence, prompt_len)

        return sorted([current, candidate], key=_score, reverse=True)[0]

    def _merge_registry_character_payload(self, row: dict[str, Any], registry_entry: dict[str, Any]) -> dict[str, Any]:
        merged = dict(row)
        details = dict(merged.get("details") or {})
        profile = normalize_persistent_profile(details.get("persistent_visual_profile") or {})
        typed_attributes = (registry_entry.get("first_appearance_profile") or {}).get("typed_attributes") or registry_entry.get("typed_attributes") or {}
        registry_profile = normalize_persistent_profile(
            {
                "role_or_archetype": ", ".join(str(value) for value in (typed_attributes.get("titles_or_roles") or [])[:2]),
                "presence_description": str(
                    ((registry_entry.get("first_appearance_profile") or {}).get("baseline_description"))
                    or ((registry_entry.get("initial_physical_description") or {}).get("description"))
                    or ""
                ).strip(),
                "body_type": ", ".join(str(value) for value in (typed_attributes.get("appearance") or [])[:2]),
                "clothing_description": ", ".join(str(value) for value in (typed_attributes.get("outfit") or [])[:2]),
                "expression": ", ".join(str(value) for value in (typed_attributes.get("body_language") or [])[:1]),
                "equipment_or_signature_items": ", ".join(str(value) for value in (typed_attributes.get("possessions") or [])[:3]),
                "fantasy_features": ", ".join(str(value) for value in (typed_attributes.get("abilities") or [])[:2]),
                "world_aesthetic_cues": ", ".join(str(value) for value in (typed_attributes.get("affiliations") or [])[:2]),
            }
        )
        for key, value in registry_profile.items():
            if key == "lore_terms":
                profile[key] = sorted({*(profile.get(key) or []), *(value or [])})
            elif profile.get(key) in ("", None, [], {}) and value not in ("", None, [], {}):
                profile[key] = value
        rebuilt_prompt = compile_character_turnaround_prompt(profile, display_name=str(merged.get("entity_name") or ""))
        if rebuilt_prompt:
            merged["positive_prompt"] = rebuilt_prompt
        details["persistent_visual_profile"] = profile
        details["typed_attributes"] = typed_attributes
        details["baseline_description"] = str(
            ((registry_entry.get("first_appearance_profile") or {}).get("baseline_description"))
            or ((registry_entry.get("initial_physical_description") or {}).get("description"))
            or details.get("baseline_description")
            or ""
        ).strip()
        details["source"] = details.get("source") or "entity_registry_direct"
        merged["details"] = details
        return merged

    def _build_registry_baseline_prompt_payload(self, entry: dict[str, Any]) -> dict[str, Any] | None:
        entity_name = str(entry.get("name") or "").strip()
        entity_type = str(entry.get("entity_type") or "").strip().lower()
        if not entity_name or entity_type not in {"character", "object", "location", "creature"}:
            return None
        first_seen = entry.get("first_seen") or {}
        baseline_profile = entry.get("first_appearance_profile") or {}
        baseline_description = str(
            baseline_profile.get("baseline_description")
            or ((entry.get("initial_physical_description") or {}).get("description"))
            or ""
        ).strip()
        typed_attributes = baseline_profile.get("typed_attributes") or entry.get("typed_attributes") or {}
        evidence = [
            str(row.get("description") or "").strip()
            for row in (entry.get("descriptions") or [])
            if isinstance(row, dict) and str(row.get("description") or "").strip()
        ]
        if entity_type == "character":
            profile = normalize_persistent_profile(
                {
                    "role_or_archetype": ", ".join(str(value) for value in (typed_attributes.get("titles_or_roles") or [])[:2]),
                    "presence_description": baseline_description or str(entry.get("entity_context") or "").strip(),
                    "body_type": ", ".join(str(value) for value in (typed_attributes.get("appearance") or [])[:2]),
                    "clothing_description": ", ".join(str(value) for value in (typed_attributes.get("outfit") or [])[:2]),
                    "expression": ", ".join(str(value) for value in (typed_attributes.get("body_language") or [])[:1]),
                    "equipment_or_signature_items": ", ".join(str(value) for value in (typed_attributes.get("possessions") or [])[:3]),
                    "fantasy_features": ", ".join(str(value) for value in (typed_attributes.get("abilities") or [])[:2]),
                    "world_aesthetic_cues": ", ".join(str(value) for value in (typed_attributes.get("affiliations") or [])[:2]),
                }
            )
            prompt = compile_character_turnaround_prompt(profile, display_name=entity_name)
        elif entity_type == "location":
            prompt = compile_location_concept_prompt(
                display_name=entity_name,
                baseline_description=baseline_description,
                current_description=baseline_description,
                atmosphere="",
                notable_features=evidence[:5],
                damage_or_restoration_state="",
            )
        else:
            latest_change = ((entry.get("state_changes") or [])[-1] if (entry.get("state_changes") or []) else {}) or {}
            current_state = f"{latest_change.get('attribute', '')}={latest_change.get('new_state', '')}".strip("=")
            prompt = compile_entity_concept_prompt(
                display_name=entity_name,
                entity_type=entity_type,
                baseline_description=baseline_description or str(entry.get("entity_context") or "").strip(),
                current_state=current_state,
                owner_or_associated_characters=(typed_attributes.get("owner_or_holder") or typed_attributes.get("possessions") or []),
            )
        if not str(prompt or "").strip():
            return None
        return {
            "book_index": first_seen.get("book_index"),
            "chapter_index": first_seen.get("chapter_index"),
            "scene_index": first_seen.get("scene_index"),
            "prompt_type": f"initial_{entity_type}_description",
            "entity_name": entity_name,
            "entity_type": entity_type,
            "positive_prompt": str(prompt).strip(),
            "image_edit_prompt": "",
            "source_evidence": evidence[0] if evidence else baseline_description,
            "confidence": "medium" if evidence else "low",
            "details": {
                "persistent_visual_profile": profile if entity_type == "character" else {},
                "baseline_description": baseline_description,
                "typed_attributes": typed_attributes,
                "source": "entity_registry_direct",
            },
        }

    def _preferred_display_name(self, *, canonical_name: str, aliases: list[str], row_names: list[str]) -> str:
        options = [canonical_name, *(aliases or []), *(row_names or [])]
        cleaned: list[str] = []
        for option in options:
            candidate = str(option or "").strip()
            if not candidate:
                continue
            if self.normalizer.is_bad_alias_like_name(candidate):
                continue
            if candidate not in cleaned:
                cleaned.append(candidate)
        if not cleaned:
            return canonical_name

        def _score(name: str) -> tuple[int, int, int, int]:
            tokens = name.split()
            first = tokens[0].rstrip(".").lower() if tokens else ""
            has_title_prefix = 1 if first in self.TITLE_LIKE_PREFIXES else 0
            looks_character = 1 if self.normalizer.looks_like_character_name(name) else 0
            in_rows = 1 if any(name == item for item in row_names) else 0
            return (
                in_rows,
                looks_character,
                len(tokens) - has_title_prefix,
                len(name),
            )

        return sorted(cleaned, key=_score, reverse=True)[0]

    def build_render_manifest(
        self,
        contract_path: str | Path,
        *,
        limit: int = 0,
        overwrite: bool = False,
        negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
        width: int = 1504,
        height: int = 1024,
        steps: int = 12,
        cfg: float = 1.0,
    ) -> dict[str, Any]:
        contract_ref = str(contract_path)
        is_db_ref = contract_ref.startswith("db://book/")
        contract = Path(contract_ref) if not is_db_ref else None
        output_dir = render_output_dir_for_contract(contract_ref)
        images_dir = output_dir / "images"
        output_dir.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(parents=True, exist_ok=True)
        if overwrite:
            for stale in images_dir.glob("*.png"):
                try:
                    stale.unlink()
                except OSError:
                    pass
        prompt_rows = self.collect_entity_visual_prompts(contract_ref, limit=limit)
        renders: list[dict[str, Any]] = []
        for index, row in enumerate(prompt_rows, start=1):
            name = str(row.get("entity_name") or "").strip()
            slug = _slugify(name)
            output_name = f"{index:02d}_{slug}.png"
            image_path = images_dir / output_name
            render_row = {
                "entity_name": name,
                "entity_type": row.get("entity_type") or "character",
                "prompt_type": row.get("prompt_type") or "initial_character_description",
                "visual_bucket": row.get("visual_bucket") or "initial_characters",
                "positive_prompt": str(row.get("positive_prompt") or "").strip(),
                "negative_prompt": negative_prompt,
                "confidence": row.get("confidence") or "medium",
                "book_index": row.get("book_index"),
                "chapter_index": row.get("chapter_index"),
                "scene_index": row.get("scene_index"),
                "source_evidence": row.get("source_evidence") or "",
                "details": row.get("details") or {},
                "workflow_mode": row.get("workflow_mode") or ("character_sheet" if str(row.get("entity_type") or "").lower() == "character" else "default"),
                "output_filename": output_name,
                "output_path": str(image_path),
                "relative_output_path": str(image_path.relative_to(ROOT)),
                "should_render": overwrite or not image_path.exists(),
                "seed": 1000 + index,
                "width": int(row.get("width") or width),
                "height": int(row.get("height") or height),
            }
            renders.append(render_row)
        payload = {
            "contract_path": contract_ref,
            "contract_relative_path": contract_ref if is_db_ref else (str(contract.relative_to(ROOT)) if str(contract).lower().startswith(str(ROOT).lower()) else str(contract)),
            "workflow_mode": "character_sheet",
            "workflow_path": str((ROOT / "modal_comfyui" / "workflows" / "character_sheet_workflow.json").relative_to(ROOT)),
            "pose_image_path": str(POSE_IMAGE.relative_to(ROOT)),
            "output_dir": str(output_dir.relative_to(ROOT)),
            "images_dir": str(images_dir.relative_to(ROOT)),
            "width": width,
            "height": height,
            "steps": steps,
            "cfg": cfg,
            "renders": renders,
        }
        manifest_path = render_manifest_path_for_contract(contract_ref)
        manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def render_from_contract(
        self,
        contract_path: str | Path,
        *,
        limit: int = 0,
        overwrite: bool = False,
        negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
        width: int = 1504,
        height: int = 1024,
        steps: int = 12,
        cfg: float = 1.0,
    ) -> dict[str, Any]:
        manifest = self.build_render_manifest(
            contract_path,
            limit=limit,
            overwrite=overwrite,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            steps=steps,
            cfg=cfg,
        )
        manifest_path = render_manifest_path_for_contract(contract_path)
        report_path = manifest_path.with_name("render_report.json")
        self.sqlite_store.persist_render_manifest(manifest)
        report_rows: list[dict[str, Any]] = []
        total = len(manifest.get("renders") or [])
        for index, row in enumerate(manifest.get("renders") or [], start=1):
            entity_name = str(row.get("entity_name") or f"render_{index}").strip()
            output_path = Path(str(row.get("output_path") or ""))
            render_status = "pending"
            if not row.get("should_render", True) and output_path.exists():
                render_status = "skipped_existing"
                print(f"RENDER_PROGRESS|{index}|{total}|{entity_name}|{render_status}", flush=True)
            else:
                command = [
                    sys.executable,
                    str(RENDER_CLIENT),
                    "--workflow-mode",
                    str(row.get("workflow_mode") or "default"),
                    "--prompt",
                    str(row.get("positive_prompt") or ""),
                    "--negative-prompt",
                    str(row.get("negative_prompt") or negative_prompt),
                    "--seed",
                    str(int(row.get("seed") or (1000 + index))),
                    "--steps",
                    str(int(row.get("steps") or steps)),
                    "--cfg",
                    str(float(row.get("cfg") or cfg)),
                    "--width",
                    str(int(row.get("width") or width)),
                    "--height",
                    str(int(row.get("height") or height)),
                    "--output",
                    str(output_path),
                ]
                if str(row.get("workflow_mode") or "").strip().lower() == "character_sheet":
                    command.extend(["--pose-image-path", str(POSE_IMAGE)])
                print(f"RENDER_PROGRESS|{index}|{total}|{entity_name}|starting", flush=True)
                try:
                    subprocess.run(command, cwd=ROOT, check=True)
                    render_status = "rendered"
                    print(f"RENDER_PROGRESS|{index}|{total}|{entity_name}|{render_status}", flush=True)
                except subprocess.CalledProcessError as exc:
                    render_status = "failed"
                    row["last_error"] = f"render_client exit code {exc.returncode}"
                    print(f"RENDER_PROGRESS|{index}|{total}|{entity_name}|{render_status}|exit={exc.returncode}", flush=True)
                    row["status"] = render_status
                    report_rows.append(dict(row))
                    manifest["renders"][index - 1] = dict(row)
                    manifest["render_report"] = {"renders": report_rows}
                    manifest["manifest_path"] = str(manifest_path.relative_to(ROOT))
                    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
                    report_path.write_text(json.dumps({"renders": report_rows}, ensure_ascii=False, indent=2), encoding="utf-8")
                    self.sqlite_store.persist_render_manifest({"contract_path": manifest["contract_path"], "workflow_path": manifest["workflow_path"], "renders": [row]})
                    raise
            row["status"] = render_status
            if output_path.exists():
                row["output_path"] = str(output_path)
            report_rows.append(dict(row))
            manifest["renders"][index - 1] = dict(row)
            manifest["render_report"] = {"renders": report_rows}
            manifest["manifest_path"] = str(manifest_path.relative_to(ROOT))
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            report_path.write_text(json.dumps({"renders": report_rows}, ensure_ascii=False, indent=2), encoding="utf-8")
            self.sqlite_store.persist_render_manifest({"contract_path": manifest["contract_path"], "workflow_path": manifest["workflow_path"], "renders": [row]})
        manifest["manifest_path"] = str(manifest_path.relative_to(ROOT))
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        report_path.write_text(json.dumps({"renders": report_rows}, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest
