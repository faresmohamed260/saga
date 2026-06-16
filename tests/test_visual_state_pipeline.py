from analysis.scene_analysis_orchestrator import SceneAnalysisOrchestrator
from analysis.scene_analyzer import SceneAnalyzer
from analysis.entity_world_state_analyzer import EntityWorldStateAnalyzer
from analysis.visual_state_analyzer import VisualStateAnalyzer
from services.encoder_persistence_service import EncoderPersistenceService


class StubLLMClient:
    def __init__(self, response):
        self.response = response
        self.calls = 0
        self.mode = "gpt_oss"

    def generate_json(self, prompt: str, strict: bool = False, validator=None, **kwargs):
        self.calls += 1
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
            "rotation_used": False,
            "rotation_attempt_count": 0,
            "fallback_used": False,
        }


def test_visual_state_analyzer_normalizes_prompt_families():
    response = {
        "characters": [
            {
                "entity_name": "Feyre",
                "visual_role": "initial_character_description",
                "physical_description": "thin hands and worn hunting clothes",
                "outfit": "worn cloak and gloves",
                "visible_condition": "cold and hungry",
                "body_language": "trembling hands",
                "persistent_visual_profile": {
                    "gender_presentation": "young woman",
                    "species_or_race": "High Fae",
                    "role_or_archetype": "huntress",
                    "presence_description": "quiet, wary presence",
                    "height_description": "average height",
                    "body_type": "lean, underfed build",
                    "skin_description": "pale winter-chapped skin",
                    "hair_description": "long brown hair",
                    "eye_description": "gray-blue eyes",
                    "facial_structure": "fine-boned face",
                    "age_appearance": "late-teen appearance",
                    "expression": "neutral expression",
                    "clothing_description": "worn cloak and simple hunting clothes",
                    "footwear_description": "weathered boots",
                    "accessories_description": "gloves",
                    "distinguishing_marks": "",
                    "fantasy_features": "",
                    "equipment_or_signature_items": "bow and ash arrow",
                    "lore_terms": ["High Fae"],
                },
                "image_edit_prompt": "",
                "source_evidence": "worn cloak and trembling hands",
                "confidence": "high",
            }
        ],
        "objects": [
            {
                "entity_name": "ash arrow",
                "visual_description": "ash arrow ready on the bowstring",
                "state_or_ownership": "carried by Feyre",
                "image_prompt": "ash arrow on a rough bow",
                "source_evidence": "she drew the ash arrow",
                "confidence": "high",
            }
        ],
        "creatures": [],
        "locations": [
            {
                "entity_name": "winter forest",
                "physical_description": "snowy forest and bare trees",
                "atmosphere": "cold and tense",
                "state_change": "",
                "image_prompt": "snowy winter forest with bare trees",
                "source_evidence": "snow through the trees",
                "confidence": "high",
            }
        ],
        "scene_compositions": [
            {
                "beat_title": "Feyre draws the ash arrow",
                "entities": ["Feyre", "ash arrow"],
                "location": "winter forest",
                "scene_prompt": "Feyre aims an ash arrow in a snowy forest",
                "image_edit_prompt": "combine Feyre reference with bow and snowy forest",
                "source_evidence": "she drew the ash arrow",
                "confidence": "high",
            }
        ],
        "diagnostics": {"missing_visual_evidence": [], "rejected_visual_claims": []},
    }

    analyzer = VisualStateAnalyzer(llm_client=StubLLMClient(response), max_attempts=1)
    result = analyzer.analyze({"book_index": 1, "chapter_index": 1, "scene_index": 1, "text": "Feyre hunts."})

    assert result["characters"][0]["entity_name"] == "Feyre"
    assert "three-view layout" in result["characters"][0]["persistent_visual_prompt"]
    assert "fantasy humanoid" in result["characters"][0]["persistent_visual_prompt"]
    assert result["objects"][0]["entity_type"] == "object"
    assert result["locations"][0]["entity_type"] == "location"
    assert result["scene_compositions"][0]["scene_prompt"].startswith("Feyre aims")
    assert result["provider_family"] == "ollama"


def test_orchestrator_merges_visual_output_into_scene_contract_fields():
    scene_response = {
        "scene_summary": "Feyre hunts in the winter forest.",
        "canonical_characters": [{"name": "Feyre", "role": "hunter", "is_new_character": True, "names_used": ["Feyre"]}],
        "character_mentions": [],
        "events": [],
        "entities_present": [],
        "entity_descriptions": [],
        "state_changes": [],
        "relationship_changes": [],
        "location": {},
        "time_signals": [],
        "alias_updates": [],
        "rejected_identity_candidates": [],
    }
    visual_response = {
        "characters": [
            {
                "entity_name": "Feyre",
                "visual_role": "character_change",
                "physical_description": "",
                "outfit": "worn cloak and gloves",
                "visible_condition": "hands shaking from cold",
                "body_language": "",
                "image_prompt": "",
                "image_edit_prompt": "edit Feyre reference with worn cloak, gloves, and shaking cold hands",
                "source_evidence": "wearing gloves and a worn cloak",
                "confidence": "high",
            }
        ],
        "objects": [],
        "creatures": [],
        "locations": [],
        "scene_compositions": [],
        "diagnostics": {"missing_visual_evidence": [], "rejected_visual_claims": []},
    }
    orchestrator = SceneAnalysisOrchestrator(
        identity_pass_enabled=False,
        scene_analyzer=SceneAnalyzer(llm_client=StubLLMClient(scene_response), max_attempts=1),
        visual_analyzer=VisualStateAnalyzer(llm_client=StubLLMClient(visual_response), max_attempts=1),
        entity_world_state_analyzer=EntityWorldStateAnalyzer(
            llm_client=StubLLMClient(
                {
                    "entities": [
                        {
                            "entity_name": "Feyre",
                            "entity_type": "character",
                            "narrative_role": "pov_hunter",
                            "baseline_description": "a determined young huntress",
                            "baseline_source": "the huntress moves through the snow",
                            "typed_attributes": {
                                "appearance": ["lean from hunger"],
                                "outfit": ["worn cloak and gloves"],
                                "condition": ["hands shaking from cold"],
                                "body_language": [],
                                "possessions": ["bow", "ash arrow"],
                                "abilities": [],
                                "titles_or_roles": ["huntress"],
                                "affiliations": [],
                            },
                            "state_changes": [
                                {
                                    "attribute": "condition",
                                    "previous_state": "",
                                    "new_state": "hands shaking from cold",
                                    "change_type": "physical_state",
                                    "evidence": "hands shaking from cold",
                                }
                            ],
                            "source_evidence": ["wearing gloves and a worn cloak"],
                            "confidence": "high",
                        }
                    ],
                    "diagnostics": {"missing_baseline_entities": [], "unsupported_claims": []},
                }
            ),
            max_attempts=1,
        ),
    )

    result = orchestrator.analyze_scene({"book_index": 1, "chapter_index": 1, "scene_index": 1, "text": "Feyre hunts."})

    assert result["visual_analysis"]["characters"][0]["entity_name"] == "Feyre"
    assert any(item["name"] == "Feyre" for item in result["entities_present"])
    assert any(item["description"] == "worn cloak and gloves" for item in result["entity_descriptions"])
    assert any(item["attribute"] == "visual_state" for item in result["state_changes"])
    assert result["entity_world_state"]["entities"][0]["typed_attributes"]["possessions"] == ["bow", "ash arrow"]


def test_encoder_builds_native_visual_prompt_sets():
    service = EncoderPersistenceService()
    scenes = [
        {
            "book_index": 1,
            "chapter_index": 1,
            "scene_index": 1,
            "visual_analysis": {
                "characters": [
                    {
                        "entity_name": "Feyre",
                        "visual_role": "initial_character_description",
                        "persistent_visual_prompt": "studio photograph, three-view layout,\nfront view full body,\nfantasy humanoid huntress,\nlong brown hair,\ngray-blue eyes,",
                        "source_evidence": "worn clothes",
                        "confidence": "high",
                    },
                    {
                        "entity_name": "Feyre",
                        "visual_role": "character_change",
                        "image_edit_prompt": "add injury and torn sleeve",
                        "source_evidence": "torn sleeve",
                        "confidence": "medium",
                    },
                ],
                "objects": [{"entity_name": "ash arrow", "entity_type": "object", "image_prompt": "ash arrow", "confidence": "high"}],
                "creatures": [],
                "locations": [{"entity_name": "forest", "entity_type": "location", "image_prompt": "snowy forest", "confidence": "high"}],
                "scene_compositions": [{"beat_title": "Hunt", "scene_prompt": "Feyre aims in snowy forest", "confidence": "high"}],
                "diagnostics": {"missing_visual_evidence": ["doe"], "rejected_visual_claims": []},
            },
        }
    ]

    prompt_sets = service._build_visual_prompt_sets(scenes)

    assert len(prompt_sets["initial_characters"]) == 1
    assert len(prompt_sets["character_changes"]) == 1
    assert len(prompt_sets["objects_creatures"]) == 1
    assert len(prompt_sets["locations"]) == 1
    assert len(prompt_sets["scene_compositions"]) == 1
    assert prompt_sets["diagnostics"]["missing_visual_evidence"] == ["doe"]


def test_encoder_keeps_strongest_initial_character_prompt_per_name():
    service = EncoderPersistenceService()
    scenes = [
        {
            "book_index": 1,
            "chapter_index": 1,
            "scene_index": 1,
            "visual_analysis": {
                "characters": [
                    {
                        "entity_name": "Feyre",
                        "visual_role": "initial_character_description",
                        "persistent_visual_prompt": "studio photograph, three-view layout,\nfemale human hunter,",
                        "persistent_visual_profile": {"gender_presentation": "female", "species_or_race": "human"},
                        "source_evidence": "basic intro",
                        "confidence": "medium",
                    }
                ],
                "objects": [],
                "creatures": [],
                "locations": [],
                "scene_compositions": [],
                "diagnostics": {},
            },
        },
        {
            "book_index": 1,
            "chapter_index": 2,
            "scene_index": 1,
            "visual_analysis": {
                "characters": [
                    {
                        "entity_name": "Feyre",
                        "visual_role": "initial_character_description",
                        "persistent_visual_prompt": "studio photograph, three-view layout,\nfemale human hunter,\nslender build,\nlong brown hair,\ngray-blue eyes,\nworn cloak and gloves,",
                        "persistent_visual_profile": {
                            "gender_presentation": "female",
                            "species_or_race": "human",
                            "body_type": "slender build",
                            "hair_description": "long brown hair",
                            "eye_description": "gray-blue eyes",
                            "clothing_description": "worn cloak and gloves",
                        },
                        "source_evidence": "richer intro",
                        "confidence": "high",
                    }
                ],
                "objects": [],
                "creatures": [],
                "locations": [],
                "scene_compositions": [],
                "diagnostics": {},
            },
        },
    ]

    prompt_sets = service._build_visual_prompt_sets(scenes)

    assert len(prompt_sets["initial_characters"]) == 1
    assert "long brown hair" in prompt_sets["initial_characters"][0]["positive_prompt"]


def test_encoder_consolidates_sparse_initial_baseline_from_later_scene_evidence():
    service = EncoderPersistenceService()
    scenes = [
        {
            "book_index": 1,
            "chapter_index": 10,
            "scene_index": 1,
            "visual_analysis": {
                "characters": [
                    {
                        "entity_name": "Rhysand",
                        "visual_role": "initial_character_description",
                        "persistent_visual_profile": {
                            "gender_presentation": "male",
                            "species_or_race": "faerie",
                            "role_or_archetype": "high lord of Night Court",
                            "lore_terms": ["Night Court"],
                        },
                        "dynamic_visual_changes": [
                            {
                                "visible_condition_change": "violet eyes, pale skin, short dark hair",
                                "outfit_change": "obsidian tunic",
                                "confidence": "high",
                            }
                        ],
                        "source_evidence": "Rhysand appears in the cell.",
                        "confidence": "high",
                    }
                ],
                "objects": [],
                "creatures": [],
                "locations": [],
                "scene_compositions": [],
                "diagnostics": {},
            },
        },
        {
            "book_index": 1,
            "chapter_index": 11,
            "scene_index": 1,
            "visual_analysis": {
                "characters": [
                    {
                        "entity_name": "Rhysand",
                        "visual_role": "initial_character_description",
                        "persistent_visual_profile": {
                            "gender_presentation": "male",
                            "species_or_race": "faerie",
                            "role_or_archetype": "high lord of Night Court",
                            "hair_description": "short dark hair",
                            "eye_description": "violet eyes",
                        },
                        "source_evidence": "Rhysand's eyes and hair are clearer here.",
                        "confidence": "high",
                    }
                ],
                "objects": [],
                "creatures": [],
                "locations": [],
                "scene_compositions": [],
                "diagnostics": {},
            },
        },
    ]

    prompt_sets = service._build_visual_prompt_sets(scenes)

    assert len(prompt_sets["initial_characters"]) == 1
    prompt = prompt_sets["initial_characters"][0]["positive_prompt"]
    assert "violet eyes" in prompt
    assert "short dark hair" in prompt
    assert "obsidian tunic" in prompt


def test_encoder_backfills_one_baseline_prompt_per_registry_entity():
    service = EncoderPersistenceService()
    scenes = [
        {
            "book_index": 1,
            "chapter_index": 1,
            "scene_index": 1,
            "entities_present": [
                {"name": "Harry", "entity_type": "character"},
                {"name": "Harry Potter", "entity_type": "character"},
                {"name": "Hedwig", "entity_type": "creature"},
                {"name": "wand", "entity_type": "object"},
            ],
            "entity_descriptions": [
                {
                    "entity_name": "Harry Potter",
                    "entity_type": "character",
                    "description": "thin boy with messy dark hair, round glasses, and school robes",
                    "description_type": "stable_trait",
                },
                {
                    "entity_name": "Hedwig",
                    "entity_type": "creature",
                    "description": "snowy owl with bright amber eyes",
                    "description_type": "stable_trait",
                },
                {
                    "entity_name": "wand",
                    "entity_type": "object",
                    "description": "slender wooden wand with a polished surface",
                    "description_type": "appearance_note",
                },
            ],
            "state_changes": [],
            "events": [],
            "relationship_changes": [],
            "location": {
                "name": "Great Hall",
                "entity_type": "location",
                "description": "vast candlelit hall with floating candles and long house tables",
            },
            "visual_analysis": {
                "characters": [],
                "objects": [],
                "creatures": [],
                "locations": [],
                "scene_compositions": [],
                "diagnostics": {},
            },
        }
    ]

    prompt_sets = service._build_visual_prompt_sets(scenes)

    initial_names = [row["entity_name"] for row in prompt_sets["initial_characters"]]
    object_creature_names = [row["entity_name"] for row in prompt_sets["objects_creatures"]]
    location_names = [row["entity_name"] for row in prompt_sets["locations"]]

    assert initial_names == ["Harry Potter"]
    assert set(object_creature_names) == {"Hedwig", "wand"}
    assert location_names == ["Great Hall"]
    assert all(row["positive_prompt"] for row in prompt_sets["initial_characters"])
    assert all(row["positive_prompt"] for row in prompt_sets["objects_creatures"])
    assert all(row["positive_prompt"] for row in prompt_sets["locations"])
