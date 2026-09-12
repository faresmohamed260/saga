#!/usr/bin/env python3
"""Pinned BookNLP-small runner for S.A.G.A.'s local literary provider boundary.

This file intentionally contains no installation or download logic. The operator
must prepare the pinned compatibility environment, spaCy model, transformer
cache, and BookNLP model artifacts ahead of time.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.metadata
import json
import sys
from pathlib import Path

EXPECTED_PACKAGE_VERSION = "1.0.7"
MODEL = "small"
PIPELINE = "entity,quote,event,coref"
REQUIRED_MODEL_FILES = (
    "entities_google_bert_uncased_L-4_H-256_A-4-v1.0.model",
    "coref_google_bert_uncased_L-2_H-256_A-4-v1.0.model",
    "speaker_google_bert_uncased_L-8_H-256_A-4-v1.0.1.model",
)


def booknlp_version() -> str:
    return importlib.metadata.version("booknlp")


def validate_model_path(model_path: Path) -> None:
    if not model_path.is_dir():
        raise SystemExit("BookNLP model directory does not exist")
    missing = [name for name in REQUIRED_MODEL_FILES if not (model_path / name).is_file()]
    if missing:
        raise SystemExit("BookNLP model directory is incomplete")


def load_booknlp():
    # Keep stdout machine-readable/bounded. BookNLP's status output is diagnostic.
    with contextlib.redirect_stdout(sys.stderr):
        from booknlp.booknlp import BookNLP
    return BookNLP


def run_health(model_path: Path) -> int:
    validate_model_path(model_path)
    version = booknlp_version()
    load_booknlp()
    print(json.dumps({"status": "ok", "booknlpVersion": version}, separators=(",", ":")))
    return 0


def run_analysis(input_path: Path, output_dir: Path, book_id: str, model_path: Path) -> int:
    if not input_path.is_file():
        raise SystemExit("input file does not exist")
    validate_model_path(model_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    BookNLP = load_booknlp()
    model_params = {
        "pipeline": PIPELINE,
        "model": MODEL,
        "model_path": str(model_path),
    }
    with contextlib.redirect_stdout(sys.stderr):
        booknlp = BookNLP("en", model_params)
        booknlp.process(str(input_path), str(output_dir), book_id)

    print(json.dumps({
        "status": "ok",
        "booknlpVersion": booknlp_version(),
        "model": MODEL,
        "pipeline": PIPELINE,
    }, separators=(",", ":")))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--health", action="store_true")
    parser.add_argument("--input")
    parser.add_argument("--output")
    parser.add_argument("--book-id")
    parser.add_argument("--model-path", required=True)
    args = parser.parse_args()
    if args.health:
        return args
    if not args.input or not args.output or not args.book_id:
        parser.error("--input, --output and --book-id are required for analysis")
    return args


def main() -> int:
    args = parse_args()
    version = booknlp_version()
    if version != EXPECTED_PACKAGE_VERSION:
        print(
            f"BookNLP package version mismatch: expected {EXPECTED_PACKAGE_VERSION}, got {version}",
            file=sys.stderr,
        )
        return 2
    model_path = Path(args.model_path)
    if args.health:
        return run_health(model_path)
    return run_analysis(Path(args.input), Path(args.output), args.book_id, model_path)


if __name__ == "__main__":
    raise SystemExit(main())
