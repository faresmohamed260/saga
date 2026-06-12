from entities.entity_registry_service import EntityRegistryService
from rag.scene_index_service import SceneIndexService
from state.canon_state_service import CanonStateService
from state.state_transition_service import StateTransitionService


def build_sample_analyzed_scenes():
    return [
        {
            "book_index": 1,
            "chapter_index": 1,
            "scene_index": 1,
            "length": 180,
            "text": "Feyre hunts in the winter forest and kills a wolf with an ash arrow.",
            "scene_summary": "Feyre hunts and kills the wolf.",
            "events": [
                {
                    "event_id": "evt_1",
                    "description": "Feyre kills the wolf.",
                    "characters": ["Feyre", "Wolf"],
                    "type": "action",
                }
            ],
            "entities_present": [
                {"name": "Feyre", "entity_type": "character"},
                {"name": "Wolf", "entity_type": "creature"},
            ],
            "entity_descriptions": [
                {
                    "entity_name": "Feyre",
                    "entity_type": "character",
                    "description": "a huntress in the snow",
                    "description_type": "stable_trait",
                }
            ],
            "state_changes": [
                {
                    "entity_name": "Wolf",
                    "entity_type": "creature",
                    "attribute": "status",
                    "previous_state": "alive",
                    "new_state": "dead",
                    "change_type": "physical_state",
                    "evidence": "Feyre kills the wolf.",
                }
            ],
            "relationship_changes": [],
            "location": {
                "name": "the forest",
                "entity_type": "location",
                "description": "snowy winter woods",
            },
            "time_signals": ["winter"],
            "entity_world_state": {
                "entities": [
                    {
                        "entity_name": "Feyre",
                        "entity_type": "character",
                        "narrative_role": "protagonist",
                        "baseline_description": "a huntress in the snow",
                        "typed_attributes": {
                            "appearance": ["wind-chapped face"],
                            "outfit": ["worn cloak"],
                            "condition": ["hungry"],
                            "body_language": [],
                            "possessions": ["ash bow"],
                            "abilities": [],
                            "titles_or_roles": ["huntress"],
                            "affiliations": [],
                        },
                        "state_changes": [],
                        "source_evidence": ["a huntress in the snow"],
                        "confidence": "high",
                    },
                    {
                        "entity_name": "ash arrow",
                        "entity_type": "object",
                        "narrative_role": "weapon",
                        "baseline_description": "an ash arrow ready to kill a wolf",
                        "typed_attributes": {
                            "appearance": ["ash arrow"],
                            "materials": ["ash wood"],
                            "abilities": [],
                            "owner_or_holder": ["Feyre"],
                            "current_state": ["nocked on the bow"],
                            "symbolic_role": ["defense"],
                        },
                        "state_changes": [],
                        "source_evidence": ["ash arrow"],
                        "confidence": "high",
                    },
                ],
                "diagnostics": {},
            },
        },
        {
            "book_index": 1,
            "chapter_index": 1,
            "scene_index": 2,
            "length": 170,
            "text": "Tamlin takes Feyre to the Spring Court manor.",
            "scene_summary": "Tamlin brings Feyre to the manor.",
            "events": [
                {
                    "event_id": "evt_1",
                    "description": "Tamlin takes Feyre to the manor.",
                    "characters": ["Tamlin", "Feyre"],
                    "type": "movement",
                }
            ],
            "entities_present": [
                {"name": "Feyre", "entity_type": "character"},
                {"name": "Tamlin", "entity_type": "character"},
            ],
            "entity_descriptions": [
                {
                    "entity_name": "Tamlin",
                    "entity_type": "character",
                    "description": "wearing a mask",
                    "description_type": "appearance_note",
                }
            ],
            "state_changes": [
                {
                    "entity_name": "Feyre",
                    "entity_type": "character",
                    "attribute": "location",
                    "previous_state": "",
                    "new_state": "Spring Court manor",
                    "change_type": "location",
                    "evidence": "Tamlin takes Feyre to the Spring Court manor.",
                }
            ],
            "relationship_changes": [
                {
                    "source_entity": "Feyre",
                    "target_entity": "Tamlin",
                    "relationship": "meets",
                    "change": "first sustained contact",
                    "evidence": "Tamlin takes Feyre to the Spring Court manor.",
                }
            ],
            "location": {
                "name": "Spring Court manor",
                "entity_type": "location",
                "description": "Tamlin's estate",
            },
            "time_signals": [],
            "entity_world_state": {
                "entities": [
                    {
                        "entity_name": "Tamlin",
                        "entity_type": "character",
                        "narrative_role": "captor",
                        "baseline_description": "a powerful fae male wearing a mask",
                        "typed_attributes": {
                            "appearance": ["broad-shouldered fae male"],
                            "outfit": ["wearing a mask"],
                            "condition": [],
                            "body_language": [],
                            "possessions": [],
                            "abilities": [],
                            "titles_or_roles": ["High Lord"],
                            "affiliations": ["Spring Court"],
                        },
                        "state_changes": [],
                        "source_evidence": ["wearing a mask"],
                        "confidence": "high",
                    }
                ],
                "diagnostics": {},
            },
        },
    ]


def test_scene_index_service():
    scenes = build_sample_analyzed_scenes()
    service = SceneIndexService(min_similarity=0.05, max_results=3)
    service.build(scenes)

    forest_results = service.retrieve("Feyre wolf ash arrow")
    manor_results = service.retrieve("Tamlin manor", min_similarity=0.05)

    assert len(forest_results) >= 1
    assert forest_results[0]["scene_index"] == 1
    assert len(manor_results) >= 1
    assert manor_results[0]["scene_index"] == 2


def test_entity_registry_and_state_services():
    scenes = build_sample_analyzed_scenes()

    registry = EntityRegistryService().build(scenes)
    registry_by_name = {item["name"]: item for item in registry}

    assert "Feyre" in registry_by_name
    assert registry_by_name["Feyre"]["mention_count"] == 2
    assert "Spring Court manor" in registry_by_name
    assert registry_by_name["Spring Court manor"]["entity_type"] == "location"
    assert "ash arrow" in registry_by_name
    assert registry_by_name["Feyre"]["typed_attributes"]["outfit"] == ["worn cloak"]
    assert registry_by_name["Tamlin"]["first_appearance_profile"]["status"] == "captured"

    transition_result = StateTransitionService().build(scenes)
    transitions = transition_result["transitions"]
    latest_state = transition_result["latest_state"]
    latest_by_name = {item["entity_name"]: item for item in latest_state}

    assert len(transitions) == 2
    assert transitions[0]["entity_name"] == "Wolf"
    assert transitions[1]["entity_name"] == "Feyre"
    assert latest_by_name["Wolf"]["attributes"]["status"] == "dead"
    assert latest_by_name["Feyre"]["attributes"]["location"] == "Spring Court manor"

    canon = CanonStateService()
    early_snapshot = canon.snapshot_at(transitions, scene_ref=(1, 1, 1))
    late_snapshot = canon.snapshot_at(transitions, scene_ref=(1, 1, 2))

    early_by_name = {item["entity_name"]: item for item in early_snapshot}
    late_by_name = {item["entity_name"]: item for item in late_snapshot}

    assert "Wolf" in early_by_name
    assert early_by_name["Wolf"]["attributes"]["status"] == "dead"
    assert "Feyre" not in early_by_name or "location" not in early_by_name["Feyre"]["attributes"]
    assert late_by_name["Feyre"]["attributes"]["location"] == "Spring Court manor"
