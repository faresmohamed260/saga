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


def ratio(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def main() -> None:
    args = parse_args()
    documents = load_documents(args.root, args.limit)
    results = []
    for profile in args.profiles:
        lexer = EnglishCharacterPronounLexer(profile=profile)
        reports = []
        pronoun_predicted = 0
        pronoun_gold = 0
        pronoun_true_positive = 0
        started = time.perf_counter()
        for document in documents:
            result = lexer.analyze(document.source)
            reports.append(evaluate_character_mentions(gold=document.gold, mentions=result.mentions))

            predicted_spans = {
                (mention.evidence.span.start_offset, mention.evidence.span.end_offset)
                for mention in result.mentions
            }
            gold_pronoun_spans = {
                (mention.start_offset, mention.end_offset)
                for mention in document.gold.mentions
                if mention.entity_type == "person" and mention.mention_kind == "pronoun"
            }
            pronoun_predicted += len(predicted_spans)
            pronoun_gold += len(gold_pronoun_spans)
            pronoun_true_positive += len(predicted_spans & gold_pronoun_spans)

        elapsed = time.perf_counter() - started
        aggregate = aggregate_character_mention_reports(reports)
        direct_precision = ratio(pronoun_true_positive, pronoun_predicted)
        direct_recall = ratio(pronoun_true_positive, pronoun_gold)
        direct_f1 = (
            0.0
            if direct_precision + direct_recall == 0
            else 2.0 * direct_precision * direct_recall / (direct_precision + direct_recall)
        )
        results.append(
            {
                "profile": profile,
                "runtimeSeconds": elapsed,
                "counts": asdict(aggregate.counts),
                "metrics": asdict(aggregate.metrics),
                "pronounExact": {
                    "predicted": pronoun_predicted,
                    "gold": pronoun_gold,
                    "truePositive": pronoun_true_positive,
                    "precision": direct_precision,
                    "recall": direct_recall,
                    "f1": direct_f1,
                },
            }
        )

    output = {
        "schemaVersion": "saga-v3-pronoun-lexer-benchmark-v2",
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
                        "pronounPrecision": row["pronounExact"]["precision"],
                        "pronounRecall": row["pronounExact"]["recall"],
                        "pronounF1": row["pronounExact"]["f1"],
                        "predicted": row["pronounExact"]["predicted"],
                        "pronounGold": row["pronounExact"]["gold"],
                        "pronounTruePositive": row["pronounExact"]["truePositive"],
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
