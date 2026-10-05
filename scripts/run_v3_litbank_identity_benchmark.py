"""Run the Phase V3.0 public LitBank identity benchmark.

Examples:
  python -m scripts.run_v3_litbank_identity_benchmark \
    --root ./third_party/litbank --out ./artifacts/v3-oracle-exact.json \
    --mode oracle-exact

  python -m scripts.run_v3_litbank_identity_benchmark \
    --root ./third_party/litbank --out ./artifacts/v3-gliner25-exact.json \
    --mode gliner25-exact --device cuda
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time

from packages.narrative_compiler.adapters.gliner2 import GLiNER25SemanticLexer
from packages.narrative_compiler.adapters.static import StaticSemanticLexer
from packages.narrative_compiler.benchmark import aggregate_identity_benchmarks, evaluate_identity_benchmark
from packages.narrative_compiler.compiler import NarrativeCompilerV30
from packages.narrative_compiler.linker import ExactSurfaceCharacterLinker
from packages.narrative_compiler.litbank import LITBANK_COMMIT, convert_litbank_tsv_document, oracle_person_mentions
from packages.narrative_compiler.model_manifest import GLINER25_BASE_V1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--mode", choices=("oracle-exact", "gliner25-exact"), default="oracle-exact")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be > 0")
    return args


def main() -> None:
    args = parse_args()
    annotation_dir = args.root.resolve() / "coref" / "tsv"
    annotation_paths = sorted(annotation_dir.glob("*.ann"))
    if args.limit is not None:
        annotation_paths = annotation_paths[: args.limit]
    if not annotation_paths:
        raise SystemExit(f"no LitBank coref/tsv annotations found under {annotation_dir}")

    shared_lexer = None
    if args.mode == "gliner25-exact":
        shared_lexer = GLiNER25SemanticLexer(device=args.device, threshold=args.threshold)

    per_document = []
    reports = []
    total_started = time.perf_counter()

    for annotation_path in annotation_paths:
        document_id = annotation_path.stem
        text_path = annotation_dir / f"{document_id}.txt"
        document = convert_litbank_tsv_document(
            document_id=document_id,
            annotation=annotation_path.read_text(encoding="utf-8"),
            text=text_path.read_text(encoding="utf-8"),
        )
        lexer = shared_lexer or StaticSemanticLexer(oracle_person_mentions(document))
        compiler = NarrativeCompilerV30(lexer=lexer, linker=ExactSurfaceCharacterLinker())
        started = time.perf_counter()
        compilation = compiler.compile_identity(document.source)
        elapsed = time.perf_counter() - started
        report = evaluate_identity_benchmark(
            gold=document.gold,
            mentions=compilation.lexer.mentions,
            entities=compilation.linker.entities,
            unresolved_mention_ids=compilation.linker.unresolved_mention_ids,
        )
        reports.append(report)
        per_document.append(
            {
                "documentId": document_id,
                "runtimeSeconds": elapsed,
                "sourceFingerprint": document.source.source_fingerprint,
                "lexerArtifactFingerprint": compilation.lexer.run.artifact_fingerprint,
                "linkerArtifactFingerprint": compilation.linker.run.artifact_fingerprint,
                "counts": asdict(report.counts),
                "metrics": asdict(report.metrics),
            }
        )

    aggregate = aggregate_identity_benchmarks(reports)
    model = None
    if args.mode == "gliner25-exact":
        model = asdict(GLINER25_BASE_V1)

    output = {
        "schemaVersion": "saga-v3-identity-benchmark-v1",
        "benchmark": "LitBank V3.0 identity challenger",
        "mode": args.mode,
        "dataset": {
            "repository": "dbamman/litbank",
            "commit": LITBANK_COMMIT,
            "license": "CC BY 4.0",
            "annotationLayer": "coref/tsv",
            "documentCount": len(per_document),
        },
        "model": model,
        "settings": {
            "device": args.device,
            "threshold": args.threshold if args.mode == "gliner25-exact" else None,
        },
        "runtimeSeconds": time.perf_counter() - total_started,
        "aggregate": {
            "counts": asdict(aggregate.counts),
            "metrics": asdict(aggregate.metrics),
        },
        "perDocument": per_document,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output["aggregate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
