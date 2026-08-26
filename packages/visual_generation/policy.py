"""Provider-neutral visual quality decisions over structured audit evidence."""

from __future__ import annotations

import re
from typing import Any

from packages.visual_generation.contracts import VisualDefectEvidence, VisualPolicyDecision


_ISSUE_RULES: tuple[tuple[str, str, str], ...] = (
    (r"malformed anatomy|extra limb|extra finger|elongated.*finger|unnatural.*finger|broken anatomy", "anatomy", "high"),
    (r"cast violation|incorrect.*human|visible human count|duplicate (?:person|subject)|people present|characters present", "character_count", "high"),
    (r"clothing.*(?:differ|drift|mismatch|var)|garment.*(?:differ|mismatch)|required attire", "clothing", "high"),
    (r"barefoot|footwear.*(?:missing|differ|mismatch)", "footwear", "high"),
    (r"identity.*(?:inconsistent|drift)|face.*(?:differ|inconsistent)|inconsistent face", "identity_consistency", "high"),
    (r"action.*(?:missing|mismatch|not depicted|contradict)|gesture.*(?:missing|mismatch)", "action_alignment", "high"),
    (r"collage|montage|split frame|multiple frames|divided composition", "composition", "high"),
    (r"wrong target|fundamentally wrong|not depicted|instead of", "wrong_target", "high"),
    (r"forbidden subject|people present|characters present|negative prompt violation|violates.*no-people", "forbidden_subject", "high"),
    (r"slightly|minor|partially obscured|subtle", "other", "low"),
)


def decide_visual_quality(
    *,
    technical_passed: bool,
    scores: dict[str, float],
    issues: list[str],
    hard_violations: list[str],
    defect_observations: list[dict[str, Any]] | None = None,
    evaluator_error: bool = False,
) -> VisualPolicyDecision:
    defects = [VisualDefectEvidence.model_validate(item) for item in list(defect_observations or [])]
    defects.extend(_legacy_issue_defects([*hard_violations, *issues]))
    if not technical_passed:
        defects.append(VisualDefectEvidence(category="technical", severity="high", confidence=1.0, evidence="Technical image validation failed."))
    defects = _dedupe_defects(defects)

    blocking = [item for item in defects if item.severity == "high" and item.confidence >= 0.70]
    review = [item for item in defects if item not in blocking and item.severity in {"medium", "high"} and item.confidence >= 0.55]
    score_failure = (
        scores.get("prompt_alignment_score", 0.0) < 0.65
        or scores.get("subject_consistency_score", 0.0) < 0.60
        or scores.get("composition_score", 0.0) < 0.55
        or scores.get("photorealism_score", 0.0) < 0.55
        or scores.get("defect_score", 1.0) > 0.35
    )
    if evaluator_error:
        return VisualPolicyDecision(outcome="uncertain", defects=defects, review_reasons=["Semantic evaluator did not produce a reliable decision."])
    if blocking or not technical_passed or hard_violations or score_failure:
        reasons = [_retry_reason(item) for item in blocking]
        if score_failure and not reasons:
            reasons.append("Correct the low-scoring prompt alignment, consistency, composition, realism, or visible defects.")
        return VisualPolicyDecision(
            outcome="rejected", defects=defects, blocking_defects=blocking,
            retry_reasons=_unique(reasons),
        )
    if review:
        return VisualPolicyDecision(
            outcome="uncertain", defects=defects,
            review_reasons=_unique([item.evidence or f"Uncertain {item.category} defect." for item in review]),
        )
    return VisualPolicyDecision(outcome="accepted", defects=defects)


def _legacy_issue_defects(issues: list[str]) -> list[VisualDefectEvidence]:
    results: list[VisualDefectEvidence] = []
    for issue in issues:
        text = str(issue or "").strip()
        lowered = text.casefold()
        if not text:
            continue
        for pattern, category, severity in _ISSUE_RULES:
            if re.search(pattern, lowered):
                confidence = 0.95 if severity == "high" else 0.45
                results.append(VisualDefectEvidence(category=category, severity=severity, confidence=confidence, evidence=text))
    return results


def _retry_reason(defect: VisualDefectEvidence) -> str:
    instructions = {
        "anatomy": "Correct malformed anatomy, hands, fingers, limbs, and body proportions.",
        "character_count": "Render exactly the required visible character count with no duplicates or background figures.",
        "clothing": "Match the required clothing consistently across every visible view.",
        "footwear": "Show the required consistent footwear in every full-body view.",
        "identity_consistency": "Keep face, hair, body, and identity identical across all views.",
        "action_alignment": "Depict the specified frozen action and gesture clearly.",
        "composition": "Use one continuous frame with no collage, montage, panels, or split composition.",
        "wrong_target": "Render the requested target itself, not a related prop or substitute.",
        "forbidden_subject": "Remove every forbidden person, creature, silhouette, body part, and narrative action.",
        "technical": "Produce a sharp, nonblank image at the required dimensions without seams.",
    }
    return instructions.get(defect.category, f"Correct the reported {defect.category} defect.")


def _dedupe_defects(items: list[VisualDefectEvidence]) -> list[VisualDefectEvidence]:
    seen: set[tuple[str, str]] = set()
    result: list[VisualDefectEvidence] = []
    for item in items:
        key = (item.category, item.evidence.casefold())
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if str(value).strip()))
