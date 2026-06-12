from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


class ComfyUIPromptPackService:
    MODE_CHARACTER_SHEET = "character_sheet"
    MODE_SCENE_PROMPT = "scene_prompt"
    MODE_LOCATION_SHEET = "location_sheet"
    MODE_OBJECT_SHEET = "object_sheet"
    MODE_FULL_PROMPT_PACK = "full_prompt_pack"
    MODES = {
        MODE_CHARACTER_SHEET,
        MODE_SCENE_PROMPT,
        MODE_LOCATION_SHEET,
        MODE_OBJECT_SHEET,
        MODE_FULL_PROMPT_PACK,
    }

    NOISY_CHARACTER_ENTRIES = {
        "had",
        "couldn",
        "never",
        "married",
        "leather",
        "high king",
        "high queen",
        "lord cassian cassian",
        "cassian he",
        "feyre azriel",
        "elain lucien",
        "nesta archeron nesta",
        "high fae nesta",
        "lady nesta",
    }
    CHARACTER_ALIAS_MERGES = {
        "rhys": "Rhysand",
        "rhysand": "Rhysand",
        "az": "Azriel",
        "azriel": "Azriel",
        "mor": "Morrigan",
        "morrigan": "Morrigan",
        "tam": "Tamlin",
        "tamlin": "Tamlin",
        "feyre": "Feyre",
        "feyre archeron": "Feyre",
        "lady feyre": "Feyre",
        "nesta": "Nesta",
        "nesta archeron": "Nesta",
        "archeron nesta": "Nesta",
        "lady nesta": "Nesta",
        "high fae nesta": "Nesta",
        "nesta archeron nesta": "Nesta",
        "elain": "Elain",
        "elain archeron": "Elain",
        "lady elain": "Elain",
        "lucien": "Lucien",
        "lucien vanserra": "Lucien",
        "clare": "Clare Beddor",
        "clare beddor": "Clare Beddor",
        "bone carver": "Bone Carver",
        "carver": "Bone Carver",
    }
    LOCATION_LIKE_CHARACTER_ENTRIES = {
        "ramiel",
        "hewn city",
        "house of wind",
        "spring court",
        "velaris",
        "vallahan",
        "oorid",
        "sangravah",
    }
    GROUP_ENTRIES = {"valkyrie", "valkyries", "fae", "illyrians", "high fae nesta"}
    OBJECT_CHARACTER_REDIRECTS = {
        "ataraxia",
        "mask",
        "crown",
        "harp",
        "silver majesty",
        "gwydion",
        "meallan",
    }
    LOCATION_ENTITY_REDIRECTS = {"ramiel", "hewn city", "house of wind", "house", "spring court", "velaris"}
    GENERIC_NEGATIVE_PROMPTS = {
        "character_portrait": "low quality, blurry, distorted anatomy, extra limbs, duplicate face, bad hands, unreadable text, watermark, logo, cropped face",
        "character_sheet": "low quality, blurry, distorted anatomy, extra limbs, duplicate body, bad hands, unreadable text, watermark, logo, cropped feet, inconsistent outfit",
        "location": "low quality, blurry, flat lighting, distorted perspective, duplicate architecture, watermark, logo, unreadable text, oversaturated clutter",
        "object": "low quality, blurry, distorted shape, extra parts, floating artifacts, watermark, logo, unreadable text, cropped object",
        "scene": "low quality, blurry, distorted anatomy, extra limbs, duplicate face, bad hands, unreadable text, watermark, logo, cropped figures, inconsistent wings",
    }
    APPEARANCE_HINTS = {
        "hair", "eyes", "face", "skin", "freckles", "freckled", "scar", "scarred", "pale", "golden", "dark-haired",
        "hazel", "violet", "teal", "coppery", "wings", "winged", "tattoo", "muscular", "thin", "tall", "beautiful",
    }
    OUTFIT_HINTS = {
        "dress", "gown", "shirt", "robes", "robe", "armor", "armour", "leathers", "boots", "jacket", "sweater",
        "cloak", "apron", "bodice", "nightclothes", "nightgown", "male's shirt", "training leathers",
    }
    INJURY_HINTS = {
        "bloodied", "bleeding", "bruised", "wound", "wounded", "black eye", "injured", "broken", "torn", "exhausted",
        "sweating", "panting", "shaking", "dizzy", "nauseated", "hungry", "aching", "limps", "limping", "collapsed",
        "bandaged", "scar on", "sore", "flushed", "prone", "dirty", "dusty",
    }
    EXPRESSION_HINTS = {
        "smile", "smirk", "grin", "weary", "angry", "hopeful", "joyful", "determined", "watchful", "grave", "tearful",
        "mischief", "respectful", "solemn", "fearful", "impatient", "wary", "calm", "feline", "blushing",
    }
    MAGIC_HINTS = {
        "glowing", "aura", "magic", "silver fire", "shadow", "tattoo vanished", "siphon", "cauldron", "glows",
        "glowed", "forged", "black tiara", "crown", "mask", "harp",
    }
    MOJIBAKE_REPLACEMENTS = {
        "â€‘": "-",
        "â€™": "'",
        "â€œ": "\"",
        "â€\u008c": "\"",
        "â€\u009d": "\"",
        "â€¦": "...",
        "Ã©": "e",
    }
    SKIP_STATE_VALUES = {"alive", "dead", "present", "unknown"}

    def build_from_json_path(
        self,
        *,
        visual_state_path: str | Path,
        contract_path: str | Path | None = None,
        mode: str = MODE_FULL_PROMPT_PACK,
        focus_characters: Optional[List[str]] = None,
        focus_locations: Optional[List[str]] = None,
        focus_entities: Optional[List[str]] = None,
        scene_id: str = "",
        chapter: int = 0,
        include_low_confidence: bool = False,
    ) -> Dict[str, Any]:
        payload = json.loads(Path(visual_state_path).read_text(encoding="utf-8"))
        contract_payload = None
        if contract_path:
            contract_payload = json.loads(Path(contract_path).read_text(encoding="utf-8"))
        result = self.build(
            visual_state=payload,
            contract=contract_payload,
            source_visual_state=str(visual_state_path),
            mode=mode,
            focus_characters=focus_characters,
            focus_locations=focus_locations,
            focus_entities=focus_entities,
            scene_id=scene_id,
            chapter=chapter,
            include_low_confidence=include_low_confidence,
        )
        result["source_visual_state"] = str(visual_state_path)
        return result

    def build(
        self,
        *,
        visual_state: Dict[str, Any],
        contract: Optional[Dict[str, Any]] = None,
        source_visual_state: str = "",
        mode: str = MODE_FULL_PROMPT_PACK,
        focus_characters: Optional[List[str]] = None,
        focus_locations: Optional[List[str]] = None,
        focus_entities: Optional[List[str]] = None,
        scene_id: str = "",
        chapter: int = 0,
        include_low_confidence: bool = False,
    ) -> Dict[str, Any]:
        chosen_mode = str(mode or self.MODE_FULL_PROMPT_PACK).strip().lower()
        if chosen_mode not in self.MODES:
            raise ValueError(f"Unsupported prompt-pack mode: {mode}")
        focus_characters = focus_characters or []
        focus_locations = focus_locations or []
        focus_entities = focus_entities or []
        selected_scene_id = str(scene_id or "").strip()
        selected_chapter = int(chapter or 0)

        diagnostics = {
            "suppressed_entries": [],
            "alias_merges": [],
            "excluded_low_confidence": [],
            "focus_filters": {
                "characters": focus_characters,
                "locations": focus_locations,
                "entities": focus_entities,
                "scene_id": selected_scene_id,
                "chapter": selected_chapter,
            },
            "mode": chosen_mode,
            "input_counts": {
                "character_visual_states": len(visual_state.get("character_visual_states") or []),
                "location_visual_states": len(visual_state.get("location_visual_states") or []),
                "entity_visual_states": len(visual_state.get("entity_visual_states") or []),
            },
            "contract_text_backed_scene_splitting": bool(contract),
        }
        chapter_text_map = self._build_chapter_text_map(contract or {})

        character_packs = self._build_character_packs(
            visual_state.get("character_visual_states") or [],
            focus_characters=focus_characters,
            include_low_confidence=include_low_confidence,
            diagnostics=diagnostics,
        )
        location_packs = self._build_location_packs(
            visual_state.get("location_visual_states") or [],
            focus_locations=focus_locations,
            include_low_confidence=include_low_confidence,
            diagnostics=diagnostics,
        )
        object_packs = self._build_object_packs(
            visual_state.get("entity_visual_states") or [],
            focus_entities=focus_entities,
            include_low_confidence=include_low_confidence,
            diagnostics=diagnostics,
        )
        scene_packs = self._build_scene_packs(
            character_packs=character_packs,
            location_packs=location_packs,
            object_packs=object_packs,
            scene_id=selected_scene_id,
            chapter=selected_chapter,
            chapter_text_map=chapter_text_map,
        )

        if chosen_mode == self.MODE_CHARACTER_SHEET:
            location_packs = []
            object_packs = []
            scene_packs = []
        elif chosen_mode == self.MODE_LOCATION_SHEET:
            character_packs = []
            object_packs = []
            scene_packs = []
        elif chosen_mode == self.MODE_OBJECT_SHEET:
            character_packs = []
            location_packs = []
            scene_packs = []
        elif chosen_mode == self.MODE_SCENE_PROMPT:
            character_packs = []
            location_packs = []
            object_packs = []

        diagnostics.update({
            "character_count": len(character_packs),
            "location_count": len(location_packs),
            "object_count": len(object_packs),
            "scene_prompt_count": len(scene_packs),
            "scene_prompt_granularity": "chapter_text_visual_beats" if chapter_text_map else "chapter_visual_beats",
            "kept_counts": {
                "character_prompts": len(character_packs),
                "location_prompts": len(location_packs),
                "object_prompts": len(object_packs),
                "scene_prompts": len(scene_packs),
            },
        })

        return {
            "source_visual_state": source_visual_state,
            "target_point": visual_state.get("target_point") or {},
            "prompt_packs": {
                "characters": character_packs,
                "locations": location_packs,
                "objects": object_packs,
                "scene_prompts": scene_packs,
            },
            "diagnostics": diagnostics,
        }

    def build_curated_test_pack(self, prompt_pack: Dict[str, Any]) -> Dict[str, Any]:
        packs = prompt_pack.get("prompt_packs") or {}
        curated_characters = self._pick_named_rows(
            packs.get("characters") or [],
            ["Nesta", "Cassian", "Gwyn", "Emerie", "Feyre"],
        )
        curated_locations = self._pick_named_rows(
            packs.get("locations") or [],
            ["House of Wind", "training ring", "river house"],
        )
        curated_objects = self._pick_named_rows(
            packs.get("objects") or [],
            ["Ataraxia", "Mask", "Harp", "Crown"],
            limit=3,
        )
        curated_scenes: List[Dict[str, Any]] = []
        notes: List[str] = []
        scene_rows = packs.get("scene_prompts") or []
        for spec in [
            ("Nesta + Cassian training scene", {"characters": {"Nesta", "Cassian"}, "location_contains": "training ring"}),
            ("Gwyn + Emerie late-book / Blood Rite adjacent scene", {"characters": {"Gwyn", "Emerie"}, "location_any": {"Snowy mountain forest near Ramiel", "Valley near Ramiel", "snowy ridge and surrounding forest"}}),
            ("Nesta + Gwyn + Emerie scene", {"characters": {"Nesta", "Gwyn", "Emerie"}}),
        ]:
            picked = self._select_scene(scene_rows, **spec[1])
            if picked:
                curated_scenes.append({**picked, "requested_title": spec[0], "score": self._score_scene_prompt(picked)})
            else:
                notes.append(f"Missing curated scene: {spec[0]}")

        for row in curated_characters:
            row["score"] = self._score_prompt(
                positive_prompt=self._join_prompt_bits([
                    row.get("appearance_prompt", ""),
                    row.get("outfit_prompt", ""),
                    row.get("injury_condition_prompt", ""),
                    row.get("expression_prompt", ""),
                    row.get("magic_prompt", ""),
                ]),
                confidence=row.get("confidence", "low"),
                risk_flags=row.get("risk_flags") or [],
                evidence_count=len(row.get("evidence") or []),
            )
        for row in curated_locations:
            row["score"] = self._score_prompt(
                positive_prompt=self._join_prompt_bits([
                    row.get("location_prompt", ""),
                    row.get("atmosphere_prompt", ""),
                    row.get("architectural_prompt", ""),
                ]),
                confidence=row.get("confidence", "low"),
                risk_flags=row.get("risk_flags") or [],
                evidence_count=len(row.get("evidence") or []),
            )
        for row in curated_objects:
            row["score"] = self._score_prompt(
                positive_prompt=self._join_prompt_bits([
                    row.get("object_prompt", ""),
                    row.get("material_prompt", ""),
                    row.get("magic_prompt", ""),
                ]),
                confidence=row.get("confidence", "low"),
                risk_flags=row.get("risk_flags") or [],
                evidence_count=len(row.get("evidence") or []),
            )

        return {
            "source_prompt_pack": prompt_pack.get("source_visual_state", ""),
            "target_point": prompt_pack.get("target_point") or {},
            "curated_test_pack": {
                "characters": curated_characters,
                "locations": curated_locations,
                "objects": curated_objects,
                "scene_prompts": curated_scenes,
            },
            "category_negative_prompts": {
                "character_sheet": self.GENERIC_NEGATIVE_PROMPTS["character_sheet"],
                "location": self.GENERIC_NEGATIVE_PROMPTS["location"],
                "object": self.GENERIC_NEGATIVE_PROMPTS["object"],
                "scene": self.GENERIC_NEGATIVE_PROMPTS["scene"],
            },
            "diagnostics": {
                "notes": notes,
                "character_count": len(curated_characters),
                "location_count": len(curated_locations),
                "object_count": len(curated_objects),
                "scene_count": len(curated_scenes),
            },
        }

    def _build_character_packs(
        self,
        rows: List[Dict[str, Any]],
        *,
        focus_characters: List[str],
        include_low_confidence: bool,
        diagnostics: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        grouped: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            raw_name = str(row.get("display_name") or "").strip()
            if not raw_name:
                continue
            normalized = self._normalize_character_name(raw_name, diagnostics)
            if not normalized:
                diagnostics["suppressed_entries"].append({"entry": raw_name, "reason": "suppressed_character_noise"})
                continue
            if self._norm(raw_name) in self.OBJECT_CHARACTER_REDIRECTS or self._norm(raw_name) in self.LOCATION_LIKE_CHARACTER_ENTRIES or self._norm(raw_name) in self.GROUP_ENTRIES:
                diagnostics["suppressed_entries"].append({"entry": raw_name, "reason": "not_individual_character"})
                continue
            if focus_characters and all(self._norm(normalized) != self._norm(item) and self._norm(raw_name) != self._norm(item) for item in focus_characters):
                continue
            if not include_low_confidence and str(row.get("confidence") or "").lower() == "low" and not (row.get("evidence") or []):
                diagnostics["excluded_low_confidence"].append(raw_name)
                continue
            pack = self._character_pack_from_row(normalized, row)
            if not pack:
                diagnostics["suppressed_entries"].append({"entry": raw_name, "reason": "insufficient_character_prompt_evidence"})
                continue
            existing = grouped.get(normalized)
            if existing is None or self._confidence_rank(pack["confidence"]) > self._confidence_rank(existing["confidence"]):
                grouped[normalized] = pack
                continue
            existing["evidence"] = self._merge_evidence(existing["evidence"], pack["evidence"])
            existing["risk_flags"] = self._dedupe_strings([*existing.get("risk_flags", []), *pack.get("risk_flags", [])])
        return sorted(grouped.values(), key=lambda item: (-self._confidence_rank(item["confidence"]), item["display_name"].lower()))

    def _build_location_packs(
        self,
        rows: List[Dict[str, Any]],
        *,
        focus_locations: List[str],
        include_low_confidence: bool,
        diagnostics: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        packs: List[Dict[str, Any]] = []
        for row in rows:
            name = str(row.get("display_name") or "").strip()
            if not name:
                continue
            if focus_locations and all(self._norm(name) != self._norm(item) for item in focus_locations):
                continue
            if not include_low_confidence and str(row.get("confidence") or "").lower() == "low" and not (row.get("evidence") or []):
                diagnostics["excluded_low_confidence"].append(name)
                continue
            pack = self._location_pack_from_row(row)
            if pack:
                packs.append(pack)
        return sorted(packs, key=lambda item: (-self._confidence_rank(item["confidence"]), item["display_name"].lower()))

    def _build_object_packs(
        self,
        rows: List[Dict[str, Any]],
        *,
        focus_entities: List[str],
        include_low_confidence: bool,
        diagnostics: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        packs: List[Dict[str, Any]] = []
        for row in rows:
            name = str(row.get("display_name") or "").strip()
            if not name:
                continue
            if focus_entities and all(self._norm(name) != self._norm(item) for item in focus_entities):
                continue
            if not include_low_confidence and str(row.get("confidence") or "").lower() == "low" and not (row.get("evidence") or []):
                diagnostics["excluded_low_confidence"].append(name)
                continue
            pack = self._object_pack_from_row(row)
            if pack:
                packs.append(pack)
        return sorted(packs, key=lambda item: (-self._confidence_rank(item["confidence"]), item["display_name"].lower()))

    def _character_pack_from_row(self, display_name: str, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        evidence_rows = row.get("evidence") or []
        categorized = self._categorize_character_evidence(evidence_rows)
        baseline = self._naturalize_visual_field(row.get("baseline_description", ""))
        appearance = self._join_prompt_bits([baseline, *categorized["appearance"][:3]])
        outfit = self._join_prompt_bits(categorized["outfit"][:3])
        injury = self._join_prompt_bits(categorized["injury"][:3])
        expression = self._join_prompt_bits(categorized["expression"][:2])
        magic = self._join_prompt_bits([*categorized["magic"][:3]])
        if not any([appearance, outfit, injury, expression, magic, evidence_rows]):
            return None
        canonical_prompt = self._join_prompt_bits([display_name, appearance, outfit])
        return {
            "character_id": row.get("character_id") or f"char_{self._slug(display_name)}",
            "display_name": display_name,
            "canonical_prompt": canonical_prompt,
            "appearance_prompt": appearance,
            "outfit_prompt": outfit,
            "injury_condition_prompt": injury,
            "expression_prompt": expression,
            "magic_prompt": magic,
            "negative_prompt": self.GENERIC_NEGATIVE_PROMPTS["character_sheet"],
            "evidence": self._trim_evidence(evidence_rows),
            "confidence": str(row.get("confidence") or "low"),
            "risk_flags": list(row.get("risk_flags") or []),
            "comfyui": {
                "recommended_workflow_type": "character_sheet",
                "suggested_aspect_ratio": "2:3",
                "suggested_resolution": "1024x1536",
                "controlnet_recommended": False,
                "ip_adapter_reference_recommended": True,
                "lora_slots": [],
                "seed_strategy": "fixed_for_character_consistency",
            },
        }

    def _location_pack_from_row(self, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        name = str(row.get("display_name") or "").strip()
        location_prompt = self._join_prompt_bits([
            name,
            self._naturalize_visual_field(row.get("baseline_description", "")),
            self._naturalize_visual_field(row.get("current_description", "")),
        ])
        atmosphere_prompt = self._join_prompt_bits([
            self._naturalize_visual_field(row.get("atmosphere", "")),
            *self._naturalize_list(row.get("recent_visual_changes") or []),
        ])
        architectural_prompt = self._join_prompt_bits([
            *self._naturalize_list(row.get("notable_features") or []),
        ])
        if not any([location_prompt, atmosphere_prompt, architectural_prompt, row.get("evidence")]):
            return None
        return {
            "location_id": row.get("location_id") or f"loc_{self._slug(name)}",
            "display_name": name,
            "location_prompt": location_prompt,
            "atmosphere_prompt": atmosphere_prompt,
            "architectural_prompt": architectural_prompt,
            "negative_prompt": self.GENERIC_NEGATIVE_PROMPTS["location"],
            "evidence": self._trim_evidence(row.get("evidence") or []),
            "confidence": str(row.get("confidence") or "low"),
            "risk_flags": list(row.get("risk_flags") or []),
            "comfyui": {
                "recommended_workflow_type": "location_concept",
                "suggested_aspect_ratio": "16:9",
                "suggested_resolution": "1536x864",
                "controlnet_recommended": False,
                "ip_adapter_reference_recommended": False,
                "lora_slots": [],
                "seed_strategy": "fixed_for_environment_consistency",
            },
        }

    def _object_pack_from_row(self, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        name = str(row.get("display_name") or "").strip()
        obj_type = str(row.get("entity_category") or row.get("entity_type") or "").strip().lower()
        object_prompt = self._join_prompt_bits([
            name,
            self._naturalize_visual_field(row.get("baseline_description", "")),
            self._naturalize_visual_field(row.get("current_appearance", row.get("current_description", ""))),
        ])
        material_prompt = self._join_prompt_bits([
            self._naturalize_visual_field(row.get("material_or_texture", "")),
        ])
        magic_prompt = self._join_prompt_bits([
            *self._naturalize_list(row.get("magical_or_state_properties") or []),
            *self._naturalize_list(row.get("recent_visual_changes") or []),
        ])
        if not any([object_prompt, material_prompt, magic_prompt, row.get("evidence")]):
            return None
        return {
            "entity_id": row.get("entity_id") or f"ent_{self._slug(name)}",
            "display_name": name,
            "object_prompt": object_prompt,
            "material_prompt": material_prompt,
            "magic_prompt": magic_prompt,
            "negative_prompt": self.GENERIC_NEGATIVE_PROMPTS["object"],
            "evidence": self._trim_evidence(row.get("evidence") or []),
            "confidence": str(row.get("confidence") or "low"),
            "risk_flags": list(row.get("risk_flags") or []),
            "comfyui": {
                "recommended_workflow_type": "object_concept",
                "suggested_aspect_ratio": "1:1",
                "suggested_resolution": "1024x1024",
                "controlnet_recommended": False,
                "ip_adapter_reference_recommended": False,
                "lora_slots": [],
                "seed_strategy": "fixed_for_object_consistency",
            },
            "entity_category": obj_type or "object",
        }

    def _build_scene_packs(
        self,
        *,
        character_packs: List[Dict[str, Any]],
        location_packs: List[Dict[str, Any]],
        object_packs: List[Dict[str, Any]],
        scene_id: str,
        chapter: int,
        chapter_text_map: Optional[Dict[Tuple[int, int], str]] = None,
    ) -> List[Dict[str, Any]]:
        chapter_scene_filter = self._scene_chapter_ref(scene_id) if scene_id else (None, None)
        chapter_map = self._build_chapter_visual_maps(
            character_packs=character_packs,
            location_packs=location_packs,
            object_packs=object_packs,
            scene_id=scene_id,
            chapter=chapter,
            chapter_scene_filter=chapter_scene_filter,
        )
        scene_packs: List[Dict[str, Any]] = []
        for (book_index, chapter_index), chapter_bucket in chapter_map.items():
            chapter_text = (chapter_text_map or {}).get((book_index, chapter_index), "")
            ordered_buckets = self._build_chapter_visual_beats(chapter_bucket, chapter_text=chapter_text)
            for beat_index, bucket in enumerate(ordered_buckets, start=1):
                chars = self._rank_scene_members(self._unique_by_name(bucket["characters"]), bucket["evidence"], limit=4)
                loc_pack = bucket.get("location")
                locs = [loc_pack] if loc_pack else []
                objs = self._rank_scene_members(self._unique_by_name(bucket["objects"]), bucket["evidence"], limit=4)
                if not chars and not locs and not objs:
                    continue
                scene_key_value = f"b{book_index}_c{chapter_index}_v{beat_index}"
                title = self._scene_title(chars, locs, objs)
                positive_prompt = self._join_prompt_bits([
                    self._scene_location_phrase(locs, scene_key_value, bucket["evidence"]),
                    self._scene_character_phrase(chars, scene_key_value, bucket["evidence"]),
                    self._scene_object_phrase(objs, scene_key_value, bucket["evidence"]),
                ])
                if not positive_prompt:
                    continue
                scene_packs.append({
                    "scene_key": scene_key_value,
                    "title": title,
                    "positive_prompt": positive_prompt,
                    "negative_prompt": self.GENERIC_NEGATIVE_PROMPTS["scene"],
                    "characters_used": [row["display_name"] for row in chars],
                    "locations_used": [row["display_name"] for row in locs],
                    "objects_used": [row["display_name"] for row in objs],
                    "source_scene_keys": sorted(bucket["source_scene_keys"]),
                    "book_index": book_index,
                    "chapter": chapter_index,
                    "scene_beat_index": beat_index,
                    "evidence": self._trim_evidence(self._merge_evidence([], bucket["evidence"])),
                    "comfyui": {
                        "recommended_workflow_type": "scene_illustration",
                        "suggested_aspect_ratio": "16:9",
                        "suggested_resolution": "1536x864",
                        "controlnet_recommended": False,
                        "ip_adapter_reference_recommended": True,
                        "lora_slots": [],
                        "seed_strategy": "fixed_for_character_consistency",
                    },
                })
        return sorted(scene_packs, key=lambda item: (int(item.get("book_index") or 0), int(item.get("chapter") or 0), int(item.get("scene_beat_index") or 0)))

    def _build_chapter_visual_maps(
        self,
        *,
        character_packs: List[Dict[str, Any]],
        location_packs: List[Dict[str, Any]],
        object_packs: List[Dict[str, Any]],
        scene_id: str,
        chapter: int,
        chapter_scene_filter: Tuple[Optional[int], Optional[int]],
    ) -> Dict[Tuple[int, int], Dict[str, Any]]:
        chapter_map: Dict[Tuple[int, int], Dict[str, Any]] = {}
        for pack in location_packs:
            for ev in pack.get("evidence") or []:
                if not self._passes_scene_filters(ev, scene_id, chapter, chapter_scene_filter):
                    continue
                chapter_key = (int(ev.get("book_index") or 0), int(ev.get("chapter") or 0))
                if not chapter_key[0] or not chapter_key[1]:
                    continue
                chapter_bucket = chapter_map.setdefault(chapter_key, {"location_events": [], "character_events": [], "object_events": [], "source_scene_keys": set()})
                chapter_bucket["location_events"].append({"pack": pack, "evidence": ev})
                scene_key_value = str(ev.get("scene_id") or "").strip()
                if scene_key_value:
                    chapter_bucket["source_scene_keys"].add(scene_key_value)
        for pack in character_packs:
            for ev in pack.get("evidence") or []:
                if not self._passes_scene_filters(ev, scene_id, chapter, chapter_scene_filter):
                    continue
                chapter_key = (int(ev.get("book_index") or 0), int(ev.get("chapter") or 0))
                if not chapter_key[0] or not chapter_key[1]:
                    continue
                chapter_bucket = chapter_map.setdefault(chapter_key, {"location_events": [], "character_events": [], "object_events": [], "source_scene_keys": set()})
                chapter_bucket["character_events"].append({"pack": pack, "evidence": ev})
                scene_key_value = str(ev.get("scene_id") or "").strip()
                if scene_key_value:
                    chapter_bucket["source_scene_keys"].add(scene_key_value)
        for pack in object_packs:
            for ev in pack.get("evidence") or []:
                if not self._passes_scene_filters(ev, scene_id, chapter, chapter_scene_filter):
                    continue
                chapter_key = (int(ev.get("book_index") or 0), int(ev.get("chapter") or 0))
                if not chapter_key[0] or not chapter_key[1]:
                    continue
                chapter_bucket = chapter_map.setdefault(chapter_key, {"location_events": [], "character_events": [], "object_events": [], "source_scene_keys": set()})
                chapter_bucket["object_events"].append({"pack": pack, "evidence": ev})
                scene_key_value = str(ev.get("scene_id") or "").strip()
                if scene_key_value:
                    chapter_bucket["source_scene_keys"].add(scene_key_value)
        return chapter_map

    def _build_chapter_visual_beats(self, chapter_bucket: Dict[str, Any], *, chapter_text: str = "") -> List[Dict[str, Any]]:
        beats: List[Dict[str, Any]] = []
        location_events = chapter_bucket.get("location_events") or []
        character_events = chapter_bucket.get("character_events") or []
        object_events = chapter_bucket.get("object_events") or []

        if chapter_text.strip():
            paragraph_beats = self._build_paragraph_anchored_visual_beats(
                chapter_text=chapter_text,
                location_events=location_events,
                character_events=character_events,
                object_events=object_events,
            )
            if paragraph_beats:
                return paragraph_beats

        if location_events:
            for event in location_events:
                evidence = event["evidence"]
                loc_pack = event["pack"]
                source_scene_key = str(evidence.get("scene_id") or "").strip()
                beat_evidence = [evidence]
                beat_evidence.extend(
                    item["evidence"]
                    for item in character_events
                    if self._chapter_event_matches_anchor(item["evidence"], evidence)
                )
                beat_evidence.extend(
                    item["evidence"]
                    for item in object_events
                    if self._chapter_event_matches_anchor(item["evidence"], evidence)
                )
                related_characters = [
                    item["pack"]
                    for item in character_events
                    if self._chapter_event_matches_anchor(item["evidence"], evidence)
                ]
                related_objects = [
                    item["pack"]
                    for item in object_events
                    if self._chapter_event_matches_anchor(item["evidence"], evidence)
                ]
                beats.append(
                    {
                        "location": loc_pack,
                        "characters": related_characters,
                        "objects": related_objects,
                        "evidence": beat_evidence,
                        "source_scene_keys": {source_scene_key} if source_scene_key else set(),
                    }
                )

        if not beats and (character_events or object_events):
            generic_evidence = [item["evidence"] for item in character_events[:6]] + [item["evidence"] for item in object_events[:4]]
            beats.append(
                {
                    "location": None,
                    "characters": [item["pack"] for item in character_events],
                    "objects": [item["pack"] for item in object_events],
                    "evidence": generic_evidence,
                    "source_scene_keys": set(chapter_bucket.get("source_scene_keys") or set()),
                }
            )

        merged = self._merge_duplicate_visual_beats(beats)
        for beat in merged:
            if not beat["characters"]:
                beat["characters"] = [item["pack"] for item in character_events]
            if not beat["objects"]:
                beat["objects"] = [item["pack"] for item in object_events]
        return merged

    def _build_paragraph_anchored_visual_beats(
        self,
        *,
        chapter_text: str,
        location_events: List[Dict[str, Any]],
        character_events: List[Dict[str, Any]],
        object_events: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        paragraphs = [item.strip() for item in re.split(r"\n\s*\n", chapter_text) if item.strip()]
        if not paragraphs:
            return []
        anchor_events: List[Dict[str, Any]] = []
        for kind, events in (("location", location_events), ("object", object_events), ("character", character_events)):
            for event in events:
                paragraph_index = self._best_paragraph_index(paragraphs, str((event.get("evidence") or {}).get("text") or ""))
                if paragraph_index is None:
                    continue
                anchor_events.append({"kind": kind, "paragraph_index": paragraph_index, "pack": event.get("pack"), "evidence": event.get("evidence")})
        if not anchor_events:
            return []
        anchor_events.sort(key=lambda item: (int(item.get("paragraph_index") or 0), {"location": 0, "object": 1, "character": 2}.get(str(item.get("kind") or ""), 9)))
        clusters: List[Dict[str, Any]] = []
        for event in anchor_events:
            if not clusters:
                clusters.append({"events": [event], "start": event["paragraph_index"], "end": event["paragraph_index"]})
                continue
            prev = clusters[-1]
            location_changed = self._norm(((event.get("pack") or {}).get("display_name")) or "") != self._norm(((prev["events"][-1].get("pack") or {}).get("display_name")) or "")
            gap = int(event["paragraph_index"]) - int(prev["end"])
            if gap > 2 or (event["kind"] == "location" and location_changed):
                clusters.append({"events": [event], "start": event["paragraph_index"], "end": event["paragraph_index"]})
            else:
                prev["events"].append(event)
                prev["end"] = max(int(prev["end"]), int(event["paragraph_index"]))

        beats: List[Dict[str, Any]] = []
        for cluster in clusters:
            cluster_events = cluster["events"]
            evidence_rows = [item["evidence"] for item in cluster_events if item.get("evidence")]
            source_scene_keys = {str((item.get("evidence") or {}).get("scene_id") or "").strip() for item in cluster_events if str((item.get("evidence") or {}).get("scene_id") or "").strip()}
            location_pack = self._dominant_pack([item for item in cluster_events if item.get("kind") == "location"])
            character_packs = [item.get("pack") for item in cluster_events if item.get("kind") == "character" and item.get("pack")]
            object_packs = [item.get("pack") for item in cluster_events if item.get("kind") == "object" and item.get("pack")]
            if not location_pack:
                location_pack = self._nearest_location_pack(cluster_events, location_events)
            if not character_packs:
                character_packs = [item.get("pack") for item in character_events if self._best_paragraph_index(paragraphs, str((item.get("evidence") or {}).get("text") or "")) in range(cluster["start"] - 1, cluster["end"] + 2) and item.get("pack")]
            if not object_packs:
                object_packs = [item.get("pack") for item in object_events if self._best_paragraph_index(paragraphs, str((item.get("evidence") or {}).get("text") or "")) in range(cluster["start"] - 1, cluster["end"] + 2) and item.get("pack")]
            beats.append(
                {
                    "location": location_pack,
                    "characters": [pack for pack in character_packs if pack],
                    "objects": [pack for pack in object_packs if pack],
                    "evidence": evidence_rows,
                    "source_scene_keys": source_scene_keys,
                }
            )
        return self._merge_duplicate_visual_beats(beats)

    def _merge_duplicate_visual_beats(self, beats: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        merged: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for beat in beats:
            location_name = self._norm(((beat.get("location") or {}).get("display_name")) or "")
            evidence_signature = self._norm(self._naturalize_evidence_text(((beat.get("evidence") or [{}])[0]).get("text", "")))
            key = (location_name, evidence_signature)
            existing = merged.get(key)
            if existing is None:
                merged[key] = {
                    "location": beat.get("location"),
                    "characters": list(beat.get("characters") or []),
                    "objects": list(beat.get("objects") or []),
                    "evidence": list(beat.get("evidence") or []),
                    "source_scene_keys": set(beat.get("source_scene_keys") or set()),
                }
                continue
            existing["characters"].extend(beat.get("characters") or [])
            existing["objects"].extend(beat.get("objects") or [])
            existing["evidence"].extend(beat.get("evidence") or [])
            existing["source_scene_keys"].update(beat.get("source_scene_keys") or set())
        rows = list(merged.values())
        rows.sort(key=lambda item: (self._norm(((item.get("location") or {}).get("display_name")) or ""), self._norm(self._naturalize_evidence_text(((item.get("evidence") or [{}])[0]).get("text", "")))))
        return rows

    def _build_chapter_text_map(self, contract: Dict[str, Any]) -> Dict[Tuple[int, int], str]:
        rows = (((contract or {}).get("outputs") or {}).get("scene_analyses") or [])
        out: Dict[Tuple[int, int], str] = {}
        for row in rows:
            book_index = int(row.get("book_index") or 0)
            chapter_index = int(row.get("chapter_index") or 0)
            text = str(row.get("text") or "").strip()
            if book_index and chapter_index and text:
                out[(book_index, chapter_index)] = text
        return out

    def _best_paragraph_index(self, paragraphs: List[str], evidence_text: str) -> Optional[int]:
        target = self._naturalize_evidence_text(evidence_text)
        if not target:
            return None
        target_tokens = [tok for tok in re.findall(r"[a-z0-9']+", target.lower()) if len(tok) > 2]
        if not target_tokens:
            return None
        best_index = None
        best_score = 0
        for index, paragraph in enumerate(paragraphs):
            para_tokens = set(re.findall(r"[a-z0-9']+", paragraph.lower()))
            score = sum(1 for tok in target_tokens if tok in para_tokens)
            if score > best_score:
                best_index = index
                best_score = score
        if best_score < min(2, len(set(target_tokens))):
            return None
        return best_index

    def _dominant_pack(self, events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        counts: Dict[str, Tuple[int, Dict[str, Any]]] = {}
        for event in events:
            pack = event.get("pack") or {}
            name = str(pack.get("display_name") or "").strip()
            if not name:
                continue
            key = self._norm(name)
            count, _ = counts.get(key, (0, pack))
            counts[key] = (count + 1, pack)
        if not counts:
            return None
        return sorted(counts.values(), key=lambda item: (-item[0], self._norm(item[1].get("display_name", ""))))[0][1]

    def _nearest_location_pack(self, cluster_events: List[Dict[str, Any]], location_events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not cluster_events or not location_events:
            return None
        target_indexes = [int(item.get("paragraph_index") or 0) for item in cluster_events]
        if not target_indexes:
            return None
        target = sum(target_indexes) / len(target_indexes)
        best: Optional[Tuple[float, Dict[str, Any]]] = None
        for event in location_events:
            idx = event.get("paragraph_index")
            if idx is None:
                continue
            distance = abs(float(idx) - float(target))
            if best is None or distance < best[0]:
                best = (distance, event.get("pack"))
        return best[1] if best else None

    def _scene_title(self, chars: List[Dict[str, Any]], locs: List[Dict[str, Any]], objs: List[Dict[str, Any]]) -> str:
        if chars and locs:
            return f"{', '.join(row['display_name'] for row in chars[:3])} at {locs[0]['display_name']}"
        if chars:
            return ", ".join(row["display_name"] for row in chars[:3])
        if locs:
            return locs[0]["display_name"]
        if objs:
            return objs[0]["display_name"]
        return "Scene prompt"

    def _scene_location_phrase(self, locs: List[Dict[str, Any]], scene_key: str, evidence_rows: Optional[List[Dict[str, Any]]] = None) -> str:
        if not locs:
            return ""
        row = locs[0]
        scene_evidence = [
            self._naturalize_evidence_text(item.get("text", ""))
            for item in (evidence_rows or row.get("evidence") or [])
            if self._evidence_matches_scene(item, scene_key)
        ]
        return self._join_prompt_bits([
            row.get("display_name", ""),
            self._join_prompt_bits(scene_evidence[:2]) or row.get("location_prompt", "").replace(row.get("display_name", ""), "", 1).strip(", "),
            row.get("atmosphere_prompt", ""),
            row.get("architectural_prompt", ""),
        ])

    def _scene_character_phrase(self, chars: List[Dict[str, Any]], scene_key: str, evidence_rows: Optional[List[Dict[str, Any]]] = None) -> str:
        bits: List[str] = []
        for row in chars[:4]:
            target_rows = [item for item in (row.get("evidence") or []) if self._evidence_matches_scene(item, scene_key)]
            if not target_rows and evidence_rows:
                target_scene_ids = {str(item.get("scene_id") or "") for item in evidence_rows if str(item.get("scene_id") or "")}
                target_chapter = self._scene_chapter_ref(scene_key)
                target_rows = [
                    item
                    for item in (row.get("evidence") or [])
                    if (
                        str(item.get("scene_id") or "") in target_scene_ids
                        or ((item.get("book_index"), item.get("chapter")) == target_chapter)
                    )
                ]
            scene_specific = self._categorize_character_evidence(target_rows)
            appearance_bits = scene_specific["appearance"][:2] if scene_specific["appearance"] else [row.get("appearance_prompt", "")]
            outfit_bits = scene_specific["outfit"][:1] if scene_specific["outfit"] else [row.get("outfit_prompt", "")]
            injury_bits = scene_specific["injury"][:1] if scene_specific["injury"] else [row.get("injury_condition_prompt", "")]
            expression_bits = scene_specific["expression"][:1] if scene_specific["expression"] else [row.get("expression_prompt", "")]
            magic_bits = scene_specific["magic"][:1] if scene_specific["magic"] else [row.get("magic_prompt", "")]
            bits.append(self._join_prompt_bits([
                row.get("display_name", ""),
                *appearance_bits,
                *outfit_bits,
                *injury_bits,
                *expression_bits,
                *magic_bits,
            ]))
        return self._join_prompt_bits(bits)

    def _scene_object_phrase(self, objs: List[Dict[str, Any]], scene_key: str, evidence_rows: Optional[List[Dict[str, Any]]] = None) -> str:
        bits: List[str] = []
        for row in objs[:4]:
            scene_evidence = [
                self._naturalize_evidence_text(item.get("text", ""))
                for item in (row.get("evidence") or [])
                if self._evidence_matches_scene(item, scene_key)
            ]
            if not scene_evidence and evidence_rows:
                target_scene_ids = {str(item.get("scene_id") or "") for item in evidence_rows if str(item.get("scene_id") or "")}
                target_chapter = self._scene_chapter_ref(scene_key)
                scene_evidence = [
                    self._naturalize_evidence_text(item.get("text", ""))
                    for item in (row.get("evidence") or [])
                    if (
                        str(item.get("scene_id") or "") in target_scene_ids
                        or ((item.get("book_index"), item.get("chapter")) == target_chapter)
                    )
                ]
            bits.append(self._join_prompt_bits([
                row.get("display_name", ""),
                self._join_prompt_bits(scene_evidence[:2]) or row.get("object_prompt", "").replace(row.get("display_name", ""), "", 1).strip(", "),
                row.get("material_prompt", ""),
                row.get("magic_prompt", ""),
            ]))
        return self._join_prompt_bits(bits)

    def _normalize_character_name(self, name: str, diagnostics: Dict[str, Any]) -> str:
        lowered = self._norm(name)
        normalized = self.CHARACTER_ALIAS_MERGES.get(lowered, name.strip())
        normalized_lower = self._norm(normalized)
        if lowered in self.NOISY_CHARACTER_ENTRIES and normalized_lower == lowered:
            return ""
        if normalized_lower in self.NOISY_CHARACTER_ENTRIES:
            return ""
        if normalized != name.strip():
            diagnostics["alias_merges"].append({"from": name.strip(), "to": normalized})
        return normalized

    def _naturalize_visual_field(self, value: Any) -> str:
        fragments = self._split_fragments(value)
        return self._join_prompt_bits(self._naturalize_list(fragments))

    def _naturalize_list(self, values: Iterable[Any]) -> List[str]:
        rows: List[str] = []
        for value in values or []:
            for fragment in self._split_fragments(value):
                text = self._naturalize_text(fragment)
                if text:
                    rows.append(text)
        return self._dedupe_strings(rows)

    def _split_fragments(self, value: Any) -> List[str]:
        text = str(value or "").strip()
        if not text:
            return []
        if ";" in text:
            return [part.strip() for part in text.split(";") if part.strip()]
        return [text]

    def _naturalize_text(self, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        for bad, good in self.MOJIBAKE_REPLACEMENTS.items():
            text = text.replace(bad, good)
        text = re.sub(r"\s+", " ", text).strip(" ,;")
        if "=" in text:
            key, raw_val = text.split("=", 1)
            key = key.strip().lower()
            raw_val = raw_val.strip(" ,;")
            if not raw_val or raw_val.lower() in self.SKIP_STATE_VALUES:
                return ""
            key_map = {
                "physical_state": "",
                "temporary_condition": "",
                "appearance_note": "",
                "emotional_state": "",
                "possession": "",
                "condition": "",
                "knowledge": "",
                "form": "",
                "status": "",
                "bargain_tattoo": "bargain tattoo",
            }
            prefix = key_map.get(key, key.replace("_", " "))
            phrase = raw_val
            phrase = phrase.replace("appears on", "visible on")
            phrase = phrase.replace("appears", "visible")
            phrase = phrase.replace("temporary_condition:", "")
            phrase = phrase.strip(" ,;")
            if key == "possession" and any(word in phrase.lower() for word in ["lost", "dropped", "broken"]):
                return ""
            if prefix and prefix not in {"knowledge", "status"}:
                phrase = f"{prefix} {phrase}".strip()
            if key == "knowledge":
                return ""
            if key == "status":
                return ""
            return phrase
        text = text.replace("temporary_condition:", "").replace("appearance_note:", "").replace("physical_state:", "")
        return text.strip(" ,;")

    def _naturalize_evidence_text(self, value: Any) -> str:
        return self._naturalize_text(value)

    def _join_prompt_bits(self, values: Iterable[str]) -> str:
        cleaned: List[str] = []
        for value in values or []:
            text = str(value or "").strip(" ,;")
            if not text:
                continue
            cleaned.append(text)
        return ", ".join(self._dedupe_strings(cleaned))

    def _trim_evidence(self, values: List[Dict[str, Any]], limit: int = 20) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        seen: set[Tuple[Any, ...]] = set()
        for item in values or []:
            key = (
                item.get("book_index"),
                item.get("chapter"),
                item.get("scene_id"),
                item.get("source"),
                item.get("text"),
            )
            if key in seen:
                continue
            seen.add(key)
            rows.append(item)
            if len(rows) >= limit:
                break
        return rows

    def _merge_evidence(self, left: List[Dict[str, Any]], right: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self._trim_evidence([*(left or []), *(right or [])], limit=24)

    def _unique_by_name(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            key = self._norm(row.get("display_name", ""))
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(row)
        return out

    def _categorize_character_evidence(self, evidence_rows: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        buckets = {"appearance": [], "outfit": [], "injury": [], "expression": [], "magic": []}
        for item in evidence_rows or []:
            text = self._naturalize_evidence_text(item.get("text", ""))
            lower = text.lower()
            if not text:
                continue
            if any(term in lower for term in self.APPEARANCE_HINTS):
                buckets["appearance"].append(text)
            if any(term in lower for term in self.OUTFIT_HINTS):
                buckets["outfit"].append(text)
            if any(term in lower for term in self.INJURY_HINTS):
                buckets["injury"].append(text)
            if any(term in lower for term in self.EXPRESSION_HINTS):
                buckets["expression"].append(text)
            if any(term in lower for term in self.MAGIC_HINTS):
                buckets["magic"].append(text)
        return {key: self._dedupe_strings(value) for key, value in buckets.items()}

    def _passes_scene_filters(
        self,
        evidence_row: Dict[str, Any],
        scene_id: str,
        chapter: int,
        chapter_scene_filter: Tuple[Optional[int], Optional[int]],
    ) -> bool:
        if scene_id and str(evidence_row.get("scene_id") or "") != scene_id:
            return False
        if chapter and int(evidence_row.get("chapter") or 0) != int(chapter):
            return False
        if chapter_scene_filter[0]:
            chapter_key = (int(evidence_row.get("book_index") or 0), int(evidence_row.get("chapter") or 0))
            if chapter_key != chapter_scene_filter:
                return False
        return True

    def _chapter_event_matches_anchor(self, evidence_row: Dict[str, Any], anchor_row: Dict[str, Any]) -> bool:
        row_scene_id = str(evidence_row.get("scene_id") or "").strip()
        anchor_scene_id = str(anchor_row.get("scene_id") or "").strip()
        if row_scene_id and anchor_scene_id and row_scene_id == anchor_scene_id:
            return True
        chapter_match = (
            int(evidence_row.get("book_index") or 0) == int(anchor_row.get("book_index") or 0)
            and int(evidence_row.get("chapter") or 0) == int(anchor_row.get("chapter") or 0)
        )
        if not chapter_match:
            return False
        anchor_text = self._naturalize_evidence_text(anchor_row.get("text", ""))
        row_text = self._naturalize_evidence_text(evidence_row.get("text", ""))
        if not anchor_text or not row_text:
            return False
        shared_tokens = set(self._norm(anchor_text).split()) & set(self._norm(row_text).split())
        return len(shared_tokens) >= 2 or bool(row_scene_id and not anchor_scene_id)

    def _scene_chapter_ref(self, scene_key: str) -> Tuple[Optional[int], Optional[int]]:
        match = re.search(r"b(\d+)_c(\d+)", str(scene_key or ""))
        if not match:
            return (None, None)
        return (int(match.group(1)), int(match.group(2)))

    def _evidence_matches_scene(self, evidence_row: Dict[str, Any], scene_key: str) -> bool:
        row_scene_id = str(evidence_row.get("scene_id") or "")
        if row_scene_id and row_scene_id == scene_key:
            return True
        target_ref = self._scene_chapter_ref(scene_key)
        if not target_ref[0]:
            return False
        return (int(evidence_row.get("book_index") or 0), int(evidence_row.get("chapter") or 0)) == target_ref

    def _rank_scene_members(self, rows: List[Dict[str, Any]], evidence_rows: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        scene_ids = {str(item.get("scene_id") or "") for item in (evidence_rows or []) if str(item.get("scene_id") or "")}
        chapter_refs = {(int(item.get("book_index") or 0), int(item.get("chapter") or 0)) for item in (evidence_rows or []) if item.get("book_index") and item.get("chapter")}
        scored: List[Tuple[int, int, str, Dict[str, Any]]] = []
        for row in rows:
            matching = [
                item for item in (row.get("evidence") or [])
                if (
                    str(item.get("scene_id") or "") in scene_ids
                    or (int(item.get("book_index") or 0), int(item.get("chapter") or 0)) in chapter_refs
                )
            ]
            scored.append((
                len(matching),
                self._confidence_rank(str(row.get("confidence") or "")),
                self._norm(row.get("display_name", "")),
                row,
            ))
        scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
        return [item[3] for item in scored[:limit] if item[0] > 0 or rows]

    def _pick_named_rows(self, rows: List[Dict[str, Any]], names: List[str], limit: int = 999) -> List[Dict[str, Any]]:
        picked: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for name in names:
            for row in rows:
                if self._norm(row.get("display_name", "")) != self._norm(name):
                    continue
                key = self._norm(row.get("display_name", ""))
                if key in seen:
                    break
                seen.add(key)
                picked.append(json.loads(json.dumps(row)))
                break
            if len(picked) >= limit:
                break
        return picked[:limit]

    def _select_scene(
        self,
        scene_rows: List[Dict[str, Any]],
        *,
        characters: set[str],
        location_contains: str = "",
        location_any: Optional[set[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        location_any = location_any or set()
        candidates: List[Tuple[int, int, Dict[str, Any]]] = []
        for row in scene_rows:
            used = set(row.get("characters_used") or [])
            if not characters.issubset(used):
                continue
            used_locations = set(row.get("locations_used") or [])
            if location_contains and not any(location_contains.lower() in str(loc).lower() for loc in used_locations):
                continue
            if location_any and not any(str(loc) in location_any for loc in used_locations):
                continue
            extra_characters = max(0, len(used - characters))
            evidence_penalty = -len(row.get("evidence") or [])
            candidates.append((extra_characters, evidence_penalty, row))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1], item[2].get("scene_key", "")))
        return json.loads(json.dumps(candidates[0][2]))

    def _score_prompt(
        self,
        *,
        positive_prompt: str,
        confidence: str,
        risk_flags: List[str],
        evidence_count: int,
    ) -> Dict[str, Any]:
        notes: List[str] = []
        specificity = min(5, max(1, 1 + min(4, len([part for part in positive_prompt.split(",") if part.strip()]) // 3)))
        evidence_strength = {"high": 5, "medium": 3, "low": 2}.get(str(confidence).lower(), 1)
        if evidence_count <= 2:
            evidence_strength = max(1, evidence_strength - 1)
            notes.append("Limited evidence count.")
        cleanliness = 5
        if any(flag for flag in risk_flags):
            cleanliness -= 1
            notes.append("Has risk flags.")
        if "=" in positive_prompt:
            cleanliness -= 2
            notes.append("Contains raw key=value fragments.")
        if "status=alive" in positive_prompt.lower():
            cleanliness -= 2
            notes.append("Contains unsupported status detail.")
        readiness = max(1, min(5, round((specificity + evidence_strength + cleanliness) / 3)))
        return {
            "visual_specificity": max(1, min(5, specificity)),
            "evidence_strength": max(1, min(5, evidence_strength)),
            "identity_cleanliness": max(1, min(5, cleanliness)),
            "comfyui_readiness": readiness,
            "notes": notes,
        }

    def _score_scene_prompt(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return self._score_prompt(
            positive_prompt=row.get("positive_prompt", ""),
            confidence="high" if len(row.get("evidence") or []) >= 4 else "medium",
            risk_flags=[],
            evidence_count=len(row.get("evidence") or []),
        )

    def _confidence_rank(self, value: str) -> int:
        return {"high": 3, "medium": 2, "low": 1}.get(str(value or "").lower(), 0)

    def _dedupe_strings(self, values: Iterable[str]) -> List[str]:
        seen: set[str] = set()
        rows: List[str] = []
        for value in values or []:
            text = str(value or "").strip()
            key = self._norm(text)
            if not key or key in seen:
                continue
            seen.add(key)
            rows.append(text)
        return rows

    def _norm(self, value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip().lower())

    def _slug(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", self._norm(value)).strip("_") or "item"
