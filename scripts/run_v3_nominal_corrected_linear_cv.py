"""Book-held-out classifiers over learned noun-chunk boundary corrections."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
import math
from pathlib import Path
import time

from packages.narrative_compiler.litbank import LITBANK_COMMIT, convert_litbank_tsv_document


PROFILES = (4, 8)
THRESHOLDS = (0.50, 0.70, 0.85, 0.95)
TOP_K_RANKS = (2000, 3000, 4000, 5000)
HASH_FEATURES = 2**18
POSSESSIVES = frozenset({"my", "your", "his", "her", "our", "their", "its"})
DETERMINERS = frozenset(
    {
        "the",
        "a",
        "an",
        "this",
        "that",
        "these",
        "those",
        "some",
        "any",
        "no",
        "every",
        "each",
        "another",
    }
)


@dataclass(frozen=True)
class ParsedDocument:
    name: str
    parsed: object
    gold_spans: frozenset[tuple[int, int]]
    gold_token_spans: tuple[tuple[int, int, int, int], ...]
    chunks: tuple[object, ...]


@dataclass(frozen=True)
class CandidateAnchor:
    start: int
    end: int
    chunk_start: int
    chunk_end: int
    root_i: int
    delta_start: int
    delta_end: int
    correction_rank: int
    train_count: int


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


def f1(precision: float, recall: float) -> float:
    return 0.0 if precision + recall == 0.0 else 2.0 * precision * recall / (precision + recall)


def overlap_chars(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    return max(0, min(a_end, b_end) - max(a_start, b_start))


def char_span(doc, start: int, end: int) -> tuple[int, int]:
    return doc[start].idx, doc[end - 1].idx + len(doc[end - 1])


def token_span(doc, start: int, end: int):
    span = doc.char_span(start, end, alignment_mode="strict")
    if span is None:
        span = doc.char_span(start, end, alignment_mode="contract")
    return None if span is None else (span.start, span.end)


def nearest_overlapping_chunk(gold_start: int, gold_end: int, chunks):
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
    for index in train_indices:
        document = documents[index]
        for token_start, token_end, char_start, char_end in document.gold_token_spans:
            chunk = nearest_overlapping_chunk(char_start, char_end, document.chunks)
            if chunk is None:
                continue
            if chunk.root.i < token_start or chunk.root.i >= token_end:
                continue
            corrections[(token_start - chunk.start, token_end - chunk.end)] += 1
    return corrections


def selected_corrections(counter: Counter[tuple[int, int]], top_non_exact: int):
    non_exact = [pair for pair, _count in counter.most_common() if pair != (0, 0)][:top_non_exact]
    return ((0, 0), *non_exact)


def lemma(token) -> str:
    value = token.lemma_.casefold().strip()
    return value if value and value != "-pron-" else token.lower_.casefold()


def length_bucket(length: int) -> str:
    if length <= 1:
        return "1"
    if length == 2:
        return "2"
    if length == 3:
        return "3"
    if length <= 5:
        return "4-5"
    if length <= 8:
        return "6-8"
    return "9+"


def count_bucket(count: int) -> str:
    if count <= 0:
        return "0"
    exponent = int(math.log2(count))
    return f"2^{exponent}"


def delta_bucket(value: int) -> str:
    if value <= -8:
        return "<=-8"
    if value >= 8:
        return ">=8"
    return str(value)


def anchor_features(document: ParsedDocument, anchor: CandidateAnchor) -> list[str]:
    doc = document.parsed
    root = doc[anchor.root_i]
    first = doc[anchor.start]
    last = doc[anchor.end - 1]
    span = doc[anchor.start : anchor.end]
    previous = doc[anchor.start - 1] if anchor.start > root.sent.start else None
    following = doc[anchor.end] if anchor.end < root.sent.end else None
    first_lower = first.lower_.casefold()
    root_lemma = lemma(root)

    features = [
        "bias",
        f"head={root_lemma}",
        f"head_pos={root.pos_}",
        f"head_tag={root.tag_}",
        f"head_dep={root.dep_}",
        f"head_suffix2={root_lemma[-2:] if len(root_lemma) >= 2 else root_lemma}",
        f"head_suffix3={root_lemma[-3:] if len(root_lemma) >= 3 else root_lemma}",
        f"first={lemma(first)}",
        f"first_pos={first.pos_}",
        f"last={lemma(last)}",
        f"last_pos={last.pos_}",
        f"length={length_bucket(anchor.end - anchor.start)}",
        f"delta_start={delta_bucket(anchor.delta_start)}",
        f"delta_end={delta_bucket(anchor.delta_end)}",
        f"delta_pair={delta_bucket(anchor.delta_start)},{delta_bucket(anchor.delta_end)}",
        f"correction_rank={min(anchor.correction_rank, 8)}",
        f"correction_count={count_bucket(anchor.train_count)}",
        f"previous={lemma(previous) if previous is not None else '<BOS>'}",
        f"previous_pos={previous.pos_ if previous is not None else '<BOS>'}",
        f"next={lemma(following) if following is not None else '<EOS>'}",
        f"next_pos={following.pos_ if following is not None else '<EOS>'}",
    ]
    if first_lower in POSSESSIVES:
        features.append("starts_possessive")
    if first_lower in DETERMINERS:
        features.append("starts_determiner")
    if anchor.delta_start == 0 and anchor.delta_end == 0:
        features.append("exact_noun_chunk")
    if anchor.start <= anchor.chunk_start and anchor.end >= anchor.chunk_end:
        features.append("contains_noun_chunk")
    if anchor.start >= anchor.chunk_start and anchor.end <= anchor.chunk_end:
        features.append("inside_noun_chunk")
    if anchor.delta_start < 0:
        features.append("expands_left")
    elif anchor.delta_start > 0:
        features.append("shrinks_left")
    if anchor.delta_end > 0:
        features.append("expands_right")
    elif anchor.delta_end < 0:
        features.append("shrinks_right")
    if any(token.pos_ == "PROPN" for token in span):
        features.append("contains_proper")
    if any(token.pos_ == "PRON" for token in span):
        features.append("contains_pronoun")
    if root.tag_ in {"NNS", "NNPS"}:
        features.append("plural_head")
    return features


def generate_document_examples(
    document: ParsedDocument,
    corrections: tuple[tuple[int, int], ...],
    correction_counts: Counter[tuple[int, int]],
):
    best_by_span: dict[tuple[int, int], CandidateAnchor] = {}
    for chunk in document.chunks:
        sentence = chunk.root.sent
        for rank, (delta_start, delta_end) in enumerate(corrections):
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
            span = char_span(document.parsed, start, end)
            anchor = CandidateAnchor(
                start=start,
                end=end,
                chunk_start=chunk.start,
                chunk_end=chunk.end,
                root_i=chunk.root.i,
                delta_start=delta_start,
                delta_end=delta_end,
                correction_rank=rank,
                train_count=correction_counts[(delta_start, delta_end)],
            )
            current = best_by_span.get(span)
            if current is None or (anchor.correction_rank, abs(delta_start) + abs(delta_end), anchor.root_i) < (
                current.correction_rank,
                abs(current.delta_start) + abs(current.delta_end),
                current.root_i,
            ):
                best_by_span[span] = anchor

    feature_rows = []
    labels = []
    for span, anchor in sorted(best_by_span.items()):
        feature_rows.append(anchor_features(document, anchor))
        labels.append(int(span in document.gold_spans))
    return feature_rows, labels


def build_matrix(documents, indices, corrections, correction_counts, hasher):
    import numpy as np
    from scipy.sparse import vstack

    matrices = []
    labels = []
    for index in indices:
        feature_rows, document_labels = generate_document_examples(
            documents[index], corrections, correction_counts
        )
        matrices.append(hasher.transform(feature_rows))
        labels.append(np.asarray(document_labels, dtype=np.int8))
    return vstack(matrices, format="csr"), np.concatenate(labels)


def operating_row(labels, scores, *, gold_total: int, threshold: float | None = None, top_k: int | None = None):
    import numpy as np

    if threshold is not None:
        selected = np.flatnonzero(scores >= threshold)
    elif top_k is not None:
        count = min(top_k, len(scores))
        selected = np.argsort(-scores, kind="stable")[:count]
    else:
        raise ValueError("threshold or top_k required")
    true_positive = int(labels[selected].sum()) if len(selected) else 0
    predicted = int(len(selected))
    precision = ratio(true_positive, predicted)
    recall = ratio(true_positive, gold_total)
    row = {
        "predicted": predicted,
        "truePositive": true_positive,
        "falsePositive": predicted - true_positive,
        "precision": precision,
        "recall": recall,
        "f1": f1(precision, recall),
    }
    if threshold is not None:
        row["threshold"] = threshold
    if top_k is not None:
        row["topK"] = top_k
    return row


def main() -> None:
    args = parse_args()

    import numpy as np
    import scipy
    import spacy
    import sklearn
    from sklearn.feature_extraction import FeatureHasher
    from sklearn.linear_model import SGDClassifier
    from sklearn.metrics import average_precision_score, roc_auc_score

    nlp = spacy.load(args.model, disable=["ner"])
    documents = parse_corpus(nlp, load_documents(args.root, args.limit))
    gold_total = sum(len(document.gold_spans) for document in documents)
    noun_chunk_candidates = sum(len(document.chunks) for document in documents)
    hasher = FeatureHasher(n_features=HASH_FEATURES, input_type="string", alternate_sign=False)
    started = time.perf_counter()

    profile_outputs = []
    for top_non_exact in PROFILES:
        oof_labels = []
        oof_scores = []
        fold_rows = []
        candidate_upper_bound_tp = 0
        candidate_count = 0

        for fold in range(args.folds):
            train_indices = [i for i in range(len(documents)) if i % args.folds != fold]
            test_indices = [i for i in range(len(documents)) if i % args.folds == fold]
            correction_counts = learn_corrections(documents, train_indices)
            corrections = selected_corrections(correction_counts, top_non_exact)

            x_train, y_train = build_matrix(
                documents, train_indices, corrections, correction_counts, hasher
            )
            x_test, y_test = build_matrix(
                documents, test_indices, corrections, correction_counts, hasher
            )
            classifier = SGDClassifier(
                loss="log_loss",
                penalty="l2",
                alpha=1e-5,
                class_weight="balanced",
                max_iter=1000,
                tol=1e-3,
                random_state=0,
            )
            classifier.fit(x_train, y_train)
            probabilities = classifier.predict_proba(x_test)[:, 1]

            oof_labels.append(y_test)
            oof_scores.append(probabilities)
            candidate_upper_bound_tp += int(y_test.sum())
            candidate_count += int(len(y_test))
            fold_rows.append(
                {
                    "fold": fold,
                    "trainDocuments": len(train_indices),
                    "testDocuments": len(test_indices),
                    "trainCandidates": int(len(y_train)),
                    "testCandidates": int(len(y_test)),
                    "testPositiveCandidates": int(y_test.sum()),
                    "corrections": [
                        {
                            "startDelta": start,
                            "endDelta": end,
                            "trainCount": correction_counts[(start, end)],
                        }
                        for start, end in corrections
                    ],
                    "iterations": int(classifier.n_iter_),
                }
            )

        labels = np.concatenate(oof_labels)
        scores = np.concatenate(oof_scores)
        profile_outputs.append(
            {
                "topNonExactCorrections": top_non_exact,
                "candidateCount": candidate_count,
                "candidateMultiplierVsNounChunk": ratio(candidate_count, noun_chunk_candidates),
                "candidateExactRecallUpperBound": ratio(candidate_upper_bound_tp, gold_total),
                "outOfFoldRanking": {
                    "averagePrecision": average_precision_score(labels, scores),
                    "rocAuc": roc_auc_score(labels, scores),
                },
                "thresholds": [
                    operating_row(labels, scores, gold_total=gold_total, threshold=threshold)
                    for threshold in THRESHOLDS
                ],
                "topK": [
                    operating_row(labels, scores, gold_total=gold_total, top_k=top_k)
                    for top_k in TOP_K_RANKS
                ],
                "folds": fold_rows,
            }
        )

    report = {
        "schemaVersion": "saga-v3-nominal-corrected-linear-cv-v1",
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
            "sklearnVersion": sklearn.__version__,
            "scipyVersion": scipy.__version__,
            "classifier": "SGDClassifier(loss=log_loss,alpha=1e-5,class_weight=balanced)",
            "featureHasherDimensions": HASH_FEATURES,
            "candidateMethod": "training-book-only top noun-chunk boundary corrections",
        },
        "counts": {
            "goldPersonNominals": gold_total,
            "nounChunkCandidates": noun_chunk_candidates,
        },
        "profiles": profile_outputs,
        "runtimeSeconds": time.perf_counter() - started,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
