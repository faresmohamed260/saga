"""Visual semantic evaluation through the injected reasoning runtime."""

from __future__ import annotations

from typing import Any

from packages.reasoning_runtime import ReasoningRuntimeClient
from packages.visual_generation.contracts import VisualPromptArtifact


class ReasoningVisionSemanticEvaluator:
    def __init__(
        self,
        reasoning_runtime: ReasoningRuntimeClient,
        *,
        hard_constraint_runtime: ReasoningRuntimeClient | None = None,
    ) -> None:
        self.reasoning_runtime = reasoning_runtime
        self.hard_constraint_runtime = hard_constraint_runtime or reasoning_runtime

    def evaluate(self, *, image_bytes: bytes, prompt: VisualPromptArtifact) -> dict[str, Any]:
        instruction = (
            "Evaluate this generated image against the production prompt. Return JSON only with scores from 0 to 1: "
            "prompt_alignment_score, subject_consistency_score, composition_score, photorealism_score, defect_score; "
            "also return issues and hard_constraint_violations as lists of concise strings, plus defect_observations as a list of objects. "
            "Each defect object must contain category, severity (low, medium, high), confidence (0 to 1), and concise visible evidence. "
            "Allowed categories are anatomy, character_count, clothing, footwear, identity_consistency, action_alignment, composition, "
            "wrong_target, forbidden_subject, technical, and other. Explicitly inspect hands/fingers, required frozen action, whether the "
            "requested target itself is shown, and whether the image is one continuous frame. A hard constraint is any explicit target or "
            "negative-prompt violation; when present, alignment must be at most 0.4 and defect score at least 0.6. Defect score is higher "
            "when there are duplicate subjects, malformed anatomy, "
            "black/blank regions, blur or soft focus when sharp focus is required, unreadable composition, text/watermarks, "
            "or character-sheet identity drift. A montage, split frame, inset panel, or collage is a hard violation when the prompt "
            "asks for one coherent narrative scene. "
            "Character names are semantic identifiers and must never appear as written labels in the image; do not require visible names or text. "
            "For a hard cast limit, count visible human figures and compare that count with the required total. "
            "Treat omitted minor expression, accessory, material, lighting, or architectural details as scored issues, not hard violations. "
            "Reserve hard violations for an incorrect "
            "cast count, a forbidden subject, duplicate subject, malformed anatomy, text/watermark, black image, or fundamentally wrong target type. "
            f"Target type: {prompt.target_type}. Positive prompt: {prompt.positive_prompt}. Negative prompt: {prompt.negative_prompt}."
        )
        parsed = self.reasoning_runtime.generate_vision_json(
            prompt=instruction,
            image_bytes=image_bytes,
        )
        if not isinstance(parsed, dict):
            raise ValueError("Vision evaluator returned a non-object JSON payload.")
        if parsed.get("error"):
            raise RuntimeError(f"Vision evaluator failed: {parsed!r}")
        parsed["request_metadata"] = self.reasoning_runtime.last_request_metadata()
        expected_clothing = str(prompt.metadata.get("expected_character_clothing") or "").strip()
        if prompt.target_type == "character" and expected_clothing:
            character_audit = self._evaluate_character_consistency(
                image_bytes=image_bytes,
                expected_clothing=expected_clothing,
                negative_prompt=prompt.negative_prompt,
                requires_footwear=prompt.metadata.get("requires_footwear") is True,
            )
            parsed["character_consistency_audit"] = character_audit
            if not character_audit["passed"]:
                violations = list(parsed.get("hard_constraint_violations") or [])
                violations.extend(character_audit["hard_constraint_violations"])
                parsed["hard_constraint_violations"] = list(dict.fromkeys(violations))
                parsed["prompt_alignment_score"] = min(_score(parsed.get("prompt_alignment_score")), 0.4)
                parsed["defect_score"] = max(_score(parsed.get("defect_score")), 0.6)
        expected_count = prompt.metadata.get("expected_visible_human_count")
        if isinstance(expected_count, int) and not isinstance(expected_count, bool):
            cast_audit = self._evaluate_hard_cast(
                image_bytes=image_bytes,
                expected_count=expected_count,
            )
            parsed["cast_audit"] = cast_audit
            if not cast_audit["passed"]:
                violations = list(parsed.get("hard_constraint_violations") or [])
                violations.append(str(cast_audit["violation"]))
                parsed["hard_constraint_violations"] = list(dict.fromkeys(violations))
                parsed["prompt_alignment_score"] = min(_score(parsed.get("prompt_alignment_score")), 0.4)
                parsed["defect_score"] = max(_score(parsed.get("defect_score")), 0.6)
        return parsed

    def _evaluate_character_consistency(
        self,
        *,
        image_bytes: bytes,
        expected_clothing: str,
        negative_prompt: str,
        requires_footwear: bool,
    ) -> dict[str, Any]:
        result = self.reasoning_runtime.generate_vision_json(
            prompt=(
                "Audit this three-view character sheet for hard visual consistency. Compare front, side, and back across the "
                "entire image. Return JSON only with these booleans: same_clothing_all_views, "
                "same_sleeve_length_all_views, same_footwear_all_views, all_views_full_body, "
                "required_clothing_match_all_views, visible_skin_tight_bodysuit, "
                "visible_transparent_or_sheer_clothing, visible_barefoot_any_view; plus hard_constraint_violations and evidence "
                "as lists of concise strings. Different or missing sleeves, changed garments or footwear, cropped bodies, "
                "forbidden garments, or failure to match required attire are hard violations. Classify only what is visibly "
                f"rendered. Required clothing: {expected_clothing}. Forbidden clothing: {negative_prompt}. "
                f"Footwear required: {str(requires_footwear).lower()}."
            ),
            image_bytes=image_bytes,
        )
        required_true = (
            "same_clothing_all_views", "same_sleeve_length_all_views", "same_footwear_all_views",
            "all_views_full_body", "required_clothing_match_all_views",
        )
        required_false = ("visible_skin_tight_bodysuit", "visible_transparent_or_sheer_clothing")
        for key in (*required_true, *required_false, "visible_barefoot_any_view"):
            if not isinstance(result.get(key), bool):
                raise ValueError(f"Vision character-consistency evaluator omitted boolean '{key}'.")
        violations = [str(item) for item in list(result.get("hard_constraint_violations") or []) if str(item).strip()]
        for key in required_true:
            if result[key] is not True:
                violations.append(f"Character-sheet hard constraint failed: {key}.")
        for key in required_false:
            if result[key] is True:
                violations.append(f"Character-sheet forbidden clothing detected: {key}.")
        if requires_footwear and result["visible_barefoot_any_view"] is True:
            violations.append("Character-sheet required footwear is missing in at least one view.")
        violations = list(dict.fromkeys(violations))
        return {
            **{key: result[key] for key in (*required_true, *required_false, "visible_barefoot_any_view")},
            "requires_footwear": requires_footwear,
            "passed": not violations,
            "hard_constraint_violations": violations,
            "evidence": [str(item) for item in list(result.get("evidence") or []) if str(item).strip()],
            "request_metadata": self.reasoning_runtime.last_request_metadata(),
        }

    def _evaluate_hard_cast(
        self,
        *,
        image_bytes: bytes,
        expected_count: int,
    ) -> dict[str, Any]:
        result = self.hard_constraint_runtime.generate_vision_json(
            prompt=(
                "Count every visible human or human-like figure in the entire image. Include tiny, blurred, cloaked, "
                "partially occluded background people and partially framed people. Do not count painted portraits or "
                "statues. Return JSON only with visible_human_count as a non-negative integer, uncertain_human_count as "
                "a non-negative integer, and detections as a list of concise locations."
            ),
            image_bytes=image_bytes,
        )
        observed_count = _nonnegative_int(result.get("visible_human_count"))
        uncertain_count = _nonnegative_int(result.get("uncertain_human_count"))
        if observed_count is None or uncertain_count is None:
            raise ValueError("Vision hard-constraint evaluator returned an invalid count payload.")
        passed = observed_count == expected_count and uncertain_count == 0
        return {
            "passed": passed,
            "expected_visible_human_count": expected_count,
            "observed_visible_human_count": observed_count,
            "uncertain_count": uncertain_count,
            "detections": [str(item) for item in list(result.get("detections") or []) if str(item).strip()],
            "request_metadata": self.hard_constraint_runtime.last_request_metadata(),
            "violation": "" if passed else (
                f"Hard cast violation: expected {expected_count} visible human figure(s), observed {observed_count} "
                f"with {uncertain_count} uncertain detection(s)."
            ),
        }


def _score(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None
