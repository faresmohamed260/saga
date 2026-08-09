from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packages.production_orchestration import OrchestrationRequest, ProductionOrchestrationService


def main() -> int:
    parser = argparse.ArgumentParser(description="Run or resume the production pipeline and package accepted deliverables.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--series-id", required=True)
    parser.add_argument("--story-id", default="")
    parser.add_argument("--blueprint-id", default="")
    parser.add_argument("--audiobook-run-id", default="")
    parser.add_argument("--source-path", action="append", default=[])
    parser.add_argument("--premise", default="")
    parser.add_argument("--target-audience", default="")
    parser.add_argument("--tone", default="")
    parser.add_argument("--desired-chapter-count", type=int, default=3)
    parser.add_argument("--stages", default="artifact_packaging")
    parser.add_argument("--exclude-visuals", action="store_true")
    parser.add_argument("--exclude-audiobook", action="store_true")
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--thread-id", default="")
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()
    request = OrchestrationRequest(
        run_id=args.run_id,
        series_id=args.series_id,
        story_id=args.story_id,
        blueprint_id=args.blueprint_id,
        audiobook_run_id=args.audiobook_run_id,
        source_paths=args.source_path,
        premise=args.premise,
        target_audience=args.target_audience,
        tone=args.tone,
        desired_chapter_count=args.desired_chapter_count,
        selected_stages=[item.strip() for item in args.stages.split(",") if item.strip()],
        include_visuals=not args.exclude_visuals,
        include_audiobook=not args.exclude_audiobook,
        max_attempts=args.max_attempts,
    )
    result = ProductionOrchestrationService.from_env().run(request, thread_id=args.thread_id)
    payload = result.model_dump()
    if args.output_json:
        target = Path(args.output_json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"decision": payload["decision"], "manifest": payload.get("manifest"), "run_metadata": payload["run_metadata"]}, ensure_ascii=False, indent=2))
    return 0 if result.decision.accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
