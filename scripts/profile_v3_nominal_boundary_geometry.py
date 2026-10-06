"""Profile how LitBank person-nominal spans differ from nearest spaCy noun chunks."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import time

from packages.narrative_compiler.litbank import LITBANK_COMMIT, convert_litbank_tsv_document


WORD_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")


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


def relation(gold_start: int, gold_end: int, chunk_start: int, chunk_end: int) -> str:
    if gold_start == chunk_start and gold_end == chunk_end:
        return "exact"
    if gold_start <= chunk_start and gold_end >= chunk_end:
        return "gold_contains_chunk"
    if chunk_start <= gold_start and chunk_end >= gold_end:
        return "chunk_contains_gold"
    if gold_start < chunk_end and gold_end > chunk_start:
        return "partial_overlap"
    return "no_overlap"


def overlap_chars(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    return max(0, min(a_end, b_end) - max(a_start, b_start))


def token_span(doc, start: int, end: int):
    span = doc.char_span(start, end, alignment_mode="strict")
    if span is not None:
        return span.start, span.end
    span = doc.char_span(start, end, alignment_mode="contract")
    if span is not None:
        return span.start, span.end
    return None


def clamp_delta(value: int) -> str:
    if value <= -6:
        return "<=-6"
    if value >= 6:
        return ">=6"
    return str(value)


def main() -> None:
    args = parse_args()
    import spacy

    nlp = spacy.load(args.model, disable=["ner"])
    documents = load_documents(args.root, args.limit)

    relation_counts: Counter[str] = Counter()
    delta_pair_counts: Counter[str] = Counter()
    start_delta_counts: Counter[str] = Counter()
    end_delta_counts: Counter[str] = Counter()
    small_shift_coverage: Counter[str] = Counter()
    gold_total = 0
    exact_total = 0
    token_aligned_misses = 0

    started = time.perf_counter()
    for document in documents:
        parsed = nlp(document.source.normalized_text)
        chunks = list(parsed.noun_chunks)
        chunk_char_spans = [(chunk.start_char, chunk.end_char, chunk) for chunk in chunks]

        gold_nominals = [
            mention
            for mention in document.gold.mentions
            if mention.entity_type == "person" and mention.mention_kind == "nominal"
        ]
        gold_total += len(gold_nominals)

        for mention in gold_nominals:
            gs, ge = mention.start_offset, mention.end_offset
            exact_chunk = next(
                (chunk for cs, ce, chunk in chunk_char_spans if cs == gs and ce == ge),
                None,
            )
            if exact_chunk is not None:
                exact_total += 1
                relation_counts["exact"] += 1
                continue

            if not chunk_char_spans:
                relation_counts["no_chunk"] += 1
                continue

            best_cs, best_ce, best_chunk = max(
                chunk_char_spans,
                key=lambda item: (
                    overlap_chars(gs, ge, item[0], item[1]),
                    -abs(item[0] - gs) - abs(item[1] - ge),
                    -abs((item[1] - item[0]) - (ge - gs)),
                ),
            )
            rel = relation(gs, ge, best_cs, best_ce)
            relation_counts[rel] += 1

            gold_tokens = token_span(parsed, gs, ge)
            if gold_tokens is None:
                relation_counts["gold_not_token_aligned"] += 1
                continue
            token_aligned_misses += 1
            gstart, gend = gold_tokens
            start_delta = gstart - best_chunk.start
            end_delta = gend - best_chunk.end
            start_delta_counts[clamp_delta(start_delta)] += 1
            end_delta_counts[clamp_delta(end_delta)] += 1
            delta_pair_counts[f"{clamp_delta(start_delta)},{clamp_delta(end_delta)}"] += 1

            for radius in (1, 2, 3, 4, 5):
                if abs(start_delta) <= radius and abs(end_delta) <= radius:
                    small_shift_coverage[str(radius)] += 1

    missed = gold_total - exact_total
    report = {
        "schemaVersion": "saga-v3-nominal-boundary-geometry-v1",
        "dataset": {
            "repository": "dbamman/litbank",
            "commit": LITBANK_COMMIT,
            "annotationLayer": "coref/tsv",
            "documentCount": len(documents),
            "license": "CC BY 4.0",
        },
        "provider": {
            "spacyVersion": spacy.__version__,
            "model": args.model,
            "modelVersion": nlp.meta.get("version"),
        },
        "counts": {
            "goldPersonNominals": gold_total,
            "exactNounChunkMatches": exact_total,
            "exactNounChunkMisses": missed,
            "tokenAlignedMisses": token_aligned_misses,
        },
        "relationToNearestChunk": dict(relation_counts.most_common()),
        "startTokenDelta": dict(start_delta_counts.most_common()),
        "endTokenDelta": dict(end_delta_counts.most_common()),
        "topDeltaPairs": delta_pair_counts.most_common(30),
        "boundedShiftCoverageAmongTokenAlignedMisses": {
            radius: {
                "count": small_shift_coverage[radius],
                "rate": 0.0
                if token_aligned_misses == 0
                else small_shift_coverage[radius] / token_aligned_misses,
            }
            for radius in ("1", "2", "3", "4", "5")
        },
        "runtimeSeconds": time.perf_counter() - started,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
