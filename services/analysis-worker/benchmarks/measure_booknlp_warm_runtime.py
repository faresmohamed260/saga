#!/usr/bin/env python3
"""Measure pinned BookNLP initialization and repeated warm processing.

Dedicated Phase-3B runtime evidence only. The same source is processed repeatedly
through one BookNLP instance so we can distinguish model initialization cost from
steady-state document processing before choosing a persistent transport/runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import resource
import shutil
import time

from booknlp.booknlp import BookNLP


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--metadata-out", required=True)
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()
    if args.repeats < 2 or args.repeats > 10:
        parser.error("--repeats must be between 2 and 10")
    return args


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def output_fingerprint(output_dir: Path, document_id: str) -> str:
    rows = []
    for suffix in ("tokens", "entities", "quotes"):
        path = output_dir / f"{document_id}.{suffix}"
        rows.append({"suffix": suffix, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).resolve()
    model_dir = Path(args.model_dir).resolve()
    output_root = Path(args.output_root).resolve()
    metadata_out = Path(args.metadata_out).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    metadata_out.parent.mkdir(parents=True, exist_ok=True)

    model_params = {
        "pipeline": "entity,quote,event,coref",
        "model": "small",
        "model_path": str(model_dir),
    }

    initialization_started = time.perf_counter()
    booknlp = BookNLP("en", model_params)
    initialization_seconds = time.perf_counter() - initialization_started

    repetitions = []
    for index in range(args.repeats):
        repeat_dir = output_root / f"repeat-{index + 1}"
        if repeat_dir.exists():
            shutil.rmtree(repeat_dir)
        repeat_dir.mkdir(parents=True)

        started = time.perf_counter()
        booknlp.process(str(input_path), str(repeat_dir), args.document_id)
        duration = time.perf_counter() - started
        repetitions.append(
            {
                "repeat": index + 1,
                "wallClockSeconds": duration,
                "outputFingerprint": output_fingerprint(repeat_dir, args.document_id),
            }
        )

    fingerprints = {row["outputFingerprint"] for row in repetitions}
    usage = resource.getrusage(resource.RUSAGE_SELF)
    metadata = {
        "schemaVersion": "saga-booknlp-warm-runtime-v1",
        "documentId": args.document_id,
        "inputBytes": input_path.stat().st_size,
        "initializationSeconds": initialization_seconds,
        "repetitions": repetitions,
        "warmOutputStable": len(fingerprints) == 1,
        "peakResidentMemoryMiB": usage.ru_maxrss / 1024.0,
    }
    metadata_out.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))
    return 0 if metadata["warmOutputStable"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
