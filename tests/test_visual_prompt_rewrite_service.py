import json
from pathlib import Path

from services.visual_prompt_rewrite_service import VisualPromptRewriteService


class StubRewriteLLM:
    def __init__(self, response):
        self.response = response

    def generate_json(self, prompt, strict=False, validator=None, **kwargs):
        if validator and not validator(self.response):
            return {"error": "validation_failed"}
        return self.response

    def provider_name(self):
        return "stub"

    def resolved_model_name(self):
        return "stub-model"


def _write_contract(tmp_path: Path, payload: dict) -> Path:
    target = tmp_path / "contract.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def test_audit_visual_prompts_flags_missing_slots_and_placeholders(tmp_path: Path):
    contract = _write_contract(
        tmp_path,
        {
            "outputs": {
                "visual_prompt_sets": {
                    "initial_characters": [
                        {
                            "entity_name": "Tamlin",
                            "source_evidence": "golden-haired masked man",
                            "positive_prompt": "old prompt",
                            "details": {
                                "persistent_visual_profile": {
                                    "gender_presentation": "male",
                                    "species_or_race": "High Fae",
                                    "role_or_archetype": "warrior, nobility",
                                    "eye_description": "same as beast form (not specified)",
                                    "clothing_description": "plain dark green tunic",
                                    "footwear_description": "not specified",
                                    "world_aesthetic_cues": "Prythian faerie court, ornate masks",
                                }
                            },
                        }
                    ]
                }
            }
        },
    )
    service = VisualPromptRewriteService(llm_client=StubRewriteLLM({}))

    payload = service.audit_contract(contract)

    assert len(payload["entries"]) == 1
    entry = payload["entries"][0]
    assert "hair_description" in entry["missing_core_slots"]
    assert "eye_description" in entry["contaminated_fields"]
    assert "footwear_description" in entry["contaminated_fields"]


def test_rewrite_visual_prompts_uses_rewriter_output(tmp_path: Path):
    contract = _write_contract(
        tmp_path,
        {
            "outputs": {
                "visual_prompt_sets": {
                    "initial_characters": [
                        {
                            "entity_name": "Feyre",
                            "source_evidence": "slender, pale, golden-brown hair",
                            "positive_prompt": "old prompt",
                            "details": {
                                "persistent_visual_profile": {
                                    "gender_presentation": "female",
                                    "species_or_race": "human",
                                    "role_or_archetype": "hunter",
                                    "world_aesthetic_cues": "impoverished winter village",
                                }
                            },
                        }
                    ]
                }
            }
        },
    )
    response = {
        "entity_name": "Feyre",
        "entity_type": "character",
        "persistent_visual_profile": {
            "gender_presentation": "female",
            "species_or_race": "human",
            "role_or_archetype": "hunter",
            "model_safe_identity": "young woman",
            "world_aesthetic_cues": "impoverished winter fantasy village with rough wool and worn leather",
            "presence_description": "grim, determined",
            "height_description": "",
            "body_type": "lean, wiry",
            "skin_description": "pale, wind-chapped skin",
            "hair_description": "golden-brown hair",
            "eye_description": "blue-grey eyes",
            "facial_structure": "sharp cheekbones and a straight nose",
            "age_appearance": "young adult",
            "expression": "focused, guarded",
            "clothing_description": "threadbare layered winter hunting clothes in rough wool and worn leather",
            "footwear_description": "sturdy weathered winter boots",
            "accessories_description": "",
            "distinguishing_marks": "faint freckles",
            "fantasy_features": "",
            "equipment_or_signature_items": "hunting satchel",
            "lore_terms": ["village"],
        },
        "rewritten_prompt": "Create a photorealistic studio character-sheet photograph. Depict Feyre as a lean young huntress with golden-brown hair and blue-grey eyes.",
        "issues": [],
        "confidence": "high",
    }
    service = VisualPromptRewriteService(llm_client=StubRewriteLLM(response))

    payload = service.rewrite_contract_prompts(contract)

    assert payload["provider"] == "stub"
    assert payload["model"] == "stub-model"
    rewritten = payload["rewritten_prompts"][0]
    assert rewritten["entity_name"] == "Feyre"
    assert rewritten["persistent_visual_profile"]["hair_description"] == "golden-brown hair"
    assert "blue-grey eyes" in rewritten["rewritten_prompt"]


def test_audit_visual_prompts_routes_explicit_creatures_out_of_character_lane(tmp_path: Path):
    contract = _write_contract(
        tmp_path,
        {
            "outputs": {
                "visual_prompt_sets": {
                    "initial_characters": [
                        {
                            "entity_name": "Attor",
                            "source_evidence": "skeletal winged creature with talons",
                            "positive_prompt": "old prompt",
                            "details": {
                                "persistent_visual_profile": {
                                    "species_or_race": "faerie creature",
                                    "role_or_archetype": "brutal enforcer",
                                    "model_safe_identity": "monstrous fantasy creature",
                                    "fantasy_features": "wings, talons, forked tongue",
                                }
                            },
                        }
                    ]
                }
            }
        },
    )
    service = VisualPromptRewriteService(llm_client=StubRewriteLLM({}))

    payload = service.audit_contract(contract)

    assert payload["entries"][0]["entity_type"] == "creature"
