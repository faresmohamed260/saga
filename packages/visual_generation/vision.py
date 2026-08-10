"""Visual semantic evaluation through the injected reasoning runtime."""

from __future__ import annotations

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
        return parsed
