from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packages.visual_generation import VisualGenerationRunRequest, VisualGenerationService


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and quality-gate visual assets for an accepted story.")
    parser.add_argument("--series-id", required=True)
    parser.add_argument("--story-id", required=True)
    parser.add_argument("--thread-id", default="")
    parser.add_argument("--include-types", default="")
    parser.add_argument("--max-renders-per-type", type=int, default=0)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--output-json", default="")
    parser.add_argument("--audit-existing", action="store_true")
    parser.add_argument("--retry-existing", action="store_true")
    args = parser.parse_args()
    request = VisualGenerationRunRequest(
        series_id=args.series_id,
        story_id=args.story_id,
        thread_id=args.thread_id,
        include_types=tuple(item.strip().lower() for item in args.include_types.split(",") if item.strip()),
        max_renders_per_type=args.max_renders_per_type,
        max_attempts=args.max_attempts,
    )
    service = VisualGenerationService.from_env()
    if args.audit_existing and args.retry_existing:
        parser.error("--audit-existing and --retry-existing are mutually exclusive")
    if args.audit_existing:
        result = service.reaudit(request)
    elif args.retry_existing:
        result = service.retry_rejected(request)
    else:
        result = service.run(request)
    audit = service.build_quality_audit(result)
    report = service.persist_runtime_report(request=request, result=result, quality_audit=audit)
    payload = {"quality_audit": audit, "report": report, "result": result.model_dump()}
    if args.output_json:
        target = Path(args.output_json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"quality_audit": audit, "report": report}, ensure_ascii=False, indent=2))
    return 0 if result.decision.accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
