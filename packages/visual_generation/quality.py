"""Technical image validation for visual generation outputs."""

from __future__ import annotations

import io
import statistics
from typing import Any


_MIN_EDGE_VARIANCE = 600.0
_CENTRAL_SEAM_RATIO = 6.0
_CENTRAL_SEAM_COVERAGE = 0.50


def evaluate_image_technical_quality(
    image_bytes: bytes,
    *,
    expected_width: int,
    expected_height: int,
    target_type: str | None = None,
) -> dict[str, Any]:
    try:
        from PIL import Image, ImageFilter, ImageStat
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Pillow is required by the visual-generation quality gate.") from exc
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image.load()
    except Exception as exc:
        return {"passed": False, "issues": [f"corrupt_image:{type(exc).__name__}"], "byte_length": len(image_bytes)}
    sample = image.resize((64, 64))
    stat = ImageStat.Stat(sample)
    mean = sum(stat.mean) / 3.0
    variance = sum(stat.var) / 3.0
    pixel_source = sample.get_flattened_data() if hasattr(sample, "get_flattened_data") else sample.getdata()
    pixels = list(pixel_source)
    black_ratio = sum(1 for pixel in pixels if max(pixel) <= 5) / max(1, len(pixels))
    border_x = max(1, int(image.width * 0.05))
    border_y = max(1, int(image.height * 0.05))
    focus_region = image.crop((border_x, border_y, image.width - border_x, image.height - border_y)).convert("L")
    sharpness_variance = ImageStat.Stat(focus_region.filter(ImageFilter.FIND_EDGES)).var[0]
    seam = _central_horizontal_seam_metrics(image) if target_type == "scene" else None
    issues: list[str] = []
    if image.width != expected_width or image.height != expected_height:
        issues.append(f"unexpected_dimensions:{image.width}x{image.height}")
    if mean <= 3.0 or variance <= 1.0 or black_ratio >= 0.98:
        issues.append("black_or_blank_image")
    if sharpness_variance < _MIN_EDGE_VARIANCE:
        issues.append("soft_or_blurred_image")
    if seam and seam["detected"]:
        issues.append("central_horizontal_seam_or_collage")
    return {
        "passed": not issues,
        "issues": issues,
        "width": image.width,
        "height": image.height,
        "byte_length": len(image_bytes),
        "mean_luminance": round(mean, 4),
        "variance": round(variance, 4),
        "black_pixel_ratio": round(black_ratio, 6),
        "sharpness_edge_variance": round(sharpness_variance, 4),
        "central_horizontal_seam": seam,
    }


def _central_horizontal_seam_metrics(image: Any) -> dict[str, Any]:
    if image.width > 256:
        image = image.resize((256, image.height))
    pixels = image.load()
    row_scores: list[float] = []
    row_coverages: list[float] = []
    for y in range(1, image.height):
        total = 0.0
        strong_edges = 0
        for x in range(image.width):
            current = pixels[x, y]
            previous = pixels[x, y - 1]
            difference = sum(abs(current[channel] - previous[channel]) for channel in range(3)) / 3.0
            total += difference
            strong_edges += difference > 20.0
        row_scores.append(total / image.width)
        row_coverages.append(strong_edges / image.width)
    lower = max(0, int(image.height * 0.4) - 1)
    upper = min(len(row_scores), int(image.height * 0.6) - 1)
    central_scores = row_scores[lower:upper]
    if not central_scores:
        return {"detected": False, "row": None, "ratio": 0.0, "coverage": 0.0}
    central_offset = max(range(len(central_scores)), key=central_scores.__getitem__)
    index = lower + central_offset
    median_score = statistics.median(row_scores) or 1e-9
    ratio = row_scores[index] / median_score
    coverage = row_coverages[index]
    return {
        "detected": ratio >= _CENTRAL_SEAM_RATIO and coverage >= _CENTRAL_SEAM_COVERAGE,
        "row": index + 1,
        "ratio": round(ratio, 4),
        "coverage": round(coverage, 6),
    }
