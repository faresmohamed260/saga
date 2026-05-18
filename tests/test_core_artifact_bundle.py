from core.builders.artifact_bundle_builder import ArtifactBundleBuilder


def _sample_scene_analyses():
    return [
        {
            "book_index": 1,
            "chapter_index": 1,
            "scene_index": 1,
            "scene_summary": "Harry and Hermione regroup after the battle.",
            "canonical_characters": [{"name": "Harry Potter"}, {"name": "Hermione Granger"}],
            "events": [
                {
                    "event_id": "evt_1",
                    "description": "Harry and Hermione regroup after the battle.",
                    "characters": ["Harry Potter", "Hermione Granger"],
                }
            ],
            "relationship_changes": [
                {
                    "source_entity": "Harry Potter",
                    "target_entity": "Hermione Granger",
                    "relationship": "friendship",
                    "change": "deepens",
                    "evidence": "They rely on each other after the battle.",
                }
            ],
            "entities_present": [
                {"name": "Department of Mysteries", "entity_type": "location"},
                {"name": "Prophecy", "entity_type": "object"},
            ],
            "location": {"name": "Department of Mysteries"},
            "time_signals": ["after the battle"],
            "state_changes": [
                {
                    "entity_name": "Harry Potter",
                    "entity_type": "character",
                    "attribute": "grief",
                    "new_state": "intensified",
                    "evidence": "He mourns Sirius.",
                    "book_index": 1,
                    "chapter_index": 1,
                    "scene_index": 1,
                }
            ],
        },
        {
            "book_index": 1,
            "chapter_index": 2,
            "scene_index": 1,
            "scene_summary": "Harry confides in Hermione at Grimmauld Place.",
            "canonical_characters": [{"name": "Harry Potter"}, {"name": "Hermione Granger"}],
            "events": [
                {
                    "event_id": "evt_2",
                    "description": "Harry confides in Hermione at Grimmauld Place.",
                    "characters": ["Harry Potter", "Hermione Granger"],
                }
            ],
            "relationship_changes": [
                {
                    "source_entity": "Harry Potter",
                    "target_entity": "Hermione Granger",
                    "relationship": "friendship",
                    "change": "grows closer",
                    "evidence": "Harry opens up to Hermione.",
                }
            ],
            "entities_present": [{"name": "Grimmauld Place", "entity_type": "location"}],
            "location": {"name": "Grimmauld Place"},
            "time_signals": ["that evening"],
            "state_changes": [
                {
                    "entity_name": "Harry Potter",
                    "entity_type": "character",
                    "attribute": "trust",
                    "new_state": "more open with Hermione",
                    "evidence": "He confides in her.",
                    "book_index": 1,
                    "chapter_index": 2,
                    "scene_index": 1,
                }
            ],
        },
    ]


def _sample_timeline():
    return [
        {
            "time_index": 1,
            "event_id": "evt_1",
            "summary": "Harry and Hermione regroup after the battle.",
            "book_index": 1,
            "chapter_index": 1,
            "scene_index": 1,
            "characters": ["Harry Potter", "Hermione Granger"],
        },
        {
            "time_index": 2,
            "event_id": "evt_2",
            "summary": "Harry confides in Hermione at Grimmauld Place.",
            "book_index": 1,
            "chapter_index": 2,
            "scene_index": 1,
            "characters": ["Harry Potter", "Hermione Granger"],
        },
    ]


def _sample_character_timelines():
    return [
        {
            "character": "Harry Potter",
            "events": [
                {"summary": "Regroups after the battle.", "time_index": 1},
                {"summary": "Confides in Hermione.", "time_index": 2},
            ],
        },
        {
            "character": "Hermione Granger",
            "events": [
                {"summary": "Supports Harry after the battle.", "time_index": 1},
                {"summary": "Listens to Harry at Grimmauld Place.", "time_index": 2},
            ],
        },
    ]


def _sample_entity_registry():
    return [
        {
            "name": "Harry Potter",
            "entity_type": "character",
            "descriptions": [{"description_type": "stable_trait", "description": "Brave and impulsive."}],
            "state_changes": [
                {
                    "attribute": "grief",
                    "new_state": "intensified",
                    "book_index": 1,
                    "chapter_index": 1,
                    "scene_index": 1,
                },
                {
                    "attribute": "trust",
                    "new_state": "more open with Hermione",
                    "book_index": 1,
                    "chapter_index": 2,
                    "scene_index": 1,
                },
            ],
            "first_seen": {"book_index": 1, "chapter_index": 1, "scene_index": 1},
            "mention_count": 5,
        },
        {
            "name": "Hermione Granger",
            "entity_type": "character",
            "descriptions": [{"description_type": "stable_trait", "description": "Brilliant and observant."}],
            "state_changes": [],
            "first_seen": {"book_index": 1, "chapter_index": 1, "scene_index": 1},
            "mention_count": 4,
        },
        {
            "name": "Grimmauld Place",
            "entity_type": "location",
            "descriptions": [{"description_type": "location_note", "description": "The Black family house."}],
            "state_changes": [],
            "first_seen": {"book_index": 1, "chapter_index": 2, "scene_index": 1},
            "mention_count": 1,
        },
    ]


def _sample_state_result():
    return {
        "transitions": [
            {
                "state_index": 1,
                "entity_name": "Harry Potter",
                "entity_type": "character",
                "attribute": "grief",
                "new_state": "intensified",
                "book_index": 1,
                "chapter_index": 1,
                "scene_index": 1,
            },
            {
                "state_index": 2,
                "entity_name": "Harry Potter",
                "entity_type": "character",
                "attribute": "trust",
                "new_state": "more open with Hermione",
                "book_index": 1,
                "chapter_index": 2,
                "scene_index": 1,
            },
        ],
        "latest_state": [
            {
                "entity_name": "Harry Potter",
                "entity_type": "character",
                "attributes": {
                    "grief": "intensified",
                    "trust": "more open with Hermione",
                },
            }
        ],
    }


def _sample_identity_result():
    return {
        "alias_map": {
            "Harry Potter": ["Harry Potter", "Harry"],
            "Hermione Granger": ["Hermione Granger", "Hermione"],
        },
        "decisions": [],
    }


def _sample_causal_graph_result():
    return {
        "graph": {
            "events": [
                {
                    "id": "cg_1",
                    "time_index": 1,
                    "book_index": 1,
                    "chapter_index": 1,
                    "scene_index": 1,
                    "description": "Regrouping after the battle.",
                    "characters": ["Harry Potter", "Hermione Granger"],
                    "caused_by": [],
                    "causes": [{"event_id": "evt_2"}],
                },
                {
                    "id": "cg_2",
                    "time_index": 2,
                    "book_index": 1,
                    "chapter_index": 2,
                    "scene_index": 1,
                    "description": "Harry confides in Hermione.",
                    "characters": ["Harry Potter", "Hermione Granger"],
                    "caused_by": [{"event_id": "evt_1"}],
                    "causes": [],
                },
            ]
        }
    }


def build_sample_artifact_bundle():
    return ArtifactBundleBuilder().build(
        resolved_scene_analyses=_sample_scene_analyses(),
        identity_result=_sample_identity_result(),
        timeline=_sample_timeline(),
        state_result=_sample_state_result(),
        entity_registry=_sample_entity_registry(),
        causal_graph_result=_sample_causal_graph_result(),
        character_timelines=_sample_character_timelines(),
    )


def test_artifact_bundle_builds_expected_families():
    bundle = build_sample_artifact_bundle()

    assert bundle["bundle_version"]
    assert len(bundle["event_ledger"]) == 2
    assert len(bundle["character_profiles"]) == 2
    assert len(bundle["relationship_profiles"]) == 1
    assert any(item["name"] == "Grimmauld Place" for item in bundle["entity_profiles"])
    assert len(bundle["canon_snapshots"]) == 2
    assert bundle["arc_registry"]["items"]
    assert bundle["knowledge_registry"]["items"]
    assert bundle["constraint_registry"]["items"]
    relationship = bundle["relationship_profiles"][0]
    first_event = bundle["event_ledger"][0]
    second_event = bundle["event_ledger"][1]
    assert first_event["direct_consequences"]
    assert first_event["stakes"]
    assert second_event["preconditions"]
    assert any("Leads to:" in item for item in first_event["direct_consequences"])
    assert any("Depends on:" in item for item in second_event["preconditions"])
    assert relationship["trust_level"] in {"medium", "high"}
    assert relationship["romantic_signal"] in {"possible", "strong", "none"}


def test_artifact_bundle_is_deterministic():
    first = build_sample_artifact_bundle()
    second = build_sample_artifact_bundle()

    assert first["event_ledger"] == second["event_ledger"]
    assert first["character_profiles"] == second["character_profiles"]
    assert first["relationship_profiles"] == second["relationship_profiles"]
    assert first["entity_profiles"] == second["entity_profiles"]
    assert first["canon_snapshots"] == second["canon_snapshots"]
    assert first["arc_registry"] == second["arc_registry"]
    assert first["knowledge_registry"] == second["knowledge_registry"]
    assert first["constraint_registry"] == second["constraint_registry"]
