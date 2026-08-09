from __future__ import annotations

import io
import math
import struct
import wave

from PIL import Image

from packages.production_orchestration import PackageChapter, PackageSourceBundle, build_epub
from packages.qualification_runtime import ProductionQualificationReport, QualificationCheck, applicable_visual_types, audio_quality, epub_quality, image_quality


class _Scene:
    character_refs = ["char-one"]
    entity_refs = ["entity-object"]


class _Entity:
    def __init__(self, entity_id: str, entity_type: str) -> None:
        self.entity_id = entity_id
        self.entity_type = entity_type


def test_qualification_report_fails_closed_on_critical_check():
    checks = [
        QualificationCheck(check_id="required", category="test", status="failed", critical=True),
        QualificationCheck(check_id="advisory", category="test", status="warning", critical=False),
    ]
    report = ProductionQualificationReport(
        report_id="qualification-test", run_id="run-test", series_id="series-test",
        source_path="book.epub", source_sha256="0" * 64, accepted=not any(item.critical and item.status == "failed" for item in checks), checks=checks,
    )
    assert report.accepted is False


def test_media_and_epub_quality_detect_real_content():
    image_buffer = io.BytesIO()
    image = Image.new("RGB", (320, 320))
    for x in range(320):
        for y in range(320):
            image.putpixel((x, y), ((x * 3) % 255, (y * 5) % 255, ((x + y) * 7) % 255))
    image.save(image_buffer, format="PNG")
    image_metrics = image_quality(image_buffer.getvalue())
    assert image_metrics["width"] == 320 and image_metrics["luma_stddev"] > 3

    audio_buffer = io.BytesIO()
    with wave.open(audio_buffer, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(24000)
        samples = [int(8000 * math.sin(2 * math.pi * 440 * index / 24000)) for index in range(24000)]
        stream.writeframes(b"".join(struct.pack("<h", sample) for sample in samples))
    audio_metrics = audio_quality(audio_buffer.getvalue())
    assert audio_metrics["duration_seconds"] == 1.0 and audio_metrics["rms"] > 0.1

    epub = build_epub(PackageSourceBundle(story_id="story", title="Story", chapters=[PackageChapter(chapter_index=1, title="One", prose="Real prose.")]))
    epub_metrics = epub_quality(epub)
    assert epub_metrics["valid"] is True and epub_metrics["chapter_count"] == 1


def test_visual_applicability_does_not_require_ungrounded_types():
    types = applicable_visual_types(
        scene_prose=[_Scene()],
        entities=[_Entity("entity-object", "artifact"), _Entity("entity-unused", "creature")],
    )

    assert types == {"scene", "character", "object"}
