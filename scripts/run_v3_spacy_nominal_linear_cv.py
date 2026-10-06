"""Book-held-out linear person-nominal classifier over spaCy noun chunks."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
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


@dataclass(frozen=True)
class Candidate:
    document_index: int
    start: int
    end: int
    label: int
    features: dict[str, object]


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


def length_bucket(length: int) -> str:
    if length <= 1:
        return "1"
    if length == 2:
        return "2"
    if length == 3:
        return "3"
    if length <= 5:
        return "4-5"
    return "6+"


def token_text(token) -> str:
    lemma = token.lemma_.casefold().strip()
    return lemma if lemma and lemma != "-pron-" else token.lower_.casefold()


def features_for(doc, chunk) -> dict[str, object]:
    root = chunk.root
    first = chunk[0]
    last = chunk[-1]
    first_lower = first.lower_.casefold()
    previous = doc[chunk.start - 1] if chunk.start > 0 else None
    following = doc[chunk.end] if chunk.end < len(doc) else None
    head_lemma = token_text(root)

    return {
        "head_lemma": head_lemma,
        "head_pos": root.pos_,
        "head_tag": root.tag_,
        "head_dep": root.dep_,
        "head_suffix2": head_lemma[-2:] if len(head_lemma) >= 2 else head_lemma,
        "head_suffix3": head_lemma[-3:] if len(head_lemma) >= 3 else head_lemma,
        "first_lemma": token_text(first),
        "last_lemma": token_text(last),
        "length_bucket": length_bucket(len(chunk)),
        "starts_possessive": first_lower in POSSESSIVES,
        "starts_determiner": first_lower in DETERMINERS,
        "root_is_plural": root.tag_ in {"NNS", "NNPS"},
        "contains_proper": any(token.pos_ == "PROPN" for token in chunk),
        "contains_pronoun": any(token.pos_ == "PRON" for token in chunk),
        "previous_lemma": token_text(previous) if previous is not None else "<BOS>",
        "previous_pos": previous.pos_ if previous is not None else "<BOS>",
        "next_lemma": token_text(following) if following is not None else "<EOS>",
        "next_pos": following.pos_ if following is not None else "<EOS>",
    }


def main() -> None:
    args = parse_args()

    import spacy
    import sklearn
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score, roc_auc_score

    nlp = spacy.load(args.model, disable=["ner"])
    documents = load_documents(args.root, args.limit)

    started = time.perf_counter()
    candidates: list[Candidate] = []
    gold_total = 0
    document_names: list[str] = []

    for document_index, (document_name, document) in enumerate(documents):
        document_names.append(document_name)
        gold_spans = {
            (mention.start_offset, mention.end_offset)
            for mention in document.gold.mentions
            if mention.entity_type == "person" and mention.mention_kind == "nominal"
        }
        gold_total += len(gold_spans)

        parsed = nlp(document.source.normalized_text)
        seen_spans: set[tuple[int, int]] = set()
        for chunk in parsed.noun_chunks:
            span = (chunk.start_char, chunk.end_char)
            if span in seen_spans:
                continue
            seen_spans.add(span)
            candidates.append(
                Candidate(
                    document_index=document_index,
                    start=chunk.start_char,
                    end=chunk.end_char,
                    label=int(span in gold_spans),
                    features=features_for(parsed, chunk),
                )
            )

    candidate_positive = sum(candidate.label for candidate in candidates)
    scores = [0.0] * len(candidates)
    fold_rows = []

    for fold in range(args.folds):
        train_indices = [
            index
            for index, candidate in enumerate(candidates)
            if candidate.document_index % args.folds != fold
        ]
        test_indices = [
            index
            for index, candidate in enumerate(candidates)
            if candidate.document_index % args.folds == fold
        ]
        if not train_indices or not test_indices:
            raise RuntimeError(f"empty train/test split for fold {fold}")

        vectorizer = DictVectorizer(sparse=True)
        x_train = vectorizer.fit_transform([candidates[index].features for index in train_indices])
        y_train = [candidates[index].label for index in train_indices]
        x_test = vectorizer.transform([candidates[index].features for index in test_indices])
        y_test = [candidates[index].label for index in test_indices]

        classifier = LogisticRegression(
            C=1.0,
            class_weight="balanced",
            max_iter=500,
            random_state=0,
            solver="liblinear",
        )
        classifier.fit(x_train, y_train)
        probabilities = classifier.predict_proba(x_test)[:, 1]
        for index, probability in zip(test_indices, probabilities, strict=True):
            scores[index] = float(probability)

        fold_rows.append(
            {
                "fold": fold,
                "trainDocuments": sum(1 for i in range(len(documents)) if i % args.folds != fold),
                "testDocuments": sum(1 for i in range(len(documents)) if i % args.folds == fold),
                "trainCandidates": len(train_indices),
                "testCandidates": len(test_indices),
                "testPositiveCandidates": sum(y_test),
                "featureCount": len(vectorizer.feature_names_),
            }
        )

    labels = [candidate.label for candidate in candidates]
    threshold_rows = []
    for threshold in THRESHOLDS:
        predicted_indices = [index for index, score in enumerate(scores) if score >= threshold]
        true_positive = sum(labels[index] for index in predicted_indices)
        predicted = len(predicted_indices)
        precision = ratio(true_positive, predicted)
        recall = ratio(true_positive, gold_total)
        threshold_rows.append(
            {
                "threshold": threshold,
                "predicted": predicted,
                "truePositive": true_positive,
                "falsePositive": predicted - true_positive,
                "precision": precision,
                "recall": recall,
                "f1": f1(precision, recall),
            }
        )

    elapsed = time.perf_counter() - started
    report = {
        "schemaVersion": "saga-v3-spacy-nominal-linear-cv-v1",
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
            "classifier": "LogisticRegression(C=1,class_weight=balanced,solver=liblinear)",
            "features": "head/edge lemmas, POS/tag/dependency, noun-chunk length/start shape, local POS/lemma context",
        },
        "counts": {
            "goldPersonNominals": gold_total,
            "nounChunkCandidates": len(candidates),
            "exactPositiveCandidates": candidate_positive,
        },
        "candidateBoundaryUpperBound": {
            "exactRecall": ratio(candidate_positive, gold_total),
        },
        "outOfFoldRanking": {
            "averagePrecision": average_precision_score(labels, scores),
            "rocAuc": roc_auc_score(labels, scores),
        },
        "thresholds": threshold_rows,
        "folds": fold_rows,
        "runtimeSeconds": elapsed,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
