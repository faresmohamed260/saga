"""Benchmark spaCy noun chunks filtered by WordNet head semantics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from packages.narrative_compiler.litbank import LITBANK_COMMIT, convert_litbank_tsv_document


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


def ratio(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def f1(precision: float, recall: float) -> float:
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def classify_head(lemma: str, *, mode: str, wn) -> bool:
    synsets = wn.synsets(lemma, pos=wn.NOUN)
    if not synsets:
        return False
    person_flags = [synset.lexname() == "noun.person" for synset in synsets]
    group_flags = [synset.lexname() == "noun.group" for synset in synsets]
    if mode == "person_first_sense":
        return person_flags[0]
    if mode == "person_any_sense":
        return any(person_flags)
    if mode == "person_majority_senses":
        return sum(person_flags) > len(person_flags) / 2
    if mode == "person_or_group_any_sense":
        return any(person or group for person, group in zip(person_flags, group_flags, strict=True))
    raise ValueError(f"unknown mode: {mode}")


def main() -> None:
    args = parse_args()
    import nltk
    import spacy
    from nltk.corpus import wordnet as wn

    nlp = spacy.load(args.model, disable=["ner"])
    documents = load_documents(args.root, args.limit)
    modes = (
        "person_first_sense",
        "person_any_sense",
        "person_majority_senses",
        "person_or_group_any_sense",
    )
    aggregate = {
        mode: {"predicted": 0, "gold": 0, "truePositive": 0}
        for mode in modes
    }

    started = time.perf_counter()
    for document in documents:
        doc = nlp(document.source.normalized_text)
        gold_spans = {
            (mention.start_offset, mention.end_offset)
            for mention in document.gold.mentions
            if mention.entity_type == "person" and mention.mention_kind == "nominal"
        }
        for mode in modes:
            predicted_spans = {
                (chunk.start_char, chunk.end_char)
                for chunk in doc.noun_chunks
                if classify_head(chunk.root.lemma_.casefold(), mode=mode, wn=wn)
            }
            aggregate[mode]["predicted"] += len(predicted_spans)
            aggregate[mode]["gold"] += len(gold_spans)
            aggregate[mode]["truePositive"] += len(predicted_spans & gold_spans)

    elapsed = time.perf_counter() - started
    results = []
    for mode in modes:
        counts = aggregate[mode]
        precision = ratio(counts["truePositive"], counts["predicted"])
        recall = ratio(counts["truePositive"], counts["gold"])
        results.append(
            {
                "mode": mode,
                **counts,
                "precision": precision,
                "recall": recall,
                "f1": f1(precision, recall),
            }
        )

    report = {
        "schemaVersion": "saga-v3-spacy-wordnet-nominal-v1",
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
            "nltkVersion": nltk.__version__,
            "wordnetVersion": wn.get_version(),
        },
        "results": results,
        "runtimeSeconds": elapsed,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
