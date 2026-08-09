from saga.services.wiki_character_reference_service import WikiCharacterReferenceService, flatten_reference_entries


class StubLLM:
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


def test_flatten_reference_entries_uses_display_name_lowercase():
    payload = {"entries": [{"display_name": "Feyre", "canon_notes": ["note"]}]}
    flattened = flatten_reference_entries(payload)
    assert flattened["feyre"]["canon_notes"] == ["note"]


def test_research_character_uses_fetched_wiki_content(monkeypatch):
    response = {
        "display_name": "Feyre",
        "entity_type": "character",
        "baseline_scope": "book 1 mortal baseline",
        "canon_notes": ["golden-brown hair", "blue-grey eyes"],
        "structured_traits": {
            "hair_description": "golden-brown hair",
            "eye_description": "blue-grey eyes",
            "skin_description": "pale freckled skin",
            "body_type": "slender",
            "facial_structure": "sharp cheekbones and straight nose",
            "clothing_description": "rough winter hunting layers",
            "footwear_description": "sturdy winter boots",
            "world_aesthetic_cues": "impoverished medieval fantasy village",
            "distinguishing_marks": "freckles",
            "fantasy_features": "",
        },
        "confidence": "high",
        "issues": [],
    }
    service = WikiCharacterReferenceService(llm_client=StubLLM(response))
    monkeypatch.setattr(
        service,
        "_resolve_page_title",
        lambda name: {
            "page_title": "Feyre_Archeron",
            "search_query": 'title:"Feyre"',
            "search_candidates": ["Feyre Archeron"],
            "resolved_via": "exact_search_match",
        },
    )
    monkeypatch.setattr(service, "_fetch_intro_excerpt", lambda title: "Feyre is a mortal huntress.")
    monkeypatch.setattr(service, "_fetch_appearance_excerpt", lambda title: "Feyre is slender with pale skin, golden-brown hair, and blue-grey eyes.")

    result = service.research_character(
        "Feyre",
        local_context={"persistent_visual_profile": {"species_or_race": "human"}},
        contract_title="A Court of Thorns and Roses.epub",
    )

    assert result["display_name"] == "Feyre"
    assert result["page_title"] == "Feyre_Archeron"
    assert result["structured_traits"]["hair_description"] == "golden-brown hair"
    assert "Feyre_Archeron" in result["page_url"]
    assert result["search_query"] == 'title:"Feyre"'
    assert result["resolved_via"] == "exact_search_match"
    assert "Book 1 mortal baseline" in result["target_scope"]


def test_resolve_page_title_prefers_direct_title_over_media_partial(monkeypatch):
    service = WikiCharacterReferenceService(llm_client=StubLLM({}))

    def fake_api_get(params):
        if params.get("titles") == "Harry Potter":
            return {"query": {"pages": {"123": {"title": "Harry Potter"}}}}
        if params.get("list") == "search":
            return {
                "query": {
                    "search": [
                        {"title": "Harry Potter and the Order of the Phoenix (film)"},
                    ]
                }
            }
        return {}

    monkeypatch.setattr(service, "_api_get", fake_api_get)
    resolved = service._resolve_page_title("Harry Potter")
    assert resolved["page_title"] == "Harry_Potter"
    assert resolved["resolved_via"] == "direct_title_match"
