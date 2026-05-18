from analysis.scene_analysis_orchestrator import SceneAnalysisOrchestrator


class StubAnalyzer:
    def __init__(self, response_by_mode):
        self.response_by_mode = response_by_mode
        self.calls = []

    def analyze(self, scene, alias_map=None, rejected_identities=None, scene_context="", local_evidence=None, analysis_mode="structured"):
        self.calls.append(
            {
                "scene": scene,
                "analysis_mode": analysis_mode,
                "local_evidence": local_evidence,
            }
        )
        return self.response_by_mode[analysis_mode]


class StubLocalExtractor:
    def extract(self, text: str):
        return {
            "mentions": [{"text": "Tomas Mandray", "label": "PERSON"}],
            "clusters": [],
            "candidate_characters": [{"name": "Tomas Mandray", "evidence_mentions": ["Tomas Mandray"], "source": "stub"}],
            "candidate_entities": [],
            "candidate_aliases": [],
            "metadata": {"provider": "stub"},
        }


class StubSemanticRefiner:
    def refine(self, bundle, scene_text: str):
        bundle = dict(bundle)
        bundle.setdefault("metadata", {})
        bundle["metadata"]["semantic_refinement"] = {"enabled": True, "characters_kept": 1}
        return bundle


class StubSceneSemanticReviewer:
    def review(self, scene_result, scene_text: str):
        scene_result = dict(scene_result)
        scene_result["semantic_post_review"] = {"enabled": True, "events_after": len(scene_result.get("events", []))}
        return scene_result


class StubIdentitySemanticReviewer:
    def review(self, scene_result, scene_text: str, local_evidence=None, pov_anchor=""):
        scene_result = dict(scene_result)
        scene_result["identity_semantic_review"] = {"enabled": True, "canonical_characters_after": len(scene_result.get("canonical_characters", [])), "pov_anchor": pov_anchor}
        return scene_result


def build_scene():
    return {
        "book_index": 1,
        "chapter_index": 1,
        "scene_index": 1,
        "length": 50,
        "text": "Feyre notices Tomas Mandray.",
    }


def test_orchestrator_compare_mode_captures_both_paths():
    content = StubAnalyzer(
        {
            "structured": {
                "scene_summary": "Structured summary",
                "canonical_characters": [],
                "character_mentions": [],
                "events": [],
                "entities_present": [],
                "entity_descriptions": [],
                "state_changes": [],
                "relationship_changes": [],
                "location": {},
                "time_signals": [],
                "alias_updates": [],
                "rejected_identity_candidates": [],
            },
            "tool": {
                "scene_summary": "Tool summary",
                "canonical_characters": [],
                "character_mentions": [],
                "events": [],
                "entities_present": [],
                "entity_descriptions": [],
                "state_changes": [],
                "relationship_changes": [],
                "location": {},
                "time_signals": [],
                "alias_updates": [],
                "rejected_identity_candidates": [],
            },
        }
    )
    identity = StubAnalyzer(
        {
            "structured": {
                "canonical_characters": [{"name": "Feyre", "role": "", "is_new_character": False, "names_used": ["Feyre"]}],
                "character_mentions": [],
                "alias_updates": [],
                "rejected_identity_candidates": [],
            },
            "tool": {
                "canonical_characters": [{"name": "Feyre", "role": "", "is_new_character": False, "names_used": ["Feyre"]}],
                "character_mentions": [{"mention_text": "Tomas Mandray", "mention_type": "name", "canonical_name": "Tomas Mandray", "is_consequential_character": True}],
                "alias_updates": [],
                "rejected_identity_candidates": [],
            },
        }
    )
    orchestrator = SceneAnalysisOrchestrator(
        local_entity_extractor=StubLocalExtractor(),
        semantic_evidence_refiner=StubSemanticRefiner(),
        identity_semantic_reviewer=StubIdentitySemanticReviewer(),
        scene_semantic_reviewer=StubSceneSemanticReviewer(),
        scene_analyzer=content,
        identity_analyzer=identity,
    )

    result = orchestrator.analyze_scene(build_scene(), analysis_mode="compare")

    assert result["analysis_mode"] == "compare"
    assert result["scene_summary"] == "Tool summary"
    assert "comparison_results" in result
    assert result["comparison_results"]["structured"]["scene_summary"] == "Structured summary"
    assert result["comparison_results"]["tool"]["local_evidence"]["candidate_characters"][0]["name"] == "Tomas Mandray"
    assert result["comparison_results"]["tool"]["local_evidence"]["metadata"]["semantic_refinement"]["enabled"] is True
    assert result["comparison_results"]["tool"]["identity_semantic_review"]["enabled"] is True
    assert result["comparison_results"]["tool"]["semantic_post_review"]["enabled"] is True
    assert result["local_evidence_raw"]["metadata"]["provider"] == "stub"


def test_orchestrator_can_skip_identity_pass_and_reuse_scene_identity_fields():
    content = StubAnalyzer(
        {
            "structured": {
                "scene_summary": "Structured summary",
                "canonical_characters": [{"name": "Feyre", "role": "", "is_new_character": False, "names_used": ["Feyre"]}],
                "character_mentions": [{"mention_text": "Tomas Mandray", "mention_type": "name", "canonical_name": "Tomas Mandray", "is_consequential_character": True}],
                "events": [],
                "entities_present": [],
                "entity_descriptions": [],
                "state_changes": [],
                "relationship_changes": [],
                "location": {},
                "time_signals": [],
                "alias_updates": [{"alias": "the huntress", "canonical_name": "Feyre", "action": "map_alias", "reasoning": "clear"}],
                "rejected_identity_candidates": ["doe"],
            }
        }
    )
    identity = StubAnalyzer(
        {
            "structured": {
                "canonical_characters": [],
                "character_mentions": [],
                "alias_updates": [],
                "rejected_identity_candidates": [],
            }
        }
    )
    orchestrator = SceneAnalysisOrchestrator(
        local_entity_extractor=StubLocalExtractor(),
        semantic_evidence_refiner=StubSemanticRefiner(),
        identity_semantic_reviewer=StubIdentitySemanticReviewer(),
        scene_semantic_reviewer=StubSceneSemanticReviewer(),
        scene_analyzer=content,
        identity_analyzer=identity,
        identity_pass_enabled=False,
    )

    result = orchestrator.analyze_scene(build_scene(), analysis_mode="structured")

    assert len(content.calls) == 1
    assert len(identity.calls) == 0
    assert result["canonical_characters"][0]["name"] == "Feyre"
    assert result["character_mentions"][0]["canonical_name"] == "Tomas Mandray"
    assert result["alias_updates"][0]["canonical_name"] == "Feyre"
    assert result["rejected_identity_candidates"] == ["doe"]
