from analysis.microtasks.identity_semantic_reviewer import IdentitySemanticReviewer
from analysis.microtasks.task_registry import MicroTaskRegistry


class StubSemanticClient:
    def __init__(self, response):
        self.response = response

    def generate_json(self, prompt: str, validator=None):
        if validator and not validator(self.response):
            return {"error": "validation_failed"}
        return dict(self.response)


def test_identity_semantic_reviewer_filters_weak_aliases_and_keeps_named_characters():
    scene_result = {
        "canonical_characters": [
            {"name": "Harry Potter", "role": "", "is_new_character": False, "names_used": ["Harry Potter"]},
            {"name": "the boy", "role": "", "is_new_character": True, "names_used": ["the boy"]},
        ],
        "character_mentions": [],
        "alias_updates": [
            {"alias": "the Chosen One", "canonical_name": "Harry Potter", "action": "map_alias", "reasoning": "clear title reference"},
            {"alias": "the boy", "canonical_name": "Harry Potter", "action": "map_alias", "reasoning": "weak generic descriptor"},
        ],
        "rejected_identity_candidates": [],
    }
    local_evidence = {
        "candidate_characters": [{"name": "Harry Potter", "evidence_mentions": ["Harry Potter"], "source": "stub", "score": 0.9}],
        "candidate_entities": [],
        "candidate_aliases": [],
        "mentions": [],
        "clusters": [],
        "metadata": {},
    }

    responses = {
        "validate_character_candidate": [
            {"keep": True, "reason": "clear named person", "confidence": "high"},
            {"keep": False, "reason": "weak generic descriptor", "confidence": "high"},
        ],
        "score_alias_merge": [
            {"keep": True, "reason": "well supported title mapping", "confidence": "high"},
            {"keep": False, "reason": "generic alias not specific enough", "confidence": "high"},
        ],
    }

    def client_factory(config):
        queued = responses[config.name]
        return StubSemanticClient(queued.pop(0))

    reviewer = IdentitySemanticReviewer(task_registry=MicroTaskRegistry(), client_factory=client_factory)
    reviewed = reviewer.review(scene_result, "Harry Potter is identified clearly in the scene.", local_evidence)

    assert [item["name"] for item in reviewed["canonical_characters"]] == ["Harry Potter"]
    assert [item["alias"] for item in reviewed["alias_updates"]] == ["the Chosen One"]
    assert "the boy" in reviewed["rejected_identity_candidates"]
    assert reviewed["identity_semantic_review"]["canonical_characters_before"] == 2
    assert reviewed["identity_semantic_review"]["alias_updates_after"] == 1


def test_identity_semantic_reviewer_can_remap_role_label_to_pov_anchor():
    scene_result = {
        "canonical_characters": [
            {"name": "High Lady", "role": "", "is_new_character": True, "names_used": ["High Lady"]},
        ],
        "character_mentions": [],
        "alias_updates": [],
        "rejected_identity_candidates": [],
    }
    local_evidence = {
        "candidate_characters": [{"name": "High Lady", "evidence_mentions": ["High Lady"], "source": "stub", "score": 0.9}],
        "candidate_entities": [],
        "candidate_aliases": [],
        "mentions": [],
        "clusters": [],
        "metadata": {},
    }

    responses = {
        "score_alias_merge": [
            {"keep": True, "reason": "role clearly refers to POV anchor", "confidence": "high"},
        ],
        "validate_character_candidate": [
            {"keep": True, "reason": "anchored POV identity", "confidence": "high"},
        ],
    }

    def client_factory(config):
        queued = responses[config.name]
        return StubSemanticClient(queued.pop(0))

    reviewer = IdentitySemanticReviewer(task_registry=MicroTaskRegistry(), client_factory=client_factory)
    reviewed = reviewer.review(
        scene_result,
        "As High Lady, Feyre looked over the Night Court with satisfaction.",
        local_evidence,
        pov_anchor="Feyre",
    )

    assert [item["name"] for item in reviewed["canonical_characters"]] == ["Feyre"]
    assert "High Lady" in reviewed["canonical_characters"][0]["names_used"]
    assert reviewed["identity_semantic_review"]["pov_anchor"] == "Feyre"
