"""Measure spaCy noun-chunk boundary coverage for LitBank person nominals."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import time

from packages.narrative_compiler.litbank import LITBANK_COMMIT, convert_litbank_tsv_document


WORD_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")
POSSESSIVES = frozenset({"my", "your", "his", "her", "our", "their", "its"})
DETERMINERS = frozenset({"the", "a", "an", "this", "that", "these", "those"})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--model", default="en_core_web_sm")
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100")
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


def length_bucket(surface: str) -> str:
    count = len(WORD_RE.findall(surface))
    if count <= 1:
        return "1"
    if count == 2:
        return "2"
    if count == 3:
        return "3"
    return "4+"


def start_bucket(surface: str) -> str:
    tokens = WORD_RE.findall(surface)
    if not tokens:
        return "other"
    first = tokens[0].casefold()
    if first in POSSESSIVES:
        return "possessive"
    if first in DETERMINERS:
        return "determiner"
    return "other"


def main() -> None:
    args = parse_args()
    import spacy

    nlp = spacy.load(args.model, disable=["ner"])
    documents = load_documents(args.root, args.limit)

    gold_total = 0
    exact_tp = 0
    candidate_total = 0
    overlap_gold = 0
    contained_gold = 0
    length_gold: Counter[str] = Counter()
    length_exact: Counter[str] = Counter()
    start_gold: Counter[str] = Counter()
    start_exact: Counter[str] = Counter()

    started = time.perf_counter()
    for document in documents:
        source_text = document.source.normalized_text
        doc = nlp(source_text)
        chunk_spans = {(chunk.start_char, chunk.end_char) for chunk in doc.noun_chunks}
        candidate_total += len(chunk_spans)

        gold_nominals = [
            mention
            for mention in document.gold.mentions
            if mention.entity_type == "person" and mention.mention_kind == "nominal"
        ]
        gold_total += len(gold_nominals)

        for mention in gold_nominals:
            gold_span = (mention.start_offset, mention.end_offset)
            lb = length_bucket(mention.surface_text)
            sb = start_bucket(mention.surface_text)
            length_gold[lb] += 1
            start_gold[sb] += 1

            if gold_span in chunk_spans:
                exact_tp += 1
                length_exact[lb] += 1
                start_exact[sb] += 1

            if any(start < mention.end_offset and end > mention.start_offset for start, end in chunk_spans):
                overlap_gold += 1
            if any(start <= mention.start_offset and end >= mention.end_offset for start, end in chunk_spans):
                contained_gold += 1

    elapsed = time.perf_counter() - started

    report = {
        "schemaVersion": "saga-v3-spacy-nominal-boundary-v1",
        "dataset": {
            "repository": "dbamman/litbank",
            "commit": LITBANK_COMMIT,
            "annotationLayer": "coref/tsv",
            "documentCount": len(documents),
            "license": "CC BY 4.0",
        },
        "provider": {
            "library": "spacy",
            "libraryVersion": spacy.__version__,
            "model": args.model,
            "modelVersion": nlp.meta.get("version"),
            "pipeline": nlp.pipe_names,
        },
        "counts": {
            "goldPersonNominals": gold_total,
            "nounChunkCandidates": candidate_total,
            "exactMatches": exact_tp,
            "goldWithAnyOverlap": overlap_gold,
            "goldContainedByChunk": contained_gold,
        },
        "metrics": {
            "exactBoundaryRecall": ratio(exact_tp, gold_total),
            "overlapCoverage": ratio(overlap_gold, gold_total),
            "containmentCoverage": ratio(contained_gold, gold_total),
        },
        "exactRecallByLength": {
            key: {
                "gold": length_gold[key],
                "exact": length_exact[key],
                "recall": ratio(length_exact[key], length_gold[key]),
            }
            for key in ("1", "2", "3", "4+")
        },
        "exactRecallByStart": {
            key: {
                "gold": start_gold[key],
                "exact": start_exact[key],
                "recall": ratio(start_exact[key], start_gold[key]),
            }
            for key in ("determiner", "possessive", "other")
        },
        "runtimeSeconds": elapsed,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
