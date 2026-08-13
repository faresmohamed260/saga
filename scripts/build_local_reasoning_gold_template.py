"""Create a source-safe gold-annotation template for extraction qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.reasoning.task_suite import build_tasks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default="analysis_outputs/local_reasoning/corpus_v1.json")
    parser.add_argument("--output", default="analysis_outputs/local_reasoning/gold_v1.json")
    args = parser.parse_args()

    corpus_path = Path(args.corpus).resolve()
    corpus_bytes = corpus_path.read_bytes()
    corpus = json.loads(corpus_bytes)
    extraction_tasks = [
        task for task in build_tasks(corpus, scope="full")
        if task.metadata.get("family") in {
            "canon_events", "canon_entities", "canon_relationships",
        }
    ]
    payload = {
        "version": "1.0.0",
        "corpus_version": corpus["corpus_version"],
        "corpus_sha256": hashlib.sha256(corpus_bytes).hexdigest(),
        "annotation_policy": {
            "canon_events": "normalized source spans",
            "canon_entities": "canonical aliases",
            "canon_relationships": "source, target, and type aliases",
            "minimum_annotators": 1,
            "review_required": True,
        },
        "annotations": [{
            "family": task.metadata["family"],
            "case_id": task.metadata["case_id"],
            "source_id": task.metadata["source_id"],
            "items": [],
            "review_status": "pending",
        } for task in extraction_tasks],
    }
    target = Path(args.output).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"annotations": len(payload["annotations"]), "output": str(target)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
