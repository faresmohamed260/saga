"""Visual semantic evaluation through the injected reasoning runtime."""

from __future__ import annotations

import io
from typing import Any

from packages.reasoning_runtime import ReasoningRuntimeClient
from packages.visual_generation.contracts import VisualPromptArtifact


class ReasoningVisionSemanticEvaluator:
    def __init__(self, reasoning_runtime: ReasoningRuntimeClient) -> None:
        self.reasoning_runtime = reasoning_runtime

    def evaluate(self, *, image_bytes: bytes, prompt: VisualPromptArtifact) -> dict[str, Any]:
        instruction = (
            "Evaluate this generated image against the production prompt. Return JSON only with scores from 0 to 1: "
            "prompt_alignment_score, subject_consistency_score, composition_score, photorealism_score, defect_score; "
            "also return issues and hard_constraint_violations as lists of concise strings. A hard constraint is any explicit target or "
            "negative-prompt violation; when present, alignment must be at most 0.4 and defect score at least 0.6. Defect score is higher "
            "when there are duplicate subjects, malformed anatomy, "
            "black/blank regions, blur or soft focus when sharp focus is required, unreadable composition, text/watermarks, "
            "or character-sheet identity drift. A montage, split frame, inset panel, or collage is a hard violation when the prompt "
            "asks for one coherent narrative scene. "
            "Character names are semantic identifiers and must never appear as written labels in the image; do not require visible names or text. "
            "For a hard cast limit, count visible human figures and compare that count with the required total. Treat omitted minor expression, "
            "accessory, material, lighting, or architectural details as scored issues, not hard violations. Reserve hard violations for an incorrect "
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
        expected_count = prompt.metadata.get("expected_visible_human_count")
        if isinstance(expected_count, int) and not isinstance(expected_count, bool):
            cast_audit = self._evaluate_hard_cast(image_bytes=image_bytes, expected_count=expected_count)
            parsed["cast_audit"] = cast_audit
            if not cast_audit["passed"]:
                violations = list(parsed.get("hard_constraint_violations") or [])
                violations.append(str(cast_audit["violation"]))
                parsed["hard_constraint_violations"] = list(dict.fromkeys(violations))
                parsed["prompt_alignment_score"] = min(_score(parsed.get("prompt_alignment_score")), 0.4)
                parsed["defect_score"] = max(_score(parsed.get("defect_score")), 0.6)
        return parsed

    def _evaluate_hard_cast(self, *, image_bytes: bytes, expected_count: int) -> dict[str, Any]:
        try:
            from PIL import Image
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Pillow is required by the visual hard-cast audit.") from exc
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        observed_count = 0
        uncertain_count = 0
        strips: list[dict[str, Any]] = []
        for index in range(4):
            left = index * image.width // 4
            right = (index + 1) * image.width // 4
            strip = image.crop((left, 0, right, image.height))
            output = io.BytesIO()
            strip.save(output, format="PNG")
            result = self.reasoning_runtime.generate_vision_json(
                prompt=(
                    "This is one non-overlapping full-height vertical quarter of a larger image. Count every visible human "
                    "or human-like figure whose HEAD CENTER is inside this strip. Include tiny, blurred, cloaked, partially "
                    "occluded background people, silhouettes, statues, human portraits, and human reflections. A body crossing "
                    "the crop edge counts only when its head center is visible in this crop. Return JSON only with "
                    "visible_head_center_count as a non-negative integer, detections as a list, and uncertain_count as a "
                    "non-negative integer."
                ),
                image_bytes=output.getvalue(),
            )
            count = _nonnegative_int(result.get("visible_head_center_count"))
            uncertain = _nonnegative_int(result.get("uncertain_count"))
            if count is None or uncertain is None:
                raise ValueError("Vision hard-cast evaluator returned an invalid count payload.")
            observed_count += count
            uncertain_count += uncertain
            strips.append({
                "strip_index": index,
                "visible_head_center_count": count,
                "uncertain_count": uncertain,
                "detections": list(result.get("detections") or []),
                "request_metadata": self.reasoning_runtime.last_request_metadata(),
            })
        passed = observed_count == expected_count and uncertain_count == 0
        return {
            "passed": passed,
            "expected_visible_human_count": expected_count,
            "observed_visible_human_count": observed_count,
            "uncertain_count": uncertain_count,
            "strips": strips,
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
