"""Technical image validation for visual generation outputs."""

from __future__ import annotations

import io
from typing import Any


def evaluate_image_technical_quality(image_bytes: bytes, *, expected_width: int, expected_height: int) -> dict[str, Any]:
    try:
        from PIL import Image, ImageStat
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
    issues: list[str] = []
    if image.width != expected_width or image.height != expected_height:
        issues.append(f"unexpected_dimensions:{image.width}x{image.height}")
    if mean <= 3.0 or variance <= 1.0 or black_ratio >= 0.98:
        issues.append("black_or_blank_image")
    return {
        "passed": not issues,
        "issues": issues,
        "width": image.width,
        "height": image.height,
        "byte_length": len(image_bytes),
        "mean_luminance": round(mean, 4),
        "variance": round(variance, 4),
        "black_pixel_ratio": round(black_ratio, 6),
    }
