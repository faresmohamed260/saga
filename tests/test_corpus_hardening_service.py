import json

from saga.services.corpus_hardening_service import CorpusHardeningService


class _StubLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def generate_json(self, prompt, strict=False, validator=None):
        self.prompts.append(prompt)
        response = self.responses.pop(0)
        if validator and not validator(response):
            return {"error": "validation_failed"}
        return response


def _sample_contract():
    return {
        "contract_version": "1.0.0",
        "inputs": {
            "books": [{"title": "A Court of Silver Flames.epub", "book_index": 5}],
            "series": {"series_id": "acotar", "series_title": "A Court of Thorns and Roses"},
        },
        "outputs": {
            "entity_registry": [
                {"name": "Feyre Archeron", "entity_type": "character", "descriptions": [], "state_changes": []},
                {"name": "Feyr e", "entity_type": "character", "descriptions": [], "state_changes": []},
                {"name": "Mor", "entity_type": "location", "descriptions": [], "state_changes": []},
                {"name": "Toward Nesta", "entity_type": "character", "descriptions": [], "state_changes": []},
                {"name": "Rhysand's House", "entity_type": "character", "descriptions": [], "state_changes": []},
            ],
            "identity_result": {"alias_map": {"Feyre Archeron": ["Feyre Archeron", "Feyr e"]}},
            "state_result": {"transitions": [{"entity_name": "Feyr e", "attribute": "role", "new_state": "High Lady"}]},
            "canon_snapshot": [{"entity_name": "Feyr e", "attributes": {"role": "High Lady"}}],
            "timeline": [{"event_id": "evt_1", "characters": ["Feyr e", "Mor"]}],
            "character_timelines": [{"character": "Feyr e", "events": [{"event_id": "evt_1"}]}],
            "resolved_scene_analyses": [
                {
                    "entities_present": [{"name": "Feyr e", "entity_type": "character"}, {"name": "Toward Nesta", "entity_type": "character"}],
                    "canonical_characters": ["Feyr e"],
                    "relationship_changes": [{"source_entity": "Feyr e", "target_entity": "Mor"}],
                }
            ],
            "scene_analyses": [],
            "causal_graph_result": {"graph": {"events": [{"id": "evt_1", "characters": ["Feyr e", "Mor"]}]}},
        },
    }


def test_corpus_hardening_service_repairs_alias_collapse_and_malformed_nodes():
    service = CorpusHardeningService()

    repaired, report = service.repair_contract(_sample_contract())

    names = [row["name"] for row in repaired["outputs"]["entity_registry"]]
    assert "Feyr e" not in names
    assert "Toward Nesta" not in names
    assert "Feyre Archeron" in names
    assert report["duplicate_identities_removed"] >= 1
    assert report["malformed_nodes_removed"] >= 1
    assert any(row["name"] == "Rhysand's House" and row["entity_type"] == "location" for row in repaired["outputs"]["entity_registry"])


def test_corpus_hardening_service_corrects_suspicious_character_types():
    service = CorpusHardeningService()

    repaired, _ = service.repair_contract(_sample_contract())
    by_name = {row["name"]: row for row in repaired["outputs"]["entity_registry"]}

    assert by_name["Mor"]["entity_type"] == "character"


def test_corpus_hardening_service_filters_non_character_event_participants():
    service = CorpusHardeningService()

    repaired, _ = service.repair_contract(_sample_contract())

    assert repaired["outputs"]["timeline"][0]["characters"] == ["Feyre Archeron", "Mor"]
    assert repaired["outputs"]["resolved_scene_analyses"][0]["canonical_characters"] == ["Feyre Archeron"]


def test_canonical_normalizer_strips_contextual_character_suffixes():
    service = CorpusHardeningService()

    assert service.normalizer.canonicalize_candidate_name("Rhysand for Solstice") == "Rhysand"
    assert service.normalizer.canonicalize_candidate_name("Nesta years ago") == "Nesta"
    assert service.normalizer.canonicalize_candidate_name("including Elain") == "Elain"
    assert service.normalizer.canonicalize_candidate_name("Azriel siphons") == "Azriel"
    assert service.normalizer.canonicalize_candidate_name("Harry saw Professors Flitwick") == "Harry"
    assert service.normalizer.canonicalize_candidate_name("Professor Albus Dumbledore") == "Albus Dumbledore"
    assert service.normalizer.canonicalize_candidate_name("Potions With Snape") == "Snape"
    assert service.normalizer.canonicalize_candidate_name("Death") == ""
    assert service.normalizer.canonicalize_candidate_name("Feyre's") == "Feyre"
    assert service.normalizer.canonicalize_candidate_name("The War") == ""
    assert service.normalizer.collapse_ocr_spacing("Feyre'stownhouse Bedroom") == "Feyre's townhouse Bedroom"
    assert service.normalizer.infer_entity_type("Feyre's Townhouse Bedroom", existing_type="character") == "location"


def test_corpus_hardening_service_cleans_raw_involved_character_rows():
    service = CorpusHardeningService()

    cleaned = service._clean_involved_character_rows([
        {"name": "Harry Seized Hedwig", "involved_events": 62},
        {"name": "Feyre's", "involved_events": 30},
        {"name": "The War", "involved_events": 28},
        {"name": "Azriel Siphons", "involved_events": 12},
    ])

    assert cleaned == [
        {"name": "Harry", "involved_events": 62},
        {"name": "Feyre", "involved_events": 30},
        {"name": "Azriel", "involved_events": 12},
    ]


def test_corpus_hardening_service_merges_short_involved_names_into_full_canonicals():
    service = CorpusHardeningService()

    cleaned = service._clean_involved_character_rows([
        {"name": "Harry Potter", "involved_events": 100},
        {"name": "Harry", "involved_events": 20},
        {"name": "Feyre Archeron", "involved_events": 50},
        {"name": "Feyre", "involved_events": 10},
    ])

    assert cleaned == [
        {"name": "Harry Potter", "involved_events": 120},
        {"name": "Feyre Archeron", "involved_events": 60},
    ]


def test_recover_missing_contracts_uses_source_books_when_contract_index_missing(tmp_path, monkeypatch):
    service = CorpusHardeningService()
    source_dir = tmp_path / "books"
    source_dir.mkdir()
    (source_dir / "1 Book One.epub").write_text("stub", encoding="utf-8")
    repair_dir = tmp_path / "repair"
    repair_dir.mkdir()
    contract_two = repair_dir / "02_2 Book Two.epub.contract.json"
    contract_two.write_text(json.dumps(_sample_contract()), encoding="utf-8")

    monkeypatch.setattr(
        service,
        "_recover_contract_from_source",
        lambda **kwargs: {
            "inputs": {"books": [{"title": kwargs["book_title"], "book_index": kwargs["book_index"]}]},
            "outputs": {"entity_registry": [], "identity_result": {"alias_map": {}}, "resolved_scene_analyses": []},
        },
    )

    recovered = service._recover_missing_contracts(
        series_id="harry-potter",
        repair_dir=repair_dir,
        repaired_files=[contract_two],
        source_dir=source_dir,
    )

    assert len(recovered) == 1
    assert "01_1 Book One.epub.contract.json" in recovered[0]


def test_corpus_hardening_service_uses_llm_for_remaining_ambiguous_merge_candidates():
    llm = _StubLLM([
        {
            "canonical_name": "Feyre Archeron",
            "merge_names": ["Feyre Archeron", "Feyre Cursebreaker"],
            "keep_separate": [],
            "rationale": "Title variant of the same character.",
        }
    ])
    service = CorpusHardeningService(llm_client=llm)
    merge_map, decisions = service._resolve_unresolved_candidates_with_llm(
        [{"normalized_name": "feyre", "options": ["Feyre Archeron", "Feyre Cursebreaker"], "selected": "Feyre Archeron"}],
        hints={},
        series_id="acotar",
        book_title="A Court of Silver Flames.epub",
    )

    assert merge_map == {"Feyre Cursebreaker": "Feyre Archeron"}
    assert len(decisions) == 1
    assert decisions[0]["canonical_name"] == "Feyre Archeron"
    assert llm.prompts


def test_corpus_hardening_service_builds_overlap_candidate_groups():
    service = CorpusHardeningService()

    groups = service._build_overlap_candidate_groups([
        {"name": "Azriel", "aliases": ["Az"]},
        {"name": "Az", "aliases": []},
        {"name": "Nesta Archeron", "aliases": ["Nesta"]},
        {"name": "Nesta", "aliases": []},
    ])

    option_sets = {tuple(group["options"]) for group in groups}
    assert ("Az", "Azriel") in option_sets
    assert ("Nesta", "Nesta Archeron") in option_sets
