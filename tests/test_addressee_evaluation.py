from packages.analysis_foundation import (
    AddresseeGoldCase,
    SceneNarrativeGrounding,
    evaluate_addressees,
)


def test_addressee_evaluation_reports_precision_recall_coverage_and_contamination():
    result = evaluate_addressees(
        groundings=[
            SceneNarrativeGrounding(scene_id="scene-explicit", addressee_character_ids=["char-a", "char-extra"]),
            SceneNarrativeGrounding(scene_id="scene-absent"),
            SceneNarrativeGrounding(scene_id="scene-unsupported", addressee_character_ids=["char-unknown"]),
        ],
        gold_cases=[
            AddresseeGoldCase(case_id="explicit", scene_id="scene-explicit", category="explicit", expected_character_ids=["char-a"]),
            AddresseeGoldCase(case_id="absent", scene_id="scene-absent", category="absent"),
            AddresseeGoldCase(case_id="unknown", scene_id="scene-unsupported", category="unknown"),
        ],
        valid_character_ids={"char-a", "char-extra"},
    )

    assert result.precision == 0.3333
    assert result.recall == 1.0
    assert result.f1 == 0.5
    assert result.coverage == 0.6667
    assert result.unsupported_attribution_rate == 0.3333
    assert result.contamination_rate == 0.6667
