from analysis.microtasks.scene_semantic_reviewer import SceneSemanticReviewer
from analysis.microtasks.task_registry import MicroTaskRegistry


class StubSemanticClient:
    def __init__(self, response):
        self.response = response

    def generate_json(self, prompt: str, validator=None):
        if validator and not validator(self.response):
            return {"error": "validation_failed"}
        return dict(self.response)


def test_scene_semantic_reviewer_filters_low_value_scene_outputs():
    scene_result = {
        "scene_summary": "Harry notices something strange on Privet Drive.",
        "events": [
            {"description": "Harry looks out the window", "characters": ["Harry Potter"], "type": "action"},
            {"description": "Owls sweep across the sky", "characters": [], "type": "discovery"},
        ],
        "state_changes": [
            {
                "entity_name": "Harry Potter",
                "entity_type": "character",
                "attribute": "knowledge",
                "previous_state": "",
                "new_state": "suspects something is wrong",
                "change_type": "knowledge",
                "evidence": "He starts to suspect the strange events matter.",
            },
            {
                "entity_name": "Window",
                "entity_type": "object",
                "attribute": "visibility",
                "previous_state": "closed",
                "new_state": "open",
                "change_type": "condition",
                "evidence": "The window is opened briefly.",
            },
        ],
        "relationship_changes": [
            {
                "source_entity": "Harry Potter",
                "target_entity": "Hermione Granger",
                "relationship": "friends",
                "change": "trust deepens",
                "evidence": "They rely on each other more after the scene.",
            },
            {
                "source_entity": "Harry Potter",
                "target_entity": "Ron Weasley",
                "relationship": "present together",
                "change": "co_present",
                "evidence": "They are simply in the same room.",
            },
        ],
    }

    responses = {
        "rank_event_significance": [
            {"keep": False, "importance": "low", "reason": "minor beat", "confidence": "high"},
            {"keep": True, "importance": "high", "reason": "canon-relevant sign", "confidence": "high"},
        ],
        "classify_state_change_importance": [
            {"keep": True, "importance": "high", "reason": "important knowledge shift", "confidence": "high"},
            {"keep": False, "importance": "low", "reason": "incidental object condition", "confidence": "high"},
        ],
        "classify_relationship_change": [
            {"keep": True, "relationship": "friends", "change": "trust deepens", "reason": "meaningful bond shift", "confidence": "high"},
            {"keep": False, "relationship": "friends", "change": "none", "reason": "mere co-presence", "confidence": "high"},
        ],
    }

    def client_factory(config):
        queued = responses[config.name]
        return StubSemanticClient(queued.pop(0))

    reviewer = SceneSemanticReviewer(task_registry=MicroTaskRegistry(), client_factory=client_factory)
    reviewed = reviewer.review(scene_result, "Harry sees unusual owls in the sky and begins to suspect something is wrong.")

    assert len(reviewed["events"]) == 1
    assert reviewed["events"][0]["description"] == "Owls sweep across the sky"
    assert len(reviewed["state_changes"]) == 1
    assert reviewed["state_changes"][0]["entity_name"] == "Harry Potter"
    assert len(reviewed["relationship_changes"]) == 1
    assert reviewed["relationship_changes"][0]["target_entity"] == "Hermione Granger"
    assert reviewed["semantic_post_review"]["events_before"] == 2
    assert reviewed["semantic_post_review"]["events_after"] == 1
