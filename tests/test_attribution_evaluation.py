from __future__ import annotations

from packages.analysis_foundation.attribution_evaluation import AttributionGoldCase, evaluate_attribution


def test_attribution_evaluation_reports_precision_recall_and_contamination():
    result = evaluate_attribution(
        events=[
            {
                "event_id": "event-1",
                "scene_id": "scene-1",
                "title": "Narrator sends note",
                "participant_refs": ["char-taryn", "char-locke", "char-vivi"],
            },
            {
                "event_id": "event-2",
                "scene_id": "scene-2",
                "title": "Unsupported guest appears",
                "participant_refs": ["char-unknown"],
            },
        ],
        gold_cases=[
            AttributionGoldCase(
                case_id="note",
                scene_id="scene-1",
                title_contains="note",
                expected_participant_refs=["char-taryn", "char-locke"],
                forbidden_participant_refs=["char-vivi"],
                narrator_character_id="char-taryn",
            ),
            AttributionGoldCase(
                case_id="missing",
                scene_id="scene-2",
                expected_participant_refs=["char-jude"],
            ),
        ],
        valid_character_refs={"char-taryn", "char-locke", "char-jude", "char-vivi"},
    )

    assert result.case_count == 2
    assert result.matched_case_count == 2
    assert result.participant_precision == 0.5
    assert result.participant_recall == 0.6667
    assert result.attribution_f1 == 0.5714
    assert result.narrator_attribution_accuracy == 1.0
    assert result.unsupported_ref_rate == 0.25
    assert result.contamination_rate == 0.5


def test_attribution_evaluation_selects_best_supported_matching_event():
    result = evaluate_attribution(
        events=[
            {
                "event_id": "partial",
                "scene_id": "scene-1",
                "title": "Locke States Marriage Conditions",
                "summary": "Locke lists conditions.",
                "participant_refs": ["char-locke"],
            },
            {
                "event_id": "complete",
                "scene_id": "scene-1",
                "title": "Locke Accepts with Conditions",
                "summary": "Locke agrees to marry Taryn but imposes three conditions.",
                "participant_refs": ["char-locke", "char-taryn"],
            },
        ],
        gold_cases=[
            AttributionGoldCase(
                case_id="conditions",
                scene_id="scene-1",
                title_any_contains=["conditions for marriage"],
                expected_participant_refs=["char-locke", "char-taryn"],
                narrator_character_id="char-taryn",
            )
        ],
        valid_character_refs={"char-locke", "char-taryn"},
    )

    assert result.details[0]["event_id"] == "complete"
    assert result.attribution_f1 == 1.0
    assert result.narrator_attribution_accuracy == 1.0
