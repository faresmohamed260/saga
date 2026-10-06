"""Run the V3 oracle-history identity retrieval/reranking benchmark on LitBank."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from packages.narrative_compiler.adapters.ettin import EttinRerankerIdentityScorer
from packages.narrative_compiler.candidates import (
    HybridIdentityCandidateGenerator,
    LexicalIdentityCandidateGenerator,
)
from packages.narrative_compiler.litbank import LITBANK_COMMIT, convert_litbank_tsv_document
from packages.narrative_compiler.model_manifest import ETTIN_RERANKER_68M_V1
from packages.narrative_compiler.qualification import (
    ResourceMonitor,
    download_and_digest_model,
    runtime_environment,
)
from packages.narrative_compiler.ranking import (
    aggregate_identity_ranking_reports,
    evaluate_oracle_history_ranking,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--candidate-mode", choices=("lexical", "hybrid"), default="hybrid")
    parser.add_argument("--scorer", choices=("none", "ettin"), default="none")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--lexical-k", type=int, default=4)
    parser.add_argument("--recent-k", type=int, default=4)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--model-cache", type=Path, default=Path(".cache/huggingface"))
    return parser.parse_args()


def load_documents(root: Path, limit: int):
    annotation_dir = root / "coref" / "tsv"
    names = sorted(annotation_dir.glob("*.ann"))[:limit]
    if not names:
        raise RuntimeError("no LitBank coref/tsv annotations found")
    documents = []
    for annotation_path in names:
        document_id = annotation_path.stem
        documents.append(
            convert_litbank_tsv_document(
                document_id=document_id,
                annotation=annotation_path.read_text(encoding="utf-8"),
                text=(annotation_dir / f"{document_id}.txt").read_text(encoding="utf-8"),
            )
        )
    return documents


def main() -> None:
    args = parse_args()
    if not 1 <= args.limit <= 100:
        raise ValueError("--limit must be between 1 and 100")
    if args.top_k < 1:
        raise ValueError("--top-k must be >= 1")

    documents = load_documents(args.root, args.limit)
    if args.candidate_mode == "lexical":
        candidate_generator = LexicalIdentityCandidateGenerator(top_k=args.top_k)
        candidate_config = {"mode": "lexical", "topK": args.top_k}
    else:
        candidate_generator = HybridIdentityCandidateGenerator(
            top_k=args.top_k,
            lexical_k=args.lexical_k,
            recent_k=args.recent_k,
        )
        candidate_config = {
            "mode": "hybrid",
            "topK": args.top_k,
            "lexicalK": args.lexical_k,
            "recentK": args.recent_k,
        }

    scorer = None
    model_record = None
    if args.scorer == "ettin":
        artifact = download_and_digest_model(
            model_id=ETTIN_RERANKER_68M_V1.model_id,
            revision=ETTIN_RERANKER_68M_V1.revision,
            cache_dir=args.model_cache,
        )
        scorer = EttinRerankerIdentityScorer(
            model_path=artifact.snapshot_path,
            device=args.device,
        )
        model_record = {
            "modelId": ETTIN_RERANKER_68M_V1.model_id,
            "revision": ETTIN_RERANKER_68M_V1.revision,
            "license": ETTIN_RERANKER_68M_V1.license_id,
            "artifact": asdict(artifact),
        }

    per_document = []
    reports = []
    with ResourceMonitor() as monitor:
        for document in documents:
            report = evaluate_oracle_history_ranking(
                source=document.source,
                gold=document.gold,
                candidate_generator=candidate_generator,
                scorer=scorer,
            )
            reports.append(report)
            per_document.append(
                {
                    "documentId": document.gold.document_id,
                    "report": asdict(report),
                }
            )
    aggregate = aggregate_identity_ranking_reports(reports)

    output = {
        "schemaVersion": "saga-v3-identity-ranking-v1",
        "benchmark": "LitBank oracle-history candidate retrieval and reranking",
        "benchmarkPurpose": (
            "Measure candidate retrieval and optional reranker ordering with oracle-correct prior clusters; "
            "does not evaluate canonical merge thresholds."
        ),
        "dataset": {
            "repository": "dbamman/litbank",
            "commit": LITBANK_COMMIT,
            "license": "CC BY 4.0",
            "annotationLayer": "coref/tsv",
            "documentCount": len(documents),
        },
        "candidateGenerator": candidate_config,
        "scorer": args.scorer,
        "model": model_record,
        "environment": runtime_environment(),
        "resources": monitor.as_dict(),
        "aggregate": asdict(aggregate),
        "perDocument": per_document,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"aggregate": output["aggregate"], "resources": output["resources"]}, indent=2))


if __name__ == "__main__":
    main()
