from saga.domain.pipeline_contract import resolve_scene_analysis


def test_resolve_scene_analysis_canonicalizes_entity_world_state_character_aliases():
    scene = {
        "book_index": 1,
        "chapter_index": 2,
        "scene_index": 1,
        "scene_summary": "Feyre returns to the cottage and sees Isaac Hale.",
        "canonical_characters": [
            {"name": "Isaac", "names_used": ["Isaac"], "role": "", "is_new_character": False},
            {"name": "Feyre", "names_used": ["Feyre"], "role": "", "is_new_character": False},
        ],
        "character_mentions": [],
        "events": [],
        "entities_present": [
            {"name": "Isaac", "entity_type": "character"},
            {"name": "Isaac Hale", "entity_type": "character"},
        ],
        "entity_descriptions": [],
        "state_changes": [],
        "relationship_changes": [],
        "location": {},
        "time_signals": [],
        "alias_updates": [],
        "rejected_identity_candidates": [],
        "entity_world_state": {
            "entities": [
                {
                    "entity_name": "Isaac Hale",
                    "entity_type": "character",
                    "baseline_description": "broad-shouldered young man with a familiar village ease",
                    "typed_attributes": {
                        "appearance": ["broad-shouldered young man"],
                        "outfit": [],
                        "condition": [],
                        "body_language": ["familiar village ease"],
                        "possessions": [],
                        "abilities": [],
                        "titles_or_roles": [],
                        "affiliations": [],
                    },
                    "state_changes": [],
                    "source_evidence": ["Isaac Hale leaned against the wall"],
                }
            ]
        },
    }
    identity_result = {
        "identity_provider": "booknlp_clean",
        "provider_locked": True,
        "alias_map": {
            "Isaac": ["Isaac", "Isaac Hale"],
            "Feyre": ["Feyre"],
        },
        "rejected_non_characters": [],
    }

    resolved = resolve_scene_analysis(scene, identity_result)

    character_names = [
        item["name"]
        for item in resolved["entities_present"]
        if item.get("entity_type") == "character"
    ]
    assert character_names.count("Isaac") == 1
    assert "Isaac Hale" not in character_names
    assert resolved["entity_world_state"]["entities"][0]["entity_name"] == "Isaac"


def test_resolve_scene_analysis_canonicalizes_event_entities_involved_character_aliases():
    scene = {
        "book_index": 1,
        "chapter_index": 2,
        "scene_index": 1,
        "scene_summary": "Nesta speaks about Tomas Mandray and Isaac Hale.",
        "canonical_characters": [
            {"name": "Nesta", "names_used": ["Nesta"], "role": "", "is_new_character": False},
            {"name": "Isaac", "names_used": ["Isaac"], "role": "", "is_new_character": False},
            {"name": "Tomas", "names_used": ["Tomas"], "role": "", "is_new_character": False},
        ],
        "character_mentions": [],
        "events": [
            {
                "event_id": "evt_1",
                "description": "Nesta names Isaac Hale and Tomas Mandray as suitors.",
                "characters": ["Nesta"],
                "entities_involved": ["Isaac Hale", "Tomas Mandray"],
                "type": "interaction",
            }
        ],
        "entities_present": [
            {"name": "Nesta", "entity_type": "character"},
            {"name": "Isaac", "entity_type": "character"},
            {"name": "Tomas", "entity_type": "character"},
        ],
        "entity_descriptions": [],
        "state_changes": [],
        "relationship_changes": [],
        "location": {},
        "time_signals": [],
        "alias_updates": [],
        "rejected_identity_candidates": [],
        "entity_world_state": {"entities": []},
    }
    identity_result = {
        "identity_provider": "booknlp_clean",
        "provider_locked": True,
        "alias_map": {
            "Isaac": ["Isaac", "Isaac Hale"],
            "Tomas": ["Tomas", "Tomas Mandray"],
            "Nesta": ["Nesta"],
        },
        "rejected_non_characters": [],
    }

    resolved = resolve_scene_analysis(scene, identity_result)

    assert resolved["events"][0]["entities_involved"] == ["Isaac", "Tomas"]
    character_names = [
        (item["name"], item["entity_type"])
        for item in resolved["entities_present"]
    ]
    assert ("Isaac Hale", "object") not in character_names
    assert ("Tomas Mandray", "object") not in character_names


def test_resolve_scene_analysis_recovers_event_participant_when_missing_from_entities():
    scene = {
        "book_index": 1,
        "chapter_index": 3,
        "scene_index": 1,
        "scene_summary": "Feyre speaks with the mercenary.",
        "canonical_characters": [
            {"name": "Feyre", "names_used": ["Feyre"], "role": "", "is_new_character": False},
        ],
        "character_mentions": [],
        "events": [
            {
                "event_id": "evt_mercenary",
                "description": "Feyre bargains with the mercenary.",
                "characters": ["Feyre"],
                "entities_involved": ["Feyre", "the mercenary"],
                "reason": "Feyre needs information.",
                "outcome": "The mercenary answers.",
                "type": "interaction",
            }
        ],
        "entities_present": [{"name": "Feyre", "entity_type": "character"}],
        "entity_descriptions": [
            {
                "entity_name": "the mercenary",
                "entity_type": "object",
                "description": "hardened female mercenary with watchful eyes",
                "description_type": "stable_trait",
            }
        ],
        "state_changes": [],
        "relationship_changes": [],
        "location": {},
        "time_signals": [],
        "alias_updates": [],
        "rejected_identity_candidates": [],
        "entity_world_state": {"entities": []},
    }
    identity_result = {
        "identity_provider": "booknlp_clean",
        "provider_locked": True,
        "alias_map": {"Feyre": ["Feyre"]},
        "rejected_non_characters": [],
    }

    resolved = resolve_scene_analysis(scene, identity_result)

    assert ("the mercenary", "character") in [
        (item["name"], item["entity_type"])
        for item in resolved["entities_present"]
    ]
