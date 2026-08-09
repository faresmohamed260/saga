from saga.agents.local_entity_extractor import LocalEntityExtractor


def test_local_entity_extractor_finds_named_character_candidates():
    extractor = LocalEntityExtractor()
    result = extractor.extract(
        "Feyre met Tomas Mandray in the market. The huntress watched him carefully from the square. Lord Mandray spoke quietly."
    )

    candidate_names = {item["name"] for item in result["candidate_characters"]}
    assert "Tomas Mandray" in candidate_names
    assert any(item["text"] == "Tomas Mandray" for item in result["mentions"])
    assert "candidate_aliases" in result
    assert result["metadata"]["provider"] in {"spacy", "regex"}
    assert "ambiguities" in result["metadata"]
