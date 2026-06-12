from __future__ import annotations

import json
from pathlib import Path

from query.comfyui_prompt_pack_service import ComfyUIPromptPackService


def _visual_payload() -> dict:
    return {
        "target_point": {"mode": "post_book", "after_book_index": 5},
        "character_visual_states": [
            {
                "character_id": "char_cassian",
                "display_name": "Cassian",
                "baseline_description": "winged Illyrian warrior, dark hair, hazel eyes",
                "current_appearance": "appearance_note=battle-scarred face",
                "clothing_or_outfit": "leather armor",
                "injuries_or_physical_condition": "temporary_condition=exhausted after training",
                "body_language_or_expression": "emotional_state=watchful",
                "magical_or_physical_transformations": ["appearance_note=eight-pointed star tattoo visible on his back"],
                "recent_visual_changes": [],
                "evidence": [{"book_index": 5, "chapter": 68, "scene_id": "b5_c68_s1", "source": "entity_description", "text": "winged Illyrian warrior in leather armor, battle-scarred face"}],
                "confidence": "high",
                "risk_flags": [],
            },
            {
                "character_id": "char_rhys",
                "display_name": "Rhys",
                "baseline_description": "dark-haired winged fae male",
                "current_appearance": "appearance_note=eight-pointed star tattoo appears on his back",
                "clothing_or_outfit": "leather armor",
                "injuries_or_physical_condition": "status=alive",
                "body_language_or_expression": "emotional_state=watchful",
                "magical_or_physical_transformations": ["shadow magic coiling around him"],
                "recent_visual_changes": [],
                "evidence": [{"book_index": 5, "chapter": 70, "scene_id": "b5_c70_s1", "source": "entity_description", "text": "dark-haired winged fae male"}],
                "confidence": "high",
                "risk_flags": [],
            },
            {
                "character_id": "char_nesta",
                "display_name": "Lady Nesta",
                "baseline_description": "high fae woman, pale skin",
                "current_appearance": "appearance_note=gray-blue eyes",
                "clothing_or_outfit": "Illyrian training leathers",
                "injuries_or_physical_condition": "condition=hands torn from rope",
                "body_language_or_expression": "emotional_state=determined",
                "magical_or_physical_transformations": ["temporary_condition=glowing with heightened confidence"],
                "recent_visual_changes": [],
                "evidence": [{"book_index": 5, "chapter": 68, "scene_id": "b5_c68_s1", "source": "entity_description", "text": "bloodied hands, sap-coated fingers, Illyrian training leathers"}],
                "confidence": "high",
                "risk_flags": [],
            },
            {
                "character_id": "char_gwyn",
                "display_name": "Gwyn",
                "baseline_description": "coppery hair, teal eyes",
                "current_appearance": "appearance_note=freckled face",
                "clothing_or_outfit": "priestess robes",
                "injuries_or_physical_condition": "temporary_condition=bandaged leg",
                "body_language_or_expression": "emotional_state=bright smile",
                "magical_or_physical_transformations": [],
                "recent_visual_changes": [],
                "evidence": [{"book_index": 5, "chapter": 68, "scene_id": "b5_c68_s1", "source": "entity_description", "text": "coppery hair, teal eyes, priestess robes, bandaged leg"}],
                "confidence": "high",
                "risk_flags": [],
            },
            {
                "character_id": "char_emerie",
                "display_name": "Emerie",
                "baseline_description": "dark-haired Illyrian female with clipped wings",
                "current_appearance": "appearance_note=windblown hair",
                "clothing_or_outfit": "Illyrian leathers",
                "injuries_or_physical_condition": "temporary_condition=limping after twisted ankle",
                "body_language_or_expression": "emotional_state=focused",
                "magical_or_physical_transformations": [],
                "recent_visual_changes": [],
                "evidence": [{"book_index": 5, "chapter": 68, "scene_id": "b5_c68_s1", "source": "entity_description", "text": "dark-haired Illyrian female with clipped wings, Illyrian leathers, limping"}],
                "confidence": "high",
                "risk_flags": [],
            },
            {
                "character_id": "char_feyre",
                "display_name": "Feyre",
                "baseline_description": "high fae woman with painted hands",
                "current_appearance": "appearance_note=pregnant belly visible beneath a dark dress",
                "clothing_or_outfit": "dark dress with soft shimmer",
                "injuries_or_physical_condition": "",
                "body_language_or_expression": "emotional_state=calm but watchful",
                "magical_or_physical_transformations": [],
                "recent_visual_changes": [],
                "evidence": [{"book_index": 5, "chapter": 75, "scene_id": "b5_c75_s1", "source": "entity_description", "text": "pregnant belly visible beneath a dark dress, painted hands"}],
                "confidence": "high",
                "risk_flags": [],
            },
            {
                "character_id": "char_noise",
                "display_name": "Cassian He",
                "baseline_description": "noise",
                "current_appearance": "",
                "clothing_or_outfit": "",
                "injuries_or_physical_condition": "",
                "body_language_or_expression": "",
                "magical_or_physical_transformations": [],
                "recent_visual_changes": [],
                "evidence": [{"book_index": 5, "chapter": 1, "scene_id": "b5_c1_s1", "source": "entity_description", "text": "bad parse"}],
                "confidence": "high",
                "risk_flags": [],
            },
            {
                "character_id": "char_empty",
                "display_name": "Tamlin",
                "baseline_description": "",
                "current_appearance": "",
                "clothing_or_outfit": "",
                "injuries_or_physical_condition": "",
                "body_language_or_expression": "",
                "magical_or_physical_transformations": [],
                "recent_visual_changes": [],
                "evidence": [],
                "confidence": "low",
                "risk_flags": ["sparse_visual_evidence"],
            },
            {
                "character_id": "char_object",
                "display_name": "Ataraxia",
                "baseline_description": "silver sword",
                "current_appearance": "",
                "clothing_or_outfit": "",
                "injuries_or_physical_condition": "",
                "body_language_or_expression": "",
                "magical_or_physical_transformations": [],
                "recent_visual_changes": [],
                "evidence": [{"book_index": 5, "chapter": 68, "scene_id": "b5_c68_s1", "source": "entity_description", "text": "silver sword"}],
                "confidence": "high",
                "risk_flags": [],
            },
        ],
        "location_visual_states": [
            {
                "location_id": "loc_how",
                "display_name": "House of Wind",
                "baseline_description": "mountain palace",
                "current_appearance": "open sky, stone floor",
                "architectural_or_environmental_details": "training ring atop a mountain palace",
                "atmosphere_or_mood": "dramatic mountain light",
                "recent_visual_changes": [],
                "evidence": [{"book_index": 5, "chapter": 68, "scene_id": "b5_c68_s1", "source": "location", "text": "training ring atop a mountain palace"}],
                "confidence": "high",
                "risk_flags": [],
            },
            {
                "location_id": "loc_training_ring",
                "display_name": "training ring",
                "baseline_description": "open stone training ring atop a mountain palace",
                "current_appearance": "windy open sky, stone floor",
                "architectural_or_environmental_details": "sparring circle with practice weapons nearby",
                "atmosphere_or_mood": "cold mountain light",
                "recent_visual_changes": [],
                "evidence": [{"book_index": 5, "chapter": 68, "scene_id": "b5_c68_s1", "source": "location", "text": "open stone training ring atop a mountain palace"}],
                "confidence": "high",
                "risk_flags": [],
            },
            {
                "location_id": "loc_river_house",
                "display_name": "river house",
                "baseline_description": "elegant riverside manor in Velaris",
                "current_appearance": "warm interior light, polished wood, painted halls",
                "architectural_or_environmental_details": "family house beside the Sidra",
                "atmosphere_or_mood": "quiet domestic warmth",
                "recent_visual_changes": [],
                "evidence": [{"book_index": 5, "chapter": 75, "scene_id": "b5_c75_s1", "source": "location", "text": "elegant riverside manor in Velaris"}],
                "confidence": "high",
                "risk_flags": [],
            },
        ],
        "entity_visual_states": [
            {
                "entity_id": "ent_ataraxia",
                "display_name": "Ataraxia",
                "entity_category": "weapon",
                "baseline_description": "silver sword",
                "current_appearance": "appearance_note=silver sword nearby",
                "material_or_texture": "polished silver metal",
                "magical_or_state_properties": ["magic=cauldron-forged"],
                "recent_visual_changes": [],
                "evidence": [{"book_index": 5, "chapter": 68, "scene_id": "b5_c68_s1", "source": "entity_description", "text": "silver sword nearby"}],
                "confidence": "high",
                "risk_flags": [],
            },
            {
                "entity_id": "ent_mask",
                "display_name": "Mask",
                "entity_category": "magical_artifact",
                "baseline_description": "ancient death mask",
                "current_appearance": "",
                "material_or_texture": "aged bone surface",
                "magical_or_state_properties": ["magic=deathly aura"],
                "recent_visual_changes": [],
                "evidence": [{"book_index": 5, "chapter": 70, "scene_id": "b5_c70_s1", "source": "entity_description", "text": "ancient death mask"}],
                "confidence": "high",
                "risk_flags": [],
            },
            {
                "entity_id": "ent_harp",
                "display_name": "Harp",
                "entity_category": "magical_artifact",
                "baseline_description": "ancient golden harp",
                "current_appearance": "",
                "material_or_texture": "golden metal and old strings",
                "magical_or_state_properties": ["magic=reality-bending resonance"],
                "recent_visual_changes": [],
                "evidence": [{"book_index": 5, "chapter": 75, "scene_id": "b5_c75_s1", "source": "entity_description", "text": "ancient golden harp"}],
                "confidence": "high",
                "risk_flags": [],
            },
        ],
    }


def test_high_confidence_character_becomes_prompt_pack() -> None:
    payload = ComfyUIPromptPackService().build(visual_state=_visual_payload())
    names = [row["display_name"] for row in payload["prompt_packs"]["characters"]]
    assert "Nesta" in names


def test_zero_evidence_low_confidence_character_is_suppressed_by_default() -> None:
    payload = ComfyUIPromptPackService().build(visual_state=_visual_payload())
    names = [row["display_name"] for row in payload["prompt_packs"]["characters"]]
    assert "Tamlin" not in names


def test_known_noisy_entries_are_suppressed() -> None:
    payload = ComfyUIPromptPackService().build(visual_state=_visual_payload())
    names = [row["display_name"] for row in payload["prompt_packs"]["characters"]]
    assert "Cassian He" not in names


def test_aliases_merge_for_prompt_output() -> None:
    payload = ComfyUIPromptPackService().build(visual_state=_visual_payload())
    names = [row["display_name"] for row in payload["prompt_packs"]["characters"]]
    assert "Rhysand" in names
    assert "Rhys" not in names
    assert "Nesta" in names
    assert "Lady Nesta" not in names


def test_object_entries_do_not_become_character_prompts() -> None:
    payload = ComfyUIPromptPackService().build(visual_state=_visual_payload())
    names = [row["display_name"] for row in payload["prompt_packs"]["characters"]]
    assert "Ataraxia" not in names


def test_location_entries_do_not_become_character_prompts() -> None:
    payload = ComfyUIPromptPackService().build(visual_state=_visual_payload())
    names = [row["display_name"] for row in payload["prompt_packs"]["characters"]]
    assert "House of Wind" not in names


def test_key_value_fragments_are_naturalized() -> None:
    payload = ComfyUIPromptPackService().build(visual_state=_visual_payload())
    nesta = next(row for row in payload["prompt_packs"]["characters"] if row["display_name"] == "Nesta")
    assert "bloodied hands, sap-coated fingers" in nesta["injury_condition_prompt"]
    assert "status=alive" not in json.dumps(payload)


def test_scene_prompt_combines_character_location_and_object() -> None:
    payload = ComfyUIPromptPackService().build(
        visual_state=_visual_payload(),
        focus_characters=["Nesta"],
        focus_locations=["House of Wind"],
        focus_entities=["Ataraxia"],
    )
    scenes = payload["prompt_packs"]["scene_prompts"]
    assert scenes
    prompt = scenes[0]["positive_prompt"]
    assert "House of Wind" in prompt
    assert "Nesta" in prompt
    assert "Ataraxia" in prompt


def test_scene_prompt_prefers_scene_specific_location_evidence() -> None:
    payload = ComfyUIPromptPackService().build(visual_state=_visual_payload())
    scene = next(
        row
        for row in payload["prompt_packs"]["scene_prompts"]
        if row.get("chapter") == 68 and "House of Wind" in (row.get("locations_used") or [])
    )
    prompt = scene["positive_prompt"]
    assert "training ring atop a mountain palace" in prompt
    assert "family house beside the Sidra" not in prompt


def test_negative_prompt_is_included() -> None:
    payload = ComfyUIPromptPackService().build(visual_state=_visual_payload())
    nesta = next(row for row in payload["prompt_packs"]["characters"] if row["display_name"] == "Nesta")
    assert nesta["negative_prompt"]


def test_output_json_schema_is_stable(tmp_path: Path) -> None:
    source = tmp_path / "visual_state.json"
    source.write_text(json.dumps(_visual_payload(), ensure_ascii=False, indent=2), encoding="utf-8")
    payload = ComfyUIPromptPackService().build_from_json_path(visual_state_path=source)
    assert {"source_visual_state", "target_point", "prompt_packs", "diagnostics"} <= set(payload.keys())
    assert {"characters", "locations", "objects", "scene_prompts"} <= set(payload["prompt_packs"].keys())


def test_full_pack_exports_one_prompt_per_kept_entity() -> None:
    payload = ComfyUIPromptPackService().build(visual_state=_visual_payload())
    diagnostics = payload["diagnostics"]
    assert diagnostics["character_count"] == 6
    assert diagnostics["location_count"] == 3
    assert diagnostics["object_count"] == 3


def test_curated_pack_generation_and_scoring() -> None:
    service = ComfyUIPromptPackService()
    prompt_pack = service.build(visual_state=_visual_payload())
    curated = service.build_curated_test_pack(prompt_pack)
    assert len(curated["curated_test_pack"]["characters"]) == 5
    assert len(curated["curated_test_pack"]["locations"]) == 3
    assert len(curated["curated_test_pack"]["objects"]) == 3
    assert curated["curated_test_pack"]["characters"][0]["score"]["comfyui_readiness"] >= 1


def test_unsupported_noisy_entries_excluded_from_curated_pack() -> None:
    service = ComfyUIPromptPackService()
    prompt_pack = service.build(visual_state=_visual_payload())
    curated = service.build_curated_test_pack(prompt_pack)
    names = [row["display_name"] for row in curated["curated_test_pack"]["characters"]]
    assert "Cassian He" not in names
    assert "Ataraxia" not in names


def test_prompts_do_not_contain_raw_key_value_fragments() -> None:
    service = ComfyUIPromptPackService()
    prompt_pack = service.build(visual_state=_visual_payload())
    blob = json.dumps(prompt_pack["prompt_packs"], ensure_ascii=False)
    assert "status=alive" not in blob


def test_scene_prompt_does_not_include_characters_without_evidence() -> None:
    service = ComfyUIPromptPackService()
    prompt_pack = service.build(visual_state=_visual_payload(), focus_characters=["Nesta"], focus_locations=["House of Wind"], focus_entities=["Ataraxia"])
    scene = prompt_pack["prompt_packs"]["scene_prompts"][0]
    assert "Rhysand" not in scene["characters_used"]


def test_scene_prompts_can_split_one_chapter_into_multiple_visual_beats() -> None:
    payload = ComfyUIPromptPackService().build(visual_state=_visual_payload())
    chapter_68 = [row for row in payload["prompt_packs"]["scene_prompts"] if row.get("chapter") == 68]
    assert len(chapter_68) >= 2
    location_sets = {tuple(row.get("locations_used") or []) for row in chapter_68}
    assert any("House of Wind" in locs for locs in location_sets)
    assert any("training ring" in locs for locs in location_sets)


def test_contract_backed_split_can_create_multiple_beats_in_same_location() -> None:
    service = ComfyUIPromptPackService()
    visual_state = {
        "target_point": {"mode": "post_book", "after_book_index": 5},
        "character_visual_states": [
            {
                "character_id": "char_nesta",
                "display_name": "Nesta",
                "baseline_description": "high fae woman",
                "current_appearance": "",
                "clothing_or_outfit": "Illyrian training leathers",
                "injuries_or_physical_condition": "condition=bloodied hands",
                "body_language_or_expression": "emotional_state=determined",
                "magical_or_physical_transformations": [],
                "recent_visual_changes": [],
                "evidence": [
                    {"book_index": 5, "chapter": 68, "scene_id": "b5_c68_s1", "source": "entity_description", "text": "Illyrian training leathers"},
                    {"book_index": 5, "chapter": 68, "scene_id": "b5_c68_s1", "source": "entity_description", "text": "bloodied hands"},
                ],
                "confidence": "high",
                "risk_flags": [],
            }
        ],
        "location_visual_states": [
            {
                "location_id": "loc_training_ring",
                "display_name": "training ring",
                "baseline_description": "open stone training ring atop a mountain palace",
                "current_appearance": "",
                "architectural_or_environmental_details": "",
                "atmosphere_or_mood": "",
                "recent_visual_changes": [],
                "evidence": [
                    {"book_index": 5, "chapter": 68, "scene_id": "b5_c68_s1", "source": "location", "text": "open stone training ring atop a mountain palace"},
                    {"book_index": 5, "chapter": 68, "scene_id": "b5_c68_s1", "source": "location", "text": "training ring under moonlight with practice swords nearby"},
                ],
                "confidence": "high",
                "risk_flags": [],
            }
        ],
        "entity_visual_states": [
            {
                "entity_id": "ent_ataraxia",
                "display_name": "Ataraxia",
                "entity_category": "weapon",
                "baseline_description": "silver sword",
                "current_appearance": "",
                "material_or_texture": "",
                "magical_or_state_properties": [],
                "recent_visual_changes": [],
                "evidence": [
                    {"book_index": 5, "chapter": 68, "scene_id": "b5_c68_s1", "source": "entity_description", "text": "silver sword nearby"},
                ],
                "confidence": "high",
                "risk_flags": [],
            }
        ],
    }
    contract = {
        "outputs": {
            "scene_analyses": [
                {
                    "book_index": 5,
                    "chapter_index": 68,
                    "scene_index": 1,
                    "text": "\n\n".join([
                        "Nesta stepped into the open stone training ring atop a mountain palace in Illyrian training leathers.",
                        "She lifted the practice weight and kept moving through the drills.",
                        "Later that night the training ring under moonlight with practice swords nearby felt colder and emptier.",
                        "Nesta stared at her bloodied hands and refused to stop.",
                        "Ataraxia lay as a silver sword nearby beside the wall.",
                    ]),
                }
            ]
        }
    }
    payload = service.build(visual_state=visual_state, contract=contract)
    chapter_68 = [row for row in payload["prompt_packs"]["scene_prompts"] if row.get("chapter") == 68]
    assert len(chapter_68) >= 2
    assert payload["diagnostics"]["contract_text_backed_scene_splitting"] is True
