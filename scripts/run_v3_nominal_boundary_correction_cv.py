"""Book-held-out noun-chunk boundary-correction candidate benchmark."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import time

from packages.narrative_compiler.litbank import LITBANK_COMMIT, convert_litbank_tsv_document


TOP_KS = (4, 8, 16, 32)


@dataclass(frozen=True)
class ParsedDocument:
    name: str
    parsed: object
    gold_spans: frozenset[tuple[int, int]]
    gold_token_spans: tuple[tuple[int, int, int, int], ...]
    chunks: tuple[object, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--model", default="en_core_web_sm")
    parser.add_argument("--folds", type=int, default=5)
    args = parser.parse_args()
    if not 5 <= args.limit <= 100:
        parser.error("--limit must be between 5 and 100")
    if not 2 <= args.folds <= min(10, args.limit):
        parser.error("--folds must be between 2 and min(10, limit)")
    return args


def load_documents(root: Path, limit: int):
    annotation_dir = root.resolve() / "coref" / "tsv"
    paths = sorted(annotation_dir.glob("*.ann"))[:limit]
    if not paths:
        raise RuntimeError("no LitBank coref/tsv annotations found")
    return [
        (
            path.stem,
            convert_litbank_tsv_document(
                document_id=path.stem,
                annotation=path.read_text(encoding="utf-8"),
                text=(annotation_dir / f"{path.stem}.txt").read_text(encoding="utf-8"),
            ),
        )
        for path in paths
    ]


def ratio(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def overlap_chars(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    return max(0, min(a_end, b_end) - max(a_start, b_start))


def char_span(doc, start: int, end: int) -> tuple[int, int]:
    return doc[start].idx, doc[end - 1].idx + len(doc[end - 1])


def nearest_overlapping_chunk(doc, gold_start: int, gold_end: int, chunks):
    candidates = []
    for chunk in chunks:
        overlap = overlap_chars(gold_start, gold_end, chunk.start_char, chunk.end_char)
        if overlap <= 0:
            continue
        candidates.append(
            (
                -overlap,
                abs(chunk.start_char - gold_start) + abs(chunk.end_char - gold_end),
                abs((chunk.end_char - chunk.start_char) - (gold_end - gold_start)),
                chunk.start,
                chunk.end,
                chunk,
            )
        )
    return None if not candidates else min(candidates)[-1]


def token_span(doc, start: int, end: int):
    span = doc.char_span(start, end, alignment_mode="strict")
    if span is None:
        span = doc.char_span(start, end, alignment_mode="contract")
    return None if span is None else (span.start, span.end)


def parse_corpus(nlp, raw_documents) -> list[ParsedDocument]:
    output = []
    for name, document in raw_documents:
        parsed = nlp(document.source.normalized_text)
        chunks = tuple(parsed.noun_chunks)
        gold_spans = []
        gold_token_spans = []
        for mention in document.gold.mentions:
            if mention.entity_type != "person" or mention.mention_kind != "nominal":
                continue
            gold_span = (mention.start_offset, mention.end_offset)
            gold_spans.append(gold_span)
            tokens = token_span(parsed, *gold_span)
            if tokens is not None:
                gold_token_spans.append((tokens[0], tokens[1], gold_span[0], gold_span[1]))
        output.append(
            ParsedDocument(
                name=name,
                parsed=parsed,
                gold_spans=frozenset(gold_spans),
                gold_token_spans=tuple(gold_token_spans),
                chunks=chunks,
            )
        )
    return output


def learn_corrections(documents: list[ParsedDocument], train_indices: list[int]) -> Counter[tuple[int, int]]:
    corrections: Counter[tuple[int, int]] = Counter()
    corrections[(0, 0)] = 10**9  # exact noun chunk is always the first candidate.
    for index in train_indices:
        document = documents[index]
        for token_start, token_end, char_start, char_end in document.gold_token_spans:
            chunk = nearest_overlapping_chunk(
                document.parsed,
                char_start,
                char_end,
                document.chunks,
            )
            if chunk is None:
                continue
            delta_start = token_start - chunk.start
            delta_end = token_end - chunk.end
            if chunk.root.i < token_start or chunk.root.i >= token_end:
                continue
            corrections[(delta_start, delta_end)] += 1
    return corrections


def selected_corrections(counter: Counter[tuple[int, int]], top_k: int) -> tuple[tuple[int, int], ...]:
    exact = (0, 0)
    non_exact = [
        pair for pair, _count in counter.most_common() if pair != exact
    ][:top_k]
    return (exact, *non_exact)


def generate_candidates(document: ParsedDocument, corrections: tuple[tuple[int, int], ...]):
    candidates: set[tuple[int, int]] = set()
    for chunk in document.chunks:
        sentence = chunk.root.sent
        for delta_start, delta_end in corrections:
            start = chunk.start + delta_start
            end = chunk.end + delta_end
            if start < sentence.start or end > sentence.end or start >= end:
                continue
            if chunk.root.i < start or chunk.root.i >= end:
                continue
            if document.parsed[start].is_punct or document.parsed[start].is_space:
                continue
            if document.parsed[end - 1].is_punct or document.parsed[end - 1].is_space:
                continue
            candidates.add(char_span(document.parsed, start, end))
    return candidates


def main() -> None:
    args = parse_args()
    import spacy

    nlp = spacy.load(args.model, disable=["ner"])
    raw_documents = load_documents(args.root, args.limit)
    started = time.perf_counter()
    documents = parse_corpus(nlp, raw_documents)

    aggregate: dict[int, dict[str, object]] = {
        top_k: {
            "candidateCount": 0,
            "gold": 0,
            "exactMatches": 0,
            "folds": [],
            "correctionUnion": set(),
        }
        for top_k in TOP_KS
    }

    for fold in range(args.folds):
        train_indices = [i for i in range(len(documents)) if i % args.folds != fold]
        test_indices = [i for i in range(len(documents)) if i % args.folds == fold]
        learned = learn_corrections(documents, train_indices)

        for top_k in TOP_KS:
            corrections = selected_corrections(learned, top_k)
            candidate_count = 0
            gold_count = 0
            exact_matches = 0
            for index in test_indices:
                document = documents[index]
                candidates = generate_candidates(document, corrections)
                candidate_count += len(candidates)
                gold_count += len(document.gold_spans)
                exact_matches += len(candidates & document.gold_spans)

            aggregate[top_k]["candidateCount"] += candidate_count
            aggregate[top_k]["gold"] += gold_count
            aggregate[top_k]["exactMatches"] += exact_matches
            aggregate[top_k]["correctionUnion"].update(corrections)
            aggregate[top_k]["folds"].append(
                {
                    "fold": fold,
                    "trainDocuments": len(train_indices),
                    "testDocuments": len(test_indices),
                    "candidateCount": candidate_count,
                    "gold": gold_count,
                    "exactMatches": exact_matches,
                    "exactRecall": ratio(exact_matches, gold_count),
                    "corrections": [
                        {"startDelta": start, "endDelta": end, "trainCount": learned[(start, end)]}
                        for start, end in corrections
                    ],
                }
            )

    noun_chunk_candidates = sum(len(document.chunks) for document in documents)
    results = []
    for top_k in TOP_KS:
        row = aggregate[top_k]
        candidate_count = int(row["candidateCount"])
        gold = int(row["gold"])
        exact_matches = int(row["exactMatches"])
        results.append(
            {
                "topNonExactCorrections": top_k,
                "candidateCount": candidate_count,
                "candidateMultiplierVsNounChunk": ratio(candidate_count, noun_chunk_candidates),
                "gold": gold,
                "exactMatches": exact_matches,
                "exactRecall": ratio(exact_matches, gold),
                "uniqueCorrectionsAcrossFolds": len(row["correctionUnion"]),
                "folds": row["folds"],
            }
        )

    report = {
        "schemaVersion": "saga-v3-nominal-boundary-correction-cv-v1",
        "dataset": {
            "repository": "dbamman/litbank",
            "commit": LITBANK_COMMIT,
            "annotationLayer": "coref/tsv",
            "documentCount": len(documents),
            "license": "CC BY 4.0",
            "split": f"{args.folds}-fold document-held-out CV by sorted document index",
        },
        "provider": {
            "spacyVersion": spacy.__version__,
            "model": args.model,
            "modelVersion": nlp.meta.get("version"),
            "method": "training-book-only nearest-overlapping noun-chunk boundary delta patterns",
        },
        "baseline": {
            "nounChunkCandidates": noun_chunk_candidates,
            "goldPersonNominals": sum(len(document.gold_spans) for document in documents),
        },
        "results": results,
        "runtimeSeconds": time.perf_counter() - started,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
