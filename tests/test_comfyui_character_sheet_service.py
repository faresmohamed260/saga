import json

from services.comfyui_character_sheet_service import ComfyUICharacterSheetService


def _row(name, *, confidence="high", species="human", role="wizard", prompt="prompt", source="") -> dict:
    return {
        "entity_name": name,
        "positive_prompt": prompt,
        "confidence": confidence,
        "details": {
            "persistent_visual_profile": {
                "species_or_race": species,
                "role_or_archetype": role,
                "model_safe_identity": f"{species} {role}".strip(),
                "hair_description": "dark hair",
                "eye_description": "green eyes",
            }
        },
        "source_evidence": source,
    }


def test_collect_character_prompts_merges_alias_duplicates_and_skips_creatures(tmp_path):
    contract_path = tmp_path / "hp.contract.json"
    contract_payload = {
        "outputs": {
            "identity_result": {
                "alias_map": {
                    "Harry": ["Harry", "Harry Potter", "Harry wizard"],
                    "Hermione": ["Hermione", "Hermione Granger"],
                    "Professor McGonagall": ["Professor McGonagall", "Minerva McGonagall"],
                    "Dudley": ["Dudley", "Dudley Dursley"],
                    "Hagrid": ["Hagrid", "Rubeus Hagrid"],
                }
            },
            "entity_registry": [
                {"name": "Harry", "entity_type": "character", "descriptions": [{"description": "boy wizard", "description_type": "stable_trait"}]},
                {"name": "Hermione", "entity_type": "character", "descriptions": [{"description": "student witch", "description_type": "stable_trait"}]},
                {"name": "Professor McGonagall", "entity_type": "character", "descriptions": [{"description": "professor in emerald robes", "description_type": "stable_trait"}]},
                {"name": "Hagrid", "entity_type": "character", "descriptions": [{"description": "half-giant gamekeeper", "description_type": "stable_trait"}]},
                {"name": "Fang", "entity_type": "character", "descriptions": [{"description": "enormous black boarhound", "description_type": "stable_trait"}]},
                {"name": "Firenze", "entity_type": "character", "descriptions": [{"description": "centaur with palomino horse body", "description_type": "stable_trait"}]},
                {"name": "Giant", "entity_type": "object", "descriptions": [{"description": "giant of a man in a black overcoat", "description_type": "stable_trait"}]},
            ],
            "visual_prompt_sets": {
                "initial_characters": [
                    _row("Harry", confidence="high", species="human", role="boy wizard", prompt="strong harry prompt"),
                    _row("Harry Potter", confidence="medium", species="human", role="young wizard", prompt="weaker potter prompt"),
                    _row("Hermione", confidence="low", species="human", role="student", prompt="short hermione prompt"),
                    _row("Hermione Granger", confidence="high", species="human", role="student witch", prompt="best hermione prompt"),
                    _row("Professor McGonagall", confidence="high", species="human", role="wizard", prompt="mcgonagall prompt"),
                    _row("Minerva McGonagall", confidence="low", species="human", role="wizard", prompt="minerva prompt"),
                    _row("Hagrid", confidence="high", species="human", role="half-giant gamekeeper", prompt="hagrid prompt"),
                    _row("Rubeus Hagrid", confidence="high", species="human", role="gamekeeper", prompt="rubeus hagrid prompt"),
                    _row("Dudley", confidence="high", species="human", role="older brother", prompt="dudley prompt"),
                    _row("Dudley Dursley", confidence="low", species="human", role="child", prompt="dudley dursley prompt"),
                    _row("Fang", confidence="high", species="large dog", role="", prompt="fang prompt"),
                    _row("Firenze", confidence="high", species="centaur", role="centaur guide", prompt="firenze prompt"),
                    _row("Giant", confidence="high", species="human (giant stature)", role="mysterious benefactor", prompt="giant prompt"),
                ]
            },
        }
    }
    contract_path.write_text(json.dumps(contract_payload), encoding="utf-8")

    rows = ComfyUICharacterSheetService().collect_character_prompts(contract_path)
    names = [row["entity_name"] for row in rows]

    assert "Harry" in names
    assert "Hermione" in names
    assert "Hagrid" in names
    assert "Dudley" not in names
    assert "Fang" not in names
    assert "Firenze" not in names
    assert "Giant" not in names


def test_collect_entity_visual_prompts_uses_entity_registry_as_source_of_truth(tmp_path):
    contract_path = tmp_path / "entities.contract.json"
    contract_payload = {
        "outputs": {
            "identity_result": {"alias_map": {}},
            "entity_registry": [
                {
                    "name": "Harry Potter",
                    "entity_type": "character",
                    "first_seen": {"book_index": 1, "chapter_index": 1, "scene_index": 1},
                    "first_appearance_profile": {
                        "baseline_description": "thin boy with messy black hair and round glasses",
                        "typed_attributes": {
                            "appearance": ["thin build", "messy black hair", "round glasses"],
                            "outfit": ["school uniform"],
                            "body_language": ["neutral expression"],
                            "possessions": ["wand"],
                            "titles_or_roles": ["student wizard"],
                            "affiliations": ["Hogwarts"],
                        },
                    },
                    "descriptions": [{"description": "thin boy with messy black hair and round glasses", "description_type": "stable_trait"}],
                },
                {
                    "name": "Fang",
                    "entity_type": "character",
                    "first_seen": {"book_index": 1, "chapter_index": 6, "scene_index": 1},
                    "descriptions": [{"description": "enormous black boarhound with heavy paws", "description_type": "stable_trait"}],
                    "typed_attributes": {"appearance": ["enormous black boarhound"]},
                },
                {
                    "name": "Hogwarts",
                    "entity_type": "location",
                    "first_seen": {"book_index": 1, "chapter_index": 7, "scene_index": 1},
                    "descriptions": [{"description": "vast stone castle lit by torches", "description_type": "stable_trait"}],
                },
                {
                    "name": "Sorting Hat",
                    "entity_type": "object",
                    "first_seen": {"book_index": 1, "chapter_index": 7, "scene_index": 1},
                    "descriptions": [{"description": "old pointed hat with a wide tear like a mouth", "description_type": "stable_trait"}],
                },
            ],
            "visual_prompt_sets": {
                "initial_characters": [
                    _row("Harry", confidence="high", species="human", role="student wizard", prompt="harry sheet prompt", source="harry intro"),
                    _row("Fang", confidence="high", species="large dog", role="", prompt="fang wrong character prompt", source="fang intro"),
                ],
                "objects_creatures": [
                    {
                        "entity_name": "Sorting Hat",
                        "entity_type": "object",
                        "positive_prompt": "sorting hat object prompt",
                        "confidence": "high",
                        "source_evidence": "old pointed hat",
                        "details": {},
                    }
                ],
                "locations": [
                    {
                        "entity_name": "Hogwarts",
                        "entity_type": "location",
                        "positive_prompt": "hogwarts location prompt",
                        "confidence": "high",
                        "source_evidence": "stone castle",
                        "details": {},
                    }
                ],
            },
        }
    }
    contract_path.write_text(json.dumps(contract_payload), encoding="utf-8")

    rows = ComfyUICharacterSheetService().collect_entity_visual_prompts(contract_path)

    assert len(rows) == 4
    by_name = {row["entity_name"]: row for row in rows}
    assert by_name["Harry Potter"]["entity_type"] == "character"
    assert by_name["Harry Potter"]["workflow_mode"] == "character_sheet"
    assert "three-view layout" in by_name["Harry Potter"]["positive_prompt"].lower()
    assert by_name["Fang"]["entity_type"] == "creature"
    assert by_name["Fang"]["workflow_mode"] == "default"
    assert "non-human fantasy creature" in by_name["Fang"]["positive_prompt"].lower()
    assert by_name["Hogwarts"]["entity_type"] == "location"
    assert by_name["Hogwarts"]["workflow_mode"] == "default"
    assert "hogwarts location prompt" in by_name["Hogwarts"]["positive_prompt"].lower()
    assert by_name["Sorting Hat"]["entity_type"] == "object"
    assert by_name["Sorting Hat"]["workflow_mode"] == "default"


def test_build_render_manifest_emits_all_entity_types_with_per_item_workflows(tmp_path):
    contract_path = tmp_path / "manifest.contract.json"
    contract_payload = {
        "outputs": {
            "identity_result": {"alias_map": {}},
            "entity_registry": [
                {
                    "name": "Harry Potter",
                    "entity_type": "character",
                    "first_seen": {"book_index": 1, "chapter_index": 1, "scene_index": 1},
                    "descriptions": [{"description": "boy with glasses", "description_type": "stable_trait"}],
                    "typed_attributes": {"titles_or_roles": ["student wizard"]},
                },
                {
                    "name": "Hedwig",
                    "entity_type": "creature",
                    "first_seen": {"book_index": 1, "chapter_index": 5, "scene_index": 1},
                    "descriptions": [{"description": "snowy owl with bright amber eyes", "description_type": "stable_trait"}],
                },
                {
                    "name": "Hogwarts",
                    "entity_type": "location",
                    "first_seen": {"book_index": 1, "chapter_index": 7, "scene_index": 1},
                    "descriptions": [{"description": "castle with high towers and torchlit halls", "description_type": "stable_trait"}],
                },
                {
                    "name": "Sorting Hat",
                    "entity_type": "object",
                    "first_seen": {"book_index": 1, "chapter_index": 7, "scene_index": 1},
                    "descriptions": [{"description": "old pointed hat with a mouthlike tear", "description_type": "stable_trait"}],
                },
            ],
            "visual_prompt_sets": {},
        }
    }
    contract_path.write_text(json.dumps(contract_payload), encoding="utf-8")

    manifest = ComfyUICharacterSheetService().build_render_manifest(contract_path)
    renders = manifest["renders"]
    assert len(renders) == 4
    by_name = {row["entity_name"]: row for row in renders}
    assert by_name["Harry Potter"]["workflow_mode"] == "character_sheet"
    assert by_name["Harry Potter"]["width"] == 1504
    assert by_name["Harry Potter"]["height"] == 1024
    assert by_name["Hedwig"]["workflow_mode"] == "default"
    assert by_name["Hedwig"]["width"] == 1024
    assert by_name["Hedwig"]["height"] == 1024
    assert by_name["Hogwarts"]["workflow_mode"] == "default"
    assert by_name["Hogwarts"]["width"] == 1344
    assert by_name["Hogwarts"]["height"] == 768
