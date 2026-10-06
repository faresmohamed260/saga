"""Profile the structural shape of LitBank person-nominal mentions."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re

from packages.narrative_compiler.litbank import LITBANK_COMMIT, convert_litbank_tsv_document


WORD_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")
POSSESSIVES = frozenset({"my", "your", "his", "her", "our", "their", "its"})
DEFINITE = frozenset({"the"})
INDEFINITE = frozenset({"a", "an"})
DEMONSTRATIVES = frozenset({"this", "that", "these", "those"})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=100)
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


def start_class(tokens: list[str]) -> str:
    if not tokens:
        return "empty"
    first = tokens[0].casefold()
    if first in POSSESSIVES:
        return "possessive"
    if first in DEFINITE:
        return "definite"
    if first in INDEFINITE:
        return "indefinite"
    if first in DEMONSTRATIVES:
        return "demonstrative"
    return "other"


def ratio(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def main() -> None:
    args = parse_args()
    documents = load_documents(args.root, args.limit)

    length_counts: Counter[int] = Counter()
    start_counts: Counter[str] = Counter()
    head_counts: Counter[str] = Counter()
    surface_counts: Counter[str] = Counter()
    first_counts: Counter[str] = Counter()
    initial_capital = 0
    possessive_started = 0
    determiner_started = 0
    single_token = 0
    total = 0

    for document in documents:
        for mention in document.gold.mentions:
            if mention.entity_type != "person" or mention.mention_kind != "nominal":
                continue
            tokens = WORD_RE.findall(mention.surface_text)
            if not tokens:
                continue
            total += 1
            length_counts[len(tokens)] += 1
            category = start_class(tokens)
            start_counts[category] += 1
            first_counts[tokens[0].casefold()] += 1
            head_counts[tokens[-1].casefold()] += 1
            surface_counts[" ".join(token.casefold() for token in tokens)] += 1
            if len(tokens) == 1:
                single_token += 1
            if category == "possessive":
                possessive_started += 1
            if category in {"definite", "indefinite", "demonstrative"}:
                determiner_started += 1
            stripped = mention.surface_text.lstrip()
            if stripped and stripped[0].isupper():
                initial_capital += 1

    report = {
        "schemaVersion": "saga-v3-litbank-nominal-profile-v1",
        "dataset": {
            "repository": "dbamman/litbank",
            "commit": LITBANK_COMMIT,
            "annotationLayer": "coref/tsv",
            "documentCount": len(documents),
            "license": "CC BY 4.0",
        },
        "personNominalCount": total,
        "shape": {
            "singleTokenCount": single_token,
            "singleTokenRate": ratio(single_token, total),
            "initialCapitalCount": initial_capital,
            "initialCapitalRate": ratio(initial_capital, total),
            "possessiveStartedCount": possessive_started,
            "possessiveStartedRate": ratio(possessive_started, total),
            "determinerStartedCount": determiner_started,
            "determinerStartedRate": ratio(determiner_started, total),
            "lengthCounts": {str(key): value for key, value in sorted(length_counts.items())},
            "startClassCounts": dict(sorted(start_counts.items())),
        },
        "topHeads": head_counts.most_common(60),
        "topFirstTokens": first_counts.most_common(40),
        "topNormalizedSurfaces": surface_counts.most_common(40),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
