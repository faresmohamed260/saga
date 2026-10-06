"""Book-held-out hashed linear classifier over expanded nominal span candidates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from packages.narrative_compiler.litbank import LITBANK_COMMIT, convert_litbank_tsv_document


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
THRESHOLDS = (0.50, 0.70, 0.85, 0.95)
TOP_KS = (2000, 3000, 4000, 5000)
EXPANSION = 3
MAX_TOKENS = 10
HASH_FEATURES = 2**18


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


def token_lemma(token) -> str:
    lemma = token.lemma_.casefold().strip()
    return lemma if lemma and lemma != "-pron-" else token.lower_.casefold()


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
    return "9-10"


def signed_bucket(value: int) -> str:
    if value <= -3:
        return "<=-3"
    if value >= 3:
        return ">=3"
    return str(value)


def char_span(doc, start: int, end: int) -> tuple[int, int]:
    return doc[start].idx, doc[end - 1].idx + len(doc[end - 1])


def candidate_features(doc, *, start: int, end: int, chunk_start: int, chunk_end: int, root_i: int) -> list[str]:
    root = doc[root_i]
    first = doc[start]
    last = doc[end - 1]
    previous = doc[start - 1] if start > root.sent.start else None
    following = doc[end] if end < root.sent.end else None
    first_lower = first.lower_.casefold()
    root_lemma = token_lemma(root)
    span = doc[start:end]

    features = [
        "bias",
        f"head={root_lemma}",
        f"head_pos={root.pos_}",
        f"head_tag={root.tag_}",
        f"head_dep={root.dep_}",
        f"head_suffix2={root_lemma[-2:] if len(root_lemma) >= 2 else root_lemma}",
        f"head_suffix3={root_lemma[-3:] if len(root_lemma) >= 3 else root_lemma}",
        f"first={token_lemma(first)}",
        f"first_pos={first.pos_}",
        f"last={token_lemma(last)}",
        f"last_pos={last.pos_}",
        f"length={length_bucket(end - start)}",
        f"root_from_start={min(root_i - start, 5)}",
        f"root_to_end={min(end - root_i - 1, 5)}",
        f"start_delta_chunk={signed_bucket(start - chunk_start)}",
        f"end_delta_chunk={signed_bucket(end - chunk_end)}",
        f"previous={token_lemma(previous) if previous is not None else '<BOS>'}",
        f"previous_pos={previous.pos_ if previous is not None else '<BOS>'}",
        f"next={token_lemma(following) if following is not None else '<EOS>'}",
        f"next_pos={following.pos_ if following is not None else '<EOS>'}",
    ]
    if first_lower in POSSESSIVES:
        features.append("starts_possessive")
    if first_lower in DETERMINERS:
        features.append("starts_determiner")
    if start == chunk_start and end == chunk_end:
        features.append("equals_noun_chunk")
    if start <= chunk_start and end >= chunk_end:
        features.append("contains_noun_chunk")
    if start >= chunk_start and end <= chunk_end:
        features.append("inside_noun_chunk")
    if any(token.pos_ == "PROPN" for token in span):
        features.append("contains_proper")
    if any(token.pos_ == "PRON" for token in span):
        features.append("contains_pronoun")
    if root.tag_ in {"NNS", "NNPS"}:
        features.append("plural_head")
    return features


def generate_document_candidates(parsed):
    """Return deterministic unique spans with their best noun-chunk anchor."""
    anchors: dict[tuple[int, int], tuple[tuple[float, float, int], tuple[int, int, int, int, int]]] = {}
    for chunk in parsed.noun_chunks:
        root_i = chunk.root.i
        sentence = chunk.root.sent
        window_start = max(sentence.start, chunk.start - EXPANSION)
        window_end = min(sentence.end, chunk.end + EXPANSION)
        for start in range(window_start, root_i + 1):
            if parsed[start].is_punct or parsed[start].is_space:
                continue
            for end in range(root_i + 1, window_end + 1):
                if end - start > MAX_TOKENS:
                    continue
                if parsed[end - 1].is_punct or parsed[end - 1].is_space:
                    continue
                span = char_span(parsed, start, end)
                anchor_key = (
                    abs(start - chunk.start) + abs(end - chunk.end),
                    abs(((start + end - 1) / 2.0) - root_i),
                    root_i,
                )
                anchor = (start, end, chunk.start, chunk.end, root_i)
                current = anchors.get(span)
                if current is None or anchor_key < current[0]:
                    anchors[span] = (anchor_key, anchor)
    return [(span, value[1]) for span, value in sorted(anchors.items())]


def operating_row(labels, scores, *, threshold: float | None = None, top_k: int | None = None, gold_total: int):
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
    from scipy.sparse import vstack
    from sklearn.feature_extraction import FeatureHasher
    from sklearn.linear_model import SGDClassifier
    from sklearn.metrics import average_precision_score, roc_auc_score

    nlp = spacy.load(args.model, disable=["ner"])
    documents = load_documents(args.root, args.limit)
    hasher = FeatureHasher(n_features=HASH_FEATURES, input_type="string", alternate_sign=False)

    matrices = []
    label_parts = []
    document_parts = []
    gold_total = 0
    started = time.perf_counter()

    for document_index, (_document_name, document) in enumerate(documents):
        parsed = nlp(document.source.normalized_text)
        gold_spans = {
            (mention.start_offset, mention.end_offset)
            for mention in document.gold.mentions
            if mention.entity_type == "person" and mention.mention_kind == "nominal"
        }
        gold_total += len(gold_spans)
        candidates = generate_document_candidates(parsed)
        feature_rows = []
        labels = []
        for span, anchor in candidates:
            start, end, chunk_start, chunk_end, root_i = anchor
            feature_rows.append(
                candidate_features(
                    parsed,
                    start=start,
                    end=end,
                    chunk_start=chunk_start,
                    chunk_end=chunk_end,
                    root_i=root_i,
                )
            )
            labels.append(int(span in gold_spans))
        matrices.append(hasher.transform(feature_rows))
        label_parts.append(np.asarray(labels, dtype=np.int8))
        document_parts.append(np.full(len(labels), document_index, dtype=np.int16))

    x_all = vstack(matrices, format="csr")
    labels = np.concatenate(label_parts)
    document_indices = np.concatenate(document_parts)
    positive_candidates = int(labels.sum())
    scores = np.zeros(len(labels), dtype=np.float64)
    fold_rows = []

    for fold in range(args.folds):
        train_mask = document_indices % args.folds != fold
        test_mask = ~train_mask
        classifier = SGDClassifier(
            loss="log_loss",
            penalty="l2",
            alpha=1e-5,
            class_weight="balanced",
            max_iter=1000,
            tol=1e-3,
            random_state=0,
        )
        classifier.fit(x_all[train_mask], labels[train_mask])
        probabilities = classifier.predict_proba(x_all[test_mask])[:, 1]
        scores[test_mask] = probabilities
        fold_rows.append(
            {
                "fold": fold,
                "trainDocuments": int(sum(1 for i in range(len(documents)) if i % args.folds != fold)),
                "testDocuments": int(sum(1 for i in range(len(documents)) if i % args.folds == fold)),
                "trainCandidates": int(train_mask.sum()),
                "testCandidates": int(test_mask.sum()),
                "testPositiveCandidates": int(labels[test_mask].sum()),
                "iterations": int(classifier.n_iter_),
            }
        )

    threshold_rows = [
        operating_row(labels, scores, threshold=threshold, gold_total=gold_total)
        for threshold in THRESHOLDS
    ]
    top_k_rows = [
        operating_row(labels, scores, top_k=top_k, gold_total=gold_total)
        for top_k in TOP_KS
    ]
    elapsed = time.perf_counter() - started

    report = {
        "schemaVersion": "saga-v3-nominal-expanded-linear-cv-v1",
        "dataset": {
            "repository": "dbamman/litbank",
            "commit": LITBANK_COMMIT,
            "annotationLayer": "coref/tsv",
            "documentCount": len(documents),
            "license": "CC BY 4.0",
            "split": f"{args.folds}-fold document-held-out CV by sorted document index",
        },
        "candidateGenerator": {
            "name": "root_window3_10",
            "expansionTokens": EXPANSION,
            "maxSpanTokens": MAX_TOKENS,
            "candidateCount": int(len(labels)),
            "exactPositiveCandidates": positive_candidates,
            "exactRecallUpperBound": ratio(positive_candidates, gold_total),
        },
        "provider": {
            "spacyVersion": spacy.__version__,
            "model": args.model,
            "modelVersion": nlp.meta.get("version"),
            "sklearnVersion": sklearn.__version__,
            "scipyVersion": scipy.__version__,
            "classifier": "SGDClassifier(loss=log_loss,alpha=1e-5,class_weight=balanced)",
            "featureHasherDimensions": HASH_FEATURES,
            "features": "head/edge lexical+syntax, bounded span geometry, noun-chunk relation, local context",
        },
        "counts": {
            "goldPersonNominals": gold_total,
        },
        "outOfFoldRanking": {
            "averagePrecision": average_precision_score(labels, scores),
            "rocAuc": roc_auc_score(labels, scores),
        },
        "thresholds": threshold_rows,
        "topK": top_k_rows,
        "folds": fold_rows,
        "runtimeSeconds": elapsed,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
