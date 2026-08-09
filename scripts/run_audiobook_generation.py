from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packages.audiobook_generation import AudiobookGenerationRunRequest, AudiobookGenerationService


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and quality-gate an audiobook for an accepted story.")
    parser.add_argument("--series-id", required=True)
    parser.add_argument("--story-id", required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--thread-id", default="")
    parser.add_argument("--narrator-voice", default="af_bella")
    parser.add_argument("--max-chapters", type=int, default=0)
    parser.add_argument("--max-segment-chars", type=int, default=1800)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--output-json", default="")
    parser.add_argument("--retry-existing", action="store_true")
    args = parser.parse_args()
    request = AudiobookGenerationRunRequest(
        series_id=args.series_id,
        story_id=args.story_id,
        run_id=args.run_id,
        thread_id=args.thread_id,
        narrator_voice=args.narrator_voice,
        max_chapters=args.max_chapters,
        max_segment_chars=args.max_segment_chars,
        max_attempts=args.max_attempts,
    )
    service = AudiobookGenerationService.from_env()
    result = service.retry_rejected(request) if args.retry_existing else service.run(request)
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
