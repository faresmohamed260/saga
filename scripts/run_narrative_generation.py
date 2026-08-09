from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packages.narrative_generation import NarrativeGenerationRunRequest, NarrativeGenerationService


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run narrative generation from a persisted generation blueprint.")
    parser.add_argument("--series-id", required=True)
    parser.add_argument("--blueprint-id", default="")
    parser.add_argument("--story-id", default="")
    parser.add_argument("--thread-id", default="narrative-generation")
    parser.add_argument("--target-words-per-scene", type=int, default=180)
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()
    request = NarrativeGenerationRunRequest(
        series_id=args.series_id,
        blueprint_id=args.blueprint_id,
        story_id=args.story_id,
        thread_id=args.thread_id,
        target_words_per_scene=args.target_words_per_scene,
    )
    service = NarrativeGenerationService.from_env()
    result = service.run(request)
    quality = service.build_quality_audit(result=result)
    report = service.persist_runtime_report(request=request, result=result, quality_audit=quality)
    payload = {
        "series_id": result.series_id,
        "story_id": result.story.story_id,
        "chapter_count": len(result.story.chapters),
        "scene_prose_count": len(result.scene_prose),
        "quality_audit": quality,
        "report": report,
        "result": result.model_dump(),
    }
    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
