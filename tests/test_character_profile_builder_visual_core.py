from core.builders.character_profile_builder import CharacterProfileBuilder


def test_character_profile_builder_prefers_first_appearance_visual_baseline_for_core_description():
    profiles = CharacterProfileBuilder().build(
        character_timelines=[{"character": "Isaac", "events": [{"event_id": "evt_1"}]}],
        entity_registry=[
            {
                "name": "Isaac",
                "entity_type": "character",
                "descriptions": [
                    {"description": "mentioned only by name; no visual details", "description_type": "stable_trait"}
                ],
                "typed_attributes": {
                    "appearance": ["young", "lean", "brown shaggy hair"],
                    "outfit": ["simple coat"],
                    "condition": [],
                    "body_language": [],
                    "possessions": [],
                    "abilities": [],
                    "titles_or_roles": [],
                    "affiliations": [],
                },
                "first_appearance_profile": {
                    "status": "captured",
                    "baseline_description": "young, lean, brown shaggy hair, simple coat",
                    "typed_attributes": {},
                    "source": {"book_index": 1, "chapter_index": 2, "scene_index": 1},
                },
                "first_seen": {"book_index": 1, "chapter_index": 2, "scene_index": 1},
                "mention_count": 2,
                "state_changes": [],
            }
        ],
        state_result={"latest_state": []},
        identity_result={"alias_map": {"Isaac": ["Isaac", "Isaac Hale"]}},
        scene_analyses=[],
    )

    assert profiles[0]["core_description"] == "young, lean, brown shaggy hair, simple coat"
