"""Rank held-out nominal span pairs using cross-book token-boundary logits."""

from __future__ import annotations

import argparse
import json
from math import ceil
from pathlib import Path
import resource
import time

import numpy as np
from sklearn.feature_extraction import FeatureHasher
from sklearn.metrics import average_precision_score

from packages.narrative_compiler.litbank import LITBANK_COMMIT
from scripts.run_v3_nominal_token_boundary_cv import (
    HASH_DIMENSIONS,
    concat_features,
    concat_labels,
    load_documents,
    make_classifier,
    ratio,
)


BUDGET_MULTIPLIERS = (0.5, 1.0, 2.0, 4.0, 8.0)
SCORERS = ("sum", "min")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--model", default="en_core_web_sm")
    parser.add_argument("--max-span-length", type=int, default=16)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    if not 5 <= args.limit <= 100:
        parser.error("--limit must be between 5 and 100")
    if not 2 <= args.folds <= min(10, args.limit):
        parser.error("--folds must be between 2 and min(10, limit)")
    if args.max_span_length < 1:
        parser.error("--max-span-length must be >= 1")
    return args


def pair_score(start_logit: float, end_logit: float, scorer: str) -> float:
    if scorer == "sum":
        return float(start_logit + end_logit)
    if scorer == "min":
        return float(min(start_logit, end_logit))
    raise ValueError(scorer)


def make_pair_pool(document, start_logits: np.ndarray, end_logits: np.ndarray, max_span_length: int):
    starts = np.flatnonzero(start_logits >= 0.0)
    end_mask = end_logits >= 0.0
    pools = {scorer: [] for scorer in SCORERS}
    gold_available = 0

    for start, end in document.gold_token_spans:
        if end - start + 1 <= max_span_length and start_logits[start] >= 0.0 and end_logits[end] >= 0.0:
            gold_available += 1

    for start in starts:
        stop = min(len(document.doc), start + max_span_length)
        for end in range(start, stop):
            if not end_mask[end]:
                continue
            span = document.doc[start : end + 1]
            char_span = (span.start_char, span.end_char)
            label = 1 if char_span in document.gold_char_spans else 0
            for scorer in SCORERS:
                pools[scorer].append(
                    (
                        pair_score(start_logits[start], end_logits[end], scorer),
                        label,
                        document.name,
                        char_span,
                    )
                )
    return pools, gold_available


def budget_row(ranked, budget: int, gold_count: int):
    selected = ranked[: min(budget, len(ranked))]
    predicted = len(selected)
    true_positive = sum(item[1] for item in selected)
    precision = ratio(true_positive, predicted)
    recall = ratio(true_positive, gold_count)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {
        "budget": budget,
        "predicted": predicted,
        "truePositive": true_positive,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def main() -> None:
    args = parse_args()
    import spacy
    import sklearn

    started = time.perf_counter()
    documents = load_documents(args.root, args.limit, args.model)
    parse_seconds = time.perf_counter() - started

    fold_rows = []
    aggregate = {
        scorer: {
            multiplier: {"predicted": 0, "truePositive": 0, "gold": 0}
            for multiplier in BUDGET_MULTIPLIERS
        }
        for scorer in SCORERS
    }

    for fold in range(args.folds):
        fold_started = time.perf_counter()
        train_indices = [index for index in range(len(documents)) if index % args.folds != fold]
        test_indices = [index for index in range(len(documents)) if index % args.folds == fold]
        hasher = FeatureHasher(n_features=HASH_DIMENSIONS, input_type="dict", alternate_sign=False)
        train_features = hasher.transform(concat_features(documents, train_indices))
        test_features = hasher.transform(concat_features(documents, test_indices))
        y_start_train = concat_labels(documents, train_indices, "start_labels")
        y_end_train = concat_labels(documents, train_indices, "end_labels")

        start_model = make_classifier(args.seed + fold * 2)
        end_model = make_classifier(args.seed + fold * 2 + 1)
        start_model.fit(train_features, y_start_train)
        end_model.fit(train_features, y_end_train)
        start_logits = start_model.decision_function(test_features)
        end_logits = end_model.decision_function(test_features)

        fold_pools = {scorer: [] for scorer in SCORERS}
        cursor = 0
        fold_gold = 0
        fold_gold_available = 0
        for index in test_indices:
            document = documents[index]
            length = len(document.doc)
            doc_start = start_logits[cursor : cursor + length]
            doc_end = end_logits[cursor : cursor + length]
            pools, available = make_pair_pool(document, doc_start, doc_end, args.max_span_length)
            for scorer in SCORERS:
                fold_pools[scorer].extend(pools[scorer])
            fold_gold += len(document.gold_char_spans)
            fold_gold_available += available
            cursor += length

        scorer_rows = {}
        for scorer in SCORERS:
            ranked = sorted(fold_pools[scorer], key=lambda item: item[0], reverse=True)
            labels = np.fromiter((item[1] for item in ranked), dtype=np.int8)
            scores = np.fromiter((item[0] for item in ranked), dtype=np.float64)
            ap = float(average_precision_score(labels, scores)) if labels.size and labels.sum() else 0.0
            budget_rows = []
            for multiplier in BUDGET_MULTIPLIERS:
                budget = max(1, ceil(fold_gold * multiplier))
                row = budget_row(ranked, budget, fold_gold)
                row["budgetMultiplierVsGold"] = multiplier
                budget_rows.append(row)
                target = aggregate[scorer][multiplier]
                target["predicted"] += row["predicted"]
                target["truePositive"] += row["truePositive"]
                target["gold"] += fold_gold
            scorer_rows[scorer] = {
                "candidatePairs": len(ranked),
                "candidateTruePositive": int(labels.sum()),
                "candidatePrecision": ratio(int(labels.sum()), len(ranked)),
                "candidateRecall": ratio(int(labels.sum()), fold_gold),
                "averagePrecisionWithinCandidatePool": ap,
                "budgets": budget_rows,
            }

        fold_rows.append(
            {
                "fold": fold,
                "trainDocuments": len(train_indices),
                "testDocuments": len(test_indices),
                "goldNominals": fold_gold,
                "goldAvailableByBoundaryGate": fold_gold_available,
                "boundaryGateRecallCeiling": ratio(fold_gold_available, fold_gold),
                "scorers": scorer_rows,
                "runtimeSeconds": time.perf_counter() - fold_started,
            }
        )

    aggregate_rows = {}
    for scorer in SCORERS:
        rows = []
        for multiplier in BUDGET_MULTIPLIERS:
            counts = aggregate[scorer][multiplier]
            precision = ratio(counts["truePositive"], counts["predicted"])
            recall = ratio(counts["truePositive"], counts["gold"])
            f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
            rows.append(
                {
                    "budgetMultiplierVsGold": multiplier,
                    **counts,
                    "precision": precision,
                    "recall": recall,
                    "f1": f1,
                }
            )
        aggregate_rows[scorer] = rows

    runtime = time.perf_counter() - started
    peak_rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    output = {
        "schemaVersion": "saga-v3-nominal-pair-rank-cv-v1",
        "dataset": {
            "repository": "dbamman/litbank",
            "commit": LITBANK_COMMIT,
            "annotationLayer": "coref/tsv",
            "license": "CC BY 4.0",
            "documentCount": len(documents),
            "split": f"{args.folds}-fold document-held-out CV by sorted document index",
            "goldPersonNominals": sum(len(document.gold_char_spans) for document in documents),
            "tokens": sum(len(document.doc) for document in documents),
        },
        "provider": {
            "candidateGate": "independent held-out start/end decision_function >= 0 (equivalent to p>=0.5)",
            "pairScorers": {
                "sum": "start_logit + end_logit",
                "min": "min(start_logit, end_logit)",
            },
            "boundaryClassifier": "SGDClassifier(loss=log_loss, class_weight=balanced, average=True)",
            "features": "local lexical + POS/tag/dependency + head + NER + noun-chunk geometry",
            "hashDimensions": HASH_DIMENSIONS,
            "spacyVersion": spacy.__version__,
            "spacyModel": args.model,
            "sklearnVersion": sklearn.__version__,
            "device": "cpu",
            "maxSpanLengthTokens": args.max_span_length,
            "budgetMultipliersVsFoldGold": list(BUDGET_MULTIPLIERS),
        },
        "folds": fold_rows,
        "aggregateBudgets": aggregate_rows,
        "resources": {
            "parseSeconds": parse_seconds,
            "runtimeSeconds": runtime,
            "peakRssMb": peak_rss_mb,
            "peakVramMb": None,
        },
        "decisionScope": {
            "publicEvidenceOnly": True,
            "productionAdopted": False,
            "canonicalIdentityThreshold": False,
            "notes": [
                "Pair ranking uses only held-out boundary-model logits from models trained on other books.",
                "Budgets are applied within each held-out fold to avoid cross-fold logit calibration assumptions.",
                "This is a no-new-model diagnostic of whether boundary evidence can rank exact nominal spans.",
                "LitBank public evidence cannot by itself promote a production provider.",
            ],
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
