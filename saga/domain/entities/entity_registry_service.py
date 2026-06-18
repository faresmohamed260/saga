import re
from typing import Dict, List, Tuple

from saga.domain.canon_normalization import CanonicalEntityNormalizer

CREATURE_MARKERS = {
    "attor", "suriel", "kelpie", "naga", "bogge", "wyrm", "wolf", "beast", "monster", "creature",
    "animal", "talons", "fangs", "claws", "snout", "muzzle", "fur", "scaled", "scales", "hide",
    "skeletal", "leathery wings", "feathered wings",
}
CHARACTER_BASELINE_ACTION_MARKERS = {
    "carrying", "watching", "walking", "walks", "running", "ran", "standing", "stood", "sitting", "sat",
    "grabbing", "grabbed", "shouting", "yelling", "knocking", "crouching", "hunched", "trembling", "shaking",
    "crying", "terrified", "aggressive", "hostile", "causing", "toward", "towards", "behind", "before",
    "after", "during", "inside", "outside", "near", "beside", "by the", "in the",
}
CHARACTER_BASELINE_NOISE_MARKERS = {
    "implied by presence", "scene context", "appears hostile", "bad temper", "cold and empty gaze",
}
CREATURE_ANATOMY_MARKERS = {
    "talons", "fangs", "claws", "snout", "muzzle", "fur", "scaled", "scales", "hide",
    "skeletal", "forked tongue", "razor-sharp teeth", "taloned feet", "leathery skin",
    "skeletal wings", "feathered wings", "leathery wings",
}
HUMANOID_MARKERS = {
    "human", "humanoid", "man", "woman", "male", "female", "girl", "boy", "lady", "lord", "queen",
    "king", "priestess", "guard", "mercenary", "hunter", "servant", "soldier", "warrior", "attendant",
    "villager", "father", "mother", "sister", "brother", "person",
}

class EntityRegistryService:
    """
    Aggregates entity mentions, descriptions, and state changes across analyzed scenes.
    """

    def build(self, analyzed_scenes: List[Dict]) -> List[Dict]:
        registry: Dict[Tuple[str, str], Dict] = {}

        for scene in sorted(analyzed_scenes, key=self._scene_key):
            scene_ref = {
                "book_index": scene.get("book_index"),
                "chapter_index": scene.get("chapter_index"),
                "scene_index": scene.get("scene_index"),
            }

            for entity in scene.get("entities_present", []):
                name = self._clean_name(entity.get("name", ""))
                entity_type = self._clean_type(entity.get("entity_type", ""))
                if not name or not entity_type:
                    continue
                key = (self._entity_key(name), entity_type)
                entry = registry.setdefault(key, self._new_entry(name, entity_type, scene_ref))
                entry["mention_count"] += 1
                entry["mentions"].append(dict(scene_ref))

            for world_entity in (scene.get("entity_world_state") or {}).get("entities") or []:
                name = self._clean_name(world_entity.get("entity_name", ""))
                entity_type = self._clean_type(world_entity.get("entity_type", ""))
                if not name or not entity_type:
                    continue
                key = (self._entity_key(name), entity_type)
                entry = registry.setdefault(key, self._new_entry(name, entity_type, scene_ref))
                narrative_role = str(world_entity.get("narrative_role") or "").strip()
                if narrative_role:
                    self._append_unique(entry["narrative_roles"], {"value": narrative_role, **scene_ref})
                baseline_description = self._clean_description(world_entity.get("baseline_description", ""))
                if baseline_description:
                    self._append_unique(
                        entry["descriptions"],
                        {
                            "description": baseline_description,
                            "description_type": "stable_trait" if entity_type == "character" else "appearance_note",
                            **scene_ref,
                        },
                    )
                typed_attributes = world_entity.get("typed_attributes") or {}
                persistent_traits = world_entity.get("persistent_traits") or {}
                dynamic_visual_state = world_entity.get("dynamic_visual_state") or {}
                if isinstance(typed_attributes, dict):
                    for attribute_name, values in typed_attributes.items():
                        if not isinstance(values, list):
                            continue
                        bucket = entry.setdefault("typed_attributes", {}).setdefault(attribute_name, [])
                        for value in values:
                            cleaned_value = self._clean_description(value)
                            if not cleaned_value or cleaned_value in bucket:
                                continue
                            bucket.append(cleaned_value)
                if isinstance(persistent_traits, dict):
                    merged_traits = entry.setdefault("persistent_traits", {})
                    for trait_name, value in persistent_traits.items():
                        cleaned_value = self._clean_description(value)
                        if cleaned_value and not self._clean_description(merged_traits.get(trait_name, "")):
                            merged_traits[trait_name] = cleaned_value
                if isinstance(dynamic_visual_state, dict):
                    cleaned_state = {
                        trait_name: self._clean_description(value)
                        for trait_name, value in dynamic_visual_state.items()
                    }
                    cleaned_state = {trait_name: value for trait_name, value in cleaned_state.items() if value}
                    if cleaned_state:
                        self._append_unique(
                            entry.setdefault("scene_visual_states", []),
                            {
                                "state": cleaned_state,
                                **scene_ref,
                            },
                        )
                for change in world_entity.get("state_changes") or []:
                    self._append_unique(entry["state_changes"], {
                        "attribute": str(change.get("attribute") or "").strip(),
                        "previous_state": str(change.get("previous_state") or "").strip(),
                        "new_state": str(change.get("new_state") or "").strip(),
                        "change_type": str(change.get("change_type") or "").strip(),
                        "evidence": str(change.get("evidence") or "").strip(),
                        **scene_ref,
                    })
                source_evidence = [self._clean_description(item) for item in (world_entity.get("source_evidence") or []) if self._clean_description(item)]
                if source_evidence:
                    entry["latest_world_state"] = {
                        "baseline_description": baseline_description,
                        "typed_attributes": typed_attributes if isinstance(typed_attributes, dict) else {},
                        "persistent_traits": persistent_traits if isinstance(persistent_traits, dict) else {},
                        "dynamic_visual_state": dynamic_visual_state if isinstance(dynamic_visual_state, dict) else {},
                        "source_evidence": source_evidence,
                        **scene_ref,
                    }

            location = scene.get("location") or {}
            if location.get("name") and location.get("entity_type") == "location":
                name = self._clean_name(location.get("name", ""))
                key = (self._entity_key(name), "location")
                entry = registry.setdefault(key, self._new_entry(name, "location", scene_ref))
                entry["mention_count"] += 1
                entry["mentions"].append(dict(scene_ref))
                if location.get("description"):
                    entry["descriptions"].append({
                        "description": location["description"],
                        "description_type": "appearance_note",
                        **scene_ref,
                    })

            for description in scene.get("entity_descriptions", []):
                name = self._clean_name(description.get("entity_name", ""))
                entity_type = self._clean_type(description.get("entity_type", ""))
                description_text = self._clean_description(description.get("description", ""))
                description_type = str(description.get("description_type") or "").strip().lower()
                if not name or not entity_type or not description_text:
                    continue
                key = (self._entity_key(name), entity_type)
                entry = registry.setdefault(
                    key,
                    self._new_entry(name, entity_type, scene_ref),
                )
                self._append_unique(entry["descriptions"], {
                    "description": description_text,
                    "description_type": description_type,
                    **scene_ref,
                })

            for change in scene.get("state_changes", []):
                name = self._clean_name(change.get("entity_name", ""))
                entity_type = self._clean_type(change.get("entity_type", ""))
                if not name or not entity_type:
                    continue
                key = (self._entity_key(name), entity_type)
                entry = registry.setdefault(
                    key,
                    self._new_entry(name, entity_type, scene_ref),
                )
                self._append_unique(entry["state_changes"], {
                    "attribute": str(change.get("attribute") or "").strip(),
                    "previous_state": str(change.get("previous_state") or "").strip(),
                    "new_state": str(change.get("new_state") or "").strip(),
                    "change_type": str(change.get("change_type") or "").strip(),
                    "evidence": str(change.get("evidence") or "").strip(),
                    **scene_ref,
                })

            for event in scene.get("events") or []:
                event_entity_names = list(event.get("entities_involved") or []) + list(event.get("characters") or [])
                for name in event_entity_names:
                    cleaned_name = self._clean_name(name)
                    if not cleaned_name:
                        continue
                    existing_key = self._find_existing_key(registry, cleaned_name)
                    if not existing_key:
                        inferred_type = self._infer_event_entity_type(cleaned_name, event, scene)
                        existing_key = (self._entity_key(cleaned_name), inferred_type)
                        registry.setdefault(existing_key, self._new_entry(cleaned_name, inferred_type, scene_ref))
                    entry = registry[existing_key]
                    self._append_unique(entry["event_links"], {
                        "event_id": event.get("event_id", ""),
                        "description": event.get("description", ""),
                        "reason": event.get("reason", ""),
                        "outcome": event.get("outcome", ""),
                        **scene_ref,
                    })

        registry = self._merge_cross_type_duplicates(registry)
        registry = self._merge_alias_like_duplicates(registry)
        output = []
        for entry in registry.values():
            self._finalize_entry(entry)
            output.append(entry)
        return sorted(output, key=lambda item: (item["entity_type"], item["name"].lower()))

    def _new_entry(self, name: str, entity_type: str, scene_ref: Dict) -> Dict:
        return {
            "name": name,
            "entity_type": entity_type,
            "first_seen": dict(scene_ref),
            "mention_count": 0,
            "mentions": [],
            "descriptions": [],
            "state_changes": [],
            "event_links": [],
            "narrative_roles": [],
            "typed_attributes": {},
            "persistent_traits": {},
            "scene_visual_states": [],
            "initial_physical_description": {
                "status": "missing",
                "description": "",
                "source": dict(scene_ref),
                "reason": "No grounded physical description was captured at first appearance.",
            },
            "first_appearance_profile": {
                "status": "missing",
                "baseline_description": "",
                "typed_attributes": {},
                "source": dict(scene_ref),
            },
            "latest_world_state": {},
            "visual_change_log": [],
            "entity_context": "",
            "analysis_quality_flags": [],
        }

    def _scene_key(self, scene: Dict) -> Tuple[int, int, int]:
        return (
            scene.get("book_index", 0),
            scene.get("chapter_index", 0),
            scene.get("scene_index", 0),
        )

    def _clean_name(self, value: str) -> str:
        cleaned = " ".join(str(value or "").strip().split())
        return cleaned

    def _clean_type(self, value: str) -> str:
        cleaned = str(value or "").strip().lower()
        return cleaned if cleaned in {"character", "object", "location", "creature"} else ""

    def _entity_key(self, name: str) -> str:
        normalized = re.sub(r"[^a-z0-9\s'-]+", " ", str(name or "").lower())
        normalized = " ".join(normalized.split())
        for prefix in ("the ", "a ", "an "):
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
        if normalized.endswith("s") and len(normalized) > 4:
            normalized = normalized[:-1]
        return normalized

    def _clean_description(self, value: str) -> str:
        return " ".join(str(value or "").strip().split())

    def _append_unique(self, rows: List[Dict], row: Dict) -> None:
        key = tuple((name, str(row.get(name) or "").strip().lower()) for name in sorted(row))
        for existing in rows:
            existing_key = tuple((name, str(existing.get(name) or "").strip().lower()) for name in sorted(existing))
            if existing_key == key:
                return
        rows.append(row)

    def _find_existing_key(self, registry: Dict[Tuple[str, str], Dict], name: str) -> Tuple[str, str] | None:
        key_name = self._entity_key(name)
        for key in registry:
            if key[0] == key_name:
                return key
        return None

    def _finalize_entry(self, entry: Dict) -> None:
        self._repair_entity_type(entry)
        first_seen = entry.get("first_seen") or {}
        descriptions = entry.get("descriptions") or []
        physical = self._select_initial_physical_description(descriptions, first_seen, entry.get("entity_type", ""))
        if physical:
            entry["initial_physical_description"] = {
                "status": "captured",
                "description": physical.get("description", ""),
                "description_type": physical.get("description_type", ""),
                "source": {
                    "book_index": physical.get("book_index"),
                    "chapter_index": physical.get("chapter_index"),
                    "scene_index": physical.get("scene_index"),
                },
                "reason": "Grounded visual description captured near first appearance.",
            }
            entry["first_appearance_profile"] = {
                "status": "captured",
                "baseline_description": physical.get("description", ""),
                "typed_attributes": entry.get("typed_attributes") or {},
                "persistent_traits": entry.get("persistent_traits") or {},
                "source": {
                    "book_index": physical.get("book_index"),
                    "chapter_index": physical.get("chapter_index"),
                    "scene_index": physical.get("scene_index"),
                },
            }
            if entry.get("entity_type") == "character":
                combined_baseline = self._compose_visual_baseline(entry)
                if combined_baseline:
                    entry["first_appearance_profile"]["baseline_description"] = combined_baseline
                    entry["initial_physical_description"]["description"] = combined_baseline
        else:
            combined_baseline = self._compose_visual_baseline(entry)
            if combined_baseline:
                entry["initial_physical_description"] = {
                    "status": "captured",
                    "description": combined_baseline,
                    "description_type": "stable_trait",
                    "source": dict(first_seen),
                    "reason": "Composed from grounded first-appearance typed attributes.",
                }
                entry["first_appearance_profile"] = {
                    "status": "captured",
                    "baseline_description": combined_baseline,
                    "typed_attributes": entry.get("typed_attributes") or {},
                    "persistent_traits": entry.get("persistent_traits") or {},
                    "source": dict(first_seen),
                }
            else:
                entry.setdefault("analysis_quality_flags", []).append("missing_initial_physical_description")
        visual_changes = []
        for row in descriptions:
            if row.get("description_type") in {"appearance_note", "temporary_condition", "possession"}:
                visual_changes.append(row)
        for row in entry.get("state_changes") or []:
            if row.get("change_type") in {"physical_state", "condition", "possession", "location", "status"}:
                visual_changes.append(row)
        for row in entry.get("scene_visual_states") or []:
            if isinstance(row, dict) and row.get("state"):
                visual_changes.append(row)
        entry["visual_change_log"] = visual_changes
        if not descriptions and not entry.get("state_changes") and not entry.get("event_links"):
            entry.setdefault("analysis_quality_flags", []).append("entity_has_no_detail_evidence")
        entry["entity_context"] = self._entity_context(entry)

    def _repair_entity_type(self, entry: Dict) -> None:
        normalizer = CanonicalEntityNormalizer()
        current_type = str(entry.get("entity_type") or "").strip().lower()
        inferred = normalizer.infer_entity_type(
            str(entry.get("name") or ""),
            existing_type=current_type,
            descriptions=[row.get("description", "") for row in (entry.get("descriptions") or []) if isinstance(row, dict)],
        )
        if current_type == "object" and inferred in {"character", "location"}:
            entry["entity_type"] = inferred
            return
        if current_type == "character" and self._entry_supports_creature(entry):
            entry["entity_type"] = "creature"
            return
        if current_type == "object" and self._entry_supports_creature(entry):
            entry["entity_type"] = "creature"

    def _select_initial_physical_description(self, descriptions: List[Dict], first_seen: Dict, entity_type: str) -> Dict | None:
        first_key = (
            first_seen.get("book_index"),
            first_seen.get("chapter_index"),
            first_seen.get("scene_index"),
        )
        physical_types = {"stable_trait", "appearance_note", "temporary_condition", "possession"}
        candidates = [
            row for row in descriptions
            if row.get("description_type") in physical_types
            and (row.get("book_index"), row.get("chapter_index"), row.get("scene_index")) == first_key
        ]
        if str(entity_type).strip().lower() == "character":
            candidates = [row for row in candidates if self._is_character_baseline_candidate(row)]
        if candidates:
            return sorted(candidates, key=self._description_priority)[0]
        candidates = [row for row in descriptions if row.get("description_type") in physical_types]
        if str(entity_type).strip().lower() == "character":
            candidates = [row for row in candidates if self._is_character_baseline_candidate(row)]
        return sorted(candidates, key=self._description_priority)[0] if candidates else None

    def _description_priority(self, row: Dict) -> Tuple[int, int, int, int]:
        kind = str(row.get("description_type") or "").strip().lower()
        ranking = {
            "stable_trait": 0,
            "appearance_note": 1,
            "temporary_condition": 2,
            "possession": 3,
        }
        description = str(row.get("description") or "").strip()
        return (
            ranking.get(kind, 9),
            int(row.get("book_index") or 0),
            int(row.get("chapter_index") or 0),
            -len(description),
        )

    def _compose_visual_baseline(self, entry: Dict) -> str:
        persistent_traits = entry.get("persistent_traits") or {}
        trait_order = [
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
            "fantasy_features",
            "species_or_race",
            "world_genre_cues",
            "size_class",
            "body_plan",
            "surface_covering",
            "coloration",
            "shape_form",
            "primary_material",
            "location_class",
            "indoor_outdoor",
            "environment_type",
            "architecture_or_terrain_style",
            "dominant_materials",
            "ambient_mood",
            "notable_features",
        ]
        parts: List[str] = []
        for key in trait_order:
            value = self._clean_description(persistent_traits.get(key, ""))
            if value and not self._looks_like_character_baseline_noise(value) and value not in parts:
                parts.append(value)
        if parts:
            return ", ".join(parts[:8])
        typed = entry.get("typed_attributes") or {}
        parts = []
        fallback_keys = ("appearance", "outfit") if entry.get("entity_type") == "character" else ("appearance", "outfit", "body_language", "condition")
        for key in fallback_keys:
            values = self._baseline_values_for_key(key, typed)
            for value in values[:3]:
                if value and not self._looks_like_character_baseline_noise(value) and value not in parts:
                    parts.append(value)
        return ", ".join(parts[:6])

    def _baseline_values_for_key(self, key: str, typed: Dict) -> List[str]:
        values = [
            self._clean_description(value)
            for value in (typed.get(key) or [])
            if self._clean_description(value)
        ]
        if key != "appearance":
            return values
        non_condition = [value for value in values if not self._looks_like_condition_phrase(value)]
        return non_condition or values

    def _looks_like_condition_phrase(self, value: str) -> bool:
        lowered = self._clean_description(value).lower()
        condition_terms = {
            "hungry", "exhausted", "trembling", "shaking", "numb", "cold", "freezing",
            "injured", "bleeding", "bloodied", "wounded", "bruised", "dizzy", "sweating",
            "crying", "tearful", "panting", "dirty", "muddy", "soaked", "burned",
        }
        tokens = set(re.findall(r"[a-z']+", lowered))
        return bool(tokens & condition_terms)

    def _looks_like_character_baseline_noise(self, value: str) -> bool:
        lowered = self._clean_description(value).lower()
        if not lowered:
            return False
        if any(marker in lowered for marker in CHARACTER_BASELINE_NOISE_MARKERS):
            return True
        if self._looks_like_condition_phrase(lowered):
            return True
        return any(marker in lowered for marker in CHARACTER_BASELINE_ACTION_MARKERS)

    def _is_character_baseline_candidate(self, row: Dict) -> bool:
        description = self._clean_description(row.get("description", ""))
        kind = str(row.get("description_type") or "").strip().lower()
        if not description:
            return False
        if kind != "stable_trait":
            return False
        return not self._looks_like_character_baseline_noise(description)

    def _infer_event_entity_type(self, name: str, event: Dict, scene: Dict) -> str:
        if name in (event.get("characters") or []):
            return "character"
        location = scene.get("location") or {}
        if self._entity_key(name) == self._entity_key(location.get("name", "")):
            return "location"
        for entity in scene.get("entities_present") or []:
            if self._entity_key(name) == self._entity_key(entity.get("name", "")):
                return self._clean_type(entity.get("entity_type", "")) or "object"
        return "object"

    def _entity_context(self, entry: Dict) -> str:
        name = entry.get("name", "Entity")
        entity_type = entry.get("entity_type", "entity")
        mention_count = int(entry.get("mention_count") or 0)
        first_seen = entry.get("first_seen") or {}
        first_seen_text = (
            f"book {first_seen.get('book_index', '?')}, "
            f"chapter {first_seen.get('chapter_index', '?')}, "
            f"scene {first_seen.get('scene_index', '?')}"
        )
        if entry.get("descriptions"):
            return f"{name} is tracked as a {entity_type} with grounded descriptive evidence, first seen in {first_seen_text}."
        if entry.get("state_changes"):
            return f"{name} is tracked as a {entity_type} because it undergoes state changes, first seen in {first_seen_text}."
        if entry.get("event_links"):
            return f"{name} is tracked as a {entity_type} because it participates in canon events, first seen in {first_seen_text}."
        return (
            f"{name} is tracked as a {entity_type} from {mention_count} mention(s), first seen in {first_seen_text}. "
            "The analyzer did not capture grounded physical/detail evidence for this entity."
        )

    def _merge_cross_type_duplicates(self, registry: Dict[Tuple[str, str], Dict]) -> Dict[Tuple[str, str], Dict]:
        grouped: Dict[str, List[Tuple[Tuple[str, str], Dict]]] = {}
        for key, entry in registry.items():
            grouped.setdefault(key[0], []).append((key, entry))
        merged_registry: Dict[Tuple[str, str], Dict] = {}
        for grouped_entries in grouped.values():
            if len(grouped_entries) == 1:
                key, entry = grouped_entries[0]
                merged_registry[key] = entry
                continue
            grouped_entries = self._prefer_creature_evidence(grouped_entries)
            grouped_entries = sorted(
                grouped_entries,
                key=lambda item: (
                    self._entity_type_priority(item[1].get("entity_type", "")),
                    self._scene_sort_key(item[1].get("first_seen") or {}),
                    -int(item[1].get("mention_count") or 0),
                ),
            )
            base_key, base_entry = grouped_entries[0]
            for _, other_entry in grouped_entries[1:]:
                base_entry = self._merge_entry_pair(base_entry, other_entry)
            merged_registry[(self._entity_key(base_entry.get("name", "")), base_entry.get("entity_type", ""))] = base_entry
        return merged_registry

    def _merge_alias_like_duplicates(self, registry: Dict[Tuple[str, str], Dict]) -> Dict[Tuple[str, str], Dict]:
        normalizer = CanonicalEntityNormalizer()
        merged_registry = dict(registry)
        type_groups: Dict[str, List[str]] = {}
        for (_, entity_type), entry in merged_registry.items():
            type_groups.setdefault(entity_type, []).append(str(entry.get("name") or ""))

        for entity_type, names in type_groups.items():
            merge_map, _ = normalizer.build_merge_map(names=names, alias_map={})
            for raw_name, target_name in merge_map.items():
                if not raw_name or not target_name or raw_name == target_name:
                    continue
                if not self._can_merge_alias_like_names(raw_name, target_name, entity_type):
                    continue
                source_key = (self._entity_key(raw_name), entity_type)
                target_key = (self._entity_key(target_name), entity_type)
                if source_key == target_key:
                    continue
                source_entry = merged_registry.get(source_key)
                target_entry = merged_registry.get(target_key)
                if not source_entry or not target_entry:
                    continue
                keeper_key, keeper_entry, merged_entry = self._merge_entry_by_priority(source_entry, target_entry)
                merged_registry.pop(source_key, None)
                merged_registry.pop(target_key, None)
                merged_registry[keeper_key] = merged_entry
            if entity_type not in {"character", "creature"}:
                continue
            single_token_index: Dict[str, Tuple[str, str]] = {}
            multi_token_tokens: Dict[str, List[str]] = {}
            for key_name, bucket_type in list(merged_registry.keys()):
                if bucket_type != entity_type:
                    continue
                entry_name = str(merged_registry[(key_name, bucket_type)].get("name") or "")
                tokens = self._entity_key(entry_name).split()
                if len(tokens) == 1 and tokens[0]:
                    single_token_index[tokens[0]] = (key_name, bucket_type)
                elif len(tokens) > 1:
                    for token in set(tokens):
                        multi_token_tokens.setdefault(token, []).append(entry_name)
            for token, source_key in list(single_token_index.items()):
                candidates = sorted(set(multi_token_tokens.get(token) or []), key=lambda item: (len(item.split()), len(item)), reverse=True)
                if len(candidates) != 1:
                    continue
                target_name = candidates[0]
                target_key = (self._entity_key(target_name), entity_type)
                if source_key == target_key:
                    continue
                source_entry = merged_registry.get(source_key)
                target_entry = merged_registry.get(target_key)
                if not source_entry or not target_entry:
                    continue
                keeper_key, _, merged_entry = self._merge_entry_by_priority(source_entry, target_entry)
                merged_registry.pop(source_key, None)
                merged_registry.pop(target_key, None)
                merged_registry[keeper_key] = merged_entry
        return merged_registry

    def _can_merge_alias_like_names(self, source_name: str, target_name: str, entity_type: str) -> bool:
        source_key = self._entity_key(source_name)
        target_key = self._entity_key(target_name)
        if not source_key or not target_key or source_key == target_key:
            return True
        source_tokens = source_key.split()
        target_tokens = target_key.split()
        if entity_type not in {"character", "creature"}:
            return False
        if len(source_tokens) == 1 and source_tokens[0] in target_tokens and len(target_tokens) > 1:
            return True
        if len(target_tokens) == 1 and target_tokens[0] in source_tokens and len(source_tokens) > 1:
            return True
        return False

    def _merge_entry_by_priority(self, left: Dict, right: Dict) -> Tuple[Tuple[str, str], Dict, Dict]:
        left_score = self._merge_preference_score(left)
        right_score = self._merge_preference_score(right)
        if right_score > left_score:
            base, other = right, left
        else:
            base, other = left, right
        merged = self._merge_entry_pair(base, other)
        key = (self._entity_key(merged.get("name", "")), merged.get("entity_type", ""))
        return key, base, merged

    def _merge_preference_score(self, entry: Dict) -> Tuple[int, int, int, int]:
        name = str(entry.get("name") or "")
        name_tokens = len(name.split())
        description_count = len(entry.get("descriptions") or [])
        typed_count = sum(len(values or []) for values in (entry.get("typed_attributes") or {}).values() if isinstance(values, list))
        mention_count = int(entry.get("mention_count") or 0)
        return (name_tokens, description_count + typed_count, mention_count, -self._entity_type_priority(entry.get("entity_type", "")))

    def _prefer_creature_evidence(self, grouped_entries: List[Tuple[Tuple[str, str], Dict]]) -> List[Tuple[Tuple[str, str], Dict]]:
        creature_entry = None
        for key, entry in grouped_entries:
            if str(entry.get("entity_type") or "").strip().lower() == "creature":
                if self._entry_supports_creature(entry):
                    creature_entry = (key, entry)
                    break
        if creature_entry is None:
            return grouped_entries
        upgraded: List[Tuple[Tuple[str, str], Dict]] = []
        for key, entry in grouped_entries:
            entity_type = str(entry.get("entity_type") or "").strip().lower()
            if entity_type == "character" and not self._entry_supports_humanoid(entry):
                entry = {**entry, "entity_type": "creature"}
                key = (key[0], "creature")
            upgraded.append((key, entry))
        return upgraded

    def _entry_supports_creature(self, entry: Dict) -> bool:
        haystack = self._entry_evidence_text(entry)
        if any(marker in haystack for marker in CREATURE_ANATOMY_MARKERS):
            return True
        has_creature = any(marker in haystack for marker in CREATURE_MARKERS)
        has_humanoid = any(marker in haystack for marker in HUMANOID_MARKERS)
        return has_creature and not has_humanoid

    def _entry_supports_humanoid(self, entry: Dict) -> bool:
        haystack = self._entry_evidence_text(entry)
        return any(marker in haystack for marker in HUMANOID_MARKERS)

    def _entry_evidence_text(self, entry: Dict) -> str:
        parts = [str(entry.get("name") or "")]
        for row in entry.get("descriptions") or []:
            parts.append(str(row.get("description") or ""))
        for row in entry.get("state_changes") or []:
            parts.extend([
                str(row.get("attribute") or ""),
                str(row.get("new_state") or ""),
                str(row.get("evidence") or ""),
            ])
        latest = entry.get("latest_world_state") or {}
        parts.extend([
            str(latest.get("baseline_description") or ""),
            " ".join(str(item or "") for item in (latest.get("source_evidence") or [])),
        ])
        typed = entry.get("typed_attributes") or {}
        if isinstance(typed, dict):
            for values in typed.values():
                if isinstance(values, list):
                    parts.extend(str(value or "") for value in values)
        return " ".join(part for part in parts if part).lower()

    def _merge_entry_pair(self, base: Dict, other: Dict) -> Dict:
        for row in other.get("mentions") or []:
            self._append_unique(base["mentions"], row)
        base["mention_count"] = len(base.get("mentions") or [])
        for row in other.get("descriptions") or []:
            self._append_unique(base["descriptions"], row)
        for row in other.get("state_changes") or []:
            self._append_unique(base["state_changes"], row)
        for row in other.get("event_links") or []:
            self._append_unique(base["event_links"], row)
        for row in other.get("narrative_roles") or []:
            self._append_unique(base["narrative_roles"], row)
        base["typed_attributes"] = self._merge_typed_attributes(
            base.get("typed_attributes") or {},
            other.get("typed_attributes") or {},
        )
        if self._scene_sort_key(other.get("first_seen") or {}) < self._scene_sort_key(base.get("first_seen") or {}):
            base["first_seen"] = dict(other.get("first_seen") or {})
        return base

    def _merge_typed_attributes(self, left: Dict, right: Dict) -> Dict:
        merged = {key: list(values) for key, values in left.items()}
        for key, values in right.items():
            bucket = merged.setdefault(key, [])
            for value in values or []:
                cleaned = self._clean_description(value)
                if cleaned and cleaned not in bucket:
                    bucket.append(cleaned)
        return merged

    def _entity_type_priority(self, entity_type: str) -> int:
        priorities = {"character": 0, "creature": 1, "location": 2, "object": 3}
        return priorities.get(str(entity_type or "").strip().lower(), 99)

    def _scene_sort_key(self, scene_ref: Dict) -> Tuple[int, int, int]:
        return (
            int(scene_ref.get("book_index") or 0),
            int(scene_ref.get("chapter_index") or 0),
            int(scene_ref.get("scene_index") or 0),
        )
