from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from query.narrative_context_service import NarrativeContextService
from redesign_lab.identity.identity_provider import override_contract_with_identity_provider
from services.encoder_persistence_service import EncoderPersistenceService


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _provider_identity_json(tmp_path: Path) -> Path:
    payload = {
        "provider": "booknlp_clean",
        "characters": [
            {
                "id": "char_tamlin",
                "display_name": "Tamlin",
                "aliases": ["Tamlin", "Lord Tamlin"],
                "mention_count": 10,
                "quote_count": 2,
                "first_seen": 5,
                "source": "booknlp_small_clean",
                "risk_flags": [],
                "cluster_ids": [1],
            },
            {
                "id": "char_lucien",
                "display_name": "Lucien",
                "aliases": ["Lucien"],
                "mention_count": 8,
                "quote_count": 1,
                "first_seen": 8,
                "source": "booknlp_small_clean",
                "risk_flags": [],
                "cluster_ids": [2],
            },
            {
                "id": "char_feyre",
                "display_name": "Feyre",
                "aliases": ["Feyre"],
                "mention_count": 12,
                "quote_count": 2,
                "first_seen": 1,
                "source": "booknlp_small_clean",
                "risk_flags": [],
                "cluster_ids": [3],
            },
            {
                "id": "char_rhysand",
                "display_name": "Rhysand",
                "aliases": ["Rhysand", "Rhys"],
                "mention_count": 9,
                "quote_count": 1,
                "first_seen": 10,
                "source": "booknlp_small_clean",
                "risk_flags": [],
                "cluster_ids": [4],
            },
        ],
        "narrator": {
            "id": "narrator_0",
            "display_name": "[NARRATOR]",
            "possible_name": None,
            "confidence": "hypothesis",
            "mention_count": 100,
            "quote_count": 5,
            "first_seen": 1,
            "risk_flags": [],
        },
        "reference_entities": [
            {
                "id": "ref_suriel",
                "display_name": "the Suriel",
                "aliases": ["the Suriel", "Suriel"],
                "category": "reference_entity",
                "mention_count": 4,
                "quote_count": 0,
                "first_seen": 12,
                "risk_flags": [],
                "cluster_ids": [10],
            }
        ],
        "alias_index": {
            "tamlin": "char_tamlin",
            "lord tamlin": "char_tamlin",
            "lucien": "char_lucien",
            "feyre": "char_feyre",
            "rhysand": "char_rhysand",
            "rhys": "char_rhysand",
        },
        "suppressed_clusters": [],
        "diagnostics": {},
    }
    path = tmp_path / "booknlp_pipeline_identity.json"
    _write_json(path, payload)
    return path


def _contract_payload() -> dict:
    return {
        "contract_version": "1.0.0",
        "inputs": {"books": [{"title": "ACOTAR", "path": "acotar.epub"}]},
        "outputs": {
            "scene_analyses": [
                {
                    "book_index": 1,
                    "chapter_index": 1,
                    "scene_index": 1,
                    "length": 100,
                    "text": "Tamlin spoke while the stranger watched.",
                    "scene_summary": "Tamlin speaks.",
                    "events": [{"event_id": "ev_1", "description": "Tamlin spoke.", "characters": ["Tamlin", "Stranger"], "type": "interaction"}],
                    "entities_present": [
                        {"name": "Tamlin", "entity_type": "character"},
                        {"name": "Stranger", "entity_type": "character"},
                        {"name": "Spring Court", "entity_type": "location"},
                    ],
                    "entity_descriptions": [{"entity_name": "Tamlin", "entity_type": "character", "description": "High Lord", "description_type": "stable_trait"}],
                    "state_changes": [],
                    "relationship_changes": [{"source_entity": "Tamlin", "target_entity": "Stranger", "relationship_type": "other"}],
                    "location": {"name": "Spring Court"},
                    "time_signals": [],
                    "canonical_characters": [
                        {"name": "Tamlin", "names_used": ["Tamlin"], "role": "", "is_new_character": False},
                        {"name": "Stranger", "names_used": ["Stranger"], "role": "", "is_new_character": True},
                    ],
                    "character_mentions": [
                        {"mention_text": "Tamlin", "mention_type": "name", "canonical_name": "Tamlin", "is_consequential_character": True},
                        {"mention_text": "Stranger", "mention_type": "name", "canonical_name": "Stranger", "is_consequential_character": True},
                    ],
                    "alias_updates": [],
                    "rejected_identity_candidates": [],
                }
            ],
            "resolved_scene_analyses": [],
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


def test_booknlp_provider_override_rebuilds_contract_outputs(tmp_path: Path) -> None:
    identity_path = _provider_identity_json(tmp_path)
    args = SimpleNamespace(identity_provider="booknlp_clean", identity_json=str(identity_path))

    patched = override_contract_with_identity_provider(_contract_payload(), provider_mode=args.identity_provider, input_json=args.identity_json)
    outputs = patched["outputs"]

    assert outputs["identity_result"]["identity_provider"] == "booknlp_clean"
    assert "Tamlin" in outputs["identity_result"]["alias_map"]
    assert "Lord Tamlin" in outputs["identity_result"]["alias_map"]["Tamlin"]
    assert outputs["identity_result"]["narrator"]["display_name"] == "[NARRATOR]"
    assert outputs["identity_result"]["reference_entities"][0]["display_name"] == "the Suriel"
    assert outputs["resolved_scene_analyses"][0]["canonical_characters"][0]["name"] == "Tamlin"
    assert all(row["name"] != "Stranger" for row in outputs["resolved_scene_analyses"][0]["canonical_characters"])
    assert all(name != "Stranger" for name in outputs["resolved_scene_analyses"][0]["events"][0]["characters"])


def test_narrative_context_includes_provider_identity_metadata(tmp_path: Path) -> None:
    identity_path = _provider_identity_json(tmp_path)
    args = SimpleNamespace(identity_provider="booknlp_clean", identity_json=str(identity_path))
    patched = override_contract_with_identity_provider(_contract_payload(), provider_mode=args.identity_provider, input_json=args.identity_json)

    context = NarrativeContextService().build_from_contract(patched, prefer_exported=False)

    assert context["narrator"]["display_name"] == "[NARRATOR]"
    assert context["reference_entities"][0]["display_name"] == "the Suriel"
    assert context["alias_index"]["tamlin"] == "Tamlin"
    assert any(row["name"] == "Tamlin" for row in context["character_states"])


def test_missing_identity_file_fails_clearly() -> None:
    args = SimpleNamespace(identity_provider="booknlp_clean", identity_json="Z:/missing/booknlp_identity.json")
    with pytest.raises(FileNotFoundError):
        override_contract_with_identity_provider(_contract_payload(), provider_mode=args.identity_provider, input_json=args.identity_json)


def test_encoder_booknlp_provider_overrides_scene_inline_strategy(tmp_path: Path) -> None:
    identity_path = _provider_identity_json(tmp_path)
    service = EncoderPersistenceService(
        analysis_model="gpt_oss",
        identity_model="gpt_oss",
        identity_provider="booknlp_clean",
        identity_json_path=str(identity_path),
    )

    identity_result = service._run_identity_resolution(
        [{"path": r"D:\Books\Ebooks\Sarah J. Maas\A Court of Thorns and Roses\A Court of Thorns and Roses.epub", "title": "A Court of Thorns and Roses.epub", "book_index": 1}]
    )

    assert identity_result["identity_provider"] == "booknlp_clean"
    assert identity_result["alias_map"]["Tamlin"] == ["Tamlin", "Lord Tamlin"]
