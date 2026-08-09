from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from packages.canon_extraction import CanonExtractionRunRequest, CanonExtractionService


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the active canon extraction slice.")
    parser.add_argument("--series-id", required=True)
    parser.add_argument("--thread-id", default="canon-extraction")
    parser.add_argument("--run-analysis-foundation", action="store_true")
    parser.add_argument("--source", action="append", dest="sources", default=[])
    parser.add_argument("--source-file", default="")
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()

    source_paths = [str(Path(value).resolve()) for value in list(args.sources or []) if str(value or "").strip()]
    if str(args.source_file or "").strip():
        source_paths.extend(
            str(Path(line.strip()).resolve())
            for line in Path(args.source_file).read_text(encoding="utf-8").splitlines()
            if str(line or "").strip()
        )

    service = CanonExtractionService.from_env()
    request = CanonExtractionRunRequest(
        series_id=str(args.series_id or "").strip(),
        thread_id=str(args.thread_id or "").strip() or "canon-extraction",
        source_paths=source_paths,
        run_analysis_foundation=bool(args.run_analysis_foundation),
    )
    result = service.run(request)
    quality_audit = service.build_quality_audit(result=result)
    report_artifact = service.persist_runtime_report(request=request, result=result, quality_audit=quality_audit)
    payload = {
        "request": {
            "series_id": request.series_id,
            "thread_id": request.thread_id,
            "run_analysis_foundation": request.run_analysis_foundation,
            "source_paths": request.source_paths or [],
        },
        "result": result.model_dump(),
        "quality_audit": quality_audit,
        "report_artifact": {
            "bucket_name": report_artifact["bucket_name"],
            "object_path": report_artifact["object_path"],
            "record_id": report_artifact["record_id"],
        },
    }
    if str(args.output_json or "").strip():
        output_path = Path(args.output_json).resolve()
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
