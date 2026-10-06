"""Book-held-out token classifiers for literary person-nominal boundaries."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import resource
import time

import numpy as np

from packages.narrative_compiler.litbank import LITBANK_COMMIT, convert_litbank_tsv_document


DEFAULT_THRESHOLDS = (0.50, 0.70, 0.85, 0.95)
PRECISION_TARGETS = (0.80, 0.90, 0.95, 0.97)
HASH_DIMENSIONS = 1 << 18


@dataclass(slots=True)
class ParsedDocument:
    name: str
    doc: object
    features: list[dict[str, object]]
    start_labels: np.ndarray
    end_labels: np.ndarray
    gold_char_spans: frozenset[tuple[int, int]]
    gold_token_spans: tuple[tuple[int, int], ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--model", default="en_core_web_sm")
    parser.add_argument("--max-span-length", type=int, default=16)
    parser.add_argument("--thresholds", type=float, nargs="+", default=list(DEFAULT_THRESHOLDS))
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    if not 5 <= args.limit <= 100:
        parser.error("--limit must be between 5 and 100")
    if not 2 <= args.folds <= min(10, args.limit):
        parser.error("--folds must be between 2 and min(10, limit)")
    if args.max_span_length < 1:
        parser.error("--max-span-length must be >= 1")
    if any(not 0.0 < threshold < 1.0 for threshold in args.thresholds):
        parser.error("--thresholds must be strictly between 0 and 1")
    args.thresholds = tuple(sorted(set(args.thresholds)))
    return args


def ratio(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def harmonic(precision: float, recall: float) -> float:
    return 0.0 if precision + recall == 0.0 else 2.0 * precision * recall / (precision + recall)


def feature_string(prefix: str, value: object) -> str:
    return f"{prefix}={value}"


def token_features(doc) -> list[dict[str, object]]:
    chunk_start = np.zeros(len(doc), dtype=np.int8)
    chunk_end = np.zeros(len(doc), dtype=np.int8)
    chunk_root = np.zeros(len(doc), dtype=np.int8)
    chunk_member = np.zeros(len(doc), dtype=np.int8)
    chunk_length = np.zeros(len(doc), dtype=np.int16)
    for chunk in doc.noun_chunks:
        length = len(chunk)
        chunk_start[chunk.start] = 1
        chunk_end[chunk.end - 1] = 1
        chunk_root[chunk.root.i] = 1
        for index in range(chunk.start, chunk.end):
            chunk_member[index] = 1
            chunk_length[index] = min(length, 16)

    rows: list[dict[str, object]] = []
    for token in doc:
        row: dict[str, object] = {
            "bias": 1.0,
            feature_string("lower", token.lower_): 1.0,
            feature_string("lemma", token.lemma_.lower()): 1.0,
            feature_string("pos", token.pos_): 1.0,
            feature_string("tag", token.tag_): 1.0,
            feature_string("dep", token.dep_): 1.0,
            feature_string("shape", token.shape_): 1.0,
            feature_string("prefix2", token.lower_[:2]): 1.0,
            feature_string("suffix2", token.lower_[-2:]): 1.0,
            feature_string("suffix3", token.lower_[-3:]): 1.0,
            feature_string("head_pos", token.head.pos_): 1.0,
            feature_string("head_dep", token.head.dep_): 1.0,
            feature_string("head_lower", token.head.lower_): 1.0,
            feature_string("ent_iob", token.ent_iob_): 1.0,
            feature_string("ent_type", token.ent_type_ or "NONE"): 1.0,
            feature_string("len", min(len(token.text), 12)): 1.0,
            "is_alpha": float(token.is_alpha),
            "is_title": float(token.is_title),
            "is_upper": float(token.is_upper),
            "is_stop": float(token.is_stop),
            "is_punct": float(token.is_punct),
            "like_num": float(token.like_num),
            "has_left": float(bool(list(token.lefts))),
            "has_right": float(bool(list(token.rights))),
            "left_children": float(min(sum(1 for _ in token.lefts), 5)),
            "right_children": float(min(sum(1 for _ in token.rights), 5)),
            "noun_chunk_member": float(chunk_member[token.i]),
            "noun_chunk_start": float(chunk_start[token.i]),
            "noun_chunk_end": float(chunk_end[token.i]),
            "noun_chunk_root": float(chunk_root[token.i]),
            feature_string("noun_chunk_len", int(chunk_length[token.i])): 1.0,
        }
        for offset in (-2, -1, 1, 2):
            neighbor_index = token.i + offset
            side = f"ctx{offset:+d}"
            if 0 <= neighbor_index < len(doc):
                neighbor = doc[neighbor_index]
                row[feature_string(f"{side}_lower", neighbor.lower_)] = 1.0
                row[feature_string(f"{side}_pos", neighbor.pos_)] = 1.0
                row[feature_string(f"{side}_tag", neighbor.tag_)] = 1.0
                row[feature_string(f"{side}_dep", neighbor.dep_)] = 1.0
                row[feature_string(f"{side}_shape", neighbor.shape_)] = 1.0
            else:
                row[feature_string(side, "BOUNDARY")] = 1.0
        rows.append(row)
    return rows


def load_documents(root: Path, limit: int, model: str) -> list[ParsedDocument]:
    import spacy

    annotation_dir = root.resolve() / "coref" / "tsv"
    paths = sorted(annotation_dir.glob("*.ann"))[:limit]
    if not paths:
        raise RuntimeError("no LitBank coref/tsv annotations found")

    source_rows = []
    for path in paths:
        converted = convert_litbank_tsv_document(
            document_id=path.stem,
            annotation=path.read_text(encoding="utf-8"),
            text=(annotation_dir / f"{path.stem}.txt").read_text(encoding="utf-8"),
        )
        gold = frozenset(
            (mention.start_offset, mention.end_offset)
            for mention in converted.gold.mentions
            if mention.entity_type == "person" and mention.mention_kind == "nominal"
        )
        source_rows.append((path.stem, converted.source.normalized_text, gold))

    nlp = spacy.load(model)
    parsed: list[ParsedDocument] = []
    texts = [text for _name, text, _gold in source_rows]
    for (name, _text, gold), doc in zip(source_rows, nlp.pipe(texts, batch_size=8)):
        start_labels = np.zeros(len(doc), dtype=np.int8)
        end_labels = np.zeros(len(doc), dtype=np.int8)
        token_spans = []
        for start, end in sorted(gold):
            span = doc.char_span(start, end, alignment_mode="strict")
            if span is None:
                raise RuntimeError(f"unaligned LitBank nominal span in {name}: {(start, end)}")
            start_labels[span.start] = 1
            end_labels[span.end - 1] = 1
            token_spans.append((span.start, span.end - 1))
        parsed.append(
            ParsedDocument(
                name=name,
                doc=doc,
                features=token_features(doc),
                start_labels=start_labels,
                end_labels=end_labels,
                gold_char_spans=gold,
                gold_token_spans=tuple(token_spans),
            )
        )
    return parsed


def concat_features(documents, indices):
    return [row for index in indices for row in documents[index].features]


def concat_labels(documents, indices, attr: str) -> np.ndarray:
    return np.concatenate([getattr(documents[index], attr) for index in indices])


def make_classifier(seed: int):
    from sklearn.linear_model import SGDClassifier

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


def precision_target_rows(labels: np.ndarray, scores: np.ndarray):
    from sklearn.metrics import precision_recall_curve

    precision, recall, thresholds = precision_recall_curve(labels, scores)
    rows = []
    for target in PRECISION_TARGETS:
        valid = np.flatnonzero(precision[:-1] >= target)
        if valid.size == 0:
            rows.append({"precisionTarget": target, "achieved": False})
            continue
        best_index = int(valid[np.argmax(recall[valid])])
        rows.append(
            {
                "precisionTarget": target,
                "achieved": True,
                "precision": float(precision[best_index]),
                "recall": float(recall[best_index]),
                "threshold": float(thresholds[best_index]),
            }
        )
    return rows


def rank_metrics(labels: np.ndarray, scores: np.ndarray):
    from sklearn.metrics import average_precision_score, roc_auc_score

    return {
        "averagePrecision": float(average_precision_score(labels, scores)),
        "rocAuc": float(roc_auc_score(labels, scores)),
        "positiveCount": int(labels.sum()),
        "candidateCount": int(labels.size),
        "precisionTargets": precision_target_rows(labels, scores),
    }


def binary_metric(labels: np.ndarray, scores: np.ndarray, threshold: float):
    predicted = scores >= threshold
    true_positive = int(np.logical_and(predicted, labels == 1).sum())
    predicted_count = int(predicted.sum())
    gold = int(labels.sum())
    precision = ratio(true_positive, predicted_count)
    recall = ratio(true_positive, gold)
    return {
        "threshold": threshold,
        "predicted": predicted_count,
        "truePositive": true_positive,
        "gold": gold,
        "precision": precision,
        "recall": recall,
        "f1": harmonic(precision, recall),
    }


def exact_pair_metrics(documents, test_indices, per_doc_scores, threshold: float, max_span_length: int):
    predicted_count = 0
    true_positive = 0
    gold_count = 0
    both_selected_gold = 0
    for index in test_indices:
        document = documents[index]
        start_scores, end_scores = per_doc_scores[index]
        starts = np.flatnonzero(start_scores >= threshold)
        end_mask = end_scores >= threshold
        predicted = set()
        for start in starts:
            stop = min(len(document.doc), start + max_span_length)
            for end in range(start, stop):
                if end_mask[end]:
                    span = document.doc[start : end + 1]
                    predicted.add((span.start_char, span.end_char))
        predicted_count += len(predicted)
        true_positive += len(predicted & document.gold_char_spans)
        gold_count += len(document.gold_char_spans)
        for start, end in document.gold_token_spans:
            if start_scores[start] >= threshold and end_scores[end] >= threshold:
                both_selected_gold += 1
    precision = ratio(true_positive, predicted_count)
    recall = ratio(true_positive, gold_count)
    return {
        "threshold": threshold,
        "candidateSpans": predicted_count,
        "truePositive": true_positive,
        "gold": gold_count,
        "precision": precision,
        "recall": recall,
        "f1": harmonic(precision, recall),
        "bothBoundarySelectedGold": both_selected_gold,
        "bothBoundarySelectedRecallCeiling": ratio(both_selected_gold, gold_count),
    }


def main() -> None:
    args = parse_args()
    import spacy
    import sklearn
    from sklearn.feature_extraction import FeatureHasher

    started = time.perf_counter()
    documents = load_documents(args.root, args.limit, args.model)
    parse_seconds = time.perf_counter() - started

    all_start_labels = []
    all_end_labels = []
    all_start_scores = []
    all_end_scores = []
    fold_rows = []
    per_doc_scores: dict[int, tuple[np.ndarray, np.ndarray]] = {}

    for fold in range(args.folds):
        fold_started = time.perf_counter()
        train_indices = [index for index in range(len(documents)) if index % args.folds != fold]
        test_indices = [index for index in range(len(documents)) if index % args.folds == fold]
        hasher = FeatureHasher(n_features=HASH_DIMENSIONS, input_type="dict", alternate_sign=False)
        train_features = hasher.transform(concat_features(documents, train_indices))
        test_features = hasher.transform(concat_features(documents, test_indices))
        y_start_train = concat_labels(documents, train_indices, "start_labels")
        y_end_train = concat_labels(documents, train_indices, "end_labels")
        y_start_test = concat_labels(documents, test_indices, "start_labels")
        y_end_test = concat_labels(documents, test_indices, "end_labels")

        start_model = make_classifier(args.seed + fold * 2)
        end_model = make_classifier(args.seed + fold * 2 + 1)
        start_model.fit(train_features, y_start_train)
        end_model.fit(train_features, y_end_train)
        start_scores = start_model.predict_proba(test_features)[:, 1]
        end_scores = end_model.predict_proba(test_features)[:, 1]

        cursor = 0
        for index in test_indices:
            length = len(documents[index].doc)
            per_doc_scores[index] = (
                start_scores[cursor : cursor + length],
                end_scores[cursor : cursor + length],
            )
            cursor += length

        all_start_labels.append(y_start_test)
        all_end_labels.append(y_end_test)
        all_start_scores.append(start_scores)
        all_end_scores.append(end_scores)
        fold_rows.append(
            {
                "fold": fold,
                "trainDocuments": len(train_indices),
                "testDocuments": len(test_indices),
                "trainTokens": int(train_features.shape[0]),
                "testTokens": int(test_features.shape[0]),
                "start": rank_metrics(y_start_test, start_scores),
                "end": rank_metrics(y_end_test, end_scores),
                "runtimeSeconds": time.perf_counter() - fold_started,
            }
        )

    start_labels = np.concatenate(all_start_labels)
    end_labels = np.concatenate(all_end_labels)
    start_scores = np.concatenate(all_start_scores)
    end_scores = np.concatenate(all_end_scores)
    all_indices = list(range(len(documents)))
    threshold_rows = []
    for threshold in args.thresholds:
        threshold_rows.append(
            {
                "threshold": threshold,
                "start": binary_metric(start_labels, start_scores, threshold),
                "end": binary_metric(end_labels, end_scores, threshold),
                "spanCandidates": exact_pair_metrics(
                    documents,
                    all_indices,
                    per_doc_scores,
                    threshold,
                    args.max_span_length,
                ),
            }
        )

    runtime = time.perf_counter() - started
    peak_rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    output = {
        "schemaVersion": "saga-v3-nominal-token-boundary-cv-v1",
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
            "family": "hashed linear token-boundary classifiers",
            "classifier": "SGDClassifier(loss=log_loss, class_weight=balanced, average=True)",
            "features": "local lexical + POS/tag/dependency + head + NER + noun-chunk geometry",
            "hashDimensions": HASH_DIMENSIONS,
            "spacyVersion": spacy.__version__,
            "spacyModel": args.model,
            "sklearnVersion": sklearn.__version__,
            "device": "cpu",
            "maxSpanLengthTokens": args.max_span_length,
            "thresholds": list(args.thresholds),
        },
        "outOfFold": {
            "start": rank_metrics(start_labels, start_scores),
            "end": rank_metrics(end_labels, end_scores),
            "thresholds": threshold_rows,
        },
        "folds": fold_rows,
        "resources": {
            "parseSeconds": parse_seconds,
            "runtimeSeconds": runtime,
            "peakRssMb": peak_rss_mb,
            "peakVramMb": None,
            "tokensPerSecond": ratio(sum(len(document.doc) for document in documents), runtime),
        },
        "decisionScope": {
            "publicEvidenceOnly": True,
            "productionAdopted": False,
            "canonicalIdentityThreshold": False,
            "notes": [
                "This benchmark evaluates nominal boundary evidence only, not canonical identity.",
                "Each book is scored only by models trained on other books.",
                "LitBank public evidence cannot by itself promote a production provider.",
                "Span-candidate rows enumerate only start/end pairs within the configured maximum length.",
            ],
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
