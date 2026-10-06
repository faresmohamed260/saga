"""Leakage-safe second-stage span ranking over held-out nominal boundary candidates."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from math import ceil
from pathlib import Path
import resource
import time

import numpy as np
from scipy.sparse import vstack
from sklearn.feature_extraction import FeatureHasher
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import average_precision_score, roc_auc_score

from packages.narrative_compiler.litbank import LITBANK_COMMIT
from scripts.run_v3_nominal_token_boundary_cv import (
    HASH_DIMENSIONS,
    load_documents,
    ratio,
)


SPAN_HASH_DIMENSIONS = 1 << 18
BUDGET_MULTIPLIERS = (0.5, 1.0, 2.0, 4.0, 8.0)


@dataclass(slots=True)
class CandidatePool:
    features: list[dict[str, object]]
    labels: np.ndarray
    gold: int
    available_gold: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--inner-folds", type=int, default=4)
    parser.add_argument("--model", default="en_core_web_sm")
    parser.add_argument("--max-span-length", type=int, default=16)
    parser.add_argument("--seed", type=int, default=29)
    args = parser.parse_args()
    if not 5 <= args.limit <= 100:
        parser.error("--limit must be between 5 and 100")
    if not 2 <= args.folds <= min(10, args.limit):
        parser.error("--folds must be between 2 and min(10, limit)")
    if not 2 <= args.inner_folds <= 8:
        parser.error("--inner-folds must be between 2 and 8")
    if args.max_span_length < 1:
        parser.error("--max-span-length must be >= 1")
    return args


def make_boundary_classifier(seed: int):
    return SGDClassifier(
        loss="log_loss",
        penalty="l2",
        alpha=1e-5,
        class_weight="balanced",
        max_iter=200,
        tol=1e-4,
        random_state=seed,
        average=True,
    )


def make_span_classifier(seed: int):
    return SGDClassifier(
        loss="log_loss",
        penalty="l2",
        alpha=3e-6,
        class_weight="balanced",
        max_iter=300,
        tol=1e-4,
        random_state=seed,
        average=True,
    )


def stack_docs(hashed_docs, indices):
    return vstack([hashed_docs[index] for index in indices], format="csr")


def stack_labels(documents, indices, attr: str):
    return np.concatenate([getattr(documents[index], attr) for index in indices])


def train_boundary_models(documents, hashed_docs, train_indices, seed: int):
    x_train = stack_docs(hashed_docs, train_indices)
    start_model = make_boundary_classifier(seed)
    end_model = make_boundary_classifier(seed + 1)
    start_model.fit(x_train, stack_labels(documents, train_indices, "start_labels"))
    end_model.fit(x_train, stack_labels(documents, train_indices, "end_labels"))
    return start_model, end_model


def score_docs(start_model, end_model, hashed_docs, indices):
    result = {}
    for index in indices:
        x_doc = hashed_docs[index]
        result[index] = (
            np.asarray(start_model.decision_function(x_doc), dtype=np.float64),
            np.asarray(end_model.decision_function(x_doc), dtype=np.float64),
        )
    return result


def noun_chunk_geometry(doc):
    chunks = [(chunk.start, chunk.end - 1) for chunk in doc.noun_chunks]
    exact = set(chunks)
    return chunks, exact


def span_features(document, start: int, end: int, start_logit: float, end_logit: float):
    doc = document.doc
    span = doc[start : end + 1]
    root = span.root
    first = doc[start]
    last = doc[end]
    before = doc[start - 1] if start > 0 else None
    after = doc[end + 1] if end + 1 < len(doc) else None
    chunks, exact_chunks = noun_chunk_geometry(doc)
    candidate = (start, end)
    contained_by_chunk = any(chunk_start <= start and end <= chunk_end for chunk_start, chunk_end in chunks)
    contains_chunk = any(start <= chunk_start and chunk_end <= end for chunk_start, chunk_end in chunks)
    overlaps_chunk = any(not (end < chunk_start or chunk_end < start) for chunk_start, chunk_end in chunks)
    token_count = len(span)
    lower_surface = span.text.lower()
    row: dict[str, object] = {
        "bias": 1.0,
        f"length={min(token_count, 16)}": 1.0,
        "length_numeric": float(token_count),
        "start_logit": float(np.clip(start_logit, -25.0, 25.0)),
        "end_logit": float(np.clip(end_logit, -25.0, 25.0)),
        "min_boundary_logit": float(np.clip(min(start_logit, end_logit), -25.0, 25.0)),
        "sum_boundary_logit": float(np.clip(start_logit + end_logit, -50.0, 50.0)),
        "boundary_logit_gap": float(np.clip(abs(start_logit - end_logit), 0.0, 50.0)),
        f"start_lower={first.lower_}": 1.0,
        f"start_lemma={first.lemma_.lower()}": 1.0,
        f"start_pos={first.pos_}": 1.0,
        f"start_tag={first.tag_}": 1.0,
        f"start_dep={first.dep_}": 1.0,
        f"end_lower={last.lower_}": 1.0,
        f"end_lemma={last.lemma_.lower()}": 1.0,
        f"end_pos={last.pos_}": 1.0,
        f"end_tag={last.tag_}": 1.0,
        f"end_dep={last.dep_}": 1.0,
        f"root_lower={root.lower_}": 1.0,
        f"root_lemma={root.lemma_.lower()}": 1.0,
        f"root_pos={root.pos_}": 1.0,
        f"root_tag={root.tag_}": 1.0,
        f"root_dep={root.dep_}": 1.0,
        f"root_head_lower={root.head.lower_}": 1.0,
        f"root_head_pos={root.head.pos_}": 1.0,
        "exact_noun_chunk": float(candidate in exact_chunks),
        "contained_by_noun_chunk": float(contained_by_chunk),
        "contains_noun_chunk": float(contains_chunk),
        "overlaps_noun_chunk": float(overlaps_chunk),
        "starts_det": float(first.pos_ == "DET"),
        "starts_possessive": float(first.tag_ in {"PRP$", "POS"}),
        "starts_title": float(first.is_title),
        "ends_nounish": float(last.pos_ in {"NOUN", "PROPN", "PRON"}),
        "contains_propn": float(any(token.pos_ == "PROPN" for token in span)),
        "contains_pron": float(any(token.pos_ == "PRON" for token in span)),
        "contains_verb": float(any(token.pos_ in {"VERB", "AUX"} for token in span)),
        "contains_punct": float(any(token.is_punct for token in span)),
        "noun_count": float(sum(token.pos_ == "NOUN" for token in span)),
        "propn_count": float(sum(token.pos_ == "PROPN" for token in span)),
        "adj_count": float(sum(token.pos_ == "ADJ" for token in span)),
        "det_count": float(sum(token.pos_ == "DET" for token in span)),
    }
    if token_count <= 6:
        row[f"surface={lower_surface}"] = 1.0
    if before is None:
        row["before=BOUNDARY"] = 1.0
    else:
        row[f"before_lower={before.lower_}"] = 1.0
        row[f"before_pos={before.pos_}"] = 1.0
        row[f"before_dep={before.dep_}"] = 1.0
    if after is None:
        row["after=BOUNDARY"] = 1.0
    else:
        row[f"after_lower={after.lower_}"] = 1.0
        row[f"after_pos={after.pos_}"] = 1.0
        row[f"after_dep={after.dep_}"] = 1.0
    return row


def make_candidate_pool(documents, indices, boundary_scores, max_span_length: int) -> CandidatePool:
    features: list[dict[str, object]] = []
    labels: list[int] = []
    gold = 0
    available_gold = 0
    for index in indices:
        document = documents[index]
        start_logits, end_logits = boundary_scores[index]
        starts = np.flatnonzero(start_logits >= 0.0)
        end_mask = end_logits >= 0.0
        gold += len(document.gold_char_spans)
        for gold_start, gold_end in document.gold_token_spans:
            if (
                gold_end - gold_start + 1 <= max_span_length
                and start_logits[gold_start] >= 0.0
                and end_logits[gold_end] >= 0.0
            ):
                available_gold += 1
        for start in starts:
            stop = min(len(document.doc), start + max_span_length)
            for end in range(start, stop):
                if not end_mask[end]:
                    continue
                span = document.doc[start : end + 1]
                features.append(span_features(document, start, end, start_logits[start], end_logits[end]))
                labels.append(1 if (span.start_char, span.end_char) in document.gold_char_spans else 0)
    return CandidatePool(
        features=features,
        labels=np.asarray(labels, dtype=np.int8),
        gold=gold,
        available_gold=available_gold,
    )


def inner_crossfit_boundary_scores(documents, hashed_docs, outer_train, inner_folds: int, seed: int):
    scores = {}
    for inner_fold in range(inner_folds):
        inner_valid = [index for position, index in enumerate(outer_train) if position % inner_folds == inner_fold]
        inner_train = [index for position, index in enumerate(outer_train) if position % inner_folds != inner_fold]
        if not inner_train or not inner_valid:
            continue
        start_model, end_model = train_boundary_models(
            documents,
            hashed_docs,
            inner_train,
            seed + inner_fold * 13,
        )
        scores.update(score_docs(start_model, end_model, hashed_docs, inner_valid))
    missing = set(outer_train) - set(scores)
    if missing:
        raise RuntimeError(f"inner cross-fitting missed documents: {sorted(missing)}")
    return scores


def rank_metrics(labels: np.ndarray, scores: np.ndarray):
    if labels.size == 0 or labels.sum() == 0:
        return {"averagePrecision": 0.0, "rocAuc": None}
    return {
        "averagePrecision": float(average_precision_score(labels, scores)),
        "rocAuc": float(roc_auc_score(labels, scores)) if len(np.unique(labels)) == 2 else None,
    }


def budget_rows(labels: np.ndarray, scores: np.ndarray, gold: int):
    order = np.argsort(-scores, kind="stable")
    rows = []
    for multiplier in BUDGET_MULTIPLIERS:
        budget = min(len(order), max(1, ceil(gold * multiplier)))
        selected = labels[order[:budget]]
        true_positive = int(selected.sum())
        precision = ratio(true_positive, budget)
        recall = ratio(true_positive, gold)
        f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
        rows.append(
            {
                "budgetMultiplierVsGold": multiplier,
                "predicted": budget,
                "truePositive": true_positive,
                "precision": precision,
                "recall": recall,
                "f1": f1,
            }
        )
    return rows


def main() -> None:
    args = parse_args()
    import spacy
    import sklearn

    started = time.perf_counter()
    documents = load_documents(args.root, args.limit, args.model)
    token_hasher = FeatureHasher(n_features=HASH_DIMENSIONS, input_type="dict", alternate_sign=False)
    hashed_docs = [token_hasher.transform(document.features) for document in documents]
    parse_hash_seconds = time.perf_counter() - started
    span_hasher = FeatureHasher(n_features=SPAN_HASH_DIMENSIONS, input_type="dict", alternate_sign=False)

    fold_rows = []
    aggregate_budgets = {
        multiplier: {"predicted": 0, "truePositive": 0, "gold": 0}
        for multiplier in BUDGET_MULTIPLIERS
    }

    for fold in range(args.folds):
        fold_started = time.perf_counter()
        outer_train = [index for index in range(len(documents)) if index % args.folds != fold]
        outer_test = [index for index in range(len(documents)) if index % args.folds == fold]

        inner_scores = inner_crossfit_boundary_scores(
            documents,
            hashed_docs,
            outer_train,
            args.inner_folds,
            args.seed + fold * 101,
        )
        train_pool = make_candidate_pool(documents, outer_train, inner_scores, args.max_span_length)

        outer_start, outer_end = train_boundary_models(
            documents,
            hashed_docs,
            outer_train,
            args.seed + 1000 + fold * 17,
        )
        test_boundary_scores = score_docs(outer_start, outer_end, hashed_docs, outer_test)
        test_pool = make_candidate_pool(documents, outer_test, test_boundary_scores, args.max_span_length)

        x_train = span_hasher.transform(train_pool.features)
        x_test = span_hasher.transform(test_pool.features)
        span_model = make_span_classifier(args.seed + 5000 + fold)
        span_model.fit(x_train, train_pool.labels)
        test_scores = np.asarray(span_model.decision_function(x_test), dtype=np.float64)

        fold_budgets = budget_rows(test_pool.labels, test_scores, test_pool.gold)
        for row in fold_budgets:
            target = aggregate_budgets[row["budgetMultiplierVsGold"]]
            target["predicted"] += row["predicted"]
            target["truePositive"] += row["truePositive"]
            target["gold"] += test_pool.gold

        fold_rows.append(
            {
                "fold": fold,
                "outerTrainDocuments": len(outer_train),
                "outerTestDocuments": len(outer_test),
                "innerFolds": args.inner_folds,
                "trainCandidates": len(train_pool.labels),
                "trainCandidatePositive": int(train_pool.labels.sum()),
                "trainCandidateRecallCeiling": ratio(train_pool.available_gold, train_pool.gold),
                "testCandidates": len(test_pool.labels),
                "testCandidatePositive": int(test_pool.labels.sum()),
                "testCandidateRecallCeiling": ratio(test_pool.available_gold, test_pool.gold),
                "ranking": rank_metrics(test_pool.labels, test_scores),
                "budgets": fold_budgets,
                "runtimeSeconds": time.perf_counter() - fold_started,
            }
        )

    aggregate_rows = []
    for multiplier in BUDGET_MULTIPLIERS:
        counts = aggregate_budgets[multiplier]
        precision = ratio(counts["truePositive"], counts["predicted"])
        recall = ratio(counts["truePositive"], counts["gold"])
        f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
        aggregate_rows.append(
            {
                "budgetMultiplierVsGold": multiplier,
                **counts,
                "precision": precision,
                "recall": recall,
                "f1": f1,
            }
        )

    runtime = time.perf_counter() - started
    peak_rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    output = {
        "schemaVersion": "saga-v3-nominal-crossfit-span-rank-cv-v1",
        "dataset": {
            "repository": "dbamman/litbank",
            "commit": LITBANK_COMMIT,
            "annotationLayer": "coref/tsv",
            "license": "CC BY 4.0",
            "documentCount": len(documents),
            "outerSplit": f"{args.folds}-fold document-held-out CV by sorted document index",
            "innerSplit": f"{args.inner_folds}-fold cross-fitting inside each outer-train partition",
            "goldPersonNominals": sum(len(document.gold_char_spans) for document in documents),
            "tokens": sum(len(document.doc) for document in documents),
        },
        "provider": {
            "candidateGenerator": "cross-fitted hashed linear nominal start/end classifiers, decision_function >= 0",
            "spanRanker": "SGDClassifier(loss=log_loss, class_weight=balanced, average=True)",
            "spanFeatures": "boundary logits + span/root/edge/context syntax + noun-chunk geometry + short surface",
            "tokenHashDimensions": HASH_DIMENSIONS,
            "spanHashDimensions": SPAN_HASH_DIMENSIONS,
            "spacyVersion": spacy.__version__,
            "spacyModel": args.model,
            "sklearnVersion": sklearn.__version__,
            "device": "cpu",
            "maxSpanLengthTokens": args.max_span_length,
            "budgetMultipliersVsFoldGold": list(BUDGET_MULTIPLIERS),
        },
        "folds": fold_rows,
        "aggregateBudgets": aggregate_rows,
        "aggregateRanking": {
            "meanFoldAveragePrecision": float(np.mean([fold["ranking"]["averagePrecision"] for fold in fold_rows])),
            "minFoldAveragePrecision": float(np.min([fold["ranking"]["averagePrecision"] for fold in fold_rows])),
            "maxFoldAveragePrecision": float(np.max([fold["ranking"]["averagePrecision"] for fold in fold_rows])),
            "meanTestCandidateRecallCeiling": float(np.mean([fold["testCandidateRecallCeiling"] for fold in fold_rows])),
        },
        "resources": {
            "parseAndHashSeconds": parse_hash_seconds,
            "runtimeSeconds": runtime,
            "peakRssMb": peak_rss_mb,
            "peakVramMb": None,
        },
        "decisionScope": {
            "publicEvidenceOnly": True,
            "productionAdopted": False,
            "canonicalIdentityThreshold": False,
            "notes": [
                "Outer-test books are never used to train boundary models or the span ranker.",
                "Outer-train span-ranker candidates use inner out-of-fold boundary scores, preventing boundary-score leakage into ranker training.",
                "This benchmark evaluates nominal span evidence only, not canonical identity.",
                "LitBank public evidence cannot by itself promote a production provider.",
            ],
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
