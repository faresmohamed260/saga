from __future__ import annotations

import json
from pathlib import Path

import pytest

from query.narrative_context_service import NarrativeContextService
from query.target_character_state_service import TargetCharacterStateService


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _pipeline_identity_json(tmp_path: Path) -> Path:
    payload = {
        "provider": "booknlp_clean",
        "characters": [
            {"id": "char_feyre", "display_name": "Feyre", "aliases": ["Feyre", "Feyre Archeron"], "mention_count": 20, "quote_count": 3, "first_seen": 1, "risk_flags": []},
            {"id": "char_tamlin", "display_name": "Tamlin", "aliases": ["Tamlin", "Lord Tamlin"], "mention_count": 10, "quote_count": 1, "first_seen": 1, "risk_flags": []},
            {"id": "char_rhysand", "display_name": "Rhysand", "aliases": ["Rhysand", "Rhys"], "mention_count": 15, "quote_count": 2, "first_seen": 20, "risk_flags": []},
            {"id": "char_nesta", "display_name": "Nesta", "aliases": ["Nesta", "Nesta Archeron"], "mention_count": 12, "quote_count": 1, "first_seen": 20, "risk_flags": []},
            {"id": "char_elain", "display_name": "Elain", "aliases": ["Elain", "Elain Archeron"], "mention_count": 3, "quote_count": 0, "first_seen": 20, "risk_flags": []},
        ],
        "narrator": {"id": "narrator_0", "display_name": "[NARRATOR]", "possible_name": "Feyre", "mention_count": 100, "quote_count": 10},
        "reference_entities": [],
        "alias_index": {
            "feyre": "char_feyre",
            "feyre archeron": "char_feyre",
            "tamlin": "char_tamlin",
            "lord tamlin": "char_tamlin",
            "rhysand": "char_rhysand",
            "rhys": "char_rhysand",
            "nesta": "char_nesta",
            "nesta archeron": "char_nesta",
            "elain": "char_elain",
            "elain archeron": "char_elain",
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
    state_changes: list[dict] | None = None,
    relationship_changes: list[dict] | None = None,
    descriptions: list[dict] | None = None,
) -> dict:
    return {
        "book_index": book_index,
        "chapter_index": chapter_index,
        "scene_index": scene_index,
        "length": 100,
        "text": summary,
        "scene_summary": summary,
        "events": [
            {
                "event_id": f"ev_b{book_index}_c{chapter_index}_s{scene_index}",
                "description": summary,
                "characters": characters,
                "type": "interaction",
            }
        ],
        "entities_present": [{"name": name, "entity_type": "character"} for name in characters],
        "entity_descriptions": descriptions or [],
        "state_changes": state_changes or [],
        "relationship_changes": relationship_changes or [],
        "location": {"name": "Velaris", "entity_type": "location"},
        "time_signals": [],
        "canonical_characters": [
            {"name": name, "names_used": [name], "role": "", "is_new_character": False}
            for name in characters
        ],
        "character_mentions": [
            {
                "mention_text": name,
                "mention_type": "name",
                "canonical_name": name,
                "is_consequential_character": True,
            }
            for name in characters
        ],
        "alias_updates": [],
        "rejected_identity_candidates": [],
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
            "stable_character_states": [{"entity_name": "Feyre", "attributes": {"title": "Impossible Future Queen"}}],
            "story_index_summary": {"document_count": 0},
            "sequel_artifacts": {"context": {}, "blueprint": {}},
        },
    }


def _series_contract_paths(tmp_path: Path) -> tuple[list[str], Path]:
    identity_path = _pipeline_identity_json(tmp_path)
    book1 = _contract_payload(
        "A Court of Thorns and Roses",
        1,
        [
            _scene(
                book_index=1,
                chapter_index=12,
                scene_index=1,
                summary="Tamlin rescues Feyre and reveals he is High Lord.",
                characters=["Feyre", "Tamlin"],
                state_changes=[
                    {"entity_name": "Tamlin", "entity_type": "character", "attribute": "title", "previous_state": "", "new_state": "High Lord", "change_type": "reveal", "evidence": "Tamlin is High Lord."},
                ],
                relationship_changes=[
                    {"source_entity": "Feyre", "target_entity": "Tamlin", "relationship": "wary alliance", "change": "begins", "evidence": "Feyre begins trusting Tamlin."},
                ],
                descriptions=[
                    {"entity_name": "Tamlin", "entity_type": "character", "description": "High Lord of the Spring Court", "description_type": "stable_trait"},
                    {"entity_name": "Feyre", "entity_type": "character", "description": "human huntress", "description_type": "stable_trait"},
                ],
            )
        ],
    )
    book2 = _contract_payload(
        "A Court of Mist and Fury",
        2,
        [
            _scene(
                book_index=2,
                chapter_index=20,
                scene_index=1,
                summary="Rhys shelters Feyre in Velaris and she starts trusting him.",
                characters=["Feyre", "Rhys"],
                state_changes=[
                    {"entity_name": "Feyre", "entity_type": "character", "attribute": "allegiance", "previous_state": "", "new_state": "Night Court", "change_type": "shift", "evidence": "Feyre chooses Velaris."},
                ],
                relationship_changes=[
                    {"source_entity": "Feyre", "target_entity": "Rhys", "relationship": "alliance", "change": "trust deepens", "evidence": "Feyre starts trusting Rhys."},
                ],
                descriptions=[
                    {"entity_name": "Rhys", "entity_type": "character", "description": "High Lord of the Night Court", "description_type": "stable_trait"},
                    {"entity_name": "Elain", "entity_type": "character", "description": "gentle sister", "description_type": "stable_trait"},
                ],
            ),
            _scene(
                book_index=2,
                chapter_index=20,
                scene_index=2,
                summary="Elain appears briefly and worries about Feyre.",
                characters=["Elain", "Feyre"],
                relationship_changes=[
                    {"source_entity": "Elain", "target_entity": "Feyre", "relationship": "family", "change": "concern expressed", "evidence": "Elain worries about Feyre."},
                ],
            ),
        ],
    )
    book3 = _contract_payload(
        "A Court of Wings and Ruin",
        3,
        [
            _scene(
                book_index=3,
                chapter_index=55,
                scene_index=1,
                summary="Feyre and Rhysand accept their mating bond before battle.",
                characters=["Feyre", "Rhysand"],
                state_changes=[
                    {"entity_name": "Feyre", "entity_type": "character", "attribute": "mate_status", "previous_state": "", "new_state": "mated to Rhysand", "change_type": "reveal", "evidence": "Feyre accepts the bond."},
                ],
                relationship_changes=[
                    {"source_entity": "Feyre", "target_entity": "Rhysand", "relationship": "romance", "change": "bond accepted", "evidence": "They accept the mating bond."},
                ],
            )
        ],
    )
    book5 = _contract_payload(
        "A Court of Silver Flames",
        5,
        [
            _scene(
                book_index=5,
                chapter_index=78,
                scene_index=1,
                summary="Nesta completes the Blood Rite with Cassian's support.",
                characters=["Nesta", "Cassian"],
                state_changes=[
                    {"entity_name": "Nesta", "entity_type": "character", "attribute": "role", "previous_state": "", "new_state": "Valkyrie", "change_type": "achievement", "evidence": "Nesta survives the Blood Rite."},
                ],
                relationship_changes=[
                    {"source_entity": "Nesta", "target_entity": "Cassian", "relationship": "romance", "change": "committed partnership", "evidence": "Cassian supports Nesta through the Rite."},
                ],
            )
        ],
    )

    payloads = [book1, book2, book3, book5]
    paths: list[str] = []
    for index, payload in enumerate(payloads, start=1):
        path = tmp_path / f"contract_{index}.json"
        _write_json(path, payload)
        paths.append(str(path))
    return paths, identity_path


def _state_by_name(payload: dict, name: str) -> dict:
    for row in payload.get("character_states") or []:
        candidates = [row.get("display_name", "")] + list(row.get("aliases") or [])
        if any(str(candidate).lower() == name.lower() for candidate in candidates):
            return row
    raise AssertionError(f"State not found for {name}")


def test_target_point_ordering_filters_future_facts(tmp_path: Path) -> None:
    contract_paths, identity_path = _series_contract_paths(tmp_path)
    service = TargetCharacterStateService()

    payload = service.build_character_state_snapshot(
        contract_paths=contract_paths,
        target_point={"mode": "mid_canon", "book_index": 2, "chapter": 20},
        identity_json_path=identity_path,
    )

    feyre = _state_by_name(payload, "Feyre")
    assert all((row.get("book_index") or 0) <= 2 for row in feyre["evidence"])
    assert "mated to Rhysand" not in json.dumps(feyre, ensure_ascii=False)
    assert "Blood Rite" not in json.dumps(payload, ensure_ascii=False)


def test_post_series_after_book_five_includes_book_five_evidence(tmp_path: Path) -> None:
    contract_paths, identity_path = _series_contract_paths(tmp_path)
    service = TargetCharacterStateService()

    payload = service.build_character_state_snapshot(
        contract_paths=contract_paths,
        target_point={"mode": "post_series", "after_book_index": 5},
        identity_json_path=identity_path,
    )

    nesta = _state_by_name(payload, "Nesta")
    assert any((row.get("book_index") == 5 and "Blood Rite" in str(row.get("summary") or "")) for row in nesta["recent_key_events"])


def test_one_state_emitted_per_profile_and_low_evidence_profiles_are_low_confidence(tmp_path: Path) -> None:
    contract_paths, identity_path = _series_contract_paths(tmp_path)
    service = TargetCharacterStateService()

    payload = service.build_character_state_snapshot(
        contract_paths=contract_paths,
        target_point={"mode": "post_series", "after_book_index": 5},
        identity_json_path=identity_path,
    )

    names = {row["display_name"] for row in payload["character_states"]}
    assert {"Feyre", "Tamlin", "Rhysand", "Nesta", "Elain"} <= names
    elain = _state_by_name(payload, "Elain")
    assert elain["confidence"] == "low"


def test_relationship_changes_are_filtered_by_target_point(tmp_path: Path) -> None:
    contract_paths, identity_path = _series_contract_paths(tmp_path)
    service = TargetCharacterStateService()

    payload = service.build_character_state_snapshot(
        contract_paths=contract_paths,
        target_point={"mode": "mid_canon", "book_index": 2, "chapter": 20},
        identity_json_path=identity_path,
    )

    feyre = _state_by_name(payload, "Feyre")
    rhys_relationship = next(row for row in feyre["relationships"] if row["other_character"] == "Rhysand")
    assert rhys_relationship["relationship_type"] == "alliance"
    assert "bond accepted" not in rhys_relationship["latest_change"]


def test_decoder_context_can_consume_generated_target_states(tmp_path: Path) -> None:
    contract_paths, identity_path = _series_contract_paths(tmp_path)
    contract = json.loads(Path(contract_paths[0]).read_text(encoding="utf-8"))

    context = NarrativeContextService().build_from_contract(
        contract,
        prefer_exported=False,
        target_point={"mode": "mid_canon", "book_index": 2, "chapter": 20},
        identity_json_path=identity_path,
        contract_paths=contract_paths,
    )

    assert context["meta"]["target_point"]["mode"] == "mid_canon"
    assert context["character_states"]
    row = context["character_states"][0]
    assert {"name", "descriptions", "canon_state", "state_transitions", "aliases"} <= set(row.keys())


def test_existing_encoder_artifacts_remain_unchanged_and_stable_states_are_not_authoritative(tmp_path: Path) -> None:
    contract_paths, identity_path = _series_contract_paths(tmp_path)
    before = [json.loads(Path(path).read_text(encoding="utf-8")) for path in contract_paths]
    service = TargetCharacterStateService()

    payload = service.build_character_state_snapshot(
        contract_paths=contract_paths,
        target_point={"mode": "post_series", "after_book_index": 5},
        identity_json_path=identity_path,
    )

    after = [json.loads(Path(path).read_text(encoding="utf-8")) for path in contract_paths]
    assert before == after
    feyre = _state_by_name(payload, "Feyre")
    assert "Impossible Future Queen" not in json.dumps(feyre, ensure_ascii=False)


def test_missing_target_point_fails_clearly(tmp_path: Path) -> None:
    contract_paths, identity_path = _series_contract_paths(tmp_path)
    service = TargetCharacterStateService()

    with pytest.raises(ValueError, match="target_point.book_index and chapter are required for mid_canon"):
        service.build_character_state_snapshot(
            contract_paths=contract_paths,
            target_point={"mode": "mid_canon"},
            identity_json_path=identity_path,
        )
