from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from saga_tools import validate_encoder_artifacts


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
                "id": "char_feyre",
                "display_name": "Feyre",
                "aliases": ["Feyre"],
                "mention_count": 12,
                "quote_count": 2,
                "first_seen": 1,
                "source": "booknlp_small_clean",
                "risk_flags": [],
                "cluster_ids": [2],
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
            "feyre": "char_feyre",
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
        "configuration": {
            "identity_provider": "booknlp_clean",
        },
        "inputs": {"books": [{"title": "ACOTAR", "path": "acotar.epub"}]},
        "outputs": {
            "chapters": [{"book_index": 1, "chapter_index": 1, "chapter_title": "One", "content": "Tamlin spoke to Feyre."}],
            "scene_analyses": [
                {
                    "book_index": 1,
                    "chapter_index": 1,
                    "scene_index": 1,
                    "length": 100,
                    "text": "Tamlin spoke to Feyre in the Spring Court.",
                    "scene_summary": "Tamlin speaks to Feyre.",
                    "events": [{"event_id": "ev_1", "description": "Tamlin speaks to Feyre.", "characters": ["Tamlin", "Feyre"], "type": "interaction"}],
                    "entities_present": [
                        {"name": "Tamlin", "entity_type": "character"},
                        {"name": "Feyre", "entity_type": "character"},
                        {"name": "Spring Court", "entity_type": "location"},
                    ],
                    "entity_descriptions": [
                        {"entity_name": "Tamlin", "entity_type": "character", "description": "High Lord", "description_type": "stable_trait"}
                    ],
                    "state_changes": [
                        {
                            "entity_name": "Tamlin",
                            "entity_type": "character",
                            "attribute": "title",
                            "previous_state": "",
                            "new_state": "High Lord",
                            "change_type": "reveal",
                            "evidence": "Tamlin is identified as High Lord.",
                        }
                    ],
                    "relationship_changes": [
                        {
                            "source_entity": "Tamlin",
                            "target_entity": "Feyre",
                            "relationship": "tense alliance",
                            "change": "initiated",
                            "evidence": "They begin speaking warily.",
                        }
                    ],
                    "location": {"name": "Spring Court", "entity_type": "location"},
                    "time_signals": ["morning"],
                    "canonical_characters": [
                        {"name": "Tamlin", "names_used": ["Tamlin"], "role": "", "is_new_character": False},
                        {"name": "Feyre", "names_used": ["Feyre"], "role": "", "is_new_character": False},
                    ],
                    "character_mentions": [
                        {"mention_text": "Tamlin", "mention_type": "name", "canonical_name": "Tamlin", "is_consequential_character": True},
                        {"mention_text": "Feyre", "mention_type": "name", "canonical_name": "Feyre", "is_consequential_character": True},
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


def test_validate_encoder_artifacts_writes_reports(tmp_path: Path) -> None:
    contract_path = tmp_path / "contract.json"
    identity_path = _provider_identity_json(tmp_path)
    out_json = tmp_path / "validation.json"
    out_md = tmp_path / "validation.md"
    _write_json(contract_path, _contract_payload())

    args = SimpleNamespace(
        contract=str(contract_path),
        out=str(out_json),
        report_md=str(out_md),
        identity_provider="booknlp_clean",
        identity_json=str(identity_path),
        compare_contract="",
    )

    validate_encoder_artifacts(args)

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["validation_mode"] == "provider_override_rebuild"
    assert payload["artifact_snapshot"]["timeline"]["count"] >= 1
    assert payload["artifact_snapshot"]["character_profiles"]["count"] >= 1
    assert payload["identity_summary"]["provider_locked"] is True
    assert out_md.exists()
