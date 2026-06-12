from analysis.visual_prompt_schema import (
    compile_character_edit_prompt,
    compile_character_turnaround_prompt,
    enrich_persistent_profile_from_legacy_fields,
    normalize_dynamic_visual_changes,
    normalize_persistent_profile,
)


def test_turnaround_prompt_uses_model_safe_translation_for_lore_terms():
    profile = normalize_persistent_profile(
        {
            "gender_presentation": "male",
            "species_or_race": "Illyrian",
            "role_or_archetype": "warrior leader",
            "presence_description": "commanding authoritative presence",
            "height_description": "tall",
            "body_type": "lean athletic build",
            "hair_description": "dark hair",
            "eye_description": "violet eyes",
            "fantasy_features": "large dark feathered wings folded behind him",
        }
    )

    prompt = compile_character_turnaround_prompt(profile, display_name="Rhysand")

    assert "winged fantasy humanoid warrior leader" in prompt
    assert "Illyrian" not in prompt
    assert "three-view layout" in prompt


def test_dynamic_visual_change_generates_identity_preserving_edit_prompt():
    changes = normalize_dynamic_visual_changes(
        [
            {
                "change_label": "under the mountain aftermath",
                "visible_condition_change": "bruised ribs and healing cuts",
                "outfit_change": "dirty torn dress",
                "body_language_change": "exhausted guarded posture",
            }
        ],
        display_name="Feyre",
    )

    assert len(changes) == 1
    assert "Keep the same face" in changes[0]["image_edit_prompt"]
    assert "dirty torn dress" in changes[0]["image_edit_prompt"]


def test_profile_enrichment_strips_scene_context_from_baseline_fields():
    profile = enrich_persistent_profile_from_legacy_fields(
        normalize_persistent_profile(
            {
                "gender_presentation": "female",
                "species_or_race": "human",
                "role_or_archetype": "peasant hunter",
                "presence_description": "standing in a dim, simple cottage with a deer carcass on the table",
            }
        ),
        physical_description="slender young woman with long brown hair and gray-blue eyes",
        outfit="worn cloak and gloves",
    )

    assert profile["presence_description"] == ""
    assert "long brown hair" in profile["hair_description"].lower()
    assert "gray-blue eyes" in profile["eye_description"].lower()
    assert "worn cloak and gloves" == profile["clothing_description"]


def test_profile_enrichment_splits_combined_trait_blob_into_cleaner_slots():
    profile = enrich_persistent_profile_from_legacy_fields(
        normalize_persistent_profile(
            {
                "gender_presentation": "young woman",
                "species_or_race": "human",
                "role_or_archetype": "hunter, protector",
            }
        ),
        physical_description="young woman, gaunt from hunger, thin frame, tangled brown hair pulled back, pale skin, gray-blue eyes",
        outfit="threadbare cloak and ragged boots",
    )

    assert profile["gender_presentation"] == "female"
    assert profile["role_or_archetype"] == "hunter"
    assert profile["body_type"] == "gaunt from hunger"
    assert "brown hair" in profile["hair_description"].lower()
    assert profile["skin_description"] == "pale skin"
    assert profile["eye_description"] == "gray-blue eyes"
    assert profile["clothing_description"] == "threadbare cloak and ragged boots"


def test_invalid_placeholder_traits_are_removed():
    profile = enrich_persistent_profile_from_legacy_fields(
        normalize_persistent_profile(
            {
                "gender_presentation": "female",
                "species_or_race": "human",
                "role_or_archetype": "hunter",
                "eye_description": "eyes unseen in text",
            }
        ),
        physical_description="dark hair tied back, pale skin",
    )

    prompt = compile_character_turnaround_prompt(profile, display_name="Feyre")

    assert "unseen in text" not in prompt.lower()
    assert "dark hair tied back" in prompt.lower()


def test_model_safe_identity_is_promoted_into_structured_slots():
    profile = enrich_persistent_profile_from_legacy_fields(
        normalize_persistent_profile(
            {
                "gender_presentation": "female",
                "species_or_race": "human",
                "role_or_archetype": "hunter",
                "model_safe_identity": "young woman with pale skin, long brown hair, brown eyes",
            }
        )
    )

    assert profile["skin_description"] == "pale skin"
    assert "brown hair" in profile["hair_description"].lower()
    assert profile["eye_description"] == "brown eyes"
