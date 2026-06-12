from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from saga_tools import validate_generation_context


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _provider_identity_json(tmp_path: Path) -> Path:
    payload = {
        "provider": "booknlp_clean",
        "characters": [
            {"id": "char_feyre", "display_name": "Feyre", "aliases": ["Feyre", "Feyre Archeron"], "mention_count": 20, "quote_count": 2, "first_seen": 1, "risk_flags": []},
            {"id": "char_rhysand", "display_name": "Rhysand", "aliases": ["Rhysand", "Rhys"], "mention_count": 15, "quote_count": 2, "first_seen": 2, "risk_flags": []},
            {"id": "char_morrigan", "display_name": "Morrigan", "aliases": ["Morrigan", "Mor"], "mention_count": 8, "quote_count": 1, "first_seen": 2, "risk_flags": []},
            {"id": "char_azriel", "display_name": "Azriel", "aliases": ["Azriel", "Az"], "mention_count": 7, "quote_count": 1, "first_seen": 2, "risk_flags": []},
            {"id": "char_tamlin", "display_name": "Tamlin", "aliases": ["Tamlin", "Lord Tamlin"], "mention_count": 9, "quote_count": 1, "first_seen": 1, "risk_flags": []},
        ],
        "narrator": {"id": "narrator_0", "display_name": "[NARRATOR]", "possible_name": "Feyre", "mention_count": 100, "quote_count": 10},
        "reference_entities": [
            {"id": "ref_velaris", "display_name": "Velaris", "aliases": ["Velaris"], "category": "reference_entity", "mention_count": 10, "quote_count": 0, "first_seen": 2, "risk_flags": []}
        ],
        "alias_index": {
            "feyre": "char_feyre",
            "feyre archeron": "char_feyre",
            "rhysand": "char_rhysand",
            "rhys": "char_rhysand",
            "morrigan": "char_morrigan",
            "mor": "char_morrigan",
            "azriel": "char_azriel",
            "az": "char_azriel",
            "tamlin": "char_tamlin",
            "lord tamlin": "char_tamlin",
        },
        "suppressed_clusters": [],
        "diagnostics": {},
    }
    path = tmp_path / "identity.json"
    _write_json(path, payload)
    return path


def _scene(*, book_index: int, chapter_index: int, scene_index: int, summary: str, characters: list[str], relationship_changes: list[dict] | None = None, state_changes: list[dict] | None = None) -> dict:
    return {
        "book_index": book_index,
        "chapter_index": chapter_index,
        "scene_index": scene_index,
        "length": 100,
        "text": summary,
        "scene_summary": summary,
        "events": [{"event_id": f"ev_b{book_index}_c{chapter_index}_s{scene_index}", "description": summary, "characters": characters, "type": "interaction"}],
        "entities_present": [{"name": name, "entity_type": "character"} for name in characters] + [{"name": "Velaris", "entity_type": "location"}],
        "entity_descriptions": [],
        "state_changes": state_changes or [],
        "relationship_changes": relationship_changes or [],
        "location": {"name": "Velaris", "entity_type": "location"},
        "time_signals": [],
        "canonical_characters": [{"name": name, "names_used": [name], "role": "", "is_new_character": False} for name in characters],
        "character_mentions": [{"mention_text": name, "mention_type": "name", "canonical_name": name, "is_consequential_character": True} for name in characters],
        "alias_updates": [],
        "rejected_identity_candidates": [],
    }


def _contract(book_title: str, book_index: int, scenes: list[dict]) -> dict:
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
            "stable_character_states": [{"entity_name": "Feyre", "attributes": {"title": "Bad Stable State"}}],
            "story_index_summary": {"document_count": 0},
            "sequel_artifacts": {"context": {}, "blueprint": {}},
        },
    }


def _target_states_json(tmp_path: Path) -> Path:
    payload = {
        "target_point": {"mode": "post_series", "after_book_index": 5, "include_future_facts": False},
        "character_states": [
            {
                "character_id": "char_feyre",
                "display_name": "Feyre",
                "aliases": ["Feyre", "Feyre Archeron"],
                "state_scope": "after_book_5",
                "core_description": "High Lady of the Night Court",
                "traits": ["determined"],
                "mention_count": 20,
                "event_count": 10,
                "first_seen": {"book_index": 1, "chapter_index": 1, "scene_index": 1, "summary": "intro"},
                "current_roles": ["High Lady"],
                "relationships": [{"other_character": "Rhysand", "relationship_type": "romance", "trust_level": "high", "conflict_level": "low", "romantic_signal": "strong", "latest_change": "bond deepened", "evidence": "They remain devoted."}],
                "emotional_state": "protective",
                "physical_state": "",
                "powers_or_abilities": ["Daemati"],
                "affiliations": ["Night Court"],
                "known_goals": [],
                "open_conflicts": [],
                "recent_key_events": [{"book_index": 5, "chapter": 78, "scene_id": "b5_c78_s1", "event_id": "ev_5", "summary": "Nyx survives the birth crisis."}],
                "stable_facts": ["title=High Lady"],
                "evidence": [{"book_index": 5, "chapter": 78, "scene_id": "b5_c78_s1", "source": "character_profile", "summary": "Nyx survives the birth crisis."}],
                "confidence": "high",
                "risk_flags": [],
            },
            {
                "character_id": "char_rhysand",
                "display_name": "Rhysand",
                "aliases": ["Rhysand", "Rhys"],
                "state_scope": "after_book_5",
                "core_description": "High Lord of the Night Court",
                "traits": ["strategic"],
                "mention_count": 15,
                "event_count": 9,
                "first_seen": {"book_index": 2, "chapter_index": 1, "scene_index": 1, "summary": "intro"},
                "current_roles": ["High Lord"],
                "relationships": [{"other_character": "Feyre", "relationship_type": "romance", "trust_level": "high", "conflict_level": "low", "romantic_signal": "strong", "latest_change": "bond deepened", "evidence": "They remain devoted."}],
                "emotional_state": "guarded",
                "physical_state": "",
                "powers_or_abilities": ["Daemati"],
                "affiliations": ["Night Court"],
                "known_goals": [],
                "open_conflicts": [],
                "recent_key_events": [{"book_index": 5, "chapter": 78, "scene_id": "b5_c78_s1", "event_id": "ev_6", "summary": "Rhys thanks Nesta after the birth crisis."}],
                "stable_facts": ["title=High Lord"],
                "evidence": [{"book_index": 5, "chapter": 78, "scene_id": "b5_c78_s1", "source": "character_profile", "summary": "Rhys thanks Nesta after the birth crisis."}],
                "confidence": "high",
                "risk_flags": [],
            },
            {
                "character_id": "char_morrigan",
                "display_name": "Morrigan",
                "aliases": ["Morrigan", "Mor"],
                "state_scope": "after_book_5",
                "core_description": "court emissary",
                "traits": [],
                "mention_count": 8,
                "event_count": 3,
                "first_seen": {"book_index": 2, "chapter_index": 2, "scene_index": 1, "summary": "intro"},
                "current_roles": [],
                "relationships": [],
                "emotional_state": "",
                "physical_state": "",
                "powers_or_abilities": [],
                "affiliations": ["Night Court"],
                "known_goals": [],
                "open_conflicts": [],
                "recent_key_events": [],
                "stable_facts": [],
                "evidence": [],
                "confidence": "medium",
                "risk_flags": [],
            },
            {
                "character_id": "char_azriel",
                "display_name": "Azriel",
                "aliases": ["Azriel", "Az"],
                "state_scope": "after_book_5",
                "core_description": "spymaster",
                "traits": [],
                "mention_count": 7,
                "event_count": 2,
                "first_seen": {"book_index": 2, "chapter_index": 2, "scene_index": 1, "summary": "intro"},
                "current_roles": ["spymaster"],
                "relationships": [],
                "emotional_state": "",
                "physical_state": "",
                "powers_or_abilities": [],
                "affiliations": ["Night Court"],
                "known_goals": [],
                "open_conflicts": [],
                "recent_key_events": [],
                "stable_facts": [],
                "evidence": [],
                "confidence": "low",
                "risk_flags": ["sparse_profile"],
            },
        ],
        "reference_entities": [],
        "diagnostics": {"future_fact_filtering": True},
    }
    path = tmp_path / "target_states.json"
    _write_json(path, payload)
    return path


def test_validate_generation_context_builds_target_aware_non_neo4j_report(tmp_path: Path) -> None:
    identity_path = _provider_identity_json(tmp_path)
    target_states_path = _target_states_json(tmp_path)
    contract_paths = []
    for idx in range(1, 6):
        if idx == 1:
            scenes = [_scene(book_index=1, chapter_index=10, scene_index=1, summary="Tamlin protects Feyre in the Spring Court.", characters=["Tamlin", "Feyre"])]
        elif idx == 2:
            scenes = [_scene(book_index=2, chapter_index=20, scene_index=1, summary="Rhysand shelters Feyre in Velaris while Morrigan and Azriel assist.", characters=["Rhys", "Feyre", "Mor", "Az"], relationship_changes=[{"source_entity": "Feyre", "target_entity": "Rhys", "relationship": "alliance", "change": "trust deepens", "evidence": "They trust each other more."}], state_changes=[{"entity_name": "Rhys", "entity_type": "character", "attribute": "title", "previous_state": "", "new_state": "High Lord", "change_type": "known", "evidence": "Rhys is High Lord."}])]
        else:
            scenes = [_scene(book_index=idx, chapter_index=1, scene_index=1, summary=f"Book {idx} continues broader court tensions around Velaris and Starfall.", characters=["Feyre", "Rhysand"])]
        contract = _contract(f"Book {idx}", idx, scenes)
        path = tmp_path / f"contract_{idx}.json"
        _write_json(path, contract)
        contract_paths.append(str(path))

    out_json = tmp_path / "context_validation.json"
    out_md = tmp_path / "context_validation.md"
    args = SimpleNamespace(
        contract=contract_paths,
        out=str(out_json),
        report_md=str(out_md),
        prompt="Prepare canon context for ACOTAR 6 after ACOSF, focusing on Feyre, Rhysand, Nesta, Cassian, Azriel, Elain, Lucien, Gwyn, Emerie, Mor, Amren, Eris, Vassa, and Koschei.",
        identity_provider="booknlp_clean",
        identity_json=str(identity_path),
        series_identity_json="",
        target_states=str(target_states_path),
        target_mode="post_series",
        book_index=None,
        chapter=None,
        scene_id="",
        after_book_index=5,
        include_future_facts=False,
        blueprint_smoke_out="",
        blueprint_smoke_report_md="",
        chapters=None,
        canon_position="post_canon",
        new_plot="",
        primary_pov="",
        relationship_direction=[],
        preserve_event=[],
        continuity_anchor="",
        divergence_anchor="",
        anchor_after="",
        anchor_before="",
        model_mode="gpt_oss",
        ollama_model="gemma4:31b-cloud",
        planner_model_mode="",
        planner_model="",
        prose_model_mode="",
        prose_model="",
    )

    validate_generation_context(args)

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["target_context"]["meta"]["target_point"]["after_book_index"] == 5
    assert payload["target_context_payload"]["character_states"]
    assert payload["target_context_payload"]["target_character_state_snapshot"]["target_point"]["after_book_index"] == 5
    assert payload["target_context_payload"]["character_states"][0]["canon_state"]["state_scope"] == "after_book_5"
    assert any(row["focus_name"] == "Rhysand" and row["present"] for row in payload["focus_character_coverage"])
    assert any(row["focus_name"] == "Mor" and row["present"] for row in payload["focus_character_coverage"])
    assert any(row["focus_name"] == "Azriel" and row["present"] for row in payload["focus_character_coverage"])
    assert any(row["term"] == "Velaris" for row in payload["noise_diagnostics"])
    assert payload["target_context_payload"]["alias_index"]["rhys"] == "Rhysand"
    assert payload["target_context_payload"]["alias_index"]["mor"] == "Morrigan"
    assert payload["target_context_payload"]["alias_index"]["az"] == "Azriel"
    assert len(payload["contracts_used"]) == 5
    assert out_md.exists()
