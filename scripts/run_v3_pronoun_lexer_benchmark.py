"""Benchmark deterministic English character-pronoun profiles on LitBank."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time

from packages.narrative_compiler.adapters.pronouns import EnglishCharacterPronounLexer
from packages.narrative_compiler.lexer_benchmark import (
    aggregate_character_mention_reports,
    evaluate_character_mentions,
)
from packages.narrative_compiler.litbank import LITBANK_COMMIT, convert_litbank_tsv_document


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--profiles", default="strict,plus_plural,plus_neuter")
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100")
    profiles = tuple(value.strip() for value in args.profiles.split(",") if value.strip())
    if not profiles:
        parser.error("--profiles must contain at least one profile")
    args.profiles = tuple(dict.fromkeys(profiles))
    return args


def load_documents(root: Path, limit: int):
    annotation_dir = root.resolve() / "coref" / "tsv"
    paths = sorted(annotation_dir.glob("*.ann"))[:limit]
    if not paths:
        raise RuntimeError("no LitBank coref/tsv annotations found")
    return [
        convert_litbank_tsv_document(
            document_id=path.stem,
            annotation=path.read_text(encoding="utf-8"),
            text=(annotation_dir / f"{path.stem}.txt").read_text(encoding="utf-8"),
        )
        for path in paths
    ]


def main() -> None:
    args = parse_args()
    documents = load_documents(args.root, args.limit)
    results = []
    for profile in args.profiles:
        lexer = EnglishCharacterPronounLexer(profile=profile)
        reports = []
        started = time.perf_counter()
        for document in documents:
            result = lexer.analyze(document.source)
            reports.append(evaluate_character_mentions(gold=document.gold, mentions=result.mentions))
        elapsed = time.perf_counter() - started
        aggregate = aggregate_character_mention_reports(reports)
        results.append(
            {
                "profile": profile,
                "runtimeSeconds": elapsed,
                "counts": asdict(aggregate.counts),
                "metrics": asdict(aggregate.metrics),
            }
        )

    output = {
        "schemaVersion": "saga-v3-pronoun-lexer-benchmark-v1",
        "benchmark": "deterministic English character-pronoun mention detection",
        "dataset": {
            "repository": "dbamman/litbank",
            "commit": LITBANK_COMMIT,
            "annotationLayer": "coref/tsv",
            "license": "CC BY 4.0",
            "documentCount": len(documents),
        },
        "results": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "results": [
                    {
                        "profile": row["profile"],
                        "precision": row["metrics"]["precision"],
                        "pronounRecall": row["metrics"]["pronoun_recall"],
                        "predicted": row["counts"]["predicted_character_mentions"],
                        "pronounGold": row["counts"]["pronoun_gold"],
                        "pronounTruePositive": row["counts"]["pronoun_true_positive"],
                        "runtimeSeconds": row["runtimeSeconds"],
                    }
                    for row in results
                ]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
