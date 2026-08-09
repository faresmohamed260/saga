from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packages.generation_planning import GenerationPlanningRunRequest, GenerationPlanningService


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the generation-planning runtime against persisted canon/CWM data.")
    parser.add_argument("--series-id", required=True)
    parser.add_argument("--thread-id", default="generation-planning")
    parser.add_argument("--premise", default="Create a canon-grounded continuation.")
    parser.add_argument("--target-audience", default="")
    parser.add_argument("--tone", default="")
    parser.add_argument("--continuation-mode", default="canon_continuation")
    parser.add_argument("--desired-chapter-count", type=int, default=3)
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()

    request = GenerationPlanningRunRequest(
        series_id=args.series_id,
        thread_id=args.thread_id,
        premise=args.premise,
        target_audience=args.target_audience,
        tone=args.tone,
        continuation_mode=args.continuation_mode,
        desired_chapter_count=args.desired_chapter_count,
    )
    service = GenerationPlanningService.from_env()
    result = service.run(request)
    quality = service.build_quality_audit(result=result)
    report = service.persist_runtime_report(request=request, result=result, quality_audit=quality)
    payload = {
        "series_id": result.series_id,
        "chapter_outline_count": len(result.blueprint.chapter_outline),
        "scene_plan_count": len(result.blueprint.scene_plan),
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
