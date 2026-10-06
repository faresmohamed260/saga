"""Train/test a lightweight person-nominal classifier on spaCy noun chunks.

This is qualification code only. Documents are split before feature fitting so
chunks from the same novel never cross train/dev/test boundaries.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import time

from packages.narrative_compiler.litbank import LITBANK_COMMIT, convert_litbank_tsv_document


POSSESSIVES = frozenset({"my", "your", "his", "her", "our", "their", "its"})
DETERMINERS = frozenset({"the", "a", "an", "this", "that", "these", "those"})
LEXNAMES = (
    "noun.person",
    "noun.group",
    "noun.animal",
    "noun.artifact",
    "noun.location",
    "noun.object",
    "noun.communication",
    "noun.cognition",
    "noun.act",
    "noun.event",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--model", default="en_core_web_sm")
    parser.add_argument("--seed", type=int, default=20261006)
    args = parser.parse_args()
    if not 30 <= args.limit <= 100:
        parser.error("--limit must be between 30 and 100")
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


def split_documents(documents, seed: int):
    shuffled = list(documents)
    random.Random(seed).shuffle(shuffled)
    total = len(shuffled)
    train_end = round(total * 0.70)
    dev_end = train_end + round(total * 0.15)
    return shuffled[:train_end], shuffled[train_end:dev_end], shuffled[dev_end:]


def ratio(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def f1(precision: float, recall: float) -> float:
    return 0.0 if precision + recall == 0 else 2.0 * precision * recall / (precision + recall)


def wordnet_features(lemma: str, wn) -> dict[str, object]:
    synsets = wn.synsets(lemma, pos=wn.NOUN)
    lexname_counts = Counter(synset.lexname() for synset in synsets)
    total = len(synsets)
    features: dict[str, object] = {
        "wn_has_synsets": bool(synsets),
        "wn_synset_count": min(total, 12),
        "wn_first_lexname": synsets[0].lexname() if synsets else "NONE",
        "wn_person_first": bool(synsets and synsets[0].lexname() == "noun.person"),
        "wn_person_any": lexname_counts["noun.person"] > 0,
        "wn_group_any": lexname_counts["noun.group"] > 0,
        "wn_person_majority": total > 0 and lexname_counts["noun.person"] > total / 2,
        "wn_person_ratio": 0.0 if total == 0 else lexname_counts["noun.person"] / total,
    }
    for lexname in LEXNAMES:
        features[f"wn_{lexname}_count"] = min(lexname_counts[lexname], 6)
        features[f"wn_{lexname}_any"] = lexname_counts[lexname] > 0
    return features


def chunk_features(chunk, wn) -> dict[str, object]:
    root = chunk.root
    tokens = list(chunk)
    first = tokens[0]
    features: dict[str, object] = {
        "root_lemma": root.lemma_.casefold(),
        "root_pos": root.pos_,
        "root_tag": root.tag_,
        "root_dep": root.dep_,
        "first_lemma": first.lemma_.casefold(),
        "first_pos": first.pos_,
        "starts_possessive": first.text.casefold() in POSSESSIVES,
        "starts_determiner": first.text.casefold() in DETERMINERS,
        "token_count": min(len(tokens), 8),
        "has_propn": any(token.pos_ == "PROPN" for token in tokens),
        "has_num": any(token.pos_ == "NUM" for token in tokens),
        "adjective_count": min(sum(token.pos_ == "ADJ" for token in tokens), 4),
        "noun_count": min(sum(token.pos_ in {"NOUN", "PROPN"} for token in tokens), 5),
        "is_plural": "Plur" in root.morph.get("Number"),
        "is_subject": root.dep_ in {"nsubj", "nsubjpass", "csubj"},
        "is_object": root.dep_ in {"dobj", "obj", "iobj", "pobj"},
        "is_attribute": root.dep_ in {"attr", "oprd", "appos"},
    }
    features.update(wordnet_features(root.lemma_.casefold(), wn))
    return features


def build_rows(documents, nlp, wn):
    rows = []
    gold_total = 0
    for document in documents:
        gold_spans = {
            (mention.start_offset, mention.end_offset)
            for mention in document.gold.mentions
            if mention.entity_type == "person" and mention.mention_kind == "nominal"
        }
        gold_total += len(gold_spans)
        doc = nlp(document.source.normalized_text)
        for chunk in doc.noun_chunks:
            span = (chunk.start_char, chunk.end_char)
            rows.append(
                {
                    "document": document.gold.document_id,
                    "span": span,
                    "text": chunk.text,
                    "features": chunk_features(chunk, wn),
                    "label": int(span in gold_spans),
                }
            )
    return rows, gold_total


def metrics_for(probabilities, labels, *, threshold: float, gold_total: int):
    predicted = [prob >= threshold for prob in probabilities]
    tp = sum(pred and label == 1 for pred, label in zip(predicted, labels, strict=True))
    fp = sum(pred and label == 0 for pred, label in zip(predicted, labels, strict=True))
    predicted_count = tp + fp
    precision = ratio(tp, predicted_count)
    recall = ratio(tp, gold_total)
    return {
        "threshold": threshold,
        "predicted": predicted_count,
        "truePositive": tp,
        "falsePositive": fp,
        "gold": gold_total,
        "precision": precision,
        "recall": recall,
        "f1": f1(precision, recall),
    }


def choose_threshold(probabilities, labels, gold_total: int):
    candidates = [value / 100 for value in range(10, 96, 2)]
    rows = [metrics_for(probabilities, labels, threshold=t, gold_total=gold_total) for t in candidates]
    best_f1 = max(rows, key=lambda row: (row["f1"], row["precision"], row["threshold"]))
    precision_target = [row for row in rows if row["precision"] >= 0.75]
    best_p75 = (
        max(precision_target, key=lambda row: (row["recall"], row["precision"], -row["threshold"]))
        if precision_target
        else None
    )
    return best_f1, best_p75, rows


def wordnet_first_sense_baseline(rows, gold_total: int):
    predicted = [bool(row["features"]["wn_person_first"]) for row in rows]
    labels = [row["label"] for row in rows]
    tp = sum(pred and label == 1 for pred, label in zip(predicted, labels, strict=True))
    fp = sum(pred and label == 0 for pred, label in zip(predicted, labels, strict=True))
    precision = ratio(tp, tp + fp)
    recall = ratio(tp, gold_total)
    return {
        "predicted": tp + fp,
        "truePositive": tp,
        "falsePositive": fp,
        "gold": gold_total,
        "precision": precision,
        "recall": recall,
        "f1": f1(precision, recall),
    }


def main() -> None:
    args = parse_args()
    import nltk
    import spacy
    from nltk.corpus import wordnet as wn
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    documents = load_documents(args.root, args.limit)
    train_docs, dev_docs, test_docs = split_documents(documents, args.seed)
    nlp = spacy.load(args.model, disable=["ner"])

    started = time.perf_counter()
    train_rows, train_gold = build_rows(train_docs, nlp, wn)
    dev_rows, dev_gold = build_rows(dev_docs, nlp, wn)
    test_rows, test_gold = build_rows(test_docs, nlp, wn)

    model = Pipeline(
        [
            ("vectorizer", DictVectorizer(sparse=True)),
            (
                "classifier",
                LogisticRegression(
                    C=1.0,
                    class_weight="balanced",
                    max_iter=1000,
                    solver="liblinear",
                    random_state=args.seed,
                ),
            ),
        ]
    )
    model.fit([row["features"] for row in train_rows], [row["label"] for row in train_rows])

    dev_prob = model.predict_proba([row["features"] for row in dev_rows])[:, 1]
    dev_labels = [row["label"] for row in dev_rows]
    best_f1, best_p75, dev_sweep = choose_threshold(dev_prob, dev_labels, dev_gold)

    test_prob = model.predict_proba([row["features"] for row in test_rows])[:, 1]
    test_labels = [row["label"] for row in test_rows]
    test_default = metrics_for(test_prob, test_labels, threshold=0.5, gold_total=test_gold)
    test_dev_f1 = metrics_for(
        test_prob,
        test_labels,
        threshold=best_f1["threshold"],
        gold_total=test_gold,
    )
    test_dev_p75 = (
        metrics_for(test_prob, test_labels, threshold=best_p75["threshold"], gold_total=test_gold)
        if best_p75 is not None
        else None
    )
    baseline = wordnet_first_sense_baseline(test_rows, test_gold)
    elapsed = time.perf_counter() - started

    def ids(rows):
        return [document.gold.document_id for document in rows]

    report = {
        "schemaVersion": "saga-v3-nominal-classifier-v1",
        "dataset": {
            "repository": "dbamman/litbank",
            "commit": LITBANK_COMMIT,
            "annotationLayer": "coref/tsv",
            "documentCount": len(documents),
            "license": "CC BY 4.0",
        },
        "split": {
            "seed": args.seed,
            "trainDocuments": ids(train_docs),
            "devDocuments": ids(dev_docs),
            "testDocuments": ids(test_docs),
        },
        "provider": {
            "spacyVersion": spacy.__version__,
            "model": args.model,
            "modelVersion": nlp.meta.get("version"),
            "nltkVersion": nltk.__version__,
            "wordnetVersion": wn.get_version(),
        },
        "training": {
            "trainChunks": len(train_rows),
            "trainPositiveChunks": sum(row["label"] for row in train_rows),
            "trainGoldNominals": train_gold,
            "devChunks": len(dev_rows),
            "devPositiveChunks": sum(row["label"] for row in dev_rows),
            "devGoldNominals": dev_gold,
            "testChunks": len(test_rows),
            "testPositiveChunks": sum(row["label"] for row in test_rows),
            "testGoldNominals": test_gold,
        },
        "devSelection": {
            "bestF1": best_f1,
            "bestPrecisionAtLeast075": best_p75,
            "thresholdSweep": dev_sweep,
        },
        "test": {
            "wordnetFirstSense": baseline,
            "default050": test_default,
            "devSelectedF1": test_dev_f1,
            "devSelectedPrecision075": test_dev_p75,
        },
        "runtimeSeconds": elapsed,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
