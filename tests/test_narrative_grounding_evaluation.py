from packages.analysis_foundation import (
    NarrativeGroundingGoldCase,
    SceneNarrativeGrounding,
    evaluate_narrative_grounding,
)


def test_narrative_grounding_evaluation_reports_required_metrics():
    result = evaluate_narrative_grounding(
        groundings=[
            SceneNarrativeGrounding(scene_id="scene-1", perspective="third_person"),
            SceneNarrativeGrounding(
                scene_id="scene-2",
                perspective="first_person",
                narrator_character_id="char-taryn",
            ),
        ],
        gold_cases=[
            NarrativeGroundingGoldCase(
                case_id="third-person-dialogue",
                scene_id="scene-1",
                expected_perspective="third_person",
            ),
            NarrativeGroundingGoldCase(
                case_id="first-person-taryn",
                scene_id="scene-2",
                expected_perspective="first_person",
                expected_narrator_character_id="char-taryn",
            ),
        ],
    )

    assert result.matched_case_count == 2
    assert result.perspective_precision == 1.0
    assert result.perspective_recall == 1.0
    assert result.perspective_f1 == 1.0
    assert result.narrator_precision == 1.0
    assert result.narrator_recall == 1.0
    assert result.narrator_f1 == 1.0
    assert result.narrator_applicable_case_count == 1
    assert result.narrator_coverage == 0.5
    assert result.contradiction_rate == 0.0


def test_narrative_grounding_evaluation_counts_perspective_and_narrator_contradictions():
    result = evaluate_narrative_grounding(
        groundings=[
            SceneNarrativeGrounding(
                scene_id="scene-1",
                perspective="first_person",
                narrator_character_id="char-wrong",
            )
        ],
        gold_cases=[
            NarrativeGroundingGoldCase(
                case_id="wrong-grounding",
                scene_id="scene-1",
                expected_perspective="third_person",
            )
        ],
    )

    assert result.perspective_f1 == 0.0
    assert result.narrator_precision == 0.0
    assert result.narrator_recall is None
    assert result.narrator_f1 is None
    assert result.narrator_applicable_case_count == 0
    assert result.narrator_coverage == 1.0
    assert result.contradiction_rate == 1.0
