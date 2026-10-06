"""Run a direct GLiNER2.5 character-mention threshold sweep on LitBank.

The exact pinned model is loaded once. Each threshold performs a real extraction
pass so threshold-sensitive decoding behavior is measured rather than assumed to
be equivalent to post-hoc confidence filtering.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time

from packages.narrative_compiler.adapters.gliner2 import GLiNER25SemanticLexer
from packages.narrative_compiler.ir import EntityType
from packages.narrative_compiler.lexer_benchmark import (
    aggregate_character_mention_reports,
    evaluate_character_mentions,
)
from packages.narrative_compiler.litbank import LITBANK_COMMIT, convert_litbank_tsv_document
from packages.narrative_compiler.model_manifest import GLINER25_BASE_V1
from packages.narrative_compiler.qualification import (
    ResourceMonitor,
    download_and_digest_model,
    runtime_environment,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--thresholds", default="0.3,0.5,0.65,0.75,0.85")
    parser.add_argument(
        "--character-labels",
        default="person",
        help="Comma-separated GLiNER labels that all map to CHARACTER for this calibration.",
    )
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--model-cache", type=Path, default=Path(".cache/huggingface"))
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100")
    try:
        thresholds = tuple(float(value.strip()) for value in args.thresholds.split(",") if value.strip())
    except ValueError as exc:
        parser.error(f"invalid --thresholds: {exc}")
    if not thresholds or any(not 0.0 <= value <= 1.0 for value in thresholds):
        parser.error("thresholds must be non-empty values between 0 and 1")
    labels = tuple(value.strip() for value in args.character_labels.split(",") if value.strip())
    if not labels:
        parser.error("--character-labels must contain at least one non-empty label")
    args.thresholds = tuple(dict.fromkeys(thresholds))
    args.character_labels = tuple(dict.fromkeys(labels))
    return args


def load_documents(root: Path, limit: int):
    annotation_dir = root.resolve() / "coref" / "tsv"
    paths = sorted(annotation_dir.glob("*.ann"))[:limit]
    if not paths:
        raise RuntimeError("no LitBank coref/tsv annotations found")
    result = []
    for annotation_path in paths:
        document_id = annotation_path.stem
        result.append(
            convert_litbank_tsv_document(
                document_id=document_id,
                annotation=annotation_path.read_text(encoding="utf-8"),
                text=(annotation_dir / f"{document_id}.txt").read_text(encoding="utf-8"),
            )
        )
    return result


def main() -> None:
    args = parse_args()
    documents = load_documents(args.root, args.limit)
    artifact = download_and_digest_model(
        model_id=GLINER25_BASE_V1.model_id,
        revision=GLINER25_BASE_V1.revision,
        cache_dir=args.model_cache,
        local_files_only=args.offline,
    )
    labels = {label: EntityType.CHARACTER for label in args.character_labels}

    loader = GLiNER25SemanticLexer(
        model_path=artifact.snapshot_path,
        device=args.device,
        threshold=args.thresholds[0],
        labels=labels,
    )
    shared_model = loader._load_model()  # qualification-only explicit model reuse

    results = []
    with ResourceMonitor() as resources:
        for threshold in args.thresholds:
            lexer = GLiNER25SemanticLexer(
                model_path=artifact.snapshot_path,
                device=args.device,
                threshold=threshold,
                labels=labels,
                model=shared_model,
            )
            reports = []
            per_document = []
            started = time.perf_counter()
            for document in documents:
                lexer_result = lexer.analyze(document.source)
                report = evaluate_character_mentions(gold=document.gold, mentions=lexer_result.mentions)
                reports.append(report)
                per_document.append(
                    {
                        "documentId": document.gold.document_id,
                        "counts": asdict(report.counts),
                        "metrics": asdict(report.metrics),
                    }
                )
            elapsed = time.perf_counter() - started
            aggregate = aggregate_character_mention_reports(reports)
            results.append(
                {
                    "threshold": threshold,
                    "runtimeSeconds": elapsed,
                    "aggregate": {
                        "counts": asdict(aggregate.counts),
                        "metrics": asdict(aggregate.metrics),
                    },
                    "perDocument": per_document,
                }
            )

    output = {
        "schemaVersion": "saga-v3-gliner-threshold-sweep-v1",
        "benchmark": "GLiNER2.5 direct character-mention threshold sweep",
        "benchmarkPurpose": "Calibrate semantic-lexer mention precision/coverage independently of identity clustering.",
        "dataset": {
            "repository": "dbamman/litbank",
            "commit": LITBANK_COMMIT,
            "license": "CC BY 4.0",
            "annotationLayer": "coref/tsv",
            "documentCount": len(documents),
        },
        "characterLabels": list(args.character_labels),
        "model": {**asdict(GLINER25_BASE_V1), "artifact": asdict(artifact)},
        "environment": runtime_environment(),
        "resources": resources.as_dict(),
        "results": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "characterLabels": output["characterLabels"],
                "results": [
                    {"threshold": row["threshold"], **row["aggregate"]["metrics"]}
                    for row in results
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
