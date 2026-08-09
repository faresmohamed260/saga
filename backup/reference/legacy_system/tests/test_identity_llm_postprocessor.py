from saga.domain.entities.identity_llm_postprocessor import IdentityLLMPostProcessor


class StubLLMClient:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def generate_json(self, prompt: str, strict: bool = False, validator=None):
        self.calls += 1
        if validator and not validator(self.response):
            return {"error": "validation_failed"}
        return self.response


class StubHintService:
    def __init__(self, hints):
        self.hints = hints
        self.calls = []

    def load_series_hints(self, series_id, candidate_names):
        self.calls.append((series_id, tuple(candidate_names)))
        return self.hints


def test_identity_llm_postprocessor_merges_promotes_and_rejects_candidates():
    identity_result = {
        "alias_map": {
            "Feyre Archeron": ["Feyre Archeron"],
            "Rhysand": ["Rhysand"],
        },
        "rejected_non_characters": [],
        "decisions": [],
        "alias_history": [],
    }
    detailed_result = {
        "temporary_person_candidates": {
            "tmp1": {"canonical_name": "Elain", "aliases": ["Elain Archeron"]},
        },
        "evaluation_summary": {
            "top_false_positive_canonicals": [
                {"canonical_name": "Death", "reason": "malformed_name", "character_score": 0.1, "non_character_score": 0.95},
            ],
            "temporary_candidates_diagnostics": [
                {"name": "Elain", "mention_count": 4, "max_person_likelihood": 0.91, "model_person_hits": 2, "honorific_backed": False},
            ],
            "top_remaining_likely_person_supporting_entities": [
                {"name": "Feyre", "mention_count": 5, "character_score": 0.88, "non_character_score": 0.1},
            ],
        },
    }
    response = {
        "decisions": [
            {"name": "Death", "action": "reject_non_character", "target_name": "", "reason": "Clearly not a person identity here."},
            {"name": "Elain", "action": "promote_canonical", "target_name": "", "reason": "Recurring real person left unresolved by deterministic pass."},
            {"name": "Feyre", "action": "merge_existing", "target_name": "Feyre Archeron", "reason": "Short-name alias of the existing canonical character."},
        ]
    }

    reviewed = IdentityLLMPostProcessor(llm_client=StubLLMClient(response)).review(identity_result, detailed_result)

    assert "Elain Archeron" in reviewed["alias_map"]
    assert "Elain" in reviewed["alias_map"]["Elain Archeron"]
    assert "Feyre" in reviewed["alias_map"]["Feyre Archeron"]
    assert "Death" in reviewed["rejected_non_characters"]
    assert len(reviewed["llm_post_review"]["applied_decisions"]) == 3


def test_identity_llm_postprocessor_finalizes_noisy_exported_aliases_even_without_explicit_merge():
    identity_result = {
        "alias_map": {
            "Feyre Archeron": ["Feyre Archeron", "Feyre", "Feyre's"],
            "Azriel Siphons": ["Azriel Siphons"],
        },
        "rejected_non_characters": [],
        "decisions": [],
        "alias_history": [
            {"canonical_name": "Feyre Archeron", "alias_name": "Feyre's", "scene_ref": {}},
        ],
    }
    detailed_result = {
        "temporary_person_candidates": {},
        "evaluation_summary": {
            "top_false_positive_canonicals": [],
            "temporary_candidates_diagnostics": [],
            "top_remaining_likely_person_supporting_entities": [],
        },
    }
    response = {
        "decisions": [
            {"name": "Feyre's", "action": "keep_unresolved", "target_name": "", "reason": "Will let deterministic cleanup normalize the possessive."},
            {"name": "Azriel Siphons", "action": "merge_existing", "target_name": "Feyre Archeron", "reason": "validation placeholder"},
        ]
    }
    response["decisions"][1] = {
        "name": "Azriel Siphons",
        "action": "promote_canonical",
        "target_name": "",
        "reason": "Allow deterministic cleanup to canonicalize this exported noisy canonical.",
    }

    reviewed = IdentityLLMPostProcessor(llm_client=StubLLMClient(response)).review(identity_result, detailed_result)

    assert "Feyre Archeron" in reviewed["alias_map"]
    assert "Feyre's" not in reviewed["alias_map"]["Feyre Archeron"]
    assert "Feyre" in reviewed["alias_map"]["Feyre Archeron"]
    assert "Azriel" in reviewed["alias_map"]
    assert "Azriel Siphons" not in reviewed["alias_map"]


def test_identity_llm_postprocessor_reviews_more_than_one_batch():
    identity_result = {
        "alias_map": {"Feyre Archeron": ["Feyre Archeron"]},
        "rejected_non_characters": [],
        "decisions": [],
        "alias_history": [],
    }
    detailed_result = {
        "temporary_person_candidates": {},
        "evaluation_summary": {
            "top_false_positive_canonicals": [
                {"canonical_name": f"Death Variant {chr(65 + idx)}", "reason": "malformed_name", "character_score": 0.1, "non_character_score": 0.95}
                for idx in range(14)
            ],
            "temporary_candidates_diagnostics": [],
            "top_remaining_likely_person_supporting_entities": [],
        },
    }
    response = {
        "decisions": [
            {"name": f"Death Variant {chr(65 + idx)}", "action": "reject_non_character", "target_name": "", "reason": "Not a person."}
            for idx in range(12)
        ]
    }
    second_response = {
        "decisions": [
            {"name": "Death Variant M", "action": "reject_non_character", "target_name": "", "reason": "Not a person."},
            {"name": "Death Variant N", "action": "reject_non_character", "target_name": "", "reason": "Not a person."},
        ]
    }

    class BatchStubLLMClient:
        def __init__(self, responses):
            self.responses = list(responses)
            self.calls = 0

        def generate_json(self, prompt: str, strict: bool = False, validator=None):
            self.calls += 1
            response = self.responses.pop(0)
            if validator and not validator(response):
                return {"error": "validation_failed"}
            return response

    stub = BatchStubLLMClient([response, second_response])
    reviewed = IdentityLLMPostProcessor(llm_client=stub).review(identity_result, detailed_result)

    assert stub.calls == 2
    assert reviewed["llm_post_review"]["candidates_reviewed"] == 14
    assert len(reviewed["rejected_non_characters"]) == 14


def test_identity_llm_postprocessor_uses_series_web_hints_for_non_character_cleanup():
    identity_result = {
        "alias_map": {
            "Harry Potter": ["Harry Potter"],
            "Hogwarts": ["Hogwarts"],
        },
        "rejected_non_characters": [],
        "decisions": [],
        "alias_history": [],
    }
    detailed_result = {
        "temporary_person_candidates": {},
        "evaluation_summary": {
            "top_false_positive_canonicals": [],
            "temporary_candidates_diagnostics": [],
            "top_remaining_likely_person_supporting_entities": [],
        },
    }
    response = {
        "decisions": [
            {"name": "Hogwarts", "action": "reject_non_character", "target_name": "", "reason": "Heuristic evidence says this is a school/location, not a person."},
        ]
    }
    hints = {
        "hogwarts": {
            "candidate_name": "Hogwarts",
            "matched_title": "Hogwarts School of Witchcraft and Wizardry",
            "entity_type": "location",
            "categories": "Locations, Schools",
            "confidence": "high",
        }
    }

    hint_service = StubHintService(hints)
    reviewed = IdentityLLMPostProcessor(
        llm_client=StubLLMClient(response),
        web_hint_service=hint_service,
        web_hints_enabled=True,
    ).review(identity_result, detailed_result, series_id="harry-potter")

    assert hint_service.calls
    assert "hogwarts" in reviewed["llm_post_review"]["heuristic_hints_used"]
    assert "Hogwarts" in reviewed["rejected_non_characters"]
    assert "Hogwarts" not in reviewed["alias_map"]


def test_identity_llm_postprocessor_preserves_anchor_entities_from_detailed_result():
    identity_result = {
        "alias_map": {
            "Without Rhys": ["Rhys", "Without Rhys"],
        },
        "rejected_non_characters": ["Mor"],
        "decisions": [],
        "alias_history": [],
    }
    detailed_result = {
        "canonical_characters": {
            "c1": {
                "canonical_name": "Rhys",
                "aliases": ["Rhysand"],
                "mention_count": 150,
                "max_person_likelihood": 0.95,
                "model_person_hits": 10,
                "honorific_backed": False,
            },
            "c2": {
                "canonical_name": "Mor",
                "aliases": [],
                "mention_count": 80,
                "max_person_likelihood": 0.93,
                "model_person_hits": 7,
                "honorific_backed": False,
            },
        },
        "temporary_person_candidates": {},
        "evaluation_summary": {
            "top_false_positive_canonicals": [],
            "temporary_candidates_diagnostics": [],
            "top_remaining_likely_person_supporting_entities": [],
        },
    }
    response = {"decisions": []}
    hint_service = StubHintService(
        {
            "mor": {
                "candidate_name": "Mor",
                "matched_title": "Mor",
                "entity_type": "location",
                "categories": "Locations",
                "confidence": "high",
            }
        }
    )

    reviewed = IdentityLLMPostProcessor(
        llm_client=StubLLMClient(response),
        web_hint_service=hint_service,
        web_hints_enabled=True,
    ).review(identity_result, detailed_result, series_id="acotar")

    assert "Rhys" in reviewed["alias_map"]["Rhysand"]
    assert "Rhysand" in reviewed["alias_map"]
    assert "Mor" in reviewed["alias_map"]
    assert "Mor" not in reviewed["rejected_non_characters"]
