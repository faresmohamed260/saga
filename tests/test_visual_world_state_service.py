from __future__ import annotations

import json
from pathlib import Path

from query.narrative_context_service import NarrativeContextService
from query.visual_world_state_service import VisualWorldStateService


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _pipeline_identity_json(tmp_path: Path) -> Path:
    payload = {
        "provider": "booknlp_clean",
        "characters": [
            {"id": "char_feyre", "display_name": "Feyre", "aliases": ["Feyre", "Feyre Archeron"], "mention_count": 20, "quote_count": 3, "first_seen": 1, "risk_flags": []},
            {"id": "char_rhysand", "display_name": "Rhysand", "aliases": ["Rhysand", "Rhys"], "mention_count": 16, "quote_count": 2, "first_seen": 10, "risk_flags": []},
            {"id": "char_nesta", "display_name": "Nesta", "aliases": ["Nesta", "Nesta Archeron"], "mention_count": 14, "quote_count": 2, "first_seen": 10, "risk_flags": []},
            {"id": "char_gwyn", "display_name": "Gwyn", "aliases": ["Gwyn"], "mention_count": 7, "quote_count": 1, "first_seen": 10, "risk_flags": []},
            {"id": "char_velaris", "display_name": "Velaris", "aliases": ["Velaris"], "mention_count": 2, "quote_count": 0, "first_seen": 1, "risk_flags": []},
        ],
        "narrator": {"id": "narrator_0", "display_name": "[NARRATOR]", "possible_name": "Feyre", "mention_count": 100, "quote_count": 10},
        "reference_entities": [{"id": "ref_suriel", "display_name": "the Suriel", "aliases": ["the Suriel", "Suriel"], "category": "reference_entity"}],
        "alias_index": {
            "feyre": "char_feyre",
            "feyre archeron": "char_feyre",
            "rhysand": "char_rhysand",
            "rhys": "char_rhysand",
            "nesta": "char_nesta",
            "nesta archeron": "char_nesta",
            "gwyn": "char_gwyn",
            "velaris": "char_velaris",
        },
        "suppressed_clusters": [],
        "diagnostics": {},
    }
    path = tmp_path / "pipeline_identity.json"
    _write_json(path, payload)
    return path


def _scene(
    *,
    book_index: int,
    chapter_index: int,
    scene_index: int,
    summary: str,
    characters: list[str],
    descriptions: list[dict] | None = None,
    state_changes: list[dict] | None = None,
    location: dict | None = None,
    visual_analysis: dict | None = None,
) -> dict:
    return {
        "book_index": book_index,
        "chapter_index": chapter_index,
        "scene_index": scene_index,
        "length": 100,
        "text": summary,
        "scene_summary": summary,
        "events": [{"event_id": f"ev_b{book_index}_c{chapter_index}_s{scene_index}", "description": summary, "characters": characters, "type": "interaction"}],
        "entities_present": [{"name": name, "entity_type": "character"} for name in characters],
        "entity_descriptions": descriptions or [],
        "state_changes": state_changes or [],
        "relationship_changes": [],
        "location": location or {"name": "Velaris", "entity_type": "location", "description": "city of starlight beside the Sidra"},
        "time_signals": [],
        "canonical_characters": [{"name": name, "names_used": [name], "role": "", "is_new_character": False} for name in characters],
        "character_mentions": [{"mention_text": name, "mention_type": "name", "canonical_name": name, "is_consequential_character": True} for name in characters],
        "alias_updates": [],
        "rejected_identity_candidates": [],
        "visual_analysis": visual_analysis or {"characters": [], "objects": [], "creatures": [], "locations": [], "scene_compositions": [], "diagnostics": {}},
    }


def _contract_payload(book_title: str, book_index: int, scenes: list[dict]) -> dict:
    return {
        "contract_version": "1.0.0",
        "inputs": {"books": [{"title": book_title, "path": f"{book_title}.epub", "book_index": book_index}]},
        "outputs": {
            "scene_analyses": scenes,
            "resolved_scene_analyses": scenes,
            "entity_registry": [],
            "state_result": {"transitions": [], "latest_state": []},
            "timeline": [],
            "identity_result": {"alias_map": {}, "rejected_non_characters": [], "decisions": [], "alias_history": []},
            "causal_graph_result": {"graph": {"events": [], "critical_path": [], "flexible_events": [], "causal_chains": [], "divergence_points": []}, "metrics": {}},
            "character_timelines": [],
            "character_profiles": [],
            "canon_snapshot": [],
            "event_ledger": [],
            "stable_character_states": [],
            "story_index_summary": {"document_count": 0},
            "sequel_artifacts": {"context": {}, "blueprint": {}},
        },
    }


def _contract_paths(tmp_path: Path) -> tuple[list[str], Path]:
    identity_path = _pipeline_identity_json(tmp_path)
    book2 = _contract_payload(
        "A Court of Mist and Fury",
        2,
        [
            _scene(
                book_index=2,
                chapter_index=20,
                scene_index=1,
                summary="Rhys shelters Feyre in the House of Wind after the wedding.",
                characters=["Feyre", "Rhys"],
                descriptions=[
                    {"entity_name": "Feyre", "entity_type": "character", "description": "white wedding gown", "description_type": "appearance_note"},
                    {"entity_name": "Feyre", "entity_type": "character", "description": "bleeding nose, bruised chin", "description_type": "temporary_condition"},
                    {"entity_name": "Rhys", "entity_type": "character", "description": "dark wings and star-dusted hand", "description_type": "appearance_note"},
                    {"entity_name": "Cauldron", "entity_type": "object", "description": "dark iron vessel on three thorny legs", "description_type": "appearance_note"},
                    {"entity_name": "House of Wind", "entity_type": "location", "description": "tall marble townhouse with wards and golden light", "description_type": "stable_trait"},
                ],
                state_changes=[
                    {"entity_name": "Feyre", "entity_type": "character", "attribute": "clothing", "previous_state": "wedding gown", "new_state": "nightclothes", "change_type": "possession", "evidence": "Feyre changes into nightclothes"},
                    {"entity_name": "Feyre", "entity_type": "character", "attribute": "physical_state", "previous_state": "", "new_state": "injured but standing", "change_type": "physical_state", "evidence": "Feyre is injured but standing"},
                    {"entity_name": "Cauldron", "entity_type": "object", "attribute": "status", "previous_state": "", "new_state": "active", "change_type": "condition", "evidence": "The Cauldron hums with power"},
                ],
                location={"name": "House of Wind", "entity_type": "location", "description": "marble townhouse with wards and a rooftop garden"},
                visual_analysis={
                    "characters": [
                        {
                            "entity_name": "Feyre",
                            "visual_role": "initial_character_description",
                            "persistent_visual_profile": {
                                "gender_presentation": "young woman",
                                "species_or_race": "High Fae",
                                "role_or_archetype": "huntress",
                                "presence_description": "wary but resilient presence",
                                "hair_description": "long brown hair",
                                "eye_description": "gray-blue eyes",
                                "clothing_description": "white wedding gown",
                            },
                            "persistent_visual_prompt": "studio photograph, three-view layout,\nfantasy humanoid huntress,\nlong brown hair,\ngray-blue eyes,\nwhite wedding gown,",
                            "source_evidence": "white wedding gown",
                            "confidence": "high",
                        }
                    ],
                    "objects": [],
                    "creatures": [],
                    "locations": [],
                    "scene_compositions": [],
                    "diagnostics": {},
                },
            )
        ],
    )
    book5 = _contract_payload(
        "A Court of Silver Flames",
        5,
        [
            _scene(
                book_index=5,
                chapter_index=68,
                scene_index=1,
                summary="Gwyn is wounded by an arrow while Emerie limps through the Blood Rite.",
                characters=["Nesta", "Gwyn", "Emerie"],
                descriptions=[
                    {"entity_name": "Gwyn", "entity_type": "character", "description": "coppery hair, teal eyes, priestess robes", "description_type": "appearance_note"},
                    {"entity_name": "Gwyn", "entity_type": "character", "description": "treated, bandaged", "description_type": "temporary_condition"},
                    {"entity_name": "Emerie", "entity_type": "character", "description": "dark-haired female with clipped wings", "description_type": "stable_trait"},
                    {"entity_name": "Emerie", "entity_type": "character", "description": "torn clothing and black eye", "description_type": "temporary_condition"},
                    {"entity_name": "sword", "entity_type": "object", "description": "glowing blade with black leather sheath", "description_type": "appearance_note"},
                ],
                state_changes=[
                    {"entity_name": "Gwyn", "entity_type": "character", "attribute": "condition", "previous_state": "wounded (arrow in thigh)", "new_state": "treated, bandaged", "change_type": "condition", "evidence": "Gwyn's arrow is removed and her leg bandaged"},
                    {"entity_name": "Emerie", "entity_type": "character", "attribute": "physical_state", "previous_state": "", "new_state": "injured (twisted ankle)", "change_type": "condition", "evidence": "Emerie limps after twisting her ankle"},
                    {"entity_name": "sword", "entity_type": "object", "attribute": "status", "previous_state": "", "new_state": "magical", "change_type": "condition", "evidence": "The sword glows with crackling magic"},
                ],
                location={"name": "Blood Rite wilderness", "entity_type": "location", "description": "mountain forest near Ramiel with cliffs, snow, and cave shelter"},
            )
        ],
    )
    payloads = [book2, book5]
    paths: list[str] = []
    for idx, payload in enumerate(payloads, start=1):
        path = tmp_path / f"contract_{idx}.json"
        _write_json(path, payload)
        paths.append(str(path))
    return paths, identity_path


def test_visual_state_service_filters_evidence_by_target_point(tmp_path: Path) -> None:
    contract_paths, identity_path = _contract_paths(tmp_path)
    payload = VisualWorldStateService().build_visual_world_state(
        contract_paths=contract_paths,
        target_point={"mode": "mid_canon", "book_index": 2, "chapter": 20},
        identity_json_path=identity_path,
    )
    names = {row["display_name"] for row in payload["character_visual_states"]}
    assert "Gwyn" in names
    gwyn = next(row for row in payload["character_visual_states"] if row["display_name"] == "Gwyn")
    assert gwyn["confidence"] == "low"
    feyre = next(row for row in payload["character_visual_states"] if row["display_name"] == "Feyre")
    assert "nightclothes" in json.dumps(feyre, ensure_ascii=False)
    assert "treated, bandaged" not in json.dumps(payload, ensure_ascii=False)


def test_future_visual_facts_are_excluded_for_mid_canon(tmp_path: Path) -> None:
    contract_paths, identity_path = _contract_paths(tmp_path)
    payload = VisualWorldStateService().build_visual_world_state(
        contract_paths=contract_paths,
        target_point={"mode": "mid_canon", "book_index": 2, "chapter": 20},
        identity_json_path=identity_path,
    )
    blob = json.dumps(payload, ensure_ascii=False)
    assert "Blood Rite wilderness" not in blob
    assert "treated, bandaged" not in blob


def test_character_entity_and_location_states_are_separated(tmp_path: Path) -> None:
    contract_paths, identity_path = _contract_paths(tmp_path)
    payload = VisualWorldStateService().build_visual_world_state(
        contract_paths=contract_paths,
        target_point={"mode": "post_series", "after_book_index": 5},
        identity_json_path=identity_path,
    )
    assert any(row["display_name"] == "Feyre" for row in payload["character_visual_states"])
    assert any(row["display_name"] == "Cauldron" for row in payload["entity_visual_states"])
    assert any("House of Wind" in row["display_name"] for row in payload["location_visual_states"])


def test_evidence_provenance_is_preserved(tmp_path: Path) -> None:
    contract_paths, identity_path = _contract_paths(tmp_path)
    payload = VisualWorldStateService().build_visual_world_state(
        contract_paths=contract_paths,
        target_point={"mode": "post_series", "after_book_index": 5},
        identity_json_path=identity_path,
    )
    feyre = next(row for row in payload["character_visual_states"] if row["display_name"] == "Feyre")
    assert feyre["evidence"]
    first = feyre["evidence"][0]
    assert {"book_index", "chapter", "scene_id", "source", "text"} <= set(first.keys())


def test_visual_world_state_preserves_persistent_character_prompt(tmp_path: Path) -> None:
    contract_paths, identity_path = _contract_paths(tmp_path)
    payload = VisualWorldStateService().build_visual_world_state(
        contract_paths=contract_paths,
        target_point={"mode": "post_series", "after_book_index": 5},
        identity_json_path=identity_path,
    )
    feyre = next(row for row in payload["character_visual_states"] if row["display_name"] == "Feyre")
    assert "three-view layout" in feyre["persistent_visual_prompt"]
    assert feyre["persistent_visual_profile"]["hair_description"] == "long brown hair"


def test_sparse_visual_evidence_produces_low_confidence_not_omission(tmp_path: Path) -> None:
    contract_paths, identity_path = _contract_paths(tmp_path)
    payload = VisualWorldStateService().build_visual_world_state(
        contract_paths=contract_paths,
        target_point={"mode": "mid_canon", "book_index": 2, "chapter": 20},
        identity_json_path=identity_path,
    )
    gwyn = next(row for row in payload["character_visual_states"] if row["display_name"] == "Gwyn")
    assert gwyn["confidence"] == "low"
    assert "sparse_visual_evidence" in gwyn["risk_flags"]


def test_noisy_entries_are_flagged_and_not_promoted_as_characters(tmp_path: Path) -> None:
    contract_paths, identity_path = _contract_paths(tmp_path)
    payload = VisualWorldStateService().build_visual_world_state(
        contract_paths=contract_paths,
        target_point={"mode": "post_series", "after_book_index": 5},
        identity_json_path=identity_path,
    )
    assert all(row["display_name"] != "Velaris" for row in payload["character_visual_states"])
    flagged = payload["diagnostics"]["noisy_entries_flagged"]
    assert any(row["entry"] == "Velaris" for row in flagged)


def test_visual_state_can_be_added_to_retrieval_context(tmp_path: Path) -> None:
    contract_paths, identity_path = _contract_paths(tmp_path)
    contracts = [json.loads(Path(path).read_text(encoding="utf-8")) for path in contract_paths]
    context = NarrativeContextService().build_from_contracts(
        contracts,
        target_point={"mode": "post_series", "after_book_index": 5},
        identity_json_path=identity_path,
        contract_paths=contract_paths,
        include_visual_world_state=True,
    )
    assert "visual_world_state" in context
    assert "character_visual_states" in context
    assert "entity_visual_states" in context
    assert "location_visual_states" in context


def test_visual_enriched_contract_keeps_original_artifacts_unchanged(tmp_path: Path) -> None:
    contract_paths, identity_path = _contract_paths(tmp_path)
    source_contract = json.loads(Path(contract_paths[0]).read_text(encoding="utf-8"))
    visual = VisualWorldStateService().build_visual_world_state(
        contract_paths=[contract_paths[0]],
        target_point={"mode": "mid_canon", "book_index": 2, "chapter": 20},
        identity_json_path=identity_path,
    )
    enriched = json.loads(json.dumps(source_contract))
    enriched["outputs"]["visual_world_state"] = visual
    assert source_contract["outputs"]["scene_analyses"] == enriched["outputs"]["scene_analyses"]
    assert source_contract["outputs"]["timeline"] == enriched["outputs"]["timeline"]
    assert source_contract["outputs"]["entity_registry"] == enriched["outputs"]["entity_registry"]
    assert "visual_world_state" in enriched["outputs"]


def test_visual_world_state_report_is_generated(tmp_path: Path) -> None:
    from saga_tools import _write_visual_world_state_report

    contract_paths, identity_path = _contract_paths(tmp_path)
    payload = VisualWorldStateService().build_visual_world_state(
        contract_paths=contract_paths,
        target_point={"mode": "post_series", "after_book_index": 5},
        identity_json_path=identity_path,
    )
    report_path = tmp_path / "visual_report.md"
    _write_visual_world_state_report(report_path, payload)
    assert report_path.exists()
    assert "Visual World State Report" in report_path.read_text(encoding="utf-8")
