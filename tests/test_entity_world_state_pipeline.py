from analysis.entity_world_state_analyzer import EntityWorldStateAnalyzer
from analysis.scene_contract_reconciler import reconcile_scene_contract


class StubLLMClient:
    def __init__(self, response):
        self.response = response
        self.mode = "gpt_oss"

    def generate_json(self, prompt: str, strict: bool = False, validator=None, **kwargs):
        if validator and not validator(self.response):
            return {"error": "validation_failed", "last_error": "stub validation failed"}
        return self.response

    def provider_name(self):
        return "ollama"

    def resolved_model_name(self):
        return "gpt-oss:120b-cloud"

    def last_request_metadata(self):
        return {
            "provider_family": "ollama",
            "resolved_model": "gpt-oss:120b-cloud",
            "provider_account_alias": "test-account",
            "rotation_used": True,
            "rotation_attempt_count": 1,
            "fallback_used": False,
        }


def test_entity_world_state_analyzer_normalizes_typed_fields():
    analyzer = EntityWorldStateAnalyzer(
        llm_client=StubLLMClient(
            {
                "entities": [
                    {
                        "entity_name": "Feyre",
                        "entity_type": "character",
                        "narrative_role": "pov",
                        "baseline_description": "a gaunt huntress with a bow",
                        "baseline_source": "the huntress moved through the snow",
                        "typed_attributes": {
                            "appearance": ["gaunt huntress"],
                            "outfit": ["worn cloak", "worn cloak"],
                            "condition": ["hungry"],
                            "body_language": ["knees shaking"],
                            "possessions": ["bow", "ash arrow"],
                            "abilities": [],
                            "titles_or_roles": ["huntress"],
                            "affiliations": [],
                        },
                        "state_changes": [
                            {
                                "attribute": "condition",
                                "previous_state": "",
                                "new_state": "hungry",
                                "change_type": "physical_state",
                                "evidence": "her stomach was empty",
                            }
                        ],
                        "source_evidence": ["her stomach was empty", "worn cloak"],
                        "confidence": "high",
                    }
                ],
                "diagnostics": {"missing_baseline_entities": [], "unsupported_claims": []},
            }
        ),
        max_attempts=1,
    )

    result = analyzer.analyze({"book_index": 1, "chapter_index": 1, "scene_index": 1, "text": "Feyre hunts."})

    assert result["entities"][0]["typed_attributes"]["outfit"] == ["worn cloak"]
    assert result["entities"][0]["state_changes"][0]["attribute"] == "condition"
    assert result["rotation_used"] is True


def test_entity_world_state_analyzer_canonicalizes_character_aliases_from_provider_map():
    analyzer = EntityWorldStateAnalyzer(
        llm_client=StubLLMClient(
            {
                "entities": [
                    {
                        "entity_name": "Isaac Hale",
                        "entity_type": "character",
                        "narrative_role": "village suitor",
                        "baseline_description": "broad-shouldered young man with a familiar village ease",
                        "baseline_source": "Isaac Hale leaned against the wall",
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
                        "confidence": "high",
                    }
                ],
                "diagnostics": {"missing_baseline_entities": [], "unsupported_claims": []},
            }
        ),
        max_attempts=1,
    )

    result = analyzer.analyze(
        {"book_index": 1, "chapter_index": 2, "scene_index": 1, "text": "Isaac Hale leaned against the wall."},
        alias_map={"Isaac": ["Isaac", "Isaac Hale"]},
    )

    assert result["entities"][0]["entity_name"] == "Isaac"


def test_reconcile_scene_contract_backfills_event_entities_and_world_state_descriptions():
    scene = {
        "book_index": 1,
        "chapter_index": 1,
        "scene_index": 1,
        "canonical_characters": [{"name": "Feyre"}],
        "events": [
            {
                "event_id": "evt_1",
                "description": "Feyre raises the ash bow in the winter forest.",
                "characters": ["Feyre"],
                "entities_involved": ["ash bow", "winter forest"],
            }
        ],
        "entities_present": [],
        "entity_descriptions": [],
        "state_changes": [],
        "relationship_changes": [],
        "location": {"name": "winter forest", "entity_type": "location"},
        "entity_world_state": {
            "entities": [
                {
                    "entity_name": "ash bow",
                    "entity_type": "object",
                    "baseline_description": "a rough hunting bow",
                    "typed_attributes": {
                        "appearance": ["rough hunting bow"],
                        "materials": ["wood"],
                        "abilities": [],
                        "owner_or_holder": ["Feyre"],
                        "current_state": ["held at the ready"],
                        "symbolic_role": [],
                    },
                    "state_changes": [],
                    "source_evidence": ["ash bow"],
                }
            ]
        },
    }

    result = reconcile_scene_contract(scene)

    assert any(item["name"] == "ash bow" and item["entity_type"] == "object" for item in result["entities_present"])
    assert any(item["name"] == "winter forest" and item["entity_type"] == "location" for item in result["entities_present"])
    assert any(item["description"] == "a rough hunting bow" for item in result["entity_descriptions"])


def test_reconcile_scene_contract_prefers_specific_non_object_type_for_duplicate_entity_name():
    scene = {
        "events": [],
        "entities_present": [
            {"name": "white mare", "entity_type": "object"},
            {"name": "White mare", "entity_type": "creature"},
        ],
        "entity_descriptions": [],
        "state_changes": [],
        "relationship_changes": [],
        "canonical_characters": [],
        "location": {},
        "entity_world_state": {"entities": []},
    }

    result = reconcile_scene_contract(scene)

    assert [item for item in result["entities_present"] if item["name"].lower() == "white mare"] == [
        {"name": "White mare", "entity_type": "creature"}
    ]


def test_entity_registry_merges_cross_scene_duplicate_name_to_preferred_type():
    from entities.entity_registry_service import EntityRegistryService

    registry = EntityRegistryService().build(
        [
            {
                "book_index": 1,
                "chapter_index": 2,
                "scene_index": 1,
                "entities_present": [{"name": "Cottage interior", "entity_type": "object"}],
                "entity_descriptions": [
                    {
                        "entity_name": "Cottage interior",
                        "entity_type": "object",
                        "description": "tight space around the table",
                        "description_type": "appearance_note",
                    }
                ],
                "state_changes": [],
                "events": [],
                "relationship_changes": [],
            },
            {
                "book_index": 1,
                "chapter_index": 4,
                "scene_index": 1,
                "entities_present": [{"name": "Cottage interior", "entity_type": "location"}],
                "entity_descriptions": [
                    {
                        "entity_name": "Cottage interior",
                        "entity_type": "location",
                        "description": "small cramped cottage room",
                        "description_type": "appearance_note",
                    }
                ],
                "state_changes": [],
                "events": [],
                "relationship_changes": [],
            },
        ]
    )

    matching = [row for row in registry if row["name"].lower() == "cottage interior"]
    assert len(matching) == 1
    assert matching[0]["entity_type"] == "location"
