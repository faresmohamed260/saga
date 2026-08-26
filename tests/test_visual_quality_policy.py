from __future__ import annotations

import json
from pathlib import Path

from packages.visual_generation import decide_visual_quality, evaluate_visual_quality_policy


FIXTURE = Path(__file__).parent / "fixtures" / "visual_quality" / "persisted_real_renders.json"


def _dataset() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_persisted_render_policy_closes_known_false_accepts():
    baseline = evaluate_visual_quality_policy(_dataset(), use_existing_decisions=True)
    hardened = evaluate_visual_quality_policy(_dataset())

    assert baseline.false_accept_rate == 0.5556
    assert baseline.recall == 0.4444
    assert hardened.precision == 1.0
    assert hardened.recall == 1.0
    assert hardened.f1 == 1.0
    assert hardened.false_accept_rate == 0.0
    assert hardened.false_reject_rate == 0.0
    assert hardened.exact_outcome_accuracy == 1.0
    assert all(value == 1.0 for value in hardened.per_defect_recall.values())


def test_medium_confidence_anatomy_is_uncertain_not_accepted_or_auto_rejected():
    decision = decide_visual_quality(
        technical_passed=True,
        scores={"prompt_alignment_score": 0.9, "subject_consistency_score": 0.9, "composition_score": 0.9, "photorealism_score": 0.9, "defect_score": 0.1},
        issues=[], hard_violations=[],
        defect_observations=[{"category": "anatomy", "severity": "medium", "confidence": 0.7, "evidence": "Borderline hand geometry."}],
    )
    assert decision.outcome == "uncertain"
    assert decision.review_reasons == ["Borderline hand geometry."]


def test_high_confidence_action_mismatch_produces_targeted_retry_instruction():
    decision = decide_visual_quality(
        technical_passed=True,
        scores={"prompt_alignment_score": 0.9, "subject_consistency_score": 0.9, "composition_score": 0.9, "photorealism_score": 0.9, "defect_score": 0.1},
        issues=[], hard_violations=[],
        defect_observations=[{"category": "action_alignment", "severity": "high", "confidence": 0.9, "evidence": "Required gesture is absent."}],
    )
    assert decision.outcome == "rejected"
    assert decision.retry_reasons == ["Depict the specified frozen action and gesture clearly."]
