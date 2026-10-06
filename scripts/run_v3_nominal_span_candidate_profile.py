"""Profile exact-gold coverage of noun-head anchored nominal span generators."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import time

from packages.narrative_compiler.litbank import LITBANK_COMMIT, convert_litbank_tsv_document


WORD_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")


PROFILES = {
    "noun_chunk": (0, None),
    "root_subspans_6": (0, 6),
    "root_window1_6": (1, 6),
    "root_window2_8": (2, 8),
    "root_window3_10": (3, 10),
}


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


def length_bucket(surface: str) -> str:
    length = len(WORD_RE.findall(surface))
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


def char_span(doc, start: int, end: int) -> tuple[int, int]:
    return doc[start].idx, doc[end - 1].idx + len(doc[end - 1])


def add_head_centered_spans(
    *,
    doc,
    chunk,
    expansion: int,
    max_tokens: int,
    target: set[tuple[int, int]],
) -> None:
    root_index = chunk.root.i
    sentence = chunk.root.sent
    window_start = max(sentence.start, chunk.start - expansion)
    window_end = min(sentence.end, chunk.end + expansion)

    for start in range(window_start, root_index + 1):
        if doc[start].is_punct or doc[start].is_space:
            continue
        for end in range(root_index + 1, window_end + 1):
            if end - start > max_tokens:
                continue
            if doc[end - 1].is_punct or doc[end - 1].is_space:
                continue
            target.add(char_span(doc, start, end))


def main() -> None:
    args = parse_args()
    import spacy

    nlp = spacy.load(args.model, disable=["ner"])
    documents = load_documents(args.root, args.limit)

    profile_candidates: dict[str, int] = Counter()
    profile_true_positive: dict[str, int] = Counter()
    profile_length_tp: dict[str, Counter[str]] = {
        profile: Counter() for profile in PROFILES
    }
    length_gold: Counter[str] = Counter()
    gold_total = 0

    started = time.perf_counter()
    for document in documents:
        parsed = nlp(document.source.normalized_text)
        gold_nominals = [
            mention
            for mention in document.gold.mentions
            if mention.entity_type == "person" and mention.mention_kind == "nominal"
        ]
        gold_spans = {(mention.start_offset, mention.end_offset) for mention in gold_nominals}
        gold_by_span = {
            (mention.start_offset, mention.end_offset): length_bucket(mention.surface_text)
            for mention in gold_nominals
        }
        gold_total += len(gold_spans)
        for bucket in gold_by_span.values():
            length_gold[bucket] += 1

        candidate_sets: dict[str, set[tuple[int, int]]] = {
            profile: set() for profile in PROFILES
        }
        for chunk in parsed.noun_chunks:
            candidate_sets["noun_chunk"].add((chunk.start_char, chunk.end_char))
            for profile, (expansion, max_tokens) in PROFILES.items():
                if profile == "noun_chunk":
                    continue
                add_head_centered_spans(
                    doc=parsed,
                    chunk=chunk,
                    expansion=expansion,
                    max_tokens=max_tokens or 999,
                    target=candidate_sets[profile],
                )

        for profile, candidate_spans in candidate_sets.items():
            profile_candidates[profile] += len(candidate_spans)
            matches = candidate_spans & gold_spans
            profile_true_positive[profile] += len(matches)
            for span in matches:
                profile_length_tp[profile][gold_by_span[span]] += 1

    elapsed = time.perf_counter() - started
    baseline_candidates = profile_candidates["noun_chunk"]

    results = []
    for profile in PROFILES:
        results.append(
            {
                "profile": profile,
                "candidateCount": profile_candidates[profile],
                "candidateMultiplierVsNounChunk": ratio(
                    profile_candidates[profile], baseline_candidates
                ),
                "gold": gold_total,
                "exactMatches": profile_true_positive[profile],
                "exactRecall": ratio(profile_true_positive[profile], gold_total),
                "exactRecallByLength": {
                    bucket: {
                        "gold": length_gold[bucket],
                        "exact": profile_length_tp[profile][bucket],
                        "recall": ratio(
                            profile_length_tp[profile][bucket], length_gold[bucket]
                        ),
                    }
                    for bucket in ("1", "2", "3", "4-5", "6-8", "9+")
                },
            }
        )

    report = {
        "schemaVersion": "saga-v3-nominal-span-candidate-profile-v1",
        "dataset": {
            "repository": "dbamman/litbank",
            "commit": LITBANK_COMMIT,
            "annotationLayer": "coref/tsv",
            "documentCount": len(documents),
            "license": "CC BY 4.0",
            "goldPersonNominals": gold_total,
        },
        "provider": {
            "spacyVersion": spacy.__version__,
            "model": args.model,
            "modelVersion": nlp.meta.get("version"),
            "generator": "noun-chunk roots with bounded sentence-local contiguous spans",
        },
        "results": results,
        "runtimeSeconds": elapsed,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
