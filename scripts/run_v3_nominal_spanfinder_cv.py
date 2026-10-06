"""Book-held-out direct person-nominal span discovery with spaCy SpanFinder."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import random
import resource
from pathlib import Path
import time
from typing import Iterable

from packages.narrative_compiler.litbank import LITBANK_COMMIT, convert_litbank_tsv_document


SPANS_KEY = "nominal_candidates"
DEFAULT_THRESHOLDS = (0.25, 0.35, 0.50, 0.65, 0.80, 0.90)


@dataclass(frozen=True, slots=True)
class CorpusDocument:
    name: str
    text: str
    gold_spans: frozenset[tuple[int, int]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--dropout", type=float, default=0.10)
    parser.add_argument("--max-span-length", type=int, default=16)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--thresholds", type=float, nargs="+", default=list(DEFAULT_THRESHOLDS))
    args = parser.parse_args()
    if not 5 <= args.limit <= 100:
        parser.error("--limit must be between 5 and 100")
    if not 2 <= args.folds <= min(10, args.limit):
        parser.error("--folds must be between 2 and min(10, limit)")
    if args.epochs < 1:
        parser.error("--epochs must be >= 1")
    if args.batch_size < 1:
        parser.error("--batch-size must be >= 1")
    if not 0.0 <= args.dropout < 1.0:
        parser.error("--dropout must be in [0, 1)")
    if args.max_span_length < 1:
        parser.error("--max-span-length must be >= 1")
    if any(not 0.0 < threshold < 1.0 for threshold in args.thresholds):
        parser.error("--thresholds must be strictly between 0 and 1")
    args.thresholds = tuple(sorted(set(args.thresholds)))
    return args


def ratio(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def f1(precision: float, recall: float) -> float:
    return 0.0 if precision + recall == 0.0 else 2.0 * precision * recall / (precision + recall)


def load_documents(root: Path, limit: int) -> list[CorpusDocument]:
    annotation_dir = root.resolve() / "coref" / "tsv"
    paths = sorted(annotation_dir.glob("*.ann"))[:limit]
    if not paths:
        raise RuntimeError("no LitBank coref/tsv annotations found")
    documents = []
    for path in paths:
        converted = convert_litbank_tsv_document(
            document_id=path.stem,
            annotation=path.read_text(encoding="utf-8"),
            text=(annotation_dir / f"{path.stem}.txt").read_text(encoding="utf-8"),
        )
        gold_spans = frozenset(
            (mention.start_offset, mention.end_offset)
            for mention in converted.gold.mentions
            if mention.entity_type == "person" and mention.mention_kind == "nominal"
        )
        documents.append(CorpusDocument(path.stem, converted.source.normalized_text, gold_spans))
    return documents


def make_pipeline(*, max_span_length: int):
    import spacy

    nlp = spacy.blank("en")
    nlp.add_pipe(
        "span_finder",
        config={
            "spans_key": SPANS_KEY,
            "threshold": 0.5,
            "min_length": 1,
            "max_length": max_span_length,
        },
    )
    return nlp


def make_example(nlp, document: CorpusDocument):
    from spacy.training import Example

    predicted = nlp.make_doc(document.text)
    reference = nlp.make_doc(document.text)
    spans = []
    for start, end in sorted(document.gold_spans):
        span = reference.char_span(start, end, alignment_mode="strict")
        if span is not None:
            spans.append(span)
    reference.spans[SPANS_KEY] = spans
    return Example(predicted, reference)


def aligned_gold(nlp, document: CorpusDocument):
    doc = nlp.make_doc(document.text)
    aligned = []
    unaligned = 0
    for start, end in document.gold_spans:
        span = doc.char_span(start, end, alignment_mode="strict")
        if span is None:
            unaligned += 1
            continue
        aligned.append((span.start, span.end - 1, start, end))
    return doc, aligned, unaligned


def predicted_spans(doc, scores, threshold: float, max_span_length: int):
    starts = {index for index, row in enumerate(scores) if float(row[0]) >= threshold}
    ends = {index for index, row in enumerate(scores) if float(row[1]) >= threshold}
    predicted = set()
    for start in starts:
        max_end = min(len(doc) - 1, start + max_span_length - 1)
        for end in range(start, max_end + 1):
            if end in ends:
                span = doc[start : end + 1]
                predicted.add((span.start_char, span.end_char))
    return predicted, starts, ends


def empty_metric_accumulator():
    return {
        "gold": 0,
        "predicted": 0,
        "truePositive": 0,
        "alignedGold": 0,
        "unalignedGold": 0,
        "startGold": 0,
        "startPredicted": 0,
        "startTruePositive": 0,
        "endGold": 0,
        "endPredicted": 0,
        "endTruePositive": 0,
        "tokens": 0,
        "characters": 0,
    }


def finalize_metric_row(threshold: float, row: dict[str, int]):
    precision = ratio(row["truePositive"], row["predicted"])
    recall = ratio(row["truePositive"], row["gold"])
    start_precision = ratio(row["startTruePositive"], row["startPredicted"])
    start_recall = ratio(row["startTruePositive"], row["startGold"])
    end_precision = ratio(row["endTruePositive"], row["endPredicted"])
    end_recall = ratio(row["endTruePositive"], row["endGold"])
    return {
        "threshold": threshold,
        **row,
        "precision": precision,
        "recall": recall,
        "f1": f1(precision, recall),
        "startPrecision": start_precision,
        "startRecall": start_recall,
        "startF1": f1(start_precision, start_recall),
        "endPrecision": end_precision,
        "endRecall": end_recall,
        "endF1": f1(end_precision, end_recall),
    }


class _NullContext:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


def train_fold(
    documents,
    *,
    train_indices,
    test_indices,
    fold,
    epochs,
    batch_size,
    dropout,
    max_span_length,
    thresholds,
    seed,
):
    from spacy.util import fix_random_seed, minibatch

    fold_seed = seed + fold
    fix_random_seed(fold_seed)
    random.seed(fold_seed)
    nlp = make_pipeline(max_span_length=max_span_length)
    train_examples = [make_example(nlp, documents[index]) for index in train_indices]
    optimizer = nlp.initialize(lambda: train_examples)

    train_started = time.perf_counter()
    epoch_rows = []
    for epoch in range(epochs):
        shuffled = list(train_examples)
        random.Random(fold_seed + epoch).shuffle(shuffled)
        losses = {}
        for batch in minibatch(shuffled, size=batch_size):
            nlp.update(batch, sgd=optimizer, drop=dropout, losses=losses)
        epoch_rows.append(
            {"epoch": epoch + 1, "spanFinderLoss": float(losses.get("span_finder", 0.0))}
        )
    train_seconds = time.perf_counter() - train_started

    finder = nlp.get_pipe("span_finder")
    threshold_rows = {threshold: empty_metric_accumulator() for threshold in thresholds}
    inference_started = time.perf_counter()
    params = getattr(optimizer, "averages", None)
    context = nlp.use_params(params) if params else _NullContext()
    with context:
        for index in test_indices:
            document = documents[index]
            doc, gold_token_spans, unaligned = aligned_gold(nlp, document)
            scores = finder.predict([doc])
            gold_starts = {start for start, _end, _char_start, _char_end in gold_token_spans}
            gold_ends = {end for _start, end, _char_start, _char_end in gold_token_spans}
            for threshold in thresholds:
                predicted, starts, ends = predicted_spans(doc, scores, threshold, max_span_length)
                row = threshold_rows[threshold]
                row["gold"] += len(document.gold_spans)
                row["alignedGold"] += len(gold_token_spans)
                row["unalignedGold"] += unaligned
                row["predicted"] += len(predicted)
                row["truePositive"] += len(predicted & document.gold_spans)
                row["startGold"] += len(gold_starts)
                row["startPredicted"] += len(starts)
                row["startTruePositive"] += len(starts & gold_starts)
                row["endGold"] += len(gold_ends)
                row["endPredicted"] += len(ends)
                row["endTruePositive"] += len(ends & gold_ends)
                row["tokens"] += len(doc)
                row["characters"] += len(document.text)

    inference_seconds = time.perf_counter() - inference_started
    return {
        "fold": fold,
        "seed": fold_seed,
        "trainDocuments": len(train_indices),
        "testDocuments": len(test_indices),
        "trainGoldNominals": sum(len(documents[index].gold_spans) for index in train_indices),
        "testGoldNominals": sum(len(documents[index].gold_spans) for index in test_indices),
        "trainSeconds": train_seconds,
        "inferenceSeconds": inference_seconds,
        "modelBytes": len(nlp.to_bytes()),
        "finalLoss": epoch_rows[-1]["spanFinderLoss"],
        "epochs": epoch_rows,
        "thresholds": {str(threshold): threshold_rows[threshold] for threshold in thresholds},
    }


def merge_threshold_rows(fold_rows: Iterable[dict], thresholds):
    aggregate = {threshold: empty_metric_accumulator() for threshold in thresholds}
    for fold in fold_rows:
        for threshold in thresholds:
            source = fold["thresholds"][str(threshold)]
            target = aggregate[threshold]
            for key in target:
                target[key] += int(source[key])
    return [finalize_metric_row(threshold, aggregate[threshold]) for threshold in thresholds]


def main() -> None:
    args = parse_args()

    import spacy

    documents = load_documents(args.root, args.limit)
    started = time.perf_counter()
    fold_rows = []
    for fold in range(args.folds):
        train_indices = [index for index in range(len(documents)) if index % args.folds != fold]
        test_indices = [index for index in range(len(documents)) if index % args.folds == fold]
        fold_rows.append(
            train_fold(
                documents,
                train_indices=train_indices,
                test_indices=test_indices,
                fold=fold,
                epochs=args.epochs,
                batch_size=args.batch_size,
                dropout=args.dropout,
                max_span_length=args.max_span_length,
                thresholds=args.thresholds,
                seed=args.seed,
            )
        )

    threshold_rows = merge_threshold_rows(fold_rows, args.thresholds)
    total_seconds = time.perf_counter() - started
    peak_rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    total_tokens = threshold_rows[0]["tokens"] if threshold_rows else 0
    total_characters = threshold_rows[0]["characters"] if threshold_rows else 0

    output = {
        "schemaVersion": "saga-v3-nominal-spanfinder-cv-v1",
        "dataset": {
            "repository": "dbamman/litbank",
            "commit": LITBANK_COMMIT,
            "annotationLayer": "coref/tsv",
            "license": "CC BY 4.0",
            "documentCount": len(documents),
            "split": f"{args.folds}-fold document-held-out CV by sorted document index",
            "goldPersonNominals": sum(len(document.gold_spans) for document in documents),
        },
        "provider": {
            "family": "spaCy SpanFinder",
            "spacyVersion": spacy.__version__,
            "component": "span_finder",
            "architecture": "spacy.SpanFinder.v1 default tok2vec",
            "packageLicense": "MIT",
            "language": "en",
            "device": "cpu",
            "spansKey": SPANS_KEY,
            "maxSpanLengthTokens": args.max_span_length,
            "epochs": args.epochs,
            "batchSize": args.batch_size,
            "dropout": args.dropout,
            "seed": args.seed,
            "thresholds": list(args.thresholds),
        },
        "folds": fold_rows,
        "thresholds": threshold_rows,
        "resources": {
            "runtimeSeconds": total_seconds,
            "peakRssMb": peak_rss_mb,
            "peakVramMb": None,
            "processedTokens": total_tokens,
            "processedCharacters": total_characters,
            "charactersPerSecond": 0.0 if total_seconds == 0.0 else total_characters / total_seconds,
            "maxSerializedModelBytes": max(row["modelBytes"] for row in fold_rows),
            "meanSerializedModelBytes": sum(row["modelBytes"] for row in fold_rows) / len(fold_rows),
        },
        "decisionScope": {
            "publicEvidenceOnly": True,
            "productionAdopted": False,
            "canonicalIdentityThreshold": False,
            "notes": [
                "This benchmark evaluates nominal span evidence only, not canonical identity.",
                "LitBank public evidence cannot by itself promote a production provider.",
                "Thresholds are benchmark operating points, not canon acceptance probabilities.",
            ],
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
