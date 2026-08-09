from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packages.narrative_generation import NarrativeSupportRunRequest, NarrativeSupportService


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit persisted generated prose against retrieved canon evidence.")
    parser.add_argument("--series-id", required=True)
    parser.add_argument("--story-id", required=True)
    parser.add_argument("--thread-id", default="narrative-support")
    parser.add_argument("--output-json", default="")
    parser.add_argument("--print-full-result", action="store_true")
    args = parser.parse_args()
    request = NarrativeSupportRunRequest(series_id=args.series_id, story_id=args.story_id, thread_id=args.thread_id)
    service = NarrativeSupportService.from_env()
    result = service.run(request)
    quality = service.build_quality_audit(result=result)
    report = service.persist_runtime_report(request=request, result=result, quality_audit=quality)
    payload = {
        "series_id": result.series_id,
        "story_id": result.story.story_id,
        "accepted": result.decision.accepted,
        "quality_audit": quality,
        "report": report,
        "result": result.model_dump(),
    }
    if args.output_json:
        output = Path(args.output_json)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    printed = payload if args.print_full_result else {
        "series_id": result.series_id,
        "story_id": result.story.story_id,
        "accepted": result.decision.accepted,
        "decision": result.decision.model_dump(),
        "scene_audits": quality["scene_audits"],
        "provider_proof": quality["provider_proof"],
        "run_metadata": result.run_metadata,
        "report": report,
        "output_json": str(args.output_json or ""),
    }
    print(json.dumps(printed, ensure_ascii=False, indent=2))
    return 0 if result.decision.accepted else 2


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    raise SystemExit(main())
