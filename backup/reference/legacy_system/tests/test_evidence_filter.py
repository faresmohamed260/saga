from saga.agents.evidence_filter import score_and_filter_evidence


def test_evidence_filter_keeps_proper_names_and_drops_generic_aliases():
    bundle = {
        "mentions": [
            {"text": "Tomas Mandray", "label": "PERSON", "is_pronoun": False},
            {"text": "man", "label": "ROLE", "is_pronoun": False},
        ],
        "clusters": [],
        "candidate_characters": [
            {"name": "Tomas Mandray", "evidence_mentions": ["Tomas Mandray"], "source": "heuristic_name"},
            {"name": "man", "evidence_mentions": ["man"], "source": "local_role_phrase"},
        ],
        "candidate_entities": [],
        "candidate_aliases": [
            {"canonical_name": "Tomas Mandray", "alias": "the man"},
            {"canonical_name": "man", "alias": "man"},
        ],
        "metadata": {"provider": "stub"},
    }

    result = score_and_filter_evidence(bundle)

    assert any(item["name"] == "Tomas Mandray" for item in result["candidate_characters"])
    assert all(item["name"] != "man" for item in result["candidate_characters"])
    assert all(item["alias"] != "man" for item in result["candidate_aliases"])
    assert result["metadata"]["filtering"]["characters_kept"] >= 1
