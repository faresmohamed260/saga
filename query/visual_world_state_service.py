from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.pipeline_contract import (
    build_entity_registry,
    build_event_ledger,
    build_formal_character_profiles,
    build_state_result,
    build_timeline,
    build_character_timelines,
    normalize_character_timelines,
    rebuild_resolved_scene_analyses,
)
from query.target_character_state_service import TargetCharacterStateService, _target_scope_label
from redesign_lab.identity.identity_provider import resolve_identity_provider_input


def _scene_key(book_index: int, chapter_index: int, scene_index: int) -> tuple[int, int, int]:
    return int(book_index or 0), int(chapter_index or 0), int(scene_index or 0)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", _norm(text))
    return slug.strip("_") or "entity"


def _dedupe_strings(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    rows: List[str] = []
    for value in values or []:
        text = str(value or "").strip()
        key = _norm(text)
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(text)
    return rows


class VisualWorldStateService:
    CHARACTER_NOISE = {
        "velaris",
        "fae",
        "spring court",
        "starfall",
        "married",
        "leather",
        "couldn",
        "had",
        "never",
        "flame",
        "lightning",
        "siphons",
        "cassian he",
        "lord cassian cassian",
        "feyre azriel",
        "elain lucien",
    }
    CLOTHING_TERMS = {
        "coat", "cloak", "dress", "gown", "armor", "armour", "boots", "boot", "shirt",
        "tunic", "apron", "robes", "robe", "leggings", "sweater", "jacket", "leathers",
        "nightgown", "nightclothes", "cloak", "shirt", "sleeves", "cloak", "cloak",
    }
    INJURY_TERMS = {
        "blood", "bleeding", "bloodied", "bruise", "bruised", "wound", "wounded", "injured",
        "bandaged", "healed", "healing", "broken", "gash", "scar", "swelling", "limping",
        "limp", "unconscious", "conscious", "trembling", "fearful", "exhausted",
    }
    BODY_TERMS = {
        "expression", "posture", "bowing", "smile", "smirk", "grin", "stare", "stared",
        "glance", "glared", "eyes wide", "trembling", "shiver", "feline delight", "protective stare",
    }
    APPEARANCE_TERMS = {
        "hair", "eyes", "face", "skin", "hands", "hand", "freckled", "golden-haired",
        "dark-haired", "brown-eyed", "violet eyes", "masked", "scarred", "pale face",
        "dark handsome", "beautiful", "claws", "fangs", "fur", "wings", "tattoo",
    }
    TRANSFORMATION_TERMS = {
        "wings", "wing", "form", "beast", "claws", "tattoo", "bargain tattoo", "siphon",
        "glamour", "mask", "made", "shadow", "magic", "transforms", "transformation",
    }
    ATMOSPHERE_TERMS = {
        "snow", "icy", "cold", "warm", "dark", "mist", "wind", "firelit", "blood-splattered",
        "sunlight", "golden light", "night", "storm", "murky", "scarred", "cozy",
    }
    DAMAGE_TERMS = {
        "broken", "war-torn", "blood-splattered", "scarred", "ruined", "destroyed",
        "restored", "repaired", "healing",
    }
    WEAPON_TERMS = {"sword", "dagger", "blade", "knife", "bow", "arrow", "spear", "axe"}
    MAGICAL_ARTIFACT_TERMS = {"cauldron", "crown", "mask", "harp", "trove", "stone", "orb", "siphon"}

    def __init__(self) -> None:
        self.target_state_service = TargetCharacterStateService()

    def build_visual_world_state(
        self,
        *,
        contract_paths: List[str | Path],
        target_point: Dict[str, Any],
        identity_json_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        if not contract_paths:
            raise ValueError("At least one contract path is required.")
        normalized_target = self.target_state_service.normalize_target_point(target_point)
        contracts = [json.loads(Path(path).read_text(encoding="utf-8")) for path in contract_paths]
        books: List[Dict[str, Any]] = []
        for contract in contracts:
            books.extend(((contract.get("inputs") or {}).get("books") or []))

        if identity_json_path:
            provider = resolve_identity_provider_input(
                provider_mode="booknlp_clean",
                input_json=identity_json_path,
                book_inputs=books or None,
            )
            try:
                identity_result = provider.build_identity_result_compat(book_inputs=books or None)
                pipeline_identity = provider.build_pipeline_identity(book_inputs=books or None)
            except TypeError:
                identity_result = provider.build_identity_result_compat()
                pipeline_identity = provider.build_pipeline_identity()
        else:
            identity_result = (contracts[-1].get("outputs") or {}).get("identity_result") or {"alias_map": {}}
            pipeline_identity = (contracts[-1].get("outputs") or {}).get("pipeline_identity") or {}

        scene_analyses: List[Dict[str, Any]] = []
        for contract in contracts:
            scene_analyses.extend(((contract.get("outputs") or {}).get("scene_analyses") or []))
        resolved_scenes = rebuild_resolved_scene_analyses(scene_analyses, identity_result)
        filtered_scenes = self.target_state_service._filter_scenes(resolved_scenes, normalized_target)
        scene_lookup = {
            _scene_key(scene.get("book_index", 0), scene.get("chapter_index", 0), scene.get("scene_index", 0)): scene
            for scene in filtered_scenes
        }
        state_result = build_state_result(filtered_scenes)
        timeline = build_timeline(filtered_scenes)
        event_ledger = build_event_ledger(filtered_scenes, timeline, {"graph": {"events": []}})
        entity_registry = build_entity_registry(filtered_scenes)
        character_timelines = build_character_timelines(timeline)
        character_timelines = normalize_character_timelines(character_timelines, identity_result)
        character_profiles = build_formal_character_profiles(
            character_timelines,
            entity_registry,
            state_result,
            identity_result,
            filtered_scenes,
        )

        alias_map = identity_result.get("alias_map") or {}
        alias_index = { _norm(alias): canonical for canonical, aliases in alias_map.items() for alias in [canonical, *(aliases or [])] if _norm(alias) }
        registry_by_name = {
            (_norm(item.get("name") or ""), item.get("entity_type") or ""): item
            for item in entity_registry
        }
        latest_state_by_name = {
            (_norm(item.get("entity_name") or ""), item.get("entity_type") or ""): item
            for item in (state_result.get("latest_state") or [])
        }
        profiles_by_name = {
            _norm(item.get("canonical_name") or ""): item
            for item in character_profiles
            if item.get("canonical_name")
        }

        character_visual_states, character_noise = self._build_character_visual_states(
            pipeline_identity=pipeline_identity,
            filtered_scenes=filtered_scenes,
            registry_by_name=registry_by_name,
            latest_state_by_name=latest_state_by_name,
            profiles_by_name=profiles_by_name,
            alias_index=alias_index,
        )
        entity_visual_states, entity_noise = self._build_entity_visual_states(
            filtered_scenes=filtered_scenes,
            scene_lookup=scene_lookup,
            entity_registry=entity_registry,
            latest_state_by_name=latest_state_by_name,
        )
        location_visual_states, location_noise = self._build_location_visual_states(
            filtered_scenes=filtered_scenes,
            scene_lookup=scene_lookup,
            entity_registry=entity_registry,
        )
        missing_visual = [
            row.get("display_name", "")
            for row in character_visual_states
            if row.get("confidence") == "low"
        ]

        return {
            "target_point": normalized_target.to_dict(),
            "character_visual_states": character_visual_states,
            "entity_visual_states": entity_visual_states,
            "location_visual_states": location_visual_states,
            "diagnostics": {
                "source_scene_count": len(resolved_scenes),
                "target_filtered_scene_count": len(filtered_scenes),
                "character_visual_state_count": len(character_visual_states),
                "entity_visual_state_count": len(entity_visual_states),
                "location_visual_state_count": len(location_visual_states),
                "missing_visual_evidence": missing_visual[:40],
                "noisy_entries_flagged": character_noise + entity_noise + location_noise,
                "target_scope": _target_scope_label(normalized_target.to_dict()),
                "identity_provider": identity_result.get("identity_provider") or "booknlp_clean",
            },
        }

    def _build_character_visual_states(
        self,
        *,
        pipeline_identity: Dict[str, Any],
        filtered_scenes: List[Dict[str, Any]],
        registry_by_name: Dict[Tuple[str, str], Dict[str, Any]],
        latest_state_by_name: Dict[Tuple[str, str], Dict[str, Any]],
        profiles_by_name: Dict[str, Dict[str, Any]],
        alias_index: Dict[str, str],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        rows: List[Dict[str, Any]] = []
        noise: List[Dict[str, Any]] = []
        for character in pipeline_identity.get("characters") or []:
            display_name = str(character.get("display_name") or "").strip()
            if not display_name:
                continue
            lowered = _norm(display_name)
            if lowered in self.CHARACTER_NOISE:
                noise.append({"entry": display_name, "classification": "character_noise", "action": "suppressed"})
                continue
            registry_entry = registry_by_name.get((lowered, "character")) or {}
            latest = (latest_state_by_name.get((lowered, "character")) or {}).get("attributes", {})
            profile = profiles_by_name.get(lowered) or {}
            evidence = self._character_visual_evidence(display_name, filtered_scenes, alias_index, registry_entry, latest, profile)
            if not evidence:
                rows.append(
                    {
                        "character_id": character.get("id") or f"char_{_slug(display_name)}",
                        "display_name": display_name,
                        "state_scope": "",
                        "baseline_description": str(profile.get("core_description") or ""),
                        "current_appearance": "",
                        "clothing_or_outfit": "",
                        "injuries_or_physical_condition": "",
                        "body_language_or_expression": "",
                        "magical_or_physical_transformations": [],
                        "recent_visual_changes": [],
                        "evidence": [],
                        "confidence": "low",
                        "risk_flags": ["sparse_visual_evidence"],
                    }
                )
                continue
            rows.append(
                {
                    "character_id": character.get("id") or f"char_{_slug(display_name)}",
                    "display_name": display_name,
                    "state_scope": "",
                    "baseline_description": evidence.get("baseline_description", ""),
                    "current_appearance": evidence.get("current_appearance", ""),
                    "clothing_or_outfit": evidence.get("clothing_or_outfit", ""),
                    "injuries_or_physical_condition": evidence.get("injuries_or_physical_condition", ""),
                    "body_language_or_expression": evidence.get("body_language_or_expression", ""),
                    "magical_or_physical_transformations": evidence.get("magical_or_physical_transformations", []),
                    "recent_visual_changes": evidence.get("recent_visual_changes", []),
                    "evidence": evidence.get("evidence", []),
                    "confidence": evidence.get("confidence", "low"),
                    "risk_flags": evidence.get("risk_flags", []),
                }
            )
        return rows, noise

    def _character_visual_evidence(
        self,
        display_name: str,
        filtered_scenes: List[Dict[str, Any]],
        alias_index: Dict[str, str],
        registry_entry: Dict[str, Any],
        latest: Dict[str, Any],
        profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        evidence_rows: List[Dict[str, Any]] = []
        baseline_candidates: List[str] = []
        appearance_candidates: List[Tuple[tuple[int, int, int], str]] = []
        clothing_candidates: List[Tuple[tuple[int, int, int], str]] = []
        injury_candidates: List[Tuple[tuple[int, int, int], str]] = []
        body_candidates: List[Tuple[tuple[int, int, int], str]] = []
        transformation_candidates: List[Tuple[tuple[int, int, int], str]] = []
        visual_changes: List[Tuple[tuple[int, int, int], str]] = []

        for row in registry_entry.get("descriptions") or []:
            text = str(row.get("description") or "").strip()
            if not text:
                continue
            ref = _scene_key(row.get("book_index", 0), row.get("chapter_index", 0), row.get("scene_index", 0))
            evidence_rows.append(self._evidence_row(row, source="entity_description", text=text))
            desc_type = str(row.get("description_type") or "")
            if desc_type == "stable_trait":
                baseline_candidates.append(text)
            categories = self._character_description_categories(text)
            if "appearance" in categories:
                appearance_candidates.append((ref, text))
            if "clothing" in categories:
                clothing_candidates.append((ref, text))
            if "injury" in categories:
                injury_candidates.append((ref, text))
            if "body" in categories:
                body_candidates.append((ref, text))
            if "transformation" in categories:
                transformation_candidates.append((ref, text))

        for key, value in (latest or {}).items():
            text = f"{key}={value}"
            if not str(value or "").strip():
                continue
            categories = self._character_state_categories(key, str(value))
            if not categories:
                continue
            evidence_rows.append({"book_index": None, "chapter": None, "scene_id": "", "source": "latest_state", "text": text})
            if "appearance" in categories:
                appearance_candidates.append(((10**9, 10**9, 10**9), text))
            if "clothing" in categories:
                clothing_candidates.append(((10**9, 10**9, 10**9), text))
            if "injury" in categories:
                injury_candidates.append(((10**9, 10**9, 10**9), text))
            if "body" in categories:
                body_candidates.append(((10**9, 10**9, 10**9), text))
            if "transformation" in categories:
                transformation_candidates.append(((10**9, 10**9, 10**9), text))

        for row in profile.get("state_history") or []:
            key = str(row.get("attribute") or "")
            value = str(row.get("new_state") or "")
            if not value:
                continue
            categories = self._character_state_categories(key, value)
            if not categories:
                continue
            ref = _scene_key(row.get("book_index", 0), row.get("chapter_index", 0), row.get("scene_index", 0))
            summary = f"{key}={value}"
            evidence_rows.append(self._evidence_row(row, source="state_transition", text=summary))
            visual_changes.append((ref, summary))
            if "appearance" in categories:
                appearance_candidates.append((ref, summary))
            if "clothing" in categories:
                clothing_candidates.append((ref, summary))
            if "injury" in categories:
                injury_candidates.append((ref, summary))
            if "body" in categories:
                body_candidates.append((ref, summary))
            if "transformation" in categories:
                transformation_candidates.append((ref, summary))

        if profile.get("core_description"):
            baseline_candidates.append(str(profile.get("core_description") or ""))
        for trait in profile.get("traits") or []:
            text = str(trait or "").strip()
            if not text:
                continue
            categories = self._character_description_categories(text)
            if "appearance" in categories and not baseline_candidates:
                baseline_candidates.append(text)

        baseline = baseline_candidates[0] if baseline_candidates else ""
        current_appearance = self._latest_text(appearance_candidates)
        clothing = self._latest_text(clothing_candidates)
        injuries = self._latest_text(injury_candidates)
        body = self._latest_text(body_candidates)
        transformations = _dedupe_strings(text for _, text in transformation_candidates)[-6:]
        recent_changes = [text for _, text in sorted(visual_changes, key=lambda item: item[0], reverse=True)[:6]]

        risk_flags: List[str] = []
        if not evidence_rows:
            risk_flags.append("sparse_visual_evidence")
        if not current_appearance and baseline:
            risk_flags.append("baseline_only")
        confidence = "high" if len(evidence_rows) >= 6 else "medium" if len(evidence_rows) >= 3 else "low"
        if len(evidence_rows) < 2:
            risk_flags.append("sparse_visual_evidence")

        return {
            "baseline_description": baseline,
            "current_appearance": current_appearance,
            "clothing_or_outfit": clothing,
            "injuries_or_physical_condition": injuries,
            "body_language_or_expression": body,
            "magical_or_physical_transformations": transformations,
            "recent_visual_changes": recent_changes,
            "evidence": evidence_rows[:16],
            "confidence": confidence,
            "risk_flags": _dedupe_strings(risk_flags),
        }

    def _build_entity_visual_states(
        self,
        *,
        filtered_scenes: List[Dict[str, Any]],
        scene_lookup: Dict[tuple[int, int, int], Dict[str, Any]],
        entity_registry: List[Dict[str, Any]],
        latest_state_by_name: Dict[Tuple[str, str], Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        rows: List[Dict[str, Any]] = []
        noise: List[Dict[str, Any]] = []
        for item in entity_registry:
            entity_type = str(item.get("entity_type") or "")
            if entity_type in {"character", "location"}:
                continue
            display_name = str(item.get("name") or "").strip()
            if not display_name:
                continue
            if _norm(display_name) in self.CHARACTER_NOISE:
                noise.append({"entry": display_name, "classification": "entity_noise", "action": "suppressed"})
                continue
            latest = (latest_state_by_name.get((_norm(display_name), entity_type)) or {}).get("attributes", {})
            evidence_rows = []
            for desc in item.get("descriptions") or []:
                text = str(desc.get("description") or "").strip()
                if text:
                    evidence_rows.append(self._evidence_row(desc, source="entity_description", text=text))
            for change in item.get("state_changes") or []:
                text = f"{change.get('attribute', '')}={change.get('new_state', '')}".strip("=")
                if text:
                    evidence_rows.append(self._evidence_row(change, source="state_transition", text=text))
            related_characters = self._associated_characters_for_entity(display_name, filtered_scenes)
            current_state = self._entity_current_state(item, latest)
            state_changes = [
                f"{change.get('attribute', '')}={change.get('new_state', '')}".strip("=")
                for change in (item.get("state_changes") or [])[-6:]
                if str(change.get("new_state") or "").strip()
            ]
            rows.append(
                {
                    "entity_id": f"ent_{_slug(display_name)}",
                    "display_name": display_name,
                    "entity_type": self._refine_entity_type(display_name, entity_type, item),
                    "baseline_description": self._baseline_description(item),
                    "current_state": current_state,
                    "location": self._latest_scene_location_for_evidence(evidence_rows, scene_lookup),
                    "owner_or_associated_characters": related_characters,
                    "state_changes": state_changes,
                    "evidence": evidence_rows[:16],
                    "confidence": "high" if len(evidence_rows) >= 4 else "medium" if len(evidence_rows) >= 2 else "low",
                    "risk_flags": ["sparse_visual_evidence"] if len(evidence_rows) < 2 else [],
                }
            )
        return rows, noise

    def _build_location_visual_states(
        self,
        *,
        filtered_scenes: List[Dict[str, Any]],
        scene_lookup: Dict[tuple[int, int, int], Dict[str, Any]],
        entity_registry: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        grouped: Dict[str, Dict[str, Any]] = {}
        noise: List[Dict[str, Any]] = []
        for scene in filtered_scenes:
            location = scene.get("location") or {}
            name = str(location.get("name") or "").strip()
            if not name:
                continue
            key = _norm(name)
            entry = grouped.setdefault(key, {"name": name, "descriptions": [], "characters": [], "scene_refs": []})
            desc = str(location.get("description") or "").strip()
            if desc:
                entry["descriptions"].append({
                    "description": desc,
                    "book_index": scene.get("book_index"),
                    "chapter_index": scene.get("chapter_index"),
                    "scene_index": scene.get("scene_index"),
                })
            entry["characters"].extend([row.get("name") for row in scene.get("canonical_characters") or [] if row.get("name")])
            entry["scene_refs"].append(_scene_key(scene.get("book_index", 0), scene.get("chapter_index", 0), scene.get("scene_index", 0)))

        for reg in entity_registry:
            if str(reg.get("entity_type") or "") != "location":
                continue
            name = str(reg.get("name") or "").strip()
            if not name:
                continue
            key = _norm(name)
            entry = grouped.setdefault(key, {"name": name, "descriptions": [], "characters": [], "scene_refs": []})
            for desc in reg.get("descriptions") or []:
                if str(desc.get("description") or "").strip():
                    entry["descriptions"].append(desc)
                    entry["scene_refs"].append(_scene_key(desc.get("book_index", 0), desc.get("chapter_index", 0), desc.get("scene_index", 0)))

        rows: List[Dict[str, Any]] = []
        for key, item in grouped.items():
            display_name = item["name"]
            descriptions = item.get("descriptions") or []
            baseline = str(descriptions[0].get("description") or "") if descriptions else ""
            latest = str(descriptions[-1].get("description") or "") if descriptions else ""
            atmosphere = self._extract_atmosphere(latest or baseline)
            recent_changes = _dedupe_strings(desc.get("description") for desc in descriptions[-4:] if desc.get("description"))
            damage_state = self._damage_state(latest or baseline)
            evidence = [self._evidence_row(desc, source="location_description", text=str(desc.get("description") or "")) for desc in descriptions if str(desc.get("description") or "").strip()]
            rows.append(
                {
                    "location_id": f"loc_{_slug(display_name)}",
                    "display_name": display_name,
                    "baseline_description": baseline,
                    "current_description": latest or baseline,
                    "atmosphere": atmosphere,
                    "notable_features": recent_changes[:5],
                    "damage_or_restoration_state": damage_state,
                    "associated_characters": _dedupe_strings(item.get("characters") or [])[:12],
                    "recent_changes": recent_changes,
                    "evidence": evidence[:16],
                    "confidence": "high" if len(evidence) >= 4 else "medium" if len(evidence) >= 2 else "low",
                    "risk_flags": ["sparse_visual_evidence"] if len(evidence) < 2 else [],
                }
            )
        return rows, noise

    def _character_description_categories(self, text: str) -> set[str]:
        lowered = _norm(text)
        categories: set[str] = set()
        if any(term in lowered for term in self.APPEARANCE_TERMS):
            categories.add("appearance")
        if any(term in lowered for term in self.CLOTHING_TERMS):
            categories.add("clothing")
        if any(term in lowered for term in self.INJURY_TERMS):
            categories.add("injury")
        if any(term in lowered for term in self.BODY_TERMS):
            categories.add("body")
        if any(term in lowered for term in self.TRANSFORMATION_TERMS):
            categories.add("transformation")
        return categories

    def _character_state_categories(self, key: str, value: str) -> set[str]:
        lowered = _norm(f"{key} {value}")
        categories: set[str] = set()
        if any(term in lowered for term in self.CLOTHING_TERMS) or key in {"clothing", "appearance_note"}:
            categories.add("clothing")
        if any(term in lowered for term in self.INJURY_TERMS) or key in {"physical_state", "temporary_condition", "condition", "hand_condition", "status"}:
            categories.add("injury")
        if any(term in lowered for term in self.BODY_TERMS) or key in {"posture", "expression", "emotional_state"}:
            categories.add("body")
        if any(term in lowered for term in self.APPEARANCE_TERMS) or key in {"appearance", "appearance_note"}:
            categories.add("appearance")
        if any(term in lowered for term in self.TRANSFORMATION_TERMS) or key in {"form", "wings", "tattoo", "glamour", "magic", "power_status"}:
            categories.add("transformation")
        return categories

    def _evidence_row(self, row: Dict[str, Any], *, source: str, text: str) -> Dict[str, Any]:
        scene_id = ""
        if row.get("book_index") is not None and row.get("chapter_index") is not None and row.get("scene_index") is not None:
            scene_id = f"b{row.get('book_index')}_c{row.get('chapter_index')}_s{row.get('scene_index')}"
        return {
            "book_index": row.get("book_index"),
            "chapter": row.get("chapter_index"),
            "scene_id": scene_id,
            "source": source,
            "text": text,
        }

    def _latest_text(self, rows: List[Tuple[tuple[int, int, int], str]]) -> str:
        if not rows:
            return ""
        rows = sorted(rows, key=lambda item: item[0])
        return rows[-1][1]

    def _baseline_description(self, registry_entry: Dict[str, Any]) -> str:
        descriptions = registry_entry.get("descriptions") or []
        for desc in descriptions:
            if str(desc.get("description_type") or "") == "stable_trait" and str(desc.get("description") or "").strip():
                return str(desc.get("description") or "").strip()
        for desc in descriptions:
            if str(desc.get("description") or "").strip():
                return str(desc.get("description") or "").strip()
        return ""

    def _entity_current_state(self, registry_entry: Dict[str, Any], latest: Dict[str, Any]) -> str:
        for key, value in latest.items():
            text = f"{key}={value}"
            if str(value or "").strip():
                return text
        changes = registry_entry.get("state_changes") or []
        if changes:
            latest_change = changes[-1]
            return f"{latest_change.get('attribute', '')}={latest_change.get('new_state', '')}".strip("=")
        descriptions = registry_entry.get("descriptions") or []
        if descriptions:
            return str(descriptions[-1].get("description") or "")
        return ""

    def _associated_characters_for_entity(self, display_name: str, scenes: List[Dict[str, Any]]) -> List[str]:
        names: List[str] = []
        target = _norm(display_name)
        for scene in scenes:
            hit = False
            for entity in scene.get("entities_present") or []:
                if _norm(entity.get("name") or "") == target:
                    hit = True
                    break
            if not hit:
                for row in scene.get("entity_descriptions") or []:
                    if _norm(row.get("entity_name") or "") == target:
                        hit = True
                        break
            if not hit:
                continue
            names.extend([item.get("name") for item in scene.get("canonical_characters") or [] if item.get("name")])
        return _dedupe_strings(names)

    def _refine_entity_type(self, display_name: str, entity_type: str, registry_entry: Dict[str, Any]) -> str:
        lowered = _norm(" ".join([display_name] + [str(d.get("description") or "") for d in (registry_entry.get("descriptions") or [])]))
        if entity_type == "creature":
            return "creature"
        if any(term in lowered for term in self.WEAPON_TERMS):
            return "weapon"
        if any(term in lowered for term in self.MAGICAL_ARTIFACT_TERMS):
            return "magical_artifact"
        if entity_type == "object":
            return "object"
        return entity_type or "unknown"

    def _latest_scene_location_for_evidence(self, evidence_rows: List[Dict[str, Any]], scene_lookup: Dict[tuple[int, int, int], Dict[str, Any]]) -> str:
        latest_ref: Optional[tuple[int, int, int]] = None
        for row in evidence_rows:
            if row.get("book_index") is None:
                continue
            ref = _scene_key(row.get("book_index", 0), row.get("chapter", 0), int(str(row.get("scene_id") or "0").split("_s")[-1]) if "_s" in str(row.get("scene_id") or "") else 0)
            if latest_ref is None or ref > latest_ref:
                latest_ref = ref
        if latest_ref is None:
            return ""
        scene = scene_lookup.get(latest_ref) or {}
        return str(((scene.get("location") or {}).get("name")) or "")

    def _extract_atmosphere(self, text: str) -> str:
        lowered = _norm(text)
        matches = [term for term in self.ATMOSPHERE_TERMS if term in lowered]
        return ", ".join(matches[:4])

    def _damage_state(self, text: str) -> str:
        lowered = _norm(text)
        matches = [term for term in self.DAMAGE_TERMS if term in lowered]
        return ", ".join(matches[:3])
