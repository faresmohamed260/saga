from saga.retrieval.story_query_service import StoryQueryService
from saga.retrieval.story_index_service import StoryIndexService
from saga.domain.timeline.character_identity_service import CharacterIdentityService


class StubLLMClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def generate_json(self, prompt: str, strict: bool = False, validator=None):
        self.calls += 1
        response = self.responses[min(self.calls - 1, len(self.responses) - 1)]
        if validator and isinstance(response, dict) and "error" not in response and not validator(response):
            return {"error": "validation_failed", "raw_output": response}
        return response


def build_character_timelines():
    return [
        {
            "character": "Feyre",
            "events": [
                {"time_index": 1, "book_index": 1, "chapter_index": 1, "scene_index": 1, "event_id": "evt_1", "summary": "Feyre hunts in the forest."},
                {"time_index": 2, "book_index": 1, "chapter_index": 1, "scene_index": 2, "event_id": "evt_2", "summary": "Feyre kills the wolf."},
                {"time_index": 5, "book_index": 1, "chapter_index": 2, "scene_index": 1, "event_id": "evt_1", "summary": "Feyre goes under the mountain to save Tamlin."},
            ],
        },
        {
            "character": "the huntress",
            "events": [
                {"time_index": 4, "book_index": 1, "chapter_index": 2, "scene_index": 1, "event_id": "evt_0", "summary": "The huntress goes under the mountain."},
            ],
        },
    ]


def build_scene_analyses():
    return [
        {
            "book_index": 1,
            "chapter_index": 2,
            "scene_index": 1,
            "text": "Feyre goes under the mountain to save Tamlin. The huntress keeps moving deeper into the mountain.",
        }
    ]


def test_incremental_identity_resolution():
    stub = StubLLMClient([
        {"is_character": True, "confidence": 0.9, "reasoning": "The huntress is a consequential role-based saga.identity."},
        {"same_character": True, "confidence": 0.92, "reasoning": "The huntress matches Feyre's established actions.", "canonical_name": "Feyre"},
    ])
    service = CharacterIdentityService(llm_client=stub)
    result = service.build(build_character_timelines(), build_scene_analyses())

    assert result["alias_map"]["Feyre"] == ["Feyre", "the huntress"]
    assert result["alias_history"][0]["resolved_at_time_index"] == 4
    assert result["alias_history"][0]["canonical_name"] == "Feyre"


def test_story_query_service():
    timeline = [
        {"time_index": 5, "book_index": 1, "chapter_index": 2, "scene_index": 1, "event_id": "evt_1", "summary": "Feyre goes under the mountain to save Tamlin.", "characters": ["Feyre", "Tamlin"]},
    ]
    state_result = {
        "transitions": [
            {"state_index": 1, "book_index": 1, "chapter_index": 2, "scene_index": 1, "entity_name": "Feyre", "entity_type": "character", "attribute": "location", "new_state": "Under the Mountain", "evidence": "Feyre goes under the mountain to save Tamlin."},
        ]
    }
    identity_result = {
        "alias_map": {
            "Feyre": ["Feyre", "the huntress"]
        },
        "decisions": [
            {"decision_type": "mapping", "character": "the huntress", "canonical_name": "Feyre", "same_character": True, "confidence": 0.92, "reasoning": "The huntress matches Feyre.", "resolved_at_time_index": 4}
        ]
    }
    entity_registry = [
        {
            "name": "Feyre",
            "entity_type": "character",
            "mention_count": 4,
            "first_seen": {"book_index": 1, "chapter_index": 1, "scene_index": 1},
            "descriptions": [{"description": "a huntress", "description_type": "stable_trait"}],
            "state_changes": [],
        }
    ]
    canon_snapshot = [
        {
            "entity_name": "Feyre",
            "entity_type": "character",
            "attributes": {"location": "Under the Mountain"},
        }
    ]
    scene_analyses = [
        {"book_index": 1, "chapter_index": 2, "scene_index": 1, "scene_summary": "Feyre goes under the mountain to save Tamlin.", "events": [], "text": "Feyre goes under the mountain to save Tamlin."}
    ]
    character_timelines = build_character_timelines()

    index = StoryIndexService()
    result = index.build(
        scene_analyses=scene_analyses,
        timeline=timeline,
        character_timelines=character_timelines,
        entity_registry=entity_registry,
        canon_snapshot=canon_snapshot,
        state_result=state_result,
        identity_result=identity_result,
    )

    assert result["document_count"] >= 7

    query_service = StoryQueryService()
    matches = query_service.search(index, "Feyre was going under the mountain to save Tamlin", min_similarity=0.05, max_results=6)
    assert matches
    assert any(item["item_type"] in {"scene", "timeline_event", "state_transition", "entity_registry", "canon_snapshot", "alias_map"} for item in matches)
