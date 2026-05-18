from query.narrative_context_service import NarrativeContextService

from tests.test_core_artifact_bundle import build_sample_artifact_bundle


def _sample_contract():
    bundle = build_sample_artifact_bundle()
    outputs = dict(bundle["raw_outputs"])
    outputs["scene_analyses"] = list(outputs["resolved_scene_analyses"])
    outputs["canon_snapshot"] = [
        {
            "entity_name": "Harry Potter",
            "attributes": {"grief": "intensified", "trust": "more open with Hermione"},
        }
    ]
    outputs["causal_graph_result"] = {
        "graph": {
            "events": [
                {
                    "id": "t_1",
                    "description": "Harry and Hermione regroup after the battle.",
                    "story_impact": 8,
                    "time_index": 1,
                    "book_index": 1,
                    "chapter_index": 1,
                    "scene_index": 1,
                    "characters": ["Harry Potter", "Hermione Granger"],
                    "caused_by": [],
                    "causes": [{"event_id": "t_2", "explanation": "Their regrouping leads to a quieter aftermath scene."}],
                },
                {
                    "id": "t_2",
                    "description": "Harry confides in Hermione at Grimmauld Place.",
                    "story_impact": 9,
                    "time_index": 2,
                    "book_index": 1,
                    "chapter_index": 2,
                    "scene_index": 1,
                    "characters": ["Harry Potter", "Hermione Granger"],
                    "caused_by": [{"event_id": "t_1", "explanation": "The regrouping gives Harry space to open up."}],
                    "causes": [],
                },
            ],
            "critical_path": [
                {"event_id": "t_1", "criticality_score": 8, "why_critical": "It anchors the emotional reset."},
                {"event_id": "t_2", "criticality_score": 9, "why_critical": "It changes Harry and Hermione's bond."},
            ],
            "flexible_events": [
                {"event_id": "t_2", "flexibility_score": 7, "why_flexible": "This intimate scene can branch in multiple sequel directions."}
            ],
            "causal_chains": [
                {
                    "chain_id": "chain_1",
                    "description": "Battle aftermath to confession",
                    "chain_type": "LINEAR",
                    "story_function": "emotional aftermath",
                    "event_sequence": ["t_1", "t_2"],
                }
            ],
            "divergence_points": [
                {
                    "event_id": "t_2",
                    "decision_made": "Harry chooses to confide in Hermione.",
                    "alternatives": ["He withdraws instead."],
                    "divergence_potential": 8,
                    "alternate_timeline": "Harry isolates himself further.",
                }
            ],
        }
    }
    return {
        "contract_version": "test",
        "generated_at_utc": "2026-01-01T00:00:00Z",
        "inputs": {
            "books": [{"title": "Harry Potter and the Order of the Phoenix", "path": "hp5.epub"}]
        },
        "outputs": outputs,
    }


def test_narrative_context_service_builds_decoder_schema():
    service = NarrativeContextService()

    context = service.build_from_contract(_sample_contract())

    assert context["meta"]["book_title"] == "Harry Potter and the Order of the Phoenix"
    assert context["story_ending"]["last_scene"]["summary"] == "Harry confides in Hermione at Grimmauld Place."
    assert len(context["story_ending"]["critical_path_tail"]) == 2
    assert any(item["name"] == "Harry Potter" for item in context["character_states"])
    assert any(item["entity_a"] == "Harry Potter" for item in context["relationship_summary"])
    assert context["unresolved_threads"][0]["event_id"] == "t_2"
    assert context["causal_chains"][0]["events"][0]["event_id"] == "t_1"
    assert context["flexible_events"][0]["event_id"] == "t_2"
    assert any(item["character"] == "Harry Potter" for item in context["character_trajectories"])


def test_narrative_context_service_prefers_exported_context_when_present():
    service = NarrativeContextService()
    contract = _sample_contract()
    exported = {
        "meta": {"book_title": "Exported Context Book"},
        "story_ending": {"last_scene": {"summary": "Precomputed ending."}, "critical_path_tail": []},
        "character_states": [{"name": "Cached Character"}],
        "relationship_summary": [],
        "unresolved_threads": [],
        "causal_chains": [],
        "flexible_events": [],
        "character_trajectories": [],
        "stats": {"characters_retrieved": 1},
    }
    contract["outputs"]["sequel_artifacts"] = {"context": exported, "blueprint": {}}

    context = service.build_from_contract(contract)

    assert context == exported


def test_narrative_context_service_rebuilds_when_exported_context_is_malformed():
    service = NarrativeContextService()
    contract = _sample_contract()
    contract["outputs"]["sequel_artifacts"] = {
        "context": {"meta": {"book_title": "Broken"}},
        "blueprint": {},
    }

    context = service.build_from_contract(contract)

    assert context["meta"]["book_title"] == "Harry Potter and the Order of the Phoenix"
    assert context["story_ending"]["last_scene"]["summary"] == "Harry confides in Hermione at Grimmauld Place."
