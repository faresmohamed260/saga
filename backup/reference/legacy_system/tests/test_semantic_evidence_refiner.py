from saga.agents.microtasks.semantic_evidence_refiner import SemanticEvidenceRefiner
from saga.agents.microtasks.task_registry import MicroTaskRegistry


class StubSemanticClient:
    def __init__(self, response):
        self.response = response

    def generate_json(self, prompt: str, validator=None):
        if validator and not validator(self.response):
            return {"error": "validation_failed"}
        return dict(self.response)


def test_semantic_evidence_refiner_filters_with_local_model_verdicts():
    bundle = {
        "mentions": [],
        "clusters": [],
        "candidate_characters": [
            {"name": "Harry Potter", "evidence_mentions": ["Harry Potter"], "source": "stub", "score": 0.9},
            {"name": "the man", "evidence_mentions": ["the man"], "source": "stub", "score": 0.8},
        ],
        "candidate_entities": [
            {"name": "Grimmauld Place", "entity_type": "location", "evidence_mentions": ["Grimmauld Place"], "source": "stub", "score": 0.8},
        ],
        "candidate_aliases": [],
        "metadata": {"provider": "stub"},
    }

    responses = {
        "normalize_candidate_surface_form": [
            {"decision": "keep", "normalized_name": "Harry Potter", "reason": "already clean", "confidence": "high"},
            {"decision": "reject", "normalized_name": "", "reason": "generic descriptor", "confidence": "high"},
        ],
        "classify_candidate_identity_type": [
            {"decision": "character", "entity_type": "character", "reason": "proper named person", "confidence": "high"},
        ],
        "validate_character_candidate": [
            {"keep": True, "reason": "important named person", "confidence": "high"},
        ],
        "validate_entity_candidate": [
            {"keep": True, "reason": "relevant", "confidence": "high"},
        ],
    }

    def client_factory(config):
        queued = responses[config.name]
        return StubSemanticClient(queued.pop(0))

    refiner = SemanticEvidenceRefiner(task_registry=MicroTaskRegistry(), client_factory=client_factory)
    refined = refiner.refine(bundle, "Harry Potter speaks to a man at Grimmauld Place.")

    assert [item["name"] for item in refined["candidate_characters"]] == ["Harry Potter"]
    assert refined["candidate_entities"][0]["name"] == "Grimmauld Place"
    assert refined["metadata"]["semantic_refinement"]["characters_rejected"] == 1


def test_semantic_evidence_refiner_can_retype_character_candidate_to_entity():
    bundle = {
        "mentions": [],
        "clusters": [],
        "candidate_characters": [
            {"name": "Privet Drive", "evidence_mentions": ["Privet Drive"], "source": "stub", "score": 0.8},
        ],
        "candidate_entities": [],
        "candidate_aliases": [],
        "metadata": {"provider": "stub"},
    }

    responses = {
        "normalize_candidate_surface_form": [
            {"decision": "keep", "normalized_name": "Privet Drive", "reason": "already clean", "confidence": "high"},
        ],
        "classify_candidate_identity_type": [
            {"decision": "entity", "entity_type": "location", "reason": "street/location name", "confidence": "high"},
        ],
        "validate_character_candidate": [],
        "validate_entity_candidate": [
            {"keep": True, "reason": "important location", "confidence": "high"},
        ],
    }

    def client_factory(config):
        queued = responses[config.name]
        return StubSemanticClient(queued.pop(0))

    refiner = SemanticEvidenceRefiner(task_registry=MicroTaskRegistry(), client_factory=client_factory)
    refined = refiner.refine(bundle, "Mr. Dursley left number four, Privet Drive early that morning.")

    assert refined["candidate_characters"] == []
    assert refined["candidate_entities"][0]["name"] == "Privet Drive"
    assert refined["candidate_entities"][0]["entity_type"] == "location"
    assert refined["metadata"]["semantic_refinement"]["characters_retyped_to_entities"] == 1


def test_semantic_evidence_refiner_can_normalize_or_reject_malformed_surface_forms():
    bundle = {
        "mentions": [],
        "clusters": [],
        "candidate_characters": [
            {"name": "When Mr", "evidence_mentions": ["When Mr"], "source": "stub", "score": 0.7},
        ],
        "candidate_entities": [],
        "candidate_aliases": [],
        "metadata": {"provider": "stub"},
    }

    responses = {
        "normalize_candidate_surface_form": [
            {"decision": "reject", "normalized_name": "", "reason": "parser fragment", "confidence": "high"},
        ],
        "classify_candidate_identity_type": [],
        "validate_character_candidate": [],
        "validate_entity_candidate": [],
    }

    def client_factory(config):
        queued = responses[config.name]
        if not queued:
            raise AssertionError(f"Unexpected task call: {config.name}")
        return StubSemanticClient(queued.pop(0))

    refiner = SemanticEvidenceRefiner(task_registry=MicroTaskRegistry(), client_factory=client_factory)
    refined = refiner.refine(bundle, "When Mr. Dursley left the house, he noticed a cat reading a map.")

    assert refined["candidate_characters"] == []
    assert refined["metadata"]["semantic_refinement"]["characters_rejected"] == 1


def test_semantic_evidence_refiner_can_retype_failed_character_validation_to_entity():
    bundle = {
        "mentions": [],
        "clusters": [],
        "candidate_characters": [
            {"name": "Night Court", "evidence_mentions": ["Night Court"], "source": "stub", "score": 0.8},
        ],
        "candidate_entities": [],
        "candidate_aliases": [],
        "metadata": {"provider": "stub"},
    }

    responses = {
        "normalize_candidate_surface_form": [
            {"decision": "keep", "normalized_name": "Night Court", "reason": "already clean", "confidence": "high"},
        ],
        "classify_candidate_identity_type": [
            {"decision": "character", "entity_type": "character", "reason": "role-like phrase", "confidence": "medium"},
        ],
        "validate_character_candidate": [],
        "validate_entity_candidate": [
            {"keep": True, "reason": "important faction/location", "confidence": "high"},
        ],
    }

    def client_factory(config):
        queued = responses[config.name]
        if not queued:
            raise AssertionError(f"Unexpected task call: {config.name}")
        return StubSemanticClient(queued.pop(0))

    refiner = SemanticEvidenceRefiner(task_registry=MicroTaskRegistry(), client_factory=client_factory)
    refined = refiner.refine(bundle, "I was High Lady of the Night Court, and the city still glittered beneath the mountain stars.")

    assert refined["candidate_characters"] == []
    assert refined["candidate_entities"][0]["name"] == "Night Court"
    assert refined["candidate_entities"][0]["entity_type"] == "location"
    assert refined["metadata"]["semantic_refinement"]["characters_retyped_to_entities"] == 1


def test_semantic_evidence_refiner_rejects_honorific_only_normalization():
    bundle = {
        "mentions": [],
        "clusters": [],
        "candidate_characters": [
            {"name": "When Mr", "evidence_mentions": ["When Mr"], "source": "stub", "score": 0.7},
        ],
        "candidate_entities": [],
        "candidate_aliases": [],
        "metadata": {"provider": "stub"},
    }

    responses = {
        "normalize_candidate_surface_form": [
            {"decision": "normalize", "normalized_name": "Mr", "reason": "leading fragment attached to name", "confidence": "medium"},
        ],
        "classify_candidate_identity_type": [
            {"decision": "reject", "entity_type": "character", "reason": "parser fragment", "confidence": "high"},
        ],
        "validate_character_candidate": [],
        "validate_entity_candidate": [],
    }

    def client_factory(config):
        queued = responses[config.name]
        if not queued:
            raise AssertionError(f"Unexpected task call: {config.name}")
        return StubSemanticClient(queued.pop(0))

    refiner = SemanticEvidenceRefiner(task_registry=MicroTaskRegistry(), client_factory=client_factory)
    refined = refiner.refine(bundle, "When Mr. Dursley left the house, he noticed a cat reading a map.")

    assert refined["candidate_characters"] == []
    assert refined["metadata"]["semantic_refinement"]["characters_rejected"] == 1
