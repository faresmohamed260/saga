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
from packages.narrative_compiler.stages import IdentityRankingPolicy


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
    parser.add_argument("--ettin-context-chars", type=int, default=360)
    parser.add_argument("--ettin-entity-contexts", type=int, default=3)
    parser.add_argument("--ettin-batch-size", type=int, default=16)
    parser.add_argument(
        "--ettin-mention-kinds",
        default="all",
        help="`all` or comma-separated mention kinds that may invoke Ettin (for example `pronoun`).",
    )
    return parser.parse_args()


def _parse_mention_kinds(raw: str) -> frozenset[str] | None:
    value = raw.strip()
    if value.casefold() == "all":
        return None
    kinds = frozenset(item.strip() for item in value.split(",") if item.strip())
    if not kinds:
        raise ValueError("--ettin-mention-kinds must be `all` or a non-empty comma-separated list")
    return kinds


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
    if args.ettin_context_chars < 32:
        raise ValueError("--ettin-context-chars must be >= 32")
    if args.ettin_entity_contexts < 1:
        raise ValueError("--ettin-entity-contexts must be >= 1")
    if args.ettin_batch_size < 1:
        raise ValueError("--ettin-batch-size must be >= 1")
    routed_kinds = _parse_mention_kinds(args.ettin_mention_kinds)

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
    scorer_config = None
    model_record = None
    if args.scorer == "ettin":
        artifact = download_and_digest_model(
            model_id=ETTIN_RERANKER_68M_V1.model_id,
            revision=ETTIN_RERANKER_68M_V1.revision,
            cache_dir=args.model_cache,
        )
        scorer_config = {
            "contextChars": args.ettin_context_chars,
            "entityContexts": args.ettin_entity_contexts,
            "batchSize": args.ettin_batch_size,
        }
        scorer = EttinRerankerIdentityScorer(
            model_path=artifact.snapshot_path,
            device=args.device,
            context_chars=args.ettin_context_chars,
            entity_contexts=args.ettin_entity_contexts,
            batch_size=args.ettin_batch_size,
        )
        model_record = {
            "modelId": ETTIN_RERANKER_68M_V1.model_id,
            "revision": ETTIN_RERANKER_68M_V1.revision,
            "license": ETTIN_RERANKER_68M_V1.license_id,
            "artifact": asdict(artifact),
        }

    ranking_policy = IdentityRankingPolicy(
        scored_mention_kinds=(frozenset() if scorer is None else routed_kinds)
    )
    policy_record = {
        "fallback": "candidate-order",
        "scoredMentionKinds": "all" if ranking_policy.scored_mention_kinds is None else sorted(ranking_policy.scored_mention_kinds),
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
                ranking_policy=ranking_policy,
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
        "schemaVersion": "saga-v3-identity-ranking-v2",
        "benchmark": "LitBank oracle-history candidate retrieval and reranking",
        "benchmarkPurpose": (
            "Measure candidate retrieval, learned scorer ordering, and mention-kind-routed final ordering with "
            "oracle-correct prior clusters; does not evaluate canonical merge thresholds."
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
        "scorerConfig": scorer_config,
        "rankingPolicy": policy_record,
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
